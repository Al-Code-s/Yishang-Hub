"""设备数采序列化器。

* 枚举字段的中文标签由 ``DisplayLabelsMixin`` 自动补 ``<field>_display``；
* 设备令牌的**摘要（``token_hash``）永不外泄**，接口只回显 ``token_prefix``，
  明文令牌仅在生成 / 轮换的那一次响应里返回；
* 测点的公司归属由「所属数采设备」推导，客户端不传 ``company_id``，
  避免把 A 公司的测点挂到 B 公司；
* ``status`` / ``last_seen_at`` / ``token_*`` 只读：在线状态与令牌只能由服务层改动。
"""

from __future__ import annotations

from rest_framework import serializers

from apps.core.serializers import ReferenceIdSerializer, ServerDerivedCodeSerializerMixin
from apps.iot.models import IoTConnection, IoTGateway, IoTMessage, IoTPoint, IoTReading


def _name_of(instance, attribute: str) -> str:
    related = getattr(instance, attribute, None)
    return str(related) if related is not None else ""


class IoTConnectionSerializer(ServerDerivedCodeSerializerMixin, ReferenceIdSerializer):
    company_name = serializers.SerializerMethodField()
    code = serializers.CharField(allow_blank=True, default="", max_length=32, label="连接编码")

    class Meta:
        model = IoTConnection
        fields = (
            "id", "company_id", "company_name", "code", "name", "protocol", "endpoint",
            "credential_ref", "timeout_seconds", "batch_limit", "rate_limit_per_minute",
            "is_enabled", "is_simulated", "is_active", "remark",
            "version", "created_at", "updated_at",
        )
        read_only_fields = ("id", "company_name", "version", "created_at", "updated_at")

    def get_company_name(self, obj: IoTConnection) -> str:
        return _name_of(obj, "company")

    def validate_code(self, value: str) -> str:
        code = (value or "").strip()
        if not code and self.instance is not None:
            raise serializers.ValidationError("连接编码不能为空。")
        return code

    def validate_batch_limit(self, value: int) -> int:
        if int(value) < 1:
            raise serializers.ValidationError("单次上报测点上限必须大于 0。")
        return int(value)


class IoTGatewaySerializer(ServerDerivedCodeSerializerMixin, ReferenceIdSerializer):
    company_name = serializers.SerializerMethodField()
    connection_name = serializers.SerializerMethodField()
    equipment_name = serializers.SerializerMethodField()
    factory_name = serializers.SerializerMethodField()
    workshop_name = serializers.SerializerMethodField()
    production_line_name = serializers.SerializerMethodField()
    has_token = serializers.SerializerMethodField()
    code = serializers.CharField(allow_blank=True, default="", max_length=32, label="设备编码")

    class Meta:
        model = IoTGateway
        fields = (
            "id", "company_id", "company_name", "code", "name", "gateway_type",
            "connection_id", "connection_name", "equipment_id", "equipment_name",
            "factory_id", "factory_name", "workshop_id", "workshop_name",
            "production_line_id", "production_line_name", "location",
            "status", "last_seen_at", "offline_minutes",
            "token_prefix", "token_rotated_at", "has_token",
            "is_simulated", "is_active", "remark",
            "version", "created_at", "updated_at",
        )
        read_only_fields = (
            "id", "company_name", "connection_name", "equipment_name", "factory_name",
            "workshop_name", "production_line_name", "status", "last_seen_at",
            "token_prefix", "token_rotated_at", "has_token",
            "version", "created_at", "updated_at",
        )

    def get_company_name(self, obj: IoTGateway) -> str:
        return _name_of(obj, "company")

    def get_connection_name(self, obj: IoTGateway) -> str:
        return _name_of(obj, "connection")

    def get_equipment_name(self, obj: IoTGateway) -> str:
        return _name_of(obj, "equipment")

    def get_factory_name(self, obj: IoTGateway) -> str:
        return _name_of(obj, "factory")

    def get_workshop_name(self, obj: IoTGateway) -> str:
        return _name_of(obj, "workshop")

    def get_production_line_name(self, obj: IoTGateway) -> str:
        return _name_of(obj, "production_line")

    def get_has_token(self, obj: IoTGateway) -> bool:
        """是否已下发设备令牌；不返回令牌本身。"""
        return bool(obj.token_hash)

    def validate_code(self, value: str) -> str:
        code = (value or "").strip()
        if not code and self.instance is not None:
            raise serializers.ValidationError("设备编码不能为空。")
        return code

    def validate(self, attrs):
        connection = attrs.get("connection", getattr(self.instance, "connection", None))
        company = attrs.get("company", getattr(self.instance, "company", None))
        if connection is not None and company is not None and connection.company_id != company.pk:
            raise serializers.ValidationError({"connection_id": "该连接不属于所选公司。"})
        return attrs


class IoTPointSerializer(ServerDerivedCodeSerializerMixin, ReferenceIdSerializer):
    # 公司归属由所属数采设备推导：客户端传了也不生效，避免跨公司挂测点
    company_id = serializers.SerializerMethodField()
    company_name = serializers.SerializerMethodField()
    gateway_code = serializers.SerializerMethodField()
    gateway_name = serializers.SerializerMethodField()
    meter_code = serializers.SerializerMethodField()
    code = serializers.CharField(
        allow_blank=True, default="", max_length=32, label="测点编码",
        help_text="设备上报时使用的测点标识；留空时由系统按编码规则生成",
    )

    class Meta:
        model = IoTPoint
        fields = (
            "id", "company_id", "company_name", "gateway_id", "gateway_code", "gateway_name",
            "code", "name", "quantity", "unit", "range_min", "range_max", "precision",
            "is_cumulative", "upper_limit", "lower_limit", "alarm_enabled",
            "meter_id", "meter_code", "is_active", "remark",
            "version", "created_at", "updated_at",
        )
        read_only_fields = (
            "id", "company_id", "company_name", "gateway_code", "gateway_name", "meter_code",
            "version", "created_at", "updated_at",
        )

    def get_company_id(self, obj: IoTPoint) -> int | None:
        return obj.gateway.company_id if obj.gateway_id else None

    def get_company_name(self, obj: IoTPoint) -> str:
        return _name_of(obj, "company")

    def get_gateway_code(self, obj: IoTPoint) -> str:
        return obj.gateway.code if obj.gateway_id else ""

    def get_gateway_name(self, obj: IoTPoint) -> str:
        return obj.gateway.name if obj.gateway_id else ""

    def get_meter_code(self, obj: IoTPoint) -> str:
        return obj.meter.code if obj.meter_id else ""

    def validate_code(self, value: str) -> str:
        code = (value or "").strip()
        if not code and self.instance is not None:
            raise serializers.ValidationError("测点编码不能为空。")
        return code

    def validate(self, attrs):
        low = attrs.get("range_min", getattr(self.instance, "range_min", None))
        high = attrs.get("range_max", getattr(self.instance, "range_max", None))
        if low is not None and high is not None and low > high:
            raise serializers.ValidationError({"range_max": "量程上限不能小于下限。"})
        upper = attrs.get("upper_limit", getattr(self.instance, "upper_limit", None))
        lower = attrs.get("lower_limit", getattr(self.instance, "lower_limit", None))
        if upper is not None and lower is not None and lower > upper:
            raise serializers.ValidationError({"upper_limit": "报警上限不能小于下限。"})
        return attrs


class IoTMessageSerializer(ReferenceIdSerializer):
    """采集日志（只读）：含重复报文与处理失败报文。"""

    company_name = serializers.SerializerMethodField()
    gateway_code = serializers.SerializerMethodField()
    gateway_name = serializers.SerializerMethodField()

    class Meta:
        model = IoTMessage
        fields = (
            "id", "company_id", "company_name", "gateway_id", "gateway_code", "gateway_name",
            "message_id", "received_at", "device_time", "source_ip", "point_count",
            "status", "error_message", "is_simulated", "payload",
            "version", "created_at", "updated_at",
        )
        read_only_fields = fields

    def get_company_name(self, obj: IoTMessage) -> str:
        return _name_of(obj, "company")

    def get_gateway_code(self, obj: IoTMessage) -> str:
        return obj.gateway.code if obj.gateway_id else ""

    def get_gateway_name(self, obj: IoTMessage) -> str:
        return obj.gateway.name if obj.gateway_id else ""


class IoTReadingSerializer(ReferenceIdSerializer):
    """标准化读数（只读）。"""

    company_name = serializers.SerializerMethodField()
    gateway_code = serializers.SerializerMethodField()
    point_code = serializers.SerializerMethodField()
    point_name = serializers.SerializerMethodField()
    quantity = serializers.SerializerMethodField()

    class Meta:
        model = IoTReading
        fields = (
            "id", "company_id", "company_name", "gateway_id", "gateway_code",
            "point_id", "point_code", "point_name", "quantity",
            "device_time", "received_at", "value", "unit", "quality", "source",
            "is_simulated",
            "version", "created_at", "updated_at",
        )
        read_only_fields = fields

    def get_company_name(self, obj: IoTReading) -> str:
        return _name_of(obj, "company")

    def get_gateway_code(self, obj: IoTReading) -> str:
        return obj.gateway.code if obj.gateway_id else ""

    def get_point_code(self, obj: IoTReading) -> str:
        return obj.point.code if obj.point_id else ""

    def get_point_name(self, obj: IoTReading) -> str:
        return obj.point.name if obj.point_id else ""

    def get_quantity(self, obj: IoTReading) -> str:
        return obj.point.quantity if obj.point_id else ""


class IngestPointSerializer(serializers.Serializer):
    code = serializers.CharField(label="测点编码")
    value = serializers.CharField(label="读数", help_text="以字符串传递，避免浮点误差")


class IngestReportSerializer(serializers.Serializer):
    """HTTP 采集入口的报文格式（设备侧按此格式上报）。"""

    message_id = serializers.CharField(label="消息 ID", help_text="设备侧生成，用于判重")
    device_time = serializers.DateTimeField(
        required=False, allow_null=True, label="设备时间", help_text="留空时按平台接收时间"
    )
    simulated = serializers.BooleanField(
        required=False, default=False, label="模拟数据", help_text="模拟数据必须显式声明"
    )
    points = IngestPointSerializer(many=True, label="测点读数")


class TokenRotateSerializer(serializers.Serializer):
    """令牌轮换入参：轮换会立即让旧令牌失效，要求写明原因（进审计日志）。"""

    reason = serializers.CharField(
        required=False, allow_blank=True, default="", label="轮换原因"
    )
