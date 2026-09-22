from __future__ import annotations

from rest_framework import serializers

from apps.core.constants import MONEY_DECIMAL_PLACES, MONEY_MAX_DIGITS
from apps.core.serializers import ReferenceIdSerializer, ServerDerivedCodeSerializerMixin
from apps.equipment.models import (
    AbnormalRecord,
    AbnormalTask,
    AbnormalType,
    Equipment,
    EquipmentPart,
    EquipmentType,
    FaultLevel,
    FaultReport,
    InspectionItem,
    InspectionRecord,
    InspectionTask,
    MaintenanceItem,
    MaintenancePlan,
    MaintenanceRecord,
    MaintenanceTask,
    RepairRecord,
    RepairTask,
    SparePart,
)
from apps.factory.models import Company, Employee


class DerivedCompanySerializerMixin(ServerDerivedCodeSerializerMixin):
    """公司由服务端推导的编号类序列化器基类。

    设备模块的具体场景：公司归属由设备（或来源单据）推导、保养 / 点巡检任务的
    「来源计划」本来就可以为空，客户端不会传这些字段，于是新增会被 DRF 自动派生的
    UniqueTogetherValidator 用一句「该字段是必填项」挡在门外（页面上连填的地方都没有）。

    规则本体（关闭自动派生的唯一性校验、重复数据由数据库唯一约束兜底）已上移到
    ``apps.core.serializers.ServerDerivedCodeSerializerMixin``，供客户投诉、
    设备数采等同样「编号由服务端推导」的模块共用；这里保留模块名以便既有代码与
    文档继续引用。由客户端显式指定公司的对象（设备台账、备品备件）不受影响。
    """


class EquipmentTypeSerializer(ReferenceIdSerializer):
    class Meta:
        model = EquipmentType
        fields = (
            "id", "code", "name", "category", "is_special", "maintenance_cycle_days",
            "remark", "is_active", "version", "created_at", "updated_at",
        )
        read_only_fields = ("id", "version", "created_at", "updated_at")

    def validate_code(self, value: str) -> str:
        code = (value or "").strip()
        if not code:
            raise serializers.ValidationError("类型编码不能为空。")
        return code

    def validate_name(self, value: str) -> str:
        name = (value or "").strip()
        if not name:
            raise serializers.ValidationError("类型名称不能为空。")
        return name


class EquipmentSerializer(ReferenceIdSerializer):
    equipment_type_name = serializers.SerializerMethodField()
    company_name = serializers.SerializerMethodField()
    factory_name = serializers.SerializerMethodField()
    workshop_name = serializers.SerializerMethodField()
    production_line_name = serializers.SerializerMethodField()
    station_name = serializers.SerializerMethodField()
    supplier_name = serializers.SerializerMethodField()
    owner_department_name = serializers.SerializerMethodField()
    owner_employee_name = serializers.SerializerMethodField()
    # 新增时允许留空：由视图层按编码规则（EQ）自动取号；编辑时仍必填，
    # 避免把已有设备改成空编号而破坏「同公司内编号唯一」。
    code = serializers.CharField(allow_blank=True, default="", max_length=32, label="设备编号")

    class Meta:
        model = Equipment
        fields = (
            "id", "company_id", "company_name", "code", "name",
            "equipment_type_id", "equipment_type_name", "status",
            "factory_id", "factory_name", "workshop_id", "workshop_name",
            "production_line_id", "production_line_name", "station_id", "station_name",
            "location", "brand", "model_no", "serial_no", "supplier_id", "supplier_name",
            "purchase_date", "start_date", "original_value", "warranty_until", "is_special",
            "owner_department_id", "owner_department_name",
            "owner_employee_id", "owner_employee_name",
            "remark", "is_active", "version", "created_at", "updated_at",
        )
        read_only_fields = (
            "id", "company_name", "equipment_type_name", "factory_name", "workshop_name",
            "production_line_name", "station_name", "supplier_name",
            "owner_department_name", "owner_employee_name",
            "version", "created_at", "updated_at",
        )

    def get_equipment_type_name(self, obj: Equipment) -> str:
        return obj.equipment_type.name if obj.equipment_type_id else ""

    def get_company_name(self, obj: Equipment) -> str:
        return obj.company.name if obj.company_id else ""

    def get_factory_name(self, obj: Equipment) -> str:
        return obj.factory.name if obj.factory_id else ""

    def get_workshop_name(self, obj: Equipment) -> str:
        return obj.workshop.name if obj.workshop_id else ""

    def get_production_line_name(self, obj: Equipment) -> str:
        return obj.production_line.name if obj.production_line_id else ""

    def get_station_name(self, obj: Equipment) -> str:
        return obj.station.name if obj.station_id else ""

    def get_supplier_name(self, obj: Equipment) -> str:
        return obj.supplier.name if obj.supplier_id else ""

    def get_owner_department_name(self, obj: Equipment) -> str:
        return obj.owner_department.name if obj.owner_department_id else ""

    def get_owner_employee_name(self, obj: Equipment) -> str:
        return obj.owner_employee.name if obj.owner_employee_id else ""

    def validate_code(self, value: str) -> str:
        code = (value or "").strip()
        if not code and self.instance is not None:
            raise serializers.ValidationError("设备编号不能为空。")
        return code

    def validate_original_value(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError("资产原值不能为负数。")
        return value

    def validate(self, attrs):
        """线体必须属于所选车间、工位必须属于所选线体，避免台账挂错层级。"""
        factory = attrs.get("factory", getattr(self.instance, "factory", None))
        workshop = attrs.get("workshop", getattr(self.instance, "workshop", None))
        line = attrs.get("production_line", getattr(self.instance, "production_line", None))
        station = attrs.get("station", getattr(self.instance, "station", None))
        if workshop is not None and factory is not None and workshop.factory_id != factory.id:
            raise serializers.ValidationError({"workshop_id": "所选车间不属于该工厂。"})
        if line is not None and workshop is not None and line.workshop_id != workshop.id:
            raise serializers.ValidationError({"production_line_id": "所选线体不属于该车间。"})
        if station is not None and line is not None and station.line_id != line.id:
            raise serializers.ValidationError({"station_id": "所选工位不属于该线体。"})
        return attrs


class EquipmentPartSerializer(ReferenceIdSerializer):
    equipment_name = serializers.SerializerMethodField()
    company_id = serializers.SerializerMethodField()
    uom_name = serializers.SerializerMethodField()

    class Meta:
        model = EquipmentPart
        fields = (
            "id", "equipment_id", "equipment_name", "company_id", "name", "part_type",
            "spec", "quantity", "uom_id", "uom_name", "position", "life_days",
            "remark", "is_active", "version", "created_at", "updated_at",
        )
        read_only_fields = (
            "id", "equipment_name", "company_id", "uom_name",
            "version", "created_at", "updated_at",
        )

    def get_equipment_name(self, obj: EquipmentPart) -> str:
        return obj.equipment.name if obj.equipment_id else ""

    def get_company_id(self, obj: EquipmentPart) -> int | None:
        return obj.equipment.company_id if obj.equipment_id else None

    def get_uom_name(self, obj: EquipmentPart) -> str:
        return obj.uom.name if obj.uom_id else ""

    def validate_name(self, value: str) -> str:
        name = (value or "").strip()
        if not name:
            raise serializers.ValidationError("零部件名称不能为空。")
        return name

    def validate_quantity(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError("数量不能为负数。")
        return value

    def validate(self, attrs):
        equipment = attrs.get("equipment", getattr(self.instance, "equipment", None))
        name = attrs.get("name", getattr(self.instance, "name", None))
        if equipment is not None and name:
            duplicated = EquipmentPart.objects.filter(equipment=equipment, name=name)
            if self.instance is not None:
                duplicated = duplicated.exclude(pk=self.instance.pk)
            if duplicated.exists():
                raise serializers.ValidationError({"name": "该设备下已存在同名零部件。"})
        return attrs


class SparePartSerializer(ReferenceIdSerializer):
    material_name = serializers.SerializerMethodField()
    equipment_type_name = serializers.SerializerMethodField()
    company_name = serializers.SerializerMethodField()
    uom_name = serializers.SerializerMethodField()
    supplier_name = serializers.SerializerMethodField()
    code = serializers.CharField(allow_blank=True, default="", max_length=32, label="备件编码")

    class Meta:
        model = SparePart
        fields = (
            "id", "company_id", "company_name", "code", "name", "part_type", "spec",
            "material_id", "material_name", "equipment_type_id", "equipment_type_name",
            "uom_id", "uom_name", "safety_stock", "reference_price", "life_days",
            "supplier_id", "supplier_name", "remark", "is_active",
            "version", "created_at", "updated_at",
        )
        read_only_fields = (
            "id", "company_name", "material_name", "equipment_type_name", "uom_name",
            "supplier_name", "version", "created_at", "updated_at",
        )

    def get_material_name(self, obj: SparePart) -> str:
        return obj.material.name if obj.material_id else ""

    def get_equipment_type_name(self, obj: SparePart) -> str:
        return obj.equipment_type.name if obj.equipment_type_id else ""

    def get_company_name(self, obj: SparePart) -> str:
        return obj.company.name if obj.company_id else ""

    def get_uom_name(self, obj: SparePart) -> str:
        return obj.uom.name if obj.uom_id else ""

    def get_supplier_name(self, obj: SparePart) -> str:
        return obj.supplier.name if obj.supplier_id else ""

    def validate_code(self, value: str) -> str:
        code = (value or "").strip()
        if not code and self.instance is not None:
            raise serializers.ValidationError("备件编码不能为空。")
        return code

    def validate_safety_stock(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError("安全库存不能为负数。")
        return value

    def validate_reference_price(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError("参考单价不能为负数。")
        return value

# 新实体统一由「设备 / 计划 / 任务」推导公司归属，避免前端漏传公司造成跨公司写入；
# 字段声明为可选，取值在视图的 perform_create 中完成后端推导（见 views.py）。
_company_id = serializers.PrimaryKeyRelatedField(
    source="company", queryset=Company.objects.all(), required=False, label="所属公司"
)


def _name_of(instance, attribute: str) -> str:
    """安全取外键显示名：字段为空时返回空串，不抛异常。"""
    related = getattr(instance, attribute, None)
    return str(related) if related is not None else ""


class MaintenanceItemSerializer(ReferenceIdSerializer):
    equipment_type_name = serializers.SerializerMethodField()

    class Meta:
        model = MaintenanceItem
        fields = (
            "id", "code", "name", "category", "equipment_type_id", "equipment_type_name",
            "cycle_days", "standard", "is_active", "remark",
            "version", "created_at", "updated_at",
        )
        read_only_fields = ("id", "equipment_type_name", "version", "created_at", "updated_at")

    def get_equipment_type_name(self, obj) -> str:
        return _name_of(obj, "equipment_type")

    def validate_code(self, value: str) -> str:
        code = (value or "").strip()
        if not code:
            raise serializers.ValidationError("项目编码不能为空。")
        return code


class MaintenancePlanSerializer(DerivedCompanySerializerMixin, ReferenceIdSerializer):
    # 编号留空时由视图层按编码规则（MP）自动取号，前端不必手工填写。
    plan_no = serializers.CharField(allow_blank=True, default="", max_length=32, label="计划编号")
    company_id = _company_id
    company_name = serializers.SerializerMethodField()
    equipment_name = serializers.SerializerMethodField()
    responsible_employee_name = serializers.SerializerMethodField()
    department_name = serializers.SerializerMethodField()
    item_ids = serializers.PrimaryKeyRelatedField(
        source="items", queryset=MaintenanceItem.objects.all(), many=True, required=False
    )
    item_names = serializers.SerializerMethodField()

    class Meta:
        model = MaintenancePlan
        fields = (
            "id", "company_id", "company_name", "plan_no", "name",
            "equipment_id", "equipment_name", "cycle_days", "start_date", "next_date",
            "item_ids", "item_names",
            "responsible_employee_id", "responsible_employee_name",
            "department_id", "department_name", "is_active", "remark",
            "version", "created_at", "updated_at",
        )
        read_only_fields = (
            "id", "company_name", "equipment_name", "item_names",
            "responsible_employee_name", "department_name",
            "version", "created_at", "updated_at",
        )

    def get_company_name(self, obj) -> str:
        return _name_of(obj, "company")

    def get_equipment_name(self, obj) -> str:
        return _name_of(obj, "equipment")

    def get_responsible_employee_name(self, obj) -> str:
        return _name_of(obj, "responsible_employee")

    def get_department_name(self, obj) -> str:
        return _name_of(obj, "department")

    def get_item_names(self, obj) -> str:
        return "、".join(item.name for item in obj.items.all())

    def validate_cycle_days(self, value: int) -> int:
        if value is None or int(value) <= 0:
            raise serializers.ValidationError("保养周期必须大于 0 天。")
        return value


class MaintenanceTaskSerializer(DerivedCompanySerializerMixin, ReferenceIdSerializer):
    # 编号留空时由视图层按编码规则（MT）自动取号；同步生成任务时同样走这条路径。
    task_no = serializers.CharField(allow_blank=True, default="", max_length=32, label="任务编号")
    company_id = _company_id
    company_name = serializers.SerializerMethodField()
    equipment_name = serializers.SerializerMethodField()
    item_name = serializers.SerializerMethodField()
    plan_no = serializers.SerializerMethodField()
    assignee_name = serializers.SerializerMethodField()

    class Meta:
        model = MaintenanceTask
        fields = (
            "id", "company_id", "company_name", "task_no", "plan_id", "plan_no",
            "equipment_id", "equipment_name", "item_id", "item_name",
            "plan_date", "status", "assignee_id", "assignee_name",
            "started_at", "finished_at", "result", "remark",
            "version", "created_at", "updated_at",
        )
        read_only_fields = (
            "id", "company_name", "equipment_name", "item_name", "plan_no",
            "assignee_name", "status", "version", "created_at", "updated_at",
        )

    def get_company_name(self, obj) -> str:
        return _name_of(obj, "company")

    def get_equipment_name(self, obj) -> str:
        return _name_of(obj, "equipment")

    def get_item_name(self, obj) -> str:
        return _name_of(obj, "item")

    def get_plan_no(self, obj) -> str:
        return obj.plan.plan_no if obj.plan_id else ""

    def get_assignee_name(self, obj) -> str:
        return _name_of(obj, "assignee")


class MaintenanceRecordSerializer(DerivedCompanySerializerMixin, ReferenceIdSerializer):
    # 编号留空时由视图层按编码规则（MR）自动取号。
    record_no = serializers.CharField(allow_blank=True, default="", max_length=32, label="记录编号")
    company_id = _company_id
    company_name = serializers.SerializerMethodField()
    equipment_name = serializers.SerializerMethodField()
    item_name = serializers.SerializerMethodField()
    executor_name = serializers.SerializerMethodField()

    class Meta:
        model = MaintenanceRecord
        fields = (
            "id", "company_id", "company_name", "record_no", "task_id", "equipment_id",
            "equipment_name", "item_id", "item_name", "maintain_date",
            "executor_id", "executor_name", "content", "result", "is_qualified",
            "cost", "remark", "version", "created_at", "updated_at",
        )
        read_only_fields = (
            "id", "company_name", "equipment_name", "item_name", "executor_name",
            "version", "created_at", "updated_at",
        )

    def get_company_name(self, obj) -> str:
        return _name_of(obj, "company")

    def get_equipment_name(self, obj) -> str:
        return _name_of(obj, "equipment")

    def get_item_name(self, obj) -> str:
        return _name_of(obj, "item")

    def get_executor_name(self, obj) -> str:
        return _name_of(obj, "executor")

    def validate_cost(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError("保养费用不能为负数。")
        return value


class FaultReportSerializer(DerivedCompanySerializerMixin, ReferenceIdSerializer):
    # 编号留空时由视图层按编码规则（FR）自动取号。
    report_no = serializers.CharField(allow_blank=True, default="", max_length=32, label="报修单号")
    company_id = _company_id
    company_name = serializers.SerializerMethodField()
    equipment_name = serializers.SerializerMethodField()
    reporter_name = serializers.SerializerMethodField()

    class Meta:
        model = FaultReport
        fields = (
            "id", "company_id", "company_name", "report_no", "equipment_id",
            "equipment_name", "level", "description", "reporter_id", "reporter_name",
            "reported_at", "status", "closed_at", "remark",
            "version", "created_at", "updated_at",
        )
        read_only_fields = (
            "id", "company_name", "equipment_name", "reporter_name",
            "status", "closed_at", "version", "created_at", "updated_at",
        )

    def get_company_name(self, obj) -> str:
        return _name_of(obj, "company")

    def get_equipment_name(self, obj) -> str:
        return _name_of(obj, "equipment")

    def get_reporter_name(self, obj) -> str:
        return _name_of(obj, "reporter")


class RepairTaskSerializer(DerivedCompanySerializerMixin, ReferenceIdSerializer):
    # 编号留空时由视图层按编码规则（RT）自动取号。
    task_no = serializers.CharField(allow_blank=True, default="", max_length=32, label="任务编号")
    company_id = _company_id
    company_name = serializers.SerializerMethodField()
    equipment_name = serializers.SerializerMethodField()
    report_no = serializers.SerializerMethodField()
    assignee_name = serializers.SerializerMethodField()

    class Meta:
        model = RepairTask
        fields = (
            "id", "company_id", "company_name", "task_no", "fault_report_id", "report_no",
            "equipment_id", "equipment_name", "symptom", "level",
            "assignee_id", "assignee_name", "assigned_date", "status",
            "started_at", "finished_at", "downtime_minutes", "remark",
            "version", "created_at", "updated_at",
        )
        read_only_fields = (
            "id", "company_name", "equipment_name", "report_no", "assignee_name",
            "status", "version", "created_at", "updated_at",
        )

    def get_company_name(self, obj) -> str:
        return _name_of(obj, "company")

    def get_equipment_name(self, obj) -> str:
        return _name_of(obj, "equipment")

    def get_report_no(self, obj) -> str:
        return obj.fault_report.report_no if obj.fault_report_id else ""

    def get_assignee_name(self, obj) -> str:
        return _name_of(obj, "assignee")


class RepairRecordSerializer(DerivedCompanySerializerMixin, ReferenceIdSerializer):
    # 编号留空时由视图层按编码规则（RR）自动取号。
    record_no = serializers.CharField(allow_blank=True, default="", max_length=32, label="记录编号")
    company_id = _company_id
    company_name = serializers.SerializerMethodField()
    equipment_name = serializers.SerializerMethodField()
    task_no = serializers.SerializerMethodField()
    repairer_name = serializers.SerializerMethodField()

    class Meta:
        model = RepairRecord
        fields = (
            "id", "company_id", "company_name", "record_no", "task_id", "task_no",
            "equipment_id", "equipment_name", "repair_date", "repairer_id", "repairer_name",
            "fault_reason", "solution", "parts_used", "cost", "downtime_minutes",
            "result", "remark", "version", "created_at", "updated_at",
        )
        read_only_fields = (
            "id", "company_name", "equipment_name", "task_no", "repairer_name",
            "version", "created_at", "updated_at",
        )

    def get_company_name(self, obj) -> str:
        return _name_of(obj, "company")

    def get_equipment_name(self, obj) -> str:
        return _name_of(obj, "equipment")

    def get_task_no(self, obj) -> str:
        return obj.task.task_no if obj.task_id else ""

    def get_repairer_name(self, obj) -> str:
        return _name_of(obj, "repairer")

    def validate_cost(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError("维修费用不能为负数。")
        return value


class InspectionItemSerializer(ReferenceIdSerializer):
    uom_name = serializers.SerializerMethodField()

    class Meta:
        model = InspectionItem
        fields = (
            "id", "code", "name", "method", "standard", "uom_id", "uom_name",
            "lower_limit", "upper_limit", "is_active", "remark",
            "version", "created_at", "updated_at",
        )
        read_only_fields = ("id", "uom_name", "version", "created_at", "updated_at")

    def get_uom_name(self, obj) -> str:
        return _name_of(obj, "uom")

    def validate_code(self, value: str) -> str:
        code = (value or "").strip()
        if not code:
            raise serializers.ValidationError("项目编码不能为空。")
        return code

    def validate(self, attrs):
        lower = attrs.get("lower_limit", getattr(self.instance, "lower_limit", None))
        upper = attrs.get("upper_limit", getattr(self.instance, "upper_limit", None))
        if lower is not None and upper is not None and lower > upper:
            raise serializers.ValidationError({"lower_limit": "下限不能大于上限。"})
        return attrs


class InspectionTaskSerializer(DerivedCompanySerializerMixin, ReferenceIdSerializer):
    # 编号留空时由视图层按编码规则（IT）自动取号。
    task_no = serializers.CharField(allow_blank=True, default="", max_length=32, label="任务编号")
    company_id = _company_id
    company_name = serializers.SerializerMethodField()
    equipment_name = serializers.SerializerMethodField()
    assignee_name = serializers.SerializerMethodField()
    item_ids = serializers.PrimaryKeyRelatedField(
        source="items", queryset=InspectionItem.objects.all(), many=True, required=False
    )
    item_names = serializers.SerializerMethodField()

    class Meta:
        model = InspectionTask
        fields = (
            "id", "company_id", "company_name", "task_no", "task_type", "equipment_id",
            "equipment_name", "plan_date", "status", "assignee_id", "assignee_name",
            "item_ids", "item_names", "started_at", "finished_at", "result", "remark",
            "version", "created_at", "updated_at",
        )
        read_only_fields = (
            "id", "company_name", "equipment_name", "assignee_name", "item_names",
            "status", "version", "created_at", "updated_at",
        )

    def get_company_name(self, obj) -> str:
        return _name_of(obj, "company")

    def get_equipment_name(self, obj) -> str:
        return _name_of(obj, "equipment")

    def get_assignee_name(self, obj) -> str:
        return _name_of(obj, "assignee")

    def get_item_names(self, obj) -> str:
        return "、".join(item.name for item in obj.items.all())


class InspectionRecordSerializer(DerivedCompanySerializerMixin, ReferenceIdSerializer):
    # 编号留空时由视图层按编码规则（IR）自动取号。
    record_no = serializers.CharField(allow_blank=True, default="", max_length=32, label="记录编号")
    company_id = _company_id
    company_name = serializers.SerializerMethodField()
    equipment_name = serializers.SerializerMethodField()
    item_name = serializers.SerializerMethodField()
    inspector_name = serializers.SerializerMethodField()

    class Meta:
        model = InspectionRecord
        fields = (
            "id", "company_id", "company_name", "record_no", "task_id", "equipment_id",
            "equipment_name", "item_id", "item_name", "inspected_at",
            "inspector_id", "inspector_name", "measured_value", "result",
            "abnormal_desc", "remark", "version", "created_at", "updated_at",
        )
        read_only_fields = (
            "id", "company_name", "equipment_name", "item_name", "inspector_name",
            "version", "created_at", "updated_at",
        )

    def get_company_name(self, obj) -> str:
        return _name_of(obj, "company")

    def get_equipment_name(self, obj) -> str:
        return _name_of(obj, "equipment")

    def get_item_name(self, obj) -> str:
        return _name_of(obj, "item")

    def get_inspector_name(self, obj) -> str:
        return _name_of(obj, "inspector")


class AbnormalTypeSerializer(ReferenceIdSerializer):
    class Meta:
        model = AbnormalType
        fields = (
            "id", "code", "name", "level", "is_active", "remark",
            "version", "created_at", "updated_at",
        )
        read_only_fields = ("id", "version", "created_at", "updated_at")

    def validate_code(self, value: str) -> str:
        code = (value or "").strip()
        if not code:
            raise serializers.ValidationError("类型编码不能为空。")
        return code


class AbnormalTaskSerializer(DerivedCompanySerializerMixin, ReferenceIdSerializer):
    # 编号留空时由视图层按编码规则（AT）自动取号。
    task_no = serializers.CharField(allow_blank=True, default="", max_length=32, label="任务编号")
    company_id = _company_id
    company_name = serializers.SerializerMethodField()
    abnormal_type_name = serializers.SerializerMethodField()
    level = serializers.SerializerMethodField()
    level_label = serializers.SerializerMethodField()
    equipment_name = serializers.SerializerMethodField()
    reported_by_name = serializers.SerializerMethodField()
    handler_name = serializers.SerializerMethodField()

    class Meta:
        model = AbnormalTask
        fields = (
            "id", "company_id", "company_name", "task_no", "abnormal_type_id",
            "abnormal_type_name", "level", "level_label",
            "equipment_id", "equipment_name", "source",
            "description", "reported_by_id", "reported_by_name", "reported_at",
            "status", "handler_id", "handler_name", "deadline", "handling",
            "closed_at", "remark", "version", "created_at", "updated_at",
        )
        read_only_fields = (
            "id", "company_name", "abnormal_type_name", "level", "level_label",
            "equipment_name", "reported_by_name", "handler_name", "status", "closed_at",
            "version", "created_at", "updated_at",
        )

    def get_company_name(self, obj) -> str:
        return _name_of(obj, "company")

    def get_abnormal_type_name(self, obj) -> str:
        return _name_of(obj, "abnormal_type")

    def get_level(self, obj) -> str:
        """异常等级取自异常类型的默认等级，避免同一异常在两处各写一个等级。"""
        return obj.abnormal_type.level if obj.abnormal_type_id else ""

    def get_level_label(self, obj) -> str:
        return obj.abnormal_type.get_level_display() if obj.abnormal_type_id else ""

    def get_equipment_name(self, obj) -> str:
        return _name_of(obj, "equipment")

    def get_reported_by_name(self, obj) -> str:
        return _name_of(obj, "reported_by")

    def get_handler_name(self, obj) -> str:
        return _name_of(obj, "handler")


class AbnormalRecordSerializer(DerivedCompanySerializerMixin, ReferenceIdSerializer):
    # 编号留空时由视图层按编码规则（AR）自动取号。
    record_no = serializers.CharField(allow_blank=True, default="", max_length=32, label="记录编号")
    company_id = _company_id
    company_name = serializers.SerializerMethodField()
    abnormal_type_name = serializers.SerializerMethodField()
    equipment_name = serializers.SerializerMethodField()
    handler_name = serializers.SerializerMethodField()

    class Meta:
        model = AbnormalRecord
        fields = (
            "id", "company_id", "company_name", "record_no", "task_id",
            "abnormal_type_id", "abnormal_type_name", "equipment_id", "equipment_name",
            "handle_date", "handler_id", "handler_name", "action", "result", "remark",
            "version", "created_at", "updated_at",
        )
        read_only_fields = (
            "id", "company_name", "abnormal_type_name", "equipment_name",
            "handler_name", "version", "created_at", "updated_at",
        )

    def get_company_name(self, obj) -> str:
        return _name_of(obj, "company")

    def get_abnormal_type_name(self, obj) -> str:
        return _name_of(obj, "abnormal_type")

    def get_equipment_name(self, obj) -> str:
        return _name_of(obj, "equipment")

    def get_handler_name(self, obj) -> str:
        return _name_of(obj, "handler")
# ---------------------------------------------------------------------------
# 动作接口的入参
#
# 这些是「动作」而不是「改字段」，所以用普通 Serializer 收参：
# 状态由服务层决定，客户端无法通过直接 PATCH status 跳步。
# ---------------------------------------------------------------------------


class MaintenanceCompleteSerializer(serializers.Serializer):
    """完成保养的提交内容。"""

    executor_id = serializers.PrimaryKeyRelatedField(
        queryset=Employee.objects.all(), required=False, allow_null=True, label="保养人"
    )
    content = serializers.CharField(required=False, allow_blank=True, default="", label="保养内容")
    result = serializers.CharField(required=False, allow_blank=True, default="", label="保养结果")
    is_qualified = serializers.BooleanField(required=False, default=True, label="验收合格")
    cost = serializers.DecimalField(
        max_digits=MONEY_MAX_DIGITS,
        decimal_places=MONEY_DECIMAL_PLACES,
        required=False,
        allow_null=True,
        label="保养费用",
    )
    maintain_date = serializers.DateField(required=False, allow_null=True, label="保养日期")


class RepairDispatchSerializer(serializers.Serializer):
    """故障报修单派工。"""

    assignee_id = serializers.PrimaryKeyRelatedField(
        queryset=Employee.objects.all(), required=False, allow_null=True, label="维修人"
    )
    level = serializers.ChoiceField(
        choices=FaultLevel.choices, required=False, label="故障等级"
    )
    symptom = serializers.CharField(required=False, allow_blank=True, default="", label="故障描述")
    assigned_date = serializers.DateField(required=False, allow_null=True, label="派工日期")
    remark = serializers.CharField(required=False, allow_blank=True, default="", label="备注")


class RepairCompleteSerializer(serializers.Serializer):
    """完成维修的提交内容。"""

    repairer_id = serializers.PrimaryKeyRelatedField(
        queryset=Employee.objects.all(), required=False, allow_null=True, label="维修人"
    )
    fault_reason = serializers.CharField(
        required=False, allow_blank=True, default="", label="故障原因"
    )
    solution = serializers.CharField(
        required=False, allow_blank=True, default="", label="维修措施"
    )
    parts_used = serializers.CharField(
        required=False, allow_blank=True, default="", label="领用备件说明"
    )
    cost = serializers.DecimalField(
        max_digits=MONEY_MAX_DIGITS,
        decimal_places=MONEY_DECIMAL_PLACES,
        required=False,
        allow_null=True,
        label="维修费用",
    )
    downtime_minutes = serializers.IntegerField(
        required=False, allow_null=True, min_value=0, label="停机时长（分钟）"
    )
    result = serializers.CharField(required=False, allow_blank=True, default="", label="维修结果")
    repair_date = serializers.DateField(required=False, allow_null=True, label="维修日期")


class AbnormalAssignSerializer(serializers.Serializer):
    """分派异常任务。"""

    handler_id = serializers.PrimaryKeyRelatedField(
        queryset=Employee.objects.all(), required=False, allow_null=True, label="处理人"
    )
    deadline = serializers.DateField(required=False, allow_null=True, label="处理期限")


class AbnormalCloseSerializer(serializers.Serializer):
    """关闭异常任务。"""

    handler_id = serializers.PrimaryKeyRelatedField(
        queryset=Employee.objects.all(), required=False, allow_null=True, label="处理人"
    )
    action = serializers.CharField(required=False, allow_blank=True, default="", label="处理动作")
    result = serializers.CharField(required=False, allow_blank=True, default="", label="处理结果")
    handle_date = serializers.DateField(required=False, allow_null=True, label="处理日期")
