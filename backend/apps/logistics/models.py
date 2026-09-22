"""生产物流管理数据模型。

设计边界：

* 本模块管理**厂内自动化物流设备**（AGV、穿梭车、堆垛机等）与其搬运任务，
  以及设备操作日志；不复制设备台账（设备台账属于 ``apps.equipment``），
  自动化设备是「物流执行单元」，与 CMMS 里的生产设备是两类对象；
* 物料与库位不复制：任务的取放位置引用 ``wms.Location``、物料引用
  ``masterdata.Material``；库存仍然只由统一库存服务改动，本模块**不动库存**；
* 任务状态只能由服务层推进（下发 → 执行 → 完成 / 取消），每次状态变化在同一事务里
  写一条操作日志，保证「任务卡片上的时间线」与日志表一致。
"""

from __future__ import annotations

from decimal import Decimal

from django.db import models
from django.db.models import Q

from apps.core.constants import quantity_field, rate_field
from apps.core.models import CompanyScopedModel


class AutomationDeviceType(models.TextChoices):
    AGV = "agv", "AGV 无人搬运车"
    SHUTTLE = "shuttle", "穿梭车"
    STACKER = "stacker", "堆垛机"
    ROBOT = "robot", "工业机器人"
    CONVEYOR = "conveyor", "输送线"
    OTHER = "other", "其他"


class AutomationDeviceStatus(models.TextChoices):
    IDLE = "idle", "空闲"
    RUNNING = "running", "作业中"
    CHARGING = "charging", "充电中"
    FAULT = "fault", "故障"
    MAINTENANCE = "maintenance", "保养维修"
    OFFLINE = "offline", "离线"


class LogisticsTaskType(models.TextChoices):
    MOVE = "move", "搬运"
    INBOUND = "inbound", "上架入库"
    OUTBOUND = "outbound", "下架出库"
    PICKING = "picking", "拣选配送"
    TRANSFER = "transfer", "库内移库"
    COUNTING = "counting", "盘点搬运"


class LogisticsTaskPriority(models.TextChoices):
    LOW = "low", "低"
    NORMAL = "normal", "普通"
    HIGH = "high", "高"
    URGENT = "urgent", "紧急"


class LogisticsTaskStatus(models.TextChoices):
    PENDING = "pending", "待下发"
    DISPATCHED = "dispatched", "已下发"
    EXECUTING = "executing", "执行中"
    FINISHED = "finished", "已完成"
    CANCELLED = "cancelled", "已取消"

    @classmethod
    def open_states(cls) -> tuple[str, ...]:
        """未结束的任务状态：用于「设备是否有在途任务」判断。"""
        return (cls.PENDING, cls.DISPATCHED, cls.EXECUTING)


class LogisticsLogAction(models.TextChoices):
    CREATE = "create", "创建任务"
    DISPATCH = "dispatch", "下发任务"
    START = "start", "开始执行"
    FINISH = "finish", "完成执行"
    CANCEL = "cancel", "取消任务"
    STATUS_CHANGE = "status_change", "设备状态变更"


class AutomationDevice(CompanyScopedModel):
    """自动化物流设备（AGV / 穿梭车 / 堆垛机 / 机器人 / 输送线）。"""

    code = models.CharField("设备编号", max_length=32)
    name = models.CharField("设备名称", max_length=64)
    device_type = models.CharField(
        "设备类型", max_length=16, choices=AutomationDeviceType.choices, db_index=True
    )
    status = models.CharField(
        "运行状态",
        max_length=16,
        choices=AutomationDeviceStatus.choices,
        default=AutomationDeviceStatus.IDLE,
        db_index=True,
    )
    workshop = models.ForeignKey(
        "factory.Workshop",
        verbose_name="所在车间",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    location = models.CharField("默认停靠点", max_length=128, blank=True, default="")
    max_load = quantity_field("额定载重", default=Decimal("0"))
    speed = rate_field("运行速度", default=Decimal("0"), help_text="米/分钟")
    battery_level = models.PositiveSmallIntegerField("电量（%）", default=100)
    commissioned_date = models.DateField("投用日期", null=True, blank=True)
    last_maintenance_date = models.DateField("上次保养日期", null=True, blank=True)
    next_maintenance_date = models.DateField("下次保养日期", null=True, blank=True, db_index=True)
    remark = models.TextField("备注", blank=True, default="")
    is_active = models.BooleanField("启用", default=True, db_index=True)

    class Meta:
        verbose_name = "自动化设备"
        verbose_name_plural = "自动化设备"
        ordering = ["code"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "code"], name="uq_automation_device_company_code"
            ),
            models.CheckConstraint(
                condition=Q(battery_level__lte=100), name="ck_automation_device_battery_range"
            ),
            models.CheckConstraint(
                condition=Q(max_load__gte=0), name="ck_automation_device_load_non_negative"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.code} {self.name}"


class LogisticsTask(CompanyScopedModel):
    """物流任务：一条任务对应一次搬运/上下架/移库作业。"""

    task_no = models.CharField("任务编号", max_length=32)
    task_type = models.CharField(
        "任务类型", max_length=16, choices=LogisticsTaskType.choices, default=LogisticsTaskType.MOVE
    )
    device = models.ForeignKey(
        AutomationDevice,
        verbose_name="执行设备",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="tasks",
        db_index=True,
    )
    priority = models.CharField(
        "优先级",
        max_length=16,
        choices=LogisticsTaskPriority.choices,
        default=LogisticsTaskPriority.NORMAL,
        db_index=True,
    )
    status = models.CharField(
        "任务状态",
        max_length=16,
        choices=LogisticsTaskStatus.choices,
        default=LogisticsTaskStatus.PENDING,
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
    from_location = models.ForeignKey(
        "wms.Location",
        verbose_name="起点库位",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    to_location = models.ForeignKey(
        "wms.Location",
        verbose_name="目标库位",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    material = models.ForeignKey(
        "masterdata.Material",
        verbose_name="物料",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    quantity = quantity_field("数量", default=Decimal("0"))
    container_no = models.CharField("容器/托盘号", max_length=64, blank=True, default="")
    requested_by = models.ForeignKey(
        "factory.Employee",
        verbose_name="申请人",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    assignee = models.ForeignKey(
        "factory.Employee",
        verbose_name="执行人",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    planned_at = models.DateTimeField("计划执行时间", null=True, blank=True)
    dispatched_at = models.DateTimeField("下发时间", null=True, blank=True)
    started_at = models.DateTimeField("开始时间", null=True, blank=True)
    finished_at = models.DateTimeField("完成时间", null=True, blank=True)
    result = models.TextField("执行结果", blank=True, default="")
    remark = models.TextField("备注", blank=True, default="")

    class Meta:
        verbose_name = "物流任务"
        verbose_name_plural = "物流任务"
        ordering = ["-id"]
        constraints = [
            models.UniqueConstraint(fields=["company", "task_no"], name="uq_logistics_task_company_no"),
            models.CheckConstraint(condition=Q(quantity__gte=0), name="ck_logistics_task_quantity"),
        ]
        indexes = [models.Index(fields=["company", "status"], name="idx_logistics_task_status")]

    def __str__(self) -> str:
        return self.task_no


class LogisticsOperationLog(CompanyScopedModel):
    """物流操作日志：由服务层在状态变更的同一事务内写入，只读展示。"""

    device = models.ForeignKey(
        AutomationDevice,
        verbose_name="设备",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="logs",
    )
    task = models.ForeignKey(
        LogisticsTask,
        verbose_name="任务",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="logs",
    )
    action = models.CharField("操作类型", max_length=16, choices=LogisticsLogAction.choices, db_index=True)
    operator = models.ForeignKey(
        "factory.Employee",
        verbose_name="操作人",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    occurred_at = models.DateTimeField("操作时间", db_index=True)
    detail = models.TextField("操作说明", blank=True, default="")
    payload = models.JSONField("附加数据", default=dict, blank=True)

    class Meta:
        verbose_name = "物流操作日志"
        verbose_name_plural = "物流操作日志"
        ordering = ["-occurred_at", "-id"]
        indexes = [models.Index(fields=["company", "action"], name="idx_logistics_log_action")]

    def __str__(self) -> str:
        return f"{self.get_action_display()}@{self.occurred_at:%Y-%m-%d %H:%M}"
