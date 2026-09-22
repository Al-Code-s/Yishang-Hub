"""能源管理序列化器。

约定：

* 枚举字段的中文标签由 ``DisplayLabelsMixin`` 自动补 ``<field>_display``，
  前端不硬编码中文；
* ``company_id`` 声明为可写外键，越权写入仍由视图 ``assert_in_scope`` 拦截；
* 抄表、开始/结束运行、报警处理都走**动作接口 + 服务层**，
  不允许直接 PATCH ``status`` 跳步（因此这些字段在序列化器里是只读的）。
"""

from __future__ import annotations

from rest_framework import serializers

from apps.core.serializers import ReferenceIdSerializer
from apps.ems.models import (
    AlarmLevel,
    AlarmStatus,
    AlarmType,
    EnergyAlarm,
    EnergyArea,
    EnergyMeter,
    EnergyPrice,
    EnergyRunRecord,
    EnergyThreshold,
    MeterReading,
    MeterStatus,
    ReadingSource,
    TariffPeriod,
)
from apps.equipment.models import Equipment
from apps.factory.models import Company, Employee

_company_id = serializers.PrimaryKeyRelatedField(
    source="company", queryset=Company.objects.all(), required=False, label="所属公司"
)


def _name_of(instance, attribute: str) -> str:
    related = getattr(instance, attribute, None)
    return str(related) if related is not None else ""


class EnergyAreaSerializer(ReferenceIdSerializer):
    parent_name = serializers.SerializerMethodField()
    department_name = serializers.SerializerMethodField()
    manager_name = serializers.SerializerMethodField()

    class Meta:
        model = EnergyArea
        fields = (
            "id", "company_id", "company_name", "code", "name", "parent_id", "parent_name",
            "department_id", "department_name", "manager_id", "manager_name", "area_size",
            "remark", "is_active", "version", "created_at", "updated_at",
        )
        read_only_fields = (
            "id", "company_name", "parent_name", "department_name",
            "manager_name", "version", "created_at", "updated_at",
        )

    company_id = _company_id
    company_name = serializers.SerializerMethodField()

    def get_company_name(self, obj: EnergyArea) -> str:
        return _name_of(obj, "company")

    def get_parent_name(self, obj: EnergyArea) -> str:
        return _name_of(obj, "parent")

    def get_department_name(self, obj: EnergyArea) -> str:
        return _name_of(obj, "department")

    def get_manager_name(self, obj: EnergyArea) -> str:
        return _name_of(obj, "manager")

    def validate_code(self, value: str) -> str:
        code = (value or "").strip()
        if not code:
            raise serializers.ValidationError("区域编码不能为空。")
        return code

    def validate(self, attrs):
        parent = attrs.get("parent", getattr(self.instance, "parent", None))
        if parent is not None and self.instance is not None and parent.pk == self.instance.pk:
            raise serializers.ValidationError({"parent_id": "上级区域不能是自己。"})
        return attrs


class EnergyMeterSerializer(ReferenceIdSerializer):
    company_id = _company_id
    company_name = serializers.SerializerMethodField()
    area_name = serializers.SerializerMethodField()
    department_name = serializers.SerializerMethodField()
    equipment_name = serializers.SerializerMethodField()
    code = serializers.CharField(allow_blank=True, default="", max_length=32, label="仪表编码")

    class Meta:
        model = EnergyMeter
        fields = (
            "id", "company_id", "company_name", "code", "name", "medium", "area_id",
            "area_name", "equipment_id", "equipment_name", "department_id", "department_name",
            "meter_model", "serial_no", "multiplier", "unit", "status", "location",
            "install_date", "last_reading_at", "is_monitored", "remark", "is_active",
            "version", "created_at", "updated_at",
        )
        read_only_fields = (
            "id", "company_name", "area_name", "department_name", "equipment_name",
            "last_reading_at", "version", "created_at", "updated_at",
        )

    def get_company_name(self, obj: EnergyMeter) -> str:
        return _name_of(obj, "company")

    def get_area_name(self, obj: EnergyMeter) -> str:
        return _name_of(obj, "area")

    def get_department_name(self, obj: EnergyMeter) -> str:
        return _name_of(obj, "department")

    def get_equipment_name(self, obj: EnergyMeter) -> str:
        return _name_of(obj, "equipment")

    def validate_code(self, value: str) -> str:
        code = (value or "").strip()
        if not code and self.instance is not None:
            raise serializers.ValidationError("仪表编码不能为空。")
        return code

    def validate_multiplier(self, value):
        if value is not None and value <= 0:
            raise serializers.ValidationError("倍率必须大于 0。")
        return value


class EnergyPriceSerializer(ReferenceIdSerializer):
    company_id = _company_id
    company_name = serializers.SerializerMethodField()

    class Meta:
        model = EnergyPrice
        fields = (
            "id", "company_id", "company_name", "medium", "tariff_period", "name",
            "unit_price", "currency_unit", "effective_from", "effective_to", "remark",
            "is_active", "version", "created_at", "updated_at",
        )
        read_only_fields = ("id", "company_name", "version", "created_at", "updated_at")

    def get_company_name(self, obj: EnergyPrice) -> str:
        return _name_of(obj, "company")

    def validate_unit_price(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError("单价不能为负数。")
        return value

    def validate(self, attrs):
        start = attrs.get("effective_from", getattr(self.instance, "effective_from", None))
        end = attrs.get("effective_to", getattr(self.instance, "effective_to", None))
        if start and end and end < start:
            raise serializers.ValidationError({"effective_to": "失效日期不能早于生效日期。"})
        return attrs


class EnergyThresholdSerializer(ReferenceIdSerializer):
    company_id = _company_id
    company_name = serializers.SerializerMethodField()
    meter_name = serializers.SerializerMethodField()

    class Meta:
        model = EnergyThreshold
        fields = (
            "id", "company_id", "company_name", "name", "medium", "meter_id", "meter_name",
            "upper_limit", "lower_limit", "daily_limit", "unit_consumption_limit",
            "offline_minutes", "alarm_level", "remark", "is_active",
            "version", "created_at", "updated_at",
        )
        read_only_fields = ("id", "company_name", "meter_name", "version", "created_at", "updated_at")

    def get_company_name(self, obj: EnergyThreshold) -> str:
        return _name_of(obj, "company")

    def get_meter_name(self, obj: EnergyThreshold) -> str:
        return _name_of(obj, "meter")

    def validate(self, attrs):
        lower = attrs.get("lower_limit", getattr(self.instance, "lower_limit", None))
        upper = attrs.get("upper_limit", getattr(self.instance, "upper_limit", None))
        if lower is not None and upper is not None and lower >= upper:
            raise serializers.ValidationError({"upper_limit": "读数上限必须大于下限。"})
        return attrs


class MeterReadingSerializer(ReferenceIdSerializer):
    company_id = _company_id
    company_name = serializers.SerializerMethodField()
    meter_code = serializers.SerializerMethodField()
    meter_name = serializers.SerializerMethodField()
    medium = serializers.SerializerMethodField()
    unit = serializers.SerializerMethodField()
    recorder_name = serializers.SerializerMethodField()

    class Meta:
        model = MeterReading
        fields = (
            "id", "company_id", "company_name", "meter_id", "meter_code", "meter_name",
            "medium", "unit", "reading_at", "reading", "consumption", "tariff_period",
            "source", "recorder_id", "recorder_name", "note",
            "version", "created_at", "updated_at",
        )
        read_only_fields = (
            "id", "company_name", "meter_code", "meter_name", "medium", "unit",
            "consumption", "recorder_name", "version", "created_at", "updated_at",
        )

    def get_company_name(self, obj: MeterReading) -> str:
        return _name_of(obj, "company")

    def get_meter_code(self, obj: MeterReading) -> str:
        return obj.meter.code if obj.meter_id else ""

    def get_meter_name(self, obj: MeterReading) -> str:
        return obj.meter.name if obj.meter_id else ""

    def get_medium(self, obj: MeterReading) -> str:
        return obj.meter.medium if obj.meter_id else ""

    def get_unit(self, obj: MeterReading) -> str:
        return obj.meter.unit if obj.meter_id else ""

    def get_recorder_name(self, obj: MeterReading) -> str:
        return _name_of(obj, "recorder")


class EnergyRunRecordSerializer(ReferenceIdSerializer):
    company_id = _company_id
    company_name = serializers.SerializerMethodField()
    meter_code = serializers.SerializerMethodField()
    meter_name = serializers.SerializerMethodField()
    unit = serializers.SerializerMethodField()
    equipment_name = serializers.SerializerMethodField()
    operator_name = serializers.SerializerMethodField()
    record_no = serializers.CharField(allow_blank=True, default="", max_length=32, label="记录编号")

    class Meta:
        model = EnergyRunRecord
        fields = (
            "id", "company_id", "company_name", "record_no", "meter_id", "meter_code",
            "meter_name", "unit", "equipment_id", "equipment_name", "status", "started_at",
            "finished_at", "run_minutes", "output_desc", "output_qty", "energy_consumption",
            "unit_consumption", "operator_id", "operator_name", "remark",
            "version", "created_at", "updated_at",
        )
        read_only_fields = (
            "id", "company_name", "meter_code", "meter_name", "unit", "equipment_name",
            "status", "finished_at", "run_minutes", "unit_consumption", "operator_name",
            "version", "created_at", "updated_at",
        )

    def get_company_name(self, obj: EnergyRunRecord) -> str:
        return _name_of(obj, "company")

    def get_meter_code(self, obj: EnergyRunRecord) -> str:
        return obj.meter.code if obj.meter_id else ""

    def get_meter_name(self, obj: EnergyRunRecord) -> str:
        return obj.meter.name if obj.meter_id else ""

    def get_unit(self, obj: EnergyRunRecord) -> str:
        return obj.meter.unit if obj.meter_id else ""

    def get_equipment_name(self, obj: EnergyRunRecord) -> str:
        return _name_of(obj, "equipment")

    def get_operator_name(self, obj: EnergyRunRecord) -> str:
        return _name_of(obj, "operator")


class EnergyAlarmSerializer(ReferenceIdSerializer):
    company_id = _company_id
    company_name = serializers.SerializerMethodField()
    meter_code = serializers.SerializerMethodField()
    meter_name = serializers.SerializerMethodField()
    area_name = serializers.SerializerMethodField()
    handler_name = serializers.SerializerMethodField()
    alarm_no = serializers.CharField(allow_blank=True, default="", max_length=32, label="报警编号")

    class Meta:
        model = EnergyAlarm
        fields = (
            "id", "company_id", "company_name", "alarm_no", "meter_id", "meter_code",
            "meter_name", "area_id", "area_name", "alarm_type", "level", "status", "source",
            "source_ref", "occurred_at", "message", "triggered_value", "threshold_value", "handler_id",
            "handler_name", "handled_at", "handle_note", "closed_at", "remark",
            "version", "created_at", "updated_at",
        )
        read_only_fields = (
            "id", "company_name", "meter_code", "meter_name", "area_name", "status",
            "source", "handled_at", "closed_at", "handler_name",
            "version", "created_at", "updated_at",
        )

    def get_company_name(self, obj: EnergyAlarm) -> str:
        return _name_of(obj, "company")

    def get_meter_code(self, obj: EnergyAlarm) -> str:
        return obj.meter.code if obj.meter_id else ""

    def get_meter_name(self, obj: EnergyAlarm) -> str:
        return obj.meter.name if obj.meter_id else ""

    def get_area_name(self, obj: EnergyAlarm) -> str:
        return _name_of(obj, "area")

    def get_handler_name(self, obj: EnergyAlarm) -> str:
        return _name_of(obj, "handler")


# ---------------------------------------------------------------------------
# 动作接口入参
# ---------------------------------------------------------------------------


class ReadingRecordSerializer(serializers.Serializer):
    """抄表录入。用量由服务层按上次读数计算，客户端不能直接指定。"""

    meter_id = serializers.PrimaryKeyRelatedField(
        queryset=EnergyMeter.objects.all(), label="计量设备"
    )
    reading = serializers.DecimalField(max_digits=20, decimal_places=6, label="表底读数")
    reading_at = serializers.DateTimeField(required=False, allow_null=True, label="抄表时间")
    tariff_period = serializers.ChoiceField(
        choices=TariffPeriod.choices, required=False, default=TariffPeriod.FLAT, label="时段"
    )
    source = serializers.ChoiceField(
        choices=ReadingSource.choices, required=False, default=ReadingSource.MANUAL, label="数据来源"
    )
    recorder_id = serializers.PrimaryKeyRelatedField(
        queryset=Employee.objects.all(), required=False, allow_null=True, label="抄表人"
    )
    note = serializers.CharField(required=False, allow_blank=True, default="", label="备注")


class RunStartSerializer(serializers.Serializer):
    """开始设备运行记录。"""

    meter_id = serializers.PrimaryKeyRelatedField(
        queryset=EnergyMeter.objects.all(), label="计量设备"
    )
    equipment_id = serializers.PrimaryKeyRelatedField(
        queryset=Equipment.objects.all(),
        required=False,
        allow_null=True,
        label="设备",
    )
    started_at = serializers.DateTimeField(required=False, allow_null=True, label="开始时间")
    operator_id = serializers.PrimaryKeyRelatedField(
        queryset=Employee.objects.all(), required=False, allow_null=True, label="操作人"
    )
    output_desc = serializers.CharField(
        required=False, allow_blank=True, default="", label="产量说明"
    )
    remark = serializers.CharField(required=False, allow_blank=True, default="", label="备注")


class RunFinishSerializer(serializers.Serializer):
    """结束设备运行记录。"""

    finished_at = serializers.DateTimeField(required=False, allow_null=True, label="结束时间")
    output_qty = serializers.DecimalField(
        max_digits=20, decimal_places=6, required=False, allow_null=True, label="产量"
    )
    output_desc = serializers.CharField(required=False, allow_blank=True, label="产量说明")
    energy_consumption = serializers.DecimalField(
        max_digits=20,
        decimal_places=6,
        required=False,
        allow_null=True,
        label="能耗用量（留空时按抄表区间自动汇总）",
    )


class RunCancelSerializer(serializers.Serializer):
    """取消设备运行记录。"""

    reason = serializers.CharField(label="取消原因")


class AlarmHandleSerializer(serializers.Serializer):
    """开始处理报警。"""

    handler_id = serializers.PrimaryKeyRelatedField(
        queryset=Employee.objects.all(), required=False, allow_null=True, label="处理人"
    )
    note = serializers.CharField(required=False, allow_blank=True, default="", label="处理说明")


class AlarmCloseSerializer(serializers.Serializer):
    """关闭报警。"""

    note = serializers.CharField(label="处理说明")


class AlarmCreateSerializer(serializers.Serializer):
    """人工上报报警（与系统自动报警区分 source）。"""

    company_id = serializers.PrimaryKeyRelatedField(
        queryset=Company.objects.all(), required=False, label="所属公司"
    )
    meter_id = serializers.PrimaryKeyRelatedField(
        queryset=EnergyMeter.objects.all(), required=False, allow_null=True, label="计量设备"
    )
    alarm_type = serializers.ChoiceField(choices=AlarmType.choices, label="报警类型")
    level = serializers.ChoiceField(
        choices=AlarmLevel.choices, required=False, default=AlarmLevel.WARNING, label="报警级别"
    )
    occurred_at = serializers.DateTimeField(required=False, allow_null=True, label="发生时间")
    message = serializers.CharField(max_length=255, label="报警内容")
    triggered_value = serializers.DecimalField(
        max_digits=20, decimal_places=6, required=False, allow_null=True, label="触发值"
    )
    threshold_value = serializers.DecimalField(
        max_digits=20, decimal_places=6, required=False, allow_null=True, label="阈值"
    )
    remark = serializers.CharField(required=False, allow_blank=True, default="", label="备注")


__all__ = [
    "AlarmCloseSerializer",
    "AlarmCreateSerializer",
    "AlarmHandleSerializer",
    "EnergyAlarmSerializer",
    "EnergyAreaSerializer",
    "EnergyMeterSerializer",
    "EnergyPriceSerializer",
    "EnergyRunRecordSerializer",
    "EnergyThresholdSerializer",
    "MeterReadingSerializer",
    "MeterStatus",
    "AlarmStatus",
    "ReadingRecordSerializer",
    "RunCancelSerializer",
    "RunFinishSerializer",
    "RunStartSerializer",
]
