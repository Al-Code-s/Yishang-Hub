"""审批查询。

可见性规则：
* 我提交的；
* 当前节点候选审批人是我的（待办）；
* 我参与过审批的；
* 超级管理员或具备数据范围的管理者按数据范围查看。
"""

from __future__ import annotations

from django.db.models import F, Q, QuerySet

from apps.core.selectors import (
    EMPTY_SCOPE_TYPE,
    resolve_data_scope,
    scoped_queryset,
)
from apps.workflow.models import ApprovalInstance, InstanceStatus, StepStatus


def role_ids_of(user) -> list[int]:
    return list(user.roles.filter(is_active=True).values_list("id", flat=True))


def todo_queryset(user) -> QuerySet:
    """我的待办：当前节点仍待审批且我可以审批。

    注意：三个条件必须写在同一个 filter() 里。分多次 filter() 会让 Django
    为 ``steps`` 建立多个 JOIN，导致「本节点待我审批」退化成「流程里存在
    某个待审批节点、且某个节点与我有关」，从而把上级节点的待办泄露给下级
    审批人。
    """
    role_ids = role_ids_of(user)
    queryset = (
        ApprovalInstance.objects.filter(
            Q(status=InstanceStatus.PENDING)
            & Q(steps__status=StepStatus.PENDING)
            & Q(steps__seq=F("current_seq"))
            & (Q(steps__assigned_user=user) | Q(steps__approver_role_id__in=role_ids))
        )
        .distinct()
    )
    # 申请人回避：模板未允许自审时不出现在自己的待办里
    return queryset.exclude(applicant=user, template__allow_self_approval=False)


def my_instances_queryset(user) -> QuerySet:
    return ApprovalInstance.objects.filter(applicant=user)


def participated_queryset(user) -> QuerySet:
    return ApprovalInstance.objects.filter(steps__decided_by=user).distinct()


def visible_instances(user) -> QuerySet:
    """综合可见范围：本人相关 + 数据范围内可管理。"""
    base = ApprovalInstance.objects.select_related(
        "template", "applicant", "company", "department"
    )
    if getattr(user, "is_superuser", False):
        return base.all()

    role_ids = role_ids_of(user)
    personal = (
        Q(applicant=user)
        | Q(steps__decided_by=user)
        | Q(steps__assigned_user=user)
        | Q(steps__approver_role_id__in=role_ids)
    )
    scope = resolve_data_scope(user)
    if scope.scope_type == EMPTY_SCOPE_TYPE:
        return base.filter(personal).distinct()
    managed = scoped_queryset(
        base,
        user,
        company_field="company_id",
        department_field="department_id",
        owner_field="applicant_id",
    )
    return base.filter(Q(pk__in=managed.values("pk")) | personal).distinct()

