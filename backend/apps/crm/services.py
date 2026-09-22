"""客户模块的领域规则。

放在服务层而不是信号里：规则需要显式可测、可审计，且不要在保存客户时
隐式产生别的副作用（任务书 4.3 禁止用 signals 承载关键流程）。

客户编码的自动取号（`next_customer_code`）也放在这里：让「编码从哪来」只有一处口径，
视图层只调用，不自己拼格式。

两条客户侧流程的状态机同样落在这里：

* 投诉：待受理 → 处理中 → 已解决 → 已关闭（跳步一律拒绝）；
* 评价：待回复 → 已回复 → 已关闭。

每次流转都在同一事务内写一条审计记录（``record_audit``），不另建一套模块日志表
——平台已有「系统管理 → 审计与登录日志」承载这件事，重复造表只会让口径分叉。
"""

from __future__ import annotations

from typing import Any

from django.db import transaction

from apps.core.exceptions import StateConflict, ValidationFailed
from apps.core.models import AuditAction
from apps.core.services import business_now, ensure_single_primary, generate_code, record_audit
from apps.crm.models import (
    ComplaintStatus,
    CustomerComplaint,
    CustomerContact,
    ProductReview,
    ProductReviewStatus,
)

CUSTOMER_CODE_RULE = "CUS"
COMPLAINT_CODE_RULE = "CMPL"
PRODUCT_REVIEW_CODE_RULE = "PRV"


def next_customer_code() -> str:
    """按编码规则取下一个客户编码。

    规则本体（编号格式与重置周期）由 `bootstrap_system.CODE_RULES` 登记，
    并可在「系统管理 -> 编码规则」中调整；这里只引用规则编码，**不硬编码格式**，
    避免出现「改了规则却不生效」的两套口径。

    取号在 `generate_code` 的事务内完成（先锁规则行再锁流水行），并发调用不会重号。
    """
    return generate_code(CUSTOMER_CODE_RULE)


def ensure_single_primary_contact(contact: CustomerContact) -> None:
    """保证同一客户下只有一个主要联系人。

    通用规则实现在 `apps/core/services.py::ensure_single_primary`，
    这里只绑定客户联系人的归属字段，避免各模块各写一份。
    """
    ensure_single_primary(
        CustomerContact,
        instance=contact,
        scope_field="customer_id",
        scope_id=contact.customer_id,
    )


def next_complaint_no() -> str:
    """客户投诉编号（编码规则 ``CMPL``，见 ``bootstrap_system.CODE_RULES``）。"""
    return generate_code(COMPLAINT_CODE_RULE)


def next_review_no() -> str:
    """产品评价编号（编码规则 ``PRV``）。"""
    return generate_code(PRODUCT_REVIEW_CODE_RULE)


def _record_transition(
    instance: Any, *, before: str, reason: str, changes: dict[str, Any] | None = None
) -> None:
    """把一次状态流转写进审计日志（必须在业务事务内调用）。"""
    payload: dict[str, Any] = {"status": {"before": before, "after": instance.status}}
    if changes:
        payload.update(changes)
    record_audit(
        action=AuditAction.UPDATE,
        instance=instance,
        changes=payload,
        reason=reason,
    )


# ---------------------------------------------------------------------------
# 客户投诉：待受理 → 处理中 → 已解决 → 已关闭
# ---------------------------------------------------------------------------


@transaction.atomic
def accept_complaint(
    complaint: CustomerComplaint,
    *,
    receiver: Any = None,
    handler: Any = None,
    measure: str = "",
) -> CustomerComplaint:
    """受理投诉：待受理 → 处理中。"""
    if complaint.status == ComplaintStatus.HANDLING:
        raise StateConflict("该投诉已在处理中。", code="COMPLAINT_STATUS_INVALID")
    if complaint.status != ComplaintStatus.PENDING:
        raise StateConflict("只有待受理的投诉可以受理。", code="COMPLAINT_STATUS_INVALID")

    before = complaint.status
    complaint.status = ComplaintStatus.HANDLING
    complaint.accepted_at = business_now()
    if receiver is not None:
        complaint.receiver = receiver
    if handler is not None:
        complaint.handler = handler
    text = (measure or "").strip()
    if text:
        complaint.handle_measure = text
    complaint.save(
        update_fields=[
            "status",
            "accepted_at",
            "receiver",
            "handler",
            "handle_measure",
            "updated_at",
        ]
    )
    _record_transition(complaint, before=before, reason="受理客户投诉")
    return complaint


@transaction.atomic
def resolve_complaint(
    complaint: CustomerComplaint,
    *,
    measure: str,
    handler: Any = None,
    satisfaction: int | None = None,
) -> CustomerComplaint:
    """登记处理结果：处理中 → 已解决。

    ``satisfaction`` 只能来自**客户回访结果**：不传即保持 0（未评价），
    不允许服务端凭空写一个分数，避免把「没有回访」伪造成「客户满意」。
    """
    if complaint.status != ComplaintStatus.HANDLING:
        raise StateConflict("只有处理中的投诉可以登记处理结果。", code="COMPLAINT_STATUS_INVALID")
    text = (measure or "").strip()
    if not text:
        raise ValidationFailed("登记处理结果必须填写处理措施。", code="COMPLAINT_MEASURE_REQUIRED")
    if satisfaction is not None and not 0 <= int(satisfaction) <= 5:
        raise ValidationFailed("满意度评分只能是 0~5。", code="COMPLAINT_SATISFACTION_INVALID")

    before = complaint.status
    complaint.status = ComplaintStatus.RESOLVED
    complaint.handle_measure = text
    complaint.resolved_at = business_now()
    if handler is not None:
        complaint.handler = handler
    if satisfaction is not None:
        complaint.satisfaction = int(satisfaction)
    complaint.save(
        update_fields=[
            "status",
            "handle_measure",
            "resolved_at",
            "handler",
            "satisfaction",
            "updated_at",
        ]
    )
    _record_transition(complaint, before=before, reason="登记投诉处理结果")
    return complaint


@transaction.atomic
def close_complaint(complaint: CustomerComplaint, *, note: str = "") -> CustomerComplaint:
    """关闭投诉：已解决 → 已关闭（未登记的投诉不允许直接关闭）。"""
    if complaint.status == ComplaintStatus.CLOSED:
        raise StateConflict("该投诉已关闭。", code="COMPLAINT_STATUS_INVALID")
    if complaint.status != ComplaintStatus.RESOLVED:
        raise StateConflict("投诉必须先登记处理结果，才能关闭。", code="COMPLAINT_STATUS_INVALID")

    before = complaint.status
    complaint.status = ComplaintStatus.CLOSED
    complaint.closed_at = business_now()
    complaint.save(update_fields=["status", "closed_at", "updated_at"])
    _record_transition(complaint, before=before, reason=(note or "").strip() or "关闭客户投诉")
    return complaint


# ---------------------------------------------------------------------------
# 产品评价：待回复 → 已回复 → 已关闭
# ---------------------------------------------------------------------------


@transaction.atomic
def reply_product_review(review: ProductReview, *, reply: str, replier: Any = None) -> ProductReview:
    """回复评价：待回复 → 已回复。"""
    if review.status == ProductReviewStatus.REPLIED:
        raise StateConflict("该评价已回复，如需修改请直接编辑回复内容。", code="REVIEW_STATUS_INVALID")
    if review.status != ProductReviewStatus.PENDING:
        raise StateConflict("已关闭的评价不能再回复。", code="REVIEW_STATUS_INVALID")
    text = (reply or "").strip()
    if not text:
        raise ValidationFailed("回复内容不能为空。", code="REVIEW_REPLY_REQUIRED")

    before = review.status
    review.status = ProductReviewStatus.REPLIED
    review.reply = text
    review.replied_at = business_now()
    if replier is not None:
        review.replier = replier
    review.save(update_fields=["status", "reply", "replied_at", "replier", "updated_at"])
    _record_transition(review, before=before, reason="回复产品评价")
    return review


@transaction.atomic
def close_product_review(review: ProductReview, *, note: str = "") -> ProductReview:
    """关闭评价：已回复 → 已关闭。"""
    if review.status == ProductReviewStatus.CLOSED:
        raise StateConflict("该评价已关闭。", code="REVIEW_STATUS_INVALID")
    if review.status != ProductReviewStatus.REPLIED:
        raise StateConflict("评价必须先回复，才能关闭。", code="REVIEW_STATUS_INVALID")

    before = review.status
    review.status = ProductReviewStatus.CLOSED
    review.closed_at = business_now()
    review.save(update_fields=["status", "closed_at", "updated_at"])
    _record_transition(review, before=before, reason=(note or "").strip() or "关闭产品评价")
    return review
