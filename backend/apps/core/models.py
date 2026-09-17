"""公共基础模型：审计字段、审计日志、Outbox、幂等、编码规则、字典、附件、通知。"""

from __future__ import annotations

import uuid
from pathlib import Path

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.logging import get_current_user


class TimeStampedModel(models.Model):
    """仅含时间戳的抽象模型，用于系统写入型实体。"""

    created_at = models.DateTimeField("创建时间", auto_now_add=True, db_index=True, editable=False)
    updated_at = models.DateTimeField("更新时间", auto_now=True, editable=False)

    class Meta:
        abstract = True


class BaseModel(TimeStampedModel):
    """业务实体通用字段：时间戳 + 操作人 + 版本号。

    组织归属字段（company/factory/department/warehouse）不在此处强制，
    由各实体按真实归属选择 CompanyScopedModel 或单独声明，避免机械堆字段。
    """

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="创建人",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
        editable=False,
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="更新人",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
        editable=False,
    )
    version = models.PositiveIntegerField("版本号", default=0, editable=False)

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        user = get_current_user()
        if user is not None:
            if self._state.adding and self.created_by_id is None:
                self.created_by = user
            self.updated_by = user
        if not self._state.adding:
            self.version = (self.version or 0) + 1
        super().save(*args, **kwargs)


class CompanyScopedModel(BaseModel):
    """归属到具体公司的业务实体。"""

    company = models.ForeignKey(
        "factory.Company",
        verbose_name="所属公司",
        on_delete=models.PROTECT,
        related_name="+",
    )

    class Meta:
        abstract = True


class AuditAction(models.TextChoices):
    LOGIN = "login", "登录"
    LOGIN_FAILED = "login_failed", "登录失败"
    LOGOUT = "logout", "退出登录"
    CREATE = "create", "新增"
    UPDATE = "update", "修改"
    DELETE = "delete", "删除"
    ACTIVATE = "activate", "启用"
    DEACTIVATE = "deactivate", "停用"
    SUBMIT = "submit", "提交"
    APPROVE = "approve", "审批通过"
    REJECT = "reject", "审批驳回"
    WITHDRAW = "withdraw", "撤回"
    EXPORT = "export", "导出"
    UPLOAD = "upload", "上传"
    DOWNLOAD = "download", "下载"
    IMPORT = "import", "导入"
    POST = "post", "过账"
    REVERSE = "reverse", "冲销"


class AuditLog(models.Model):
    """关键操作审计。与业务操作同事务写入，且一经写入不可修改/删除。

    审计中不保存完整密码、令牌等敏感原文。
    """

    id = models.BigAutoField(primary_key=True)
    request_id = models.CharField("请求标识", max_length=64, blank=True, default="", db_index=True)
    action = models.CharField("操作类型", max_length=32, choices=AuditAction.choices, db_index=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="操作人",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audit_logs",
    )
    actor_username = models.CharField("操作人账号快照", max_length=64, blank=True, default="")
    actor_name = models.CharField("操作人姓名快照", max_length=64, blank=True, default="")
    company = models.ForeignKey(
        "factory.Company",
        verbose_name="所属公司",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    object_type = models.CharField("对象类型", max_length=128, blank=True, default="", db_index=True)
    object_id = models.CharField("对象主键", max_length=64, blank=True, default="", db_index=True)
    object_repr = models.CharField("对象描述", max_length=255, blank=True, default="")
    changes = models.JSONField("关键字段变更摘要", default=dict, blank=True)
    reason = models.TextField("原因", blank=True, default="")
    approval_basis = models.CharField("审批依据", max_length=255, blank=True, default="")
    ip_address = models.GenericIPAddressField("来源 IP", null=True, blank=True)
    user_agent = models.CharField("客户端", max_length=255, blank=True, default="")
    created_at = models.DateTimeField("操作时间", auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "审计日志"
        verbose_name_plural = "审计日志"
        ordering = ["-id"]
        indexes = [
            models.Index(fields=["object_type", "object_id"], name="idx_audit_object"),
            models.Index(fields=["actor", "-created_at"], name="idx_audit_actor_time"),
            models.Index(fields=["action", "-created_at"], name="idx_audit_action_time"),
        ]

    def __str__(self) -> str:
        return f"{self.created_at:%Y-%m-%d %H:%M:%S} {self.actor_username} {self.action}"

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise RuntimeError("审计日志不可修改。")
        # 显式禁止通过 save() 覆盖主键，保证只追加写入
        kwargs.pop("force_update", None)
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise RuntimeError("审计日志不可删除。")


class OutboxStatus(models.TextChoices):
    PENDING = "pending", "待处理"
    PROCESSING = "processing", "处理中"
    DONE = "done", "已完成"
    FAILED = "failed", "待重试"
    DEAD = "dead", "需人工处理"


class OutboxEvent(models.Model):
    """事务性发件箱：事件与业务数据同事务写入，后台轮询至少一次投递。

    消费者必须幂等；通过 dedup_key 支持生产端去重。
    """

    id = models.BigAutoField(primary_key=True)
    event_id = models.UUIDField("事件标识", default=uuid.uuid4, unique=True, editable=False)
    event_type = models.CharField("事件类型", max_length=128, db_index=True)
    aggregate_type = models.CharField("聚合类型", max_length=128)
    aggregate_id = models.CharField("聚合主键", max_length=64)
    payload = models.JSONField("事件内容", default=dict, blank=True)
    status = models.CharField(
        "状态", max_length=16, choices=OutboxStatus.choices, default=OutboxStatus.PENDING, db_index=True
    )
    attempts = models.PositiveIntegerField("已尝试次数", default=0)
    max_attempts = models.PositiveIntegerField("最大尝试次数", default=5)
    next_retry_at = models.DateTimeField("下次重试时间", null=True, blank=True, db_index=True)
    last_error = models.TextField("最近错误", blank=True, default="")
    dedup_key = models.CharField("去重键", max_length=191, null=True, blank=True, unique=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True, db_index=True)
    processed_at = models.DateTimeField("处理完成时间", null=True, blank=True)

    class Meta:
        verbose_name = "发件箱事件"
        verbose_name_plural = "发件箱事件"
        ordering = ["id"]
        indexes = [models.Index(fields=["status", "next_retry_at"], name="idx_outbox_status_retry")]

    def __str__(self) -> str:
        return f"{self.event_type}#{self.aggregate_id}"


class IdempotencyRecord(models.Model):
    """幂等记录：同一标识重复调用不产生重复业务结果。"""

    id = models.BigAutoField(primary_key=True)
    scope = models.CharField("幂等范围", max_length=128)
    key = models.CharField("幂等标识", max_length=128)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    request_hash = models.CharField("请求内容摘要", max_length=64)
    status_code = models.PositiveSmallIntegerField("响应状态码", null=True, blank=True)
    response_body = models.JSONField("响应内容", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    expires_at = models.DateTimeField("过期时间", db_index=True)

    class Meta:
        verbose_name = "幂等记录"
        verbose_name_plural = "幂等记录"
        constraints = [
            models.UniqueConstraint(fields=["scope", "key"], name="uq_idempotency_scope_key"),
        ]

    def __str__(self) -> str:
        return f"{self.scope}:{self.key}"


class ResetPeriod(models.TextChoices):
    NEVER = "never", "不重置"
    DAILY = "daily", "每日"
    MONTHLY = "monthly", "每月"
    YEARLY = "yearly", "每年"


class CodeRule(BaseModel):
    """编码规则。pattern 支持 {YYYY}{MM}{DD}{SEQ:n} 占位符。"""

    code = models.CharField("规则编码", max_length=64, unique=True)
    name = models.CharField("规则名称", max_length=128)
    pattern = models.CharField("编号格式", max_length=128, help_text="例：SO{YYYYMMDD}{SEQ:4}")
    reset_period = models.CharField(
        "重置周期", max_length=16, choices=ResetPeriod.choices, default=ResetPeriod.NEVER
    )
    is_active = models.BooleanField("启用", default=True)
    remark = models.TextField("备注", blank=True, default="")

    class Meta:
        verbose_name = "编码规则"
        verbose_name_plural = "编码规则"
        ordering = ["code"]

    def __str__(self) -> str:
        return f"{self.code} ({self.pattern})"


class CodeSequence(models.Model):
    """编码流水。以 (规则, 周期键) 唯一约束保证并发下不重号。"""

    id = models.BigAutoField(primary_key=True)
    rule = models.ForeignKey(CodeRule, on_delete=models.CASCADE, related_name="sequences")
    period_key = models.CharField("周期键", max_length=16)
    last_value = models.PositiveIntegerField("当前流水值", default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "编码流水"
        verbose_name_plural = "编码流水"
        constraints = [
            models.UniqueConstraint(fields=["rule", "period_key"], name="uq_code_sequence_rule_period"),
        ]

    def __str__(self) -> str:
        return f"{self.rule_id}:{self.period_key}={self.last_value}"


class Dictionary(BaseModel):
    """数据字典。"""

    code = models.CharField("字典编码", max_length=64, unique=True)
    name = models.CharField("字典名称", max_length=128)
    is_system = models.BooleanField("系统内置", default=False)
    is_active = models.BooleanField("启用", default=True, db_index=True)
    remark = models.TextField("备注", blank=True, default="")

    class Meta:
        verbose_name = "数据字典"
        verbose_name_plural = "数据字典"
        ordering = ["code"]

    def __str__(self) -> str:
        return f"{self.code} {self.name}"


class DictionaryItem(BaseModel):
    """字典明细项。"""

    dictionary = models.ForeignKey(Dictionary, on_delete=models.CASCADE, related_name="items")
    code = models.CharField("项编码", max_length=64)
    label = models.CharField("项名称", max_length=128)
    sort_order = models.IntegerField("排序", default=0)
    is_active = models.BooleanField("启用", default=True)
    extra = models.JSONField("扩展属性", default=dict, blank=True)

    class Meta:
        verbose_name = "字典明细"
        verbose_name_plural = "字典明细"
        ordering = ["dictionary_id", "sort_order", "id"]
        constraints = [
            models.UniqueConstraint(fields=["dictionary", "code"], name="uq_dictionary_item_code"),
        ]

    def __str__(self) -> str:
        return f"{self.dictionary.code}.{self.code}"


def attachment_upload_to(instance: Attachment, filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    now = timezone.now()
    return f"attachments/{now:%Y/%m}/{uuid.uuid4().hex}{suffix}"


class Attachment(BaseModel):
    """业务附件。默认私有，下载必须经过权限校验，不能依靠猜测地址访问。"""

    file = models.FileField("文件", upload_to=attachment_upload_to, max_length=255)
    original_name = models.CharField("原始文件名", max_length=255)
    content_type = models.CharField("内容类型", max_length=128, blank=True, default="")
    size_bytes = models.PositiveBigIntegerField("文件大小", default=0)
    sha256 = models.CharField("内容摘要", max_length=64, blank=True, default="", db_index=True)
    biz_type = models.CharField("业务类型", max_length=128, blank=True, default="", db_index=True)
    biz_id = models.CharField("业务主键", max_length=64, blank=True, default="", db_index=True)

    class Meta:
        verbose_name = "附件"
        verbose_name_plural = "附件"
        ordering = ["-id"]
        indexes = [models.Index(fields=["biz_type", "biz_id"], name="idx_attachment_biz")]

    def __str__(self) -> str:
        return self.original_name


class Notification(TimeStampedModel):
    """站内通知 / 待办。由 Outbox 消费者创建，source_event_id 保证重放幂等。"""

    id = models.BigAutoField(primary_key=True)
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications"
    )
    title = models.CharField("标题", max_length=200)
    body = models.TextField("内容", blank=True, default="")
    biz_type = models.CharField("业务类型", max_length=128, blank=True, default="")
    biz_id = models.CharField("业务主键", max_length=64, blank=True, default="")
    is_read = models.BooleanField("已读", default=False, db_index=True)
    read_at = models.DateTimeField("读取时间", null=True, blank=True)
    source_event_id = models.UUIDField("来源事件", null=True, blank=True, unique=True)

    class Meta:
        verbose_name = "通知"
        verbose_name_plural = "通知"
        ordering = ["-id"]
        indexes = [models.Index(fields=["recipient", "is_read"], name="idx_notification_recipient")]

    def __str__(self) -> str:
        return self.title
