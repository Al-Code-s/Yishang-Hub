from __future__ import annotations

from rest_framework import serializers

from apps.core.models import Notification
from apps.core.serializers import DisplayLabelsMixin
from apps.identity.models import LoginAttempt, Menu, Permission, Role, RoleScopeGrant, User


class UserSerializer(DisplayLabelsMixin, serializers.ModelSerializer):
    company_name = serializers.SerializerMethodField()
    department_name = serializers.SerializerMethodField()
    roles = serializers.SerializerMethodField()
    is_locked = serializers.BooleanField(read_only=True)

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "display_name",
            "phone",
            "email",
            "company_id",
            "company_name",
            "department_id",
            "department_name",
            "is_active",
            "is_staff",
            "must_change_password",
            "failed_login_count",
            "locked_until",
            "is_locked",
            "last_login",
            "last_login_ip",
            "roles",
            "version",
            "remark",
            "date_joined",
            "updated_at",
        )
        read_only_fields = fields

    def get_company_name(self, obj: User) -> str:
        return obj.company.name if obj.company_id else ""

    def get_department_name(self, obj: User) -> str:
        return obj.department.name if obj.department_id else ""

    def get_roles(self, obj: User) -> list[dict[str, object]]:
        return [
            {"id": role.id, "code": role.code, "name": role.name} for role in obj.active_roles()
        ]


class UserCreateSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=64)
    password = serializers.CharField(max_length=128, write_only=True, style={"input_type": "password"})
    display_name = serializers.CharField(max_length=64, required=False, allow_blank=True, default="")
    phone = serializers.CharField(max_length=32, required=False, allow_blank=True, default="")
    email = serializers.EmailField(required=False, allow_blank=True, default="")
    company_id = serializers.IntegerField(required=False, allow_null=True, default=None)
    department_id = serializers.IntegerField(required=False, allow_null=True, default=None)
    is_staff = serializers.BooleanField(required=False, default=False)
    must_change_password = serializers.BooleanField(required=False, default=True)
    remark = serializers.CharField(required=False, allow_blank=True, default="")
    role_ids = serializers.ListField(child=serializers.IntegerField(), required=False, default=list)


class UserUpdateSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=64, required=False)
    display_name = serializers.CharField(max_length=64, required=False, allow_blank=True)
    phone = serializers.CharField(max_length=32, required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    company_id = serializers.IntegerField(required=False, allow_null=True)
    department_id = serializers.IntegerField(required=False, allow_null=True)
    is_staff = serializers.BooleanField(required=False)
    remark = serializers.CharField(required=False, allow_blank=True)
    expected_version = serializers.IntegerField(required=False, allow_null=True)


class SetUserActiveSerializer(serializers.Serializer):
    is_active = serializers.BooleanField()
    reason = serializers.CharField(required=False, allow_blank=True, default="")


class ResetPasswordSerializer(serializers.Serializer):
    new_password = serializers.CharField(max_length=128, write_only=True)
    reason = serializers.CharField(required=False, allow_blank=True, default="")


class AssignRolesSerializer(serializers.Serializer):
    role_ids = serializers.ListField(child=serializers.IntegerField(), allow_empty=True)


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=64)
    password = serializers.CharField(max_length=128, write_only=True)


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(max_length=128, write_only=True)
    new_password = serializers.CharField(max_length=128, write_only=True)


class UpdateProfileSerializer(serializers.Serializer):
    display_name = serializers.CharField(max_length=64, required=False, allow_blank=True)
    phone = serializers.CharField(max_length=32, required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)


class RoleScopeGrantSerializer(DisplayLabelsMixin, serializers.ModelSerializer):
    class Meta:
        model = RoleScopeGrant
        fields = ("id", "dimension", "object_id")
        read_only_fields = fields


class RoleSerializer(DisplayLabelsMixin, serializers.ModelSerializer):
    permission_codes = serializers.SerializerMethodField()
    menu_codes = serializers.SerializerMethodField()
    scope_grants = RoleScopeGrantSerializer(many=True, read_only=True)
    user_count = serializers.SerializerMethodField()
    company_name = serializers.SerializerMethodField()

    class Meta:
        model = Role
        fields = (
            "id",
            "code",
            "name",
            "company_id",
            "company_name",
            "data_scope_type",
            "is_system",
            "is_active",
            "sort_order",
            "remark",
            "permission_codes",
            "menu_codes",
            "scope_grants",
            "user_count",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def get_permission_codes(self, obj: Role) -> list[str]:
        return sorted(obj.permissions.values_list("code", flat=True))

    def get_menu_codes(self, obj: Role) -> list[str]:
        return sorted(obj.menus.values_list("code", flat=True))

    def get_user_count(self, obj: Role) -> int:
        return obj.user_links.count()

    def get_company_name(self, obj: Role) -> str:
        return obj.company.name if obj.company_id else ""


class RoleWriteSerializer(serializers.Serializer):
    code = serializers.RegexField(r"^[a-z][a-z0-9_]*$", max_length=64, required=False)
    name = serializers.CharField(max_length=64, required=False)
    company_id = serializers.IntegerField(required=False, allow_null=True)
    data_scope_type = serializers.CharField(max_length=16, required=False)
    is_active = serializers.BooleanField(required=False)
    sort_order = serializers.IntegerField(required=False)
    remark = serializers.CharField(required=False, allow_blank=True)


class SetRolePermissionsSerializer(serializers.Serializer):
    permission_codes = serializers.ListField(child=serializers.CharField(), allow_empty=True)


class SetRoleMenusSerializer(serializers.Serializer):
    menu_codes = serializers.ListField(child=serializers.CharField(), allow_empty=True)


class SetRoleScopeSerializer(serializers.Serializer):
    data_scope_type = serializers.CharField(max_length=16)
    company_ids = serializers.ListField(child=serializers.IntegerField(), required=False, default=list)
    factory_ids = serializers.ListField(child=serializers.IntegerField(), required=False, default=list)
    department_ids = serializers.ListField(
        child=serializers.IntegerField(), required=False, default=list
    )
    warehouse_ids = serializers.ListField(
        child=serializers.IntegerField(), required=False, default=list
    )


class PermissionSerializer(DisplayLabelsMixin, serializers.ModelSerializer):
    class Meta:
        model = Permission
        fields = ("id", "code", "name", "module", "resource", "action", "permission_type")
        read_only_fields = fields


class MenuSerializer(DisplayLabelsMixin, serializers.ModelSerializer):
    class Meta:
        model = Menu
        fields = (
            "id",
            "code",
            "name",
            "parent_id",
            "path",
            "component",
            "icon",
            "menu_type",
            "permission_code",
            "sort_order",
            "is_active",
            "visible",
        )
        read_only_fields = fields


class LoginAttemptSerializer(DisplayLabelsMixin, serializers.ModelSerializer):
    class Meta:
        model = LoginAttempt
        fields = ("id", "username", "user_id", "ip_address", "successful", "failure_reason", "created_at")
        read_only_fields = fields


class NotificationSerializer(DisplayLabelsMixin, serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ("id", "title", "body", "biz_type", "biz_id", "is_read", "read_at", "created_at")
        read_only_fields = fields
