"""设备与备件主数据（EAM/CMMS 基础信息，阶段 4 第一步）。

设计边界（任务书 10.5）：
* 本模块当前只承载**设备类型、设备台账、设备零部件、备品备件**四类主数据；
  保养、维修、点巡检、异常上报、数采监控属于阶段 4 后续增量，**不预建空表**，
  避免出现「有菜单、有表、没有流程」的伪功能；
* 设备与备件归属公司，按数据范围过滤（`company_field="company_id"`）；
* 备件通过 `material` 关联 `masterdata.Material`，**库存与采购复用统一库存服务与采购模块**，
  本模块不直接读写库存余额，也不自建一套库存；
* 「设备零部件」是挂在某台设备上的组成件/易损件（结构性质），
  「备品备件」是可采购、可库存的备件主数据（物料性质）——两者不是一张表；
* 设备状态（在用/闲置/维修中/停用/报废）当前只作**台账属性**维护；
  维修、点巡检带来的自动状态流转随对应增量接入，避免出现「有字段没有流程」。
"""

from __future__ import annotations

from decimal import Decimal

from django.db import models
from django.db.models import F, Q
from django.utils import timezone

from apps.core.constants import money_field, price_field, quantity_field
from apps.core.models import BaseModel, CompanyScopedModel


class EquipmentCategory(models.TextChoices):
    PRODUCTION = "production", "生产设备"
    UTILITY = "utility", "公用工程设备"
    INSPECTION = "inspection", "检测设备"
    LOGISTICS = "logistics", "物流设备"
    AUXILIARY = "auxiliary", "辅助设备"
    OTHER = "other", "其他"


class EquipmentStatus(models.TextChoices):
    IN_USE = "in_use", "在用"
    IDLE = "idle", "闲置"
    REPAIRING = "repairing", "维修中"
    STOPPED = "stopped", "停用"
    SCRAPPED = "scrapped", "已报废"


class PartType(models.TextChoices):
    WEAR = "wear", "易损件"
    STANDARD = "standard", "标准件"
    ELECTRIC = "electric", "电气件"
    MECHANICAL = "mechanical", "机械件"
    CONSUMABLE = "consumable", "耗材"
    OTHER = "other", "其他"


class EquipmentType(BaseModel):
    """设备类型：平台级共享参考数据，不按公司拆分。"""

    code = models.CharField("类型编码", max_length=32)
    name = models.CharField("类型名称", max_length=64)
    category = models.CharField(
        "设备分类",
        max_length=16,
        choices=EquipmentCategory.choices,
        default=EquipmentCategory.PRODUCTION,
        db_index=True,
    )
    is_special = models.BooleanField(
        "特种设备", default=False, help_text="锅炉、压力容器、起重机械等需定期检验的设备"
    )
    maintenance_cycle_days = models.PositiveIntegerField(
        "保养周期（天）", default=0, help_text="0 表示尚未设定周期；保养计划增量启用后按此排期"
    )
    remark = models.TextField("备注", blank=True, default="")
    is_active = models.BooleanField("启用", default=True, db_index=True)

    class Meta:
        verbose_name = "设备类型"
        verbose_name_plural = "设备类型"
        ordering = ["code"]
        constraints = [
            models.UniqueConstraint(fields=["code"], name="uq_equipment_type_code"),
        ]

    def __str__(self) -> str:
        return f"{self.code} {self.name}"


class Equipment(CompanyScopedModel):
    """设备台账：一台设备的完整基础信息。"""

    code = models.CharField("设备编号", max_length=32)
    name = models.CharField("设备名称", max_length=128)
    equipment_type = models.ForeignKey(
        EquipmentType,
        verbose_name="设备类型",
        on_delete=models.PROTECT,
        related_name="equipments",
        db_index=True,
    )
    status = models.CharField(
        "设备状态",
        max_length=16,
        choices=EquipmentStatus.choices,
        default=EquipmentStatus.IN_USE,
        db_index=True,
    )
    factory = models.ForeignKey(
        "factory.Factory",
        verbose_name="所属工厂",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
        db_index=True,
    )
    workshop = models.ForeignKey(
        "factory.Workshop",
        verbose_name="所属车间",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    production_line = models.ForeignKey(
        "factory.ProductionLine",
        verbose_name="所属线体",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    station = models.ForeignKey(
        "factory.Station",
        verbose_name="工位",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    location = models.CharField("安装位置", max_length=128, blank=True, default="")
    brand = models.CharField("品牌", max_length=64, blank=True, default="")
    model_no = models.CharField("规格型号", max_length=64, blank=True, default="")
    serial_no = models.CharField("出厂编号", max_length=64, blank=True, default="")
    supplier = models.ForeignKey(
        "srm.Supplier",
        verbose_name="供应商",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    purchase_date = models.DateField("采购日期", null=True, blank=True)
    start_date = models.DateField("启用日期", null=True, blank=True)
    original_value = money_field("资产原值", default=Decimal("0"))
    warranty_until = models.DateField("保修截止日期", null=True, blank=True)
    is_special = models.BooleanField("特种设备", default=False)
    owner_department = models.ForeignKey(
        "factory.Department",
        verbose_name="负责部门",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    owner_employee = models.ForeignKey(
        "factory.Employee",
        verbose_name="责任人",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    remark = models.TextField("备注", blank=True, default="")
    is_active = models.BooleanField("启用", default=True, db_index=True)

    class Meta:
        verbose_name = "设备台账"
        verbose_name_plural = "设备台账"
        ordering = ["code"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "code"], name="uq_equipment_company_code"
            ),
            models.CheckConstraint(
                condition=Q(original_value__gte=0),
                name="ck_equipment_original_value_non_negative",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.code} {self.name}"


class EquipmentPart(BaseModel):
    """设备零部件：挂在某台设备上的组成件 / 易损件。公司归属通过设备间接确定。"""

    equipment = models.ForeignKey(
        Equipment,
        verbose_name="设备",
        on_delete=models.CASCADE,
        related_name="parts",
        db_index=True,
    )
    name = models.CharField("零部件名称", max_length=64)
    part_type = models.CharField(
        "零件类别",
        max_length=16,
        choices=PartType.choices,
        default=PartType.WEAR,
        db_index=True,
    )
    spec = models.CharField("规格型号", max_length=64, blank=True, default="")
    quantity = quantity_field("数量", default=Decimal("1"))
    uom = models.ForeignKey(
        "masterdata.UoM",
        verbose_name="单位",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    position = models.CharField("安装位置", max_length=64, blank=True, default="")
    life_days = models.PositiveIntegerField(
        "参考寿命（天）", default=0, help_text="0 表示未设定寿命"
    )
    remark = models.TextField("备注", blank=True, default="")
    is_active = models.BooleanField("启用", default=True, db_index=True)

    class Meta:
        verbose_name = "设备零部件"
        verbose_name_plural = "设备零部件"
        ordering = ["equipment_id", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["equipment", "name"], name="uq_equipment_part_name"
            ),
            models.CheckConstraint(
                condition=Q(quantity__gte=0), name="ck_equipment_part_quantity_non_negative"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.equipment_id}-{self.name}"


class SparePart(CompanyScopedModel):
    """备品备件 / 配件主数据：可采购、可库存，库存走统一库存服务。"""

    code = models.CharField("备件编码", max_length=32)
    name = models.CharField("备件名称", max_length=128)
    part_type = models.CharField(
        "备件类别",
        max_length=16,
        choices=PartType.choices,
        default=PartType.WEAR,
        db_index=True,
    )
    spec = models.CharField("规格型号", max_length=64, blank=True, default="")
    material = models.ForeignKey(
        "masterdata.Material",
        verbose_name="对应物料",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
        help_text="关联后该备件的库存与采购复用统一库存服务与采购模块",
    )
    equipment_type = models.ForeignKey(
        EquipmentType,
        verbose_name="适用设备类型",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="spare_parts",
    )
    uom = models.ForeignKey(
        "masterdata.UoM",
        verbose_name="单位",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    safety_stock = quantity_field("安全库存", default=Decimal("0"))
    reference_price = price_field("参考单价", default=Decimal("0"))
    life_days = models.PositiveIntegerField(
        "参考寿命（天）", default=0, help_text="0 表示未设定寿命"
    )
    supplier = models.ForeignKey(
        "srm.Supplier",
        verbose_name="常用供应商",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    remark = models.TextField("备注", blank=True, default="")
    is_active = models.BooleanField("启用", default=True, db_index=True)

    class Meta:
        verbose_name = "备品备件"
        verbose_name_plural = "备品备件"
        ordering = ["code"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "code"], name="uq_spare_part_company_code"
            ),
            models.CheckConstraint(
                condition=Q(safety_stock__gte=0), name="ck_spare_part_safety_stock_non_negative"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.code} {self.name}"



# ---------------------------------------------------------------------------
# 设备保养、维修、点巡检、异常上报（阶段 4 第二步）
#
# 数据边界：
# * 「保养项目 / 点巡检项目 / 异常类型」是**技术标准类的共享参考数据**，
#   不按公司拆分（与 `EquipmentType` 一致），避免同一套国标在每家公司各维护一份；
# * 「计划 / 任务 / 记录」归属公司，按数据范围过滤；
# * 任务与记录不是同一张表：任务是**待执行的工作**（有状态流转），
#   记录是**已发生的事实**（写完即历史），两者各自有编号与权限；
# * 备件领用不直接扣库存，需变动库存时调用统一库存服务（`apps/wms/services`），
#   本模块只记录「领用了什么」的文字说明与费用。
# ---------------------------------------------------------------------------


class MaintenanceCategory(models.TextChoices):
    DAILY = "daily", "日常保养"
    LEVEL1 = "level1", "一级保养"
    LEVEL2 = "level2", "二级保养"
    PRECISION = "precision", "精密保养"
    OTHER = "other", "其他"


class TaskStatus(models.TextChoices):
    """保养 / 维修 / 点巡检任务共用的状态机。

    合法迁移：待执行 → 进行中 → 已完成；待执行 / 进行中 → 已取消。
    """

    PENDING = "pending", "待执行"
    IN_PROGRESS = "in_progress", "进行中"
    COMPLETED = "completed", "已完成"
    CANCELLED = "cancelled", "已取消"

    @classmethod
    def open_states(cls) -> tuple[str, ...]:
        return (cls.PENDING, cls.IN_PROGRESS)


class InspectionMethod(models.TextChoices):
    VISUAL = "visual", "目视"
    AUDIO = "audio", "听音"
    MEASURE = "measure", "测量"
    TRIAL = "trial", "试运行"
    OTHER = "other", "其他"


class InspectionTaskType(models.TextChoices):
    POINT = "point", "点检"
    PATROL = "patrol", "巡检"


class InspectionResult(models.TextChoices):
    NORMAL = "normal", "正常"
    ABNORMAL = "abnormal", "异常"


class FaultLevel(models.TextChoices):
    LOW = "low", "轻微"
    MEDIUM = "medium", "一般"
    HIGH = "high", "严重"
    CRITICAL = "critical", "紧急"


class FaultReportStatus(models.TextChoices):
    REPORTED = "reported", "待派工"
    ASSIGNED = "assigned", "已派工"
    REPAIRING = "repairing", "维修中"
    CLOSED = "closed", "已关闭"
    CANCELLED = "cancelled", "已取消"


class AbnormalSource(models.TextChoices):
    MANUAL = "manual", "人工上报"
    INSPECTION = "inspection", "点巡检发现"
    DEVICE = "device", "设备告警"


class AbnormalStatus(models.TextChoices):
    REPORTED = "reported", "待分派"
    ASSIGNED = "assigned", "已分派"
    HANDLING = "handling", "处理中"
    CLOSED = "closed", "已关闭"
    CANCELLED = "cancelled", "已取消"


class MaintenanceItem(BaseModel):
    """设备保养项目：说明「保养做什么、做到什么标准」。平台级共享参考数据。"""

    code = models.CharField("项目编码", max_length=32)
    name = models.CharField("项目名称", max_length=128)
    category = models.CharField(
        "保养类别",
        max_length=16,
        choices=MaintenanceCategory.choices,
        default=MaintenanceCategory.DAILY,
        db_index=True,
    )
    equipment_type = models.ForeignKey(
        EquipmentType,
        verbose_name="适用设备类型",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="maintenance_items",
        help_text="留空表示适用于所有设备类型",
    )
    cycle_days = models.PositiveIntegerField(
        "建议周期（天）", default=0, help_text="0 表示由保养计划按设备实际情况设定"
    )
    standard = models.TextField("保养内容与标准", blank=True, default="")
    is_active = models.BooleanField("启用", default=True, db_index=True)
    remark = models.TextField("备注", blank=True, default="")

    class Meta:
        verbose_name = "设备保养项目"
        verbose_name_plural = "设备保养项目"
        ordering = ["code"]
        constraints = [
            models.UniqueConstraint(fields=["code"], name="uq_maintenance_item_code"),
        ]

    def __str__(self) -> str:
        return f"{self.code} {self.name}"


class MaintenancePlan(CompanyScopedModel):
    """设备保养计划：按周期为某台设备排保养。

    计划本身**不直接产生记录**；到期时由「生成保养任务」动作按
    `next_date` 起逐周期生成任务（同一计划同一天只会有一条任务）。
    """

    plan_no = models.CharField("计划编号", max_length=32)
    name = models.CharField("计划名称", max_length=128)
    equipment = models.ForeignKey(
        Equipment,
        verbose_name="设备",
        on_delete=models.PROTECT,
        related_name="maintenance_plans",
        db_index=True,
    )
    cycle_days = models.PositiveIntegerField("保养周期（天）", default=30)
    start_date = models.DateField("开始日期")
    next_date = models.DateField("下次保养日期", db_index=True)
    items = models.ManyToManyField(
        MaintenanceItem, verbose_name="保养项目", blank=True, related_name="plans"
    )
    responsible_employee = models.ForeignKey(
        "factory.Employee",
        verbose_name="负责人",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    department = models.ForeignKey(
        "factory.Department",
        verbose_name="负责部门",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    is_active = models.BooleanField("启用", default=True, db_index=True)
    remark = models.TextField("备注", blank=True, default="")

    class Meta:
        verbose_name = "设备保养计划"
        verbose_name_plural = "设备保养计划"
        ordering = ["-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "plan_no"], name="uq_maintenance_plan_company_no"
            ),
            models.CheckConstraint(
                condition=Q(cycle_days__gt=0), name="ck_maintenance_plan_cycle_positive"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.plan_no} {self.name}"


class MaintenanceTask(CompanyScopedModel):
    """设备保养任务：真正要执行的保养工作。"""

    task_no = models.CharField("任务编号", max_length=32)
    plan = models.ForeignKey(
        MaintenancePlan,
        verbose_name="保养计划",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="tasks",
    )
    equipment = models.ForeignKey(
        Equipment,
        verbose_name="设备",
        on_delete=models.PROTECT,
        related_name="maintenance_tasks",
        db_index=True,
    )
    item = models.ForeignKey(
        MaintenanceItem,
        verbose_name="保养项目",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="tasks",
        help_text="留空表示该任务覆盖所属计划的全部保养项目",
    )
    plan_date = models.DateField("计划保养日期", db_index=True)
    status = models.CharField(
        "任务状态",
        max_length=16,
        choices=TaskStatus.choices,
        default=TaskStatus.PENDING,
        db_index=True,
    )
    assignee = models.ForeignKey(
        "factory.Employee",
        verbose_name="执行人",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    started_at = models.DateTimeField("开始保养时间", null=True, blank=True)
    finished_at = models.DateTimeField("完成时间", null=True, blank=True)
    result = models.CharField("保养结论", max_length=255, blank=True, default="")
    remark = models.TextField("备注", blank=True, default="")

    class Meta:
        verbose_name = "设备保养任务"
        verbose_name_plural = "设备保养任务"
        ordering = ["-plan_date", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "task_no"], name="uq_maintenance_task_company_no"
            ),
            # 同一计划同一天只生成一条任务；MySQL 下 plan 为 NULL 的手工任务不受此约束，
            # 需要去重时由服务层负责（见 services.py::generate_maintenance_tasks）
            models.UniqueConstraint(
                fields=["plan", "plan_date"], name="uq_maintenance_task_plan_date"
            ),
        ]
        indexes = [models.Index(fields=["company", "status"], name="idx_maint_task_status")]

    def __str__(self) -> str:
        return self.task_no


class MaintenanceRecord(CompanyScopedModel):
    """设备保养记录：已完成的保养事实，由任务完成时生成，也可单独补录。"""

    record_no = models.CharField("记录编号", max_length=32)
    task = models.ForeignKey(
        MaintenanceTask,
        verbose_name="保养任务",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="records",
    )
    equipment = models.ForeignKey(
        Equipment,
        verbose_name="设备",
        on_delete=models.PROTECT,
        related_name="maintenance_records",
        db_index=True,
    )
    item = models.ForeignKey(
        MaintenanceItem,
        verbose_name="保养项目",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="records",
    )
    maintain_date = models.DateField("保养日期", db_index=True)
    executor = models.ForeignKey(
        "factory.Employee",
        verbose_name="保养人",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    content = models.TextField("保养内容", blank=True, default="")
    result = models.TextField("保养结果", blank=True, default="")
    is_qualified = models.BooleanField("验收合格", default=True)
    cost = money_field("保养费用", default=Decimal("0"))
    remark = models.TextField("备注", blank=True, default="")

    class Meta:
        verbose_name = "设备保养记录"
        verbose_name_plural = "设备保养记录"
        ordering = ["-maintain_date", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "record_no"], name="uq_maintenance_record_company_no"
            ),
            models.CheckConstraint(
                condition=Q(cost__gte=0), name="ck_maintenance_record_cost_non_negative"
            ),
        ]

    def __str__(self) -> str:
        return self.record_no


class FaultReport(CompanyScopedModel):
    """设备故障保修单：设备坏了先报修，再派工维修。

    保修单只承载「故障现象与上报信息」；派工与维修过程在维修任务上记录，
    因此不会出现「同一字段在两张表里各改一遍」。
    """

    report_no = models.CharField("报修单号", max_length=32)
    equipment = models.ForeignKey(
        Equipment,
        verbose_name="设备",
        on_delete=models.PROTECT,
        related_name="fault_reports",
        db_index=True,
    )
    level = models.CharField(
        "故障等级",
        max_length=16,
        choices=FaultLevel.choices,
        default=FaultLevel.MEDIUM,
        db_index=True,
    )
    description = models.TextField("故障现象")
    reporter = models.ForeignKey(
        "factory.Employee",
        verbose_name="报修人",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    reported_at = models.DateTimeField("报修时间", default=timezone.now, db_index=True)
    status = models.CharField(
        "处理状态",
        max_length=16,
        choices=FaultReportStatus.choices,
        default=FaultReportStatus.REPORTED,
        db_index=True,
    )
    closed_at = models.DateTimeField("关闭时间", null=True, blank=True)
    remark = models.TextField("备注", blank=True, default="")

    class Meta:
        verbose_name = "设备故障保修"
        verbose_name_plural = "设备故障保修"
        ordering = ["-reported_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "report_no"], name="uq_fault_report_company_no"
            ),
        ]
        indexes = [models.Index(fields=["company", "status"], name="idx_fault_report_status")]

    def __str__(self) -> str:
        return self.report_no


class RepairTask(CompanyScopedModel):
    """设备维修任务：派工与维修执行。"""

    task_no = models.CharField("任务编号", max_length=32)
    fault_report = models.ForeignKey(
        FaultReport,
        verbose_name="故障保修单",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="repair_tasks",
    )
    equipment = models.ForeignKey(
        Equipment,
        verbose_name="设备",
        on_delete=models.PROTECT,
        related_name="repair_tasks",
        db_index=True,
    )
    symptom = models.TextField("故障描述", blank=True, default="")
    level = models.CharField(
        "故障等级", max_length=16, choices=FaultLevel.choices, default=FaultLevel.MEDIUM
    )
    assignee = models.ForeignKey(
        "factory.Employee",
        verbose_name="维修人",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    assigned_date = models.DateField("派工日期", null=True, blank=True, db_index=True)
    status = models.CharField(
        "任务状态",
        max_length=16,
        choices=TaskStatus.choices,
        default=TaskStatus.PENDING,
        db_index=True,
    )
    started_at = models.DateTimeField("开始维修时间", null=True, blank=True)
    finished_at = models.DateTimeField("完成时间", null=True, blank=True)
    downtime_minutes = models.PositiveIntegerField("停机时长（分钟）", default=0)
    remark = models.TextField("备注", blank=True, default="")

    class Meta:
        verbose_name = "设备维修任务"
        verbose_name_plural = "设备维修任务"
        ordering = ["-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "task_no"], name="uq_repair_task_company_no"
            ),
        ]
        indexes = [models.Index(fields=["company", "status"], name="idx_repair_task_status")]

    def __str__(self) -> str:
        return self.task_no


class RepairRecord(CompanyScopedModel):
    """设备维修记录：维修完成后的结果、原因、费用与停机时长。"""

    record_no = models.CharField("记录编号", max_length=32)
    task = models.ForeignKey(
        RepairTask,
        verbose_name="维修任务",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="records",
    )
    equipment = models.ForeignKey(
        Equipment,
        verbose_name="设备",
        on_delete=models.PROTECT,
        related_name="repair_records",
        db_index=True,
    )
    repair_date = models.DateField("维修日期", db_index=True)
    repairer = models.ForeignKey(
        "factory.Employee",
        verbose_name="维修人",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    fault_reason = models.TextField("故障原因", blank=True, default="")
    solution = models.TextField("维修措施", blank=True, default="")
    parts_used = models.TextField(
        "领用备件说明", blank=True, default="", help_text="领用后如需扣减库存，请在仓储模块走领料出库"
    )
    cost = money_field("维修费用", default=Decimal("0"))
    downtime_minutes = models.PositiveIntegerField("停机时长（分钟）", default=0)
    result = models.TextField("维修结果", blank=True, default="")
    remark = models.TextField("备注", blank=True, default="")

    class Meta:
        verbose_name = "设备维修记录"
        verbose_name_plural = "设备维修记录"
        ordering = ["-repair_date", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "record_no"], name="uq_repair_record_company_no"
            ),
            models.CheckConstraint(
                condition=Q(cost__gte=0), name="ck_repair_record_cost_non_negative"
            ),
        ]

    def __str__(self) -> str:
        return self.record_no


class InspectionItem(BaseModel):
    """点巡检项目：检什么、怎么检、合格范围。平台级共享参考数据。"""

    code = models.CharField("项目编码", max_length=32)
    name = models.CharField("项目名称", max_length=128)
    method = models.CharField(
        "检查方法",
        max_length=16,
        choices=InspectionMethod.choices,
        default=InspectionMethod.VISUAL,
        db_index=True,
    )
    standard = models.TextField("检查标准", blank=True, default="")
    uom = models.ForeignKey(
        "masterdata.UoM",
        verbose_name="计量单位",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    lower_limit = quantity_field("下限", null=True, blank=True)
    upper_limit = quantity_field("上限", null=True, blank=True)
    is_active = models.BooleanField("启用", default=True, db_index=True)
    remark = models.TextField("备注", blank=True, default="")

    class Meta:
        verbose_name = "点巡检项目"
        verbose_name_plural = "点巡检项目"
        ordering = ["code"]
        constraints = [
            models.UniqueConstraint(fields=["code"], name="uq_inspection_item_code"),
            models.CheckConstraint(
                condition=Q(lower_limit__isnull=True)
                | Q(upper_limit__isnull=True)
                | Q(lower_limit__lte=F("upper_limit")),
                name="ck_inspection_item_limit_order",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.code} {self.name}"


class InspectionTask(CompanyScopedModel):
    """点巡检任务：一次点检 / 巡检要做的工作。"""

    task_no = models.CharField("任务编号", max_length=32)
    task_type = models.CharField(
        "任务类型",
        max_length=16,
        choices=InspectionTaskType.choices,
        default=InspectionTaskType.POINT,
        db_index=True,
    )
    equipment = models.ForeignKey(
        Equipment,
        verbose_name="设备",
        on_delete=models.PROTECT,
        related_name="inspection_tasks",
        db_index=True,
    )
    plan_date = models.DateField("计划日期", db_index=True)
    status = models.CharField(
        "任务状态",
        max_length=16,
        choices=TaskStatus.choices,
        default=TaskStatus.PENDING,
        db_index=True,
    )
    assignee = models.ForeignKey(
        "factory.Employee",
        verbose_name="执行人",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    items = models.ManyToManyField(
        InspectionItem, verbose_name="点巡检项目", blank=True, related_name="tasks"
    )
    started_at = models.DateTimeField("开始时间", null=True, blank=True)
    finished_at = models.DateTimeField("完成时间", null=True, blank=True)
    result = models.CharField("任务结论", max_length=255, blank=True, default="")
    remark = models.TextField("备注", blank=True, default="")

    class Meta:
        verbose_name = "点巡检任务"
        verbose_name_plural = "点巡检任务"
        ordering = ["-plan_date", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "task_no"], name="uq_inspection_task_company_no"
            ),
        ]
        indexes = [models.Index(fields=["company", "status"], name="idx_inspection_task_status")]

    def __str__(self) -> str:
        return self.task_no


class InspectionRecord(CompanyScopedModel):
    """点巡检记录：每个项目的实际测量值与判定。

    判定为异常时，可由服务层一键转成故障保修单，形成「点检发现 → 报修 → 维修」闭环。
    """

    record_no = models.CharField("记录编号", max_length=32)
    task = models.ForeignKey(
        InspectionTask,
        verbose_name="点巡检任务",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="records",
    )
    equipment = models.ForeignKey(
        Equipment,
        verbose_name="设备",
        on_delete=models.PROTECT,
        related_name="inspection_records",
        db_index=True,
    )
    item = models.ForeignKey(
        InspectionItem,
        verbose_name="点巡检项目",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="records",
    )
    inspected_at = models.DateTimeField("检查时间", default=timezone.now, db_index=True)
    inspector = models.ForeignKey(
        "factory.Employee",
        verbose_name="检查人",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    measured_value = quantity_field("实测值", null=True, blank=True)
    result = models.CharField(
        "判定结果",
        max_length=16,
        choices=InspectionResult.choices,
        default=InspectionResult.NORMAL,
        db_index=True,
    )
    abnormal_desc = models.CharField("异常描述", max_length=255, blank=True, default="")
    remark = models.TextField("备注", blank=True, default="")

    class Meta:
        verbose_name = "点巡检记录"
        verbose_name_plural = "点巡检记录"
        ordering = ["-inspected_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "record_no"], name="uq_inspection_record_company_no"
            ),
        ]

    def __str__(self) -> str:
        return self.record_no


class AbnormalType(BaseModel):
    """设备异常类型：平台级共享参考数据。"""

    code = models.CharField("类型编码", max_length=32)
    name = models.CharField("类型名称", max_length=128)
    level = models.CharField(
        "默认等级",
        max_length=16,
        choices=FaultLevel.choices,
        default=FaultLevel.MEDIUM,
        db_index=True,
    )
    is_active = models.BooleanField("启用", default=True, db_index=True)
    remark = models.TextField("备注", blank=True, default="")

    class Meta:
        verbose_name = "设备异常类型"
        verbose_name_plural = "设备异常类型"
        ordering = ["code"]
        constraints = [
            models.UniqueConstraint(fields=["code"], name="uq_abnormal_type_code"),
        ]

    def __str__(self) -> str:
        return f"{self.code} {self.name}"


class AbnormalTask(CompanyScopedModel):
    """设备异常任务：现场发现的异常（异响、渗漏、参数漂移等）的分派与处理。"""

    task_no = models.CharField("任务编号", max_length=32)
    abnormal_type = models.ForeignKey(
        AbnormalType,
        verbose_name="异常类型",
        on_delete=models.PROTECT,
        related_name="tasks",
        db_index=True,
    )
    equipment = models.ForeignKey(
        Equipment,
        verbose_name="设备",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="abnormal_tasks",
        db_index=True,
    )
    source = models.CharField(
        "来源",
        max_length=16,
        choices=AbnormalSource.choices,
        default=AbnormalSource.MANUAL,
        db_index=True,
    )
    description = models.TextField("异常描述")
    reported_by = models.ForeignKey(
        "factory.Employee",
        verbose_name="上报人",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    reported_at = models.DateTimeField("上报时间", default=timezone.now, db_index=True)
    status = models.CharField(
        "处理状态",
        max_length=16,
        choices=AbnormalStatus.choices,
        default=AbnormalStatus.REPORTED,
        db_index=True,
    )
    handler = models.ForeignKey(
        "factory.Employee",
        verbose_name="处理人",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    deadline = models.DateField("处理期限", null=True, blank=True, db_index=True)
    handling = models.TextField("处理措施", blank=True, default="")
    closed_at = models.DateTimeField("关闭时间", null=True, blank=True)
    remark = models.TextField("备注", blank=True, default="")

    class Meta:
        verbose_name = "设备异常任务"
        verbose_name_plural = "设备异常任务"
        ordering = ["-reported_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "task_no"], name="uq_abnormal_task_company_no"
            ),
        ]
        indexes = [models.Index(fields=["company", "status"], name="idx_abnormal_task_status")]

    def __str__(self) -> str:
        return self.task_no


class AbnormalRecord(CompanyScopedModel):
    """设备异常记录：异常处理完成后沉淀的事实。"""

    record_no = models.CharField("记录编号", max_length=32)
    task = models.ForeignKey(
        AbnormalTask,
        verbose_name="异常任务",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="records",
    )
    abnormal_type = models.ForeignKey(
        AbnormalType,
        verbose_name="异常类型",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="records",
    )
    equipment = models.ForeignKey(
        Equipment,
        verbose_name="设备",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="abnormal_records",
    )
    handle_date = models.DateField("处理日期", db_index=True)
    handler = models.ForeignKey(
        "factory.Employee",
        verbose_name="处理人",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    action = models.TextField("处理动作", blank=True, default="")
    result = models.TextField("处理结果", blank=True, default="")
    remark = models.TextField("备注", blank=True, default="")

    class Meta:
        verbose_name = "设备异常记录"
        verbose_name_plural = "设备异常记录"
        ordering = ["-handle_date", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "record_no"], name="uq_abnormal_record_company_no"
            ),
        ]

    def __str__(self) -> str:
        return self.record_no
