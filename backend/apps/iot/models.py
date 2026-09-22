"""设备数采与监控（IoT）数据模型。

设计边界（任务书 10.14、11.1~11.5 与 ``docs/hardware-integration.md``）：

* 本模块只做**只读采集**：连接配置 → 数采设备（网关）→ 测点 → 原始报文 → 标准化读数。
  平台**不下发任何控制逻辑**，不替代 PLC 实时控制、安全联锁、SIS 或消防联动；
* 首版只实现 **HTTP 上报入口** 与 **内置模拟器**；MQTT / Modbus 等协议只保留
  「待协议确认」的选项，采集入口对未实现的协议**明确拒绝**，不做假适配；
* **设备独立凭证**：网关使用一次性下发的令牌上报（库里只存 SHA-256 摘要），
  不复用员工登录会话；令牌可随时轮换，明文只在生成时返回一次；
* **去重**：报文按「网关 + 消息 ID」判重并记入采集日志；读数按「测点 + 设备时间」
  建唯一约束，重复上报不会产生第二条读数；
* **模拟数据必须可辨识**：``is_simulated`` 从连接配置一路带到报文与读数，
  界面按「模拟」标签显示，绝不把模拟值当成真实采集结果（任务书 2.4）；
* 越限与离线报警统一调用 ``apps/ems/services.py::raise_alarm`` 写入能源报警台账，
  本模块**不直接写 EMS 的表**（AGENTS.md 三.4）。
"""

from __future__ import annotations

from django.db import models
from django.db.models import Q

from apps.core.constants import reading_field
from apps.core.models import CompanyScopedModel


class IoTProtocol(models.TextChoices):
    """采集协议。

    只有 ``http`` 与 ``simulator`` 在首版实现了入口；``mqtt`` / ``modbus``
    是**尚未实现**的待确认协议，采集入口会明确拒绝，避免出现「界面能配、数据进不来」
    的假支持。
    """

    HTTP = "http", "HTTP 上报（已实现）"
    SIMULATOR = "simulator", "内置模拟器（模拟数据）"
    MQTT = "mqtt", "MQTT（待协议确认，未实现）"
    MODBUS = "modbus", "Modbus（待协议确认，未实现）"


class GatewayType(models.TextChoices):
    """数采设备类型（任务书 11.1：传感器 / 智能水表 / 智能电表等）。"""

    GATEWAY = "gateway", "采集网关"
    SENSOR = "sensor", "传感器"
    ELECTRIC_METER = "electric_meter", "智能电表"
    WATER_METER = "water_meter", "智能水表"
    PLC = "plc", "PLC（只读采集）"
    OTHER = "other", "其他"


class GatewayStatus(models.TextChoices):
    UNKNOWN = "unknown", "未知"
    ONLINE = "online", "在线"
    OFFLINE = "offline", "离线"
    DISABLED = "disabled", "已停用"


class PointQuantity(models.TextChoices):
    """测点的物理量类型。

    任务书 11.1 提到温度、电压、振动、电流等传感器，但**具体分配未明确**
    （见 ``docs/assumptions.md`` A-01），因此这里只提供通用物理量，
    不预设「哪台设备测什么」。
    """

    TEMPERATURE = "temperature", "温度"
    VOLTAGE = "voltage", "电压"
    CURRENT = "current", "电流"
    VIBRATION = "vibration", "振动"
    PRESSURE = "pressure", "压力"
    FLOW = "flow", "流量"
    ELECTRICITY = "electricity", "电量"
    WATER = "water", "水量"
    GAS = "gas", "气量"
    OTHER = "other", "其他"


class MessageStatus(models.TextChoices):
    RECEIVED = "received", "已接收"
    PROCESSED = "processed", "已处理"
    DUPLICATED = "duplicated", "重复报文"
    FAILED = "failed", "处理失败"


class ReadingQuality(models.TextChoices):
    GOOD = "good", "正常"
    UNCERTAIN = "uncertain", "可疑"
    BAD = "bad", "异常"


class ReadingSource(models.TextChoices):
    DEVICE = "device", "设备上报"
    SIMULATOR = "simulator", "模拟器"


class IoTConnection(CompanyScopedModel):
    """连接配置：协议、地址、凭证引用、超时、限流与批次上限。"""

    code = models.CharField("连接编码", max_length=32)
    name = models.CharField("连接名称", max_length=64)
    protocol = models.CharField(
        "采集协议", max_length=16, choices=IoTProtocol.choices, default=IoTProtocol.HTTP
    )
    endpoint = models.CharField(
        "接入地址", max_length=128, blank=True, default="", help_text="如 http://10.0.0.8:8080/report"
    )
    credential_ref = models.CharField(
        "凭证引用",
        max_length=128,
        blank=True,
        default="",
        help_text="凭证**说明或引用位置**，平台不在此保存明文密码或密钥",
    )
    timeout_seconds = models.PositiveIntegerField("超时（秒）", default=10)
    batch_limit = models.PositiveIntegerField(
        "单次上报测点上限", default=200, help_text="超过上限的报文会被拒绝"
    )
    rate_limit_per_minute = models.PositiveIntegerField(
        "每分钟上报次数上限", default=60, help_text="按网关统计；0 表示不限制"
    )
    is_enabled = models.BooleanField("启用采集", default=True)
    is_simulated = models.BooleanField(
        "模拟连接", default=False, help_text="模拟连接产生的数据会全程标注为「模拟」"
    )
    is_active = models.BooleanField("启用", default=True, db_index=True)
    remark = models.TextField("备注", blank=True, default="")

    class Meta:
        verbose_name = "数采连接配置"
        verbose_name_plural = "数采连接配置"
        ordering = ["code"]
        constraints = [
            models.UniqueConstraint(fields=["company", "code"], name="uq_iot_connection_company_code"),
            models.CheckConstraint(
                condition=Q(batch_limit__gt=0), name="ck_iot_connection_batch_limit_positive"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.code} {self.name}"


class IoTGateway(CompanyScopedModel):
    """数采设备（网关 / 传感器 / 智能表）。

    设备凭证：``token_hash`` 只保存令牌的 SHA-256 摘要，``token_prefix`` 用于在界面上
    辨认「这把令牌是哪一把」。明文令牌只在生成/轮换时返回一次，平台不留存明文。
    """

    code = models.CharField("设备编码", max_length=32)
    name = models.CharField("设备名称", max_length=64)
    gateway_type = models.CharField(
        "设备类型", max_length=16, choices=GatewayType.choices, default=GatewayType.GATEWAY
    )
    connection = models.ForeignKey(
        IoTConnection,
        verbose_name="连接配置",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="gateways",
    )
    equipment = models.ForeignKey(
        "equipment.Equipment",
        verbose_name="关联设备台账",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="iot_gateways",
    )
    factory = models.ForeignKey(
        "factory.Factory",
        verbose_name="工厂",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    workshop = models.ForeignKey(
        "factory.Workshop",
        verbose_name="车间",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    production_line = models.ForeignKey(
        "factory.ProductionLine",
        verbose_name="线体",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    location = models.CharField("安装位置", max_length=128, blank=True, default="")
    status = models.CharField(
        "在线状态", max_length=16, choices=GatewayStatus.choices, default=GatewayStatus.UNKNOWN,
        db_index=True,
    )
    last_seen_at = models.DateTimeField("最近上报时间", null=True, blank=True, db_index=True)
    offline_minutes = models.PositiveIntegerField(
        "离线判定（分钟）", default=0, help_text="超过该时长未上报即判定离线；0 表示不判定"
    )
    token_prefix = models.CharField("令牌前缀", max_length=16, blank=True, default="")
    token_hash = models.CharField(
        "令牌摘要", max_length=64, blank=True, default="", help_text="设备令牌的 SHA-256 摘要"
    )
    token_rotated_at = models.DateTimeField("令牌更新时间", null=True, blank=True)
    is_simulated = models.BooleanField("模拟设备", default=False, db_index=True)
    is_active = models.BooleanField("启用", default=True, db_index=True)
    remark = models.TextField("备注", blank=True, default="")

    class Meta:
        verbose_name = "数采设备"
        verbose_name_plural = "数采设备"
        ordering = ["code"]
        constraints = [
            models.UniqueConstraint(fields=["company", "code"], name="uq_iot_gateway_company_code"),
        ]
        indexes = [models.Index(fields=["company", "status"], name="idx_iot_gateway_status")]

    def __str__(self) -> str:
        return f"{self.code} {self.name}"


class IoTPoint(CompanyScopedModel):
    """测点：设备上的一个可采集量（温度、电压、振动、电流、水量…）。"""

    gateway = models.ForeignKey(
        IoTGateway,
        verbose_name="数采设备",
        on_delete=models.CASCADE,
        related_name="points",
        db_index=True,
    )
    code = models.CharField("测点编码", max_length=32)
    name = models.CharField("测点名称", max_length=64)
    quantity = models.CharField(
        "物理量", max_length=16, choices=PointQuantity.choices, default=PointQuantity.OTHER
    )
    unit = models.CharField("单位", max_length=16, blank=True, default="")
    range_min = reading_field("量程下限", null=True, blank=True)
    range_max = reading_field("量程上限", null=True, blank=True)
    precision = models.PositiveSmallIntegerField("小数位", default=3)
    is_cumulative = models.BooleanField(
        "累计值", default=False, help_text="累计值（如电能表底）与瞬时值的统计口径不同"
    )
    upper_limit = reading_field("上限", null=True, blank=True)
    lower_limit = reading_field("下限", null=True, blank=True)
    alarm_enabled = models.BooleanField("越限报警", default=True)
    meter = models.ForeignKey(
        "ems.EnergyMeter",
        verbose_name="关联计量仪表",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="iot_points",
        help_text="仅作对照线索：首版**不**把采集读数自动写入能源抄表，避免重复计量",
    )
    is_active = models.BooleanField("启用", default=True, db_index=True)
    remark = models.TextField("备注", blank=True, default="")

    class Meta:
        verbose_name = "采集测点"
        verbose_name_plural = "采集测点"
        ordering = ["gateway_id", "code"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "gateway", "code"], name="uq_iot_point_gateway_code"
            ),
        ]
        indexes = [models.Index(fields=["gateway", "is_active"], name="idx_iot_point_active")]

    def __str__(self) -> str:
        return f"{self.gateway_id}-{self.code}"


class IoTMessage(CompanyScopedModel):
    """原始报文（采集日志）。

    每条上报**都留一行**，包括重复报文与处理失败的报文：这是「采集失败日志」的载体，
    也是排查「设备说发了、平台说没收到」时唯一可信的依据。
    ``message_id`` 由设备侧生成，用于判重。
    """

    gateway = models.ForeignKey(
        IoTGateway,
        verbose_name="数采设备",
        on_delete=models.CASCADE,
        related_name="messages",
        db_index=True,
    )
    message_id = models.CharField("消息 ID", max_length=64)
    received_at = models.DateTimeField("接收时间", db_index=True)
    device_time = models.DateTimeField("设备时间", null=True, blank=True)
    source_ip = models.GenericIPAddressField("来源 IP", null=True, blank=True)
    payload = models.JSONField("原始报文", default=dict, blank=True)
    point_count = models.PositiveIntegerField("测点数", default=0)
    status = models.CharField(
        "处理状态", max_length=16, choices=MessageStatus.choices, default=MessageStatus.RECEIVED,
        db_index=True,
    )
    error_message = models.CharField("处理说明", max_length=255, blank=True, default="")
    is_simulated = models.BooleanField("模拟数据", default=False, db_index=True)

    class Meta:
        verbose_name = "采集报文"
        verbose_name_plural = "采集报文"
        ordering = ["-received_at", "-id"]
        indexes = [
            models.Index(fields=["gateway", "message_id"], name="idx_iot_message_dedupe"),
            models.Index(fields=["company", "status"], name="idx_iot_message_status"),
        ]

    def __str__(self) -> str:
        return f"{self.gateway_id}/{self.message_id}"


class IoTReading(CompanyScopedModel):
    """标准化读数：设备时间、接收时间、数值、单位、数据质量、来源与去重依据。

    「测点 + 设备时间」唯一：设备重发同一时刻的读数不会产生第二条记录，
    这是比「按报文判重」更硬的去重依据（网关重启后可能重发旧报文）。
    """

    gateway = models.ForeignKey(
        IoTGateway,
        verbose_name="数采设备",
        on_delete=models.CASCADE,
        related_name="readings",
        db_index=True,
    )
    point = models.ForeignKey(
        IoTPoint,
        verbose_name="测点",
        on_delete=models.CASCADE,
        related_name="readings",
        db_index=True,
    )
    message = models.ForeignKey(
        IoTMessage,
        verbose_name="来源报文",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="readings",
    )
    device_time = models.DateTimeField("设备时间", db_index=True)
    received_at = models.DateTimeField("接收时间", db_index=True)
    value = reading_field("读数")
    unit = models.CharField("单位", max_length=16, blank=True, default="")
    quality = models.CharField(
        "数据质量", max_length=16, choices=ReadingQuality.choices, default=ReadingQuality.GOOD
    )
    source = models.CharField(
        "数据来源", max_length=16, choices=ReadingSource.choices, default=ReadingSource.DEVICE
    )
    is_simulated = models.BooleanField("模拟数据", default=False, db_index=True)

    class Meta:
        verbose_name = "采集读数"
        verbose_name_plural = "采集读数"
        ordering = ["-device_time", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["point", "device_time"], name="uq_iot_reading_point_time"
            ),
        ]
        indexes = [
            models.Index(fields=["company", "point", "device_time"], name="idx_iot_reading_timeline"),
            models.Index(fields=["company", "received_at"], name="idx_iot_reading_received"),
        ]

    def __str__(self) -> str:
        return f"{self.point_id}@{self.device_time:%Y-%m-%d %H:%M:%S}"


__all__ = [
    "GatewayStatus",
    "GatewayType",
    "IoTConnection",
    "IoTGateway",
    "IoTMessage",
    "IoTPoint",
    "IoTProtocol",
    "IoTReading",
    "MessageStatus",
    "PointQuantity",
    "ReadingQuality",
    "ReadingSource",
]
