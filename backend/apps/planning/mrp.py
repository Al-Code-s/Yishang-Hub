"""MRP 计算服务（任务书 10.6，阶段 3 第二步）。

算法（逐层净算，结果可解释）：

1. **顶层需求**：状态为「已批准 / 部分发货」的销售订单行，未发货量 = `quantity - shipped_quantity`；
   需求日期取订单行 `expected_date`，为空回落到订单 `expected_date`，再为空回落到当前业务日期。
2. **低层码排序**：先按生效 BOM 静态遍历出每个物料的**最低层级**，
   再按层级升序净算 —— 保证净算某物料时，它来自所有上层父件的需求都已到齐（标准 MRP 做法）。
3. **净算**：逐物料、逐时间分段滚动：
   `结余 = 上段结余 + 本段供给 − 本段需求`；为负即产生**净需求**，并把结余置 0（逐批净算 lot-for-lot）。
   现有可用库存计入期初（`on_hand − frozen − reserved`），采购在途按预计到货日期计入对应分段，
   MES 已下达 / 在制的生产工单未完工数量按计划完工日期计入对应分段（在制供给）。
4. **展开**：**自制品**（有生效 BOM，或分类为成品/半成品）的净需求按 BOM 行
   `gross_quantity`（含损耗，后端已按 6 位小数舍入）展开为下层的**毛需求**；
   因此子件需求来自父件**净需求**而非毛需求，不会对已有库存重复展开。
5. **建议**：净需求 → 自制品出生产建议、其余出采购建议；建议交期 = 需求分段日期。
6. **重算**：每次运算是**新增一条运行记录**，历史运行与已转单建议保持原样。

明确不做（首版，见 `docs/progress.md` 第十五节与 `docs/assumptions.md` §四之六）：

* 提前期与批量规则 —— 逐批净算，建议交期 = 需求分段日期；
* 独立需求 / 生产计划录入 —— 需求来源只有销售订单（生产工单本身是供给，不是需求）；
* 在制供给只取 **MES 已下达 / 生产中的工单**未完工数量；草稿工单不算承诺，不进入供给；
* 替代料替代与安全库存缓冲 —— 替代料行不参与展开、不作供给。
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date, datetime, time
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from django.db import transaction
from django.db.models import F, Sum
from django.utils import timezone

from apps.core.exceptions import StateConflict, ValidationFailed
from apps.core.models import AuditAction
from apps.core.permissions import require_codes
from apps.core.services import (
    build_changes,
    business_timezone,
    generate_code,
    publish_event,
    record_audit,
)
from apps.integration.models import DocumentLink, DocumentRelation
from apps.masterdata.models import Material, Sku
from apps.planning import services
from apps.planning.models import (
    BomLineType,
    MrpBucket,
    MrpDemandLine,
    MrpDemandSource,
    MrpRun,
    MrpRunStatus,
    MrpSuggestion,
    MrpSuggestionStatus,
    MrpSuggestionType,
    MrpSupplyLine,
    MrpSupplySource,
    mrp_bucket_date,
)
from apps.procurement.models import OrderStatus as PurchaseOrderStatus
from apps.procurement.models import PurchaseOrderLine
from apps.sales.models import SalesOrderLine, SalesOrderStatus
from apps.wms.models import InventoryBalance, QualityStatus

logger = logging.getLogger("yishang.planning")

MRP_CODE_RULE = "MRP"
EVENT_RUN_COMPLETED = "planning.mrp.completed"
EVENT_SUGGESTION_CONVERTED = "planning.mrp.suggestion_converted"
AGGREGATE_RUN = "planning.MrpRun"
AGGREGATE_SUGGESTION = "planning.MrpSuggestion"

ZERO = Decimal("0")
QUANT = Decimal("0.000001")
MAX_LEVEL = 10
#: 运行 MRP 时未指定区间的默认天数（缺省为「今天起 90 天」）
DEFAULT_HORIZON_DAYS = 90

#: 需要生产的物料分类（成品 / 半成品）；其余按采购处理
MANUFACTURED_CATEGORY_TYPES = ("finished", "semifinished")


def _q(value: Any) -> Decimal:
    """数量统一按 6 位小数 ROUND_HALF_UP 舍入（唯一舍入点）。"""
    return Decimal(value or 0).quantize(QUANT, rounding=ROUND_HALF_UP)


def _sku_of_material(material: Material) -> Sku | None:
    """成品 SKU 与库存物料一对一（任务书 9.2），这里反过来找 SKU。"""
    return (
        Sku.objects.select_related("style")
        .filter(material_id=material.pk, is_active=True)
        .first()
    )


def _explodable_bom(company: Any, material: Material, sku: Any = None) -> Any:
    """返回该物料可展开的生效 BOM；不可自制返回 None。

    解析规则：物料需能对应到一个 SKU（成品 SKU ↔ 库存物料一对一）；
    先找 SKU 专属 BOM，找不到再回落款式通用 BOM（`services.get_effective_bom_for`）。
    """
    if sku is None:
        sku = _sku_of_material(material)
    if sku is None:
        return None
    return services.get_effective_bom_for(company, sku.style_id, sku.pk)


def _suggestion_type(material: Material, bom: Any) -> str:
    if bom is not None:
        return MrpSuggestionType.PRODUCTION
    category = getattr(material, "category", None)
    if category is not None and category.category_type in MANUFACTURED_CATEGORY_TYPES:
        return MrpSuggestionType.PRODUCTION
    return MrpSuggestionType.PURCHASE


def _collect_sales_demands(
    *, company: Any, horizon_start: date, horizon_end: date, warehouse: Any = None
) -> list[dict[str, Any]]:
    """顶层需求：销售订单未发货量（任务书 10.6「销售需求」）。

    * 只取「已批准 / 部分发货」的订单：草稿、审核中不占用供给，已取消/已驳回/已关闭不产生需求。
    * 逾期需求（需求日期早于区间起点）计入**第一个分段**，而不是被丢掉。
    * 订单已占用库存时，占用部分已在可用量里扣除，因此**不会**被当成自由供给重复使用。
    """
    queryset = (
        SalesOrderLine.objects.select_related("order", "material", "sku", "sku__style", "uom")
        .filter(
            order__company=company,
            order__status__in=(SalesOrderStatus.APPROVED, SalesOrderStatus.PARTIALLY_SHIPPED),
            quantity__gt=F("shipped_quantity"),
        )
        .order_by("order__expected_date", "order_id", "line_no")
    )
    if warehouse is not None:
        queryset = queryset.filter(order__warehouse=warehouse)

    rows: list[dict[str, Any]] = []
    for line in queryset:
        remaining = _q(line.quantity - line.shipped_quantity)
        if remaining <= ZERO:
            continue
        due = line.expected_date or line.order.expected_date or line.order.order_date
        if due is None:
            due = horizon_start
        if due > horizon_end:
            continue
        rows.append(
            {
                "material": line.material,
                "sku": line.sku,
                "style": line.sku.style if line.sku_id else None,
                "warehouse": line.order.warehouse,
                "quantity": remaining,
                "due_date": due,
                "level_hint": 0,
                "source_type": MrpDemandSource.SALES_ORDER,
                "source_id": str(line.order_id),
                "source_no": line.order.order_no,
                "source_line_no": line.line_no,
                "path": f"{line.order.order_no}#{line.line_no} > {line.material.code}",
                "note": "",
            }
        )
    return rows

def _on_hand_supplies(
    *, company: Any, horizon_start: date, bucket: str, warehouse: Any = None
) -> dict[int, list[dict[str, Any]]]:
    """现有可用库存：`on_hand − frozen − reserved`（冻结与占用不作为自由供给）。"""
    queryset = InventoryBalance.objects.filter(
        company=company, quality_status=QualityStatus.QUALIFIED
    )
    if warehouse is not None:
        queryset = queryset.filter(warehouse=warehouse)
    rows = (
        queryset.annotate(available=F("on_hand") - F("frozen") - F("reserved"))
        .values("material_id", "warehouse_id")
        .annotate(total=Sum("available"))
        .order_by("material_id")
    )
    result: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        quantity = _q(row["total"])
        if quantity <= ZERO:
            continue
        result[row["material_id"]].append(
            {
                "source_type": MrpSupplySource.ON_HAND,
                "warehouse_id": row["warehouse_id"],
                "quantity": quantity,
                "available_date": horizon_start,
                "bucket_date": mrp_bucket_date(horizon_start, bucket),
                "reference_type": "wms.InventoryBalance",
                "reference_id": str(row["warehouse_id"] or ""),
                "reference_no": "",
                "remark": "合格库存可用量（不含冻结与占用）",
            }
        )
    return result


def _on_order_supplies(
    *,
    company: Any,
    horizon_start: date,
    horizon_end: date,
    bucket: str,
    warehouse: Any = None,
) -> dict[int, list[dict[str, Any]]]:
    """采购在途：已批准 / 部分收货的采购订单行未收数量，按预计到货日期计入。"""
    queryset = (
        PurchaseOrderLine.objects.select_related("order", "material")
        .filter(
            order__company=company,
            order__status__in=(
                PurchaseOrderStatus.APPROVED,
                PurchaseOrderStatus.PARTIALLY_RECEIVED,
            ),
            quantity__gt=F("received_quantity"),
        )
        .order_by("expected_date", "order_id", "line_no")
    )
    result: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for line in queryset:
        quantity = _q(line.quantity - line.received_quantity)
        if quantity <= ZERO:
            continue
        expected = line.expected_date or line.order.expected_date or line.order.order_date
        if expected is None or expected > horizon_end:
            continue
        if warehouse is not None:
            effective = line.warehouse_id or line.order.warehouse_id
            if effective != getattr(warehouse, "pk", warehouse):
                continue
        result[line.material_id].append(
            {
                "source_type": MrpSupplySource.ON_ORDER,
                "warehouse_id": line.warehouse_id or line.order.warehouse_id,
                "quantity": quantity,
                "available_date": expected,
                "bucket_date": mrp_bucket_date(max(expected, horizon_start), bucket),
                "reference_type": "procurement.PurchaseOrder",
                "reference_id": str(line.order_id),
                "reference_no": line.order.order_no,
                "remark": f"采购订单第 {line.line_no} 行未收数量",
            }
        )
    return result


def _in_progress_supplies(
    *,
    company: Any,
    horizon_start: date,
    horizon_end: date,
    bucket: str,
    warehouse: Any = None,
) -> dict[int, list[dict[str, Any]]]:
    """在制供给：MES 已下达 / 生产中工单的**未完工数量**。

    只认「已下达」与「生产中」两种状态：草稿工单还没有冻结 BOM 与工艺快照，
    把它算成供给等于把不存在的能力当成可用库存（任务书 20.3 不用模拟结果冒充真实）。
    指定仓库筛选时不产生在制供给——工单只承诺产出物料，不承诺产出入到哪个仓库。
    """
    from apps.mes.models import ProductionOrder, ProductionOrderStatus

    queryset = (
        ProductionOrder.objects.select_related("product_material")
        .filter(
            company=company,
            is_active=True,
            status__in=(ProductionOrderStatus.RELEASED, ProductionOrderStatus.IN_PROGRESS),
            product_material__isnull=False,
        )
        .order_by("planned_end", "id")
    )
    result: dict[int, list[dict[str, Any]]] = defaultdict(list)
    if warehouse is not None:
        return result
    for order in queryset:
        quantity = _q(order.quantity - order.completed_quantity)
        if quantity <= ZERO:
            continue
        if order.planned_end is not None:
            expected_date = order.planned_end.astimezone(business_timezone()).date()
            if expected_date > horizon_end:
                continue
        else:
            expected_date = horizon_start
        result[order.product_material_id].append(
            {
                "source_type": MrpSupplySource.IN_PROGRESS,
                "warehouse_id": None,
                "quantity": quantity,
                "available_date": expected_date,
                "bucket_date": mrp_bucket_date(max(expected_date, horizon_start), bucket),
                "reference_type": "mes.ProductionOrder",
                "reference_id": str(order.pk),
                "reference_no": order.order_no,
                "remark": f"生产工单 {order.order_no} 未完工数量",
            }
        )
    return result


def _build_graph(
    *, company: Any, roots: list[dict[str, Any]]
) -> tuple[dict[int, Any], dict[int, list[Any]], dict[int, int], dict[int, Material]]:
    """按生效 BOM 静态遍历，得到：物料 → BOM、物料 → 子件行、物料 → 最低层级、物料表。

    循环 BOM 在此**直接拒绝**（任务书 10.6「循环 BOM 检查」），
    而不是靠层级上限默默截断。
    """
    bom_of: dict[int, Any] = {}
    edges: dict[int, list[Any]] = defaultdict(list)
    low_level: dict[int, int] = {}
    materials: dict[int, Material] = {}
    visiting: list[str] = []

    def walk(material: Material, sku: Any, depth: int, ancestors: frozenset[int]) -> None:
        if depth > MAX_LEVEL:
            raise ValidationFailed(
                f"BOM 层级超过 {MAX_LEVEL} 层，疑似存在循环或数据异常。", code="BOM_TOO_DEEP"
            )
        material_id = material.pk
        materials[material_id] = material
        previous = low_level.get(material_id)
        low_level[material_id] = depth if previous is None else max(previous, depth)
        if material_id not in bom_of:
            bom = _explodable_bom(company, material, sku)
            bom_of[material_id] = bom
            if bom is not None:
                lines = list(
                    bom.lines.select_related("material")
                    .filter(line_type=BomLineType.NORMAL)
                    .order_by("line_no")
                )
                edges[material_id] = lines
                for line in lines:
                    child = line.material
                    if child.pk in ancestors or child.pk == material_id:
                        chain = " > ".join([*visiting, material.code, child.code])
                        raise ValidationFailed(
                            f"BOM 存在循环引用：{chain}。请先修正 BOM 后再运行 MRP。",
                            code="BOM_CYCLE_DETECTED",
                        )
                    visiting.append(material.code)
                    try:
                        walk(child, None, depth + 1, ancestors | {material_id})
                    finally:
                        visiting.pop()

    for root in roots:
        walk(root["material"], root.get("sku"), 0, frozenset())
    return bom_of, edges, low_level, materials


def _net_item(
    *,
    demands: list[dict[str, Any]],
    supplies: list[dict[str, Any]],
    horizon_start: date,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """单个物料的逐段净算，返回（净需求/建议输入, 净算过程）。"""
    initial = sum(
        (item["quantity"] for item in supplies if item["source_type"] == MrpSupplySource.ON_HAND),
        ZERO,
    )
    # 采购在途与在制供给都是「未来某段才到货」的供给，按预计到货 / 计划完工分段计入；
    # 只有现有可用库存进期初。
    inbound_by_bucket: dict[date, Decimal] = defaultdict(lambda: ZERO)
    for item in supplies:
        if item["source_type"] in {MrpSupplySource.ON_ORDER, MrpSupplySource.IN_PROGRESS}:
            inbound_by_bucket[item["bucket_date"]] += item["quantity"]
    demand_by_bucket: dict[date, Decimal] = defaultdict(lambda: ZERO)
    for row in demands:
        demand_by_bucket[row["bucket_date"]] += row["quantity"]

    buckets = sorted(set(demand_by_bucket) | set(inbound_by_bucket))
    available = _q(initial)
    shortages: list[dict[str, Any]] = []
    trace: list[dict[str, Any]] = []
    for bucket_date in buckets:
        opening = available
        supply = _q(inbound_by_bucket.get(bucket_date, ZERO))
        demand = _q(demand_by_bucket.get(bucket_date, ZERO))
        available = opening + supply - demand
        net_requirement = ZERO
        if available < ZERO:
            net_requirement = -available
            available = ZERO
        trace.append(
            {
                "bucket_date": bucket_date.isoformat(),
                "opening": str(opening),
                "supply": str(supply),
                "demand": str(demand),
                "net_requirement": str(net_requirement),
                "closing": str(available),
            }
        )
        if net_requirement > ZERO:
            shortages.append(
                {
                    "bucket_date": bucket_date,
                    "quantity": _q(net_requirement),
                    "demand_quantity": demand,
                    "supply_quantity": supply,
                }
            )
    if not buckets and initial > ZERO:
        trace.append(
            {
                "bucket_date": horizon_start.isoformat(),
                "opening": str(initial),
                "supply": "0",
                "demand": "0",
                "net_requirement": "0",
                "closing": str(initial),
            }
        )
    return shortages, trace

def _compute(
    *,
    company: Any,
    horizon_start: date,
    horizon_end: date,
    bucket: str,
    warehouse: Any = None,
) -> dict[str, Any]:
    """纯计算（不写库）：需求 → 低层码 → 逐层净算 → 展开 → 建议。

    纯函数式的好处：**循环 BOM 等错误不会留下半截数据**，失败时只记录一条 failed 运行。
    """
    base_demands = _collect_sales_demands(
        company=company, horizon_start=horizon_start, horizon_end=horizon_end, warehouse=warehouse
    )
    for row in base_demands:
        due = row.pop("bucket_date", None)
        due = due or row["due_date"]
        row["bucket_date"] = mrp_bucket_date(max(due, horizon_start), bucket)
        row["level"] = 0

    bom_of, edges, low_level, materials = _build_graph(company=company, roots=base_demands)

    supplies: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for material_id, rows in _on_hand_supplies(
        company=company, horizon_start=horizon_start, bucket=bucket, warehouse=warehouse
    ).items():
        supplies[material_id].extend(rows)
    for material_id, rows in _on_order_supplies(
        company=company,
        horizon_start=horizon_start,
        horizon_end=horizon_end,
        bucket=bucket,
        warehouse=warehouse,
    ).items():
        supplies[material_id].extend(rows)
    for material_id, rows in _in_progress_supplies(
        company=company,
        horizon_start=horizon_start,
        horizon_end=horizon_end,
        bucket=bucket,
        warehouse=warehouse,
    ).items():
        supplies[material_id].extend(rows)

    demands: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in base_demands:
        demands[row["material"].pk].append(row)

    demand_rows: list[dict[str, Any]] = []
    suggestion_rows: list[dict[str, Any]] = []
    unexploded: list[str] = []
    # 低层码升序：父件先净算，展开出的子件需求在**本循环内动态产生**，
    # 因此这里不能预先过滤「当前已有需求的物料」——子件在被展开前需求量必为 0，
    # 预过滤会让派生需求永远不被净算（BOM 展开形同失效）。
    order: list[int] = sorted(
        low_level, key=lambda material_id: (low_level[material_id], material_id)
    )
    for material_id in order:
        item_demands = demands.get(material_id)
        if not item_demands:
            continue
        material = materials[material_id]
        bom = bom_of.get(material_id)
        suggestion_type = _suggestion_type(material, bom)
        shortages, trace = _net_item(
            demands=item_demands,
            supplies=supplies.get(material_id, []),
            horizon_start=horizon_start,
        )
        for row in item_demands:
            row["exploded"] = bool(shortages and edges.get(material_id))
        demand_rows.extend(item_demands)
        if not shortages:
            continue
        shortest = min(item_demands, key=lambda row: len(row["path"]))
        for shortage in shortages:
            bucket_date = shortage["bucket_date"]
            quantity = shortage["quantity"]
            reason_parts = [
                f"{bucket_date.isoformat()} 分段净需求 {quantity}",
                f"（本段需求 {shortage['demand_quantity']}、本段在途 {shortage['supply_quantity']}）",
            ]
            if suggestion_type == MrpSuggestionType.PRODUCTION:
                if bom is not None:
                    reason_parts.append(f"自制品，按 BOM {bom.code} v{bom.version_no} 展开下级")
                else:
                    reason_parts.append("分类为成品/半成品但**无生效 BOM**，无法展开，请先维护 BOM")
                    if material.code not in unexploded:
                        unexploded.append(material.code)
            else:
                reason_parts.append("采购件（无生效 BOM 且分类不属于成品/半成品）")
            suggestion_rows.append(
                {
                    "material": material,
                    "sku": shortest.get("sku") if suggestion_type == MrpSuggestionType.PRODUCTION else None,
                    "style": shortest.get("style") if suggestion_type == MrpSuggestionType.PRODUCTION else None,
                    "warehouse": shortest.get("warehouse"),
                    "suggestion_type": suggestion_type,
                    "quantity": quantity,
                    "due_date": bucket_date,
                    "bucket_date": bucket_date,
                    "reason": "".join(reason_parts)[:255],
                    "detail": {
                        "level": low_level[material_id],
                        "bom_id": getattr(bom, "pk", None),
                        "bom_code": getattr(bom, "code", None),
                        "bom_version_no": getattr(bom, "version_no", None),
                        "trace": trace,
                        "demand_sources": sorted(
                            {f"{row['source_no']}#{row['source_line_no'] or '-'}" for row in item_demands}
                        ),
                    },
                }
            )
            if suggestion_type == MrpSuggestionType.PRODUCTION and bom is not None:
                for line in edges.get(material_id, []):
                    child = line.material
                    child_quantity = _q(quantity * line.gross_quantity)
                    if child_quantity <= ZERO:
                        continue
                    demands[child.pk].append(
                        {
                            "material": child,
                            "sku": None,
                            "style": None,
                            "warehouse": shortest.get("warehouse"),
                            "quantity": child_quantity,
                            "due_date": bucket_date,
                            "bucket_date": bucket_date,
                            "level": low_level.get(child.pk, low_level[material_id] + 1),
                            "source_type": MrpDemandSource.PARENT_ITEM,
                            "source_id": str(material_id),
                            "source_no": material.code,
                            "source_line_no": None,
                            "path": f"{shortest['path']} > {child.code}",
                            "note": (
                                f"{material.code} 净需求 {quantity} × 用量 {line.gross_quantity}"
                                f"（含损耗，BOM {bom.code} v{bom.version_no} 第 {line.line_no} 行）"
                            ),
                        }
                    )

    supply_rows: list[dict[str, Any]] = []
    touched = {row["material"].pk for row in demand_rows}
    for material_id in sorted(touched):
        for row in supplies.get(material_id, []):
            supply_rows.append({"material_id": material_id, **row})

    buckets = sorted({row["bucket_date"] for row in demand_rows} | {row["bucket_date"] for row in supply_rows})
    summary = {
        "item_count": len({row["material"].pk for row in demand_rows}),
        "level_count": (max(low_level.values()) + 1) if low_level else 0,
        "demand_line_count": len(demand_rows),
        "demand_quantity": str(_q(sum((row["quantity"] for row in demand_rows), ZERO))),
        "supply_line_count": len(supply_rows),
        "supply_quantity": str(_q(sum((row["quantity"] for row in supply_rows), ZERO))),
        "suggestion_count": len(suggestion_rows),
        "purchase_suggestion_count": sum(
            1 for row in suggestion_rows if row["suggestion_type"] == MrpSuggestionType.PURCHASE
        ),
        "production_suggestion_count": sum(
            1 for row in suggestion_rows if row["suggestion_type"] == MrpSuggestionType.PRODUCTION
        ),
        "suggestion_quantity": str(_q(sum((row["quantity"] for row in suggestion_rows), ZERO))),
        "unexploded_materials": unexploded,
        "bucket_count": len(buckets),
        "buckets": [item.isoformat() for item in buckets],
    }
    parameters = {
        "bucket": bucket,
        "horizon_start": horizon_start.isoformat(),
        "horizon_end": horizon_end.isoformat(),
        "warehouse_id": getattr(warehouse, "pk", warehouse),
        "demand_sources": [MrpDemandSource.SALES_ORDER],
        "include_substitutes": False,
        "lead_time_mode": "lot_for_lot",
        "in_progress_supply": "mes_open_orders",
        "frozen_and_reserved": "excluded_from_available",
    }
    return {
        "demands": demand_rows,
        "supplies": supply_rows,
        "suggestions": suggestion_rows,
        "summary": summary,
        "parameters": parameters,
    }


def _record_failure(
    *,
    company: Any,
    user: Any,
    horizon_start: date,
    horizon_end: date,
    bucket: str,
    warehouse: Any,
    message: str,
) -> None:
    """计算失败时留一条 failed 运行（尽力而为，绝不用它掩盖原始异常）。"""
    try:
        MrpRun.objects.create(
            company_id=getattr(company, "pk", company),
            run_no=generate_code(MRP_CODE_RULE),
            status=MrpRunStatus.FAILED,
            bucket=bucket,
            horizon_start=horizon_start,
            horizon_end=horizon_end,
            warehouse=warehouse,
            started_at=timezone.now(),
            finished_at=timezone.now(),
            error_message=message[:255],
            created_by=user,
            updated_by=user,
        )
    except Exception:  # pragma: no cover - 记录失败本身不能再失败
        logger.exception("记录 MRP 失败运行出错")

def _persist(run: MrpRun, payload: dict[str, Any], *, user: Any) -> None:
    """把计算结果落库（与运行记录同事务）。"""
    demands = []
    for index, row in enumerate(payload["demands"], start=1):
        material = row["material"]
        demands.append(
            MrpDemandLine(
                run=run,
                line_no=index,
                level=row.get("level", 0),
                source_type=row["source_type"],
                source_id=row.get("source_id", ""),
                source_no=row.get("source_no", ""),
                source_line_no=row.get("source_line_no"),
                material=material,
                sku=row.get("sku"),
                style=row.get("style"),
                warehouse=row.get("warehouse"),
                quantity=row["quantity"],
                due_date=row["due_date"],
                bucket_date=row["bucket_date"],
                path=row.get("path", "")[:255],
                exploded=bool(row.get("exploded")),
                note=row.get("note", "")[:255],
                created_by=user,
                updated_by=user,
            )
        )
    MrpDemandLine.objects.bulk_create(demands)

    supplies = [
        MrpSupplyLine(
            run=run,
            line_no=index,
            source_type=row["source_type"],
            material_id=row["material_id"],
            warehouse_id=row.get("warehouse_id"),
            quantity=row["quantity"],
            available_date=row["available_date"],
            bucket_date=row["bucket_date"],
            reference_type=row.get("reference_type", "")[:64],
            reference_id=row.get("reference_id", "")[:64],
            reference_no=row.get("reference_no", "")[:64],
            remark=row.get("remark", "")[:255],
            created_by=user,
            updated_by=user,
        )
        for index, row in enumerate(payload["supplies"], start=1)
    ]
    MrpSupplyLine.objects.bulk_create(supplies)

    suggestions = []
    for index, row in enumerate(payload["suggestions"], start=1):
        material = row["material"]
        if row["suggestion_type"] == MrpSuggestionType.PURCHASE:
            uom = material.purchase_uom or material.base_uom
        else:
            uom = material.base_uom
        suggestions.append(
            MrpSuggestion(
                run=run,
                line_no=index,
                suggestion_type=row["suggestion_type"],
                status=MrpSuggestionStatus.OPEN,
                material=material,
                sku=row.get("sku"),
                style=row.get("style"),
                warehouse=row.get("warehouse"),
                quantity=row["quantity"],
                uom=uom,
                due_date=row["due_date"],
                bucket_date=row["bucket_date"],
                reason=row["reason"][:255],
                detail=row["detail"],
                created_by=user,
                updated_by=user,
            )
        )
    MrpSuggestion.objects.bulk_create(suggestions)


def run_mrp(
    *,
    company: Any,
    user: Any,
    horizon_start: date,
    horizon_end: date,
    bucket: str = MrpBucket.DAY,
    warehouse: Any = None,
    remark: str = "",
) -> MrpRun:
    """运行一次 MRP，返回运行记录（含需求 / 供给 / 建议明细）。

    运行是**同步**的：MRP 的结果直接决定采购与生产动作，异步化会让结果与库存/订单状态脱节；
    真正的计算可解释且规模可控（首版按公司维度逐层净算）。
    """
    require_codes(user, "planning.mrp.run")
    if bucket not in MrpBucket.values:
        raise ValidationFailed("时间分段只支持按日或按周。", code="INVALID_BUCKET")
    if horizon_end < horizon_start:
        raise ValidationFailed("需求区间结束日期不能早于开始日期。", code="INVALID_HORIZON")

    company_id = getattr(company, "pk", company)
    started = timezone.now()
    try:
        payload = _compute(
            company=company,
            horizon_start=horizon_start,
            horizon_end=horizon_end,
            bucket=bucket,
            warehouse=warehouse,
        )
    except ValidationFailed as exc:
        _record_failure(
            company=company,
            user=user,
            horizon_start=horizon_start,
            horizon_end=horizon_end,
            bucket=bucket,
            warehouse=warehouse,
            message=str(exc),
        )
        raise

    with transaction.atomic():
        run = MrpRun.objects.create(
            company_id=company_id,
            run_no=generate_code(MRP_CODE_RULE),
            status=MrpRunStatus.COMPLETED,
            bucket=bucket,
            horizon_start=horizon_start,
            horizon_end=horizon_end,
            warehouse=warehouse,
            parameters=payload["parameters"],
            summary=payload["summary"],
            started_at=started,
            finished_at=timezone.now(),
            remark=remark,
            created_by=user,
            updated_by=user,
        )
        _persist(run, payload, user=user)
        record_audit(
            action=AuditAction.CREATE,
            instance=run,
            changes={
                "run_no": {"before": "", "after": run.run_no},
                "horizon": {
                    "before": "",
                    "after": f"{horizon_start.isoformat()} ~ {horizon_end.isoformat()}",
                },
                "bucket": {"before": "", "after": bucket},
                "summary": {"before": {}, "after": payload["summary"]},
            },
            object_repr=run.run_no,
            company=run.company,
            actor=user,
        )
        publish_event(
            event_type=EVENT_RUN_COMPLETED,
            aggregate_type=AGGREGATE_RUN,
            aggregate_id=str(run.pk),
            payload={
                "run_no": run.run_no,
                "company_id": company_id,
                "bucket": bucket,
                "horizon_start": horizon_start.isoformat(),
                "horizon_end": horizon_end.isoformat(),
                "summary": payload["summary"],
            },
            dedup_key=f"mrp-run:{run.pk}",
        )
    return run


@transaction.atomic
def archive_run(run: MrpRun, *, user: Any, reason: str = "") -> MrpRun:
    """归档运行：只改状态，不删除明细（历史可追溯）。"""
    require_codes(user, "planning.mrp.archive")
    run = MrpRun.objects.select_for_update().get(pk=run.pk)
    if run.status == MrpRunStatus.ARCHIVED:
        raise StateConflict("该 MRP 运行已归档。", code="STATE_CONFLICT")
    before = {"status": run.status}
    run.status = MrpRunStatus.ARCHIVED
    run.archived_at = timezone.now()
    run.archived_by = user
    if reason:
        run.remark = f"{run.remark}\n归档原因：{reason}".strip()
    run.updated_by = user
    run.save()
    record_audit(
        action=AuditAction.UPDATE,
        instance=run,
        changes=build_changes(before, {"status": run.status}),
        object_repr=run.run_no,
        reason=reason,
        company=run.company,
        actor=user,
    )
    return run


@transaction.atomic
def cancel_suggestion(suggestion: MrpSuggestion, *, user: Any, reason: str) -> MrpSuggestion:
    """取消建议（例如计划员判断该需求已由其他方式满足）。必须填原因。"""
    require_codes(user, "planning.mrp.cancel")
    suggestion = MrpSuggestion.objects.select_for_update().get(pk=suggestion.pk)
    if suggestion.status != MrpSuggestionStatus.OPEN:
        raise StateConflict(
            f"建议当前状态为「{suggestion.get_status_display()}」，只有待处理的建议可以取消。",
            code="SUGGESTION_NOT_OPEN",
        )
    if not str(reason or "").strip():
        raise ValidationFailed("取消建议必须填写原因。", code="REASON_REQUIRED")
    before = {"status": suggestion.status}
    suggestion.status = MrpSuggestionStatus.CANCELLED
    suggestion.cancel_reason = str(reason).strip()[:255]
    suggestion.updated_by = user
    suggestion.save()
    record_audit(
        action=AuditAction.UPDATE,
        instance=suggestion,
        changes=build_changes(before, {"status": suggestion.status}),
        object_repr=f"{suggestion.run.run_no}#{suggestion.line_no}",
        reason=str(reason).strip(),
        company=suggestion.run.company,
        actor=user,
    )
    return suggestion


@transaction.atomic
def convert_suggestion(
    suggestion: MrpSuggestion, *, user: Any, needed_date: date | None = None, remark: str = ""
) -> MrpSuggestion:
    """把**建议**转成草稿下游单据（任务书 10.6「建议审核转单」）。

    转单前重新检查建议有效性（不满足即拒绝，不做"先转了再说"）：

    1. 建议必须处于「待处理」，已转单/已取消直接拒绝 —— 这是「同一建议不得重复转单」的保障；
    2. 所属运行必须是该公司**最新一次已完成**的运行，否则说明已重算，建议已过期（`SUGGESTION_STALE`）；
    3. 物料必须仍启用；
    4. 按建议类型分流：采购建议转**草稿采购申请**，生产建议转**草稿 MES 生产工单**
       （见 `_convert_production_suggestion`）——两者都只到草稿，不绕过各自的下达 / 审批动作。

    转单只创建**草稿**单据（采购申请仍要走审批，工单仍要人工下达），因此 MRP 不会绕过
    审批或生产确认直接产生采购承诺 / 产能承诺。
    """
    require_codes(user, "planning.mrp.convert")
    suggestion = (
        MrpSuggestion.objects.select_for_update()
        .select_related("run", "run__company", "material", "sku", "style")
        .get(pk=suggestion.pk)
    )
    run = suggestion.run
    if run.status != MrpRunStatus.COMPLETED:
        raise StateConflict(
            f"MRP 运行当前状态为「{run.get_status_display()}」，只有已完成的运行可以转单。",
            code="MRP_RUN_NOT_ACTIVE",
        )
    if suggestion.status == MrpSuggestionStatus.CONVERTED:
        raise StateConflict(
            f"该建议已转单（{suggestion.converted_document_type} "
            f"{suggestion.converted_document_no}），不能重复转单。",
            code="SUGGESTION_ALREADY_CONVERTED",
        )
    if suggestion.status != MrpSuggestionStatus.OPEN:
        raise StateConflict(
            f"建议当前状态为「{suggestion.get_status_display()}」，不能转单。",
            code="SUGGESTION_NOT_OPEN",
        )
    newer = MrpRun.objects.filter(
        company_id=run.company_id, status=MrpRunStatus.COMPLETED, pk__gt=run.pk
    ).exists()
    if newer:
        raise StateConflict(
            "该建议所属的 MRP 运行已被更新的运行取代，请使用最新运行的算结果转单。",
            code="SUGGESTION_STALE",
        )
    if not suggestion.material.is_active:
        raise StateConflict("建议物料已停用，不能转单。", code="MATERIAL_INACTIVE")
    if suggestion.suggestion_type == MrpSuggestionType.PRODUCTION:
        return _convert_production_suggestion(
            user, suggestion, needed_date=needed_date, remark=remark
        )

    from apps.procurement import services as procurement_services

    requisition = procurement_services.create_requisition(
        user=user,
        company=run.company,
        lines=[
            {
                "material": suggestion.material,
                "quantity": suggestion.quantity,
                "uom": suggestion.uom,
                "needed_date": needed_date or suggestion.due_date,
                "remark": f"MRP {run.run_no} 第 {suggestion.line_no} 行建议",
            }
        ],
        request_type="planned",
        needed_date=needed_date or suggestion.due_date,
        purpose=f"MRP {run.run_no} 采购建议转单"[:255],
        remark=remark or suggestion.reason[:255],
    )
    return _mark_suggestion_converted(
        suggestion,
        user=user,
        target_type="procurement.PurchaseRequisition",
        target_id=str(requisition.pk),
        target_no=requisition.requisition_no,
        link_remark=f"MRP 运行 {run.run_no} 采购建议",
        event_payload={"requisition_no": requisition.requisition_no},
        remark=remark,
    )


def _mark_suggestion_converted(
    suggestion: MrpSuggestion,
    *,
    user: Any,
    target_type: str,
    target_id: str,
    target_no: str,
    link_remark: str,
    event_payload: dict[str, Any],
    remark: str = "",
) -> MrpSuggestion:
    """转单收尾：写 DocumentLink、置状态、写审计与 Outbox（采购 / 生产两条路径共用）。"""
    run = suggestion.run
    DocumentLink.objects.create(
        source_type="planning.MrpSuggestion",
        source_id=str(suggestion.pk),
        source_no=f"{run.run_no}#{suggestion.line_no}",
        target_type=target_type,
        target_id=target_id,
        target_no=target_no,
        relation=DocumentRelation.GENERATED_FROM,
        quantity=suggestion.quantity,
        remark=link_remark,
    )
    before = {
        "status": suggestion.status,
        "converted_document_no": suggestion.converted_document_no,
    }
    suggestion.status = MrpSuggestionStatus.CONVERTED
    suggestion.converted_document_type = target_type
    suggestion.converted_document_id = target_id
    suggestion.converted_document_no = target_no
    suggestion.converted_at = timezone.now()
    suggestion.converted_by = user
    suggestion.updated_by = user
    suggestion.save()
    record_audit(
        action=AuditAction.UPDATE,
        instance=suggestion,
        changes=build_changes(before, {
            "status": suggestion.status,
            "converted_document_no": suggestion.converted_document_no,
        }),
        object_repr=f"{run.run_no}#{suggestion.line_no}",
        reason=remark,
        company=run.company,
        actor=user,
    )
    publish_event(
        event_type=EVENT_SUGGESTION_CONVERTED,
        aggregate_type=AGGREGATE_SUGGESTION,
        aggregate_id=str(suggestion.pk),
        payload={
            "run_no": run.run_no,
            "suggestion_line_no": suggestion.line_no,
            **event_payload,
            "material_code": suggestion.material.code,
            "quantity": str(suggestion.quantity),
        },
        dedup_key=f"mrp-suggestion-converted:{suggestion.pk}",
    )
    return suggestion


def _convert_production_suggestion(
    user: Any, suggestion: MrpSuggestion, *, needed_date: Any = None, remark: str = ""
) -> MrpSuggestion:
    """生产建议转单：生成**草稿 MES 生产工单**。

    只生成草稿：下达时要冻结 BOM / 工艺快照并生成工序，这一步必须由生产角色在 MES
    里显式执行，MRP 不替它做决定（任务书 9.5）。因此生产建议转单**不会**立即增加在制供给，
    要等工单真正下达后才计入 MRP 的在制供给。
    """
    from apps.mes import services as mes_services

    run = suggestion.run
    if suggestion.style_id is None:
        raise StateConflict(
            "该生产建议没有关联款式，无法生成生产工单；请先维护物料的款式与 SKU 对应关系。",
            code="STYLE_REQUIRED",
        )
    due = needed_date or suggestion.due_date
    planned_end = None
    if isinstance(due, datetime):
        planned_end = due if timezone.is_aware(due) else due.replace(tzinfo=business_timezone())
    elif due is not None:
        planned_end = datetime.combine(due, time.min, tzinfo=business_timezone())
    order = mes_services.create_order(
        user,
        company=run.company,
        style=suggestion.style,
        sku=suggestion.sku,
        product_material=suggestion.material,
        quantity=suggestion.quantity,
        planned_end=planned_end,
        # 值为 ProductionSourceType.MRP_SUGGESTION，这里用字面量避免计划模块反向依赖 MES 模型
        source_type="mrp_suggestion",
        source_no=f"{run.run_no}#{suggestion.line_no}",
        remark=(remark or suggestion.reason)[:255] or f"MRP {run.run_no} 生产建议转单",
    )
    return _mark_suggestion_converted(
        suggestion,
        user=user,
        target_type="mes.ProductionOrder",
        target_id=str(order.pk),
        target_no=order.order_no,
        link_remark=f"MRP 运行 {run.run_no} 生产建议",
        event_payload={"production_order_no": order.order_no},
        remark=remark,
    )


__all__ = [
    "DEFAULT_HORIZON_DAYS",
    "EVENT_RUN_COMPLETED",
    "EVENT_SUGGESTION_CONVERTED",
    "MAX_LEVEL",
    "MRP_CODE_RULE",
    "archive_run",
    "cancel_suggestion",
    "convert_suggestion",
    "run_mrp",
]
