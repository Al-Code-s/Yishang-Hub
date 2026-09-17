"""采购业务服务：采购申请 → 审批 → 采购订单 → 到货 → 待检收货 → 检验放行。

关键约定（任务书 4.3、5.3、10.5）：

* 所有金额由**后端**计算与校验，前端提交的 `amount` / `total_amount` 一律忽略；
  舍入统一为 `ROUND_HALF_UP`，保留 4 位小数，舍入发生在**行金额与其汇总**两处。
* 库存变动**只经** `apps.wms.services.stock`，本模块不写任何库存表。
* 收货过账（记库存）与检验放行（改质量状态）是**两个动作**，分别有独立状态与审计。
* 审批通过由 `apps.workflow.registry` 显式回写单据状态，与审批同事务提交。
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
from apps.core.exceptions import (
    ObjectNotFound,
    StateConflict,
    ValidationFailed,
)
from apps.core.models import AuditAction
from apps.core.permissions import require_codes
from apps.core.services import build_changes, generate_code, publish_event, record_audit
from apps.procurement.models import (
    GoodsReceipt,
    GoodsReceiptLine,
    InspectionResult,
    OrderStatus,
    PurchaseOrder,
    PurchaseOrderLine,
    PurchaseRequisition,
    PurchaseRequisitionLine,
    ReceiptStatus,
    RequisitionStatus,
)
from apps.srm.models import AdmissionStatus, Supplier
from apps.wms.models import DocumentType, QualityStatus
from apps.wms.services import stock

logger = logging.getLogger("yishang.procurement")

BIZ_TYPE_REQUISITION = "procurement.requisition"
BIZ_TYPE_ORDER = "procurement.order"

EVENT_ORDER_SUBMITTED = "procurement.order.submitted"
EVENT_RECEIPT_POSTED = "procurement.receipt.posted"
EVENT_RECEIPT_INSPECTED = "procurement.receipt.inspected"

ZERO = Decimal("0")
HUNDRED = Decimal("100")
MONEY_QUANT = Decimal(1).scaleb(-MONEY_DECIMAL_PLACES)

# 不允许直接下单的准入状态（任务书 10.4：停用供应商不能新建正常采购订单）
BLOCKED_ADMISSION = (
    AdmissionStatus.PENDING,
    AdmissionStatus.REJECTED,
    AdmissionStatus.SUSPENDED,
    AdmissionStatus.TERMINATED,
)


def money(value: Any) -> Decimal:
    """金额舍入：ROUND_HALF_UP，保留 MONEY_DECIMAL_PLACES 位。"""
    return Decimal(value or 0).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def compute_line_amount(quantity: Any, price: Any) -> Decimal:
    """行未税金额 = 数量 × 未税单价（先乘后舍入）。"""
    return money(Decimal(quantity or 0) * Decimal(price or 0))


# --------------------------------------------------------------------------
# 采购申请
# --------------------------------------------------------------------------


def _require(queryset, pk: Any, name: str):
    obj = queryset.filter(pk=pk).first()
    if obj is None:
        raise ObjectNotFound(f"{name}不存在：{pk}", code="NOT_FOUND")
    return obj


def _requisition_line_kwargs(row: dict) -> dict:
    material_id = row.get("material_id") or row.get("material")
    if material_id is None:
        raise ValidationFailed("申请明细缺少物料。", code="LINE_MATERIAL_REQUIRED")
    quantity = Decimal(row.get("quantity") or 0)
    if quantity <= ZERO:
        raise ValidationFailed("申请数量必须大于 0。", code="INVALID_LINE_QUANTITY")
    return {
        "material_id": _pk(material_id),
        "quantity": quantity,
        "uom_id": _pk(row.get("uom")),
        "needed_date": row.get("needed_date"),
        "suggested_supplier_id": _pk(row.get("suggested_supplier")),
        "remark": str(row.get("remark") or "")[:255],
    }


def _replace_requisition_lines(requisition: PurchaseRequisition, lines: Sequence[dict]) -> None:
    if not lines:
        raise ValidationFailed("采购申请必须至少包含一行明细。", code="EMPTY_DOCUMENT")
    requisition.lines.all().delete()
    for index, row in enumerate(lines, start=1):
        PurchaseRequisitionLine.objects.create(
            requisition=requisition, line_no=index, **_requisition_line_kwargs(row)
        )


@transaction.atomic
def create_requisition(
    *,
    user: Any,
    company: Any,
    lines: Sequence[dict],
    request_type: str = "normal",
    needed_date: Any = None,
    department: Any = None,
    factory: Any = None,
    purpose: str = "",
    remark: str = "",
    requisition_no: str = "",
) -> PurchaseRequisition:
    require_codes(user, "procurement.requisition.create")
    requisition = PurchaseRequisition(
        company_id=getattr(company, "pk", company),
        requisition_no=str(requisition_no or "").strip() or generate_code("PR"),
        request_type=request_type,
        applicant=user,
        department_id=getattr(department, "pk", department),
        factory_id=getattr(factory, "pk", factory),
        needed_date=needed_date,
        purpose=purpose[:255],
        remark=remark,
    )
    requisition.save()
    _replace_requisition_lines(requisition, lines)
    record_audit(
        action=AuditAction.CREATE,
        instance=requisition,
        changes={
            "requisition_no": {"before": "", "after": requisition.requisition_no},
            "request_type": {"before": "", "after": request_type},
            "line_count": {"before": 0, "after": len(lines)},
        },
        object_repr=requisition.requisition_no,
        company=requisition.company,
        actor=user,
    )
    return requisition


@transaction.atomic
def update_requisition(
    requisition: PurchaseRequisition,
    *,
    user: Any,
    lines: Sequence[dict] | None = None,
    **header: Any,
) -> PurchaseRequisition:
    require_codes(user, "procurement.requisition.update")
    if requisition.status != RequisitionStatus.DRAFT:
        raise StateConflict("只有草稿状态的采购申请可以修改。", code="STATE_CONFLICT")
    before = {
        "request_type": requisition.request_type,
        "purpose": requisition.purpose,
        "needed_date": requisition.needed_date,
        "line_count": requisition.lines.count(),
    }
    for field in ("request_type", "needed_date", "purpose", "remark", "department_id", "factory_id"):
        if field in header and header[field] is not None:
            setattr(requisition, field, header[field])
    requisition.save()
    if lines is not None:
        _replace_requisition_lines(requisition, lines)
    after = {
        "request_type": requisition.request_type,
        "purpose": requisition.purpose,
        "needed_date": requisition.needed_date,
        "line_count": requisition.lines.count(),
    }
    changes = build_changes(before, after)
    if changes:
        record_audit(
            action=AuditAction.UPDATE,
            instance=requisition,
            changes=changes,
            object_repr=requisition.requisition_no,
            company=requisition.company,
            actor=user,
        )
    return requisition


def _submit_for_approval(
    document, *, user: Any, biz_type: str, title: str, summary: str, amount, comment: str
):
    """创建并提交审批实例。复用 workflow，不新建审批体系。"""
    from apps.workflow import services as workflow_services

    instance = workflow_services.create_instance(
        user,
        title=title,
        biz_type=biz_type,
        biz_id=str(document.pk),
        biz_no=getattr(document, "requisition_no", "") or getattr(document, "order_no", ""),
        summary=summary,
        amount=amount,
        company=document.company,
        department=getattr(document, "department", None),
    )
    workflow_services.submit_instance(user, instance, comment=comment)
    return instance


@transaction.atomic
def submit_requisition(
    requisition: PurchaseRequisition, *, user: Any, comment: str = ""
) -> PurchaseRequisition:
    require_codes(user, "procurement.requisition.submit")
    requisition = PurchaseRequisition.objects.select_for_update().get(pk=requisition.pk)
    if requisition.status != RequisitionStatus.DRAFT:
        raise StateConflict("只有草稿状态的采购申请可以提交。", code="STATE_CONFLICT")
    if not requisition.lines.exists():
        raise ValidationFailed("采购申请没有明细，不能提交。", code="EMPTY_DOCUMENT")
    instance = _submit_for_approval(
        requisition,
        user=user,
        biz_type=BIZ_TYPE_REQUISITION,
        title=f"采购申请 {requisition.requisition_no}",
        summary=requisition.purpose,
        amount=None,
        comment=comment,
    )
    requisition.status = RequisitionStatus.SUBMITTED
    requisition.approval_instance_id = instance.pk
    requisition.save(update_fields=["status", "approval_instance_id", "updated_at"])
    record_audit(
        action=AuditAction.SUBMIT,
        instance=requisition,
        changes={"status": {"before": RequisitionStatus.DRAFT, "after": RequisitionStatus.SUBMITTED}},
        reason=comment,
        object_repr=requisition.requisition_no,
        approval_basis=f"workflow.ApprovalInstance#{instance.pk}",
        company=requisition.company,
        actor=user,
    )
    publish_event(
        event_type="procurement.requisition.submitted",
        aggregate_type="procurement.PurchaseRequisition",
        aggregate_id=requisition.pk,
        payload={"requisition_id": requisition.pk, "requisition_no": requisition.requisition_no},
        dedup_key=f"requisition:{requisition.pk}:submitted",
    )
    return requisition


def on_requisition_approval_outcome(instance, outcome: str) -> None:
    """审批终结回写采购申请状态（由 workflow.registry 在同一事务内调用）。"""
    from apps.workflow.registry import OUTCOME_APPROVED, OUTCOME_REJECTED, OUTCOME_WITHDRAWN

    requisition = PurchaseRequisition.objects.filter(pk=instance.biz_id).first()
    if requisition is None or requisition.status != RequisitionStatus.SUBMITTED:
        return
    if outcome == OUTCOME_APPROVED:
        requisition.status = RequisitionStatus.APPROVED
        requisition.approved_at = timezone.now()
    elif outcome == OUTCOME_REJECTED:
        requisition.status = RequisitionStatus.REJECTED
    elif outcome == OUTCOME_WITHDRAWN:
        requisition.status = RequisitionStatus.DRAFT
    else:  # pragma: no cover - 未知结果不应出现
        return
    requisition.save(update_fields=["status", "approved_at", "updated_at"])
    record_audit(
        action=AuditAction.APPROVE
        if outcome == OUTCOME_APPROVED
        else (AuditAction.REJECT if outcome == OUTCOME_REJECTED else AuditAction.WITHDRAW),
        instance=requisition,
        changes={"status": {"before": RequisitionStatus.SUBMITTED, "after": requisition.status}},
        object_repr=requisition.requisition_no,
        approval_basis=f"workflow.ApprovalInstance#{instance.pk}",
        company=requisition.company,
        actor=instance.applicant,
    )


@transaction.atomic
def cancel_requisition(requisition: PurchaseRequisition, *, user: Any, reason: str) -> PurchaseRequisition:
    require_codes(user, "procurement.requisition.update")
    if not reason.strip():
        raise ValidationFailed("取消必须填写原因。", code="REASON_REQUIRED")
    requisition = PurchaseRequisition.objects.select_for_update().get(pk=requisition.pk)
    if requisition.status in (RequisitionStatus.CANCELLED, RequisitionStatus.CLOSED):
        raise StateConflict("该采购申请已取消或关闭。", code="STATE_CONFLICT")
    if requisition.purchase_orders.exclude(status=OrderStatus.CANCELLED).exists():
        raise StateConflict("该申请已生成采购订单，不能取消；请先处理相关订单。", code="HAS_DOWNSTREAM")
    previous = requisition.status
    requisition.status = RequisitionStatus.CANCELLED
    requisition.save(update_fields=["status", "updated_at"])
    record_audit(
        action=AuditAction.UPDATE,
        instance=requisition,
        changes={"status": {"before": previous, "after": RequisitionStatus.CANCELLED}},
        reason=reason,
        object_repr=requisition.requisition_no,
        company=requisition.company,
        actor=user,
    )
    return requisition


# --------------------------------------------------------------------------
# 采购订单
# --------------------------------------------------------------------------


def _assert_supplier_usable(supplier: Supplier, *, exception_reason: str, user: Any) -> bool:
    """校验供应商是否可用于正常采购。

    停用或未准入的供应商不能新建正常采购订单；确需例外时，必须填写原因
    并持有 `procurement.order.override_supplier` 权限，例外会被审计留痕。
    """
    problems: list[str] = []
    if not supplier.is_active:
        problems.append("供应商已停用")
    if supplier.admission_status in BLOCKED_ADMISSION:
        problems.append(f"供应商准入状态为「{supplier.get_admission_status_display()}」")
    if not problems:
        return False
    if not str(exception_reason or "").strip():
        raise ValidationFailed(
            "；".join(problems) + "，不能新建正常采购订单。如属例外，必须填写例外原因。",
            code="SUPPLIER_NOT_USABLE",
        )
    require_codes(user, "procurement.order.override_supplier")
    return True


def recalculate_order_amounts(order: PurchaseOrder) -> PurchaseOrder:
    """按行重算金额。金额一律由后端计算，前端传入值被忽略。"""
    total = ZERO
    tax = ZERO
    for line in order.lines.all():
        amount = compute_line_amount(line.quantity, line.price)
        if line.amount != amount:
            line.amount = amount
            line.save(update_fields=["amount", "updated_at"])
        total += amount
        tax += money(amount * Decimal(order.tax_rate or 0) / HUNDRED)
    order.total_amount = money(total)
    order.tax_amount = money(tax)
    order.amount_with_tax = money(total + tax)
    order.save(update_fields=["total_amount", "tax_amount", "amount_with_tax", "updated_at"])
    return order


def _order_line_kwargs(row: dict) -> dict:
    """规范化订单行。

    同时接受对象键（``material``/``uom``/``warehouse``/``source_line``）与
    主键键（``material_id`` 等）：视图层传入主键，转单场景直接构造主键字典，
    两条路径必须落到同一套校验上。
    """
    material = row.get("material")
    if material is None:
        material = row.get("material_id")
    if material is None:
        raise ValidationFailed("订单明细缺少物料。", code="LINE_MATERIAL_REQUIRED")
    quantity = Decimal(row.get("quantity") or 0)
    if quantity <= ZERO:
        raise ValidationFailed("订单数量必须大于 0。", code="INVALID_LINE_QUANTITY")
    price = Decimal(row.get("price") or 0)
    if price < ZERO:
        raise ValidationFailed("未税单价不能为负。", code="INVALID_LINE_PRICE")
    expected_date = row.get("expected_date")
    return {
        "material_id": getattr(material, "pk", material),
        "quantity": quantity,
        "price": price,
        "amount": compute_line_amount(quantity, price),
        "uom_id": _pk(row.get("uom") or row.get("uom_id")),
        "expected_date": expected_date,
        "warehouse_id": _pk(row.get("warehouse") or row.get("warehouse_id")),
        "source_line_id": _pk(row.get("source_line") or row.get("source_line_id")),
        "remark": str(row.get("remark") or "")[:255],
    }


def _pk(value: Any) -> int | None:
    if value is None or value == "":
        return None
    return getattr(value, "pk", value)


def _replace_order_lines(order: PurchaseOrder, lines: Sequence[dict]) -> None:
    if not lines:
        raise ValidationFailed("采购订单必须至少包含一行明细。", code="EMPTY_DOCUMENT")
    order.lines.all().delete()
    for index, row in enumerate(lines, start=1):
        PurchaseOrderLine.objects.create(order=order, line_no=index, **_order_line_kwargs(row))


@transaction.atomic
def create_order(
    *,
    user: Any,
    company: Any,
    supplier: Supplier,
    lines: Sequence[dict],
    order_date: Any = None,
    expected_date: Any = None,
    warehouse: Any = None,
    source_requisition: Any = None,
    buyer: Any = None,
    tax_rate: Any = 0,
    payment_terms: str = "",
    currency: str = "CNY",
    supplier_exception_reason: str = "",
    remark: str = "",
    order_no: str = "",
) -> PurchaseOrder:
    require_codes(user, "procurement.order.create")
    exception = _assert_supplier_usable(supplier, exception_reason=supplier_exception_reason, user=user)
    order = PurchaseOrder(
        company_id=getattr(company, "pk", company) or supplier.company_id,
        order_no=str(order_no or "").strip() or generate_code("PO"),
        supplier=supplier,
        status=OrderStatus.DRAFT,
        source_requisition_id=_pk(source_requisition),
        buyer_id=_pk(buyer),
        order_date=order_date,
        expected_date=expected_date,
        warehouse_id=_pk(warehouse),
        currency=currency[:8],
        tax_rate=Decimal(tax_rate or 0),
        payment_terms=payment_terms[:64],
        supplier_exception=exception,
        supplier_exception_reason=supplier_exception_reason,
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
            "supplier_id": {"before": "", "after": order.supplier_id},
            "amount_with_tax": {"before": "", "after": str(order.amount_with_tax)},
            "supplier_exception": {"before": False, "after": exception},
        },
        reason=supplier_exception_reason,
        object_repr=order.order_no,
        company=order.company,
        actor=user,
    )
    return order


@transaction.atomic
def update_order(
    order: PurchaseOrder, *, user: Any, lines: Sequence[dict] | None = None, **header: Any
) -> PurchaseOrder:
    require_codes(user, "procurement.order.update")
    order = PurchaseOrder.objects.select_for_update().get(pk=order.pk)
    if order.status != OrderStatus.DRAFT:
        raise StateConflict("只有草稿状态的采购订单可以修改。", code="STATE_CONFLICT")
    if "supplier" in header and header["supplier"] is not None:
        supplier = header["supplier"]
        order.supplier = supplier
        order.supplier_exception = _assert_supplier_usable(
            supplier,
            exception_reason=header.get("supplier_exception_reason", order.supplier_exception_reason),
            user=user,
        )
    for field in (
        "order_date",
        "expected_date",
        "warehouse_id",
        "buyer_id",
        "currency",
        "tax_rate",
        "payment_terms",
        "remark",
        "source_requisition_id",
        "supplier_exception_reason",
    ):
        if field in header and header[field] is not None:
            setattr(order, field, header[field])
    order.save()
    if lines is not None:
        _replace_order_lines(order, lines)
    recalculate_order_amounts(order)
    record_audit(
        action=AuditAction.UPDATE,
        instance=order,
        changes={
            "line_count": {"before": "", "after": order.lines.count()},
            "amount_with_tax": {"before": "", "after": str(order.amount_with_tax)},
        },
        object_repr=order.order_no,
        company=order.company,
        actor=user,
    )
    return order


@transaction.atomic
def submit_order(order: PurchaseOrder, *, user: Any, comment: str = "") -> PurchaseOrder:
    require_codes(user, "procurement.order.submit")
    order = PurchaseOrder.objects.select_for_update().get(pk=order.pk)
    if order.status != OrderStatus.DRAFT:
        raise StateConflict("只有草稿状态的采购订单可以提交。", code="STATE_CONFLICT")
    if not order.lines.exists():
        raise ValidationFailed("采购订单没有明细，不能提交。", code="EMPTY_DOCUMENT")
    recalculate_order_amounts(order)
    instance = _submit_for_approval(
        order,
        user=user,
        biz_type=BIZ_TYPE_ORDER,
        title=f"采购订单 {order.order_no}",
        summary=f"{order.supplier.name} 价税合计 {order.amount_with_tax}",
        amount=order.amount_with_tax,
        comment=comment,
    )
    order.status = OrderStatus.SUBMITTED
    order.approval_instance_id = instance.pk
    order.save(update_fields=["status", "approval_instance_id", "updated_at"])
    record_audit(
        action=AuditAction.SUBMIT,
        instance=order,
        changes={"status": {"before": OrderStatus.DRAFT, "after": OrderStatus.SUBMITTED}},
        reason=comment,
        object_repr=order.order_no,
        approval_basis=f"workflow.ApprovalInstance#{instance.pk}",
        company=order.company,
        actor=user,
    )
    publish_event(
        event_type=EVENT_ORDER_SUBMITTED,
        aggregate_type="procurement.PurchaseOrder",
        aggregate_id=order.pk,
        payload={
            "order_id": order.pk,
            "order_no": order.order_no,
            "supplier_id": order.supplier_id,
            "amount_with_tax": str(order.amount_with_tax),
        },
        dedup_key=f"order:{order.pk}:submitted",
    )
    return order


def on_order_approval_outcome(instance, outcome: str) -> None:
    """审批终结回写采购订单状态（与审批同事务）。"""
    from apps.workflow.registry import OUTCOME_APPROVED, OUTCOME_REJECTED, OUTCOME_WITHDRAWN

    order = PurchaseOrder.objects.filter(pk=instance.biz_id).first()
    if order is None or order.status != OrderStatus.SUBMITTED:
        return
    if outcome == OUTCOME_APPROVED:
        order.status = OrderStatus.APPROVED
        order.approved_at = timezone.now()
    elif outcome == OUTCOME_REJECTED:
        order.status = OrderStatus.REJECTED
    elif outcome == OUTCOME_WITHDRAWN:
        order.status = OrderStatus.DRAFT
    else:  # pragma: no cover
        return
    order.save(update_fields=["status", "approved_at", "updated_at"])
    record_audit(
        action=AuditAction.APPROVE
        if outcome == OUTCOME_APPROVED
        else (AuditAction.REJECT if outcome == OUTCOME_REJECTED else AuditAction.WITHDRAW),
        instance=order,
        changes={"status": {"before": OrderStatus.SUBMITTED, "after": order.status}},
        object_repr=order.order_no,
        approval_basis=f"workflow.ApprovalInstance#{instance.pk}",
        company=order.company,
        actor=instance.applicant,
    )


@transaction.atomic
def cancel_order(order: PurchaseOrder, *, user: Any, reason: str) -> PurchaseOrder:
    require_codes(user, "procurement.order.update")
    if not reason.strip():
        raise ValidationFailed("取消必须填写原因。", code="REASON_REQUIRED")
    order = PurchaseOrder.objects.select_for_update().get(pk=order.pk)
    if order.status in (OrderStatus.CANCELLED, OrderStatus.CLOSED):
        raise StateConflict("该采购订单已取消或关闭。", code="STATE_CONFLICT")
    if order.receipts.exclude(status=ReceiptStatus.CANCELLED).exists():
        raise StateConflict("该订单已存在收货记录，不能取消；请先处理相关收货单。", code="HAS_DOWNSTREAM")
    previous = order.status
    order.status = OrderStatus.CANCELLED
    order.save(update_fields=["status", "updated_at"])
    record_audit(
        action=AuditAction.UPDATE,
        instance=order,
        changes={"status": {"before": previous, "after": OrderStatus.CANCELLED}},
        reason=reason,
        object_repr=order.order_no,
        company=order.company,
        actor=user,
    )
    return order


@transaction.atomic
def close_order(order: PurchaseOrder, *, user: Any, reason: str = "") -> PurchaseOrder:
    """关闭订单（不再收货）。已到货部分不回退。"""
    require_codes(user, "procurement.order.close")
    order = PurchaseOrder.objects.select_for_update().get(pk=order.pk)
    if order.status not in (OrderStatus.APPROVED, OrderStatus.PARTIALLY_RECEIVED, OrderStatus.RECEIVED):
        raise StateConflict("只有已批准或已到货的订单可以关闭。", code="STATE_CONFLICT")
    previous = order.status
    order.status = OrderStatus.CLOSED
    order.closed_at = timezone.now()
    order.save(update_fields=["status", "closed_at", "updated_at"])
    record_audit(
        action=AuditAction.UPDATE,
        instance=order,
        changes={"status": {"before": previous, "after": OrderStatus.CLOSED}},
        reason=reason,
        object_repr=order.order_no,
        company=order.company,
        actor=user,
    )
    return order


# --------------------------------------------------------------------------
# 收货与检验
# --------------------------------------------------------------------------


def _receipt_line_kwargs(receipt: GoodsReceipt, row: dict) -> dict:
    order_line = row.get("order_line")
    if order_line is None:
        raise ValidationFailed("收货明细必须指定订单行。", code="LINE_ORDER_LINE_REQUIRED")
    if order_line.order_id != receipt.purchase_order_id:
        raise ValidationFailed("收货明细的订单行不属于该采购订单。", code="ORDER_LINE_MISMATCH")
    quantity = Decimal(row.get("quantity") or 0)
    if quantity <= ZERO:
        raise ValidationFailed("收货数量必须大于 0。", code="INVALID_LINE_QUANTITY")
    location = row.get("location")
    if location is not None:
        warehouse_id = getattr(location, "zone", None)
        warehouse_id = getattr(warehouse_id, "warehouse_id", None) if warehouse_id else None
        if warehouse_id is not None and warehouse_id != receipt.warehouse_id:
            raise ValidationFailed("收货储位不属于收货仓库。", code="LOCATION_WAREHOUSE_MISMATCH")
    return {
        "order_line": order_line,
        "material_id": order_line.material_id,
        "quantity": quantity,
        "location_id": _pk(location),
        "batch_no": str(row.get("batch_no") or "").strip()[:64],
        "roll_no": str(row.get("roll_no") or "").strip()[:64],
        "remark": str(row.get("remark") or "")[:255],
    }


def _assert_receipt_quantities(receipt: GoodsReceipt, rows: list[dict], *, exclude_self: bool = True) -> None:
    """收货数量不得超过订单未收数量。

    订单行的 `received_quantity` 只统计**已过账**的收货；为避免多张草稿收货单
    同时占用同一批未收数量，这里把**其他未取消收货单**的数量也计入占用。
    """
    others = GoodsReceiptLine.objects.filter(order_line__order_id=receipt.purchase_order_id).exclude(
        receipt__status=ReceiptStatus.CANCELLED
    )
    if exclude_self and receipt.pk:
        others = others.exclude(receipt_id=receipt.pk)
    committed: dict[int, Decimal] = {}
    for row in others.values("order_line_id", "quantity"):
        committed[row["order_line_id"]] = committed.get(row["order_line_id"], ZERO) + row["quantity"]

    claimed: dict[int, Decimal] = {}
    for row in rows:
        order_line = row["order_line"]
        claimed[order_line.pk] = claimed.get(order_line.pk, ZERO) + Decimal(row["quantity"])

    for line_pk, want in claimed.items():
        order_line = next(r["order_line"] for r in rows if r["order_line"].pk == line_pk)
        available = order_line.quantity - order_line.received_quantity - committed.get(line_pk, ZERO)
        if want > available:
            raise ValidationFailed(
                f"物料 {order_line.material_id} 收货数量超出订单未收数量。",
                code="OVER_RECEIPT",
                details={
                    "requested": str(want),
                    "available": str(max(available, ZERO)),
                    "hint": "不允许超收；请修改收货数量或先处理其他未完成的收货单。",
                },
            )


def _replace_receipt_lines(receipt: GoodsReceipt, lines: Sequence[dict]) -> None:
    if not lines:
        raise ValidationFailed("收货单必须至少包含一行明细。", code="EMPTY_DOCUMENT")
    prepared = [(_receipt_line_kwargs(receipt, dict(row))) for row in lines]
    _assert_receipt_quantities(receipt, prepared, exclude_self=False)
    receipt.lines.all().delete()
    for index, kwargs in enumerate(prepared, start=1):
        GoodsReceiptLine.objects.create(receipt=receipt, line_no=index, **kwargs)


@transaction.atomic
def create_receipt(
    *,
    user: Any,
    order: PurchaseOrder,
    warehouse: Any,
    lines: Sequence[dict],
    supplier_delivery_no: str = "",
    remark: str = "",
    receipt_no: str = "",
) -> GoodsReceipt:
    require_codes(user, "procurement.receipt.create")
    order = PurchaseOrder.objects.select_for_update().get(pk=order.pk)
    if order.status not in OrderStatus.open_for_receipt():
        raise StateConflict(
            f"采购订单当前状态为「{order.get_status_display()}」，不能收货。",
            code="ORDER_NOT_RECEIVABLE",
        )
    receipt = GoodsReceipt(
        company_id=order.company_id,
        receipt_no=str(receipt_no or "").strip() or generate_code("RC"),
        purchase_order=order,
        supplier_id=order.supplier_id,
        status=ReceiptStatus.DRAFT,
        warehouse_id=_pk(warehouse) or order.warehouse_id,
        supplier_delivery_no=supplier_delivery_no[:64],
        remark=remark,
    )
    if receipt.warehouse_id is None:
        raise ValidationFailed("收货必须指定收货仓库。", code="WAREHOUSE_REQUIRED")
    receipt.save()
    _replace_receipt_lines(receipt, lines)
    record_audit(
        action=AuditAction.CREATE,
        instance=receipt,
        changes={
            "receipt_no": {"before": "", "after": receipt.receipt_no},
            "purchase_order_id": {"before": "", "after": order.pk},
            "line_count": {"before": 0, "after": receipt.lines.count()},
        },
        object_repr=receipt.receipt_no,
        company=receipt.company,
        actor=user,
    )
    return receipt


@transaction.atomic
def update_receipt(
    receipt: GoodsReceipt, *, user: Any, lines: Sequence[dict] | None = None, **header: Any
) -> GoodsReceipt:
    require_codes(user, "procurement.receipt.update")
    receipt = GoodsReceipt.objects.select_for_update().get(pk=receipt.pk)
    if receipt.status != ReceiptStatus.DRAFT:
        raise StateConflict("只有草稿状态的收货单可以修改。", code="STATE_CONFLICT")
    for field in ("warehouse_id", "supplier_delivery_no", "remark"):
        if field in header and header[field] is not None:
            setattr(receipt, field, header[field])
    receipt.save()
    if lines is not None:
        _replace_receipt_lines(receipt, lines)
    record_audit(
        action=AuditAction.UPDATE,
        instance=receipt,
        changes={"line_count": {"before": "", "after": receipt.lines.count()}},
        object_repr=receipt.receipt_no,
        company=receipt.company,
        actor=user,
    )
    return receipt


def _refresh_order_receipt_status(order: PurchaseOrder) -> None:
    """按已过账收货累计量更新订单状态。"""
    lines = list(order.lines.all())
    if not lines:
        return
    if all(line.received_quantity >= line.quantity for line in lines):
        target = OrderStatus.RECEIVED
    elif any(line.received_quantity > ZERO for line in lines):
        target = OrderStatus.PARTIALLY_RECEIVED
    else:
        return
    if order.status != target:
        order.status = target
        order.save(update_fields=["status", "updated_at"])


@transaction.atomic
def post_receipt(receipt: GoodsReceipt, *, user: Any, idempotency_key: str | None = None) -> GoodsReceipt:
    """收货过账：把**实物到货**记账为**待检库存**。

    这是「实物到货」与「库存记账」的衔接点，但与「质量放行」是不同动作：
    过账后库存为 `quarantine`，只有 `inspect_receipt` 放行后才能被领用或销售。
    """
    require_codes(user, "procurement.receipt.post")
    receipt = (
        GoodsReceipt.objects.select_for_update()
        .select_related("purchase_order", "warehouse", "company")
        .get(pk=receipt.pk)
    )
    if receipt.status == ReceiptStatus.POSTED:
        # 幂等：已过账直接返回，不重复记账
        return receipt
    if receipt.status != ReceiptStatus.DRAFT:
        raise StateConflict("只有草稿状态的收货单可以过账。", code="STATE_CONFLICT")

    order = PurchaseOrder.objects.select_for_update().get(pk=receipt.purchase_order_id)
    if order.status not in OrderStatus.open_for_receipt():
        raise StateConflict(
            f"采购订单当前状态为「{order.get_status_display()}」，不能收货。",
            code="ORDER_NOT_RECEIVABLE",
        )
    lines = list(receipt.lines.select_related("order_line", "material", "location").all())
    if not lines:
        raise ValidationFailed("收货单没有明细，不能过账。", code="EMPTY_DOCUMENT")

    for line in lines:
        order_line = PurchaseOrderLine.objects.select_for_update().get(pk=line.order_line_id)
        remaining = order_line.quantity - order_line.received_quantity
        if line.quantity > remaining:
            raise ValidationFailed(
                f"物料 {order_line.material_id} 收货数量超出订单未收数量。",
                code="OVER_RECEIPT",
                details={"requested": str(line.quantity), "available": str(remaining)},
            )

    document = stock.create_document(
        document_type=DocumentType.RECEIPT,
        company=receipt.company_id,
        warehouse=receipt.warehouse,
        user=user,
        biz_type="procurement.receipt",
        biz_id=receipt.pk,
        biz_no=receipt.receipt_no,
        remark=f"采购收货 {receipt.receipt_no}",
        lines=[
            {
                "material_id": line.material_id,
                "location_id": line.location_id,
                "batch_no": line.batch_no,
                "roll_no": line.roll_no,
                "quality_status": QualityStatus.QUARANTINE,
                "direction": "in",
                "quantity": line.quantity,
                "remark": f"收货单 {receipt.receipt_no} 第 {line.line_no} 行",
            }
            for line in lines
        ],
    )
    stock.post_document(
        document,
        user=user,
        idempotency_key=idempotency_key or f"procurement-receipt-{receipt.pk}",
        reason=f"采购收货过账 {receipt.receipt_no}",
    )

    for line in lines:
        PurchaseOrderLine.objects.filter(pk=line.order_line_id).update(
            received_quantity=F("received_quantity") + line.quantity
        )
    _refresh_order_receipt_status(order)

    receipt.status = ReceiptStatus.POSTED
    receipt.received_at = timezone.now()
    receipt.received_by = user
    receipt.receipt_document_id = document.pk
    receipt.save(update_fields=["status", "received_at", "received_by", "receipt_document_id", "updated_at"])
    record_audit(
        action=AuditAction.POST,
        instance=receipt,
        changes={
            "status": {"before": ReceiptStatus.DRAFT, "after": ReceiptStatus.POSTED},
            "inventory_document": {"before": "", "after": document.document_no},
        },
        object_repr=receipt.receipt_no,
        company=receipt.company,
        actor=user,
    )
    publish_event(
        event_type=EVENT_RECEIPT_POSTED,
        aggregate_type="procurement.GoodsReceipt",
        aggregate_id=receipt.pk,
        payload={
            "receipt_id": receipt.pk,
            "receipt_no": receipt.receipt_no,
            "order_no": order.order_no,
            "inventory_document_no": document.document_no,
        },
        dedup_key=f"receipt:{receipt.pk}:posted",
    )
    return receipt


@transaction.atomic
def inspect_receipt(
    receipt: GoodsReceipt,
    *,
    user: Any,
    result: str,
    remark: str = "",
    idempotency_key: str | None = None,
) -> GoodsReceipt:
    """来料检验判定：调用统一库存服务做**质量放行**。

    * `result=qualified` → 待检库存转为合格，此后可被领用或销售；
    * `result=rejected`  → 待检库存转为不合格，仍留在仓内但不可动用（退货走库存出库）。

    未配置真实检测设备接口，本动作是**人工判定**，结论与判定人一并留痕。
    """
    require_codes(user, "procurement.receipt.inspect")
    if result not in (InspectionResult.QUALIFIED, InspectionResult.REJECTED):
        raise ValidationFailed("检验结论只能是合格或不合格。", code="INVALID_INSPECTION_RESULT")
    receipt = (
        GoodsReceipt.objects.select_for_update()
        .select_related("warehouse", "company", "purchase_order")
        .get(pk=receipt.pk)
    )
    if receipt.status == ReceiptStatus.INSPECTED:
        raise StateConflict("该收货单已完成检验判定。", code="ALREADY_INSPECTED")
    if receipt.status != ReceiptStatus.POSTED:
        raise StateConflict(
            "只有「已收货待检」的收货单可以检验判定；请先完成收货过账。", code="STATE_CONFLICT"
        )
    if not remark.strip():
        raise ValidationFailed("检验判定必须填写说明。", code="REASON_REQUIRED")

    target_status = (
        QualityStatus.QUALIFIED if result == InspectionResult.QUALIFIED else QualityStatus.REJECTED
    )
    lines = list(receipt.lines.select_related("material", "location").all())
    last_document_id = None
    for line in lines:
        document = stock.release_quality(
            user=user,
            company=receipt.company_id,
            warehouse=receipt.warehouse,
            material=line.material,
            quantity=line.quantity,
            location=line.location,
            batch_no=line.batch_no,
            roll_no=line.roll_no,
            from_status=QualityStatus.QUARANTINE,
            to_status=target_status,
            biz_type="procurement.receipt",
            biz_id=receipt.pk,
            biz_no=receipt.receipt_no,
            reason=f"来料检验 {receipt.receipt_no} 第 {line.line_no} 行：{remark[:200]}",
            idempotency_key=(idempotency_key or f"procurement-inspect-{receipt.pk}")
            if len(lines) == 1
            else f"procurement-inspect-{receipt.pk}-{line.line_no}",
        )
        last_document_id = document.pk

    receipt.status = ReceiptStatus.INSPECTED
    receipt.inspection_result = result
    receipt.inspected_at = timezone.now()
    receipt.inspected_by = user
    receipt.inspection_remark = remark
    receipt.quality_document_id = last_document_id
    receipt.save(
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
        instance=receipt,
        changes={
            "status": {"before": ReceiptStatus.POSTED, "after": ReceiptStatus.INSPECTED},
            "inspection_result": {"before": InspectionResult.NONE, "after": result},
        },
        reason=remark,
        object_repr=receipt.receipt_no,
        approval_basis=f"wms.InventoryDocument#{last_document_id}",
        company=receipt.company,
        actor=user,
    )
    publish_event(
        event_type=EVENT_RECEIPT_INSPECTED,
        aggregate_type="procurement.GoodsReceipt",
        aggregate_id=receipt.pk,
        payload={
            "receipt_id": receipt.pk,
            "receipt_no": receipt.receipt_no,
            "order_no": receipt.purchase_order.order_no,
            "result": result,
        },
        dedup_key=f"receipt:{receipt.pk}:inspected",
    )
    return receipt


@transaction.atomic
def cancel_receipt(receipt: GoodsReceipt, *, user: Any, reason: str) -> GoodsReceipt:
    require_codes(user, "procurement.receipt.update")
    if not reason.strip():
        raise ValidationFailed("取消必须填写原因。", code="REASON_REQUIRED")
    receipt = GoodsReceipt.objects.select_for_update().get(pk=receipt.pk)
    if receipt.status != ReceiptStatus.DRAFT:
        raise StateConflict(
            "只有草稿状态的收货单可以取消；已过账的收货不能取消，请走退货或冲销流程。",
            code="STATE_CONFLICT",
        )
    receipt.status = ReceiptStatus.CANCELLED
    receipt.save(update_fields=["status", "updated_at"])
    record_audit(
        action=AuditAction.UPDATE,
        instance=receipt,
        changes={"status": {"before": ReceiptStatus.DRAFT, "after": ReceiptStatus.CANCELLED}},
        reason=reason,
        object_repr=receipt.receipt_no,
        company=receipt.company,
        actor=user,
    )
    return receipt


@transaction.atomic
def create_order_from_requisition(
    requisition: PurchaseRequisition,
    *,
    user: Any,
    supplier: Supplier,
    lines: Sequence[dict] | None = None,
    **header: Any,
) -> PurchaseOrder:
    """按已批准的采购申请转采购订单。

    规则（任务书 10.6 的「转单前重新检查建议有效性」「同一建议不得重复转单」同样适用）：

    * 只有**已批准**的申请可以转单；
    * 转单数量不得超过申请行**未转数量**，超转直接拒绝；
    * 转单在同一事务内更新申请行的 `ordered_quantity`，因此重复转单会被拦截。
    """
    require_codes(user, "procurement.order.create")
    requisition = PurchaseRequisition.objects.select_for_update().get(pk=requisition.pk)
    if requisition.status != RequisitionStatus.APPROVED:
        raise StateConflict(
            f"采购申请当前状态为「{requisition.get_status_display()}」，只有已批准的申请可以转订单。",
            code="REQUISITION_NOT_APPROVED",
        )
    requisition_lines = list(
        requisition.lines.select_for_update().select_related("material").order_by("line_no")
    )
    if not requisition_lines:
        raise ValidationFailed("采购申请没有明细，不能转订单。", code="EMPTY_DOCUMENT")

    selected = {
        (_pk(row.get("requisition_line")) or _pk(row.get("source_line"))): row for row in (lines or [])
    }
    order_lines: list[dict] = []
    for line in requisition_lines:
        row = selected.get(line.pk)
        if lines is not None and row is None:
            continue
        quantity = Decimal(row["quantity"]) if row is not None else (line.quantity - line.ordered_quantity)
        if quantity <= ZERO:
            continue
        available = line.quantity - line.ordered_quantity
        if quantity > available:
            raise ValidationFailed(
                f"申请行 {line.line_no} 转单数量超出未转数量。",
                code="OVER_CONVERT",
                details={"requested": str(quantity), "available": str(available)},
            )
        order_lines.append(
            {
                "material_id": line.material_id,
                "quantity": quantity,
                "price": (row or {}).get("price") or line.material.purchase_price or ZERO,
                "uom_id": line.uom_id,
                "expected_date": (row or {}).get("expected_date") or line.needed_date,
                "source_line_id": line.pk,
                "remark": line.remark,
            }
        )
    if not order_lines:
        raise ValidationFailed("没有可转单的申请明细。", code="NOTHING_TO_CONVERT")

    order = create_order(
        user=user,
        company=requisition.company,
        supplier=supplier,
        lines=order_lines,
        source_requisition=requisition,
        **header,
    )
    for line in order.lines.all():
        if line.source_line_id:
            PurchaseRequisitionLine.objects.filter(pk=line.source_line_id).update(
                ordered_quantity=F("ordered_quantity") + line.quantity
            )
    return order


__all__ = [
    "BIZ_TYPE_ORDER",
    "BIZ_TYPE_REQUISITION",
    "cancel_order",
    "cancel_receipt",
    "cancel_requisition",
    "close_order",
    "compute_line_amount",
    "create_order",
    "create_order_from_requisition",
    "create_receipt",
    "create_requisition",
    "inspect_receipt",
    "money",
    "on_order_approval_outcome",
    "on_requisition_approval_outcome",
    "post_receipt",
    "recalculate_order_amounts",
    "submit_order",
    "submit_requisition",
    "update_order",
    "update_receipt",
    "update_requisition",
]
