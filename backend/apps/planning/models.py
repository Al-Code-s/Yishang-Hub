"""计划模块：BOM（物料清单）与工艺路线，版本化工程数据。

阶段 3 第一步。设计边界（任务书 9.5、10.6、17）：

* BOM / 工艺路线是**版本化工程数据**：草稿可改；提交后冻结；审核通过后生效。
  需要变更时**新建版本**，不覆盖已审核版本，保证已下达工单引用的版本内容不变
  （任务书 9.5「工单下达保存版本快照」、14.2 必测案例 13）。
* 「款式 + SKU 范围」在同一时间只允许一个生效版本：由服务层在事务内用
  ``select_for_update`` 保证。MySQL 没有部分唯一索引，因此不靠索引兜底。
* ``scope_key`` 是**规范化唯一键**：MySQL 的联合唯一索引不约束 NULL
  （多行 NULL 互不冲突），所以不能直接对 (company, style, sku, version_no)
  建唯一索引——这与 ``wms.InventoryBalance.dimension_key`` 是同一个坑。
* 快照：``services.build_bom_snapshot()`` / ``build_routing_snapshot()`` 输出不可变结构，
  由 MES 工单下达时保存。工单在阶段 3 后续增量实现，本模块**不建空的快照表**。
* 不使用 signals；版本与状态迁移只由 services 修改。
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.db import models
from django.db.models import F, Q

from apps.core.constants import quantity_field, rate_field
from apps.core.models import BaseModel, CompanyScopedModel


class BomStatus(models.TextChoices):
    DRAFT = "draft", "草稿"
    SUBMITTED = "submitted", "审核中"
    APPROVED = "approved", "已审核"
    REJECTED = "rejected", "已驳回"
    OBSOLETE = "obsolete", "已作废"


class RoutingStatus(models.TextChoices):
    DRAFT = "draft", "草稿"
    SUBMITTED = "submitted", "审核中"
    APPROVED = "approved", "已审核"
    REJECTED = "rejected", "已驳回"
    OBSOLETE = "obsolete", "已作废"


class BomLineType(models.TextChoices):
    NORMAL = "normal", "正常用料"
    SUBSTITUTE = "substitute", "替代料"


def engineering_scope_key(style_id: int, sku_id: int | None) -> str:
    """规范化「款式 / SKU 范围」键。

    ``sku_id`` 为空表示款式通用版本；MySQL 唯一索引对 NULL 不去重，
    因此把范围压成一个非空字符串再进唯一索引。
    """
    if sku_id is None:
        return f"style:{style_id}"
    return f"style:{style_id}:sku:{sku_id}"


DEFAULT_ROUTING_STEPS: tuple[tuple[str, bool], ...] = (
    ("裁剪", False),
    ("缝制", False),
    ("整烫", False),
    ("检验", True),
    ("包装", False),
)

class ScopeLabelMixin:
    """「款式 / SKU 范围」展示标签。BOM 与工艺路线共用同一口径。"""

    @property
    def scope_label(self) -> str:
        return "款式通用" if self.sku_id is None else f"SKU {self.sku_id}"



class Bom(ScopeLabelMixin, CompanyScopedModel):
    """物料清单（BOM）版本。

    一个「款式 + SKU 范围」可以有多个版本，但**同一时间只允许一个已审核版本生效**；
    审核新版本时旧版本自动转 `obsolete`（见 ``services.approve_bom``）。
    """

    code = models.CharField("BOM 编号", max_length=64)
    style = models.ForeignKey(
        "masterdata.Style", verbose_name="款式", on_delete=models.PROTECT, related_name="boms"
    )
    sku = models.ForeignKey(
        "masterdata.Sku",
        verbose_name="差异 SKU",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="boms",
        help_text="为空表示款式通用 BOM；填写表示该 SKU 的差异用料版本。",
    )
    version_no = models.PositiveIntegerField("版本号", default=1)
    scope_key = models.CharField("范围键", max_length=96, editable=False, db_index=True)
    status = models.CharField(
        "状态", max_length=16, choices=BomStatus.choices, default=BomStatus.DRAFT, db_index=True
    )
    effective_from = models.DateField("生效日期", null=True, blank=True)
    effective_to = models.DateField("失效日期", null=True, blank=True)
    is_active = models.BooleanField("启用", default=True, db_index=True)

    approval_instance = models.ForeignKey(
        "workflow.ApprovalInstance",
        verbose_name="审批实例",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    submitted_at = models.DateTimeField("提交时间", null=True, blank=True)
    approved_at = models.DateTimeField("审核时间", null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="审核人",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    remark = models.TextField("备注", blank=True, default="")

    class Meta:
        verbose_name = "物料清单"
        verbose_name_plural = "物料清单"
        ordering = ["company_id", "style_id", "version_no"]
        constraints = [
            models.UniqueConstraint(fields=["company", "code"], name="uq_bom_company_code"),
            models.UniqueConstraint(
                fields=["company", "scope_key", "version_no"], name="uq_bom_scope_version"
            ),
            models.CheckConstraint(condition=Q(version_no__gte=1), name="ck_bom_version_positive"),
            models.CheckConstraint(
                condition=Q(effective_to__isnull=True)
                | Q(effective_from__isnull=True)
                | Q(effective_to__gte=F("effective_from")),
                name="ck_bom_effective_range",
            ),
        ]

    def save(self, *args, **kwargs):
        self.scope_key = engineering_scope_key(self.style_id, self.sku_id)
        super().save(*args, **kwargs)

    @property
    def is_editable(self) -> bool:
        """只有草稿版本可以修改明细。已提交/已审核/已作废一律冻结。"""
        return self.status == BomStatus.DRAFT and self.is_active

    def __str__(self) -> str:
        return f"{self.code} v{self.version_no}"

class BomLine(BaseModel):
    """BOM 明细。

    ``quantity`` 是**单位成品净用量**（生产 1 个成品所需量），
    ``gross_quantity`` = 净用量 ×(1+损耗率)，由后端计算，前端传入会被忽略。
    """

    bom = models.ForeignKey(Bom, on_delete=models.CASCADE, related_name="lines")
    line_no = models.PositiveIntegerField("行号")
    material = models.ForeignKey(
        "masterdata.Material",
        verbose_name="用料",
        on_delete=models.PROTECT,
        related_name="+",
        db_index=True,
    )
    quantity = quantity_field("标准用量")
    loss_rate = rate_field("损耗率", default=0, help_text="0.05 表示 5%")
    uom = models.ForeignKey(
        "masterdata.UoM",
        verbose_name="单位",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    line_type = models.CharField(
        "行类型", max_length=16, choices=BomLineType.choices, default=BomLineType.NORMAL
    )
    substitute_for = models.ForeignKey(
        "self",
        verbose_name="替代的用料行",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="substitutes",
        help_text="仅替代料行使用；必须指向同一 BOM 内的正常用料行。",
    )
    position = models.CharField("使用部位", max_length=64, blank=True, default="")
    is_key_material = models.BooleanField("关键用料", default=False)
    remark = models.CharField("备注", max_length=255, blank=True, default="")

    class Meta:
        verbose_name = "BOM 明细"
        verbose_name_plural = "BOM 明细"
        ordering = ["bom_id", "line_no"]
        constraints = [
            models.UniqueConstraint(fields=["bom", "line_no"], name="uq_bom_line_no"),
            models.CheckConstraint(
                condition=Q(quantity__gt=0), name="ck_bom_line_quantity_positive"
            ),
            models.CheckConstraint(
                condition=Q(loss_rate__gte=0), name="ck_bom_line_loss_non_negative"
            ),
            models.CheckConstraint(
                condition=Q(loss_rate__lt=1), name="ck_bom_line_loss_lt_one"
            ),
        ]

    @property
    def gross_quantity(self) -> Decimal:
        """含损耗用量 = 净用量 × (1 + 损耗率)。

        舍入规则：统一按数量精度 6 位小数 ``ROUND_HALF_UP`` 舍入，
        且**只在这一处**舍入，保证接口输出与快照口径一致（任务书 5.3）。
        全程使用 Decimal，禁止 float。
        """
        raw = self.quantity * (Decimal("1") + self.loss_rate)
        return raw.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)

    def __str__(self) -> str:
        return f"{self.bom_id}-{self.line_no}"

class Routing(ScopeLabelMixin, CompanyScopedModel):
    """工艺路线版本。版本与审核规则与 BOM 完全一致。"""

    code = models.CharField("工艺编号", max_length=64)
    style = models.ForeignKey(
        "masterdata.Style", verbose_name="款式", on_delete=models.PROTECT, related_name="routings"
    )
    sku = models.ForeignKey(
        "masterdata.Sku",
        verbose_name="差异 SKU",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="routings",
    )
    version_no = models.PositiveIntegerField("版本号", default=1)
    scope_key = models.CharField("范围键", max_length=96, editable=False, db_index=True)
    status = models.CharField(
        "状态", max_length=16, choices=RoutingStatus.choices, default=RoutingStatus.DRAFT, db_index=True
    )
    effective_from = models.DateField("生效日期", null=True, blank=True)
    effective_to = models.DateField("失效日期", null=True, blank=True)
    is_active = models.BooleanField("启用", default=True, db_index=True)

    approval_instance = models.ForeignKey(
        "workflow.ApprovalInstance",
        verbose_name="审批实例",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    submitted_at = models.DateTimeField("提交时间", null=True, blank=True)
    approved_at = models.DateTimeField("审核时间", null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="审核人",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    remark = models.TextField("备注", blank=True, default="")

    class Meta:
        verbose_name = "工艺路线"
        verbose_name_plural = "工艺路线"
        ordering = ["company_id", "style_id", "version_no"]
        constraints = [
            models.UniqueConstraint(fields=["company", "code"], name="uq_routing_company_code"),
            models.UniqueConstraint(
                fields=["company", "scope_key", "version_no"], name="uq_routing_scope_version"
            ),
            models.CheckConstraint(
                condition=Q(version_no__gte=1), name="ck_routing_version_positive"
            ),
        ]

    def save(self, *args, **kwargs):
        self.scope_key = engineering_scope_key(self.style_id, self.sku_id)
        super().save(*args, **kwargs)

    @property
    def is_editable(self) -> bool:
        return self.status == RoutingStatus.DRAFT and self.is_active

    def __str__(self) -> str:
        return f"{self.code} v{self.version_no}"

class RoutingStep(BaseModel):
    """工序。

    ``is_quality_gate`` 是任务书 9.5 的「工序质检点」：MES 在该工序必须产生检验记录。
    ``standard_hours`` 是该工序单件标准工时（小时），用于 OEE 理论产能与工序效率。
    """

    routing = models.ForeignKey(Routing, on_delete=models.CASCADE, related_name="steps")
    sequence = models.PositiveIntegerField("工序顺序")
    name = models.CharField("工序名称", max_length=64)
    workshop = models.ForeignKey(
        "factory.Workshop",
        verbose_name="车间",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    workcenter = models.CharField("工作中心/线体", max_length=64, blank=True, default="")
    equipment_requirement = models.CharField("设备要求", max_length=128, blank=True, default="")
    standard_hours = quantity_field("标准工时（小时）", default=0)
    is_quality_gate = models.BooleanField("工序质检点", default=False)
    is_outsourced = models.BooleanField("外协工序", default=False)
    remark = models.CharField("备注", max_length=255, blank=True, default="")

    class Meta:
        verbose_name = "工序"
        verbose_name_plural = "工序"
        ordering = ["routing_id", "sequence"]
        constraints = [
            models.UniqueConstraint(fields=["routing", "sequence"], name="uq_routing_step_sequence"),
            models.CheckConstraint(
                condition=Q(sequence__gte=1), name="ck_routing_step_sequence_positive"
            ),
            models.CheckConstraint(
                condition=Q(standard_hours__gte=0), name="ck_routing_step_hours_non_negative"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.sequence}.{self.name}"


# ---------------------------------------------------------------------------
# MRP（阶段 3 第二步，任务书 10.6）
#
# 口径约定（与 docs/progress.md 第十五节、docs/business-flows.md §12.1 一致）：
#
# * 需求来源首版只有「已批准 / 部分发货的销售订单行未发货量」；
#   子件需求由**父件净需求**展开（不是父件毛需求），因此不会对已有库存重复展开。
# * 供给只认「合格库存可用量」「采购在途」，在制供给（MES）未实现，当前恒为 0。
# * 逐批净算（lot-for-lot）：首版**不建模提前期与批量规则**，建议交期 = 需求所在时间分段。
# * 每次重算生成**新的运行记录**，不覆盖历史运行与已转单建议。
# ---------------------------------------------------------------------------


class MrpRunStatus(models.TextChoices):
    COMPLETED = "completed", "已完成"
    ARCHIVED = "archived", "已归档"
    FAILED = "failed", "计算失败"


class MrpBucket(models.TextChoices):
    DAY = "day", "按日"
    WEEK = "week", "按周"


class MrpDemandSource(models.TextChoices):
    SALES_ORDER = "sales_order", "销售订单"
    PARENT_ITEM = "parent_item", "上层净需求展开"


class MrpSupplySource(models.TextChoices):
    ON_HAND = "on_hand", "现有可用库存"
    ON_ORDER = "on_order", "采购在途"
    IN_PROGRESS = "in_progress", "在制供给"


class MrpSuggestionType(models.TextChoices):
    PURCHASE = "purchase", "采购建议"
    PRODUCTION = "production", "生产建议"


class MrpSuggestionStatus(models.TextChoices):
    OPEN = "open", "待处理"
    CONVERTED = "converted", "已转单"
    CANCELLED = "cancelled", "已取消"


def mrp_bucket_date(day: date, bucket: str) -> date:
    """把日期归入时间分段：按周取该周周一（ISO），按日取当天。"""
    if bucket == MrpBucket.WEEK:
        return day - timedelta(days=day.weekday())
    return day


class MrpRun(CompanyScopedModel):
    """一次 MRP 计算（计算快照）。

    「重算不自动覆盖已执行采购单/工单」（任务书 10.6）的实现方式：
    重算是**新增一条运行记录**，历史运行的明细与建议保持原样，且已转单的建议不会被新运行改写。
    `parameters` / `summary` 保存本次口径与结果计数，保证结果可解释、可复核。
    """

    run_no = models.CharField("运行编号", max_length=64)
    status = models.CharField(
        "状态",
        max_length=16,
        choices=MrpRunStatus.choices,
        default=MrpRunStatus.COMPLETED,
        db_index=True,
    )
    bucket = models.CharField(
        "时间分段", max_length=8, choices=MrpBucket.choices, default=MrpBucket.DAY
    )
    horizon_start = models.DateField("需求区间起")
    horizon_end = models.DateField("需求区间止")
    warehouse = models.ForeignKey(
        "wms.Warehouse",
        verbose_name="限定仓库",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
        help_text="为空表示按公司全部仓库汇总可用量。",
    )
    parameters = models.JSONField("计算口径", default=dict, blank=True)
    summary = models.JSONField("结果摘要", default=dict, blank=True)
    started_at = models.DateTimeField("开始时间", null=True, blank=True)
    finished_at = models.DateTimeField("结束时间", null=True, blank=True)
    error_message = models.CharField("失败原因", max_length=255, blank=True, default="")
    archived_at = models.DateTimeField("归档时间", null=True, blank=True)
    archived_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="归档人",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    remark = models.TextField("备注", blank=True, default="")

    class Meta:
        verbose_name = "MRP 运行"
        verbose_name_plural = "MRP 运行"
        ordering = ["-id"]
        constraints = [
            models.UniqueConstraint(fields=["company", "run_no"], name="uq_mrp_run_company_no"),
            models.CheckConstraint(
                condition=Q(horizon_end__gte=F("horizon_start")), name="ck_mrp_horizon_ordered"
            ),
        ]

    def __str__(self) -> str:
        return self.run_no

class MrpDemandLine(BaseModel):
    """展开后的需求行（毛需求）。

    `quantity` 为**本行需求量**；`level=0` 表示顶层需求（销售订单），
    `level>=1` 表示由父件净需求展开得到的子件需求。
    `path` 记录需求来源链（如 `SO-DEMO-0001#1 > YS-W-2401 > FAB-001`），
    `source_id` / `source_no` 指向直接来源（销售订单或上层物料），用于「供需追溯」（任务书 10.6）。
    不做自关联外键：需求是**逐层展开的快照**，来源链已由 `path` 与来源字段表达，
    自关联会带来「父行是聚合行还是明细行」的歧义。
    """

    run = models.ForeignKey(MrpRun, on_delete=models.CASCADE, related_name="demands")
    line_no = models.PositiveIntegerField("行号")
    level = models.PositiveIntegerField("BOM 层级", default=0)
    source_type = models.CharField(
        "需求来源", max_length=16, choices=MrpDemandSource.choices, default=MrpDemandSource.SALES_ORDER
    )
    source_id = models.CharField("来源单据主键", max_length=64, blank=True, default="")
    source_no = models.CharField("来源单据编号", max_length=64, blank=True, default="")
    source_line_no = models.PositiveIntegerField("来源行号", null=True, blank=True)
    material = models.ForeignKey(
        "masterdata.Material",
        verbose_name="需求物料",
        on_delete=models.PROTECT,
        related_name="+",
        db_index=True,
    )
    sku = models.ForeignKey(
        "masterdata.Sku",
        verbose_name="需求 SKU",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    style = models.ForeignKey(
        "masterdata.Style",
        verbose_name="款式",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    warehouse = models.ForeignKey(
        "wms.Warehouse",
        verbose_name="需求仓库",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    quantity = quantity_field("需求量")
    due_date = models.DateField("需求日期", null=True, blank=True)
    bucket_date = models.DateField("需求分段", db_index=True)
    path = models.CharField("需求路径", max_length=255, blank=True, default="")
    exploded = models.BooleanField("已展开下级 BOM", default=False)
    note = models.CharField("说明", max_length=255, blank=True, default="")

    class Meta:
        verbose_name = "MRP 需求行"
        verbose_name_plural = "MRP 需求行"
        ordering = ["run_id", "line_no"]
        constraints = [
            models.UniqueConstraint(fields=["run", "line_no"], name="uq_mrp_demand_line_no"),
            models.CheckConstraint(
                condition=Q(quantity__gt=0), name="ck_mrp_demand_quantity_positive"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.run_id}#{self.line_no}"


class MrpSupplyLine(BaseModel):
    """供给行快照（现有可用库存 / 采购在途 / 在制供给）。

    「已占用库存不得再作为其他需求的自由供给」（任务书 10.6）：
    现有库存行的数量取 `on_hand - frozen - reserved`，冻结与占用**不计入**可用供给。
    """

    run = models.ForeignKey(MrpRun, on_delete=models.CASCADE, related_name="supplies")
    line_no = models.PositiveIntegerField("行号")
    source_type = models.CharField(
        "供给来源", max_length=16, choices=MrpSupplySource.choices
    )
    material = models.ForeignKey(
        "masterdata.Material",
        verbose_name="供给物料",
        on_delete=models.PROTECT,
        related_name="+",
        db_index=True,
    )
    warehouse = models.ForeignKey(
        "wms.Warehouse",
        verbose_name="仓库",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    quantity = quantity_field("供给量")
    available_date = models.DateField("可用日期")
    bucket_date = models.DateField("供给分段")
    reference_type = models.CharField("来源单据类型", max_length=64, blank=True, default="")
    reference_id = models.CharField("来源单据主键", max_length=64, blank=True, default="")
    reference_no = models.CharField("来源单据编号", max_length=64, blank=True, default="")
    remark = models.CharField("备注", max_length=255, blank=True, default="")

    class Meta:
        verbose_name = "MRP 供给行"
        verbose_name_plural = "MRP 供给行"
        ordering = ["run_id", "line_no"]
        constraints = [
            models.UniqueConstraint(fields=["run", "line_no"], name="uq_mrp_supply_line_no"),
            models.CheckConstraint(
                condition=Q(quantity__gt=0), name="ck_mrp_supply_quantity_positive"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.run_id}#{self.line_no}"

class MrpSuggestion(BaseModel):
    """MRP 建议（缺料清单的落地形式）。

    * 采购建议：物料不可自制（无生效 BOM 且分类不是成品/半成品）时的净短缺；
    * 生产建议：物料可自制（有生效 BOM，或分类为成品/半成品）时的净短缺。
    * `detail` 保存该分段的净算过程（期初可用、累计供给、累计需求、本段净需求），
      使建议可解释、可复核（任务书 10.6「可解释排程」）。
    * 转单是**一次性**动作：转单后 `status=converted` 并记录目标单据，
      重复转单会被拒绝（任务书 10.6「同一建议不得重复转单」）。
    """

    run = models.ForeignKey(MrpRun, on_delete=models.CASCADE, related_name="suggestions")
    line_no = models.PositiveIntegerField("行号")
    suggestion_type = models.CharField(
        "建议类型", max_length=16, choices=MrpSuggestionType.choices, db_index=True
    )
    status = models.CharField(
        "状态",
        max_length=16,
        choices=MrpSuggestionStatus.choices,
        default=MrpSuggestionStatus.OPEN,
        db_index=True,
    )
    material = models.ForeignKey(
        "masterdata.Material",
        verbose_name="建议物料",
        on_delete=models.PROTECT,
        related_name="+",
        db_index=True,
    )
    sku = models.ForeignKey(
        "masterdata.Sku",
        verbose_name="建议 SKU",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    style = models.ForeignKey(
        "masterdata.Style",
        verbose_name="款式",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    warehouse = models.ForeignKey(
        "wms.Warehouse",
        verbose_name="仓库",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    quantity = quantity_field("建议数量")
    uom = models.ForeignKey(
        "masterdata.UoM",
        verbose_name="单位",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    due_date = models.DateField("建议交期", null=True, blank=True)
    bucket_date = models.DateField("需求分段", db_index=True)
    reason = models.CharField("建议依据", max_length=255, blank=True, default="")
    detail = models.JSONField("净算过程", default=dict, blank=True)
    converted_document_type = models.CharField("目标单据类型", max_length=64, blank=True, default="")
    converted_document_id = models.CharField("目标单据主键", max_length=64, blank=True, default="")
    converted_document_no = models.CharField("目标单据编号", max_length=64, blank=True, default="")
    converted_at = models.DateTimeField("转单时间", null=True, blank=True)
    converted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="转单人",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    cancel_reason = models.CharField("取消原因", max_length=255, blank=True, default="")
    remark = models.TextField("备注", blank=True, default="")

    class Meta:
        verbose_name = "MRP 建议"
        verbose_name_plural = "MRP 建议"
        ordering = ["run_id", "line_no"]
        constraints = [
            models.UniqueConstraint(fields=["run", "line_no"], name="uq_mrp_suggestion_line_no"),
            models.CheckConstraint(
                condition=Q(quantity__gt=0), name="ck_mrp_suggestion_quantity_positive"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.run_id}#{self.line_no}"

__all__ = [
    "DEFAULT_ROUTING_STEPS",
    "ScopeLabelMixin",
    "Bom",
    "BomLine",
    "BomLineType",
    "BomStatus",
    "MrpBucket",
    "MrpDemandLine",
    "MrpDemandSource",
    "MrpRun",
    "MrpRunStatus",
    "MrpSuggestion",
    "MrpSuggestionStatus",
    "MrpSuggestionType",
    "MrpSupplyLine",
    "MrpSupplySource",
    "Routing",
    "RoutingStatus",
    "RoutingStep",
    "engineering_scope_key",
    "mrp_bucket_date",
]
