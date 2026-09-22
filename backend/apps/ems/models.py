"""能源管理（EMS）数据模型。

设计边界：

* 本模块只承载**能源计量与能耗分析**：计量区域、计量设备（仪表）、能源价格、
  报警阈值、抄表读数、设备运行记录、能源报警。它不复制设备主数据，
  计量设备通过 ``equipment`` 关联设备台账（设备由设备模块维护）；
* 用能统计**一律由抄表读数聚合得到**，不落冗余日/月汇总表：
  汇总表会因为一次补录或冲销而与明细不一致，正是「有页面没有真数据」的根源；
* 单价按「介质 + 尖峰平谷时段 + 生效日期」维护，费用 = 用量 × 当期单价；
  数量、单价、金额全部 Decimal（禁止 float），API 以字符串输出；
* 设备离线检测由 ``ems_offline_check`` 管理命令按调用触发，不假装有实时采集；
  真实数采接入属于硬件接入范畴（见 ``docs/hardware-integration.md``）。
"""

from __future__ import annotations

from decimal import Decimal

from django.db import models
from django.db.models import Q

from apps.core.constants import (
    METER_READING_DECIMAL_PLACES,
    METER_READING_MAX_DIGITS,
    price_field,
    quantity_field,
    rate_field,
    reading_field,
)
from apps.core.models import CompanyScopedModel


class EnergyMedium(models.TextChoices):
    """能源介质。统计、价格、阈值、报警都按介质区分。"""

    ELECTRICITY = "electricity", "电"
    WATER = "water", "水"
    GAS = "gas", "气"
    LIQUID = "liquid", "液"


class TariffPeriod(models.TextChoices):
    """分时电价时段（尖峰平谷）。水/气/液价格同样可用此时段口径。"""

    SHARP = "sharp", "尖"
    PEAK = "peak", "峰"
    FLAT = "flat", "平"
    VALLEY = "valley", "谷"


class MeterStatus(models.TextChoices):
    ONLINE = "online", "在线"
    OFFLINE = "offline", "离线"
    STOPPED = "stopped", "停用"


class ReadingSource(models.TextChoices):
    MANUAL = "manual", "人工抄表"
    AUTO = "auto", "自动采集"
    IMPORT = "import", "批量导入"


class RunStatus(models.TextChoices):
    RUNNING = "running", "运行中"
    FINISHED = "finished", "已结束"
    CANCELLED = "cancelled", "已取消"


class AlarmType(models.TextChoices):
    OVER_LIMIT = "over_limit", "越限报警"
    OFFLINE = "offline", "设备离线"
    UNIT_CONSUMPTION = "unit_consumption", "单耗报警"
    ENERGY_CONSUMPTION = "energy_consumption", "能耗报警"


class AlarmLevel(models.TextChoices):
    INFO = "info", "提示"
    WARNING = "warning", "预警"
    CRITICAL = "critical", "严重"


class AlarmStatus(models.TextChoices):
    PENDING = "pending", "待处理"
    HANDLING = "handling", "处理中"
    CLOSED = "closed", "已关闭"


class AlarmSource(models.TextChoices):
    AUTO = "auto", "系统触发"
    MANUAL = "manual", "人工上报"


class EnergyArea(CompanyScopedModel):
    """计量区域：车间、楼层、工序等能耗统计边界，支持上下级。"""

    code = models.CharField("区域编码", max_length=32)
    name = models.CharField("区域名称", max_length=64)
    parent = models.ForeignKey(
        "self",
        verbose_name="上级区域",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="children",
    )
    department = models.ForeignKey(
        "factory.Department",
        verbose_name="所属部门",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
        db_index=True,
    )
    manager = models.ForeignKey(
        "factory.Employee",
        verbose_name="区域负责人",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    area_size = quantity_field("面积", default=Decimal("0"), help_text="用于单位面积能耗分析")
    remark = models.TextField("备注", blank=True, default="")
    is_active = models.BooleanField("启用", default=True, db_index=True)

    class Meta:
        verbose_name = "计量区域"
        verbose_name_plural = "计量区域"
        ordering = ["code"]
        constraints = [
            models.UniqueConstraint(fields=["company", "code"], name="uq_energy_area_company_code"),
            models.CheckConstraint(condition=Q(area_size__gte=0), name="ck_energy_area_size_non_negative"),
        ]

    def __str__(self) -> str:
        return f"{self.code} {self.name}"


class EnergyMeter(CompanyScopedModel):
    """计量设备（水表 / 电表 / 气表 / 液表）。

    它既是「基础管理 - 设备管理」维护的对象，也是「设备监控」按设备展示状态的
    数据来源；关联 ``equipment`` 后可以把能耗挂到具体设备上（单耗分析）。
    """

    code = models.CharField("仪表编码", max_length=32)
    name = models.CharField("仪表名称", max_length=64)
    medium = models.CharField(
        "能源介质", max_length=16, choices=EnergyMedium.choices, db_index=True
    )
    area = models.ForeignKey(
        EnergyArea,
        verbose_name="计量区域",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="meters",
    )
    equipment = models.ForeignKey(
        "equipment.Equipment",
        verbose_name="关联设备",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="energy_meters",
        help_text="设备级能耗与单耗分析依赖此关联",
    )
    department = models.ForeignKey(
        "factory.Department",
        verbose_name="使用部门",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    meter_model = models.CharField("规格型号", max_length=64, blank=True, default="")
    serial_no = models.CharField("出厂编号", max_length=64, blank=True, default="")
    multiplier = rate_field("倍率", default=Decimal("1"))
    unit = models.CharField("计量单位", max_length=16, default="kWh")
    status = models.CharField(
        "运行状态", max_length=16, choices=MeterStatus.choices, default=MeterStatus.ONLINE, db_index=True
    )
    location = models.CharField("安装位置", max_length=128, blank=True, default="")
    install_date = models.DateField("安装日期", null=True, blank=True)
    last_reading_at = models.DateTimeField("最近抄表时间", null=True, blank=True, db_index=True)
    is_monitored = models.BooleanField("纳入监控", default=True, db_index=True)
    remark = models.TextField("备注", blank=True, default="")
    is_active = models.BooleanField("启用", default=True, db_index=True)

    class Meta:
        verbose_name = "计量设备"
        verbose_name_plural = "计量设备"
        ordering = ["code"]
        constraints = [
            models.UniqueConstraint(fields=["company", "code"], name="uq_energy_meter_company_code"),
            models.CheckConstraint(condition=Q(multiplier__gt=0), name="ck_energy_meter_multiplier_positive"),
        ]
        indexes = [models.Index(fields=["company", "status"], name="idx_energy_meter_status")]

    def __str__(self) -> str:
        return f"{self.code} {self.name}"


class EnergyPrice(CompanyScopedModel):
    """能源价格：同一介质按时段维护不同单价，按生效日期区间取价。"""

    medium = models.CharField("能源介质", max_length=16, choices=EnergyMedium.choices, db_index=True)
    tariff_period = models.CharField(
        "时段", max_length=16, choices=TariffPeriod.choices, default=TariffPeriod.FLAT
    )
    name = models.CharField("价格名称", max_length=64)
    unit_price = price_field("单价", default=Decimal("0"))
    currency_unit = models.CharField("计价单位", max_length=16, default="元/kWh")
    effective_from = models.DateField("生效日期")
    effective_to = models.DateField("失效日期", null=True, blank=True)
    remark = models.TextField("备注", blank=True, default="")
    is_active = models.BooleanField("启用", default=True, db_index=True)

    class Meta:
        verbose_name = "能源价格"
        verbose_name_plural = "能源价格"
        ordering = ["medium", "tariff_period", "-effective_from"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "medium", "tariff_period", "effective_from"],
                name="uq_energy_price_company_medium_period_from",
            ),
            models.CheckConstraint(condition=Q(unit_price__gte=0), name="ck_energy_price_non_negative"),
        ]

    def __str__(self) -> str:
        return f"{self.get_medium_display()}{self.get_tariff_period_display()}价 {self.name}"


class EnergyThreshold(CompanyScopedModel):
    """报警阈值：越限、日用量、单耗与离线判定集中配置。"""

    name = models.CharField("阈值名称", max_length=64)
    medium = models.CharField("能源介质", max_length=16, choices=EnergyMedium.choices, db_index=True)
    meter = models.ForeignKey(
        EnergyMeter,
        verbose_name="计量设备",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="thresholds",
        help_text="留空表示对该介质的全部仪表生效",
    )
    upper_limit = reading_field("读数上限", null=True, blank=True)
    lower_limit = reading_field("读数下限", null=True, blank=True)
    daily_limit = quantity_field("日用量上限", null=True, blank=True)
    unit_consumption_limit = quantity_field("单耗上限", null=True, blank=True)
    offline_minutes = models.PositiveIntegerField(
        "离线判定（分钟）", default=0, help_text="0 表示不检测离线"
    )
    alarm_level = models.CharField(
        "报警级别", max_length=16, choices=AlarmLevel.choices, default=AlarmLevel.WARNING
    )
    remark = models.TextField("备注", blank=True, default="")
    is_active = models.BooleanField("启用", default=True, db_index=True)

    class Meta:
        verbose_name = "能源阈值"
        verbose_name_plural = "能源阈值"
        ordering = ["medium", "name"]
        constraints = [
            models.UniqueConstraint(fields=["company", "name"], name="uq_energy_threshold_company_name"),
            models.CheckConstraint(
                condition=Q(offline_minutes__gte=0), name="ck_energy_threshold_offline_non_negative"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.name}（{self.get_medium_display()}）"


class MeterReading(CompanyScopedModel):
    """抄表读数：用能统计的唯一事实来源。

    ``consumption``（本次用量）在写入时由服务层按「本次读数 − 上次读数」计算并冻结，
    这样历史区间统计不会被后续补录悄悄改写；读数回退（小于上次读数）会被服务拒绝，
    避免出现负用量把月报冲成负数。
    """

    meter = models.ForeignKey(
        EnergyMeter, verbose_name="计量设备", on_delete=models.CASCADE, related_name="readings"
    )
    reading_at = models.DateTimeField("抄表时间", db_index=True)
    reading = reading_field("表底读数")
    consumption = quantity_field("本次用量", default=Decimal("0"))
    tariff_period = models.CharField(
        "时段", max_length=16, choices=TariffPeriod.choices, default=TariffPeriod.FLAT
    )
    source = models.CharField(
        "数据来源", max_length=16, choices=ReadingSource.choices, default=ReadingSource.MANUAL
    )
    recorder = models.ForeignKey(
        "factory.Employee",
        verbose_name="抄表人",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    note = models.CharField("备注", max_length=255, blank=True, default="")

    class Meta:
        verbose_name = "抄表读数"
        verbose_name_plural = "抄表读数"
        ordering = ["-reading_at", "-id"]
        constraints = [
            models.CheckConstraint(condition=Q(reading__gte=0), name="ck_meter_reading_non_negative"),
            models.CheckConstraint(
                condition=Q(consumption__gte=0), name="ck_meter_reading_consumption_non_negative"
            ),
        ]
        indexes = [
            models.Index(fields=["company", "meter", "reading_at"], name="idx_meter_reading_timeline")
        ]

    def __str__(self) -> str:
        return f"{self.meter_id}@{self.reading_at:%Y-%m-%d %H:%M}"


class EnergyRunRecord(CompanyScopedModel):
    """设备运行记录：运行时长 + 产量 → 单耗，是「单耗报警」的计算依据。"""

    record_no = models.CharField("记录编号", max_length=32)
    meter = models.ForeignKey(
        EnergyMeter, verbose_name="计量设备", on_delete=models.PROTECT, related_name="run_records"
    )
    equipment = models.ForeignKey(
        "equipment.Equipment",
        verbose_name="设备",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="energy_run_records",
    )
    status = models.CharField(
        "状态", max_length=16, choices=RunStatus.choices, default=RunStatus.RUNNING, db_index=True
    )
    started_at = models.DateTimeField("开始时间")
    finished_at = models.DateTimeField("结束时间", null=True, blank=True)
    run_minutes = models.PositiveIntegerField("运行时长（分钟）", default=0)
    output_desc = models.CharField("产量说明", max_length=64, blank=True, default="")
    output_qty = quantity_field("产量", default=Decimal("0"))
    energy_consumption = quantity_field("能耗用量", default=Decimal("0"))
    unit_consumption = quantity_field("单位能耗（单耗）", default=Decimal("0"))
    operator = models.ForeignKey(
        "factory.Employee",
        verbose_name="操作人",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    remark = models.TextField("备注", blank=True, default="")

    class Meta:
        verbose_name = "设备运行记录"
        verbose_name_plural = "设备运行记录"
        ordering = ["-started_at", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["company", "record_no"], name="uq_energy_run_company_no"),
            models.CheckConstraint(
                condition=Q(energy_consumption__gte=0), name="ck_energy_run_consumption_non_negative"
            ),
            models.CheckConstraint(condition=Q(output_qty__gte=0), name="ck_energy_run_output_non_negative"),
        ]
        indexes = [models.Index(fields=["company", "status"], name="idx_energy_run_status")]

    def __str__(self) -> str:
        return self.record_no


class EnergyAlarm(CompanyScopedModel):
    """能源报警：越限、离线、单耗、能耗四类，统一走「待处理 → 处理中 → 已关闭」。"""

    alarm_no = models.CharField("报警编号", max_length=32)
    meter = models.ForeignKey(
        EnergyMeter,
        verbose_name="计量设备",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="alarms",
    )
    area = models.ForeignKey(
        EnergyArea,
        verbose_name="计量区域",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="alarms",
    )
    alarm_type = models.CharField(
        "报警类型", max_length=24, choices=AlarmType.choices, db_index=True
    )
    level = models.CharField("报警级别", max_length=16, choices=AlarmLevel.choices, default=AlarmLevel.WARNING)
    status = models.CharField(
        "处理状态", max_length=16, choices=AlarmStatus.choices, default=AlarmStatus.PENDING, db_index=True
    )
    source = models.CharField(
        "报警来源", max_length=16, choices=AlarmSource.choices, default=AlarmSource.AUTO
    )
    source_ref = models.CharField(
        "来源标识",
        max_length=128,
        blank=True,
        default="",
        db_index=True,
        help_text="报警的精确来源，如数采测点 iot:网关编码:测点编码；用于按来源去重与追溯",
    )
    occurred_at = models.DateTimeField("发生时间", db_index=True)
    message = models.CharField("报警内容", max_length=255)
    triggered_value = reading_field("触发值", null=True, blank=True)
    threshold_value = reading_field("阈值", null=True, blank=True)
    handler = models.ForeignKey(
        "factory.Employee",
        verbose_name="处理人",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    handled_at = models.DateTimeField("开始处理时间", null=True, blank=True)
    handle_note = models.TextField("处理说明", blank=True, default="")
    closed_at = models.DateTimeField("关闭时间", null=True, blank=True)
    remark = models.TextField("备注", blank=True, default="")

    class Meta:
        verbose_name = "能源报警"
        verbose_name_plural = "能源报警"
        ordering = ["-occurred_at", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["company", "alarm_no"], name="uq_energy_alarm_company_no"),
        ]
        indexes = [models.Index(fields=["company", "status"], name="idx_energy_alarm_status")]

    def __str__(self) -> str:
        return f"{self.alarm_no} {self.message}"


__all__ = [
    "AlarmLevel",
    "AlarmSource",
    "AlarmStatus",
    "AlarmType",
    "EnergyAlarm",
    "EnergyArea",
    "EnergyMedium",
    "EnergyMeter",
    "EnergyPrice",
    "EnergyRunRecord",
    "EnergyThreshold",
    "MeterReading",
    "MeterStatus",
    "ReadingSource",
    "RunStatus",
    "TariffPeriod",
    "METER_READING_DECIMAL_PLACES",
    "METER_READING_MAX_DIGITS",
]
