"""安全环保序列化器。

* 枚举字段中文标签由 ``DisplayLabelsMixin`` 自动补 ``<field>_display``；
* 编号（制度、培训、隐患、事故、许可、检查、监测…）留空时由视图层按编码规则取号；
* ``status`` 一律只读：状态只能通过动作接口（整改、验收、批准、完工…）推进，
  不允许直接 PATCH 跳步。
"""

from __future__ import annotations

from rest_framework import serializers

from apps.core.serializers import ReferenceIdSerializer
from apps.ehs.models import (
    AccidentRecord,
    ComplianceCheck,
    EhsOperationLog,
    EmergencyPlan,
    EnvironmentMonitor,
    FireDrill,
    FireFacility,
    HazardRecord,
    SafetyCheck,
    SafetyRegulation,
    SafetyTraining,
    SpecialEquipmentInspection,
    WasteRecord,
    WorkPermit,
)
from apps.equipment.models import Equipment
from apps.factory.models import Employee


def _name_of(instance, attribute: str) -> str:
    related = getattr(instance, attribute, None)
    return str(related) if related is not None else ""


def _employee_field(**kwargs) -> serializers.PrimaryKeyRelatedField:
    return serializers.PrimaryKeyRelatedField(
        queryset=Employee.objects.all(), required=False, allow_null=True, **kwargs
    )


class SafetyRegulationSerializer(ReferenceIdSerializer):
    company_name = serializers.SerializerMethodField()
    owner_department_name = serializers.SerializerMethodField()
    owner_employee_name = serializers.SerializerMethodField()
    code = serializers.CharField(allow_blank=True, default="", max_length=32, label="制度编号")

    class Meta:
        model = SafetyRegulation
        fields = (
            "id", "company_id", "company_name", "code", "name", "category", "version_no",
            "issue_org", "issue_date", "effective_date", "status", "owner_department_id",
            "owner_department_name", "owner_employee_id", "owner_employee_name", "remark",
            "is_active", "version", "created_at", "updated_at",
        )
        read_only_fields = (
            "id", "company_name", "owner_department_name", "owner_employee_name",
            "version", "created_at", "updated_at",
        )

    def get_company_name(self, obj: SafetyRegulation) -> str:
        return _name_of(obj, "company")

    def get_owner_department_name(self, obj: SafetyRegulation) -> str:
        return _name_of(obj, "owner_department")

    def get_owner_employee_name(self, obj: SafetyRegulation) -> str:
        return _name_of(obj, "owner_employee")

    def validate_code(self, value: str) -> str:
        code = (value or "").strip()
        if not code and self.instance is not None:
            raise serializers.ValidationError("制度编号不能为空。")
        return code


class SafetyTrainingSerializer(ReferenceIdSerializer):
    company_name = serializers.SerializerMethodField()
    department_name = serializers.SerializerMethodField()
    training_no = serializers.CharField(allow_blank=True, default="", max_length=32, label="培训编号")

    class Meta:
        model = SafetyTraining
        fields = (
            "id", "company_id", "company_name", "training_no", "topic", "training_type",
            "trainer", "department_id", "department_name", "planned_date", "actual_date",
            "duration_hours", "participant_count", "passed_count", "status", "remark",
            "version", "created_at", "updated_at",
        )
        read_only_fields = ("id", "company_name", "department_name", "version", "created_at", "updated_at")

    def get_company_name(self, obj: SafetyTraining) -> str:
        return _name_of(obj, "company")

    def get_department_name(self, obj: SafetyTraining) -> str:
        return _name_of(obj, "department")

    def validate(self, attrs):
        participants = attrs.get("participant_count", getattr(self.instance, "participant_count", 0))
        passed = attrs.get("passed_count", getattr(self.instance, "passed_count", 0))
        if participants is not None and passed is not None and passed > participants:
            raise serializers.ValidationError({"passed_count": "考核通过人数不能超过参训人数。"})
        return attrs


class HazardRecordSerializer(ReferenceIdSerializer):
    company_name = serializers.SerializerMethodField()
    department_name = serializers.SerializerMethodField()
    reported_by_name = serializers.SerializerMethodField()
    rectified_by_name = serializers.SerializerMethodField()
    verified_by_name = serializers.SerializerMethodField()
    hazard_no = serializers.CharField(allow_blank=True, default="", max_length=32, label="隐患编号")
    is_overdue = serializers.SerializerMethodField()

    class Meta:
        model = HazardRecord
        fields = (
            "id", "company_id", "company_name", "hazard_no", "title", "description", "level",
            "source", "location", "department_id", "department_name", "reported_by_id",
            "reported_by_name", "found_date", "due_date", "status", "rectify_measure",
            "rectified_by_id", "rectified_by_name", "rectified_date", "verify_result",
            "verified_by_id", "verified_by_name", "verified_date", "is_overdue", "remark",
            "version", "created_at", "updated_at",
        )
        read_only_fields = (
            "id", "company_name", "department_name", "reported_by_name", "rectified_by_name",
            "verified_by_name", "status", "rectified_date", "verify_result", "verified_by_id",
            "verified_date", "is_overdue", "version", "created_at", "updated_at",
        )

    def get_company_name(self, obj: HazardRecord) -> str:
        return _name_of(obj, "company")

    def get_department_name(self, obj: HazardRecord) -> str:
        return _name_of(obj, "department")

    def get_reported_by_name(self, obj: HazardRecord) -> str:
        return _name_of(obj, "reported_by")

    def get_rectified_by_name(self, obj: HazardRecord) -> str:
        return _name_of(obj, "rectified_by")

    def get_verified_by_name(self, obj: HazardRecord) -> str:
        return _name_of(obj, "verified_by")

    def get_is_overdue(self, obj: HazardRecord) -> bool:
        """未关闭且已过整改期限 → 逾期，界面直接标红。"""
        from apps.core.services import business_today

        if obj.status == "closed" or obj.due_date is None:
            return False
        return obj.due_date < business_today()


class EmergencyPlanSerializer(ReferenceIdSerializer):
    company_name = serializers.SerializerMethodField()
    owner_employee_name = serializers.SerializerMethodField()
    code = serializers.CharField(allow_blank=True, default="", max_length=32, label="预案编号")

    class Meta:
        model = EmergencyPlan
        fields = (
            "id", "company_id", "company_name", "code", "name", "plan_type", "response_level",
            "issue_date", "review_date", "drill_cycle_days", "next_drill_date", "status",
            "owner_employee_id", "owner_employee_name", "remark", "is_active",
            "version", "created_at", "updated_at",
        )
        read_only_fields = ("id", "company_name", "owner_employee_name", "version", "created_at", "updated_at")

    def get_company_name(self, obj: EmergencyPlan) -> str:
        return _name_of(obj, "company")

    def get_owner_employee_name(self, obj: EmergencyPlan) -> str:
        return _name_of(obj, "owner_employee")

    def validate_code(self, value: str) -> str:
        code = (value or "").strip()
        if not code and self.instance is not None:
            raise serializers.ValidationError("预案编号不能为空。")
        return code


class AccidentRecordSerializer(ReferenceIdSerializer):
    company_name = serializers.SerializerMethodField()
    department_name = serializers.SerializerMethodField()
    reporter_name = serializers.SerializerMethodField()
    investigator_name = serializers.SerializerMethodField()
    accident_no = serializers.CharField(allow_blank=True, default="", max_length=32, label="事故编号")

    class Meta:
        model = AccidentRecord
        fields = (
            "id", "company_id", "company_name", "accident_no", "title", "category", "level",
            "occurred_at", "location", "department_id", "department_name", "injured_count",
            "lost_days", "loss_amount", "description", "causes", "measures", "reporter_id",
            "reporter_name", "reported_at", "investigator_id", "investigator_name",
            "investigation_result", "status", "closed_date", "remark",
            "version", "created_at", "updated_at",
        )
        read_only_fields = (
            "id", "company_name", "department_name", "reporter_name", "investigator_name",
            "status", "reported_at", "closed_date", "version", "created_at", "updated_at",
        )

    def get_company_name(self, obj: AccidentRecord) -> str:
        return _name_of(obj, "company")

    def get_department_name(self, obj: AccidentRecord) -> str:
        return _name_of(obj, "department")

    def get_reporter_name(self, obj: AccidentRecord) -> str:
        return _name_of(obj, "reporter")

    def get_investigator_name(self, obj: AccidentRecord) -> str:
        return _name_of(obj, "investigator")

    def validate_loss_amount(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError("直接损失金额不能为负数。")
        return value


class EnvironmentMonitorSerializer(ReferenceIdSerializer):
    company_name = serializers.SerializerMethodField()
    monitor_no = serializers.CharField(allow_blank=True, default="", max_length=32, label="监测编号")
    is_over_limit = serializers.SerializerMethodField()

    class Meta:
        model = EnvironmentMonitor
        fields = (
            "id", "company_id", "company_name", "monitor_no", "medium", "point_name",
            "pollutant", "limit_value", "measured_value", "unit", "is_compliant",
            "is_over_limit", "monitored_at", "permit_no", "monitor_org", "remark",
            "version", "created_at", "updated_at",
        )
        read_only_fields = (
            "id", "company_name", "is_compliant", "is_over_limit",
            "version", "created_at", "updated_at",
        )

    def get_company_name(self, obj: EnvironmentMonitor) -> str:
        return _name_of(obj, "company")

    def get_is_over_limit(self, obj: EnvironmentMonitor) -> bool | None:
        if obj.limit_value is None or obj.measured_value is None:
            return None
        return obj.measured_value > obj.limit_value


class WasteRecordSerializer(ReferenceIdSerializer):
    company_name = serializers.SerializerMethodField()
    waste_no = serializers.CharField(allow_blank=True, default="", max_length=32, label="台账编号")

    class Meta:
        model = WasteRecord
        fields = (
            "id", "company_id", "company_name", "waste_no", "waste_name", "waste_type",
            "waste_code", "quantity", "unit", "produced_date", "storage_location",
            "disposal_method", "disposal_org", "transfer_no", "disposed_date", "status",
            "remark", "version", "created_at", "updated_at",
        )
        read_only_fields = ("id", "company_name", "version", "created_at", "updated_at")

    def get_company_name(self, obj: WasteRecord) -> str:
        return _name_of(obj, "company")

    def validate_quantity(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError("产生量不能为负数。")
        return value


class ComplianceCheckSerializer(ReferenceIdSerializer):
    company_name = serializers.SerializerMethodField()
    checker_name = serializers.SerializerMethodField()
    owner_employee_name = serializers.SerializerMethodField()
    check_no = serializers.CharField(allow_blank=True, default="", max_length=32, label="检查编号")

    class Meta:
        model = ComplianceCheck
        fields = (
            "id", "company_id", "company_name", "check_no", "title", "check_type",
            "check_date", "organization", "checker_id", "checker_name", "result", "issues",
            "rectify_due_date", "status", "rectified_date", "owner_employee_id",
            "owner_employee_name", "remark", "version", "created_at", "updated_at",
        )
        read_only_fields = (
            "id", "company_name", "checker_name", "owner_employee_name", "status",
            "rectified_date", "version", "created_at", "updated_at",
        )

    def get_company_name(self, obj: ComplianceCheck) -> str:
        return _name_of(obj, "company")

    def get_checker_name(self, obj: ComplianceCheck) -> str:
        return _name_of(obj, "checker")

    def get_owner_employee_name(self, obj: ComplianceCheck) -> str:
        return _name_of(obj, "owner_employee")


class FireFacilitySerializer(ReferenceIdSerializer):
    company_name = serializers.SerializerMethodField()
    department_name = serializers.SerializerMethodField()
    owner_employee_name = serializers.SerializerMethodField()
    code = serializers.CharField(allow_blank=True, default="", max_length=32, label="设施编号")

    class Meta:
        model = FireFacility
        fields = (
            "id", "company_id", "company_name", "code", "name", "facility_type", "location",
            "quantity", "unit", "last_check_date", "next_check_date", "status",
            "department_id", "department_name", "owner_employee_id", "owner_employee_name",
            "remark", "is_active", "version", "created_at", "updated_at",
        )
        read_only_fields = (
            "id", "company_name", "department_name", "owner_employee_name",
            "version", "created_at", "updated_at",
        )

    def get_company_name(self, obj: FireFacility) -> str:
        return _name_of(obj, "company")

    def get_department_name(self, obj: FireFacility) -> str:
        return _name_of(obj, "department")

    def get_owner_employee_name(self, obj: FireFacility) -> str:
        return _name_of(obj, "owner_employee")

    def validate_code(self, value: str) -> str:
        code = (value or "").strip()
        if not code and self.instance is not None:
            raise serializers.ValidationError("设施编号不能为空。")
        return code


class FireDrillSerializer(ReferenceIdSerializer):
    company_name = serializers.SerializerMethodField()
    plan_name = serializers.SerializerMethodField()
    drill_no = serializers.CharField(allow_blank=True, default="", max_length=32, label="演练编号")

    class Meta:
        model = FireDrill
        fields = (
            "id", "company_id", "company_name", "drill_no", "topic", "drill_type",
            "planned_date", "actual_date", "organizer", "participant_count",
            "duration_minutes", "assessment", "issues", "plan_id", "plan_name", "remark",
            "version", "created_at", "updated_at",
        )
        read_only_fields = ("id", "company_name", "plan_name", "version", "created_at", "updated_at")

    def get_company_name(self, obj: FireDrill) -> str:
        return _name_of(obj, "company")

    def get_plan_name(self, obj: FireDrill) -> str:
        return _name_of(obj, "plan")


class WorkPermitSerializer(ReferenceIdSerializer):
    company_name = serializers.SerializerMethodField()
    applicant_name = serializers.SerializerMethodField()
    department_name = serializers.SerializerMethodField()
    approver_name = serializers.SerializerMethodField()
    guardian_name = serializers.SerializerMethodField()
    accepted_by_name = serializers.SerializerMethodField()
    permit_no = serializers.CharField(allow_blank=True, default="", max_length=32, label="许可编号")

    class Meta:
        model = WorkPermit
        fields = (
            "id", "company_id", "company_name", "permit_no", "permit_type", "status",
            "work_content", "work_location", "risk_level", "protective_measures",
            "applicant_id", "applicant_name", "department_id", "department_name",
            "start_at", "end_at", "approver_id", "approver_name", "approved_at",
            "guardian_id", "guardian_name", "started_at", "finished_at", "accepted_by_id",
            "accepted_by_name", "accepted_at", "result", "remark",
            "version", "created_at", "updated_at",
        )
        read_only_fields = (
            "id", "company_name", "applicant_name", "department_name", "approver_name",
            "guardian_name", "accepted_by_name", "status", "approved_at", "started_at",
            "finished_at", "accepted_at", "result", "version", "created_at", "updated_at",
        )

    def get_company_name(self, obj: WorkPermit) -> str:
        return _name_of(obj, "company")

    def get_applicant_name(self, obj: WorkPermit) -> str:
        return _name_of(obj, "applicant")

    def get_department_name(self, obj: WorkPermit) -> str:
        return _name_of(obj, "department")

    def get_approver_name(self, obj: WorkPermit) -> str:
        return _name_of(obj, "approver")

    def get_guardian_name(self, obj: WorkPermit) -> str:
        return _name_of(obj, "guardian")

    def get_accepted_by_name(self, obj: WorkPermit) -> str:
        return _name_of(obj, "accepted_by")

    def validate(self, attrs):
        start = attrs.get("start_at", getattr(self.instance, "start_at", None))
        end = attrs.get("end_at", getattr(self.instance, "end_at", None))
        if start and end and end < start:
            raise serializers.ValidationError({"end_at": "计划结束时间不能早于开始时间。"})
        return attrs


class SafetyCheckSerializer(ReferenceIdSerializer):
    company_name = serializers.SerializerMethodField()
    checker_name = serializers.SerializerMethodField()
    department_name = serializers.SerializerMethodField()
    equipment_name = serializers.SerializerMethodField()
    check_no = serializers.CharField(allow_blank=True, default="", max_length=32, label="检查编号")

    class Meta:
        model = SafetyCheck
        fields = (
            "id", "company_id", "company_name", "check_no", "check_type", "title",
            "check_date", "checker_id", "checker_name", "department_id", "department_name",
            "equipment_id", "equipment_name", "check_content", "problem_count", "conclusion",
            "status", "rectify_requirement", "rectified_date", "remark",
            "version", "created_at", "updated_at",
        )
        read_only_fields = (
            "id", "company_name", "checker_name", "department_name", "equipment_name",
            "version", "created_at", "updated_at",
        )

    def get_company_name(self, obj: SafetyCheck) -> str:
        return _name_of(obj, "company")

    def get_checker_name(self, obj: SafetyCheck) -> str:
        return _name_of(obj, "checker")

    def get_department_name(self, obj: SafetyCheck) -> str:
        return _name_of(obj, "department")

    def get_equipment_name(self, obj: SafetyCheck) -> str:
        return _name_of(obj, "equipment")


class SpecialEquipmentInspectionSerializer(ReferenceIdSerializer):
    company_name = serializers.SerializerMethodField()
    equipment_code = serializers.SerializerMethodField()
    linked_equipment_name = serializers.SerializerMethodField()
    certificate_no = serializers.CharField(allow_blank=True, default="", max_length=32, label="报告编号")

    class Meta:
        model = SpecialEquipmentInspection
        fields = (
            "id", "company_id", "company_name", "certificate_no", "equipment_id",
            "equipment_code", "linked_equipment_name", "equipment_name", "inspection_org",
            "inspection_date", "next_inspection_date", "result", "inspector", "issue_date",
            "remark", "version", "created_at", "updated_at",
        )
        read_only_fields = (
            "id", "company_name", "equipment_code", "linked_equipment_name",
            "version", "created_at", "updated_at",
        )

    def get_company_name(self, obj: SpecialEquipmentInspection) -> str:
        return _name_of(obj, "company")

    def get_equipment_code(self, obj: SpecialEquipmentInspection) -> str:
        return obj.equipment.code if obj.equipment_id else ""

    def get_linked_equipment_name(self, obj: SpecialEquipmentInspection) -> str:
        return _name_of(obj, "equipment")

    def validate(self, attrs):
        equipment = attrs.get("equipment", getattr(self.instance, "equipment", None))
        name = attrs.get("equipment_name") or getattr(self.instance, "equipment_name", "")
        if equipment is not None:
            if not equipment.is_special:
                raise serializers.ValidationError(
                    {"equipment_id": "该设备未标记为特种设备，请先在设备台账中勾选「特种设备」。"}
                )
            attrs["equipment_name"] = name or equipment.name
        elif not name:
            raise serializers.ValidationError(
                {"equipment_name": "请选择设备台账中的特种设备，或填写设备名称。"}
            )
        return attrs


class EhsOperationLogSerializer(ReferenceIdSerializer):
    company_name = serializers.SerializerMethodField()
    operator_name = serializers.SerializerMethodField()

    class Meta:
        model = EhsOperationLog
        fields = (
            "id", "company_id", "company_name", "domain", "business_type", "business_label",
            "action", "operator_id", "operator_name", "occurred_at", "detail", "payload",
            "version", "created_at", "updated_at",
        )
        read_only_fields = fields

    def get_company_name(self, obj: EhsOperationLog) -> str:
        return _name_of(obj, "company")

    def get_operator_name(self, obj: EhsOperationLog) -> str:
        return _name_of(obj, "operator")


# ---------------------------------------------------------------------------
# 动作接口入参
# ---------------------------------------------------------------------------


class HazardRectifySerializer(serializers.Serializer):
    measure = serializers.CharField(label="整改措施")
    rectified_by_id = _employee_field(label="整改人")


class HazardVerifySerializer(serializers.Serializer):
    result = serializers.CharField(label="验收结论")
    passed = serializers.BooleanField(default=True, label="是否通过")
    verified_by_id = _employee_field(label="验收人")


class AccidentInvestigateSerializer(serializers.Serializer):
    investigator_id = _employee_field(label="调查负责人")


class AccidentRectifySerializer(serializers.Serializer):
    measures = serializers.CharField(label="整改与预防措施")
    causes = serializers.CharField(required=False, allow_blank=True, default="", label="原因分析")


class AccidentCloseSerializer(serializers.Serializer):
    result = serializers.CharField(label="调查结论")
    closed_date = serializers.DateField(required=False, allow_null=True, label="关闭日期")


class PermitApproveSerializer(serializers.Serializer):
    approver_id = _employee_field(label="审批人")
    guardian_id = _employee_field(label="监护人")
    note = serializers.CharField(required=False, allow_blank=True, default="", label="审批说明")


class PermitRejectSerializer(serializers.Serializer):
    reason = serializers.CharField(label="驳回理由")
    approver_id = _employee_field(label="审批人")


class PermitStartSerializer(serializers.Serializer):
    operator_id = _employee_field(label="操作人")


class PermitFinishSerializer(serializers.Serializer):
    result = serializers.CharField(required=False, allow_blank=True, default="", label="完工说明")
    operator_id = _employee_field(label="操作人")


class PermitAcceptSerializer(serializers.Serializer):
    result = serializers.CharField(label="验收结论")
    accepted_by_id = _employee_field(label="验收人")


class ComplianceCloseSerializer(serializers.Serializer):
    rectified_date = serializers.DateField(required=False, allow_null=True, label="整改完成日期")


__all__ = [
    "AccidentCloseSerializer",
    "AccidentInvestigateSerializer",
    "AccidentRecordSerializer",
    "AccidentRectifySerializer",
    "ComplianceCheckSerializer",
    "ComplianceCloseSerializer",
    "EhsOperationLogSerializer",
    "EmergencyPlanSerializer",
    "EnvironmentMonitorSerializer",
    "Equipment",
    "FireDrillSerializer",
    "FireFacilitySerializer",
    "HazardRecordSerializer",
    "HazardRectifySerializer",
    "HazardVerifySerializer",
    "PermitAcceptSerializer",
    "PermitApproveSerializer",
    "PermitFinishSerializer",
    "PermitRejectSerializer",
    "PermitStartSerializer",
    "SafetyCheckSerializer",
    "SafetyRegulationSerializer",
    "SafetyTrainingSerializer",
    "SpecialEquipmentInspectionSerializer",
    "WorkPermitSerializer",
]
