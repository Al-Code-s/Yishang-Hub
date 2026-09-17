"""组织与工厂接口。所有列表都按数据范围过滤。"""

from __future__ import annotations

from django.db import transaction
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.exceptions import ObjectNotFound
from apps.core.models import AuditAction
from apps.core.services import record_audit
from apps.core.viewsets import ActiveFilterMixin, ScopedModelViewSet
from apps.factory.models import (
    Company,
    Department,
    Employee,
    Factory,
    ProductionLine,
    Shift,
    Station,
    Team,
    TeamMember,
    Workshop,
)
from apps.factory.serializers import (
    CompanySerializer,
    DepartmentSerializer,
    EmployeeSerializer,
    FactorySerializer,
    ProductionLineSerializer,
    ShiftSerializer,
    StationSerializer,
    TeamMemberWriteSerializer,
    TeamSerializer,
    WorkshopSerializer,
)


class CompanyViewSet(ActiveFilterMixin, ScopedModelViewSet):
    queryset = Company.objects.all()
    serializer_class = CompanySerializer
    # Company 自身即公司维度，直接按主键收敛
    scope_fields = {"company_field": "id", "owner_field": "created_by_id"}
    audit_fields = ("code", "name", "short_name", "is_active", "contact_person", "contact_phone")
    search_fields = ["code", "name", "short_name"]
    ordering_fields = ["id", "code", "name"]
    uniqueness_error_map = {"uq_company_code": "公司编码已存在。", "code": "公司编码已存在。"}
    required_permissions = {
        "list": "factory.company.view",
        "retrieve": "factory.company.view",
        "create": "factory.company.create",
        "partial_update": "factory.company.update",
        "set_active": "factory.company.update",
    }


class DepartmentViewSet(ActiveFilterMixin, ScopedModelViewSet):
    queryset = Department.objects.select_related("company", "parent").all()
    serializer_class = DepartmentSerializer
    scope_fields = {"company_field": "company_id", "department_field": "id"}
    audit_fields = ("company_id", "parent_id", "code", "name", "department_type", "is_active")
    search_fields = ["code", "name"]
    filterset_fields = ["company_id", "parent_id", "department_type"]
    ordering_fields = ["id", "code", "sort_order"]
    uniqueness_error_map = {"uq_department_company_code": "同一公司下部门编码已存在。"}
    required_permissions = {
        "list": "factory.department.view",
        "retrieve": "factory.department.view",
        "create": "factory.department.create",
        "partial_update": "factory.department.update",
        "set_active": "factory.department.update",
        "tree": "factory.department.view",
    }


    @action(detail=False, methods=["get"])
    def tree(self, request, *args, **kwargs):
        rows = list(self.filter_queryset(self.get_queryset()))
        nodes = {row.id: {**DepartmentSerializer(row).data, "children": []} for row in rows}
        roots = []
        for row in rows:
            node = nodes[row.id]
            parent = nodes.get(row.parent_id) if row.parent_id else None
            (parent["children"] if parent else roots).append(node)
        return Response(roots)


class FactoryViewSet(ActiveFilterMixin, ScopedModelViewSet):
    queryset = Factory.objects.select_related("company", "manager").all()
    serializer_class = FactorySerializer
    scope_fields = {"company_field": "company_id", "factory_field": "id"}
    audit_fields = ("company_id", "code", "name", "manager_id", "is_active", "address")
    search_fields = ["code", "name"]
    filterset_fields = ["company_id"]
    ordering_fields = ["id", "code", "name"]
    uniqueness_error_map = {"uq_factory_company_code": "同一公司下工厂编码已存在。"}
    required_permissions = {
        "list": "factory.factory.view",
        "retrieve": "factory.factory.view",
        "create": "factory.factory.create",
        "partial_update": "factory.factory.update",
        "set_active": "factory.factory.update",
    }


class WorkshopViewSet(ActiveFilterMixin, ScopedModelViewSet):
    queryset = Workshop.objects.select_related("factory").all()
    serializer_class = WorkshopSerializer
    scope_fields = {"company_field": "factory__company_id", "factory_field": "factory_id"}
    audit_fields = ("factory_id", "code", "name", "workshop_type", "is_active")
    search_fields = ["code", "name"]
    filterset_fields = ["factory_id", "workshop_type"]
    ordering_fields = ["id", "code", "sort_order"]
    uniqueness_error_map = {"uq_workshop_factory_code": "同一工厂下车间编码已存在。"}
    required_permissions = {
        "list": "factory.workshop.view",
        "retrieve": "factory.workshop.view",
        "create": "factory.workshop.create",
        "partial_update": "factory.workshop.update",
        "set_active": "factory.workshop.update",
    }


class ProductionLineViewSet(ActiveFilterMixin, ScopedModelViewSet):
    queryset = ProductionLine.objects.select_related("workshop", "workshop__factory").all()
    serializer_class = ProductionLineSerializer
    scope_fields = {
        "company_field": "workshop__factory__company_id",
        "factory_field": "workshop__factory_id",
    }
    audit_fields = ("workshop_id", "code", "name", "line_type", "daily_capacity", "is_active")
    search_fields = ["code", "name"]
    filterset_fields = ["workshop_id", "line_type"]
    ordering_fields = ["id", "code"]
    uniqueness_error_map = {"uq_line_workshop_code": "同一车间下线体编码已存在。"}
    required_permissions = {
        "list": "factory.line.view",
        "retrieve": "factory.line.view",
        "create": "factory.line.create",
        "partial_update": "factory.line.update",
        "set_active": "factory.line.update",
    }


class StationViewSet(ActiveFilterMixin, ScopedModelViewSet):
    queryset = Station.objects.select_related("line", "line__workshop").all()
    serializer_class = StationSerializer
    scope_fields = {
        "company_field": "line__workshop__factory__company_id",
        "factory_field": "line__workshop__factory_id",
    }
    audit_fields = ("line_id", "code", "name", "process_name", "is_active", "sort_order")
    search_fields = ["code", "name", "process_name"]
    filterset_fields = ["line_id"]
    ordering_fields = ["id", "code", "sort_order"]
    uniqueness_error_map = {"uq_station_line_code": "同一线体下工位编码已存在。"}
    required_permissions = {
        "list": "factory.station.view",
        "retrieve": "factory.station.view",
        "create": "factory.station.create",
        "partial_update": "factory.station.update",
        "set_active": "factory.station.update",
    }


class EmployeeViewSet(ActiveFilterMixin, ScopedModelViewSet):
    queryset = Employee.objects.select_related("company", "department", "factory", "user").all()
    serializer_class = EmployeeSerializer
    scope_fields = {
        "company_field": "company_id",
        "department_field": "department_id",
        "factory_field": "factory_id",
        "owner_field": "user_id",
    }
    audit_fields = (
        "employee_no", "name", "department_id", "factory_id", "position",
        "status", "is_active", "user_id",
    )
    search_fields = ["employee_no", "name", "phone", "position"]
    filterset_fields = ["company_id", "department_id", "factory_id", "status"]
    ordering_fields = ["id", "employee_no", "hire_date"]
    uniqueness_error_map = {"uq_employee_company_no": "同一公司下工号已存在。"}
    required_permissions = {
        "list": "factory.employee.view",
        "retrieve": "factory.employee.view",
        "create": "factory.employee.create",
        "partial_update": "factory.employee.update",
        "set_active": "factory.employee.update",
    }


class ShiftViewSet(ActiveFilterMixin, ScopedModelViewSet):
    queryset = Shift.objects.select_related("company").all()
    serializer_class = ShiftSerializer
    scope_fields = {"company_field": "company_id"}
    audit_fields = ("company_id", "code", "name", "start_time", "end_time", "cross_day", "is_active")
    search_fields = ["code", "name"]
    filterset_fields = ["company_id"]
    ordering_fields = ["id", "code"]
    uniqueness_error_map = {"uq_shift_company_code": "同一公司下班次编码已存在。"}
    required_permissions = {
        "list": "factory.shift.view",
        "retrieve": "factory.shift.view",
        "create": "factory.shift.create",
        "partial_update": "factory.shift.update",
        "set_active": "factory.shift.update",
    }


class TeamViewSet(ActiveFilterMixin, ScopedModelViewSet):
    queryset = Team.objects.select_related("workshop", "leader", "shift").all()
    serializer_class = TeamSerializer
    scope_fields = {
        "company_field": "workshop__factory__company_id",
        "factory_field": "workshop__factory_id",
    }
    audit_fields = ("code", "name", "workshop_id", "leader_id", "shift_id", "is_active")
    search_fields = ["code", "name"]
    filterset_fields = ["workshop_id", "shift_id"]
    ordering_fields = ["id", "code"]
    required_permissions = {
        "list": "factory.team.view",
        "retrieve": "factory.team.view",
        "create": "factory.team.create",
        "partial_update": "factory.team.update",
        "set_active": "factory.team.update",
        "set_members": "factory.team.update",
    }

    @action(detail=True, methods=["post"], url_path="members")
    def set_members(self, request, *args, **kwargs):
        """整体替换班组成员。保留成员快照的依据是历史报工记录，而非本表。"""
        team = self.get_object()
        serializer = TeamMemberWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        members = serializer.validated_data["members"]

        employee_ids = [item["employee_id"] for item in members]
        existing_ids = set(
            Employee.objects.filter(id__in=employee_ids).values_list("id", flat=True)
        )
        missing = set(employee_ids) - existing_ids
        if missing:
            raise ObjectNotFound(f"员工不存在：{sorted(missing)}", code="EMPLOYEE_NOT_FOUND")

        with transaction.atomic():
            before = sorted(team.members.values_list("employee_id", flat=True))
            TeamMember.objects.filter(team=team).exclude(employee_id__in=employee_ids).delete()
            keep = set(TeamMember.objects.filter(team=team).values_list("employee_id", flat=True))
            TeamMember.objects.bulk_create(
                [
                    TeamMember(
                        team=team,
                        employee_id=item["employee_id"],
                        role_in_team=item["role_in_team"],
                        start_date=item["start_date"],
                        end_date=item["end_date"],
                    )
                    for item in members
                    if item["employee_id"] not in keep
                ]
            )
            after = sorted(team.members.values_list("employee_id", flat=True))
            record_audit(
                action=AuditAction.UPDATE,
                instance=team,
                changes={"members": {"before": before, "after": after}},
                reason="调整班组成员",
                object_repr=str(team),
            )
        return Response(TeamSerializer(team).data, status=status.HTTP_200_OK)
