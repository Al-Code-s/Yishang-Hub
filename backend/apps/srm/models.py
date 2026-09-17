"""供应商主数据（SRM）。

设计边界（任务书 10.4）：
* 本模块承载**供应商档案、联系人、资质**；寻源、准入审批、报价、评价属于阶段 2 后续增量，
  审批复用 `workflow` 既有审批体系，不新建一套审批；
* 供应商归属公司，按数据范围过滤；
* 「停用供应商不能新建正常采购订单」是采购侧的校验规则，本模块只负责维护
  `is_active` 与 `admission_status`，采购模块在阶段 2 后续调用时校验。

资质去重：`certificate_no` 可为空。若直接对 (supplier, type, certificate_no) 建联合唯一索引，
MySQL 允许多个 NULL 但不允许多个 ''，语义会变得混乱。因此使用**单列规范化去重键**
`dedup_key`：仅在填写了证书编号时生成（未填写时为 NULL，MySQL 允许重复 NULL），
键值统一 `casefold()`，不依赖数据库排序规则的大小写行为（任务书 5.1、5.4）。
"""

from __future__ import annotations

from django.db import models
from django.db.models import Q

from apps.core.models import BaseModel, CompanyScopedModel


class SupplierCategory(models.TextChoices):
    FABRIC = "fabric", "面料"
    ACCESSORY = "accessory", "辅料"
    PACKAGING = "packaging", "包装物"
    EQUIPMENT = "equipment", "设备"
    SPARE_PART = "spare_part", "备品备件"
    SERVICE = "service", "服务"
    OTHER = "other", "其他"


class SupplierGrade(models.TextChoices):
    A = "A", "A 级（优先）"
    B = "B", "B 级（合格）"
    C = "C", "C 级（限用）"
    D = "D", "D 级（观察）"


class AdmissionStatus(models.TextChoices):
    PENDING = "pending", "待准入"
    ADMITTED = "admitted", "已准入"
    REJECTED = "rejected", "未通过"
    SUSPENDED = "suspended", "暂停合作"
    TERMINATED = "terminated", "已终止"


class QualificationType(models.TextChoices):
    BUSINESS_LICENSE = "business_license", "营业执照"
    QUALITY_SYSTEM = "quality_system", "质量体系认证"
    ENVIRONMENTAL = "environmental", "环保资质"
    TEST_REPORT = "test_report", "检测报告"
    SOCIAL_COMPLIANCE = "social_compliance", "社会责任审核"
    OTHER = "other", "其他"


class Supplier(CompanyScopedModel):
    """供应商档案。"""

    code = models.CharField("供应商编码", max_length=32)
    name = models.CharField("供应商名称", max_length=128)
    short_name = models.CharField("供应商简称", max_length=64, blank=True, default="")
    category = models.CharField(
        "供应类别",
        max_length=16,
        choices=SupplierCategory.choices,
        default=SupplierCategory.FABRIC,
        db_index=True,
    )
    grade = models.CharField(
        "供应商等级", max_length=4, choices=SupplierGrade.choices, default=SupplierGrade.C
    )
    admission_status = models.CharField(
        "准入状态",
        max_length=16,
        choices=AdmissionStatus.choices,
        default=AdmissionStatus.PENDING,
        db_index=True,
    )
    payment_terms = models.CharField("结算方式", max_length=64, blank=True, default="")
    tax_no = models.CharField("纳税人识别号", max_length=32, blank=True, default="")
    address = models.CharField("地址", max_length=255, blank=True, default="")
    primary_contact_name = models.CharField("主要联系人", max_length=64, blank=True, default="")
    primary_contact_phone = models.CharField("主要联系电话", max_length=32, blank=True, default="")
    buyer = models.ForeignKey(
        "factory.Employee",
        verbose_name="采购员",
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
        verbose_name = "供应商"
        verbose_name_plural = "供应商"
        ordering = ["code"]
        constraints = [
            models.UniqueConstraint(fields=["company", "code"], name="uq_supplier_company_code"),
        ]

    def __str__(self) -> str:
        return f"{self.code} {self.name}"


class SupplierContact(BaseModel):
    """供应商联系人。"""

    supplier = models.ForeignKey(
        Supplier,
        verbose_name="供应商",
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
        verbose_name = "供应商联系人"
        verbose_name_plural = "供应商联系人"
        ordering = ["supplier_id", "-is_primary", "id"]
        constraints = [
            models.UniqueConstraint(fields=["supplier", "name"], name="uq_supplier_contact_name"),
        ]

    def __str__(self) -> str:
        return f"{self.supplier_id}-{self.name}"


class SupplierQualification(BaseModel):
    """供应商资质证书及其有效期（任务书 10.4 的「到期提醒」依据）。"""

    supplier = models.ForeignKey(
        Supplier,
        verbose_name="供应商",
        on_delete=models.CASCADE,
        related_name="qualifications",
        db_index=True,
    )
    qualification_type = models.CharField(
        "资质类型", max_length=32, choices=QualificationType.choices, db_index=True
    )
    certificate_no = models.CharField("证书编号", max_length=64, blank=True, default="")
    issued_by = models.CharField("发证机构", max_length=128, blank=True, default="")
    issued_date = models.DateField("发证日期", null=True, blank=True)
    expiry_date = models.DateField("到期日期", null=True, blank=True, db_index=True)
    is_active = models.BooleanField("启用", default=True, db_index=True)
    remark = models.TextField("备注", blank=True, default="")
    # 规范化去重键：仅当填写了证书编号时非空，未填写时为 NULL（MySQL 允许多个 NULL）
    dedup_key = models.CharField(
        "去重键", max_length=191, unique=True, null=True, blank=True, editable=False
    )

    class Meta:
        verbose_name = "供应商资质"
        verbose_name_plural = "供应商资质"
        ordering = ["supplier_id", "qualification_type", "id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(issued_date__isnull=True)
                | Q(expiry_date__isnull=True)
                | Q(expiry_date__gte=models.F("issued_date")),
                name="ck_supplier_qualification_date_order",
            ),
        ]

    def build_dedup_key(self) -> str | None:
        certificate_no = (self.certificate_no or "").strip().casefold()
        if not certificate_no:
            return None
        return f"{self.supplier_id}|{self.qualification_type}|{certificate_no}"[:191]

    def save(self, *args, **kwargs):
        self.dedup_key = self.build_dedup_key()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.supplier_id}-{self.qualification_type}"
