"""审批业务服务。

规则要点：
* 审批实例保存模板与节点快照，模板后续修改不影响历史；
* 默认禁止申请人审批自己的单据，例外需在模板上显式开启并留痕；
* 条件路由（金额 / 部门）在提交时求值，未命中任何节点时直接报错，
  避免“静默通过”；
* 审批通过与库存过账是两个动作，本模块不产生任何库存副作用。
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.core.exceptions import NotPermitted, ObjectNotFound, StateConflict, ValidationFailed
from apps.core.models import AuditAction
from apps.core.permissions import require_codes
from apps.core.services import publish_event, record_audit
from apps.identity.models import User
from apps.workflow.models import (
    ApprovalAction,
    ApprovalInstance,
    ApprovalLog,
    ApprovalStep,
    ApprovalTemplate,
    InstanceStatus,
    StepStatus,
)
from apps.workflow.registry import (
    OUTCOME_APPROVED,
    OUTCOME_REJECTED,
    OUTCOME_WITHDRAWN,
    apply_biz_outcome,
)

EVENT_APPROVAL_SUBMITTED = "workflow.approval.submitted"
EVENT_APPROVAL_DECIDED = "workflow.approval.decided"

PERMISSION_SUBMIT = "workflow.instance.submit"
PERMISSION_APPROVE = "workflow.instance.approve"
PERMISSION_WITHDRAW = "workflow.instance.withdraw"

GENERIC_BIZ_TYPE = "generic.request"


def resolve_template(*, code: str | None = None, biz_type: str | None = None, company=None) -> ApprovalTemplate:
    queryset = ApprovalTemplate.objects.filter(is_active=True)
    if code:
        template = queryset.filter(code=code).first()
    elif biz_type:
        candidates = queryset.filter(biz_type=biz_type)
        template = (
            candidates.filter(company=company).first()
            if company is not None
            else None
        ) or candidates.filter(company__isnull=True).first() or candidates.first()
    else:
        template = None
    if template is None:
        raise ObjectNotFound(
            "未找到可用的审批模板。",
            code="APPROVAL_TEMPLATE_NOT_FOUND",
            details={"code": code, "biz_type": biz_type},
        )
    return template


def _snapshot_template(template: ApprovalTemplate) -> dict[str, Any]:
    return {
        "code": template.code,
        "name": template.name,
        "biz_type": template.biz_type,
        "version_no": template.version_no,
        "allow_self_approval": template.allow_self_approval,
        "nodes": [
            {
                "seq": node.seq,
                "name": node.name,
                "approver_type": node.approver_type,
                "approver_role_id": node.approver_role_id,
                "approver_user_id": node.approver_user_id,
                "amount_min": str(node.amount_min) if node.amount_min is not None else None,
                "amount_max": str(node.amount_max) if node.amount_max is not None else None,
                "department_ids": list(node.department_ids or []),
            }
            for node in template.nodes.filter(is_active=True).order_by("seq")
        ],
    }


@transaction.atomic
def create_instance(
    actor: User,
    *,
    title: str,
    template_code: str | None = None,
    biz_type: str = GENERIC_BIZ_TYPE,
    biz_id: str = "",
    biz_no: str = "",
    summary: str = "",
    amount: Decimal | None = None,
    company=None,
    department=None,
) -> ApprovalInstance:
    """创建审批单（草稿）。提交时才会路由并生成步骤。"""
    if not title.strip():
        raise ValidationFailed("申请标题不能为空。", code="TITLE_REQUIRED")

    target_company = company if company is not None else actor.company
    template = resolve_template(code=template_code, biz_type=biz_type, company=target_company)

    instance = ApprovalInstance.objects.create(
        template=template,
        template_version=template.version_no,
        biz_type=biz_type,
        biz_id=str(biz_id or ""),
        title=title.strip(),
        summary=summary,
        company=target_company,
        department=department if department is not None else actor.department,
        applicant=actor,
        amount=amount,
        status=InstanceStatus.DRAFT,
        created_by=actor,
        updated_by=actor,
    )

    if not biz_no:
        instance.biz_no = f"SP{instance.pk:08d}"
        instance.save(update_fields=["biz_no"])

    record_audit(
        action=AuditAction.CREATE,
        instance=instance,
        object_repr=instance.title,
        changes={"title": instance.title, "biz_type": instance.biz_type},
    )
    return instance


def _applicable_nodes(template: ApprovalTemplate, instance: ApprovalInstance) -> list[Any]:
    nodes = list(template.nodes.filter(is_active=True).order_by("seq"))
    matched = [
        node for node in nodes if node.matches(amount=instance.amount, department_id=instance.department_id)
    ]
    if not matched:
        raise ValidationFailed(
            "当前审批模板没有匹配的审批节点，已拒绝提交，避免单据被静默跳过。",
            code="APPROVAL_NO_MATCHING_NODE",
        )
    return matched


@transaction.atomic
def submit_instance(actor: User, instance: ApprovalInstance, *, comment: str = "") -> ApprovalInstance:
    """提交审批：生成步骤、推进到首个节点，并通过发件箱通知审批人。"""
    instance = ApprovalInstance.objects.select_for_update().get(pk=instance.pk)
    if instance.status != InstanceStatus.DRAFT:
        raise StateConflict("只有草稿状态的审批单可以提交。", code="APPROVAL_NOT_DRAFT")
    if instance.applicant_id != actor.pk:
        require_codes(actor, PERMISSION_SUBMIT)

    template = instance.template
    nodes = _applicable_nodes(template, instance)

    instance.template_snapshot = _snapshot_template(template)
    instance.template_version = template.version_no
    instance.steps.all().delete()

    first_seq = nodes[0].seq
    ApprovalStep.objects.bulk_create(
        [
            ApprovalStep(
                instance=instance,
                seq=node.seq,
                name=node.name,
                approver_type=node.approver_type,
                approver_role=node.approver_role,
                assigned_user=node.approver_user,
                status=StepStatus.PENDING if node.seq == first_seq else StepStatus.WAITING,
            )
            for node in nodes
        ]
    )

    instance.status = InstanceStatus.PENDING
    instance.current_seq = first_seq
    instance.submitted_at = timezone.now()
    instance.save(
        update_fields=[
            "template_snapshot", "template_version", "status", "current_seq",
            "submitted_at", "updated_at",
        ]
    )

    ApprovalLog.objects.create(
        instance=instance,
        seq=0,
        action=ApprovalAction.SUBMIT,
        actor=actor,
        actor_name=actor.display_name or actor.username,
        comment=comment,
    )
    record_audit(
        action=AuditAction.SUBMIT,
        instance=instance,
        object_repr=instance.title,
        reason=comment,
    )

    first_step = instance.steps.get(seq=first_seq)
    publish_event(
        event_type=EVENT_APPROVAL_SUBMITTED,
        aggregate_type="workflow.ApprovalInstance",
        aggregate_id=instance.pk,
        payload={
            "instance_id": instance.pk,
            "biz_no": instance.biz_no,
            "title": instance.title,
            "applicant_id": instance.applicant_id,
            "assignee_user_ids": first_step.candidate_user_ids(),
            "step_name": first_step.name,
        },
    )
    return instance


def _assert_can_decide(actor: User, instance: ApprovalInstance, step: ApprovalStep) -> None:
    require_codes(actor, PERMISSION_APPROVE)
    candidates = set(step.candidate_user_ids())
    if actor.pk not in candidates:
        raise NotPermitted(
            "当前节点不允许该用户审批。", code="NOT_CURRENT_APPROVER", details={"step_id": step.pk}
        )
    if actor.pk == instance.applicant_id and not instance.template.allow_self_approval:
        raise NotPermitted(
            "该审批模板不允许申请人审批自己的单据。", code="SELF_APPROVAL_FORBIDDEN"
        )


@transaction.atomic
def approve_instance(actor: User, instance: ApprovalInstance, *, comment: str = "") -> ApprovalInstance:
    instance = ApprovalInstance.objects.select_for_update().get(pk=instance.pk)
    if instance.status != InstanceStatus.PENDING:
        raise StateConflict("只有审批中的单据可以审批。", code="APPROVAL_NOT_PENDING")

    step = instance.steps.filter(seq=instance.current_seq).first()
    if step is None or step.status != StepStatus.PENDING:
        raise StateConflict("当前节点状态异常，无法审批。", code="APPROVAL_STEP_NOT_PENDING")

    _assert_can_decide(actor, instance, step)

    step.status = StepStatus.APPROVED
    step.decided_by = actor
    step.decided_at = timezone.now()
    step.decision = "approved"
    step.comment = comment
    step.save(update_fields=["status", "decided_by", "decided_at", "decision", "comment"])

    ApprovalLog.objects.create(
        instance=instance,
        step=step,
        seq=step.seq,
        action=ApprovalAction.APPROVE,
        actor=actor,
        actor_name=actor.display_name or actor.username,
        comment=comment,
    )
    record_audit(
        action=AuditAction.APPROVE,
        instance=instance,
        changes={"step": {"before": step.name, "after": "approved"}},
        reason=comment,
        object_repr=instance.title,
    )

    next_step = instance.steps.filter(seq__gt=step.seq, status=StepStatus.WAITING).order_by("seq").first()
    if next_step is not None:
        next_step.status = StepStatus.PENDING
        next_step.save(update_fields=["status"])
        instance.current_seq = next_step.seq
        instance.save(update_fields=["current_seq", "updated_at"])
        publish_event(
            event_type=EVENT_APPROVAL_SUBMITTED,
            aggregate_type="workflow.ApprovalInstance",
            aggregate_id=instance.pk,
            payload={
                "instance_id": instance.pk,
                "biz_no": instance.biz_no,
                "title": instance.title,
                "applicant_id": instance.applicant_id,
                "assignee_user_ids": next_step.candidate_user_ids(),
                "step_name": next_step.name,
            },
            dedup_key=f"approval:{instance.pk}:step:{next_step.seq}",
        )
        return instance

    instance.status = InstanceStatus.APPROVED
    instance.finished_at = timezone.now()
    instance.save(update_fields=["status", "finished_at", "updated_at"])
    apply_biz_outcome(instance, OUTCOME_APPROVED)
    publish_event(
        event_type=EVENT_APPROVAL_DECIDED,
        aggregate_type="workflow.ApprovalInstance",
        aggregate_id=instance.pk,
        payload={
            "instance_id": instance.pk,
            "biz_no": instance.biz_no,
            "title": instance.title,
            "result": "approved",
            "recipient_user_ids": [instance.applicant_id],
        },
        dedup_key=f"approval:{instance.pk}:decided",
    )
    return instance


@transaction.atomic
def reject_instance(
    actor: User, instance: ApprovalInstance, *, comment: str = ""
) -> ApprovalInstance:
    if not comment.strip():
        raise ValidationFailed("驳回必须填写审批意见。", code="REJECT_COMMENT_REQUIRED")

    instance = ApprovalInstance.objects.select_for_update().get(pk=instance.pk)
    if instance.status != InstanceStatus.PENDING:
        raise StateConflict("只有审批中的单据可以驳回。", code="APPROVAL_NOT_PENDING")

    step = instance.steps.filter(seq=instance.current_seq).first()
    if step is None or step.status != StepStatus.PENDING:
        raise StateConflict("当前节点状态异常，无法驳回。", code="APPROVAL_STEP_NOT_PENDING")

    _assert_can_decide(actor, instance, step)

    step.status = StepStatus.REJECTED
    step.decided_by = actor
    step.decided_at = timezone.now()
    step.decision = "rejected"
    step.comment = comment
    step.save(update_fields=["status", "decided_by", "decided_at", "decision", "comment"])

    instance.steps.filter(status=StepStatus.WAITING).update(status=StepStatus.SKIPPED)
    instance.status = InstanceStatus.REJECTED
    instance.finished_at = timezone.now()
    instance.save(update_fields=["status", "finished_at", "updated_at"])
    apply_biz_outcome(instance, OUTCOME_REJECTED)

    ApprovalLog.objects.create(
        instance=instance,
        step=step,
        seq=step.seq,
        action=ApprovalAction.REJECT,
        actor=actor,
        actor_name=actor.display_name or actor.username,
        comment=comment,
    )
    record_audit(
        action=AuditAction.REJECT,
        instance=instance,
        reason=comment,
        object_repr=instance.title,
    )
    publish_event(
        event_type=EVENT_APPROVAL_DECIDED,
        aggregate_type="workflow.ApprovalInstance",
        aggregate_id=instance.pk,
        payload={
            "instance_id": instance.pk,
            "biz_no": instance.biz_no,
            "title": instance.title,
            "result": "rejected",
            "recipient_user_ids": [instance.applicant_id],
        },
        dedup_key=f"approval:{instance.pk}:decided",
    )
    return instance


@transaction.atomic
def withdraw_instance(
    actor: User, instance: ApprovalInstance, *, comment: str = ""
) -> ApprovalInstance:
    instance = ApprovalInstance.objects.select_for_update().get(pk=instance.pk)
    if instance.applicant_id != actor.pk:
        raise NotPermitted("只有申请人本人可以撤回。", code="NOT_APPLICANT")
    if instance.status != InstanceStatus.PENDING:
        raise StateConflict("只有审批中的单据可以撤回。", code="APPROVAL_NOT_PENDING")

    instance.steps.filter(status__in=[StepStatus.WAITING, StepStatus.PENDING]).update(
        status=StepStatus.CANCELLED
    )
    instance.status = InstanceStatus.WITHDRAWN
    instance.finished_at = timezone.now()
    instance.save(update_fields=["status", "finished_at", "updated_at"])
    apply_biz_outcome(instance, OUTCOME_WITHDRAWN)

    ApprovalLog.objects.create(
        instance=instance,
        seq=instance.current_seq,
        action=ApprovalAction.WITHDRAW,
        actor=actor,
        actor_name=actor.display_name or actor.username,
        comment=comment,
    )
    record_audit(
        action=AuditAction.WITHDRAW,
        instance=instance,
        reason=comment,
        object_repr=instance.title,
    )
    return instance


def add_comment(actor: User, instance: ApprovalInstance, *, comment: str) -> ApprovalLog:
    """补充意见。仅申请人与各节点候选审批人可以留言。"""
    if not comment.strip():
        raise ValidationFailed("意见内容不能为空。", code="COMMENT_REQUIRED")
    participants = {instance.applicant_id}
    for step in instance.steps.all():
        participants.update(step.candidate_user_ids())
    if actor.pk not in participants and not actor.is_superuser:
        raise NotPermitted("只有流程参与人可以补充意见。", code="NOT_PARTICIPANT")

    log = ApprovalLog.objects.create(
        instance=instance,
        seq=instance.current_seq,
        action=ApprovalAction.COMMENT,
        actor=actor,
        actor_name=actor.display_name or actor.username,
        comment=comment,
    )
    record_audit(action=AuditAction.UPDATE, instance=instance, reason=f"审批意见：{comment}")
    return log


def mark_template_changed(actor: User, template: ApprovalTemplate) -> None:
    """模板节点发生变化时递增版本号，便于实例快照与排查。"""
    template.version_no = (template.version_no or 1) + 1
    template.save(update_fields=["version_no", "updated_at"])
    record_audit(
        action=AuditAction.UPDATE,
        instance=template,
        changes={"version_no": {"before": template.version_no - 1, "after": template.version_no}},
        reason="审批模板变更",
    )


def candidate_user_ids_for_pending(template: ApprovalTemplate, amount, department_id) -> list[int]:
    """预演用：给定金额与部门，返回将参与审批的用户。"""
    users: list[int] = []
    for node in template.nodes.filter(is_active=True).order_by("seq"):
        if node.matches(amount=amount, department_id=department_id):
            if node.approver_user_id:
                users.append(node.approver_user_id)
            else:
                from apps.identity.models import UserRole

                users.extend(
                    UserRole.objects.filter(
                        role_id=node.approver_role_id, user__is_active=True
                    ).values_list("user_id", flat=True)
                )
    return list(dict.fromkeys(users))


__all__ = [
    "EVENT_APPROVAL_DECIDED",
    "EVENT_APPROVAL_SUBMITTED",
    "GENERIC_BIZ_TYPE",
    "PERMISSION_APPROVE",
    "PERMISSION_SUBMIT",
    "PERMISSION_WITHDRAW",
    "add_comment",
    "approve_instance",
    "candidate_user_ids_for_pending",
    "create_instance",
    "mark_template_changed",
    "reject_instance",
    "resolve_template",
    "submit_instance",
    "withdraw_instance",
]
