"""安全环保接口。

* 台账类对象：标准 CRUD（编号留空自动取号）；
* 隐患 / 事故 / 作业许可：状态只通过动作接口推进，服务层负责校验与写操作日志；
* 操作日志只读；
* 排污监测在保存后由服务层按「实测值 vs 限值」自动判定是否达标。
"""

from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.models import AuditAction
from apps.core.services import business_now, record_audit
from apps.core.viewsets import ActiveFilterMixin, ReadOnlyScopedViewSet, ScopedModelViewSet
from apps.ehs import services
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
from apps.ehs.serializers import (
    AccidentCloseSerializer,
    AccidentInvestigateSerializer,
    AccidentRecordSerializer,
    AccidentRectifySerializer,
    ComplianceCheckSerializer,
    ComplianceCloseSerializer,
    EhsOperationLogSerializer,
    EmergencyPlanSerializer,
    EnvironmentMonitorSerializer,
    FireDrillSerializer,
    FireFacilitySerializer,
    HazardRecordSerializer,
    HazardRectifySerializer,
    HazardVerifySerializer,
    PermitAcceptSerializer,
    PermitApproveSerializer,
    PermitFinishSerializer,
    PermitRejectSerializer,
    PermitStartSerializer,
    SafetyCheckSerializer,
    SafetyRegulationSerializer,
    SafetyTrainingSerializer,
    SpecialEquipmentInspectionSerializer,
    WasteRecordSerializer,
    WorkPermitSerializer,
)


class EhsScopedViewSet(ActiveFilterMixin, ScopedModelViewSet):
    """安全环保通用视图基类：按公司收敛数据范围。"""

    scope_fields = {"company_field": "company_id"}


class SafetyRegulationViewSet(EhsScopedViewSet):
    queryset = SafetyRegulation.objects.select_related(
        "company", "owner_department", "owner_employee"
    ).all()
    serializer_class = SafetyRegulationSerializer
    audit_fields = (
        "code", "name", "category", "version_no", "issue_date", "effective_date", "status",
        "owner_department_id", "owner_employee_id", "is_active",
    )
    search_fields = ["code", "name", "issue_org"]
    filterset_fields = ["company_id", "category", "status", "owner_department_id"]
    ordering_fields = ["id", "code", "name", "effective_date", "updated_at"]
    uniqueness_error_map = {"uq_safety_regulation_company_code": "同一公司下制度编号已存在。"}
    required_permissions = {
        "list": "ehs.regulation.view",
        "retrieve": "ehs.regulation.view",
        "create": "ehs.regulation.create",
        "partial_update": "ehs.regulation.update",
        "set_active": "ehs.regulation.update",
    }

    def perform_create(self, serializer) -> None:
        data = serializer.validated_data
        data["code"] = str(data.get("code") or "").strip() or services.next_regulation_code()
        super().perform_create(serializer)


class SafetyTrainingViewSet(EhsScopedViewSet):
    queryset = SafetyTraining.objects.select_related("company", "department").all()
    serializer_class = SafetyTrainingSerializer
    audit_fields = (
        "training_no", "topic", "training_type", "trainer", "department_id", "planned_date",
        "actual_date", "duration_hours", "participant_count", "passed_count", "status",
    )
    search_fields = ["training_no", "topic", "trainer"]
    filterset_fields = ["company_id", "training_type", "status", "department_id"]
    ordering_fields = ["id", "training_no", "actual_date", "planned_date"]
    uniqueness_error_map = {"uq_safety_training_company_no": "同一公司下培训编号已存在。"}
    required_permissions = {
        "list": "ehs.training.view",
        "retrieve": "ehs.training.view",
        "create": "ehs.training.create",
        "partial_update": "ehs.training.update",
    }

    def perform_create(self, serializer) -> None:
        data = serializer.validated_data
        data["training_no"] = str(data.get("training_no") or "").strip() or services.next_training_no()
        super().perform_create(serializer)


class HazardRecordViewSet(EhsScopedViewSet):
    queryset = HazardRecord.objects.select_related(
        "company", "department", "reported_by", "rectified_by", "verified_by"
    ).all()
    serializer_class = HazardRecordSerializer
    audit_fields = (
        "hazard_no", "title", "level", "source", "location", "department_id", "found_date",
        "due_date", "status",
    )
    search_fields = ["hazard_no", "title", "description", "location"]
    filterset_fields = ["company_id", "level", "source", "status", "department_id"]
    ordering_fields = ["id", "hazard_no", "found_date", "due_date", "level"]
    uniqueness_error_map = {"uq_hazard_record_company_no": "同一公司下隐患编号已存在。"}
    required_permissions = {
        "list": "ehs.hazard.view",
        "retrieve": "ehs.hazard.view",
        "create": "ehs.hazard.create",
        "partial_update": "ehs.hazard.update",
        "rectify": "ehs.hazard.rectify",
        "submit_verify": "ehs.hazard.rectify",
        "verify": "ehs.hazard.verify",
    }

    def perform_create(self, serializer) -> None:
        data = serializer.validated_data
        data["hazard_no"] = str(data.get("hazard_no") or "").strip() or services.next_hazard_no()
        super().perform_create(serializer)

    @extend_schema(request=HazardRectifySerializer, responses={200: HazardRecordSerializer})
    @action(detail=True, methods=["post"], url_path="rectify")
    def rectify(self, request, *args, **kwargs) -> Response:
        """开始整改：待整改 / 待验收（退回）→ 整改中。"""
        hazard = self.get_object()
        payload = HazardRectifySerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        updated = services.start_hazard_rectify(
            hazard,
            measure=payload.validated_data["measure"],
            operator=payload.validated_data.get("rectified_by_id"),
            rectified_by=payload.validated_data.get("rectified_by_id"),
        )
        record_audit(
            action=AuditAction.UPDATE, instance=updated,
            changes={"status": updated.status, "rectify_measure": updated.rectify_measure},
            object_repr=updated.hazard_no,
        )
        return Response(self.get_serializer(updated).data)

    @extend_schema(responses={200: HazardRecordSerializer})
    @action(detail=True, methods=["post"], url_path="submit-verify")
    def submit_verify(self, request, *args, **kwargs) -> Response:
        """提交验收：整改中 → 待验收。"""
        hazard = self.get_object()
        updated = services.submit_hazard_verify(hazard)
        record_audit(
            action=AuditAction.UPDATE, instance=updated,
            changes={"status": updated.status}, object_repr=updated.hazard_no,
        )
        return Response(self.get_serializer(updated).data)

    @extend_schema(request=HazardVerifySerializer, responses={200: HazardRecordSerializer})
    @action(detail=True, methods=["post"], url_path="verify")
    def verify(self, request, *args, **kwargs) -> Response:
        """验收：通过则关闭，不通过退回整改中。"""
        hazard = self.get_object()
        payload = HazardVerifySerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        updated = services.verify_hazard(
            hazard,
            result=data["result"],
            passed=data["passed"],
            operator=data.get("verified_by_id"),
            verified_by=data.get("verified_by_id"),
        )
        record_audit(
            action=AuditAction.UPDATE, instance=updated,
            changes={"status": updated.status, "verify_result": updated.verify_result},
            reason=data["result"],
            object_repr=updated.hazard_no,
        )
        return Response(self.get_serializer(updated).data)


class EmergencyPlanViewSet(EhsScopedViewSet):
    queryset = EmergencyPlan.objects.select_related("company", "owner_employee").all()
    serializer_class = EmergencyPlanSerializer
    audit_fields = (
        "code", "name", "plan_type", "response_level", "issue_date", "review_date",
        "drill_cycle_days", "next_drill_date", "status", "owner_employee_id", "is_active",
    )
    search_fields = ["code", "name"]
    filterset_fields = ["company_id", "plan_type", "response_level", "status"]
    ordering_fields = ["id", "code", "name", "next_drill_date"]
    uniqueness_error_map = {"uq_emergency_plan_company_code": "同一公司下预案编号已存在。"}
    required_permissions = {
        "list": "ehs.emergency_plan.view",
        "retrieve": "ehs.emergency_plan.view",
        "create": "ehs.emergency_plan.create",
        "partial_update": "ehs.emergency_plan.update",
        "set_active": "ehs.emergency_plan.update",
    }

    def perform_create(self, serializer) -> None:
        data = serializer.validated_data
        data["code"] = str(data.get("code") or "").strip() or services.next_plan_code()
        super().perform_create(serializer)


class AccidentRecordViewSet(EhsScopedViewSet):
    queryset = AccidentRecord.objects.select_related(
        "company", "department", "reporter", "investigator"
    ).all()
    serializer_class = AccidentRecordSerializer
    audit_fields = (
        "accident_no", "title", "category", "level", "occurred_at", "location",
        "injured_count", "lost_days", "loss_amount", "status",
    )
    search_fields = ["accident_no", "title", "description", "location"]
    filterset_fields = ["company_id", "category", "level", "status", "department_id"]
    ordering_fields = ["id", "accident_no", "occurred_at", "level"]
    uniqueness_error_map = {"uq_accident_record_company_no": "同一公司下事故编号已存在。"}
    required_permissions = {
        "list": "ehs.accident.view",
        "retrieve": "ehs.accident.view",
        "create": "ehs.accident.create",
        "partial_update": "ehs.accident.update",
        "investigate": "ehs.accident.handle",
        "rectify": "ehs.accident.handle",
        "close": "ehs.accident.handle",
    }

    def perform_create(self, serializer) -> None:
        data = serializer.validated_data
        data["accident_no"] = (
            str(data.get("accident_no") or "").strip() or services.next_accident_no()
        )
        serializer.validated_data["reported_at"] = business_now()
        super().perform_create(serializer)

    @extend_schema(request=AccidentInvestigateSerializer, responses={200: AccidentRecordSerializer})
    @action(detail=True, methods=["post"], url_path="investigate")
    def investigate(self, request, *args, **kwargs) -> Response:
        """启动调查：已上报 → 调查中。"""
        accident = self.get_object()
        payload = AccidentInvestigateSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        updated = services.start_accident_investigation(
            accident,
            investigator=payload.validated_data.get("investigator_id"),
            operator=payload.validated_data.get("investigator_id"),
        )
        record_audit(
            action=AuditAction.UPDATE, instance=updated,
            changes={"status": updated.status}, object_repr=updated.accident_no,
        )
        return Response(self.get_serializer(updated).data)

    @extend_schema(request=AccidentRectifySerializer, responses={200: AccidentRecordSerializer})
    @action(detail=True, methods=["post"], url_path="rectify")
    def rectify(self, request, *args, **kwargs) -> Response:
        """登记整改：调查中 → 已整改。"""
        accident = self.get_object()
        payload = AccidentRectifySerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        updated = services.rectify_accident(
            accident, measures=data["measures"], causes=data.get("causes") or ""
        )
        record_audit(
            action=AuditAction.UPDATE, instance=updated,
            changes={"status": updated.status}, object_repr=updated.accident_no,
        )
        return Response(self.get_serializer(updated).data)

    @extend_schema(request=AccidentCloseSerializer, responses={200: AccidentRecordSerializer})
    @action(detail=True, methods=["post"], url_path="close")
    def close(self, request, *args, **kwargs) -> Response:
        """关闭事故：已整改 → 已关闭。"""
        accident = self.get_object()
        payload = AccidentCloseSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        updated = services.close_accident(
            accident, result=data["result"], closed_date=data.get("closed_date")
        )
        record_audit(
            action=AuditAction.UPDATE, instance=updated,
            changes={"status": updated.status}, reason=data["result"],
            object_repr=updated.accident_no,
        )
        return Response(self.get_serializer(updated).data)


class EnvironmentMonitorViewSet(EhsScopedViewSet):
    queryset = EnvironmentMonitor.objects.select_related("company").all()
    serializer_class = EnvironmentMonitorSerializer
    audit_fields = (
        "monitor_no", "medium", "point_name", "pollutant", "limit_value", "measured_value",
        "is_compliant", "monitored_at", "permit_no",
    )
    search_fields = ["monitor_no", "point_name", "pollutant", "permit_no"]
    filterset_fields = ["company_id", "medium", "is_compliant"]
    ordering_fields = ["id", "monitor_no", "monitored_at"]
    uniqueness_error_map = {"uq_env_monitor_company_no": "同一公司下监测编号已存在。"}
    required_permissions = {
        "list": "ehs.env_monitor.view",
        "retrieve": "ehs.env_monitor.view",
        "create": "ehs.env_monitor.create",
        "partial_update": "ehs.env_monitor.update",
    }

    def perform_create(self, serializer) -> None:
        data = serializer.validated_data
        data["monitor_no"] = str(data.get("monitor_no") or "").strip() or services.next_monitor_no()
        super().perform_create(serializer)
        services.apply_monitor_compliance(serializer.instance)

    def perform_update(self, serializer) -> None:
        super().perform_update(serializer)
        services.apply_monitor_compliance(serializer.instance)


class WasteRecordViewSet(EhsScopedViewSet):
    queryset = WasteRecord.objects.select_related("company").all()
    serializer_class = WasteRecordSerializer
    audit_fields = (
        "waste_no", "waste_name", "waste_type", "waste_code", "quantity", "produced_date",
        "storage_location", "disposal_method", "disposal_org", "transfer_no", "status",
    )
    search_fields = ["waste_no", "waste_name", "waste_code", "transfer_no", "disposal_org"]
    filterset_fields = ["company_id", "waste_type", "status"]
    ordering_fields = ["id", "waste_no", "produced_date", "quantity"]
    uniqueness_error_map = {"uq_waste_record_company_no": "同一公司下台账编号已存在。"}
    required_permissions = {
        "list": "ehs.waste.view",
        "retrieve": "ehs.waste.view",
        "create": "ehs.waste.create",
        "partial_update": "ehs.waste.update",
    }

    def perform_create(self, serializer) -> None:
        data = serializer.validated_data
        data["waste_no"] = str(data.get("waste_no") or "").strip() or services.next_waste_no()
        super().perform_create(serializer)


class ComplianceCheckViewSet(EhsScopedViewSet):
    queryset = ComplianceCheck.objects.select_related(
        "company", "checker", "owner_employee"
    ).all()
    serializer_class = ComplianceCheckSerializer
    audit_fields = (
        "check_no", "title", "check_type", "check_date", "organization", "result", "issues",
        "rectify_due_date", "status",
    )
    search_fields = ["check_no", "title", "organization", "issues"]
    filterset_fields = ["company_id", "check_type", "result", "status"]
    ordering_fields = ["id", "check_no", "check_date"]
    uniqueness_error_map = {"uq_compliance_check_company_no": "同一公司下检查编号已存在。"}
    required_permissions = {
        "list": "ehs.compliance.view",
        "retrieve": "ehs.compliance.view",
        "create": "ehs.compliance.create",
        "partial_update": "ehs.compliance.update",
        "close": "ehs.compliance.update",
    }

    def perform_create(self, serializer) -> None:
        data = serializer.validated_data
        data["check_no"] = str(data.get("check_no") or "").strip() or services.next_compliance_no()
        super().perform_create(serializer)

    @extend_schema(request=ComplianceCloseSerializer, responses={200: ComplianceCheckSerializer})
    @action(detail=True, methods=["post"], url_path="close")
    def close(self, request, *args, **kwargs) -> Response:
        """关闭合规检查（整改完成）。"""
        check = self.get_object()
        payload = ComplianceCloseSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        updated = services.close_compliance_check(
            check, rectified_date=payload.validated_data.get("rectified_date")
        )
        record_audit(
            action=AuditAction.UPDATE, instance=updated,
            changes={"status": updated.status}, object_repr=updated.check_no,
        )
        return Response(self.get_serializer(updated).data)


class FireFacilityViewSet(EhsScopedViewSet):
    queryset = FireFacility.objects.select_related(
        "company", "department", "owner_employee"
    ).all()
    serializer_class = FireFacilitySerializer
    audit_fields = (
        "code", "name", "facility_type", "location", "quantity", "last_check_date",
        "next_check_date", "status", "department_id", "is_active",
    )
    search_fields = ["code", "name", "location"]
    filterset_fields = ["company_id", "facility_type", "status", "department_id"]
    ordering_fields = ["id", "code", "next_check_date"]
    uniqueness_error_map = {"uq_fire_facility_company_code": "同一公司下设施编号已存在。"}
    required_permissions = {
        "list": "ehs.fire_facility.view",
        "retrieve": "ehs.fire_facility.view",
        "create": "ehs.fire_facility.create",
        "partial_update": "ehs.fire_facility.update",
        "set_active": "ehs.fire_facility.update",
    }

    def perform_create(self, serializer) -> None:
        data = serializer.validated_data
        data["code"] = str(data.get("code") or "").strip() or services.next_fire_facility_code()
        super().perform_create(serializer)


class FireDrillViewSet(EhsScopedViewSet):
    queryset = FireDrill.objects.select_related("company", "plan").all()
    serializer_class = FireDrillSerializer
    audit_fields = (
        "drill_no", "topic", "drill_type", "planned_date", "actual_date", "organizer",
        "participant_count", "duration_minutes",
    )
    search_fields = ["drill_no", "topic", "organizer"]
    filterset_fields = ["company_id", "drill_type", "plan_id"]
    ordering_fields = ["id", "drill_no", "actual_date"]
    uniqueness_error_map = {"uq_fire_drill_company_no": "同一公司下演练编号已存在。"}
    required_permissions = {
        "list": "ehs.fire_drill.view",
        "retrieve": "ehs.fire_drill.view",
        "create": "ehs.fire_drill.create",
        "partial_update": "ehs.fire_drill.update",
    }

    def perform_create(self, serializer) -> None:
        data = serializer.validated_data
        data["drill_no"] = str(data.get("drill_no") or "").strip() or services.next_drill_no()
        super().perform_create(serializer)


class WorkPermitViewSet(EhsScopedViewSet):
    queryset = WorkPermit.objects.select_related(
        "company", "applicant", "department", "approver", "guardian", "accepted_by"
    ).all()
    serializer_class = WorkPermitSerializer
    audit_fields = (
        "permit_no", "permit_type", "status", "work_content", "work_location", "risk_level",
        "applicant_id", "department_id", "start_at", "end_at",
    )
    search_fields = ["permit_no", "work_content", "work_location"]
    filterset_fields = ["company_id", "permit_type", "status", "risk_level", "department_id"]
    ordering_fields = ["id", "permit_no", "start_at", "created_at"]
    uniqueness_error_map = {"uq_work_permit_company_no": "同一公司下许可编号已存在。"}
    required_permissions = {
        "list": "ehs.permit.view",
        "retrieve": "ehs.permit.view",
        "create": "ehs.permit.create",
        "partial_update": "ehs.permit.update",
        "approve": "ehs.permit.approve",
        "reject": "ehs.permit.approve",
        "start": "ehs.permit.execute",
        "finish": "ehs.permit.execute",
        "accept": "ehs.permit.accept",
    }

    def perform_create(self, serializer) -> None:
        data = serializer.validated_data
        data["permit_no"] = str(data.get("permit_no") or "").strip() or services.next_permit_no()
        super().perform_create(serializer)

    @extend_schema(request=PermitApproveSerializer, responses={200: WorkPermitSerializer})
    @action(detail=True, methods=["post"], url_path="approve")
    def approve(self, request, *args, **kwargs) -> Response:
        """批准作业许可：待审批 → 已批准（动火等作业必须指定监护人）。"""
        permit = self.get_object()
        payload = PermitApproveSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        updated = services.approve_permit(
            permit,
            approver=data.get("approver_id"),
            guardian=data.get("guardian_id"),
            note=data.get("note") or "",
        )
        record_audit(
            action=AuditAction.APPROVE, instance=updated,
            changes={"status": updated.status}, object_repr=updated.permit_no,
        )
        return Response(self.get_serializer(updated).data)

    @extend_schema(request=PermitRejectSerializer, responses={200: WorkPermitSerializer})
    @action(detail=True, methods=["post"], url_path="reject")
    def reject(self, request, *args, **kwargs) -> Response:
        """驳回作业许可：待审批 → 已驳回。"""
        permit = self.get_object()
        payload = PermitRejectSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        updated = services.reject_permit(
            permit, reason=data["reason"], approver=data.get("approver_id")
        )
        record_audit(
            action=AuditAction.REJECT, instance=updated,
            changes={"status": updated.status}, reason=data["reason"],
            object_repr=updated.permit_no,
        )
        return Response(self.get_serializer(updated).data)

    @extend_schema(request=PermitStartSerializer, responses={200: WorkPermitSerializer})
    @action(detail=True, methods=["post"], url_path="start")
    def start(self, request, *args, **kwargs) -> Response:
        """开始作业：已批准 → 作业中。"""
        permit = self.get_object()
        payload = PermitStartSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        updated = services.start_permit_work(permit, operator=payload.validated_data.get("operator_id"))
        record_audit(
            action=AuditAction.UPDATE, instance=updated,
            changes={"status": updated.status}, object_repr=updated.permit_no,
        )
        return Response(self.get_serializer(updated).data)

    @extend_schema(request=PermitFinishSerializer, responses={200: WorkPermitSerializer})
    @action(detail=True, methods=["post"], url_path="finish")
    def finish(self, request, *args, **kwargs) -> Response:
        """完工：作业中 → 已完工。"""
        permit = self.get_object()
        payload = PermitFinishSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        updated = services.finish_permit_work(
            permit, result=data.get("result") or "", operator=data.get("operator_id")
        )
        record_audit(
            action=AuditAction.UPDATE, instance=updated,
            changes={"status": updated.status}, object_repr=updated.permit_no,
        )
        return Response(self.get_serializer(updated).data)

    @extend_schema(request=PermitAcceptSerializer, responses={200: WorkPermitSerializer})
    @action(detail=True, methods=["post"], url_path="accept")
    def accept(self, request, *args, **kwargs) -> Response:
        """现场验收：已完工 → 已验收。"""
        permit = self.get_object()
        payload = PermitAcceptSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        updated = services.accept_permit(
            permit, result=data["result"], accepted_by=data.get("accepted_by_id")
        )
        record_audit(
            action=AuditAction.APPROVE, instance=updated,
            changes={"status": updated.status}, reason=data["result"],
            object_repr=updated.permit_no,
        )
        return Response(self.get_serializer(updated).data)


class SafetyCheckViewSet(EhsScopedViewSet):
    queryset = SafetyCheck.objects.select_related(
        "company", "checker", "department", "equipment"
    ).all()
    serializer_class = SafetyCheckSerializer
    audit_fields = (
        "check_no", "check_type", "title", "check_date", "checker_id", "department_id",
        "equipment_id", "problem_count", "status",
    )
    search_fields = ["check_no", "title", "check_content", "conclusion"]
    filterset_fields = ["company_id", "check_type", "status", "department_id", "equipment_id"]
    ordering_fields = ["id", "check_no", "check_date", "problem_count"]
    uniqueness_error_map = {"uq_safety_check_company_no": "同一公司下检查编号已存在。"}
    required_permissions = {
        "list": "ehs.safety_check.view",
        "retrieve": "ehs.safety_check.view",
        "create": "ehs.safety_check.create",
        "partial_update": "ehs.safety_check.update",
    }

    def perform_create(self, serializer) -> None:
        data = serializer.validated_data
        data["check_no"] = str(data.get("check_no") or "").strip() or services.next_safety_check_no()
        super().perform_create(serializer)


class SpecialEquipmentInspectionViewSet(EhsScopedViewSet):
    queryset = SpecialEquipmentInspection.objects.select_related("company", "equipment").all()
    serializer_class = SpecialEquipmentInspectionSerializer
    audit_fields = (
        "certificate_no", "equipment_id", "equipment_name", "inspection_org",
        "inspection_date", "next_inspection_date", "result",
    )
    search_fields = ["certificate_no", "equipment_name", "inspection_org", "inspector"]
    filterset_fields = ["company_id", "result", "equipment_id"]
    ordering_fields = ["id", "certificate_no", "inspection_date", "next_inspection_date"]
    uniqueness_error_map = {"uq_special_equipment_cert_company_no": "同一公司下报告编号已存在。"}
    required_permissions = {
        "list": "ehs.special_equipment.view",
        "retrieve": "ehs.special_equipment.view",
        "create": "ehs.special_equipment.create",
        "partial_update": "ehs.special_equipment.update",
    }

    def perform_create(self, serializer) -> None:
        data = serializer.validated_data
        data["certificate_no"] = (
            str(data.get("certificate_no") or "").strip() or services.next_special_cert_no()
        )
        super().perform_create(serializer)


class EhsOperationLogViewSet(ReadOnlyScopedViewSet):
    """安全环保操作日志：只读。"""

    queryset = EhsOperationLog.objects.select_related("company", "operator").all()
    serializer_class = EhsOperationLogSerializer
    scope_fields = {"company_field": "company_id"}
    search_fields = ["detail", "business_label", "action"]
    filterset_fields = ["company_id", "domain", "action", "business_type", "operator_id"]
    ordering_fields = ["id", "occurred_at"]
    required_permissions = {
        "list": "ehs.log.view",
        "retrieve": "ehs.log.view",
    }
