"""供应商主数据（SRM）。

设计边界（任务书 10.4）：
* 本模块承载**供应商档案、联系人、资质**与**五维量化评价（含权重配置）**；
  寻源、准入审批、报价仍属后续增量，审批复用 `workflow` 既有审批体系，不新建一套审批；
* 供应商归属公司，按数据范围过滤；
* 「停用供应商不能新建正常采购订单」是采购侧的校验规则，本模块只负责维护
  `is_active` 与 `admission_status`，采购模块在调用时校验（`procurement` 已落地）。

资质去重：`certificate_no` 可为空。若直接对 (supplier, type, certificate_no) 建联合唯一索引，
MySQL 允许多个 NULL 但不允许多个 ''，语义会变得混乱。因此使用**单列规范化去重键**
`dedup_key`：仅在填写了证书编号时生成（未填写时为 NULL，MySQL 允许重复 NULL），
键值统一 `casefold()`，不依赖数据库排序规则的大小写行为（任务书 5.1、5.4）。

五维评价的三条硬口径（`docs/assumptions.md` A-10~A-12，**刻意如此，不要放宽**）：

1. **权重总和必须为 100%**，由服务层在保存时校验；权重配置只增不改——
   需要调整就派生新版本，旧版本原样保留，历史评分沿用**评分时的权重快照**。
2. **必须保存评分依据**：每条明细保存原始观测值与计算过程（配置权重、有效权重、加权分），
   不允许只存一个最终分数。
3. **无数据不自动记零分**：某维度缺数据时按配置「标注缺失」或「重新分配有效权重」，
   两者都在评价单上留痕（`missing_dimensions` / `effective_weight_total`）。
"""

from __future__ import annotations

from django.db import models
from django.db.models import F, Q

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


class EvaluationDimension(models.TextChoices):
    """五维评价的维度（任务书 10.4）。"""

    QUALITY = "quality", "质量"
    TECHNOLOGY = "technology", "技术"
    RESPONSE = "response", "响应"
    DELIVERY = "delivery", "交付"
    COST = "cost", "成本"


class MissingDimensionPolicy(models.TextChoices):
    """缺数据维度的处理口径（`docs/assumptions.md` A-12）。

    两种策略都必须留痕，**不允许把「没有数据」当成「数据为零」**。
    """

    MARK_MISSING = "mark_missing", "标注缺失（不重分配权重）"
    REDISTRIBUTE = "redistribute", "重新分配有效权重"


class SupplierEvaluationStatus(models.TextChoices):
    DRAFT = "draft", "草稿"
    EFFECTIVE = "effective", "已生效"
    ARCHIVED = "archived", "已归档"


#: 维度 → 权重配置上的字段名（权重口径的唯一映射，服务层与序列化器共用）
DIMENSION_WEIGHT_FIELD: dict[str, str] = {
    EvaluationDimension.QUALITY: "quality_weight",
    EvaluationDimension.TECHNOLOGY: "technology_weight",
    EvaluationDimension.RESPONSE: "response_weight",
    EvaluationDimension.DELIVERY: "delivery_weight",
    EvaluationDimension.COST: "cost_weight",
}

#: 维度的稳定顺序，避免各处按不同的遍历顺序产出结果
EVALUATION_DIMENSIONS: tuple[str, ...] = tuple(EvaluationDimension.values)


def weight_field(*args, **kwargs):
    """权重 / 得分字段：0~100，保留 2 位小数（禁用 float，任务书 0.3）。"""
    kwargs.setdefault("max_digits", 5)
    kwargs.setdefault("decimal_places", 2)
    return models.DecimalField(*args, **kwargs)


class SupplierEvaluationWeight(CompanyScopedModel):
    """五维评价权重配置。

    **只增不改**：调整权重通过派生新版本实现，旧版本原样保留（A-10 的「留痕」）。
    同一公司下版本号唯一；同一时刻最多一条 ``is_active=True``，由服务层在事务内保证。
    """

    version_no = models.PositiveIntegerField("版本号", default=1)
    quality_weight = weight_field("质量权重(%)", default=0)
    technology_weight = weight_field("技术权重(%)", default=0)
    response_weight = weight_field("响应权重(%)", default=0)
    delivery_weight = weight_field("交付权重(%)", default=0)
    cost_weight = weight_field("成本权重(%)", default=0)
    is_active = models.BooleanField("启用", default=True, db_index=True)
    remark = models.TextField("备注", blank=True, default="")

    class Meta:
        verbose_name = "供应商评价权重"
        verbose_name_plural = "供应商评价权重"
        ordering = ["-version_no", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "version_no"], name="uq_srm_eval_weight_company_version"
            ),
            models.CheckConstraint(
                condition=(
                    Q(quality_weight__gte=0)
                    & Q(quality_weight__lte=100)
                    & Q(technology_weight__gte=0)
                    & Q(technology_weight__lte=100)
                    & Q(response_weight__gte=0)
                    & Q(response_weight__lte=100)
                    & Q(delivery_weight__gte=0)
                    & Q(delivery_weight__lte=100)
                    & Q(cost_weight__gte=0)
                    & Q(cost_weight__lte=100)
                ),
                name="ck_srm_eval_weight_range",
            ),
        ]

    @property
    def total_weight(self):
        return (
            self.quality_weight
            + self.technology_weight
            + self.response_weight
            + self.delivery_weight
            + self.cost_weight
        )

    def weights(self) -> dict[str, object]:
        """按维度返回权重，供快照与计算使用。"""
        return {dimension: getattr(self, field) for dimension, field in DIMENSION_WEIGHT_FIELD.items()}

    def __str__(self) -> str:
        return f"供应商评价权重 v{self.version_no}"


class SupplierEvaluation(CompanyScopedModel):
    """供应商五维量化评价单（草稿 → 已生效 → 已归档）。

    总分**只能由服务层按权重快照计算**：客户端传入的 ``total_score`` 一律忽略，
    不允许人工填报一个好看的分数（与 QMS 判定同口径）。
    """

    evaluation_no = models.CharField("评价单号", max_length=32)
    supplier = models.ForeignKey(
        Supplier,
        verbose_name="供应商",
        on_delete=models.PROTECT,
        related_name="evaluations",
        db_index=True,
    )
    weight_config = models.ForeignKey(
        SupplierEvaluationWeight,
        verbose_name="权重配置",
        on_delete=models.PROTECT,
        related_name="evaluations",
        db_index=True,
    )
    # 权重快照：评价发生时各维度的配置权重（JSON，键为维度英文键）
    weight_snapshot = models.JSONField("权重快照", default=dict, blank=True)
    missing_dimension_policy = models.CharField(
        "缺数据处理",
        max_length=16,
        choices=MissingDimensionPolicy.choices,
        default=MissingDimensionPolicy.MARK_MISSING,
    )
    period_start = models.DateField("评价期间起", null=True, blank=True)
    period_end = models.DateField("评价期间止", null=True, blank=True)
    evaluated_by = models.ForeignKey(
        "factory.Employee",
        verbose_name="评价人",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
        db_index=True,
    )
    evaluated_at = models.DateTimeField("评价时间", null=True, blank=True)
    status = models.CharField(
        "状态",
        max_length=16,
        choices=SupplierEvaluationStatus.choices,
        default=SupplierEvaluationStatus.DRAFT,
        db_index=True,
    )
    total_score = weight_field("加权总分", null=True, blank=True)
    effective_weight_total = weight_field("有效权重合计(%)", null=True, blank=True)
    grade = models.CharField("评价等级", max_length=4, blank=True, default="")
    missing_dimensions = models.JSONField("缺失维度", default=list, blank=True)
    remark = models.TextField("备注", blank=True, default="")
    is_active = models.BooleanField("启用", default=True, db_index=True)

    class Meta:
        verbose_name = "供应商评价"
        verbose_name_plural = "供应商评价"
        ordering = ["-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "evaluation_no"], name="uq_srm_eval_company_no"
            ),
            models.CheckConstraint(
                condition=Q(period_start__isnull=True)
                | Q(period_end__isnull=True)
                | Q(period_end__gte=F("period_start")),
                name="ck_srm_eval_period_order",
            ),
        ]

    @property
    def is_editable(self) -> bool:
        return self.status == SupplierEvaluationStatus.DRAFT

    def __str__(self) -> str:
        return f"{self.evaluation_no} {self.supplier_id}"


class SupplierEvaluationLine(BaseModel):
    """评价明细：一个维度一行，保存**原始观测值 + 计算过程**（A-11）。

    明细不单独挂公司：公司归属由父单 ``evaluation`` 决定，
    范围过滤一律经 ``evaluation__company_id``（与 QMS 检验结果同口径）。
    """

    evaluation = models.ForeignKey(
        SupplierEvaluation,
        verbose_name="评价单",
        on_delete=models.CASCADE,
        related_name="lines",
        db_index=True,
    )
    dimension = models.CharField("维度", max_length=16, choices=EvaluationDimension.choices)
    raw_score = models.DecimalField("原始得分", max_digits=5, decimal_places=2, null=True, blank=True)
    #: 原始观测值：如到货准时批次数、检验不合格批次数（可解释性的来源）
    raw_observation = models.JSONField("原始观测值", default=dict, blank=True)
    weight = models.DecimalField("配置权重(%)", max_digits=5, decimal_places=2, default=0)
    effective_weight = models.DecimalField("有效权重(%)", max_digits=5, decimal_places=2, default=0)
    weighted_score = models.DecimalField(
        "加权得分", max_digits=5, decimal_places=2, null=True, blank=True
    )
    is_missing = models.BooleanField("缺数据", default=False)
    remark = models.TextField("备注", blank=True, default="")

    class Meta:
        verbose_name = "供应商评价明细"
        verbose_name_plural = "供应商评价明细"
        ordering = ["evaluation_id", "dimension"]
        constraints = [
            models.UniqueConstraint(
                fields=["evaluation", "dimension"], name="uq_srm_eval_line_dimension"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.evaluation_id}-{self.dimension}"


__all__ = [
    "DIMENSION_WEIGHT_FIELD",
    "EVALUATION_DIMENSIONS",
    "AdmissionStatus",
    "EvaluationDimension",
    "MissingDimensionPolicy",
    "QualificationType",
    "Supplier",
    "SupplierCategory",
    "SupplierContact",
    "SupplierEvaluation",
    "SupplierEvaluationLine",
    "SupplierEvaluationStatus",
    "SupplierEvaluationWeight",
    "SupplierGrade",
    "SupplierQualification",
    "weight_field",
]
