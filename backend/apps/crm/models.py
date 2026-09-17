"""客户主数据（CRM）。

设计边界（任务书 10.2）：
* 本模块当前只承载**客户档案与联系人**主数据，不做服务工单、投诉、满意度；
  那些属于阶段 6，避免把「主数据」与「服务流程」糅在一张表里；
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
