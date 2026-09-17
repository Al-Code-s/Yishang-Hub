from __future__ import annotations

from rest_framework import serializers

from apps.core.serializers import ReferenceIdSerializer
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


class CompanySerializer(ReferenceIdSerializer):
    class Meta:
        model = Company
        fields = (
            "id", "code", "name", "short_name", "address", "contact_person",
            "contact_phone", "is_active", "remark", "version", "created_at", "updated_at",
        )
        read_only_fields = ("id", "version", "created_at", "updated_at")


class DepartmentSerializer(ReferenceIdSerializer):
    company_name = serializers.SerializerMethodField()
    parent_name = serializers.SerializerMethodField()
    full_path = serializers.SerializerMethodField()

    class Meta:
        model = Department
        fields = (
            "id", "company_id", "company_name", "parent_id", "parent_name", "full_path",
            "code", "name", "department_type", "sort_order", "is_active", "remark",
            "version", "created_at", "updated_at",
        )
        read_only_fields = ("id", "company_name", "parent_name", "full_path", "version", "created_at", "updated_at")

    def validate(self, attrs):
        """层级合法性：上级部门必须同公司，且不能形成环。"""
        company = attrs.get("company", getattr(self.instance, "company", None))
        parent = attrs.get("parent", getattr(self.instance, "parent", None))
        if parent is not None:
            if company is None:
                raise serializers.ValidationError({"company_id": "请先指定所属公司。"})
            if parent.company_id != company.pk:
                raise serializers.ValidationError({"parent_id": "上级部门必须属于同一公司。"})
            if self.instance is not None:
                node = parent
                seen = {self.instance.pk}
                while node is not None:
                    if node.pk in seen:
                        raise serializers.ValidationError({"parent_id": "部门层级存在循环引用。"})
                    seen.add(node.pk)
                    node = node.parent
        return attrs
    def get_company_name(self, obj: Department) -> str:
        return obj.company.name if obj.company_id else ""

    def get_parent_name(self, obj: Department) -> str:
        return obj.parent.name if obj.parent_id else ""

    def get_full_path(self, obj: Department) -> str:
        names: list[str] = []
        node = obj
        seen: set[int] = set()
        while node is not None and node.pk not in seen:
            seen.add(node.pk)
            names.append(node.name)
            node = node.parent
        return " / ".join(reversed(names))


class FactorySerializer(ReferenceIdSerializer):
    company_name = serializers.SerializerMethodField()
    manager_name = serializers.SerializerMethodField()

    class Meta:
        model = Factory
        fields = (
            "id", "company_id", "company_name", "code", "name", "address", "manager_id",
            "manager_name", "is_active", "remark", "version", "created_at", "updated_at",
        )
        read_only_fields = ("id", "company_name", "manager_name", "version", "created_at", "updated_at")

    def get_company_name(self, obj: Factory) -> str:
        return obj.company.name if obj.company_id else ""

    def get_manager_name(self, obj: Factory) -> str:
        return obj.manager.name if obj.manager_id else ""


class WorkshopSerializer(ReferenceIdSerializer):
    factory_name = serializers.SerializerMethodField()

    class Meta:
        model = Workshop
        fields = (
            "id", "factory_id", "factory_name", "code", "name", "workshop_type",
            "sort_order", "is_active", "remark", "version", "created_at", "updated_at",
        )
        read_only_fields = ("id", "factory_name", "version", "created_at", "updated_at")

    def get_factory_name(self, obj: Workshop) -> str:
        return obj.factory.name if obj.factory_id else ""


class ProductionLineSerializer(ReferenceIdSerializer):
    workshop_name = serializers.SerializerMethodField()
    factory_id = serializers.IntegerField(source="workshop.factory_id", read_only=True)

    class Meta:
        model = ProductionLine
        fields = (
            "id", "workshop_id", "workshop_name", "factory_id", "code", "name", "line_type",
            "daily_capacity", "is_active", "remark", "version", "created_at", "updated_at",
        )
        read_only_fields = (
            "id", "workshop_name", "factory_id", "version", "created_at", "updated_at",
        )

    def get_workshop_name(self, obj: ProductionLine) -> str:
        return obj.workshop.name if obj.workshop_id else ""


class StationSerializer(ReferenceIdSerializer):
    line_name = serializers.SerializerMethodField()
    workshop_id = serializers.IntegerField(source="line.workshop_id", read_only=True)

    class Meta:
        model = Station
        fields = (
            "id", "line_id", "line_name", "workshop_id", "code", "name", "process_name",
            "sort_order", "is_active", "remark", "version", "created_at", "updated_at",
        )
        read_only_fields = ("id", "line_name", "workshop_id", "version", "created_at", "updated_at")

    def get_line_name(self, obj: Station) -> str:
        return obj.line.name if obj.line_id else ""


class EmployeeSerializer(ReferenceIdSerializer):
    company_name = serializers.SerializerMethodField()
    department_name = serializers.SerializerMethodField()
    factory_name = serializers.SerializerMethodField()
    username = serializers.SerializerMethodField()

    class Meta:
        model = Employee
        fields = (
            "id", "company_id", "company_name", "department_id", "department_name",
            "factory_id", "factory_name", "user_id", "username", "employee_no", "name",
            "gender", "phone", "email", "position", "employment_type", "hire_date",
            "leave_date", "status", "is_active", "remark", "version", "created_at", "updated_at",
        )
        read_only_fields = (
            "id", "company_name", "department_name", "factory_name", "username",
            "version", "created_at", "updated_at",
        )

    def get_company_name(self, obj: Employee) -> str:
        return obj.company.name if obj.company_id else ""

    def get_department_name(self, obj: Employee) -> str:
        return obj.department.name if obj.department_id else ""

    def get_factory_name(self, obj: Employee) -> str:
        return obj.factory.name if obj.factory_id else ""

    def get_username(self, obj: Employee) -> str:
        return obj.user.username if obj.user_id else ""


class ShiftSerializer(ReferenceIdSerializer):
    company_name = serializers.SerializerMethodField()
    duration_hours = serializers.SerializerMethodField()

    class Meta:
        model = Shift
        fields = (
            "id", "company_id", "company_name", "code", "name", "start_time", "end_time",
            "cross_day", "break_minutes", "duration_hours", "is_active", "remark",
            "version", "created_at", "updated_at",
        )
        read_only_fields = (
            "id", "company_name", "cross_day", "duration_hours", "version", "created_at", "updated_at",
        )

    def get_company_name(self, obj: Shift) -> str:
        return obj.company.name if obj.company_id else ""

    def get_duration_hours(self, obj: Shift) -> str:
        start_minutes = obj.start_time.hour * 60 + obj.start_time.minute
        end_minutes = obj.end_time.hour * 60 + obj.end_time.minute
        if obj.cross_day:
            end_minutes += 24 * 60
        worked = end_minutes - start_minutes - (obj.break_minutes or 0)
        return f"{worked / 60:.2f}"

    def validate(self, attrs):
        """班次时间必须可判定：不允许上下班时间相同，休息时长不能超过班次跨度。"""
        start = attrs.get("start_time", getattr(self.instance, "start_time", None))
        end = attrs.get("end_time", getattr(self.instance, "end_time", None))
        break_minutes = attrs.get("break_minutes", getattr(self.instance, "break_minutes", 0) or 0)
        if start is None or end is None:
            return attrs
        if start == end:
            raise serializers.ValidationError(
                {"end_time": "上班时间与下班时间不能相同；跨夜班请填写真实的下班时间（如 04:00）。"}
            )
        start_minutes = start.hour * 60 + start.minute
        end_minutes = end.hour * 60 + end.minute
        if end <= start:
            end_minutes += 24 * 60
        if break_minutes >= end_minutes - start_minutes:
            raise serializers.ValidationError(
                {"break_minutes": "休息时长必须小于班次总时长。"}
            )
        return attrs


class TeamSerializer(ReferenceIdSerializer):
    workshop_name = serializers.SerializerMethodField()
    leader_name = serializers.SerializerMethodField()
    shift_name = serializers.SerializerMethodField()
    members = serializers.SerializerMethodField()

    class Meta:
        model = Team
        fields = (
            "id", "code", "name", "workshop_id", "workshop_name", "leader_id", "leader_name",
            "shift_id", "shift_name", "members", "is_active", "remark",
            "version", "created_at", "updated_at",
        )
        read_only_fields = (
            "id", "workshop_name", "leader_name", "shift_name", "members",
            "version", "created_at", "updated_at",
        )

    def get_workshop_name(self, obj: Team) -> str:
        return obj.workshop.name if obj.workshop_id else ""

    def get_leader_name(self, obj: Team) -> str:
        return obj.leader.name if obj.leader_id else ""

    def get_shift_name(self, obj: Team) -> str:
        return obj.shift.name if obj.shift_id else ""

    def get_members(self, obj: Team) -> list[dict[str, object]]:
        return [
            {
                "id": member.id,
                "employee_id": member.employee_id,
                "employee_no": member.employee.employee_no,
                "name": member.employee.name,
                "role_in_team": member.role_in_team,
                "is_active": member.is_active,
            }
            for member in obj.members.select_related("employee").all()
        ]


class TeamMemberWriteSerializer(serializers.Serializer):
    members = serializers.ListField(child=serializers.DictField(), allow_empty=True)

    def validate_members(self, value: list[dict]) -> list[dict]:
        cleaned: list[dict] = []
        seen: set[int] = set()
        for index, item in enumerate(value):
            employee_id = item.get("employee_id")
            if employee_id in (None, ""):
                raise serializers.ValidationError(f"第 {index + 1} 行缺少 employee_id。")
            try:
                employee_id_int = int(employee_id)
            except (TypeError, ValueError) as exc:
                raise serializers.ValidationError(
                    f"第 {index + 1} 行的 employee_id 不是整数。"
                ) from exc
            if employee_id_int in seen:
                raise serializers.ValidationError(f"第 {index + 1} 行的员工重复。")
            seen.add(employee_id_int)
            cleaned.append(
                {
                    "employee_id": employee_id_int,
                    "role_in_team": str(item.get("role_in_team", "") or ""),
                    "start_date": item.get("start_date") or None,
                    "end_date": item.get("end_date") or None,
                }
            )
        return cleaned


__all__ = [
    "CompanySerializer",
    "DepartmentSerializer",
    "EmployeeSerializer",
    "FactorySerializer",
    "ProductionLineSerializer",
    "ShiftSerializer",
    "StationSerializer",
    "TeamMember",
    "TeamMemberWriteSerializer",
    "TeamSerializer",
    "WorkshopSerializer",
]
