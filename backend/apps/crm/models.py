"""客户主数据（CRM）。

设计边界（任务书 10.2）：
* 本模块承载**客户档案与联系人**主数据，以及客户侧的两条流程单据：
  **客户投诉**（待受理 → 处理中 → 已解决 → 已关闭）与
  **产品评价**（待回复 → 已回复 → 已关闭）。流程单据与客户主数据分表存放，
  避免把「主数据」与「流程记录」糅在一张表里；
* 客户归属公司，按数据范围过滤（`company_field="company_id"`）；
* 联系人、地址等从属信息拆表，不塞进客户主表。

关于「一个客户只能有一个主联系人」：MySQL 不支持带条件的部分唯一索引
（`UniqueConstraint(condition=...)` 在 MySQL 上不被支持），因此该规则由
`apps/crm/services.py` 在事务内保证，并在测试中覆盖，而不是靠数据库约束。
"""

from __future__ import annotations

from decimal import Decimal

from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.core.models import BaseModel, CompanyScopedModel


class CustomerCategory(models.TextChoices):
    BRAND = "brand", "品牌客户"
    DISTRIBUTOR = "distributor", "经销商"
    AGENT = "agent", "代理商"
    DIRECT = "direct", "直客"
    ONLINE = "online", "电商"


class CustomerLevel(models.TextChoices):
    A = "A", "A 类（战略）"
    B = "B", "B 类（重点）"
    C = "C", "C 类（一般）"
    D = "D", "D 类（观察）"


class CustomerStatus(models.TextChoices):
    POTENTIAL = "potential", "潜在"
    ACTIVE = "active", "合作中"
    SUSPENDED = "suspended", "暂停合作"
    TERMINATED = "terminated", "已终止"


class Customer(CompanyScopedModel):
    """客户档案。"""

    code = models.CharField("客户编码", max_length=32)
    name = models.CharField("客户名称", max_length=128)
    short_name = models.CharField("客户简称", max_length=64, blank=True, default="")
    category = models.CharField(
        "客户分类", max_length=16, choices=CustomerCategory.choices, default=CustomerCategory.DIRECT
    )
    level = models.CharField(
        "客户等级", max_length=8, choices=CustomerLevel.choices, default=CustomerLevel.C
    )
    status = models.CharField(
        "合作状态",
        max_length=16,
        choices=CustomerStatus.choices,
        default=CustomerStatus.POTENTIAL,
        db_index=True,
    )
    credit_limit = models.DecimalField(
        "信用额度", max_digits=20, decimal_places=4, default=Decimal("0")
    )
    payment_terms = models.CharField("结算方式", max_length=64, blank=True, default="")
    tax_no = models.CharField("纳税人识别号", max_length=32, blank=True, default="")
    address = models.CharField("地址", max_length=255, blank=True, default="")
    primary_contact_name = models.CharField("主要联系人", max_length=64, blank=True, default="")
    primary_contact_phone = models.CharField("主要联系电话", max_length=32, blank=True, default="")
    salesman = models.ForeignKey(
        "factory.Employee",
        verbose_name="业务员",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
        db_index=True,
    )
    tags = models.JSONField("标签", default=list, blank=True)
    is_active = models.BooleanField("启用", default=True, db_index=True)
    remark = models.TextField("备注", blank=True, default="")

    class Meta:
        verbose_name = "客户"
        verbose_name_plural = "客户"
        ordering = ["code"]
        constraints = [
            models.UniqueConstraint(fields=["company", "code"], name="uq_customer_company_code"),
            models.CheckConstraint(
                condition=Q(credit_limit__gte=0),
                name="ck_customer_credit_limit_non_negative",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.code} {self.name}"


class CustomerContact(BaseModel):
    """客户联系人。公司归属通过 Customer 间接确定。"""

    customer = models.ForeignKey(
        Customer,
        verbose_name="客户",
        on_delete=models.CASCADE,
        related_name="contacts",
        db_index=True,
    )
    name = models.CharField("姓名", max_length=64)
    position = models.CharField("职务", max_length=64, blank=True, default="")
    phone = models.CharField("电话", max_length=32, blank=True, default="")
    email = models.CharField("邮箱", max_length=254, blank=True, default="")
    is_primary = models.BooleanField("主要联系人", default=False)
    is_active = models.BooleanField("启用", default=True, db_index=True)
    remark = models.TextField("备注", blank=True, default="")

    class Meta:
        verbose_name = "客户联系人"
        verbose_name_plural = "客户联系人"
        ordering = ["customer_id", "-is_primary", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["customer", "name"], name="uq_customer_contact_name"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.customer_id}-{self.name}"


class ComplaintType(models.TextChoices):
    """投诉类型。"""

    QUALITY = "quality", "产品质量"
    DELIVERY = "delivery", "交期延误"
    SERVICE = "service", "服务态度"
    PRICE = "price", "价格与结算"
    PACKAGING = "packaging", "包装与标识"
    OTHER = "other", "其他"


class ComplaintLevel(models.TextChoices):
    """投诉级别。"""

    GENERAL = "general", "一般"
    IMPORTANT = "important", "重要"
    SEVERE = "severe", "严重"


class ComplaintStatus(models.TextChoices):
    """投诉处理状态。状态只能由 `apps/crm/services.py` 推进。"""

    PENDING = "pending", "待受理"
    HANDLING = "handling", "处理中"
    RESOLVED = "resolved", "已解决"
    CLOSED = "closed", "已关闭"


class ComplaintSource(models.TextChoices):
    """投诉来源渠道。"""

    PHONE = "phone", "电话"
    EMAIL = "email", "邮件"
    VISIT = "visit", "来访"
    ONLINE = "online", "线上（微信/电商）"
    SALESMAN = "salesman", "业务员反馈"
    OTHER = "other", "其他"


class CustomerComplaint(CompanyScopedModel):
    """客户投诉：待受理 → 处理中 → 已解决 → 已关闭。

    编号留空时按编码规则（`CMPL`）自动取号；状态不允许直接 PATCH，
    只能由 `accept` / `resolve` / `close` 三个动作经服务层推进，
    跳步一律拒绝，避免出现「没处理就关闭」的静默销账。

    `satisfaction` 为 0 表示客户尚未评价：不自动填充、也不由处理人代填，
    避免把「没有回访」伪造成「客户满意」。
    """

    complaint_no = models.CharField("投诉编号", max_length=32)
    customer = models.ForeignKey(
        Customer,
        verbose_name="客户",
        on_delete=models.PROTECT,
        related_name="complaints",
        db_index=True,
    )
    complaint_type = models.CharField(
        "投诉类型",
        max_length=16,
        choices=ComplaintType.choices,
        default=ComplaintType.QUALITY,
        db_index=True,
    )
    level = models.CharField(
        "投诉级别", max_length=16, choices=ComplaintLevel.choices, default=ComplaintLevel.GENERAL
    )
    status = models.CharField(
        "处理状态",
        max_length=16,
        choices=ComplaintStatus.choices,
        default=ComplaintStatus.PENDING,
        db_index=True,
    )
    source = models.CharField(
        "投诉来源", max_length=16, choices=ComplaintSource.choices, default=ComplaintSource.PHONE
    )
    title = models.CharField("投诉主题", max_length=128)
    content = models.TextField("投诉内容")
    complained_at = models.DateTimeField("投诉时间", default=timezone.now, db_index=True)
    reporter = models.CharField("投诉人", max_length=64, blank=True, default="")
    reporter_phone = models.CharField("投诉人电话", max_length=32, blank=True, default="")
    related_no = models.CharField(
        "关联单据号",
        max_length=64,
        blank=True,
        default="",
        help_text="如销售订单号、发货单号；仅作追溯线索，不建立强外键",
    )
    receiver = models.ForeignKey(
        "factory.Employee",
        verbose_name="受理人",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    handler = models.ForeignKey(
        "factory.Employee",
        verbose_name="处理人",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    accepted_at = models.DateTimeField("受理时间", null=True, blank=True)
    resolved_at = models.DateTimeField("解决时间", null=True, blank=True)
    closed_at = models.DateTimeField("关闭时间", null=True, blank=True)
    handle_measure = models.TextField("处理措施", blank=True, default="")
    satisfaction = models.PositiveSmallIntegerField(
        "满意度评分", default=0, help_text="0 表示客户尚未评价；1~5 为回访评分"
    )
    remark = models.TextField("备注", blank=True, default="")

    class Meta:
        verbose_name = "客户投诉"
        verbose_name_plural = "客户投诉"
        ordering = ["-complained_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "complaint_no"], name="uq_customer_complaint_company_no"
            ),
            models.CheckConstraint(
                condition=Q(satisfaction__gte=0) & Q(satisfaction__lte=5),
                name="ck_customer_complaint_satisfaction_range",
            ),
        ]
        indexes = [models.Index(fields=["company", "status"], name="idx_complaint_status")]

    def __str__(self) -> str:
        return f"{self.complaint_no} {self.title}"


class ProductReviewStatus(models.TextChoices):
    """产品评价处理状态。状态只能由 `apps/crm/services.py` 推进。"""

    PENDING = "pending", "待回复"
    REPLIED = "replied", "已回复"
    CLOSED = "closed", "已关闭"


class ProductReview(CompanyScopedModel):
    """产品评价：客户对已交付产品（款式/SKU）的评分与反馈。

    与投诉的区别：投诉是**问题件**，必须走处理闭环；评价是**反馈件**，
    只需要「回复 → 关闭」。评分固定 1~5 分，由客户给出，不允许留空造分。
    """

    review_no = models.CharField("评价编号", max_length=32)
    customer = models.ForeignKey(
        Customer,
        verbose_name="客户",
        on_delete=models.PROTECT,
        related_name="product_reviews",
        db_index=True,
    )
    sku = models.ForeignKey(
        "masterdata.Sku",
        verbose_name="关联 SKU",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
        help_text="可选：评价到具体 SKU 时填写，否则只记录产品描述",
    )
    product_desc = models.CharField("产品/款式描述", max_length=128, blank=True, default="")
    score = models.PositiveSmallIntegerField("评分", help_text="1~5 分，由客户给出")
    status = models.CharField(
        "处理状态",
        max_length=16,
        choices=ProductReviewStatus.choices,
        default=ProductReviewStatus.PENDING,
        db_index=True,
    )
    reviewer_name = models.CharField("评价人", max_length=64, blank=True, default="")
    reviewed_at = models.DateField("评价日期", db_index=True)
    content = models.TextField("评价内容")
    reply = models.TextField("回复内容", blank=True, default="")
    replier = models.ForeignKey(
        "factory.Employee",
        verbose_name="回复人",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    replied_at = models.DateTimeField("回复时间", null=True, blank=True)
    closed_at = models.DateTimeField("关闭时间", null=True, blank=True)
    remark = models.TextField("备注", blank=True, default="")

    class Meta:
        verbose_name = "产品评价"
        verbose_name_plural = "产品评价"
        ordering = ["-reviewed_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "review_no"], name="uq_product_review_company_no"
            ),
            models.CheckConstraint(
                condition=Q(score__gte=1) & Q(score__lte=5),
                name="ck_product_review_score_range",
            ),
        ]
        indexes = [models.Index(fields=["company", "status"], name="idx_product_review_status")]

    def __str__(self) -> str:
        return f"{self.review_no} {self.customer_id}"
