"""设备模块的查询（备件现存量等）。

库存数字一律取自仓储模块的统一库存余额（`wms.InventoryBalance`）：
本模块**不复制、不缓存**库存，避免出现「设备模块的库存」与「仓储的库存」两套口径。
可用量 = 实存量 - 冻结量 - 占用量，与库存服务对外口径一致。
"""

from __future__ import annotations

from decimal import Decimal

from django.db.models import Q

from apps.core.selectors import scoped_queryset
from apps.equipment.models import SparePart


def spare_part_stock_rows(
    user,
    *,
    company_id: int | None = None,
    warehouse_id: int | None = None,
    part_type: str | None = None,
    below_safety_only: bool = False,
    search: str = "",
) -> list[dict]:
    """备件现存量行。

    只列出**建立了「对应物料」关系的备件**——没有对应物料的备件无法入库，
    库存表里也不会有它的余额。为了让「有备件但从未入库」这件事可见，
    没有余额记录的备件会以 0 数量、无仓库的行返回，而不是直接隐身。
    """
    from apps.wms.models import InventoryBalance

    parts = (
        SparePart.objects.filter(material__isnull=False)
        .select_related("material", "uom", "equipment_type")
        .order_by("code")
    )
    parts = scoped_queryset(parts, user, company_field="company_id")
    if company_id is not None:
        parts = parts.filter(company_id=company_id)
    if part_type:
        parts = parts.filter(part_type=part_type)
    if search:
        parts = parts.filter(
            Q(code__icontains=search) | Q(name__icontains=search) | Q(spec__icontains=search)
        )
    part_list = list(parts)
    if not part_list:
        return []

    parts_by_material: dict[int, list[SparePart]] = {}
    for part in part_list:
        parts_by_material.setdefault(part.material_id, []).append(part)

    balances = (
        InventoryBalance.objects.filter(material_id__in=list(parts_by_material))
        .select_related("material", "warehouse", "location")
        .order_by("material_id", "warehouse_id", "id")
    )
    balances = scoped_queryset(balances, user, company_field="company_id")
    if warehouse_id is not None:
        balances = balances.filter(warehouse_id=warehouse_id)

    rows: list[dict] = []
    seen: set[tuple[int, int | None]] = set()
    for balance in balances:
        for part in parts_by_material.get(balance.material_id, []):
            rows.append(_stock_row(part, balance))
            seen.add((part.id, balance.warehouse_id))

    # 没有任何余额记录的备件：库存为 0，仍然列出，便于发现「建了备件档案但从未入库」
    for part in part_list:
        has_balance = any(key[0] == part.id for key in seen)
        if not has_balance and warehouse_id is None:
            rows.append(_stock_row(part, None))

    if below_safety_only:
        rows = [row for row in rows if row["below_safety"]]
    return rows


def _stock_row(part: SparePart, balance) -> dict:
    """把「备件 + 库存余额」拍平成一行。金额与数量一律用字符串传给前端。"""
    zero = Decimal("0")
    on_hand = balance.on_hand if balance is not None else zero
    frozen = balance.frozen if balance is not None else zero
    reserved = balance.reserved if balance is not None else zero
    available = on_hand - frozen - reserved
    safety_stock = part.safety_stock or zero
    return {
        # 主键取库存余额行主键；没有任何余额时用负的备件主键占位，
        # 保证整页 id 唯一且为整数（通用列表组件按整数 id 处理行）。
        "id": balance.id if balance is not None else -part.id,
        "spare_part_id": part.id,
        "code": part.code,
        "name": part.name,
        "part_type": part.part_type,
        "spec": part.spec,
        "equipment_type_name": part.equipment_type.name if part.equipment_type_id else "",
        "uom_name": part.uom.name if part.uom_id else "",
        "warehouse_id": balance.warehouse_id if balance is not None else None,
        "warehouse_name": balance.warehouse.name if balance is not None else "",
        "location_name": (balance.location.name if balance.location_id else "")
        if balance is not None
        else "",
        "batch_no": balance.batch_no if balance is not None else "",
        "quality_status": balance.quality_status if balance is not None else "",
        "on_hand": str(on_hand),
        "frozen": str(frozen),
        "reserved": str(reserved),
        "available": str(available),
        "safety_stock": str(safety_stock),
        "below_safety": safety_stock > zero and available < safety_stock,
        "life_days": part.life_days,
    }
