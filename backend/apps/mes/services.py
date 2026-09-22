"""生产执行（MES）服务：工单下达、领料、报工、完工与完工入库。

状态机（非法跃迁一律拒绝，不能靠 PATCH 跳步）::

    draft --release--> released --首次报工--> in_progress --complete--> completed --close--> closed
    draft / released --cancel--> cancelled

关键口径（刻意如此，不要放宽）：

* **下达即冻结**：下达时把生效的工艺路线与 BOM 写进快照并生成工序 / 用料行；
  之后工程数据出新版本不影响已下达工单（任务书 9.5、14.2 案例 13）。
* **报工数量守恒**：单次报工「合格 + 返工 + 报废」必须等于报工数量；同一工序
  累计报工不得超过工单计划数量——报多了是数据错误，不是产能。
* **末道工序口径**：工单的完工 / 合格数量取末道工序的累计数（同一件产品要经过
  多道工序，把全部工序报工数相加会重复计数）；报废数量汇总全部工序。
* **质量门**：质检点工序报满时自动生成一张 QMS 检验单（草稿）；工单完工要求
  全部质检点检验单已判定为「合格」或「让步接收」，未判定与不合格都不能完工。
* **库存只能经统一库存服务**：领料与完工入库都调用 `apps.wms.services.stock`
  生成并过账库存单据，本模块不写库存余额与流水（任务书 10.8）。
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from decimal import Decimal
from typing import Any

from django.db import transaction
from django.db.models import F, Sum
from django.utils import timezone

from apps.core.exceptions import ObjectNotFound, StateConflict, ValidationFailed
from apps.core.models import AuditAction
from apps.core.permissions import require_codes
from apps.core.services import build_changes, generate_code, publish_event, record_audit
from apps.mes.models import (
    ProductionMaterialSource,
    ProductionOrder,
    ProductionOrderMaterial,
    ProductionOrderStatus,
    ProductionOrderStep,
    ProductionReport,
    ProductionReportType,
    ProductionSourceType,
    ProductionStepStatus,
)
from apps.planning import services as planning_services
from apps.qms import services as qms_services
from apps.qms.models import QualityInspectionType, QualityJudgement
from apps.wms.models import DocumentType, QualityStatus
from apps.wms.services import stock

ORDER_CODE_RULE = "MO"
REPORT_CODE_RULE = "RPT"
BIZ_TYPE_ORDER = "mes.ProductionOrder"
EVENT_ORDER_RELEASED = "mes.production_order.released"
EVENT_ORDER_COMPLETED = "mes.production_order.completed"
AGGREGATE_ORDER = "mes.ProductionOrder"

ZERO = Decimal("0")
QUANT = Decimal("0.000001")


def _q(value: Any) -> Decimal:
    """数量统一按 6 位小数舍入（与库存 / 计划口径一致）。"""
    return Decimal(value or 0).quantize(QUANT)


def next_order_no() -> str:
    """工单号（编码规则 MO）。"""
    return generate_code(ORDER_CODE_RULE)


def next_report_no() -> str:
    """报工单号（编码规则 RPT）。"""
    return generate_code(REPORT_CODE_RULE)


def _int_id(value: Any) -> int | None:
    if value is None:
        return None
    return int(getattr(value, "pk", value))


def _positive(value: Any, message: str) -> Decimal:
    if value is None:
        raise ValidationFailed(message, code="VALIDATION_ERROR")
    decimal_value = _q(value)
    if decimal_value <= ZERO:
        raise ValidationFailed(message, code="VALIDATION_ERROR")
    return decimal_value


def _non_negative(value: Any, message: str) -> Decimal:
    decimal_value = _q(value or ZERO)
    if decimal_value < ZERO:
        raise ValidationFailed(message, code="VALIDATION_ERROR")
    return decimal_value


def _uom_label(material: Any) -> str:
    uom = getattr(material, "base_uom", None)
    return str(getattr(uom, "name", "") or "")[:16]


def _replace_materials(order: ProductionOrder, rows: Iterable[dict[str, Any]]) -> None:
    """整表替换工单用料。只在草稿工单上调用。"""
    order.materials.all().delete()
    seen: set[int] = set()
    for index, row in enumerate(rows, start=1):
        material = row.get("material")
        if material is None:
            raise ValidationFailed(f"第 {index} 行缺少物料。", code="LINE_MATERIAL_REQUIRED")
        material_id = _int_id(material)
        if material_id in seen:
            raise ValidationFailed(
                f"物料「{material}」在用料清单中重复出现，请合并为一行。",
                code="DUPLICATE_MATERIAL",
            )
        seen.add(material_id)
        required = _positive(row.get("required_quantity"), f"第 {index} 行用量必须大于 0。")
        ProductionOrderMaterial.objects.create(
            order=order,
            line_no=index,
            material_id=material_id,
            source=row.get("source") or ProductionMaterialSource.MANUAL,
            required_quantity=required,
            unit=str(row.get("unit") or _uom_label(material))[:16],
            location_id=_int_id(row.get("location") or row.get("location_id")),
            remark=str(row.get("remark") or "")[:255],
        )


def _assert_style_usable(order: ProductionOrder) -> None:
    if not getattr(order.style, "is_active", True):
        raise ValidationFailed("款式已停用，不能下达生产工单。", code="STYLE_INACTIVE")


@transaction.atomic
def create_order(
    user: Any,
    *,
    company: Any,
    style: Any,
    quantity: Any = None,
    sku: Any = None,
    product_material: Any = None,
    unit: str = "",
    factory: Any = None,
    workshop: Any = None,
    production_line: Any = None,
    material_warehouse: Any = None,
    receipt_warehouse: Any = None,
    planned_start: Any = None,
    planned_end: Any = None,
    owner: Any = None,
    source_type: str = ProductionSourceType.MANUAL,
    source_no: str = "",
    materials: Sequence[dict[str, Any]] | None = None,
    remark: str = "",
    order_no: str = "",
) -> ProductionOrder:
    """新建生产工单（草稿）。跨模块调用（如 MRP 转单）同样走这里。"""
    require_codes(user, "mes.order.create")
    company_id = _int_id(company)
    if style is None:
        raise ValidationFailed("生产工单必须指定款式。", code="STYLE_REQUIRED")
    if style.company_id != company_id:
        raise ValidationFailed("款式与公司不一致。", code="COMPANY_STYLE_MISMATCH")
    if sku is not None and sku.style_id != style.pk:
        raise ValidationFailed("所选 SKU 不属于该款式。", code="SKU_STYLE_MISMATCH")
    quantity_value = _positive(quantity, "计划数量必须大于 0。")
    with transaction.atomic():
        order = ProductionOrder(
            company_id=company_id,
            order_no=str(order_no or "").strip() or next_order_no(),
            source_type=source_type,
            source_no=str(source_no or "")[:64],
            style=style,
            sku=sku,
            product_material=product_material,
            quantity=quantity_value,
            unit=str(unit or _uom_label(product_material))[:16],
            factory=factory,
            workshop=workshop,
            production_line=production_line,
            material_warehouse=material_warehouse,
            receipt_warehouse=receipt_warehouse,
            planned_start=planned_start,
            planned_end=planned_end,
            owner=owner,
            remark=remark,
        )
        order.save()
        if materials:
            _replace_materials(order, materials)
        record_audit(
            action=AuditAction.CREATE,
            instance=order,
            changes={
                "order_no": {"before": "", "after": order.order_no},
                "style_id": {"before": None, "after": order.style_id},
                "quantity": {"before": "", "after": str(order.quantity)},
                "source_no": {"before": "", "after": order.source_no},
            },
            reason=remark,
            object_repr=order.order_no,
            company=order.company,
            actor=user,
        )
    return order


@transaction.atomic
def update_order(
    order: ProductionOrder,
    *,
    user: Any,
    materials: Sequence[dict[str, Any]] | None = None,
    **header: Any,
) -> ProductionOrder:
    """修改草稿工单。已下达工单不可改（要变更就取消后重开）。"""
    require_codes(user, "mes.order.update")
    locked = ProductionOrder.objects.select_for_update().filter(pk=order.pk).first()
    if locked is None:
        raise ObjectNotFound("生产工单不存在。", details={"order_id": order.pk})
    if locked.status != ProductionOrderStatus.DRAFT:
        raise StateConflict(
            "只有草稿状态的工单可以修改；已下达工单请先取消再重开。",
            code="STATE_CONFLICT",
            details={"order_no": locked.order_no, "status": locked.status},
        )
    changed: dict[str, Any] = {}
    for field, value in header.items():
        if value is None:
            continue
        if field == "quantity":
            value = _positive(value, "计划数量必须大于 0。")
        current = getattr(locked, field)
        if current != value:
            changed[field] = {"before": current, "after": value}
            setattr(locked, field, value)
    if changed:
        locked.save()
    if materials is not None:
        _replace_materials(locked, materials)
        changed["material_line_count"] = {"before": 0, "after": locked.materials.count()}
    if changed:
        record_audit(
            action=AuditAction.UPDATE,
            instance=locked,
            changes=changed,
            object_repr=locked.order_no,
            company=locked.company,
            actor=user,
        )
    return locked


def _expand_bom_materials(
    order: ProductionOrder, snapshot: dict[str, Any]
) -> list[dict[str, Any]]:
    """按 BOM 快照展开单层用料（多层级展开由 MRP 负责）。"""
    from apps.masterdata.models import Material

    rows: list[dict[str, Any]] = []
    for line in snapshot.get("lines", []):
        if line.get("line_type") != "normal":
            # 替代料不参与下达展开，与 MRP 的口径一致
            continue
        gross = _q(line.get("gross_quantity"))
        if gross <= ZERO:
            continue
        material = Material.objects.filter(pk=line.get("material_id")).first()
        if material is None:
            continue
        rows.append(
            {
                "material": material,
                "source": ProductionMaterialSource.BOM,
                "required_quantity": _q(gross * order.quantity),
                "unit": _uom_label(material),
                "remark": f"BOM 快照第 {line.get('line_no')} 行",
            }
        )
    return rows


@transaction.atomic
def release_order(
    order: ProductionOrder, *, user: Any, materials: Sequence[dict[str, Any]] | None = None
) -> ProductionOrder:
    """下达工单：冻结工艺路线与 BOM 快照，并生成工序与用料行。

    * 没有生效工艺路线不能下达（工序是生产执行的最小单位，不能凭感觉填）；
    * 没有任何用料（既无生效 BOM，也没有手工用料行）也不能下达；
    * 快照一经写入不再变化，工程数据出新版本不影响本工单。
    """
    require_codes(user, "mes.order.release")
    locked = (
        ProductionOrder.objects.select_for_update()
        .select_related("company", "style", "sku", "product_material")
        .filter(pk=order.pk)
        .first()
    )
    if locked is None:
        raise ObjectNotFound("生产工单不存在。", details={"order_id": order.pk})
    if locked.status != ProductionOrderStatus.DRAFT:
        raise StateConflict(
            f"工单当前状态为「{locked.get_status_display()}」，只有草稿工单可以下达。",
            code="STATE_CONFLICT",
            details={"order_no": locked.order_no, "status": locked.status},
        )
    if locked.quantity <= ZERO:
        raise ValidationFailed("计划数量必须大于 0 才能下达。", code="INVALID_QUANTITY")
    _assert_style_usable(locked)
    if locked.steps.exists():
        raise StateConflict("该工单已经生成过工序，不能重复下达。", code="STATE_CONFLICT")

    routing = planning_services.get_effective_routing(locked.company, locked.style, locked.sku)
    if routing is None:
        raise ValidationFailed(
            "该款式没有生效的工艺路线，无法下达生产工单。请先在计划管理审核工艺路线。",
            code="ROUTING_REQUIRED",
        )
    if materials is not None:
        _replace_materials(locked, materials)
    bom = planning_services.get_effective_bom_for(
        locked.company, locked.style_id, locked.sku_id
    )
    bom_snapshot: dict[str, Any] = {}
    if bom is not None:
        bom_snapshot = planning_services.build_bom_snapshot(bom)
        if not locked.materials.exists():
            rows = _expand_bom_materials(locked, bom_snapshot)
            if not rows:
                raise ValidationFailed(
                    "生效 BOM 没有可展开的正常用料行，无法下达生产工单。",
                    code="BOM_EMPTY",
                )
            _replace_materials(locked, rows)
    if not locked.materials.exists():
        raise ValidationFailed(
            "该款式没有生效 BOM，也没有手工填写工单用料，无法下达生产工单。",
            code="BOM_REQUIRED",
        )

    routing_snapshot = planning_services.build_routing_snapshot(routing)
    for step in routing_snapshot.get("steps", []):
        ProductionOrderStep.objects.create(
            order=locked,
            sequence=int(step["sequence"]),
            name=str(step["name"])[:128],
            workshop_id=step.get("workshop_id"),
            workcenter=str(step.get("workcenter") or "")[:64],
            equipment_requirement=str(step.get("equipment_requirement") or "")[:128],
            standard_hours=_q(step.get("standard_hours")),
            is_quality_gate=bool(step.get("is_quality_gate")),
            is_outsourced=bool(step.get("is_outsourced")),
        )
    if not locked.steps.exists():
        raise ValidationFailed("工艺路线没有工序行，无法下达生产工单。", code="ROUTING_EMPTY")

    locked.bom_snapshot = bom_snapshot
    locked.routing_snapshot = routing_snapshot
    locked.status = ProductionOrderStatus.RELEASED
    locked.released_at = timezone.now()
    locked.released_by = user
    locked.save()
    record_audit(
        action=AuditAction.SUBMIT,
        instance=locked,
        changes={
            "status": {
                "before": ProductionOrderStatus.DRAFT,
                "after": ProductionOrderStatus.RELEASED,
            },
            "routing_version": {"before": None, "after": routing.version_no},
            "bom_version": {"before": None, "after": bom.version_no if bom else None},
        },
        object_repr=locked.order_no,
        company=locked.company,
        actor=user,
    )
    publish_event(
        event_type=EVENT_ORDER_RELEASED,
        aggregate_type=AGGREGATE_ORDER,
        aggregate_id=locked.pk,
        payload={
            "order_no": locked.order_no,
            "style_id": locked.style_id,
            "quantity": str(locked.quantity),
            "routing_code": routing.code,
            "bom_code": bom.code if bom else "",
        },
        dedup_key=f"mes.order:{locked.pk}:released",
    )
    return locked


@transaction.atomic
def issue_materials(
    order: ProductionOrder,
    *,
    user: Any,
    lines: Sequence[dict[str, Any]] | None = None,
    idempotency_key: str | None = None,
) -> tuple[ProductionOrder, Any]:
    """工单领料：经统一库存服务生成并过账一张**出库**单据。

    一次性领料（`issue_document` 已存在即拒绝重复领料）：生产领料要么整单领，
    要么按手工行领。分次领料属于更细的批次管理，本阶段不做，避免出现
    「领了一半但系统说不清是谁领的」的糊涂账。
    """
    require_codes(user, "mes.order.issue", "wms.document.create", "wms.document.post")
    locked = (
        ProductionOrder.objects.select_for_update()
        .select_related("company", "material_warehouse")
        .filter(pk=order.pk)
        .first()
    )
    if locked is None:
        raise ObjectNotFound("生产工单不存在。", details={"order_id": order.pk})
    if locked.status not in {
        ProductionOrderStatus.RELEASED,
        ProductionOrderStatus.IN_PROGRESS,
    }:
        raise StateConflict(
            f"工单当前状态为「{locked.get_status_display()}」，不能领料。",
            code="STATE_CONFLICT",
        )
    if locked.issue_document_id:
        raise StateConflict(
            f"该工单已领料（出库单 {locked.issue_document.document_no}），不支持重复领料。",
            code="MATERIAL_ALREADY_ISSUED",
        )
    warehouse = locked.material_warehouse
    if warehouse is None:
        raise ValidationFailed("请先指定领料仓库。", code="WAREHOUSE_REQUIRED")

    issued: dict[int, Decimal] = {}
    rows: list[dict[str, Any]] = []
    if lines:
        for index, row in enumerate(lines, start=1):
            material = row.get("material")
            if material is None:
                raise ValidationFailed(f"第 {index} 行缺少物料。", code="LINE_MATERIAL_REQUIRED")
            quantity = _positive(row.get("quantity"), f"第 {index} 行领料数量必须大于 0。")
            material_id = _int_id(material)
            issued[material_id] = issued.get(material_id, ZERO) + quantity
            rows.append(
                {
                    "material_id": material_id,
                    "location_id": _int_id(row.get("location") or row.get("location_id")),
                    "batch_no": str(row.get("batch_no") or "")[:64],
                    "quality_status": QualityStatus.QUALIFIED,
                    "quantity": quantity,
                    "remark": str(row.get("remark") or "")[:255],
                }
            )
    else:
        for line in locked.materials.select_related("material").order_by("line_no"):
            remaining = _q(line.required_quantity - line.issued_quantity)
            if remaining <= ZERO:
                continue
            issued[line.material_id] = issued.get(line.material_id, ZERO) + remaining
            rows.append(
                {
                    "material_id": line.material_id,
                    "location_id": line.location_id,
                    "batch_no": "",
                    "quality_status": QualityStatus.QUALIFIED,
                    "quantity": remaining,
                    "remark": f"工单 {locked.order_no} 第 {line.line_no} 行用料",
                }
            )
        if not rows:
            raise ValidationFailed("该工单没有待领料数量。", code="NOTHING_TO_ISSUE")

    document = stock.create_document(
        document_type=DocumentType.ISSUE,
        company=locked.company_id,
        warehouse=warehouse,
        user=user,
        biz_type=BIZ_TYPE_ORDER,
        biz_id=locked.pk,
        biz_no=locked.order_no,
        remark=f"生产领料 {locked.order_no}",
        lines=rows,
    )
    stock.post_document(
        document,
        user=user,
        idempotency_key=idempotency_key or f"mes-issue-{locked.pk}",
        reason=f"生产领料过账 {locked.order_no}",
    )
    for material_id, quantity in issued.items():
        ProductionOrderMaterial.objects.filter(order=locked, material_id=material_id).update(
            issued_quantity=F("issued_quantity") + quantity
        )
    locked.issue_document = document
    locked.save(update_fields=["issue_document", "updated_at"])
    record_audit(
        action=AuditAction.POST,
        instance=locked,
        changes={
            "inventory_document": {"before": "", "after": document.document_no},
            "line_count": {"before": 0, "after": len(rows)},
        },
        reason=f"生产领料 {locked.order_no}",
        object_repr=locked.order_no,
        company=locked.company,
        actor=user,
    )
    return locked, document


def _final_step(order: ProductionOrder) -> ProductionOrderStep | None:
    return order.steps.order_by("-sequence").first()


def _recalculate_order(order: ProductionOrder) -> None:
    """按「末道工序口径」收敛工单的完工 / 合格 / 报废数量。"""
    totals = order.steps.aggregate(scrap=Sum("scrap_quantity"))
    final = _final_step(order)
    order.completed_quantity = _q(final.reported_quantity) if final else ZERO
    order.qualified_quantity = _q(final.qualified_quantity) if final else ZERO
    order.scrap_quantity = _q(totals["scrap"] or ZERO)


def _ensure_gate_inspection(order: ProductionOrder, step: ProductionOrderStep, user: Any) -> None:
    """质检点工序报满时生成一张 QMS 检验单（草稿），由质量人员判定。"""
    if step.inspection_order_id or not step.is_quality_gate:
        return
    inspection = qms_services.create_order(
        user,
        company=order.company,
        inspection_type=QualityInspectionType.IPQC,
        source_no=order.order_no,
        material=order.product_material,
        product_desc=f"{order.style} 第 {step.sequence} 道工序 {step.name}"[:255],
        workshop=step.workshop or order.workshop,
        production_line=order.production_line,
        quantity=step.reported_quantity,
        sample_quantity=step.reported_quantity,
        unit=order.unit,
        remark=f"工单 {order.order_no} 质检点工序自动生成",
    )
    step.inspection_order = inspection


@transaction.atomic
def report_production(
    order: ProductionOrder,
    *,
    user: Any,
    step: ProductionOrderStep,
    report_type: str = ProductionReportType.NORMAL,
    quantity: Any = None,
    qualified_quantity: Any = ZERO,
    rework_quantity: Any = ZERO,
    scrap_quantity: Any = ZERO,
    operator: Any = None,
    equipment: Any = None,
    work_hours: Any = ZERO,
    started_at: Any = None,
    finished_at: Any = None,
    remark: str = "",
) -> tuple[ProductionReport, ProductionOrder]:
    """按工序报工，并推进工序 / 工单进度。

    质检点工序报满时会自动生成 QMS 检验单；该动作因此**额外要求**
    `qms.inspection.create`，缺少权限时整笔报工回滚（不允许只写一半）。
    """
    require_codes(user, "mes.report.create")
    locked = (
        ProductionOrder.objects.select_for_update()
        .select_related("company", "style", "workshop", "production_line", "product_material")
        .filter(pk=order.pk)
        .first()
    )
    if locked is None:
        raise ObjectNotFound("生产工单不存在。", details={"order_id": order.pk})
    if locked.status not in {
        ProductionOrderStatus.RELEASED,
        ProductionOrderStatus.IN_PROGRESS,
    }:
        raise StateConflict(
            f"工单当前状态为「{locked.get_status_display()}」，不能报工。",
            code="STATE_CONFLICT",
            details={"order_no": locked.order_no, "status": locked.status},
        )
    locked_step = ProductionOrderStep.objects.select_for_update().filter(pk=step.pk).first()
    if locked_step is None or locked_step.order_id != locked.pk:
        raise ValidationFailed("该工序不属于本工单。", code="STEP_ORDER_MISMATCH")
    if locked_step.status == ProductionStepStatus.COMPLETED:
        raise StateConflict(
            f"工序「{locked_step.name}」已完工，不能继续报工。", code="STEP_ALREADY_COMPLETED"
        )

    reported = _positive(quantity, "报工数量必须大于 0。")
    qualified = _non_negative(qualified_quantity, "合格数量不能为负数。")
    rework = _non_negative(rework_quantity, "返工数量不能为负数。")
    scrap = _non_negative(scrap_quantity, "报废数量不能为负数。")
    if qualified + rework + scrap != reported:
        raise ValidationFailed(
            "合格 + 返工 + 报废 必须等于报工数量。",
            code="QUANTITY_MISMATCH",
            details={
                "quantity": str(reported),
                "qualified": str(qualified),
                "rework": str(rework),
                "scrap": str(scrap),
            },
        )
    total_after = _q(locked_step.reported_quantity + reported)
    if total_after > locked.quantity:
        raise ValidationFailed(
            "工序累计报工数量不能超过工单计划数量。",
            code="OVER_PRODUCTION",
            details={
                "planned": str(locked.quantity),
                "reported_before": str(locked_step.reported_quantity),
                "requested": str(reported),
            },
        )

    now = timezone.now()
    report = ProductionReport(
        company=locked.company,
        report_no=next_report_no(),
        order=locked,
        step=locked_step,
        report_type=report_type,
        quantity=reported,
        qualified_quantity=qualified,
        rework_quantity=rework,
        scrap_quantity=scrap,
        operator=operator,
        equipment=equipment,
        work_hours=_non_negative(work_hours, "实际工时不能为负数。"),
        started_at=started_at,
        finished_at=finished_at,
        reported_at=now,
        reported_by=user,
        remark=str(remark or "")[:255],
    )
    report.save()

    before_status = locked_step.status
    before_reported = _q(locked_step.reported_quantity)
    locked_step.reported_quantity = total_after
    locked_step.qualified_quantity = _q(locked_step.qualified_quantity + qualified)
    locked_step.scrap_quantity = _q(locked_step.scrap_quantity + scrap)
    if locked_step.status == ProductionStepStatus.PENDING:
        locked_step.status = ProductionStepStatus.IN_PROGRESS
        locked_step.started_at = started_at or now
    if total_after >= locked.quantity:
        locked_step.status = ProductionStepStatus.COMPLETED
        locked_step.finished_at = finished_at or now
    _ensure_gate_inspection(locked, locked_step, user)
    locked_step.save()

    before_order_status = locked.status
    if locked.actual_start is None:
        locked.actual_start = locked_step.started_at or now
    if locked.status == ProductionOrderStatus.RELEASED:
        locked.status = ProductionOrderStatus.IN_PROGRESS
    _recalculate_order(locked)
    locked.save()

    record_audit(
        action=AuditAction.UPDATE,
        instance=locked,
        changes={
            "step_status": {"before": before_status, "after": locked_step.status},
            "report_no": {"before": "", "after": report.report_no},
            "reported_quantity": {"before": str(before_reported), "after": str(total_after)},
            "order_status": {"before": before_order_status, "after": locked.status},
        },
        reason=remark,
        object_repr=locked.order_no,
        company=locked.company,
        actor=user,
    )
    return report, locked


@transaction.atomic
def complete_order(order: ProductionOrder, *, user: Any, remark: str = "") -> ProductionOrder:
    """工单完工：全部工序完工 **且** 所有质检点检验单判定合格 / 让步接收。"""
    require_codes(user, "mes.order.complete")
    locked = (
        ProductionOrder.objects.select_for_update()
        .select_related("company")
        .filter(pk=order.pk)
        .first()
    )
    if locked is None:
        raise ObjectNotFound("生产工单不存在。", details={"order_id": order.pk})
    if locked.status == ProductionOrderStatus.COMPLETED:
        return locked
    if locked.status != ProductionOrderStatus.IN_PROGRESS:
        raise StateConflict(
            f"工单当前状态为「{locked.get_status_display()}」，不能完工。",
            code="STATE_CONFLICT",
        )
    unfinished = list(
        locked.steps.exclude(status=ProductionStepStatus.COMPLETED)
        .order_by("sequence")
        .values_list("name", flat=True)
    )
    if unfinished:
        raise StateConflict(
            f"还有工序未报满，不能完工：{'、'.join(unfinished[:5])}。",
            code="STEPS_NOT_FINISHED",
            details={"pending_steps": unfinished},
        )
    blocked: list[str] = []
    for step in locked.steps.filter(is_quality_gate=True).select_related("inspection_order"):
        inspection = step.inspection_order
        if inspection is None:
            blocked.append(f"{step.name}（未生成检验单）")
        elif inspection.judgement not in {
            QualityJudgement.PASSED,
            QualityJudgement.CONCESSION,
        }:
            blocked.append(f"{step.name}（{inspection.get_judgement_display()}）")
    if blocked:
        raise StateConflict(
            f"质检点尚未判定合格，不能完工：{'、'.join(blocked)}。",
            code="QUALITY_GATE_NOT_PASSED",
            details={"blocked_steps": blocked},
        )
    _recalculate_order(locked)
    previous = locked.status
    locked.status = ProductionOrderStatus.COMPLETED
    locked.actual_end = timezone.now()
    locked.save()
    record_audit(
        action=AuditAction.UPDATE,
        instance=locked,
        changes=build_changes(
            {"status": previous, "qualified_quantity": ""},
            {"status": locked.status, "qualified_quantity": str(locked.qualified_quantity)},
        ),
        reason=remark,
        object_repr=locked.order_no,
        company=locked.company,
        actor=user,
    )
    publish_event(
        event_type=EVENT_ORDER_COMPLETED,
        aggregate_type=AGGREGATE_ORDER,
        aggregate_id=locked.pk,
        payload={
            "order_no": locked.order_no,
            "qualified_quantity": str(locked.qualified_quantity),
            "scrap_quantity": str(locked.scrap_quantity),
        },
        dedup_key=f"mes.order:{locked.pk}:completed",
    )
    return locked


@transaction.atomic
def receipt_finished_goods(
    order: ProductionOrder,
    *,
    user: Any,
    location: Any = None,
    batch_no: str = "",
    idempotency_key: str | None = None,
) -> tuple[ProductionOrder, Any]:
    """完工入库：按合格数量经统一库存服务生成并过账一张**入库**单据。"""
    require_codes(user, "mes.order.complete", "wms.document.create", "wms.document.post")
    locked = (
        ProductionOrder.objects.select_for_update()
        .select_related("company", "product_material", "receipt_warehouse")
        .filter(pk=order.pk)
        .first()
    )
    if locked is None:
        raise ObjectNotFound("生产工单不存在。", details={"order_id": order.pk})
    if locked.receipt_document_id:
        raise StateConflict(
            f"该工单已完工入库（入库单 {locked.receipt_document.document_no}）。",
            code="RECEIPT_ALREADY_POSTED",
        )
    if locked.status != ProductionOrderStatus.COMPLETED:
        raise StateConflict(
            f"工单当前状态为「{locked.get_status_display()}」，只有已完工工单可以入库。",
            code="STATE_CONFLICT",
        )
    if locked.product_material_id is None:
        raise ValidationFailed("请先指定产出物料，才能完工入库。", code="MATERIAL_REQUIRED")
    warehouse = locked.receipt_warehouse
    if warehouse is None:
        raise ValidationFailed("请先指定完工入库仓库。", code="WAREHOUSE_REQUIRED")
    _recalculate_order(locked)
    quantity = _q(locked.qualified_quantity)
    if quantity <= ZERO:
        raise ValidationFailed("合格数量为 0，没有可入库的产出。", code="NOTHING_TO_RECEIPT")

    document = stock.create_document(
        document_type=DocumentType.RECEIPT,
        company=locked.company_id,
        warehouse=warehouse,
        user=user,
        biz_type=BIZ_TYPE_ORDER,
        biz_id=locked.pk,
        biz_no=locked.order_no,
        remark=f"生产完工入库 {locked.order_no}",
        lines=[
            {
                "material_id": locked.product_material_id,
                "location_id": _int_id(location),
                "batch_no": str(batch_no or locked.order_no)[:64],
                "quality_status": QualityStatus.QUALIFIED,
                "quantity": quantity,
                "remark": f"工单 {locked.order_no} 完工入库",
            }
        ],
    )
    stock.post_document(
        document,
        user=user,
        idempotency_key=idempotency_key or f"mes-receipt-{locked.pk}",
        reason=f"生产完工入库过账 {locked.order_no}",
    )
    locked.receipt_document = document
    locked.save(update_fields=["receipt_document", "updated_at"])
    record_audit(
        action=AuditAction.POST,
        instance=locked,
        changes={
            "inventory_document": {"before": "", "after": document.document_no},
            "quantity": {"before": "", "after": str(quantity)},
        },
        object_repr=locked.order_no,
        company=locked.company,
        actor=user,
    )
    return locked, document


@transaction.atomic
def close_order(order: ProductionOrder, *, user: Any, remark: str = "") -> ProductionOrder:
    """关闭工单：已完工 → 已关闭。关闭后视为业务终结，不再计入在制。"""
    require_codes(user, "mes.order.close")
    locked = ProductionOrder.objects.select_for_update().filter(pk=order.pk).first()
    if locked is None:
        raise ObjectNotFound("生产工单不存在。", details={"order_id": order.pk})
    if locked.status == ProductionOrderStatus.CLOSED:
        return locked
    if locked.status != ProductionOrderStatus.COMPLETED:
        raise StateConflict(
            f"工单当前状态为「{locked.get_status_display()}」，只有已完工工单可以关闭。",
            code="STATE_CONFLICT",
        )
    locked.status = ProductionOrderStatus.CLOSED
    locked.closed_at = timezone.now()
    locked.closed_by = user
    locked.save()
    record_audit(
        action=AuditAction.UPDATE,
        instance=locked,
        changes={
            "status": {
                "before": ProductionOrderStatus.COMPLETED,
                "after": ProductionOrderStatus.CLOSED,
            }
        },
        reason=remark,
        object_repr=locked.order_no,
        company=locked.company,
        actor=user,
    )
    return locked


@transaction.atomic
def cancel_order(order: ProductionOrder, *, user: Any, reason: str) -> ProductionOrder:
    """取消工单：只有草稿与已下达（未开工）工单可以取消。"""
    require_codes(user, "mes.order.cancel")
    if not str(reason or "").strip():
        raise ValidationFailed("取消必须填写原因。", code="REASON_REQUIRED")
    locked = ProductionOrder.objects.select_for_update().filter(pk=order.pk).first()
    if locked is None:
        raise ObjectNotFound("生产工单不存在。", details={"order_id": order.pk})
    if locked.status not in {ProductionOrderStatus.DRAFT, ProductionOrderStatus.RELEASED}:
        raise StateConflict(
            f"工单当前状态为「{locked.get_status_display()}」，不能取消；"
            "已开工工单请走完工流程。",
            code="STATE_CONFLICT",
        )
    previous = locked.status
    locked.status = ProductionOrderStatus.CANCELLED
    locked.cancel_reason = str(reason)[:255]
    locked.save()
    record_audit(
        action=AuditAction.UPDATE,
        instance=locked,
        changes={"status": {"before": previous, "after": ProductionOrderStatus.CANCELLED}},
        reason=reason,
        object_repr=locked.order_no,
        company=locked.company,
        actor=user,
    )
    return locked


__all__ = [
    "BIZ_TYPE_ORDER",
    "ORDER_CODE_RULE",
    "REPORT_CODE_RULE",
    "cancel_order",
    "close_order",
    "complete_order",
    "create_order",
    "issue_materials",
    "next_order_no",
    "next_report_no",
    "receipt_finished_goods",
    "release_order",
    "report_production",
    "update_order",
]
