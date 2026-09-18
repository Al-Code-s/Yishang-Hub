"""身份与权限接口。

所有写操作均在后端做权限与数据范围校验，绝不依赖前端传入的组织标识。
"""

from __future__ import annotations

from typing import Any

from django.contrib.auth import login as django_login
from django.contrib.auth import logout as django_logout
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import HasRequiredPermissions
from apps.identity import services
from apps.identity.models import LoginAttempt, Menu, Permission, Role, User
from apps.identity.selectors import build_menu_tree, my_menu_queryset, permission_groups
from apps.identity.serializers import (
    AssignRolesSerializer,
    ChangePasswordSerializer,
    LoginAttemptSerializer,
    LoginSerializer,
    MenuSerializer,
    NotificationSerializer,
    PermissionSerializer,
    ResetPasswordSerializer,
    RoleSerializer,
    RoleWriteSerializer,
    SetRoleMenusSerializer,
    SetRolePermissionsSerializer,
    SetRoleScopeSerializer,
    SetUserActiveSerializer,
    UpdateProfileSerializer,
    UserCreateSerializer,
    UserSerializer,
    UserUpdateSerializer,
)


class CsrfBootstrapView(APIView):
    """为前端写入 CSRF Cookie。

    SPA 首次访问时调用，之后所有写操作都必须携带 X-CSRFToken 请求头。
    """

    permission_classes = [AllowAny]
    authentication_classes: list[Any] = []

    @method_decorator(ensure_csrf_cookie)
    def get(self, request, *args, **kwargs) -> Response:
        return Response({"detail": "CSRF Cookie 已下发。"})


@method_decorator(csrf_protect, name="dispatch")
class LoginView(APIView):
    """口令登录。

    任务书 6.1 要求「登录接口同样防护 CSRF」：这里清空 ``authentication_classes``
    是为了让未登录的匿名请求不再触发 DRF 会话鉴权，但 DRF 的
    ``SessionAuthentication`` **只对已登录会话**调用 ``enforce_csrf``，匿名请求不会校验，
    因此必须显式用 ``csrf_protect`` 给 dispatch 加 Django 的 CSRF 校验，
    否则登录接口会变成无 CSRF 防护的写接口。
    """

    permission_classes = [AllowAny]
    authentication_classes: list[Any] = []

    @extend_schema(request=LoginSerializer, responses={200: UserSerializer})
    def post(self, request, *args, **kwargs) -> Response:
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = services.login_user(
            request,
            username=serializer.validated_data["username"],
            password=serializer.validated_data["password"],
        )
        django_login(request, user)
        # 登录成功后轮换会话标识，降低会话固定攻击风险
        request.session.cycle_key()
        return Response(_session_payload(user))


class LogoutView(APIView):
    def post(self, request, *args, **kwargs) -> Response:
        user = request.user
        services.logout_user(request, user)
        django_logout(request)
        return Response({"detail": "已退出登录。"})


class SessionView(APIView):
    """当前登录态、权限编码与菜单。前端据此渲染菜单与按钮。"""

    def get(self, request, *args, **kwargs) -> Response:
        return Response(_session_payload(request.user))


class ChangePasswordView(APIView):
    @extend_schema(request=ChangePasswordSerializer)
    def post(self, request, *args, **kwargs) -> Response:
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.change_own_password(
            request.user,
            old_password=serializer.validated_data["old_password"],
            new_password=serializer.validated_data["new_password"],
        )
        # 修改密码后使当前会话重新鉴权，其它会话因鉴权哈希变化而失效
        django_login(request, request.user)
        return Response({"detail": "密码修改成功，其它设备的登录状态已失效。"})


class ProfileView(APIView):
    def get(self, request, *args, **kwargs) -> Response:
        return Response(UserSerializer(request.user).data)

    def put(self, request, *args, **kwargs) -> Response:
        serializer = UpdateProfileSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = request.user
        for field, value in serializer.validated_data.items():
            if field == "phone" and value == "":
                value = None
            setattr(user, field, value)
        user.save(update_fields=[*serializer.validated_data.keys(), "updated_at"])
        return Response(UserSerializer(user).data)


def _session_payload(user: User) -> dict[str, Any]:
    menus = my_menu_queryset(user).order_by("sort_order", "id")
    return {
        "user": UserSerializer(user).data,
        "permissions": sorted(user.permission_codes()),
        "menus": build_menu_tree(menus),
        "unread_notifications": services.unread_notification_count(user),
    }


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.select_related("company", "department").all()
    permission_classes = [HasRequiredPermissions]
    # 用户不做物理删除，停用即可；更新统一走 PATCH 以避免全量覆盖
    http_method_names = ["get", "post", "patch", "head", "options"]
    required_permissions = {
        "list": "identity.user.view",
        "retrieve": "identity.user.view",
        "create": "identity.user.create",
        "update": "identity.user.update",
        "partial_update": "identity.user.update",
        "destroy": "identity.user.update",
        "set_active": "identity.user.deactivate",
        "reset_password": "identity.user.reset_password",
        "unlock": "identity.user.unlock",
        "assign_roles": "identity.user.assign_role",
        "options": "identity.user.view",
    }

    search_fields = ["username", "display_name", "phone"]
    ordering_fields = ["id", "username", "date_joined", "last_login"]
    filterset_fields = ["is_active", "company_id", "department_id"]

    def get_queryset(self):
        return services.scoped_users(self.request.user)

    def list(self, request, *args, **kwargs) -> Response:
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        serializer = UserSerializer(page if page is not None else queryset, many=True)
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    def create(self, request, *args, **kwargs) -> Response:
        serializer = UserCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        role_ids = data.pop("role_ids", [])
        user = services.create_user(request.user, password=data.pop("password"), role_ids=role_ids, **data)
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs) -> Response:
        user = self.get_object()
        serializer = UserUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        expected_version = data.pop("expected_version", None)
        updated = services.update_user(
            request.user, user, expected_version=expected_version, **data
        )
        return Response(UserSerializer(updated).data)

    @action(detail=True, methods=["post"], url_path="set-active")
    def set_active(self, request, *args, **kwargs) -> Response:
        serializer = SetUserActiveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = services.set_user_active(
            request.user,
            self.get_object(),
            is_active=serializer.validated_data["is_active"],
            reason=serializer.validated_data.get("reason", ""),
        )
        return Response(UserSerializer(user).data)

    @action(detail=True, methods=["post"], url_path="reset-password")
    def reset_password(self, request, *args, **kwargs) -> Response:
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.reset_user_password(
            request.user,
            self.get_object(),
            new_password=serializer.validated_data["new_password"],
            reason=serializer.validated_data.get("reason", ""),
        )
        return Response({"detail": "密码已重置，该用户下次登录需修改密码。"})

    @action(detail=True, methods=["post"])
    def unlock(self, request, *args, **kwargs) -> Response:
        user = services.unlock_user(request.user, self.get_object())
        return Response(UserSerializer(user).data)

    @action(detail=True, methods=["post"], url_path="roles")
    def assign_roles(self, request, *args, **kwargs) -> Response:
        serializer = AssignRolesSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = services.assign_user_roles(
            request.user, self.get_object(), role_ids=serializer.validated_data["role_ids"]
        )
        return Response(UserSerializer(user).data)


class RoleViewSet(viewsets.ModelViewSet):
    queryset = Role.objects.prefetch_related("permissions", "menus", "scope_grants").all()
    serializer_class = RoleSerializer
    permission_classes = [HasRequiredPermissions]
    http_method_names = ["get", "post", "patch", "head", "options"]
    required_permissions = {
        "list": "identity.role.view",
        "retrieve": "identity.role.view",
        "create": "identity.role.create",
        "update": "identity.role.update",
        "partial_update": "identity.role.update",
        "destroy": "identity.role.delete",
        "set_permissions": "identity.role.assign_permission",
        "set_menus": "identity.role.assign_permission",
        "set_scope": "identity.role.assign_permission",
    }
    search_fields = ["code", "name"]
    filterset_fields = ["is_active", "data_scope_type"]

    def create(self, request, *args, **kwargs) -> Response:
        serializer = RoleWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        role = services.create_role(request.user, **data)
        return Response(RoleSerializer(role).data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs) -> Response:
        role = self.get_object()
        serializer = RoleWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        updated = services.update_role(request.user, role, **data)
        return Response(RoleSerializer(updated).data)

    def destroy(self, request, *args, **kwargs) -> Response:
        services.delete_role(request.user, self.get_object())
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"], url_path="permissions")
    def set_permissions(self, request, *args, **kwargs) -> Response:
        serializer = SetRolePermissionsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        role = services.set_role_permissions(
            request.user, self.get_object(), permission_codes=serializer.validated_data["permission_codes"]
        )
        return Response(RoleSerializer(role).data)

    @action(detail=True, methods=["post"], url_path="menus")
    def set_menus(self, request, *args, **kwargs) -> Response:
        serializer = SetRoleMenusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        role = services.set_role_menus(
            request.user, self.get_object(), menu_codes=serializer.validated_data["menu_codes"]
        )
        return Response(RoleSerializer(role).data)

    @action(detail=True, methods=["post"], url_path="scope")
    def set_scope(self, request, *args, **kwargs) -> Response:
        serializer = SetRoleScopeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        role = services.set_role_scope(request.user, self.get_object(), **serializer.validated_data)
        return Response(RoleSerializer(role).data)


class PermissionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Permission.objects.all()
    serializer_class = PermissionSerializer
    permission_classes = [HasRequiredPermissions]
    required_permissions = {"list": "identity.permission.view", "retrieve": "identity.permission.view"}
    filterset_fields = ["module", "permission_type"]
    search_fields = ["code", "name"]

    @action(detail=False, methods=["get"], url_path="grouped")
    def grouped(self, request, *args, **kwargs) -> Response:
        return Response(permission_groups())


class MenuViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Menu.objects.all()
    serializer_class = MenuSerializer
    permission_classes = [HasRequiredPermissions]
    required_permissions = {
        "list": "identity.menu.view",
        "retrieve": "identity.menu.view",
        "tree": "identity.menu.view",
        "mine": "identity.user.view",
    }

    def list(self, request, *args, **kwargs) -> Response:
        return Response(MenuSerializer(self.get_queryset(), many=True).data)

    @action(detail=False, methods=["get"])
    def tree(self, request, *args, **kwargs) -> Response:
        return Response(build_menu_tree(Menu.objects.all().order_by("sort_order", "id")))

    @action(detail=False, methods=["get"])
    def mine(self, request, *args, **kwargs) -> Response:
        menus = my_menu_queryset(request.user).order_by("sort_order", "id")
        return Response(build_menu_tree(menus))


class LoginAttemptViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = LoginAttempt.objects.select_related("user").all()
    serializer_class = LoginAttemptSerializer
    permission_classes = [HasRequiredPermissions]
    required_permissions = {"list": "identity.log.view", "retrieve": "identity.log.view"}
    filterset_fields = ["username", "successful"]
    ordering_fields = ["id", "created_at"]


class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = NotificationSerializer
    permission_classes = [HasRequiredPermissions]
    required_permissions = {
        "list": "core.notification.view",
        "retrieve": "core.notification.view",
        "mark_read": "core.notification.view",
        "mark_all_read": "core.notification.view",
        "unread_count": "core.notification.view",
    }
    filterset_fields = ["is_read", "biz_type"]

    def get_queryset(self):
        return self.request.user.notifications.all()

    @action(detail=True, methods=["post"], url_path="read")
    def mark_read(self, request, *args, **kwargs) -> Response:
        services.mark_notification_read(request.user, self.get_object().pk)
        return Response({"detail": "已标记为已读。"})

    @action(detail=False, methods=["post"], url_path="read-all")
    def mark_all_read(self, request, *args, **kwargs) -> Response:
        request.user.notifications.filter(is_read=False).update(
            is_read=True, read_at=timezone.now()
        )
        return Response({"detail": "全部通知已标记为已读。"})

    @action(detail=False, methods=["get"], url_path="unread-count")
    def unread_count(self, request, *args, **kwargs) -> Response:
        return Response({"count": services.unread_notification_count(request.user)})
