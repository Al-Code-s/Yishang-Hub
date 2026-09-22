"""生产执行（MES）：生产工单、工单用料、工单工序与生产报工。

设计边界（AGENTS.md 一、三；任务书 10.7）：

* 本模块**只做生产执行**：工单下达、领料、报工、完工与完工入库。
  计划侧（MRP 运算与建议）仍在 ``apps/planning``，质量判定仍在 ``apps/qms``。
* **工单下达保存版本快照**：下达瞬间把生效的工艺路线与 BOM 冻结进
  ``routing_snapshot`` / ``bom_snapshot`` 并据此生成工序与用料行。之后工程数据
  出新版本不影响已下达工单（任务书 9.5「工单下达保存版本快照」、14.2 案例 13）。
* **库存只能经统一库存服务**：领料与完工入库都通过 ``apps.wms.services.stock``
  生成并过账库存单据，本模块不写库存余额与流水。
* 报工口径由服务层校验：单次报工「合格 + 返工 + 报废」必须等于报工数量，
  且同一工序累计报工不得超过工单计划数量。
* 质检点（``ProductionOrderStep.is_quality_gate``）工序报满时自动生成一张 QMS
  检验单；工单完工要求全部质检点检验单已判定为「合格」或「让步接收」。
* 状态只由 ``services`` 推进；不使用 signals 连锁创建单据。
"""

from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.core.constants import quantity_field
from apps.core.models import BaseModel, CompanyScopedModel


class ProductionOrderStatus(models.TextChoices):
    DRAFT = "draft", "草稿"
    RELEASED = "released", "已下达"
    IN_PROGRESS = "in_progress", "生产中"
    COMPLETED = "completed", "已完工"
    CLOSED = "closed", "已关闭"
    CANCELLED = "cancelled", "已取消"


class ProductionSourceType(models.TextChoices):
    MANUAL = "manual", "手工创建"
    SALES_ORDER = "sales_order", "销售订单"
    MRP_SUGGESTION = "mrp_suggestion", "MRP 生产建议"


class ProductionMaterialSource(models.TextChoices):
    BOM = "bom", "BOM 展开"
    MANUAL = "manual", "手工添加"


class ProductionStepStatus(models.TextChoices):
    PENDING = "pending", "待开工"
    IN_PROGRESS = "in_progress", "进行中"
    COMPLETED = "completed", "已完成"


class ProductionReportType(models.TextChoices):
    NORMAL = "normal", "正常报工"
    FIRST_ARTICLE = "first_article", "首件报工"
    REWORK = "rework", "返工报工"


class ProductionOrder(CompanyScopedModel):
    """生产工单：一次生产任务的抬头，承载计划数量、进度与工程数据快照。

    ``completed_quantity`` / ``qualified_quantity`` 取**末道工序**的合格累计数
    （同一件产品会经过多道工序，按工单汇总所有工序报工数会重复计数）；
    ``scrap_quantity`` 则是**全部工序报废之和**。
    """

    order_no = models.CharField("工单号", max_length=32)
    source_type = models.CharField(
        "来源类型",
        max_length=16,
        choices=ProductionSourceType.choices,
        default=ProductionSourceType.MANUAL,
        db_index=True,
    )
    source_no = models.CharField(
        "来源单据号", max_length=64, blank=True, default="", db_index=True
    )
    factory = models.ForeignKey(
        "factory.Factory",
        verbose_name="工厂",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
        db_index=True,
    )
    workshop = models.ForeignKey(
        "factory.Workshop",
        verbose_name="车间",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
        db_index=True,
    )
    production_line = models.ForeignKey(
        "factory.ProductionLine",
        verbose_name="线体",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    style = models.ForeignKey(
        "masterdata.Style",
        verbose_name="款式",
        on_delete=models.PROTECT,
        related_name="production_orders",
        db_index=True,
    )
    sku = models.ForeignKey(
        "masterdata.Sku",
        verbose_name="差异 SKU",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    product_material = models.ForeignKey(
        "masterdata.Material",
        verbose_name="产出物料",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
        help_text="完工入库与质检单使用的成品 / 半成品物料。",
    )
    quantity = quantity_field("计划数量", default=Decimal("0"))
    completed_quantity = quantity_field("完工数量", default=Decimal("0"), editable=False)
    qualified_quantity = quantity_field("合格数量", default=Decimal("0"), editable=False)
    scrap_quantity = quantity_field("报废数量", default=Decimal("0"), editable=False)
    unit = models.CharField("单位", max_length=16, blank=True, default="")
    status = models.CharField(
        "状态",
        max_length=16,
        choices=ProductionOrderStatus.choices,
        default=ProductionOrderStatus.DRAFT,
        db_index=True,
    )
    planned_start = models.DateTimeField("计划开工", null=True, blank=True)
    planned_end = models.DateTimeField("计划完工", null=True, blank=True)
    actual_start = models.DateTimeField("实际开工", null=True, blank=True)
    actual_end = models.DateTimeField("实际完工", null=True, blank=True)
    material_warehouse = models.ForeignKey(
        "wms.Warehouse",
        verbose_name="领料仓库",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    receipt_warehouse = models.ForeignKey(
        "wms.Warehouse",
        verbose_name="完工入库仓库",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    bom_snapshot = models.JSONField("BOM 快照", default=dict, blank=True)
    routing_snapshot = models.JSONField("工艺路线快照", default=dict, blank=True)
    owner = models.ForeignKey(
        "factory.Employee",
        verbose_name="责任人",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    released_at = models.DateTimeField("下达时间", null=True, blank=True)
    released_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="下达人",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    closed_at = models.DateTimeField("关闭时间", null=True, blank=True)
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="关闭人",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    cancel_reason = models.CharField("取消原因", max_length=255, blank=True, default="")
    issue_document = models.ForeignKey(
        "wms.InventoryDocument",
        verbose_name="领料出库单",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    receipt_document = models.ForeignKey(
        "wms.InventoryDocument",
        verbose_name="完工入库单",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    is_active = models.BooleanField("启用", default=True, db_index=True)
    remark = models.TextField("备注", blank=True, default="")

    class Meta:
        verbose_name = "生产工单"
        verbose_name_plural = "生产工单"
        ordering = ["-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "order_no"], name="uq_mes_order_company_no"
            ),
            models.CheckConstraint(
                condition=Q(quantity__gte=0), name="ck_mes_order_quantity_non_negative"
            ),
        ]
        indexes = [models.Index(fields=["status", "planned_end"], name="idx_mes_order_state")]

    def __str__(self) -> str:
        return self.order_no

    @property
    def progress_rate(self) -> Decimal:
        """完工进度（0~1）；计划数量为 0 时返回 0，避免除零。"""
        if not self.quantity:
            return Decimal("0")
        return (self.qualified_quantity or Decimal("0")) / self.quantity


class ProductionOrderMaterial(BaseModel):
    """工单用料：下达时按 BOM 快照展开，领料时按行过账。

    公司归属由工单确定（与设备零部件同一口径），因此不重复挂 ``company`` 字段。
    """

    order = models.ForeignKey(
        ProductionOrder,
        verbose_name="生产工单",
        on_delete=models.CASCADE,
        related_name="materials",
        db_index=True,
    )
    line_no = models.PositiveIntegerField("行号")
    material = models.ForeignKey(
        "masterdata.Material",
        verbose_name="物料",
        on_delete=models.PROTECT,
        related_name="+",
        db_index=True,
    )
    source = models.CharField(
        "用来源",
        max_length=16,
        choices=ProductionMaterialSource.choices,
        default=ProductionMaterialSource.BOM,
    )
    required_quantity = quantity_field("用量", default=Decimal("0"))
    issued_quantity = quantity_field("已领数量", default=Decimal("0"))
    unit = models.CharField("单位", max_length=16, blank=True, default="")
    location = models.ForeignKey(
        "wms.Location",
        verbose_name="默认领料储位",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    remark = models.CharField("备注", max_length=255, blank=True, default="")

    class Meta:
        verbose_name = "工单用料"
        verbose_name_plural = "工单用料"
        ordering = ["order_id", "line_no"]
        constraints = [
            models.UniqueConstraint(
                fields=["order", "line_no"], name="uq_mes_material_order_line"
            ),
            models.CheckConstraint(
                condition=Q(required_quantity__gt=0),
                name="ck_mes_material_required_positive",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.order_id}#{self.line_no}"


class ProductionOrderStep(BaseModel):
    """工单工序：下达时按工艺路线快照复制，报工按工序累计。

    ``is_quality_gate`` 为真表示该工序是质检点：工序报满时服务层会生成一张
    QMS 检验单（``inspection_order``），工单完工前该检验单必须已判定合格或让步接收。
    """

    order = models.ForeignKey(
        ProductionOrder,
        verbose_name="生产工单",
        on_delete=models.CASCADE,
        related_name="steps",
        db_index=True,
    )
    sequence = models.PositiveIntegerField("工序号")
    name = models.CharField("工序名称", max_length=128)
    workshop = models.ForeignKey(
        "factory.Workshop",
        verbose_name="车间",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    workcenter = models.CharField("工作中心", max_length=64, blank=True, default="")
    equipment_requirement = models.CharField(
        "设备要求", max_length=128, blank=True, default=""
    )
    standard_hours = quantity_field("单件标准工时（小时）", default=Decimal("0"))
    is_quality_gate = models.BooleanField("质检点", default=False)
    is_outsourced = models.BooleanField("委外工序", default=False)
    status = models.CharField(
        "状态",
        max_length=16,
        choices=ProductionStepStatus.choices,
        default=ProductionStepStatus.PENDING,
        db_index=True,
    )
    reported_quantity = quantity_field("累计报工", default=Decimal("0"))
    qualified_quantity = quantity_field("累计合格", default=Decimal("0"))
    scrap_quantity = quantity_field("累计报废", default=Decimal("0"))
    started_at = models.DateTimeField("开工时间", null=True, blank=True)
    finished_at = models.DateTimeField("完工时间", null=True, blank=True)
    inspection_order = models.ForeignKey(
        "qms.QualityInspectionOrder",
        verbose_name="质检单",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    remark = models.CharField("备注", max_length=255, blank=True, default="")

    class Meta:
        verbose_name = "工单工序"
        verbose_name_plural = "工单工序"
        ordering = ["order_id", "sequence"]
        constraints = [
            models.UniqueConstraint(
                fields=["order", "sequence"], name="uq_mes_step_order_sequence"
            ),
            models.CheckConstraint(
                condition=Q(standard_hours__gte=0), name="ck_mes_step_hours_non_negative"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.order_id}@{self.sequence}"


class ProductionReport(CompanyScopedModel):
    """生产报工：一次「谁在哪个工序上做了多少、其中多少合格」的记录。

    报工是**不可回改的原始记录**（不提供修改接口）：填错了就补一条返工报工，
    而不是把历史数字改掉。因此 ``report_no`` 在服务层取号、数量口径在服务层校验。
    """

    report_no = models.CharField("报工单号", max_length=32)
    order = models.ForeignKey(
        ProductionOrder,
        verbose_name="生产工单",
        on_delete=models.CASCADE,
        related_name="reports",
        db_index=True,
    )
    step = models.ForeignKey(
        ProductionOrderStep,
        verbose_name="工序",
        on_delete=models.CASCADE,
        related_name="reports",
        db_index=True,
    )
    report_type = models.CharField(
        "报工类型",
        max_length=16,
        choices=ProductionReportType.choices,
        default=ProductionReportType.NORMAL,
        db_index=True,
    )
    quantity = quantity_field("报工数量", default=Decimal("0"))
    qualified_quantity = quantity_field("合格数量", default=Decimal("0"))
    rework_quantity = quantity_field("返工数量", default=Decimal("0"))
    scrap_quantity = quantity_field("报废数量", default=Decimal("0"))
    operator = models.ForeignKey(
        "factory.Employee",
        verbose_name="报工人",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
        db_index=True,
    )
    equipment = models.ForeignKey(
        "equipment.Equipment",
        verbose_name="生产设备",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    work_hours = quantity_field("实际工时（小时）", default=Decimal("0"))
    started_at = models.DateTimeField("开工时间", null=True, blank=True)
    finished_at = models.DateTimeField("完工时间", null=True, blank=True)
    reported_at = models.DateTimeField("报工时间", null=True, blank=True, editable=False)
    reported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="报工来源账号",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    remark = models.CharField("备注", max_length=255, blank=True, default="")

    class Meta:
        verbose_name = "生产报工"
        verbose_name_plural = "生产报工"
        ordering = ["-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "report_no"], name="uq_mes_report_company_no"
            ),
            models.CheckConstraint(
                condition=Q(quantity__gt=0), name="ck_mes_report_quantity_positive"
            ),
        ]
        indexes = [models.Index(fields=["order_id", "step_id"], name="idx_mes_report_order")]

    def __str__(self) -> str:
        return self.report_no


__all__ = [
    "ProductionMaterialSource",
    "ProductionOrder",
    "ProductionOrderMaterial",
    "ProductionOrderStatus",
    "ProductionOrderStep",
    "ProductionReport",
    "ProductionReportType",
    "ProductionSourceType",
    "ProductionStepStatus",
]
