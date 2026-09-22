"""设备与备件主数据接口。

设备、备件归属公司，按数据范围过滤；零部件通过 `equipment__company_id`
继承同一范围，避免「看不到设备、却能看到其零部件」的越权读取。
"""

from __future__ import annotations

from django.db import transaction
from drf_spectacular.utils import extend_schema
from rest_framework import serializers as drf_serializers
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.exceptions import StateConflict
from apps.core.models import AuditAction
from apps.core.pagination import StandardPagination
from apps.core.permissions import HasRequiredPermissions
from apps.core.selectors import assert_in_scope
from apps.core.services import record_audit
from apps.core.viewsets import ActiveFilterMixin, ScopedModelViewSet
from apps.equipment import selectors, services
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
    InspectionResult,
    InspectionTask,
    MaintenanceItem,
    MaintenancePlan,
    MaintenanceRecord,
    MaintenanceTask,
    RepairRecord,
    RepairTask,
    SparePart,
)
from apps.equipment.serializers import (
    AbnormalAssignSerializer,
    AbnormalCloseSerializer,
    AbnormalRecordSerializer,
    AbnormalTaskSerializer,
    AbnormalTypeSerializer,
    EquipmentPartSerializer,
    EquipmentSerializer,
    EquipmentTypeSerializer,
    FaultReportSerializer,
    InspectionItemSerializer,
    InspectionRecordSerializer,
    InspectionTaskSerializer,
    MaintenanceCompleteSerializer,
    MaintenanceItemSerializer,
    MaintenancePlanSerializer,
    MaintenanceRecordSerializer,
    MaintenanceTaskSerializer,
    RepairCompleteSerializer,
    RepairDispatchSerializer,
    RepairRecordSerializer,
    RepairTaskSerializer,
    SparePartSerializer,
)
from apps.equipment.services import (
    next_abnormal_record_no,
    next_abnormal_task_no,
    next_equipment_code,
    next_fault_report_no,
    next_inspection_record_no,
    next_inspection_task_no,
    next_maintenance_plan_no,
    next_maintenance_record_no,
    next_maintenance_task_no,
    next_repair_record_no,
    next_repair_task_no,
    next_spare_part_code,
)


class EquipmentTypeViewSet(ActiveFilterMixin, ScopedModelViewSet):
    queryset = EquipmentType.objects.all()
    serializer_class = EquipmentTypeSerializer
    scope_fields = None  # 全局共享参考数据
    audit_fields = (
        "code", "name", "category", "is_special", "maintenance_cycle_days", "is_active",
    )
    search_fields = ["code", "name"]
    filterset_fields = ["category", "is_special"]
    ordering_fields = ["id", "code", "name", "category"]
    uniqueness_error_map = {"uq_equipment_type_code": "设备类型编码已存在。"}
    required_permissions = {
        "list": "equipment.type.view",
        "retrieve": "equipment.type.view",
        "create": "equipment.type.create",
        "partial_update": "equipment.type.update",
        "set_active": "equipment.type.update",
    }


class EquipmentViewSet(ActiveFilterMixin, ScopedModelViewSet):
    queryset = Equipment.objects.select_related(
        "company", "equipment_type", "factory", "workshop", "production_line",
        "station", "supplier", "owner_department", "owner_employee",
    ).all()
    serializer_class = EquipmentSerializer
    scope_fields = {"company_field": "company_id", "factory_field": "factory_id"}
    audit_fields = (
        "code", "name", "equipment_type_id", "status", "factory_id", "workshop_id",
        "production_line_id", "location", "model_no", "serial_no", "is_special",
        "owner_department_id", "owner_employee_id", "is_active",
    )
    search_fields = ["code", "name", "brand", "model_no", "serial_no", "location"]
    filterset_fields = [
        "company_id", "equipment_type_id", "status", "factory_id", "workshop_id",
        "is_special", "owner_department_id",
    ]
    ordering_fields = ["id", "code", "name", "status", "start_date", "updated_at"]
    uniqueness_error_map = {"uq_equipment_company_code": "同一公司下设备编号已存在。"}
    required_permissions = {
        "list": "equipment.equipment.view",
        "retrieve": "equipment.equipment.view",
        "create": "equipment.equipment.create",
        "partial_update": "equipment.equipment.update",
        "set_active": "equipment.equipment.deactivate",
    }

    def perform_create(self, serializer) -> None:
        """设备编号留空时按编码规则（EQ）自动取号。"""
        code = str(serializer.validated_data.get("code") or "").strip()
        serializer.validated_data["code"] = code or next_equipment_code()
        super().perform_create(serializer)


class EquipmentPartViewSet(ActiveFilterMixin, ScopedModelViewSet):
    queryset = EquipmentPart.objects.select_related("equipment", "uom").all()
    serializer_class = EquipmentPartSerializer
    scope_fields = {"company_field": "equipment__company_id"}
    audit_fields = (
        "equipment_id", "name", "part_type", "spec", "quantity", "uom_id",
        "position", "life_days", "is_active",
    )
    search_fields = ["name", "spec", "position"]
    filterset_fields = ["equipment_id", "part_type"]
    ordering_fields = ["id", "name", "life_days"]
    uniqueness_error_map = {"uq_equipment_part_name": "该设备下已存在同名零部件。"}
    required_permissions = {
        "list": "equipment.part.view",
        "retrieve": "equipment.part.view",
        "create": "equipment.part.create",
        "partial_update": "equipment.part.update",
        "set_active": "equipment.part.update",
    }


class SparePartViewSet(ActiveFilterMixin, ScopedModelViewSet):
    queryset = SparePart.objects.select_related(
        "company", "material", "equipment_type", "uom", "supplier"
    ).all()
    serializer_class = SparePartSerializer
    scope_fields = {"company_field": "company_id"}
    audit_fields = (
        "code", "name", "part_type", "spec", "material_id", "equipment_type_id",
        "uom_id", "safety_stock", "reference_price", "life_days", "supplier_id", "is_active",
    )
    search_fields = ["code", "name", "spec"]
    filterset_fields = [
        "company_id", "part_type", "equipment_type_id", "material_id", "supplier_id",
    ]
    ordering_fields = ["id", "code", "name", "life_days", "updated_at"]
    uniqueness_error_map = {"uq_spare_part_company_code": "同一公司下备件编码已存在。"}
    required_permissions = {
        "list": "equipment.spare_part.view",
        "retrieve": "equipment.spare_part.view",
        "create": "equipment.spare_part.create",
        "partial_update": "equipment.spare_part.update",
        "set_active": "equipment.spare_part.deactivate",
    }

    def perform_create(self, serializer) -> None:
        """备件编码留空时按编码规则（SP）自动取号。"""
        code = str(serializer.validated_data.get("code") or "").strip()
        serializer.validated_data["code"] = code or next_spare_part_code()
        super().perform_create(serializer)



# ---------------------------------------------------------------------------
# 阶段 4 第二步：保养 / 维修 / 点巡检 / 异常上报
#
# 所有写操作都遵守同一套约定：
# * 状态流转只在动作接口（start / complete / close …）里发生，不用 PATCH 直接改状态；
# * 任务完成时由服务层在同一事务里生成对应记录，界面不需要「再点一次生成」；
# * 公司归属由设备/计划推导，前端不必传 company_id，越权写入仍被 assert_in_scope 拦住。
# ---------------------------------------------------------------------------


def _int_or_none(value) -> int | None:
    try:
        return int(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


class DeriveCompanyMixin:
    """新增时由设备（或计划 / 报修单 / 任务）推导公司归属。"""

    def derive_company(self, serializer):
        data = serializer.validated_data
        company = data.get("company")
        if company is not None:
            return company
        equipment = data.get("equipment")
        if equipment is None and data.get("plan") is not None:
            equipment = data["plan"].equipment
        if equipment is None and data.get("fault_report") is not None:
            equipment = data["fault_report"].equipment
        if equipment is None and data.get("task") is not None:
            equipment = data["task"].equipment
        return equipment.company if equipment is not None else None

    def perform_create(self, serializer) -> None:
        company = self.derive_company(serializer)
        if company is not None:
            serializer.validated_data["company"] = company
        super().perform_create(serializer)


class MaintenanceItemViewSet(ActiveFilterMixin, ScopedModelViewSet):
    queryset = MaintenanceItem.objects.select_related("equipment_type").all()
    serializer_class = MaintenanceItemSerializer
    scope_fields = None
    audit_fields = ("code", "name", "category", "equipment_type_id", "cycle_days", "is_active")
    search_fields = ["code", "name", "standard"]
    filterset_fields = ["category", "equipment_type_id"]
    ordering_fields = ["id", "code", "name"]
    uniqueness_error_map = {"uq_maintenance_item_code": "该项目编码已存在。"}
    required_permissions = {
        "list": "equipment.maintenance_item.view",
        "retrieve": "equipment.maintenance_item.view",
        "create": "equipment.maintenance_item.create",
        "partial_update": "equipment.maintenance_item.update",
        "set_active": "equipment.maintenance_item.update",
    }


class MaintenancePlanViewSet(ActiveFilterMixin, DeriveCompanyMixin, ScopedModelViewSet):
    queryset = (
        MaintenancePlan.objects.select_related(
            "company", "equipment", "responsible_employee", "department"
        )
        .prefetch_related("items")
        .all()
    )
    serializer_class = MaintenancePlanSerializer
    scope_fields = {"company_field": "company_id"}
    audit_fields = (
        "plan_no", "name", "equipment_id", "cycle_days", "start_date", "next_date",
        "responsible_employee_id", "department_id", "is_active",
    )
    search_fields = ["plan_no", "name", "equipment__code", "equipment__name"]
    filterset_fields = ["company_id", "equipment_id", "department_id", "responsible_employee_id"]
    ordering_fields = ["id", "plan_no", "next_date", "updated_at"]
    uniqueness_error_map = {"uq_maintenance_plan_company_no": "同一公司下计划编号已存在。"}
    required_permissions = {
        "list": "equipment.maintenance_plan.view",
        "retrieve": "equipment.maintenance_plan.view",
        "create": "equipment.maintenance_plan.create",
        "partial_update": "equipment.maintenance_plan.update",
        "set_active": "equipment.maintenance_plan.update",
        "generate_tasks": "equipment.maintenance_task.create",
    }

    def perform_create(self, serializer) -> None:
        """计划编号留空时按编码规则（MP）自动取号，下次保养日期默认取开始日期。"""
        data = serializer.validated_data
        data["plan_no"] = str(data.get("plan_no") or "").strip() or next_maintenance_plan_no()
        if not data.get("next_date"):
            data["next_date"] = data["start_date"]
        super().perform_create(serializer)

    @action(detail=True, methods=["post"], url_path="generate-tasks")
    def generate_tasks(self, request, *args, **kwargs) -> Response:
        """按计划周期补生成到期保养任务（可重复调用，不会重复生成）。"""
        plan = self.get_object()
        until_raw = request.data.get("until_date")
        until_date = None
        if until_raw:
            parsed = drf_serializers.DateField().run_validation(until_raw)
            until_date = parsed
        with transaction.atomic():
            created = services.generate_maintenance_tasks(plan, until_date=until_date)
            rows = MaintenanceTaskSerializer(created, many=True).data
        plan.refresh_from_db()
        return Response(
            {
                "created_count": len(created),
                "created": rows,
                "next_date": plan.next_date,
                "limit": services.MAX_TASKS_PER_GENERATION,
            }
        )


class MaintenanceTaskViewSet(ActiveFilterMixin, DeriveCompanyMixin, ScopedModelViewSet):
    queryset = (
        MaintenanceTask.objects.select_related(
            "company", "plan", "equipment", "item", "assignee"
        ).all()
    )
    serializer_class = MaintenanceTaskSerializer
    scope_fields = {"company_field": "company_id"}
    audit_fields = (
        "task_no", "plan_id", "equipment_id", "item_id", "plan_date", "status",
        "assignee_id", "result",
    )
    search_fields = ["task_no", "equipment__code", "equipment__name", "result"]
    # plan_date 支持区间查询：保养日历按月取数时要按 plan_date 过滤
    filterset_fields = {
        "company_id": ["exact"],
        "plan_id": ["exact"],
        "equipment_id": ["exact"],
        "status": ["exact"],
        "assignee_id": ["exact"],
        "plan_date": ["exact", "gte", "lte"],
    }
    ordering_fields = ["id", "task_no", "plan_date", "updated_at"]
    uniqueness_error_map = {
        "uq_maintenance_task_company_no": "同一公司下任务编号已存在。",
        "uq_maintenance_task_plan_date": "该计划当天已存在保养任务。",
    }
    required_permissions = {
        "list": "equipment.maintenance_task.view",
        "retrieve": "equipment.maintenance_task.view",
        "create": "equipment.maintenance_task.create",
        "partial_update": "equipment.maintenance_task.update",
        "set_active": "equipment.maintenance_task.update",
        "start": "equipment.maintenance_task.execute",
        "complete": "equipment.maintenance_task.execute",
        "cancel": "equipment.maintenance_task.update",
    }

    def perform_create(self, serializer) -> None:
        data = serializer.validated_data
        data["task_no"] = str(data.get("task_no") or "").strip() or next_maintenance_task_no()
        super().perform_create(serializer)

    @action(detail=True, methods=["post"])
    def start(self, request, *args, **kwargs) -> Response:
        """开始保养：待执行 → 进行中。"""
        task = self.get_object()
        with transaction.atomic():
            services.start_equipment_task(task)
            record_audit(
                action=AuditAction.UPDATE,
                instance=task,
                changes={"status": {"before": "pending", "after": task.status}},
                object_repr=str(task),
            )
        return Response(self.get_serializer(task).data)

    @action(detail=True, methods=["post"])
    def complete(self, request, *args, **kwargs) -> Response:
        """完成保养：写入保养记录并把任务置为已完成（同一事务）。"""
        task = self.get_object()
        payload = MaintenanceCompleteSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        with transaction.atomic():
            record = services.complete_maintenance_task(
                task,
                executor=data.get("executor_id"),
                content=data.get("content", ""),
                result=data.get("result", ""),
                is_qualified=data.get("is_qualified", True),
                cost=data.get("cost"),
                maintain_date=data.get("maintain_date"),
            )
            record_audit(
                action=AuditAction.UPDATE,
                instance=task,
                changes={"status": {"before": "in_progress", "after": task.status}},
                object_repr=str(task),
            )
        task.refresh_from_db()
        return Response(
            {
                "task": self.get_serializer(task).data,
                "record": MaintenanceRecordSerializer(record).data,
            }
        )

    @action(detail=True, methods=["post"])
    def cancel(self, request, *args, **kwargs) -> Response:
        task = self.get_object()
        with transaction.atomic():
            services.cancel_equipment_task(task, reason=str(request.data.get("reason", "") or ""))
        return Response(self.get_serializer(task).data)


class MaintenanceRecordViewSet(ActiveFilterMixin, DeriveCompanyMixin, ScopedModelViewSet):
    queryset = (
        MaintenanceRecord.objects.select_related(
            "company", "task", "equipment", "item", "executor"
        ).all()
    )
    serializer_class = MaintenanceRecordSerializer
    scope_fields = {"company_field": "company_id"}
    audit_fields = (
        "record_no", "task_id", "equipment_id", "item_id", "maintain_date",
        "executor_id", "is_qualified", "cost",
    )
    search_fields = ["record_no", "equipment__code", "equipment__name", "content", "result"]
    filterset_fields = ["company_id", "equipment_id", "item_id", "executor_id", "is_qualified"]
    ordering_fields = ["id", "record_no", "maintain_date", "updated_at"]
    uniqueness_error_map = {"uq_maintenance_record_company_no": "同一公司下记录编号已存在。"}
    required_permissions = {
        "list": "equipment.maintenance_record.view",
        "retrieve": "equipment.maintenance_record.view",
        "create": "equipment.maintenance_record.create",
        "partial_update": "equipment.maintenance_record.update",
        "set_active": "equipment.maintenance_record.update",
    }

    def perform_create(self, serializer) -> None:
        data = serializer.validated_data
        data["record_no"] = str(data.get("record_no") or "").strip() or next_maintenance_record_no()
        super().perform_create(serializer)


class FaultReportViewSet(ActiveFilterMixin, DeriveCompanyMixin, ScopedModelViewSet):
    queryset = FaultReport.objects.select_related(
        "company", "equipment", "reporter"
    ).all()
    serializer_class = FaultReportSerializer
    scope_fields = {"company_field": "company_id"}
    audit_fields = ("report_no", "equipment_id", "level", "description", "reporter_id", "status")
    search_fields = ["report_no", "equipment__code", "equipment__name", "description"]
    filterset_fields = ["company_id", "equipment_id", "level", "status", "reporter_id"]
    ordering_fields = ["id", "report_no", "reported_at", "updated_at"]
    uniqueness_error_map = {"uq_fault_report_company_no": "同一公司下报修单号已存在。"}
    required_permissions = {
        "list": "equipment.fault_report.view",
        "retrieve": "equipment.fault_report.view",
        "create": "equipment.fault_report.create",
        "partial_update": "equipment.fault_report.update",
        "set_active": "equipment.fault_report.update",
        "close": "equipment.fault_report.update",
        "dispatch_repair": "equipment.repair_task.create",
    }

    def perform_create(self, serializer) -> None:
        data = serializer.validated_data
        data["report_no"] = str(data.get("report_no") or "").strip() or next_fault_report_no()
        super().perform_create(serializer)

    @action(detail=True, methods=["post"])
    def close(self, request, *args, **kwargs) -> Response:
        """关闭保修单（例如现场自行处理完毕、无需维修）。"""
        report = self.get_object()
        with transaction.atomic():
            services.close_fault_report(report)
        return Response(self.get_serializer(report).data)

    @action(detail=True, methods=["post"], url_path="dispatch")
    def dispatch_repair(self, request, *args, **kwargs) -> Response:
        """按报修单派工：生成维修任务并回写保修单状态。

        方法名刻意不叫 `dispatch`：那会覆盖 `APIView.dispatch`，
        导致整个视图集（列表 / 详情 / 全部动作）都无法响应请求。
        对外 URL 仍是 `.../dispatch/`，调用方无感。
        """
        report = self.get_object()
        payload = RepairDispatchSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        assert_in_scope(report, request.user, company_field="company_id")
        with transaction.atomic():
            task = services.create_repair_task_from_report(
                report,
                assignee=data.get("assignee_id"),
                level=data.get("level"),
                symptom=data.get("symptom", ""),
                assigned_date=data.get("assigned_date"),
                remark=data.get("remark", ""),
            )
        assert_in_scope(task, request.user, company_field="company_id")
        return Response(RepairTaskSerializer(task).data, status=status.HTTP_201_CREATED)


class RepairTaskViewSet(ActiveFilterMixin, DeriveCompanyMixin, ScopedModelViewSet):
    queryset = RepairTask.objects.select_related(
        "company", "fault_report", "equipment", "assignee"
    ).all()
    serializer_class = RepairTaskSerializer
    scope_fields = {"company_field": "company_id"}
    audit_fields = (
        "task_no", "fault_report_id", "equipment_id", "level", "assignee_id",
        "assigned_date", "status", "downtime_minutes",
    )
    search_fields = ["task_no", "equipment__code", "equipment__name", "symptom"]
    filterset_fields = ["company_id", "equipment_id", "status", "assignee_id", "fault_report_id"]
    ordering_fields = ["id", "task_no", "assigned_date", "updated_at"]
    uniqueness_error_map = {"uq_repair_task_company_no": "同一公司下任务编号已存在。"}
    required_permissions = {
        "list": "equipment.repair_task.view",
        "retrieve": "equipment.repair_task.view",
        "create": "equipment.repair_task.create",
        "partial_update": "equipment.repair_task.update",
        "set_active": "equipment.repair_task.update",
        "start": "equipment.repair_task.execute",
        "complete": "equipment.repair_task.execute",
        "cancel": "equipment.repair_task.update",
    }

    def perform_create(self, serializer) -> None:
        data = serializer.validated_data
        data["task_no"] = str(data.get("task_no") or "").strip() or next_repair_task_no()
        super().perform_create(serializer)

    @action(detail=True, methods=["post"])
    def start(self, request, *args, **kwargs) -> Response:
        task = self.get_object()
        with transaction.atomic():
            services.start_equipment_task(task)
            if task.fault_report_id:
                services.sync_fault_report_progress(task.fault_report, task)
            record_audit(
                action=AuditAction.UPDATE,
                instance=task,
                changes={"status": {"before": "pending", "after": task.status}},
                object_repr=str(task),
            )
        return Response(self.get_serializer(task).data)

    @action(detail=True, methods=["post"])
    def complete(self, request, *args, **kwargs) -> Response:
        """完成维修：写入维修记录、关闭来源报修单、按停机时长累计。"""
        task = self.get_object()
        payload = RepairCompleteSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        with transaction.atomic():
            record = services.complete_repair_task(
                task,
                repairer=data.get("repairer_id"),
                fault_reason=data.get("fault_reason", ""),
                solution=data.get("solution", ""),
                parts_used=data.get("parts_used", ""),
                cost=data.get("cost"),
                downtime_minutes=data.get("downtime_minutes"),
                result=data.get("result", ""),
                repair_date=data.get("repair_date"),
            )
            record_audit(
                action=AuditAction.UPDATE,
                instance=task,
                changes={"status": {"before": "in_progress", "after": task.status}},
                object_repr=str(task),
            )
        task.refresh_from_db()
        return Response(
            {
                "task": self.get_serializer(task).data,
                "record": RepairRecordSerializer(record).data,
            }
        )

    @action(detail=True, methods=["post"])
    def cancel(self, request, *args, **kwargs) -> Response:
        task = self.get_object()
        with transaction.atomic():
            services.cancel_equipment_task(task, reason=str(request.data.get("reason", "") or ""))
        return Response(self.get_serializer(task).data)


class RepairRecordViewSet(ActiveFilterMixin, DeriveCompanyMixin, ScopedModelViewSet):
    queryset = RepairRecord.objects.select_related(
        "company", "task", "equipment", "repairer"
    ).all()
    serializer_class = RepairRecordSerializer
    scope_fields = {"company_field": "company_id"}
    audit_fields = (
        "record_no", "task_id", "equipment_id", "repair_date", "repairer_id",
        "fault_reason", "cost", "downtime_minutes",
    )
    search_fields = ["record_no", "equipment__code", "equipment__name", "fault_reason", "solution"]
    filterset_fields = ["company_id", "equipment_id", "repairer_id", "task_id"]
    ordering_fields = ["id", "record_no", "repair_date", "updated_at"]
    uniqueness_error_map = {"uq_repair_record_company_no": "同一公司下记录编号已存在。"}
    required_permissions = {
        "list": "equipment.repair_record.view",
        "retrieve": "equipment.repair_record.view",
        "create": "equipment.repair_record.create",
        "partial_update": "equipment.repair_record.update",
        "set_active": "equipment.repair_record.update",
    }

    def perform_create(self, serializer) -> None:
        data = serializer.validated_data
        data["record_no"] = str(data.get("record_no") or "").strip() or next_repair_record_no()
        super().perform_create(serializer)


class InspectionItemViewSet(ActiveFilterMixin, ScopedModelViewSet):
    queryset = InspectionItem.objects.select_related("uom").all()
    serializer_class = InspectionItemSerializer
    scope_fields = None
    audit_fields = ("code", "name", "method", "uom_id", "lower_limit", "upper_limit", "is_active")
    search_fields = ["code", "name", "standard"]
    filterset_fields = ["method"]
    ordering_fields = ["id", "code", "name"]
    uniqueness_error_map = {"uq_inspection_item_code": "该项目编码已存在。"}
    required_permissions = {
        "list": "equipment.inspection_item.view",
        "retrieve": "equipment.inspection_item.view",
        "create": "equipment.inspection_item.create",
        "partial_update": "equipment.inspection_item.update",
        "set_active": "equipment.inspection_item.update",
    }


class InspectionTaskViewSet(ActiveFilterMixin, DeriveCompanyMixin, ScopedModelViewSet):
    queryset = (
        InspectionTask.objects.select_related("company", "equipment", "assignee")
        .prefetch_related("items")
        .all()
    )
    serializer_class = InspectionTaskSerializer
    scope_fields = {"company_field": "company_id"}
    audit_fields = (
        "task_no", "task_type", "equipment_id", "plan_date", "status", "assignee_id", "result",
    )
    search_fields = ["task_no", "equipment__code", "equipment__name", "result"]
    filterset_fields = {
        "company_id": ["exact"],
        "equipment_id": ["exact"],
        "task_type": ["exact"],
        "status": ["exact"],
        "assignee_id": ["exact"],
        "plan_date": ["exact", "gte", "lte"],
    }
    ordering_fields = ["id", "task_no", "plan_date", "updated_at"]
    uniqueness_error_map = {"uq_inspection_task_company_no": "同一公司下任务编号已存在。"}
    required_permissions = {
        "list": "equipment.inspection_task.view",
        "retrieve": "equipment.inspection_task.view",
        "create": "equipment.inspection_task.create",
        "partial_update": "equipment.inspection_task.update",
        "set_active": "equipment.inspection_task.update",
        "start": "equipment.inspection_task.execute",
        "complete": "equipment.inspection_task.execute",
        "cancel": "equipment.inspection_task.update",
    }

    def perform_create(self, serializer) -> None:
        data = serializer.validated_data
        data["task_no"] = str(data.get("task_no") or "").strip() or next_inspection_task_no()
        super().perform_create(serializer)

    @action(detail=True, methods=["post"])
    def start(self, request, *args, **kwargs) -> Response:
        task = self.get_object()
        with transaction.atomic():
            services.start_equipment_task(task)
        return Response(self.get_serializer(task).data)

    @action(detail=True, methods=["post"])
    def complete(self, request, *args, **kwargs) -> Response:
        """结束点巡检任务。异常明细请另行登记点巡检记录，由记录触发转报修。"""
        task = self.get_object()
        with transaction.atomic():
            services.finish_equipment_task(task, result=str(request.data.get("result", "") or ""))
            record_audit(
                action=AuditAction.UPDATE,
                instance=task,
                changes={"status": {"before": "in_progress", "after": task.status}},
                object_repr=str(task),
            )
        return Response(self.get_serializer(task).data)

    @action(detail=True, methods=["post"])
    def cancel(self, request, *args, **kwargs) -> Response:
        task = self.get_object()
        with transaction.atomic():
            services.cancel_equipment_task(task, reason=str(request.data.get("reason", "") or ""))
        return Response(self.get_serializer(task).data)


class InspectionRecordViewSet(ActiveFilterMixin, DeriveCompanyMixin, ScopedModelViewSet):
    queryset = InspectionRecord.objects.select_related(
        "company", "task", "equipment", "item", "inspector"
    ).all()
    serializer_class = InspectionRecordSerializer
    scope_fields = {"company_field": "company_id"}
    audit_fields = (
        "record_no", "task_id", "equipment_id", "item_id", "measured_value",
        "result", "inspector_id",
    )
    search_fields = ["record_no", "equipment__code", "equipment__name", "abnormal_desc"]
    filterset_fields = ["company_id", "equipment_id", "item_id", "result", "inspector_id"]
    ordering_fields = ["id", "record_no", "inspected_at", "updated_at"]
    uniqueness_error_map = {"uq_inspection_record_company_no": "同一公司下记录编号已存在。"}
    required_permissions = {
        "list": "equipment.inspection_record.view",
        "retrieve": "equipment.inspection_record.view",
        "create": "equipment.inspection_record.create",
        "partial_update": "equipment.inspection_record.update",
        "set_active": "equipment.inspection_record.update",
        "raise_fault": "equipment.fault_report.create",
    }

    def perform_create(self, serializer) -> None:
        data = serializer.validated_data
        data["record_no"] = str(data.get("record_no") or "").strip() or next_inspection_record_no()
        super().perform_create(serializer)

    @action(detail=True, methods=["post"], url_path="raise-fault")
    def raise_fault(self, request, *args, **kwargs) -> Response:
        """点巡检异常一键转报修，形成「点检发现 → 报修 → 维修」闭环。"""
        record = self.get_object()
        if record.result != InspectionResult.ABNORMAL:
            raise StateConflict("只有判定为异常的记录才能转报修。", code="NOT_ABNORMAL_RECORD")
        level = str(request.data.get("level") or FaultLevel.MEDIUM)
        with transaction.atomic():
            report = services.raise_fault_from_inspection(record, level=level)
        assert_in_scope(report, request.user, company_field="company_id")
        return Response(FaultReportSerializer(report).data, status=status.HTTP_201_CREATED)


class AbnormalTypeViewSet(ActiveFilterMixin, ScopedModelViewSet):
    queryset = AbnormalType.objects.all()
    serializer_class = AbnormalTypeSerializer
    scope_fields = None
    audit_fields = ("code", "name", "level", "is_active")
    search_fields = ["code", "name"]
    filterset_fields = ["level"]
    ordering_fields = ["id", "code", "name"]
    uniqueness_error_map = {"uq_abnormal_type_code": "该类型编码已存在。"}
    required_permissions = {
        "list": "equipment.abnormal_type.view",
        "retrieve": "equipment.abnormal_type.view",
        "create": "equipment.abnormal_type.create",
        "partial_update": "equipment.abnormal_type.update",
        "set_active": "equipment.abnormal_type.update",
    }


class AbnormalTaskViewSet(ActiveFilterMixin, DeriveCompanyMixin, ScopedModelViewSet):
    queryset = AbnormalTask.objects.select_related(
        "company", "abnormal_type", "equipment", "reported_by", "handler"
    ).all()
    serializer_class = AbnormalTaskSerializer
    scope_fields = {"company_field": "company_id"}
    audit_fields = (
        "task_no", "abnormal_type_id", "equipment_id", "source", "description",
        "reported_by_id", "status", "handler_id", "deadline",
    )
    search_fields = ["task_no", "description", "equipment__code", "equipment__name"]
    filterset_fields = ["company_id", "abnormal_type_id", "equipment_id", "source", "status", "handler_id"]
    ordering_fields = ["id", "task_no", "reported_at", "deadline", "updated_at"]
    uniqueness_error_map = {"uq_abnormal_task_company_no": "同一公司下任务编号已存在。"}
    required_permissions = {
        "list": "equipment.abnormal_task.view",
        "retrieve": "equipment.abnormal_task.view",
        "create": "equipment.abnormal_task.create",
        "partial_update": "equipment.abnormal_task.update",
        "set_active": "equipment.abnormal_task.update",
        "assign": "equipment.abnormal_task.handle",
        "handle": "equipment.abnormal_task.handle",
        "close": "equipment.abnormal_task.handle",
    }

    def perform_create(self, serializer) -> None:
        data = serializer.validated_data
        data["task_no"] = str(data.get("task_no") or "").strip() or next_abnormal_task_no()
        super().perform_create(serializer)

    @action(detail=True, methods=["post"])
    def assign(self, request, *args, **kwargs) -> Response:
        """分派处理人（可同时设定处理期限）。"""
        task = self.get_object()
        payload = AbnormalAssignSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        with transaction.atomic():
            services.assign_abnormal_task(
                task,
                handler=payload.validated_data.get("handler_id"),
                deadline=payload.validated_data.get("deadline"),
            )
        return Response(self.get_serializer(task).data)

    @action(detail=True, methods=["post"])
    def handle(self, request, *args, **kwargs) -> Response:
        """登记处理措施，进入处理中。"""
        task = self.get_object()
        with transaction.atomic():
            services.start_abnormal_handling(
                task, action=str(request.data.get("action", "") or "")
            )
        return Response(self.get_serializer(task).data)

    @action(detail=True, methods=["post"])
    def close(self, request, *args, **kwargs) -> Response:
        """关闭异常任务并生成异常记录。"""
        task = self.get_object()
        payload = AbnormalCloseSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        with transaction.atomic():
            record = services.close_abnormal_task(
                task,
                action=data.get("action", ""),
                result=data.get("result", ""),
                handle_date=data.get("handle_date"),
                handler=data.get("handler_id"),
            )
        task.refresh_from_db()
        return Response(
            {
                "task": self.get_serializer(task).data,
                "record": AbnormalRecordSerializer(record).data,
            }
        )


class AbnormalRecordViewSet(ActiveFilterMixin, DeriveCompanyMixin, ScopedModelViewSet):
    queryset = AbnormalRecord.objects.select_related(
        "company", "task", "abnormal_type", "equipment", "handler"
    ).all()
    serializer_class = AbnormalRecordSerializer
    scope_fields = {"company_field": "company_id"}
    audit_fields = (
        "record_no", "task_id", "abnormal_type_id", "equipment_id", "handle_date", "handler_id",
    )
    search_fields = ["record_no", "action", "result", "equipment__code", "equipment__name"]
    filterset_fields = ["company_id", "abnormal_type_id", "equipment_id", "handler_id", "task_id"]
    ordering_fields = ["id", "record_no", "handle_date", "updated_at"]
    uniqueness_error_map = {"uq_abnormal_record_company_no": "同一公司下记录编号已存在。"}
    required_permissions = {
        "list": "equipment.abnormal_record.view",
        "retrieve": "equipment.abnormal_record.view",
        "create": "equipment.abnormal_record.create",
        "partial_update": "equipment.abnormal_record.update",
        "set_active": "equipment.abnormal_record.update",
    }

    def perform_create(self, serializer) -> None:
        data = serializer.validated_data
        data["record_no"] = str(data.get("record_no") or "").strip() or next_abnormal_record_no()
        super().perform_create(serializer)


class SparePartStockView(APIView):
    """备件现存量（库存台账）。

    数量全部来自仓储模块的统一库存余额，本接口只做「备件 × 仓库 × 储位」的联表展示，
    **不复制、不缓存**库存数字：仓储里改了库存，这里立刻反映。
    """

    permission_classes = [HasRequiredPermissions]
    required_permissions = {"GET": "equipment.spare_part_stock.view"}

    @extend_schema(responses={200: dict})
    def get(self, request, *args, **kwargs) -> Response:
        rows = selectors.spare_part_stock_rows(
            request.user,
            company_id=_int_or_none(request.query_params.get("company_id")),
            warehouse_id=_int_or_none(request.query_params.get("warehouse_id")),
            part_type=(request.query_params.get("part_type") or "").strip() or None,
            below_safety_only=(request.query_params.get("below_safety") or "").lower()
            in {"1", "true", "yes"},
            search=(request.query_params.get("search") or "").strip(),
        )
        paginator = StandardPagination()
        page = paginator.paginate_queryset(rows, request, view=self)
        return paginator.get_paginated_response(page)
