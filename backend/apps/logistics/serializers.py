"""生产物流序列化器。"""

from __future__ import annotations

from rest_framework import serializers

from apps.core.serializers import ReferenceIdSerializer
from apps.factory.models import Company, Employee
from apps.logistics.models import (
    AutomationDevice,
    AutomationDeviceStatus,
    LogisticsOperationLog,
    LogisticsTask,
)
from apps.wms.models import Location

_company_id = serializers.PrimaryKeyRelatedField(
    source="company", queryset=Company.objects.all(), required=False, label="所属公司"
)


def _name_of(instance, attribute: str) -> str:
    related = getattr(instance, attribute, None)
    return str(related) if related is not None else ""


class AutomationDeviceSerializer(ReferenceIdSerializer):
    company_id = _company_id
    company_name = serializers.SerializerMethodField()
    workshop_name = serializers.SerializerMethodField()
    code = serializers.CharField(allow_blank=True, default="", max_length=32, label="设备编号")

    class Meta:
        model = AutomationDevice
        fields = (
            "id", "company_id", "company_name", "code", "name", "device_type", "status",
            "workshop_id", "workshop_name", "location", "max_load", "speed", "battery_level",
            "commissioned_date", "last_maintenance_date", "next_maintenance_date",
            "remark", "is_active", "version", "created_at", "updated_at",
        )
        read_only_fields = (
            "id", "company_name", "workshop_name", "status", "version", "created_at", "updated_at",
        )

    def get_company_name(self, obj: AutomationDevice) -> str:
        return _name_of(obj, "company")

    def get_workshop_name(self, obj: AutomationDevice) -> str:
        return _name_of(obj, "workshop")

    def validate_code(self, value: str) -> str:
        code = (value or "").strip()
        if not code and self.instance is not None:
            raise serializers.ValidationError("设备编号不能为空。")
        return code

    def validate_battery_level(self, value: int) -> int:
        if value is not None and not 0 <= value <= 100:
            raise serializers.ValidationError("电量必须在 0 到 100 之间。")
        return value


class LogisticsTaskSerializer(ReferenceIdSerializer):
    company_id = _company_id
    company_name = serializers.SerializerMethodField()
    device_code = serializers.SerializerMethodField()
    device_name = serializers.SerializerMethodField()
    warehouse_name = serializers.SerializerMethodField()
    from_location_name = serializers.SerializerMethodField()
    to_location_name = serializers.SerializerMethodField()
    material_name = serializers.SerializerMethodField()
    requested_by_name = serializers.SerializerMethodField()
    assignee_name = serializers.SerializerMethodField()
    task_no = serializers.CharField(allow_blank=True, default="", max_length=32, label="任务编号")

    class Meta:
        model = LogisticsTask
        fields = (
            "id", "company_id", "company_name", "task_no", "task_type", "device_id",
            "device_code", "device_name", "priority", "status", "warehouse_id",
            "warehouse_name", "from_location_id", "from_location_name", "to_location_id",
            "to_location_name", "material_id", "material_name", "quantity", "container_no",
            "requested_by_id", "requested_by_name", "assignee_id", "assignee_name",
            "planned_at", "dispatched_at", "started_at", "finished_at", "result", "remark",
            "version", "created_at", "updated_at",
        )
        read_only_fields = (
            "id", "company_name", "device_code", "device_name", "warehouse_name",
            "from_location_name", "to_location_name", "material_name", "requested_by_name",
            "assignee_name", "status", "dispatched_at", "started_at", "finished_at",
            "version", "created_at", "updated_at",
        )

    def get_company_name(self, obj: LogisticsTask) -> str:
        return _name_of(obj, "company")

    def get_device_code(self, obj: LogisticsTask) -> str:
        return obj.device.code if obj.device_id else ""

    def get_device_name(self, obj: LogisticsTask) -> str:
        return obj.device.name if obj.device_id else ""

    def get_warehouse_name(self, obj: LogisticsTask) -> str:
        return _name_of(obj, "warehouse")

    def get_from_location_name(self, obj: LogisticsTask) -> str:
        return _name_of(obj, "from_location")

    def get_to_location_name(self, obj: LogisticsTask) -> str:
        return _name_of(obj, "to_location")

    def get_material_name(self, obj: LogisticsTask) -> str:
        return _name_of(obj, "material")

    def get_requested_by_name(self, obj: LogisticsTask) -> str:
        return _name_of(obj, "requested_by")

    def get_assignee_name(self, obj: LogisticsTask) -> str:
        return _name_of(obj, "assignee")

    def validate_quantity(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError("数量不能为负数。")
        return value

    def validate(self, attrs):
        start = attrs.get("from_location", getattr(self.instance, "from_location", None))
        end = attrs.get("to_location", getattr(self.instance, "to_location", None))
        if start is not None and end is not None and start.pk == end.pk:
            raise serializers.ValidationError({"to_location_id": "起点库位与目标库位不能相同。"})
        return attrs


class LogisticsOperationLogSerializer(ReferenceIdSerializer):
    device_code = serializers.SerializerMethodField()
    device_name = serializers.SerializerMethodField()
    task_no = serializers.SerializerMethodField()
    operator_name = serializers.SerializerMethodField()
    company_name = serializers.SerializerMethodField()

    class Meta:
        model = LogisticsOperationLog
        fields = (
            "id", "company_id", "company_name", "device_id", "device_code", "device_name",
            "task_id", "task_no", "action", "operator_id", "operator_name", "occurred_at",
            "detail", "payload", "version", "created_at", "updated_at",
        )
        read_only_fields = fields

    def get_company_name(self, obj: LogisticsOperationLog) -> str:
        return _name_of(obj, "company")

    def get_device_code(self, obj: LogisticsOperationLog) -> str:
        return obj.device.code if obj.device_id else ""

    def get_device_name(self, obj: LogisticsOperationLog) -> str:
        return obj.device.name if obj.device_id else ""

    def get_task_no(self, obj: LogisticsOperationLog) -> str:
        return obj.task.task_no if obj.task_id else ""

    def get_operator_name(self, obj: LogisticsOperationLog) -> str:
        return _name_of(obj, "operator")


# ---------------------------------------------------------------------------
# 动作接口入参
# ---------------------------------------------------------------------------


class TaskDispatchSerializer(serializers.Serializer):
    device_id = serializers.PrimaryKeyRelatedField(
        queryset=AutomationDevice.objects.all(), required=False, allow_null=True, label="执行设备"
    )
    assignee_id = serializers.PrimaryKeyRelatedField(
        queryset=Employee.objects.all(), required=False, allow_null=True, label="执行人"
    )
    planned_at = serializers.DateTimeField(required=False, allow_null=True, label="计划执行时间")


class TaskFinishSerializer(serializers.Serializer):
    result = serializers.CharField(required=False, allow_blank=True, default="", label="执行结果")
    quantity = serializers.DecimalField(
        max_digits=20, decimal_places=6, required=False, allow_null=True, label="实际数量"
    )
    to_location_id = serializers.PrimaryKeyRelatedField(
        queryset=Location.objects.all(), required=False, allow_null=True, label="目标库位"
    )
    operator_id = serializers.PrimaryKeyRelatedField(
        queryset=Employee.objects.all(), required=False, allow_null=True, label="操作人"
    )


class TaskCancelSerializer(serializers.Serializer):
    reason = serializers.CharField(label="取消原因")
    operator_id = serializers.PrimaryKeyRelatedField(
        queryset=Employee.objects.all(), required=False, allow_null=True, label="操作人"
    )


class DeviceStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=AutomationDeviceStatus.choices, label="设备状态")
    battery_level = serializers.IntegerField(
        required=False, allow_null=True, min_value=0, max_value=100, label="电量（%）"
    )
    detail = serializers.CharField(required=False, allow_blank=True, default="", label="说明")
    operator_id = serializers.PrimaryKeyRelatedField(
        queryset=Employee.objects.all(), required=False, allow_null=True, label="操作人"
    )


class TaskStartSerializer(serializers.Serializer):
    operator_id = serializers.PrimaryKeyRelatedField(
        queryset=Employee.objects.all(), required=False, allow_null=True, label="操作人"
    )
