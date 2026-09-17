"""审批流程模型。

首版能力：顺序多级审批、金额与部门条件路由、提交/通过/驳回/撤回、
审批意见与附件、模板版本快照、申请人回避。

审批通过与库存过账是不同动作，二者不混为一谈。
"""

from __future__ import annotations

from django.conf import settings
from django.db import models

from apps.core.constants import MONEY_DECIMAL_PLACES, MONEY_MAX_DIGITS
from apps.core.models import BaseModel, TimeStampedModel


class ApproverType(models.TextChoices):
    ROLE = "role", "按角色"
    USER = "user", "指定人员"


class InstanceStatus(models.TextChoices):
    DRAFT = "draft", "草稿"
    PENDING = "pending", "审批中"
    APPROVED = "approved", "已通过"
    REJECTED = "rejected", "已驳回"
    WITHDRAWN = "withdrawn", "已撤回"
    CANCELLED = "cancelled", "已取消"

    @classmethod
    def open_statuses(cls) -> tuple[str, ...]:
        return (cls.DRAFT, cls.PENDING)


class StepStatus(models.TextChoices):
    WAITING = "waiting", "未开始"
    PENDING = "pending", "待审批"
    APPROVED = "approved", "已通过"
    REJECTED = "rejected", "已驳回"
    SKIPPED = "skipped", "已跳过"
    CANCELLED = "cancelled", "已取消"


class ApprovalAction(models.TextChoices):
    SUBMIT = "submit", "提交"
    APPROVE = "approve", "通过"
    REJECT = "reject", "驳回"
    WITHDRAW = "withdraw", "撤回"
    COMMENT = "comment", "意见"


class ApprovalTemplate(BaseModel):
    """审批模板。节点变更时 version_no 自增，实例保存快照以保证历史可追溯。"""

    code = models.CharField("模板编码", max_length=64, unique=True)
    name = models.CharField("模板名称", max_length=128)
    biz_type = models.CharField(
        "业务类型",
        max_length=64,
        db_index=True,
        help_text="例如 generic.request、procurement.request；用于按业务选择模板。",
    )
    company = models.ForeignKey(
        "factory.Company",
        verbose_name="适用公司",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="approval_templates",
    )
    allow_self_approval = models.BooleanField(
        "允许申请人审批自己的单据",
        default=False,
        help_text="默认关闭；开启属于例外授权，必须在审批轨迹中留痕。",
    )
    version_no = models.PositiveIntegerField("模板版本", default=1)
    description = models.TextField("说明", blank=True, default="")
    is_active = models.BooleanField("启用", default=True, db_index=True)

    class Meta:
        verbose_name = "审批模板"
        verbose_name_plural = "审批模板"
        ordering = ["biz_type", "code"]

    def __str__(self) -> str:
        return f"{self.name}({self.code})"


class ApprovalTemplateNode(BaseModel):
    """审批节点。按 seq 顺序审批；金额与部门条件用于路由。"""

    template = models.ForeignKey(
        ApprovalTemplate, on_delete=models.CASCADE, related_name="nodes"
    )
    seq = models.PositiveIntegerField("顺序号")
    name = models.CharField("节点名称", max_length=64)
    approver_type = models.CharField(
        "审批人类型", max_length=8, choices=ApproverType.choices, default=ApproverType.ROLE
    )
    approver_role = models.ForeignKey(
        "identity.Role",
        verbose_name="审批角色",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="approval_nodes",
    )
    approver_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="指定审批人",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    amount_min = models.DecimalField(
        "金额下限", max_digits=MONEY_MAX_DIGITS, decimal_places=MONEY_DECIMAL_PLACES,
        null=True, blank=True,
    )
    amount_max = models.DecimalField(
        "金额上限", max_digits=MONEY_MAX_DIGITS, decimal_places=MONEY_DECIMAL_PLACES,
        null=True, blank=True,
    )
    department_ids = models.JSONField(
        "适用部门",
        default=list,
        blank=True,
        help_text="为空表示不限部门；否则申请人部门需命中列表。",
    )
    is_active = models.BooleanField("启用", default=True)

    class Meta:
        verbose_name = "审批节点"
        verbose_name_plural = "审批节点"
        ordering = ["template_id", "seq"]
        constraints = [
            models.UniqueConstraint(fields=["template", "seq"], name="uq_template_node_seq"),
        ]

    def __str__(self) -> str:
        return f"{self.template_id}-{self.seq}-{self.name}"

    def matches(self, *, amount, department_id) -> bool:
        """判断该节点是否适用于本次申请。"""
        if amount is not None:
            if self.amount_min is not None and amount < self.amount_min:
                return False
            if self.amount_max is not None and amount > self.amount_max:
                return False
        elif self.amount_min is not None or self.amount_max is not None:
            # 模板设置了金额区间但申请未填金额：不命中，避免误路由
            return False
        if self.department_ids:
            return department_id is not None and department_id in self.department_ids
        return True


class ApprovalInstance(BaseModel):
    """审批实例。template_snapshot 保存提交时刻的模板与节点，保证历史不被后续修改影响。"""

    template = models.ForeignKey(
        ApprovalTemplate, on_delete=models.PROTECT, related_name="instances"
    )
    template_version = models.PositiveIntegerField("模板版本快照", default=1)
    template_snapshot = models.JSONField("模板快照", default=dict, blank=True)

    biz_type = models.CharField("业务类型", max_length=64, db_index=True)
    biz_id = models.CharField("业务主键", max_length=64, blank=True, default="", db_index=True)
    biz_no = models.CharField("业务单号", max_length=64, blank=True, default="")
    title = models.CharField("标题", max_length=200)
    summary = models.TextField("申请说明", blank=True, default="")

    company = models.ForeignKey(
        "factory.Company",
        verbose_name="所属公司",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="approval_instances",
    )
    department = models.ForeignKey(
        "factory.Department",
        verbose_name="申请部门",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="approval_instances",
    )
    applicant = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="申请人",
        on_delete=models.PROTECT,
        related_name="approval_instances",
    )
    amount = models.DecimalField(
        "涉及金额", max_digits=MONEY_MAX_DIGITS, decimal_places=MONEY_DECIMAL_PLACES,
        null=True, blank=True,
    )
    status = models.CharField(
        "状态", max_length=16, choices=InstanceStatus.choices, default=InstanceStatus.DRAFT,
        db_index=True,
    )
    current_seq = models.PositiveIntegerField("当前节点顺序", default=0)
    submitted_at = models.DateTimeField("提交时间", null=True, blank=True)
    finished_at = models.DateTimeField("完成时间", null=True, blank=True)

    class Meta:
        verbose_name = "审批实例"
        verbose_name_plural = "审批实例"
        ordering = ["-id"]
        indexes = [
            models.Index(fields=["status", "-id"], name="idx_approval_status"),
            models.Index(fields=["biz_type", "biz_id"], name="idx_approval_biz"),
            models.Index(fields=["applicant", "status"], name="idx_approval_applicant"),
        ]

    def __str__(self) -> str:
        return f"{self.title}({self.status})"

    @property
    def current_step(self) -> ApprovalStep | None:
        return self.steps.filter(seq=self.current_seq).first()


class ApprovalStep(models.Model):
    """审批步骤。"""

    id = models.BigAutoField(primary_key=True)
    instance = models.ForeignKey(
        ApprovalInstance, on_delete=models.CASCADE, related_name="steps"
    )
    seq = models.PositiveIntegerField("顺序号")
    name = models.CharField("节点名称", max_length=64)
    approver_type = models.CharField(
        "审批人类型", max_length=8, choices=ApproverType.choices, default=ApproverType.ROLE
    )
    approver_role = models.ForeignKey(
        "identity.Role", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    assigned_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    status = models.CharField(
        "状态", max_length=16, choices=StepStatus.choices, default=StepStatus.WAITING, db_index=True
    )
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    decided_at = models.DateTimeField("处理时间", null=True, blank=True)
    decision = models.CharField("处理结果", max_length=16, blank=True, default="")
    comment = models.TextField("审批意见", blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "审批步骤"
        verbose_name_plural = "审批步骤"
        ordering = ["instance_id", "seq"]
        constraints = [
            models.UniqueConstraint(fields=["instance", "seq"], name="uq_approval_step_seq"),
        ]

    def __str__(self) -> str:
        return f"{self.instance_id}-{self.seq}-{self.name}"

    def candidate_user_ids(self) -> list[int]:
        """该步骤的候选审批人。"""
        if self.assigned_user_id:
            return [self.assigned_user_id]
        if self.approver_role_id:
            from apps.identity.models import UserRole

            return list(
                UserRole.objects.filter(
                    role_id=self.approver_role_id,
                    user__is_active=True,
                ).values_list("user_id", flat=True)
            )
        return []


class ApprovalLog(models.Model):
    """审批轨迹。只追加，不修改。"""

    id = models.BigAutoField(primary_key=True)
    instance = models.ForeignKey(
        ApprovalInstance, on_delete=models.CASCADE, related_name="logs"
    )
    step = models.ForeignKey(
        ApprovalStep, null=True, blank=True, on_delete=models.SET_NULL, related_name="logs"
    )
    seq = models.PositiveIntegerField("节点顺序", default=0)
    action = models.CharField("动作", max_length=16, choices=ApprovalAction.choices)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    actor_name = models.CharField("操作人快照", max_length=64, blank=True, default="")
    comment = models.TextField("意见", blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "审批轨迹"
        verbose_name_plural = "审批轨迹"
        ordering = ["instance_id", "id"]

    def __str__(self) -> str:
        return f"{self.instance_id}-{self.action}"

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise RuntimeError("审批轨迹不可修改。")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise RuntimeError("审批轨迹不可删除。")


__all__ = [
    "ApprovalAction",
    "ApprovalInstance",
    "ApprovalLog",
    "ApprovalStep",
    "ApprovalTemplate",
    "ApprovalTemplateNode",
    "ApproverType",
    "InstanceStatus",
    "StepStatus",
    "TimeStampedModel",
]
