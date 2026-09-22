"""质量管理（QMS）：检验项目、检验单与检验结果、质量报警、质量问题知识库。

设计边界（AGENTS.md 一、三）：

* 本模块**不替代**采购的来料检验放行（``procurement.receipt.inspect``）与仓储的质量放行
  （``wms``），也不改动它们已有的流程。检验单通过 ``source_no`` 引用来源单据，
  属于**并行的质量记录与判定**能力；两个已有流程要接线时由业务方显式发起，
  不做跨模块隐式副作用。
* **检验结果判断在服务层完成**：定量项目按上下限自动判合格，定性项目由检验员给出判定；
  只要存在不合格项，整单就不能被判为「合格」——粉饰结果与跳步都被拒绝。
* 判定为不合格时自动生成一条**质量报警**（本模块自己的台账，不复用能源报警台账），
  报警有独立闭环（待处理 → 处理中 → 已关闭）；不合格报警未关闭时检验单不能关闭。
* **产品质量问题知识库**记录问题现象、原因分析与纠正 / 预防措施，可反向引用产生它的
  检验单或质量报警，让「这一次为什么不合格」沉淀成「下次怎么避免」。
"""

from __future__ import annotations

from decimal import Decimal

from django.db import models
from django.db.models import F, Q

from apps.core.constants import quantity_field, reading_field
from apps.core.models import BaseModel, CompanyScopedModel


class InspectionCategory(models.TextChoices):
    APPEARANCE = "appearance", "外观"
    SIZE = "size", "尺寸"
    PHYSICAL = "physical", "理化性能"
    FUNCTION = "function", "功能"
    PACKAGE = "package", "包装"
    OTHER = "other", "其他"


class InspectionValueType(models.TextChoices):
    QUANTITATIVE = "quantitative", "定量（按上下限自动判定）"
    QUALITATIVE = "qualitative", "定性（目视 / 描述判定）"


class QualityInspectionType(models.TextChoices):
    IQC = "iqc", "来料检验"
    IPQC = "ipqc", "过程检验"
    FQC = "fqc", "成品检验"
    OQC = "oqc", "出货检验"
    FIRST_ARTICLE = "first_article", "首件检验"
    OTHER = "other", "其他"


class QualityInspectionStatus(models.TextChoices):
    DRAFT = "draft", "草稿"
    SUBMITTED = "submitted", "已提交"
    JUDGED = "judged", "已判定"
    CLOSED = "closed", "已关闭"


class QualityJudgement(models.TextChoices):
    PENDING = "pending", "待判定"
    PASSED = "passed", "合格"
    FAILED = "failed", "不合格"
    CONCESSION = "concession", "让步接收"


class QualityAlertLevel(models.TextChoices):
    MINOR = "minor", "轻微"
    MAJOR = "major", "严重"
    CRITICAL = "critical", "致命"


class QualityAlertStatus(models.TextChoices):
    OPEN = "open", "待处理"
    HANDLING = "handling", "处理中"
    CLOSED = "closed", "已关闭"


class QualityIssueCategory(models.TextChoices):
    MATERIAL = "material", "原材料"
    CRAFT = "craft", "工艺"
    EQUIPMENT = "equipment", "设备"
    DESIGN = "design", "设计"
    OPERATION = "operation", "操作"
    STORAGE = "storage", "储运"
    OTHER = "other", "其他"


class QualityIssueStatus(models.TextChoices):
    DRAFT = "draft", "草稿"
    PUBLISHED = "published", "已发布"
    ARCHIVED = "archived", "已归档"


class QualityInspectionItem(CompanyScopedModel):
    """检验项目：检验单明细的判定依据（判定口径的唯一来源）。

    定量项目的``lower_limit`` / ``upper_limit`` 是**包含端点**的；两者都留空表示该项目
    没有数值口径，必须按定性项目登记，避免出现「有上下限字段却不用」的模糊数据。
    """

    code = models.CharField("项目编码", max_length=32)
    name = models.CharField("项目名称", max_length=128)
    category = models.CharField(
        "项目类别",
        max_length=16,
        choices=InspectionCategory.choices,
        default=InspectionCategory.APPEARANCE,
        db_index=True,
    )
    value_type = models.CharField(
        "判定方式",
        max_length=16,
        choices=InspectionValueType.choices,
        default=InspectionValueType.QUANTITATIVE,
    )
    unit = models.CharField("单位", max_length=16, blank=True, default="")
    method = models.CharField("检验方法与工具", max_length=255, blank=True, default="")
    standard_text = models.CharField("标准要求", max_length=255, blank=True, default="")
    lower_limit = reading_field("标准下限", null=True, blank=True)
    upper_limit = reading_field("标准上限", null=True, blank=True)
    is_active = models.BooleanField("启用", default=True, db_index=True)
    remark = models.TextField("备注", blank=True, default="")

    class Meta:
        verbose_name = "检验项目"
        verbose_name_plural = "检验项目"
        ordering = ["code"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "code"], name="uq_qms_item_company_code"
            ),
            models.CheckConstraint(
                condition=(
                    Q(lower_limit__isnull=True)
                    | Q(upper_limit__isnull=True)
                    | Q(lower_limit__lte=F("upper_limit"))
                ),
                name="ck_qms_item_limit_order",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.code} {self.name}"


class QualityInspectionOrder(CompanyScopedModel):
    """检验单：一次检验的抬头（谁在什么时候检验了什么、结论是什么）。"""

    order_no = models.CharField("检验单号", max_length=32)
    inspection_type = models.CharField(
        "检验类型",
        max_length=16,
        choices=QualityInspectionType.choices,
        default=QualityInspectionType.IQC,
        db_index=True,
    )
    status = models.CharField(
        "单据状态",
        max_length=16,
        choices=QualityInspectionStatus.choices,
        default=QualityInspectionStatus.DRAFT,
        db_index=True,
    )
    judgement = models.CharField(
        "判定结论",
        max_length=16,
        choices=QualityJudgement.choices,
        default=QualityJudgement.PENDING,
        db_index=True,
    )
    source_no = models.CharField(
        "来源单据号", max_length=64, blank=True, default="", help_text="如采购收货单号、生产工单号"
    )
    material = models.ForeignKey(
        "masterdata.Material",
        verbose_name="受检物料",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
        db_index=True,
    )
    product_desc = models.CharField("产品 / 物料描述", max_length=255, blank=True, default="")
    batch_no = models.CharField("批次号", max_length=64, blank=True, default="", db_index=True)
    supplier = models.ForeignKey(
        "srm.Supplier",
        verbose_name="供应商",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
        db_index=True,
    )
    workshop = models.ForeignKey(
        "factory.Workshop",
        verbose_name="受检车间",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    production_line = models.ForeignKey(
        "factory.ProductionLine",
        verbose_name="受检线体",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    equipment = models.ForeignKey(
        "equipment.Equipment",
        verbose_name="受检设备",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    quantity = quantity_field("受检数量", default=Decimal("0"))
    sample_quantity = quantity_field("抽样数量", default=Decimal("0"))
    unit = models.CharField("单位", max_length=16, blank=True, default="")
    inspector = models.ForeignKey(
        "factory.Employee",
        verbose_name="检验员",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
        db_index=True,
    )
    inspected_at = models.DateTimeField("检验时间", null=True, blank=True)
    judge_remark = models.TextField("判定说明", blank=True, default="")
    judged_at = models.DateTimeField("判定时间", null=True, blank=True, editable=False)
    is_active = models.BooleanField("启用", default=True, db_index=True)
    remark = models.TextField("备注", blank=True, default="")

    class Meta:
        verbose_name = "检验单"
        verbose_name_plural = "检验单"
        ordering = ["-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "order_no"], name="uq_qms_order_company_no"
            ),
            models.CheckConstraint(
                condition=Q(quantity__gte=0), name="ck_qms_order_quantity_non_negative"
            ),
            models.CheckConstraint(
                condition=Q(sample_quantity__gte=0),
                name="ck_qms_order_sample_non_negative",
            ),
        ]
        indexes = [models.Index(fields=["status", "judgement"], name="idx_qms_order_state")]

    def __str__(self) -> str:
        return self.order_no


class QualityInspectionResult(BaseModel):
    """检验结果明细：一条「项目 + 实测值 + 是否合格」。

    公司归属通过检验单确定（与设备零部件同一口径），因此不重复挂 ``company`` 字段。
    ``is_qualified`` 由服务层按项目口径计算，**不接受客户端直接指定定量项的结论**。
    """

    order = models.ForeignKey(
        QualityInspectionOrder,
        verbose_name="检验单",
        on_delete=models.CASCADE,
        related_name="results",
        db_index=True,
    )
    item = models.ForeignKey(
        QualityInspectionItem,
        verbose_name="检验项目",
        on_delete=models.PROTECT,
        related_name="+",
        db_index=True,
    )
    measured_value = reading_field("实测值", null=True, blank=True)
    text_value = models.CharField("实测描述", max_length=255, blank=True, default="")
    is_qualified = models.BooleanField("是否合格", default=True)
    remark = models.CharField("备注", max_length=255, blank=True, default="")
    sort_order = models.PositiveIntegerField("排序", default=0)

    class Meta:
        verbose_name = "检验结果"
        verbose_name_plural = "检验结果"
        ordering = ["sort_order", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["order", "item"], name="uq_qms_result_order_item"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.order.order_no}/{self.item.code}"


class QualityAlert(CompanyScopedModel):
    """质量报警：检验判定不合格时自动生成，处理闭环独立于检验单。"""

    alert_no = models.CharField("报警编号", max_length=32)
    order = models.ForeignKey(
        QualityInspectionOrder,
        verbose_name="来源检验单",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="alerts",
        db_index=True,
    )
    level = models.CharField(
        "报警级别",
        max_length=16,
        choices=QualityAlertLevel.choices,
        default=QualityAlertLevel.MAJOR,
        db_index=True,
    )
    status = models.CharField(
        "处理状态",
        max_length=16,
        choices=QualityAlertStatus.choices,
        default=QualityAlertStatus.OPEN,
        db_index=True,
    )
    title = models.CharField("报警主题", max_length=255)
    description = models.TextField("报警说明", blank=True, default="")
    material = models.ForeignKey(
        "masterdata.Material",
        verbose_name="物料",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    batch_no = models.CharField("批次号", max_length=64, blank=True, default="")
    handler = models.ForeignKey(
        "factory.Employee",
        verbose_name="处理人",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    handled_at = models.DateTimeField("开始处理时间", null=True, blank=True)
    close_remark = models.TextField("关闭说明", blank=True, default="")
    closed_at = models.DateTimeField("关闭时间", null=True, blank=True)

    class Meta:
        verbose_name = "质量报警"
        verbose_name_plural = "质量报警"
        ordering = ["-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "alert_no"], name="uq_qms_alert_company_no"
            ),
        ]
        indexes = [models.Index(fields=["status", "level"], name="idx_qms_alert_state")]

    def __str__(self) -> str:
        return self.alert_no


class QualityIssue(CompanyScopedModel):
    """产品质量问题知识库：把「这一次为什么不合格」沉淀下来。"""

    issue_no = models.CharField("问题编号", max_length=32)
    title = models.CharField("问题标题", max_length=255)
    category = models.CharField(
        "问题分类",
        max_length=16,
        choices=QualityIssueCategory.choices,
        default=QualityIssueCategory.MATERIAL,
        db_index=True,
    )
    severity = models.CharField(
        "严重程度",
        max_length=16,
        choices=QualityAlertLevel.choices,
        default=QualityAlertLevel.MAJOR,
    )
    phenomenon = models.TextField("问题现象")
    cause = models.TextField("原因分析", blank=True, default="")
    corrective_action = models.TextField("纠正措施", blank=True, default="")
    preventive_action = models.TextField("预防措施", blank=True, default="")
    material = models.ForeignKey(
        "masterdata.Material",
        verbose_name="关联物料",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    product_desc = models.CharField("产品 / 物料描述", max_length=255, blank=True, default="")
    tags = models.JSONField("标签", default=list, blank=True)
    source_order = models.ForeignKey(
        QualityInspectionOrder,
        verbose_name="来源检验单",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    source_alert = models.ForeignKey(
        QualityAlert,
        verbose_name="来源质量报警",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    status = models.CharField(
        "状态",
        max_length=16,
        choices=QualityIssueStatus.choices,
        default=QualityIssueStatus.DRAFT,
        db_index=True,
    )
    published_at = models.DateTimeField("发布时间", null=True, blank=True, editable=False)
    is_active = models.BooleanField("启用", default=True, db_index=True)
    remark = models.TextField("备注", blank=True, default="")

    class Meta:
        verbose_name = "质量问题知识库"
        verbose_name_plural = "质量问题知识库"
        ordering = ["-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "issue_no"], name="uq_qms_issue_company_no"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.issue_no} {self.title}"


__all__ = [
    "InspectionCategory",
    "InspectionValueType",
    "QualityAlert",
    "QualityAlertLevel",
    "QualityAlertStatus",
    "QualityInspectionItem",
    "QualityInspectionOrder",
    "QualityInspectionResult",
    "QualityInspectionStatus",
    "QualityInspectionType",
    "QualityIssue",
    "QualityIssueCategory",
    "QualityIssueStatus",
    "QualityJudgement",
]
