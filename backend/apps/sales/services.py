"""销售业务服务：销售订单 → 审批 → 库存占用 → 发货出库 → 销售退货。

关键约定（任务书 4.3、5.3、10.3、12.1）：

* 所有金额由**后端**计算，前端提交的 `amount` / `total_amount` 一律忽略；
  舍入统一 `ROUND_HALF_UP` 保留 4 位，发生在**行金额**与**汇总**两处。
* 库存变动**只经** `apps.wms.services.stock`：本模块不写任何库存表。
  占用走 `reserve_stock`，发货走 `create_document` + `post_document`，
  退货收货走收货单据、质量放行走 `release_quality`。
* **先占用、后发货**：发货过账要求数量全部由本订单占用覆盖
  （`require_full_reservation=True`），不会占用其他订单的库存。
* 退货**先验收再判定质量状态**：收货进待检，检验后合格回库或判为不合格。
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from apps.core.constants import MONEY_DECIMAL_PLACES
from apps.core.exceptions import ObjectNotFound, StateConflict, ValidationFailed
from apps.core.models import AuditAction
from apps.core.permissions import require_codes
from apps.core.services import generate_code, publish_event, record_audit
from apps.crm.models import Customer, CustomerStatus
from apps.sales.models import (
    ReturnDisposition,
    ReturnStatus,
    SalesOrder,
    SalesOrderLine,
    SalesOrderStatus,
    SalesReturn,
    SalesReturnLine,
    SalesShipment,
    SalesShipmentLine,
    ShipmentStatus,
)
from apps.wms.models import DocumentType, QualityStatus, StockReservation, Warehouse
from apps.wms.services import stock

logger = logging.getLogger("yishang.sales")

BIZ_TYPE_ORDER = "sales.order"

EVENT_ORDER_SUBMITTED = "sales.order.submitted"
EVENT_ORDER_RESERVED = "sales.order.stock_reserved"
EVENT_SHIPMENT_POSTED = "sales.shipment.posted"
EVENT_RETURN_POSTED = "sales.return.posted"
EVENT_RETURN_INSPECTED = "sales.return.inspected"

ZERO = Decimal("0")
HUNDRED = Decimal("100")
MONEY_QUANT = Decimal(1).scaleb(-MONEY_DECIMAL_PLACES)

# 不允许下单的客户状态：暂停合作或已终止的客户不能新建销售订单（任务书 10.2 / 10.3）
BLOCKED_CUSTOMER_STATUS = (CustomerStatus.SUSPENDED, CustomerStatus.TERMINATED)


def money(value: Any) -> Decimal:
    """金额舍入：ROUND_HALF_UP，保留 MONEY_DECIMAL_PLACES 位。"""
    return Decimal(value or 0).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def compute_line_amount(quantity: Any, price: Any) -> Decimal:
    """行未税金额 = 数量 × 未税单价（先乘后舍入）。"""
    return money(Decimal(quantity or 0) * Decimal(price or 0))


def _pk(value: Any) -> int | None:
    if value is None:
        return None
    return getattr(value, "pk", value)


def _assert_customer_usable(customer: Customer) -> None:
    if customer.status in BLOCKED_CUSTOMER_STATUS:
        raise StateConflict(
            f"客户「{customer.name}」已停用，不能新建销售订单。",
            code="CUSTOMER_INACTIVE",
            details={"customer_id": customer.pk, "status": customer.status},
        )

# --------------------------------------------------------------------------
# 销售订单
# --------------------------------------------------------------------------


def _order_line_kwargs(row: dict) -> dict:
    material_id = row.get("material_id") or row.get("material")
    if material_id is None:
        raise ValidationFailed("订单明细缺少物料。", code="LINE_MATERIAL_REQUIRED")
    quantity = Decimal(row.get("quantity") or 0)
    if quantity <= ZERO:
        raise ValidationFailed("订单数量必须大于 0。", code="INVALID_LINE_QUANTITY")
    price = Decimal(row.get("price") or 0)
    if price < ZERO:
        raise ValidationFailed("单价不能为负数。", code="INVALID_LINE_PRICE")
    return {
        "material_id": _pk(material_id),
        "sku_id": _pk(row.get("sku") or row.get("sku_id")),
        "quantity": quantity,
        "price": price,
        "amount": compute_line_amount(quantity, price),
        "uom_id": _pk(row.get("uom") or row.get("uom_id")),
        "expected_date": row.get("expected_date"),
        "remark": str(row.get("remark") or "")[:255],
    }


def _replace_order_lines(order: SalesOrder, lines: Sequence[dict]) -> None:
    if not lines:
        raise ValidationFailed("销售订单必须至少包含一行明细。", code="EMPTY_DOCUMENT")
    order.lines.all().delete()
    for index, row in enumerate(lines, start=1):
        SalesOrderLine.objects.create(order=order, line_no=index, **_order_line_kwargs(row))


def recalculate_order_amounts(order: SalesOrder) -> SalesOrder:
    """按行金额汇总单头金额。行金额已在写入时舍入，这里只做汇总。"""
    total = ZERO
    for line in order.lines.all():
        total += line.amount or ZERO
    total = money(total)
    tax = money(total * (order.tax_rate or ZERO) / HUNDRED)
    order.total_amount = total
    order.tax_amount = tax
    order.amount_with_tax = money(total + tax)
    order.save(update_fields=["total_amount", "tax_amount", "amount_with_tax", "updated_at"])
    return order


@transaction.atomic
def create_order(
    *,
    user: Any,
    company: Any,
    customer: Customer,
    lines: Sequence[dict],
    order_date: Any = None,
    expected_date: Any = None,
    priority: str = "normal",
    warehouse: Warehouse | None = None,
    salesman: Any = None,
    tax_rate: Any = 0,
    payment_terms: str = "",
    delivery_address: str = "",
    currency: str = "CNY",
    remark: str = "",
    order_no: str = "",
) -> SalesOrder:
    require_codes(user, "sales.order.create")
    if customer.company_id != _pk(company):
        raise ValidationFailed("客户与订单所属公司不一致。", code="COMPANY_CUSTOMER_MISMATCH")
    _assert_customer_usable(customer)
    if Decimal(tax_rate or 0) < ZERO or Decimal(tax_rate or 0) > HUNDRED:
        raise ValidationFailed("税率必须在 0~100 之间。", code="INVALID_TAX_RATE")

    order = SalesOrder(
        company_id=_pk(company),
        order_no=str(order_no or "").strip() or generate_code("SO"),
        customer=customer,
        status=SalesOrderStatus.DRAFT,
        salesman_id=_pk(salesman) or _pk(user),
        order_date=order_date,
        expected_date=expected_date,
        priority=priority,
        warehouse=warehouse,
        currency=currency or "CNY",
        tax_rate=Decimal(tax_rate or 0),
        payment_terms=payment_terms,
        delivery_address=delivery_address,
        remark=remark,
    )
    order.save()
    _replace_order_lines(order, lines)
    recalculate_order_amounts(order)
    record_audit(
        action=AuditAction.CREATE,
        instance=order,
        changes={
            "order_no": {"before": "", "after": order.order_no},
            "status": {"before": "", "after": order.status},
            "amount_with_tax": {"before": "0", "after": str(order.amount_with_tax)},
            "line_count": {"before": 0, "after": len(lines)},
        },
        reason=remark,
        object_repr=order.order_no,
        company=order.company,
        actor=user,
    )
    logger.info("销售订单创建 order=%s customer=%s", order.order_no, customer.pk)
    return order


@transaction.atomic
def update_order(
    order: SalesOrder, *, user: Any, lines: Sequence[dict] | None = None, **header: Any
) -> SalesOrder:
    """修改草稿订单。已提交/已批准订单不允许直接改明细（任务书 10.3）。"""
    require_codes(user, "sales.order.update")
    locked = SalesOrder.objects.select_for_update().filter(pk=order.pk).first()
    if locked is None:
        raise ObjectNotFound("销售订单不存在。", details={"order_id": order.pk})
    if locked.status != SalesOrderStatus.DRAFT:
        raise StateConflict(
            "只有草稿状态的销售订单可以修改；已提交订单请撤回后再改。",
            code="STATE_CONFLICT",
            details={"order_no": locked.order_no, "status": locked.status},
        )
    changed: dict[str, Any] = {}
    for field, value in header.items():
        if value is None:
            continue
        current = getattr(locked, field)
        if current != value:
            changed[field] = {"before": current, "after": value}
            setattr(locked, field, value)
    if changed:
        locked.save()
    if lines is not None:
        _replace_order_lines(locked, lines)
        changed["line_count"] = {"before": 0, "after": len(lines)}
    recalculate_order_amounts(locked)
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


@transaction.atomic
def submit_order(order: SalesOrder, *, user: Any, comment: str = "") -> SalesOrder:
    require_codes(user, "sales.order.submit")
    from apps.workflow import services as workflow_services

    locked = SalesOrder.objects.select_for_update().get(pk=order.pk)
    if locked.status != SalesOrderStatus.DRAFT:
        raise StateConflict("只有草稿状态的销售订单可以提交。", code="STATE_CONFLICT")
    if not locked.lines.exists():
        raise ValidationFailed("销售订单没有明细，不能提交。", code="EMPTY_DOCUMENT")
    instance = workflow_services.create_instance(
        user,
        title=f"销售订单 {locked.order_no}",
        biz_type=BIZ_TYPE_ORDER,
        biz_id=str(locked.pk),
        biz_no=locked.order_no,
        summary=locked.remark,
        amount=locked.amount_with_tax,
        company=locked.company,
        department=getattr(user, "department", None),
    )
    workflow_services.submit_instance(user, instance, comment=comment)
    locked.status = SalesOrderStatus.SUBMITTED
    locked.approval_instance_id = instance.pk
    locked.save(update_fields=["status", "approval_instance_id", "updated_at"])
    record_audit(
        action=AuditAction.SUBMIT,
        instance=locked,
        changes={"status": {"before": SalesOrderStatus.DRAFT, "after": SalesOrderStatus.SUBMITTED}},
        reason=comment,
        object_repr=locked.order_no,
        approval_basis=f"workflow.ApprovalInstance#{instance.pk}",
        company=locked.company,
        actor=user,
    )
    publish_event(
        event_type=EVENT_ORDER_SUBMITTED,
        aggregate_type="sales.SalesOrder",
        aggregate_id=locked.pk,
        payload={
            "order_id": locked.pk,
            "order_no": locked.order_no,
            "amount_with_tax": str(locked.amount_with_tax),
        },
        dedup_key=f"sales.order:{locked.pk}:submitted",
    )
    return locked


def on_order_approval_outcome(instance, outcome: str) -> None:
    """审批终结回写销售订单状态（由 workflow.registry 在同一事务内调用）。"""
    from apps.workflow.registry import OUTCOME_APPROVED, OUTCOME_REJECTED, OUTCOME_WITHDRAWN

    order = SalesOrder.objects.filter(pk=instance.biz_id).first()
    if order is None or order.status != SalesOrderStatus.SUBMITTED:
        return
    if outcome == OUTCOME_APPROVED:
        order.status = SalesOrderStatus.APPROVED
        order.approved_at = timezone.now()
    elif outcome == OUTCOME_REJECTED:
        order.status = SalesOrderStatus.REJECTED
    elif outcome == OUTCOME_WITHDRAWN:
        order.status = SalesOrderStatus.DRAFT
    else:  # pragma: no cover - 未知结果不应出现
        return
    order.save(update_fields=["status", "approved_at", "updated_at"])
    record_audit(
        action=AuditAction.APPROVE
        if outcome == OUTCOME_APPROVED
        else (AuditAction.REJECT if outcome == OUTCOME_REJECTED else AuditAction.WITHDRAW),
        instance=order,
        changes={"status": {"before": SalesOrderStatus.SUBMITTED, "after": order.status}},
        object_repr=order.order_no,
        approval_basis=f"workflow.ApprovalInstance#{instance.pk}",
        company=order.company,
        actor=instance.applicant,
    )

@transaction.atomic
def cancel_order(order: SalesOrder, *, user: Any, reason: str) -> SalesOrder:
    """取消订单。已发货的订单不能取消（任务书 10.3：已发货部分不得直接删除）。"""
    require_codes(user, "sales.order.update")
    if not str(reason or "").strip():
        raise ValidationFailed("取消必须填写原因。", code="REASON_REQUIRED")
    locked = SalesOrder.objects.select_for_update().get(pk=order.pk)
    if locked.status == SalesOrderStatus.CANCELLED:
        raise StateConflict("该销售订单已取消。", code="STATE_CONFLICT")
    if locked.status not in SalesOrderStatus.cancellable():
        raise StateConflict(
            f"订单当前状态为「{locked.get_status_display()}」，不能取消；"
            "已发货的部分请走退货流程，剩余部分可关闭订单。",
            code="HAS_SHIPMENT",
            details={"status": locked.status},
        )
    if locked.shipments.exclude(status=ShipmentStatus.CANCELLED).exists():
        raise StateConflict("该订单已有发货单，不能取消；请先处理发货单。", code="HAS_SHIPMENT")
    previous = locked.status
    locked.status = SalesOrderStatus.CANCELLED
    locked.save(update_fields=["status", "updated_at"])
    # 取消订单必须释放尚未消耗的占用，否则可用量会被长期锁死
    released = stock.release_reservations_for_biz(
        user=user, biz_type=BIZ_TYPE_ORDER, biz_id=locked.pk, reason=f"订单取消：{reason[:200]}"
    )
    record_audit(
        action=AuditAction.UPDATE,
        instance=locked,
        changes={
            "status": {"before": previous, "after": locked.status},
            "released_reservations": {"before": 0, "after": len(released)},
        },
        reason=reason,
        object_repr=locked.order_no,
        company=locked.company,
        actor=user,
    )
    return locked


@transaction.atomic
def close_order(order: SalesOrder, *, user: Any, reason: str = "") -> SalesOrder:
    """关闭订单：不再发货。剩余未发货数量作废，占用一并释放。"""
    require_codes(user, "sales.order.close")
    locked = SalesOrder.objects.select_for_update().get(pk=order.pk)
    if locked.status == SalesOrderStatus.CLOSED:
        return locked
    if locked.status not in (*SalesOrderStatus.open_for_shipment(), SalesOrderStatus.SHIPPED):
        raise StateConflict(
            f"订单当前状态为「{locked.get_status_display()}」，不能关闭。",
            code="STATE_CONFLICT",
            details={"status": locked.status},
        )
    previous = locked.status
    locked.status = SalesOrderStatus.CLOSED
    locked.closed_at = timezone.now()
    locked.save(update_fields=["status", "closed_at", "updated_at"])
    stock.release_reservations_for_biz(
        user=user, biz_type=BIZ_TYPE_ORDER, biz_id=locked.pk, reason=f"订单关闭：{reason[:200]}"
    )
    record_audit(
        action=AuditAction.UPDATE,
        instance=locked,
        changes={"status": {"before": previous, "after": locked.status}},
        reason=reason,
        object_repr=locked.order_no,
        company=locked.company,
        actor=user,
    )
    return locked


# --------------------------------------------------------------------------
# 库存占用
# --------------------------------------------------------------------------


@transaction.atomic
def reserve_order_stock(
    order: SalesOrder,
    *,
    user: Any,
    reason: str = "",
    location: Any = None,
    batch_no: str = "",
    roll_no: str = "",
) -> list[StockReservation]:
    """按订单未发货数量占用库存（任务书 10.3「库存占用」）。

    * 只能占用**合格**库存；待检与不合格库存不参与占用；
    * 幂等：每行使用固定 `dedup_key`，重复点击「库存占用」不会重复占用；
    * 部分发货后再次调用返回原有占用记录（不会重复累加）；
    * 占用维度为「订单发货仓库 + 无储位/无批次（或传入的储位批次）」，
      发货明细必须使用**同一维度**，否则占用覆盖校验会拒绝出库。
    """
    require_codes(user, "sales.order.reserve", "wms.inventory.reserve")
    locked = SalesOrder.objects.select_for_update().get(pk=order.pk)
    if locked.status not in SalesOrderStatus.open_for_shipment():
        raise StateConflict(
            f"订单当前状态为「{locked.get_status_display()}」，不能占用库存；"
            "只有已批准与部分发货的订单可以占用。",
            code="ORDER_NOT_RESERVABLE",
            details={"status": locked.status},
        )
    warehouse = locked.warehouse
    if warehouse is None:
        raise ValidationFailed("订单未指定发货仓库，无法占用库存。", code="WAREHOUSE_REQUIRED")
    reservations: list[StockReservation] = []
    for line in locked.lines.select_related("material").order_by("line_no"):
        quantity = line.remaining_quantity
        if quantity <= ZERO:
            continue
        # 未指定储位/批次时按「可用量最大的合格维度」占用（库位推荐）；
        # 发货单行留空时后端按占用维度出库，保证占用维度 = 出库维度。
        target_location, target_batch, target_roll = location, batch_no, roll_no
        if location is None and not batch_no and not roll_no:
            chosen = stock.choose_reservation_dimension(
                company=locked.company_id,
                warehouse=warehouse,
                material=line.material,
                quantity=quantity,
            )
            if chosen is not None:
                target_location = chosen["location"]
                target_batch = chosen["batch_no"]
                target_roll = chosen["roll_no"]
        reservations.append(
            stock.reserve_stock(
                user=user,
                company=locked.company_id,
                warehouse=warehouse,
                material=line.material,
                quantity=quantity,
                biz_type=BIZ_TYPE_ORDER,
                biz_id=locked.pk,
                biz_no=locked.order_no,
                location=target_location,
                batch_no=target_batch,
                roll_no=target_roll,
                quality_status=QualityStatus.QUALIFIED,
                dedup_key=f"sales-order-{locked.pk}-line-{line.pk}",
                reason=reason or f"销售订单 {locked.order_no} 第 {line.line_no} 行占用",
            )
        )
    record_audit(
        action=AuditAction.UPDATE,
        instance=locked,
        changes={
            "reserved_lines": {"before": 0, "after": len(reservations)},
            "reserved_quantity": {
                "before": 0,
                "after": sum((item.quantity for item in reservations), ZERO),
            },
        },
        reason=reason,
        object_repr=locked.order_no,
        company=locked.company,
        actor=user,
    )
    publish_event(
        event_type=EVENT_ORDER_RESERVED,
        aggregate_type="sales.SalesOrder",
        aggregate_id=locked.pk,
        payload={
            "order_id": locked.pk,
            "order_no": locked.order_no,
            "reservation_ids": [item.pk for item in reservations],
        },
        dedup_key=f"sales.order:{locked.pk}:reserved:{len(reservations)}",
    )
    return reservations


@transaction.atomic
def release_order_stock(order: SalesOrder, *, user: Any, reason: str) -> list[StockReservation]:
    """释放订单尚未消耗的占用（订单取消、关闭，或人工释放）。"""
    require_codes(user, "sales.order.release", "wms.inventory.release")
    if not str(reason or "").strip():
        raise ValidationFailed("释放占用必须填写原因。", code="REASON_REQUIRED")
    locked = SalesOrder.objects.select_for_update().get(pk=order.pk)
    released = stock.release_reservations_for_biz(
        user=user, biz_type=BIZ_TYPE_ORDER, biz_id=locked.pk, reason=reason
    )
    record_audit(
        action=AuditAction.UPDATE,
        instance=locked,
        changes={"released_reservations": {"before": 0, "after": len(released)}},
        reason=reason,
        object_repr=locked.order_no,
        company=locked.company,
        actor=user,
    )
    return released

# --------------------------------------------------------------------------
# 销售发货
# --------------------------------------------------------------------------


def _shipment_line_kwargs(row: dict) -> dict:
    order_line = row.get("order_line")
    if order_line is None:
        raise ValidationFailed("发货明细缺少订单行。", code="ORDER_LINE_REQUIRED")
    quantity = Decimal(row.get("quantity") or 0)
    if quantity <= ZERO:
        raise ValidationFailed("发货数量必须大于 0。", code="INVALID_LINE_QUANTITY")
    return {
        "order_line_id": _pk(order_line),
        "material_id": _pk(getattr(order_line, "material_id", None) or row.get("material")),
        "quantity": quantity,
        "location_id": _pk(row.get("location") or row.get("location_id")),
        "batch_no": str(row.get("batch_no") or "").strip(),
        "roll_no": str(row.get("roll_no") or "").strip(),
        "remark": str(row.get("remark") or "")[:255],
    }


def _replace_shipment_lines(shipment: SalesShipment, lines: Sequence[dict]) -> None:
    if not lines:
        raise ValidationFailed("发货单必须至少包含一行明细。", code="EMPTY_DOCUMENT")
    shipment.lines.all().delete()
    for index, row in enumerate(lines, start=1):
        SalesShipmentLine.objects.create(
            shipment=shipment, line_no=index, **_shipment_line_kwargs(row)
        )


def _assert_shipment_quantities(
    shipment: SalesShipment, rows: Sequence[dict], *, exclude_self: bool = True
) -> None:
    """发货数量不得超过订单行未发货数量；同订单其他**草稿**发货单也计入占用。"""
    pending: dict[int, Decimal] = {}
    if exclude_self:
        others = SalesShipmentLine.objects.filter(
            shipment__sales_order_id=shipment.sales_order_id,
            shipment__status=ShipmentStatus.DRAFT,
        ).exclude(shipment_id=shipment.pk)
        for line in others:
            pending[line.order_line_id] = pending.get(line.order_line_id, ZERO) + line.quantity
    for row in rows:
        order_line = row["order_line"]
        if order_line.order_id != shipment.sales_order_id:
            raise ValidationFailed(
                "发货明细的订单行不属于该销售订单。",
                code="ORDER_LINE_MISMATCH",
                details={"order_line_id": order_line.pk},
            )
        remaining = order_line.remaining_quantity - pending.get(order_line.pk, ZERO)
        if row["quantity"] > remaining:
            raise ValidationFailed(
                f"物料 {order_line.material_id} 发货数量超过订单未发货数量。",
                code="OVER_SHIPMENT",
                details={"requested": str(row["quantity"]), "available": str(remaining)},
            )


@transaction.atomic
def create_shipment(
    *,
    user: Any,
    order: SalesOrder,
    warehouse: Warehouse,
    lines: Sequence[dict],
    receiver_name: str = "",
    receiver_phone: str = "",
    delivery_address: str = "",
    carrier: str = "",
    tracking_no: str = "",
    shipment_no: str = "",
    remark: str = "",
) -> SalesShipment:
    require_codes(user, "sales.shipment.create")
    order = SalesOrder.objects.select_for_update().get(pk=order.pk)
    if order.status not in SalesOrderStatus.open_for_shipment():
        raise StateConflict(
            f"销售订单当前状态为「{order.get_status_display()}」，不能创建发货单。",
            code="ORDER_NOT_SHIPPABLE",
            details={"status": order.status},
        )
    if order.warehouse_id and order.warehouse_id != warehouse.pk:
        raise ValidationFailed(
            "发货仓库与订单指定的发货仓库不一致。",
            code="WAREHOUSE_MISMATCH",
            details={"order_warehouse_id": order.warehouse_id, "warehouse_id": warehouse.pk},
        )
    shipment = SalesShipment(
        company_id=order.company_id,
        shipment_no=str(shipment_no or "").strip() or generate_code("SH"),
        sales_order=order,
        customer_id=order.customer_id,
        status=ShipmentStatus.DRAFT,
        warehouse=warehouse,
        receiver_name=receiver_name,
        receiver_phone=receiver_phone,
        delivery_address=delivery_address or order.delivery_address,
        carrier=carrier,
        tracking_no=tracking_no,
        remark=remark,
    )
    shipment.save()
    _assert_shipment_quantities(shipment, lines)
    _replace_shipment_lines(shipment, lines)
    record_audit(
        action=AuditAction.CREATE,
        instance=shipment,
        changes={
            "shipment_no": {"before": "", "after": shipment.shipment_no},
            "order_no": {"before": "", "after": order.order_no},
            "line_count": {"before": 0, "after": len(lines)},
        },
        reason=remark,
        object_repr=shipment.shipment_no,
        company=shipment.company,
        actor=user,
    )
    return shipment


@transaction.atomic
def update_shipment(
    shipment: SalesShipment, *, user: Any, lines: Sequence[dict] | None = None, **header: Any
) -> SalesShipment:
    require_codes(user, "sales.shipment.update")
    locked = SalesShipment.objects.select_for_update().filter(pk=shipment.pk).first()
    if locked is None:
        raise ObjectNotFound("发货单不存在。", details={"shipment_id": shipment.pk})
    if locked.status != ShipmentStatus.DRAFT:
        raise StateConflict(
            "只有草稿状态的发货单可以修改；已出库发货单请走退货流程。",
            code="STATE_CONFLICT",
            details={"shipment_no": locked.shipment_no, "status": locked.status},
        )
    changed: dict[str, Any] = {}
    for field, value in header.items():
        if value is None:
            continue
        current = getattr(locked, field)
        if current != value:
            changed[field] = {"before": current, "after": value}
            setattr(locked, field, value)
    if changed:
        locked.save()
    if lines is not None:
        _assert_shipment_quantities(locked, lines)
        _replace_shipment_lines(locked, lines)
        changed["line_count"] = {"before": 0, "after": len(lines)}
    if changed:
        record_audit(
            action=AuditAction.UPDATE,
            instance=locked,
            changes=changed,
            object_repr=locked.shipment_no,
            company=locked.company,
            actor=user,
        )
    return locked


def _refresh_order_shipment_status(order: SalesOrder) -> None:
    """按累计发货数量收敛订单状态（不改动已关闭/已取消订单）。"""
    lines = list(order.lines.all())
    if not lines:
        return
    total = sum((line.quantity or ZERO for line in lines), ZERO)
    shipped = sum((line.shipped_quantity or ZERO for line in lines), ZERO)
    if shipped <= ZERO:
        target = None
    elif shipped >= total:
        target = SalesOrderStatus.SHIPPED
    else:
        target = SalesOrderStatus.PARTIALLY_SHIPPED
    if target is None or order.status == target:
        return
    if order.status not in SalesOrderStatus.open_for_shipment():
        return
    order.status = target
    order.save(update_fields=["status", "updated_at"])

@transaction.atomic
def _shipment_document_lines(
    order: SalesOrder, lines: Sequence[SalesShipmentLine], *, shipment_no: str
) -> list[dict[str, Any]]:
    """把发货单行转成库存出库行；**出库维度与占用维度保持一致**。

    行上留空的储位 / 批次 / 卷号由该订单物料的未结占用推导，这样即使前端
    没有填储位（正常情况），出库维度也与占用维度完全相同，不会被
    `require_full_reservation` 误判为「占用覆盖不足」（任务书 10.8）。
    """
    rows: list[dict[str, Any]] = []
    for line in lines:
        hint = (
            stock.open_reservation_hint(
                biz_type=BIZ_TYPE_ORDER, biz_id=order.pk, material_id=line.material_id
            )
            or {}
        )
        rows.append(
            {
                "material_id": line.material_id,
                "location_id": line.location_id or hint.get("location_id"),
                "batch_no": line.batch_no or hint.get("batch_no", ""),
                "roll_no": line.roll_no or hint.get("roll_no", ""),
                "quality_status": QualityStatus.QUALIFIED,
                "quantity": line.quantity,
                "remark": f"发货单 {shipment_no} 第 {line.line_no} 行",
            }
        )
    return rows


def post_shipment(
    shipment: SalesShipment, *, user: Any, idempotency_key: str | None = None
) -> SalesShipment:
    """发货过账：**出库**扣减库存，并消耗本订单的占用。

    * 「先占用、后发货」：数量必须全部由本订单占用覆盖，否则拒绝
      （`RESERVATION_REQUIRED`），不会占用其他订单的库存；
    * 占用消耗与实存量扣减在统一库存服务的**同一事务**内完成。
    """
    require_codes(user, "sales.shipment.post", "wms.document.create", "wms.document.post")
    locked = (
        SalesShipment.objects.select_for_update()
        .select_related("sales_order", "warehouse", "company")
        .filter(pk=shipment.pk)
        .first()
    )
    if locked is None:
        raise ObjectNotFound("发货单不存在。", details={"shipment_id": shipment.pk})
    if locked.status == ShipmentStatus.POSTED:
        # 幂等：已过账直接返回，不重复扣减库存
        return locked
    if locked.status != ShipmentStatus.DRAFT:
        raise StateConflict("只有草稿状态的发货单可以过账。", code="STATE_CONFLICT")

    order = SalesOrder.objects.select_for_update().get(pk=locked.sales_order_id)
    if order.status not in SalesOrderStatus.open_for_shipment():
        raise StateConflict(
            f"销售订单当前状态为「{order.get_status_display()}」，不能发货。",
            code="ORDER_NOT_SHIPPABLE",
            details={"status": order.status},
        )
    lines = list(
        locked.lines.select_related("order_line", "material", "location").order_by("line_no")
    )
    if not lines:
        raise ValidationFailed("发货单没有明细，不能过账。", code="EMPTY_DOCUMENT")

    for line in lines:
        order_line = SalesOrderLine.objects.select_for_update().get(pk=line.order_line_id)
        remaining = order_line.remaining_quantity
        if line.quantity > remaining:
            raise ValidationFailed(
                f"物料 {order_line.material_id} 发货数量超过订单未发货数量。",
                code="OVER_SHIPMENT",
                details={"requested": str(line.quantity), "available": str(remaining)},
            )

    document = stock.create_document(
        document_type=DocumentType.ISSUE,
        company=locked.company_id,
        warehouse=locked.warehouse,
        user=user,
        biz_type=BIZ_TYPE_ORDER,
        biz_id=order.pk,
        biz_no=order.order_no,
        remark=f"销售发货 {locked.shipment_no}",
        lines=_shipment_document_lines(order, lines, shipment_no=locked.shipment_no),
    )
    stock.post_document(
        document,
        user=user,
        idempotency_key=idempotency_key or f"sales-shipment-{locked.pk}",
        reason=f"销售发货过账 {locked.shipment_no}",
        # 销售发货必须来自本订单占用：未占用就出库会被拒绝
        require_full_reservation=True,
    )

    for line in lines:
        SalesOrderLine.objects.filter(pk=line.order_line_id).update(
            shipped_quantity=F("shipped_quantity") + line.quantity
        )
    order.refresh_from_db(fields=["status"])
    _refresh_order_shipment_status(order)

    locked.status = ShipmentStatus.POSTED
    locked.shipped_at = timezone.now()
    locked.shipped_by = user
    locked.issue_document_id = document.pk
    locked.save(
        update_fields=["status", "shipped_at", "shipped_by", "issue_document_id", "updated_at"]
    )
    record_audit(
        action=AuditAction.POST,
        instance=locked,
        changes={
            "status": {"before": ShipmentStatus.DRAFT, "after": ShipmentStatus.POSTED},
            "inventory_document": {"before": "", "after": document.document_no},
        },
        object_repr=locked.shipment_no,
        company=locked.company,
        actor=user,
    )
    publish_event(
        event_type=EVENT_SHIPMENT_POSTED,
        aggregate_type="sales.SalesShipment",
        aggregate_id=locked.pk,
        payload={
            "shipment_id": locked.pk,
            "shipment_no": locked.shipment_no,
            "order_no": order.order_no,
            "inventory_document_no": document.document_no,
        },
        dedup_key=f"sales.shipment:{locked.pk}:posted",
    )
    logger.info("销售发货过账 shipment=%s order=%s", locked.shipment_no, order.order_no)
    return locked


@transaction.atomic
def cancel_shipment(shipment: SalesShipment, *, user: Any, reason: str) -> SalesShipment:
    require_codes(user, "sales.shipment.update")
    if not str(reason or "").strip():
        raise ValidationFailed("取消必须填写原因。", code="REASON_REQUIRED")
    locked = SalesShipment.objects.select_for_update().filter(pk=shipment.pk).first()
    if locked is None:
        raise ObjectNotFound("发货单不存在。", details={"shipment_id": shipment.pk})
    if locked.status != ShipmentStatus.DRAFT:
        raise StateConflict(
            "已出库的发货单不能取消；请通过销售退货流程处理。", code="STATE_CONFLICT"
        )
    locked.status = ShipmentStatus.CANCELLED
    locked.save(update_fields=["status", "updated_at"])
    record_audit(
        action=AuditAction.UPDATE,
        instance=locked,
        changes={"status": {"before": ShipmentStatus.DRAFT, "after": ShipmentStatus.CANCELLED}},
        reason=reason,
        object_repr=locked.shipment_no,
        company=locked.company,
        actor=user,
    )
    return locked

# --------------------------------------------------------------------------
# 销售退货
# --------------------------------------------------------------------------


def _return_line_kwargs(row: dict) -> dict:
    order_line = row.get("order_line")
    if order_line is None:
        raise ValidationFailed("退货明细缺少订单行。", code="ORDER_LINE_REQUIRED")
    quantity = Decimal(row.get("quantity") or 0)
    if quantity <= ZERO:
        raise ValidationFailed("退货数量必须大于 0。", code="INVALID_LINE_QUANTITY")
    return {
        "order_line_id": _pk(order_line),
        "material_id": _pk(getattr(order_line, "material_id", None) or row.get("material")),
        "quantity": quantity,
        "location_id": _pk(row.get("location") or row.get("location_id")),
        "batch_no": str(row.get("batch_no") or "").strip(),
        "roll_no": str(row.get("roll_no") or "").strip(),
        "remark": str(row.get("remark") or "")[:255],
    }


def _replace_return_lines(return_doc: SalesReturn, lines: Sequence[dict]) -> None:
    if not lines:
        raise ValidationFailed("退货单必须至少包含一行明细。", code="EMPTY_DOCUMENT")
    return_doc.lines.all().delete()
    for index, row in enumerate(lines, start=1):
        SalesReturnLine.objects.create(
            return_doc=return_doc, line_no=index, **_return_line_kwargs(row)
        )


def _assert_return_quantities(
    return_doc: SalesReturn, rows: Sequence[dict], *, exclude_self: bool = True
) -> None:
    """退货数量不得超过订单行「已发货 - 已退货」数量；草稿退货单同样计入占用。"""
    pending: dict[int, Decimal] = {}
    if exclude_self:
        others = SalesReturnLine.objects.filter(
            return_doc__sales_order_id=return_doc.sales_order_id,
            return_doc__status=ReturnStatus.DRAFT,
        ).exclude(return_doc_id=return_doc.pk)
        for line in others:
            pending[line.order_line_id] = pending.get(line.order_line_id, ZERO) + line.quantity
    for row in rows:
        order_line = row["order_line"]
        if order_line.order_id != return_doc.sales_order_id:
            raise ValidationFailed(
                "退货明细的订单行不属于该销售订单。",
                code="ORDER_LINE_MISMATCH",
                details={"order_line_id": order_line.pk},
            )
        available = order_line.returnable_quantity - pending.get(order_line.pk, ZERO)
        if row["quantity"] > available:
            raise ValidationFailed(
                f"物料 {order_line.material_id} 退货数量超过可退货数量。",
                code="OVER_RETURN",
                details={"requested": str(row["quantity"]), "available": str(available)},
            )


@transaction.atomic
def create_return(
    *,
    user: Any,
    order: SalesOrder,
    warehouse: Warehouse,
    lines: Sequence[dict],
    shipment: SalesShipment | None = None,
    reason: str = "",
    return_no: str = "",
    remark: str = "",
) -> SalesReturn:
    require_codes(user, "sales.return.create")
    order = SalesOrder.objects.select_for_update().get(pk=order.pk)
    if not order.shipments.filter(status=ShipmentStatus.POSTED).exists():
        raise StateConflict("该订单还没有已出库的发货单，不能创建退货单。", code="NO_SHIPMENT")
    return_doc = SalesReturn(
        company_id=order.company_id,
        return_no=str(return_no or "").strip() or generate_code("SR"),
        sales_order=order,
        shipment=shipment,
        customer_id=order.customer_id,
        status=ReturnStatus.DRAFT,
        warehouse=warehouse,
        reason=reason,
        remark=remark,
    )
    return_doc.save()
    _assert_return_quantities(return_doc, lines)
    _replace_return_lines(return_doc, lines)
    record_audit(
        action=AuditAction.CREATE,
        instance=return_doc,
        changes={
            "return_no": {"before": "", "after": return_doc.return_no},
            "order_no": {"before": "", "after": order.order_no},
            "line_count": {"before": 0, "after": len(lines)},
        },
        reason=reason,
        object_repr=return_doc.return_no,
        company=return_doc.company,
        actor=user,
    )
    return return_doc


@transaction.atomic
def update_return(
    return_doc: SalesReturn, *, user: Any, lines: Sequence[dict] | None = None, **header: Any
) -> SalesReturn:
    require_codes(user, "sales.return.update")
    locked = SalesReturn.objects.select_for_update().filter(pk=return_doc.pk).first()
    if locked is None:
        raise ObjectNotFound("退货单不存在。", details={"return_id": return_doc.pk})
    if locked.status != ReturnStatus.DRAFT:
        raise StateConflict(
            "只有草稿状态的退货单可以修改。",
            code="STATE_CONFLICT",
            details={"return_no": locked.return_no, "status": locked.status},
        )
    changed: dict[str, Any] = {}
    for field, value in header.items():
        if value is None:
            continue
        current = getattr(locked, field)
        if current != value:
            changed[field] = {"before": current, "after": value}
            setattr(locked, field, value)
    if changed:
        locked.save()
    if lines is not None:
        _assert_return_quantities(locked, lines)
        _replace_return_lines(locked, lines)
        changed["line_count"] = {"before": 0, "after": len(lines)}
    if changed:
        record_audit(
            action=AuditAction.UPDATE,
            instance=locked,
            changes=changed,
            object_repr=locked.return_no,
            company=locked.company,
            actor=user,
        )
    return locked


@transaction.atomic
def _inherit_return_dimensions(
    return_doc: SalesReturn, lines: Sequence[SalesReturnLine]
) -> None:
    """退货行没有填储位 / 批次 / 卷号时，从**原发货的出库单据**继承该物料的维度。

    继承结果会**写回退货行**：收货过账与后续检验判定的质量放行必须落在同一个
    维度上，否则放行会因为「该维度没有待检库存」而失败；同时保证退回的货物回到
    它原本出库的批次，批次追溯不断链（任务书 9.4）。
    """
    if not return_doc.shipment_id:
        return
    issue_document_id = (
        SalesShipment.objects.filter(pk=return_doc.shipment_id)
        .values_list("issue_document_id", flat=True)
        .first()
    )
    if not issue_document_id:
        return
    for line in lines:
        if line.location_id or line.batch_no or line.roll_no:
            continue
        hint = (
            stock.document_line_hint(
                document_id=issue_document_id, material_id=line.material_id
            )
            or {}
        )
        if not hint:
            continue
        line.location_id = hint.get("location_id")
        line.batch_no = hint.get("batch_no", "")
        line.roll_no = hint.get("roll_no", "")
        line.save(update_fields=["location_id", "batch_no", "roll_no", "updated_at"])


def _return_document_lines(lines: Sequence[SalesReturnLine]) -> list[dict[str, Any]]:
    """把退货单行转成入库行：退回货物一律先进入**待检**库存。"""
    return [
        {
            "material_id": line.material_id,
            "location_id": line.location_id,
            "batch_no": line.batch_no,
            "roll_no": line.roll_no,
            "quality_status": QualityStatus.QUARANTINE,
            "direction": "in",
            "quantity": line.quantity,
            "remark": f"{line.return_doc.return_no} 第 {line.line_no} 行",
        }
        for line in lines
    ]


def post_return(
    return_doc: SalesReturn, *, user: Any, idempotency_key: str | None = None
) -> SalesReturn:
    """退货收货过账：退回货物**先进入待检库存**，不代表可以直接再销售。"""
    require_codes(user, "sales.return.post", "wms.document.create", "wms.document.post")
    locked = (
        SalesReturn.objects.select_for_update()
        .select_related("sales_order", "warehouse", "company")
        .filter(pk=return_doc.pk)
        .first()
    )
    if locked is None:
        raise ObjectNotFound("退货单不存在。", details={"return_id": return_doc.pk})
    if locked.status == ReturnStatus.POSTED:
        return locked
    if locked.status != ReturnStatus.DRAFT:
        raise StateConflict("只有草稿状态的退货单可以收货过账。", code="STATE_CONFLICT")
    lines = list(
        locked.lines.select_related("order_line", "material", "location").order_by("line_no")
    )
    if not lines:
        raise ValidationFailed("退货单没有明细，不能过账。", code="EMPTY_DOCUMENT")
    for line in lines:
        order_line = SalesOrderLine.objects.select_for_update().get(pk=line.order_line_id)
        available = order_line.returnable_quantity
        if line.quantity > available:
            raise ValidationFailed(
                f"物料 {order_line.material_id} 退货数量超过可退货数量。",
                code="OVER_RETURN",
                details={"requested": str(line.quantity), "available": str(available)},
            )

    _inherit_return_dimensions(locked, lines)
    document = stock.create_document(
        document_type=DocumentType.RECEIPT,
        company=locked.company_id,
        warehouse=locked.warehouse,
        user=user,
        biz_type="sales.return",
        biz_id=locked.pk,
        biz_no=locked.return_no,
        remark=f"销售退货 {locked.return_no}",
        lines=_return_document_lines(lines),
    )
    stock.post_document(
        document,
        user=user,
        idempotency_key=idempotency_key or f"sales-return-{locked.pk}",
        reason=f"销售退货收货 {locked.return_no}",
    )

    for line in lines:
        SalesOrderLine.objects.filter(pk=line.order_line_id).update(
            returned_quantity=F("returned_quantity") + line.quantity
        )
    locked.status = ReturnStatus.POSTED
    locked.received_at = timezone.now()
    locked.received_by = user
    locked.receipt_document_id = document.pk
    locked.save(
        update_fields=["status", "received_at", "received_by", "receipt_document_id", "updated_at"]
    )
    record_audit(
        action=AuditAction.POST,
        instance=locked,
        changes={
            "status": {"before": ReturnStatus.DRAFT, "after": ReturnStatus.POSTED},
            "inventory_document": {"before": "", "after": document.document_no},
        },
        object_repr=locked.return_no,
        company=locked.company,
        actor=user,
    )
    publish_event(
        event_type=EVENT_RETURN_POSTED,
        aggregate_type="sales.SalesReturn",
        aggregate_id=locked.pk,
        payload={
            "return_id": locked.pk,
            "return_no": locked.return_no,
            "order_no": locked.sales_order.order_no,
            "inventory_document_no": document.document_no,
        },
        dedup_key=f"sales.return:{locked.pk}:posted",
    )
    return locked

@transaction.atomic
def inspect_return(
    return_doc: SalesReturn,
    *,
    user: Any,
    result: str,
    remark: str = "",
    idempotency_key: str | None = None,
) -> SalesReturn:
    """退货检验判定：调用统一库存服务做**质量放行**。

    * `qualified` → 待检转为合格，可再次销售；
    * `rejected`  → 转为不合格，留在仓内但不可销售（报废/维修走后续流程）。

    未接入真实检测设备接口，本动作是**人工判定**，结论与判定人一并留痕。
    """
    require_codes(user, "sales.return.inspect", "wms.quality.release")
    if result not in (ReturnDisposition.QUALIFIED, ReturnDisposition.REJECTED):
        raise ValidationFailed("检验结论只能是合格或不合格。", code="INVALID_INSPECTION_RESULT")
    if not str(remark or "").strip():
        raise ValidationFailed("检验判定必须填写说明。", code="REASON_REQUIRED")
    locked = (
        SalesReturn.objects.select_for_update()
        .select_related("warehouse", "company", "sales_order")
        .filter(pk=return_doc.pk)
        .first()
    )
    if locked is None:
        raise ObjectNotFound("退货单不存在。", details={"return_id": return_doc.pk})
    if locked.status == ReturnStatus.INSPECTED:
        raise StateConflict("该退货单已完成检验判定。", code="ALREADY_INSPECTED")
    if locked.status != ReturnStatus.POSTED:
        raise StateConflict(
            "只有「已收货待检」的退货单可以检验判定；请先完成收货过账。", code="STATE_CONFLICT"
        )

    target_status = (
        QualityStatus.QUALIFIED if result == ReturnDisposition.QUALIFIED else QualityStatus.REJECTED
    )
    lines = list(locked.lines.select_related("material", "location").order_by("line_no"))
    last_document_id = None
    for line in lines:
        document = stock.release_quality(
            user=user,
            company=locked.company_id,
            warehouse=locked.warehouse,
            material=line.material,
            quantity=line.quantity,
            location=line.location,
            batch_no=line.batch_no,
            roll_no=line.roll_no,
            from_status=QualityStatus.QUARANTINE,
            to_status=target_status,
            biz_type="sales.return",
            biz_id=locked.pk,
            biz_no=locked.return_no,
            reason=f"退货检验 {locked.return_no} 第 {line.line_no} 行：{remark[:200]}",
            idempotency_key=(idempotency_key or f"sales-return-inspect-{locked.pk}")
            if len(lines) == 1
            else f"sales-return-inspect-{locked.pk}-{line.line_no}",
        )
        last_document_id = document.pk

    locked.status = ReturnStatus.INSPECTED
    locked.inspection_result = result
    locked.inspected_at = timezone.now()
    locked.inspected_by = user
    locked.inspection_remark = remark
    locked.quality_document_id = last_document_id
    locked.save(
        update_fields=[
            "status",
            "inspection_result",
            "inspected_at",
            "inspected_by",
            "inspection_remark",
            "quality_document_id",
            "updated_at",
        ]
    )
    record_audit(
        action=AuditAction.POST,
        instance=locked,
        changes={
            "status": {"before": ReturnStatus.POSTED, "after": ReturnStatus.INSPECTED},
            "inspection_result": {"before": ReturnDisposition.NONE, "after": result},
        },
        reason=remark,
        object_repr=locked.return_no,
        approval_basis=f"wms.InventoryDocument#{last_document_id}",
        company=locked.company,
        actor=user,
    )
    publish_event(
        event_type=EVENT_RETURN_INSPECTED,
        aggregate_type="sales.SalesReturn",
        aggregate_id=locked.pk,
        payload={
            "return_id": locked.pk,
            "return_no": locked.return_no,
            "order_no": locked.sales_order.order_no,
            "result": result,
        },
        dedup_key=f"sales.return:{locked.pk}:inspected",
    )
    return locked


@transaction.atomic
def cancel_return(return_doc: SalesReturn, *, user: Any, reason: str) -> SalesReturn:
    require_codes(user, "sales.return.update")
    if not str(reason or "").strip():
        raise ValidationFailed("取消必须填写原因。", code="REASON_REQUIRED")
    locked = SalesReturn.objects.select_for_update().filter(pk=return_doc.pk).first()
    if locked is None:
        raise ObjectNotFound("退货单不存在。", details={"return_id": return_doc.pk})
    if locked.status != ReturnStatus.DRAFT:
        raise StateConflict(
            "已收货的退货单不能取消；请通过检验判定与库存处置处理。", code="STATE_CONFLICT"
        )
    locked.status = ReturnStatus.CANCELLED
    locked.save(update_fields=["status", "updated_at"])
    record_audit(
        action=AuditAction.UPDATE,
        instance=locked,
        changes={"status": {"before": ReturnStatus.DRAFT, "after": ReturnStatus.CANCELLED}},
        reason=reason,
        object_repr=locked.return_no,
        company=locked.company,
        actor=user,
    )
    return locked


__all__ = [
    "BIZ_TYPE_ORDER",
    "cancel_order",
    "cancel_return",
    "cancel_shipment",
    "close_order",
    "compute_line_amount",
    "create_order",
    "create_return",
    "create_shipment",
    "inspect_return",
    "money",
    "on_order_approval_outcome",
    "post_return",
    "post_shipment",
    "recalculate_order_amounts",
    "release_order_stock",
    "reserve_order_stock",
    "submit_order",
    "update_order",
    "update_return",
    "update_shipment",
]
