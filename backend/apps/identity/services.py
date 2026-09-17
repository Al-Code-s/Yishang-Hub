"""用户与权限业务服务：一律在事务内完成校验、写入与审计。"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from apps.core.exceptions import (
    APIError,
    NotPermitted,
    ObjectNotFound,
    StateConflict,
    ValidationFailed,
)
from apps.core.models import AuditAction
from apps.core.selectors import assert_in_scope, scoped_queryset
from apps.core.services import build_changes, record_audit, require_object, snapshot_fields
from apps.identity.models import (
    LoginAttempt,
    Menu,
    Permission,
    Role,
    RoleScopeGrant,
    ScopeDimension,
    User,
    UserRole,
)

USER_AUDIT_FIELDS = (
    "username",
    "display_name",
    "phone",
    "email",
    "company_id",
    "department_id",
    "is_active",
    "is_staff",
    "must_change_password",
)

ROLE_AUDIT_FIELDS = ("code", "name", "company_id", "data_scope_type", "is_active", "remark")

IP_RATE_LIMIT_MULTIPLIER = 4


# --------------------------------------------------------------------------
# 登录 / 登出 / 口令
# --------------------------------------------------------------------------


def _client_ip(request: Any) -> str:
    from apps.core.middleware import _client_ip as resolve_ip

    return resolve_ip(request) if request is not None else ""


def _check_ip_rate_limit(ip: str, limit: int, window_minutes: int) -> None:
    """按来源 IP 粗粒度限流，避免对单一账号的暴力破解也算在账号锁定上。"""
    if not ip:
        return
    cache_key = f"identity:login_rate:{ip}"
    try:
        count = cache.get(cache_key, 0) + 1
        cache.set(cache_key, count, timeout=window_minutes * 60)
    except Exception:  # 缓存不可用时不应阻断登录，退化为仅账号级锁定
        return
    if count > limit * IP_RATE_LIMIT_MULTIPLIER:
        raise APIError(
            "登录尝试过于频繁，请稍后再试。",
            code="LOGIN_RATE_LIMITED",
            status_code=429,
        )


def _record_login_failure(
    *,
    identifier: str,
    user: User | None,
    ip: str,
    reason: str,
    lock_limit: int | None = None,
    lock_minutes: int = 0,
) -> None:
    """在独立事务中记录一次登录失败。

    说明：登录失败必须以异常形式返回给调用方，如果把「记录失败次数」和
    「抛出异常」放在同一个事务里，异常回滚会把失败计数与尝试记录一起丢掉，
    账号锁定策略将永远无法生效。
    """
    with transaction.atomic():
        LoginAttempt.objects.create(
            username=identifier,
            user=user,
            ip_address=ip or None,
            successful=False,
            failure_reason=reason,
        )
        if user is not None and lock_limit is not None:
            user.register_login_failure(limit=lock_limit, lock_minutes=lock_minutes)
        record_audit(
            action=AuditAction.LOGIN_FAILED,
            instance=user,
            object_repr=str(user) if user is not None else identifier,
            reason=reason,
            actor=None,
        )


def login_user(request: Any, *, username: str, password: str) -> User:
    """登录。包含失败计数、账号锁定、尝试留痕与安全审计。"""
    config = settings.YISHANG
    limit = config["LOGIN_FAILURE_LIMIT"]
    window = config["LOGIN_FAILURE_WINDOW_MINUTES"]
    lock_minutes = config["LOGIN_LOCK_MINUTES"]
    ip = _client_ip(request)
    identifier = (username or "").strip()

    _check_ip_rate_limit(ip, limit, window)

    if not identifier or not password:
        raise ValidationFailed("请输入登录账号与密码。", code="CREDENTIALS_REQUIRED")

    existing = User.objects.filter(username=identifier).first() or User.objects.filter(
        phone=identifier
    ).first()

    if existing is not None and existing.is_locked:
        _record_login_failure(
            identifier=identifier, user=existing, ip=ip, reason="account_locked"
        )
        raise APIError(
            "账号已被锁定，请稍后再试或联系管理员解锁。",
            code="ACCOUNT_LOCKED",
            status_code=423,
            details={"locked_until": existing.locked_until.isoformat() if existing.locked_until else None},
        )

    if existing is not None and not existing.is_active:
        _record_login_failure(
            identifier=identifier, user=existing, ip=ip, reason="account_disabled"
        )
        raise APIError("账号已停用，请联系管理员。", code="ACCOUNT_DISABLED", status_code=403)

    user = authenticate(request, username=identifier, password=password)

    if user is None:
        _record_login_failure(
            identifier=identifier,
            user=existing,
            ip=ip,
            reason="invalid_credentials",
            lock_limit=limit,
            lock_minutes=lock_minutes,
        )
        raise APIError("账号或密码错误。", code="INVALID_CREDENTIALS", status_code=401)

    with transaction.atomic():
        user.register_login_success(ip=ip or None)
        LoginAttempt.objects.create(
            username=user.username, user=user, ip_address=ip or None, successful=True
        )
        record_audit(action=AuditAction.LOGIN, instance=user, object_repr=str(user), actor=user)
    return user

def logout_user(request: Any, user: User) -> None:
    record_audit(action=AuditAction.LOGOUT, instance=user, object_repr=str(user), actor=user)


def _validate_and_set_password(user: User, raw_password: str) -> None:
    try:
        validate_password(raw_password, user)
    except Exception as exc:  # django.core.exceptions.ValidationError
        messages = getattr(exc, "messages", [str(exc)])
        raise ValidationFailed("；".join(messages), code="PASSWORD_POLICY_VIOLATION") from exc
    user.set_password(raw_password)


@transaction.atomic
def change_own_password(user: User, *, old_password: str, new_password: str) -> User:
    """本人修改密码。修改后其它会话立即失效（Django 会话鉴权哈希随密码变化）。"""
    if not user.check_password(old_password):
        raise ValidationFailed("原密码不正确。", code="OLD_PASSWORD_INCORRECT")
    if old_password == new_password:
        raise ValidationFailed("新密码不能与原密码相同。", code="PASSWORD_UNCHANGED")
    _validate_and_set_password(user, new_password)
    user.save(update_fields=["password", "password_changed_at", "must_change_password", "updated_at"])
    record_audit(action=AuditAction.UPDATE, instance=user, object_repr=str(user), reason="本人修改密码")
    return user


@transaction.atomic
def reset_user_password(actor: User, target: User, *, new_password: str, reason: str = "") -> User:
    """管理员重置他人密码。"""
    assert_user_manageable(actor, target)
    _validate_and_set_password(target, new_password)
    target.must_change_password = True
    target.save(
        update_fields=["password", "password_changed_at", "must_change_password", "updated_at"]
    )
    record_audit(
        action=AuditAction.UPDATE,
        instance=target,
        object_repr=str(target),
        reason=reason or "管理员重置密码",
    )
    return target


# --------------------------------------------------------------------------
# 用户管理
# --------------------------------------------------------------------------


def assert_user_manageable(actor: User, target: User) -> None:
    """校验操作者是否有权管理目标用户（数据范围）。"""
    if actor.pk == target.pk:
        return
    if actor.is_superuser:
        return
    assert_in_scope(
        target,
        actor,
        company_field="company_id",
        department_field="department_id",
        owner_field="id",
    )


@transaction.atomic
def create_user(actor: User, *, password: str, role_ids: Iterable[int] = (), **fields: Any) -> User:
    username = (fields.get("username") or "").strip()
    if not username:
        raise ValidationFailed("登录账号不能为空。", code="USERNAME_REQUIRED")
    if User.objects.filter(username=username).exists():
        raise StateConflict(f"登录账号已存在：{username}", code="USERNAME_DUPLICATED")

    company = _resolve_company(fields.get("company_id"))
    department = _resolve_department(fields.get("department_id"))
    if company is not None and not actor.is_superuser:
        assert_in_scope(company, actor, owner_field="id")

    user = User(
        username=username,
        display_name=fields.get("display_name", ""),
        phone=fields.get("phone") or None,
        email=fields.get("email", ""),
        company=company,
        department=department,
        is_staff=bool(fields.get("is_staff", False)),
        must_change_password=bool(fields.get("must_change_password", True)),
        remark=fields.get("remark", ""),
        created_by=actor,
        updated_by=actor,
    )
    _validate_and_set_password(user, password)
    user.must_change_password = bool(fields.get("must_change_password", True))
    user.save()

    if role_ids:
        _sync_user_roles(user, list(role_ids))
    record_audit(action=AuditAction.CREATE, instance=user, object_repr=str(user))
    return user


@transaction.atomic
def update_user(actor: User, target: User, *, expected_version: int | None = None, **fields: Any) -> User:
    assert_user_manageable(actor, target)
    from apps.core.services import assert_version

    assert_version(target, expected_version)
    if fields.get("company_id") is not None:
        _resolve_company(fields["company_id"])
    if fields.get("department_id") is not None:
        _resolve_department(fields["department_id"])

    before = snapshot_fields(target, USER_AUDIT_FIELDS)
    for field in USER_AUDIT_FIELDS:
        if field in {"username", "is_active", "must_change_password"}:
            continue
        if field in fields:
            setattr(target, field, fields[field])
    if "username" in fields:
        new_username = (fields["username"] or "").strip()
        if new_username and new_username != target.username:
            if User.objects.filter(username=new_username).exclude(pk=target.pk).exists():
                raise StateConflict(f"登录账号已存在：{new_username}", code="USERNAME_DUPLICATED")
            target.username = new_username
    target.updated_by = actor
    target.version = (target.version or 0) + 1
    target.save()

    after = snapshot_fields(target, USER_AUDIT_FIELDS)
    changes = build_changes(before, after)
    if changes:
        record_audit(action=AuditAction.UPDATE, instance=target, changes=changes, object_repr=str(target))
    return target


@transaction.atomic
def set_user_active(actor: User, target: User, *, is_active: bool, reason: str = "") -> User:
    assert_user_manageable(actor, target)
    if target.is_superuser and not is_active and not actor.is_superuser:
        raise NotPermitted("只有超级管理员可以停用超级管理员。", code="SUPERUSER_PROTECTED")
    if actor.pk == target.pk and not is_active:
        raise StateConflict("不能停用自己的账号。", code="CANNOT_DISABLE_SELF")

    before = {"is_active": target.is_active}
    target.is_active = is_active
    target.updated_by = actor
    if not is_active:
        # 停用后立即失效：会话中的用户会因 is_active=False 而无法通过鉴权
        target.locked_until = None
        target.failed_login_count = 0
    target.save(update_fields=["is_active", "locked_until", "failed_login_count", "updated_by", "updated_at"])

    record_audit(
        action=AuditAction.ACTIVATE if is_active else AuditAction.DEACTIVATE,
        instance=target,
        changes=build_changes(before, {"is_active": is_active}),
        reason=reason,
        object_repr=str(target),
    )
    return target


@transaction.atomic
def unlock_user(actor: User, target: User) -> User:
    assert_user_manageable(actor, target)
    target.unlock()
    record_audit(action=AuditAction.UPDATE, instance=target, reason="管理员解除账号锁定")
    return target


@transaction.atomic
def assign_user_roles(actor: User, target: User, *, role_ids: Iterable[int]) -> User:
    assert_user_manageable(actor, target)
    before = {"roles": sorted(target.roles.values_list("code", flat=True))}
    _sync_user_roles(target, list(role_ids))
    after = {"roles": sorted(target.roles.values_list("code", flat=True))}
    record_audit(
        action=AuditAction.UPDATE,
        instance=target,
        changes=build_changes(before, after),
        reason="调整用户角色",
        object_repr=str(target),
    )
    return target


def _sync_user_roles(user: User, role_ids: list[int]) -> None:
    roles = list(Role.objects.filter(id__in=role_ids))
    if len(roles) != len(set(role_ids)):
        missing = set(role_ids) - {role.id for role in roles}
        raise ObjectNotFound(f"角色不存在：{sorted(missing)}", code="ROLE_NOT_FOUND")
    for role in roles:
        if not role.is_active:
            raise StateConflict(f"角色已停用，不能分配：{role.code}", code="ROLE_INACTIVE")

    UserRole.objects.filter(user=user).exclude(role_id__in=role_ids).delete()
    existing = set(UserRole.objects.filter(user=user).values_list("role_id", flat=True))
    UserRole.objects.bulk_create(
        [UserRole(user=user, role=role) for role in roles if role.id not in existing],
        ignore_conflicts=True,
    )
    user.bump_permission_version()


# --------------------------------------------------------------------------
# 角色管理
# --------------------------------------------------------------------------


@transaction.atomic
def create_role(actor: User, **fields: Any) -> Role:
    code = (fields.get("code") or "").strip()
    if not code:
        raise ValidationFailed("角色编码不能为空。", code="ROLE_CODE_REQUIRED")
    if Role.objects.filter(code=code).exists():
        raise StateConflict(f"角色编码已存在：{code}", code="ROLE_CODE_DUPLICATED")
    company = _resolve_company(fields.get("company_id"))
    if company is not None and not actor.is_superuser:
        assert_in_scope(company, actor, owner_field="id")
    role = Role.objects.create(
        code=code,
        name=fields.get("name", code),
        company=company,
        data_scope_type=fields.get("data_scope_type", Role._meta.get_field("data_scope_type").default),
        remark=fields.get("remark", ""),
        sort_order=fields.get("sort_order", 0),
    )
    record_audit(action=AuditAction.CREATE, instance=role, object_repr=str(role))
    return role


@transaction.atomic
def update_role(actor: User, role: Role, **fields: Any) -> Role:
    if role.is_system and "code" in fields and fields["code"] != role.code:
        raise NotPermitted("系统内置角色的编码不可修改。", code="SYSTEM_ROLE_PROTECTED")
    if fields.get("company_id") is not None:
        _resolve_company(fields["company_id"])
    before = snapshot_fields(role, ROLE_AUDIT_FIELDS)
    for field in ROLE_AUDIT_FIELDS:
        if field in fields and field != "code":
            setattr(role, field, fields[field])
    if "code" in fields and fields["code"]:
        new_code = fields["code"].strip()
        if new_code != role.code:
            if Role.objects.filter(code=new_code).exclude(pk=role.pk).exists():
                raise StateConflict(f"角色编码已存在：{new_code}", code="ROLE_CODE_DUPLICATED")
            role.code = new_code
    role.save()
    after = snapshot_fields(role, ROLE_AUDIT_FIELDS)
    changes = build_changes(before, after)
    if changes:
        record_audit(action=AuditAction.UPDATE, instance=role, changes=changes, object_repr=str(role))
    return role


@transaction.atomic
def delete_role(actor: User, role: Role, *, reason: str = "") -> None:
    if role.is_system:
        raise NotPermitted("系统内置角色不可删除。", code="SYSTEM_ROLE_PROTECTED")
    if UserRole.objects.filter(role=role).exists():
        raise StateConflict(
            "该角色已分配给用户，请先解除分配或改为停用。",
            code="ROLE_IN_USE",
        )
    # 已确认没有用户在用该角色，删除后无需刷新权限缓存
    record_audit(action=AuditAction.DELETE, instance=role, reason=reason, object_repr=str(role))
    role.delete()


@transaction.atomic
def set_role_permissions(actor: User, role: Role, *, permission_codes: Iterable[str]) -> Role:
    codes = list(dict.fromkeys(permission_codes))
    permissions = list(Permission.objects.filter(code__in=codes))
    missing = set(codes) - {permission.code for permission in permissions}
    if missing:
        raise ObjectNotFound(f"权限编码不存在：{sorted(missing)}", code="PERMISSION_NOT_FOUND")

    before = {"permissions": sorted(role.permissions.values_list("code", flat=True))}
    role.permissions.set(permissions)
    after = {"permissions": sorted(role.permissions.values_list("code", flat=True))}
    affected = list(UserRole.objects.filter(role=role).values_list("user_id", flat=True))
    _bump_users_permission_version(affected)
    record_audit(
        action=AuditAction.UPDATE,
        instance=role,
        changes=build_changes(before, after),
        reason="调整角色操作权限",
    )
    return role


@transaction.atomic
def set_role_menus(actor: User, role: Role, *, menu_codes: Iterable[str]) -> Role:
    codes = list(dict.fromkeys(menu_codes))
    menus = list(Menu.objects.filter(code__in=codes))
    missing = set(codes) - {menu.code for menu in menus}
    if missing:
        raise ObjectNotFound(f"菜单编码不存在：{sorted(missing)}", code="MENU_NOT_FOUND")
    before = {"menus": sorted(role.menus.values_list("code", flat=True))}
    role.menus.set(menus)
    after = {"menus": sorted(role.menus.values_list("code", flat=True))}
    affected = list(UserRole.objects.filter(role=role).values_list("user_id", flat=True))
    _bump_users_permission_version(affected)
    record_audit(
        action=AuditAction.UPDATE,
        instance=role,
        changes=build_changes(before, after),
        reason="调整角色菜单权限",
    )
    return role


@transaction.atomic
def set_role_scope(
    actor: User,
    role: Role,
    *,
    data_scope_type: str,
    company_ids: Iterable[int] = (),
    factory_ids: Iterable[int] = (),
    department_ids: Iterable[int] = (),
    warehouse_ids: Iterable[int] = (),
) -> Role:
    """设置角色的数据范围。自定义范围需要显式给出各维度对象。"""
    from apps.identity.models import DataScopeType

    if data_scope_type not in DataScopeType.values:
        raise ValidationFailed(f"未知的数据范围类型：{data_scope_type}", code="INVALID_DATA_SCOPE")

    _validate_scope_targets(
        actor,
        company_ids=company_ids,
        factory_ids=factory_ids,
        department_ids=department_ids,
        warehouse_ids=warehouse_ids,
    )

    before = {
        "data_scope_type": role.data_scope_type,
        "grants": sorted(
            f"{grant.dimension}:{grant.object_id}" for grant in role.scope_grants.all()
        ),
    }
    role.data_scope_type = data_scope_type
    role.save(update_fields=["data_scope_type", "updated_at"])

    role.scope_grants.all().delete()
    grants = []
    for dimension, ids in (
        (ScopeDimension.COMPANY, company_ids),
        (ScopeDimension.FACTORY, factory_ids),
        (ScopeDimension.DEPARTMENT, department_ids),
        (ScopeDimension.WAREHOUSE, warehouse_ids),
    ):
        grants.extend(
            RoleScopeGrant(role=role, dimension=dimension, object_id=int(obj_id))
            for obj_id in dict.fromkeys(ids)
        )
    if grants:
        RoleScopeGrant.objects.bulk_create(grants, ignore_conflicts=True)

    after = {
        "data_scope_type": role.data_scope_type,
        "grants": sorted(
            f"{grant.dimension}:{grant.object_id}" for grant in role.scope_grants.all()
        ),
    }
    affected = list(UserRole.objects.filter(role=role).values_list("user_id", flat=True))
    _bump_users_permission_version(affected)
    record_audit(
        action=AuditAction.UPDATE,
        instance=role,
        changes=build_changes(before, after),
        reason="调整角色数据范围",
    )
    return role


def _validate_scope_targets(actor: User, **dimensions: Iterable[int]) -> None:
    """授权对象必须真实存在，且不能超出操作者自身范围。"""
    from apps.factory.models import Company, Department, Factory
    from apps.wms.models import Warehouse

    model_map = {
        "company_ids": Company,
        "factory_ids": Factory,
        "department_ids": Department,
        "warehouse_ids": Warehouse,
    }
    for key, ids in dimensions.items():
        id_list = [int(obj_id) for obj_id in ids]
        if not id_list:
            continue
        model = model_map[key]
        found = set(model.objects.filter(id__in=id_list).values_list("id", flat=True))
        missing = set(id_list) - found
        if missing:
            raise ObjectNotFound(
                f"{model._meta.verbose_name}不存在：{sorted(missing)}",
                code="SCOPE_TARGET_NOT_FOUND",
            )
        if not actor.is_superuser:
            for obj_id in id_list:
                assert_in_scope(model.objects.get(pk=obj_id), actor, owner_field="id")


def _bump_users_permission_version(user_ids: Iterable[int]) -> None:
    """角色/授权变更后自增相关用户的权限版本，使权限缓存立即失效。"""
    from django.db.models import F

    unique_ids = list(dict.fromkeys(user_ids))
    if not unique_ids:
        return
    User.objects.filter(id__in=unique_ids).update(permission_version=F("permission_version") + 1)


# --------------------------------------------------------------------------
# 通知
# --------------------------------------------------------------------------


def _resolve_company(company_id: int | None):
    if not company_id:
        return None
    from apps.factory.models import Company

    return require_object(Company, int(company_id), code="COMPANY_NOT_FOUND")


def _resolve_department(department_id: int | None):
    if not department_id:
        return None
    from apps.factory.models import Department

    return require_object(Department, int(department_id), code="DEPARTMENT_NOT_FOUND")


def unread_notification_count(user: User) -> int:
    from apps.core.models import Notification

    return Notification.objects.filter(recipient=user, is_read=False).count()


def mark_notification_read(user: User, notification_id: int) -> None:
    from apps.core.models import Notification

    updated = Notification.objects.filter(id=notification_id, recipient=user, is_read=False).update(
        is_read=True, read_at=timezone.now()
    )
    if not updated and not Notification.objects.filter(id=notification_id, recipient=user).exists():
        raise ObjectNotFound("通知不存在。", code="NOTIFICATION_NOT_FOUND")


def scoped_users(user: User):
    """按数据范围过滤用户查询集，供列表接口与选择器使用。"""
    return scoped_queryset(
        User.objects.select_related("company", "department"),
        user,
        company_field="company_id",
        department_field="department_id",
        owner_field="id",
    )


__all__ = [
    "assign_user_roles",
    "change_own_password",
    "create_role",
    "create_user",
    "delete_role",
    "login_user",
    "logout_user",
    "mark_notification_read",
    "reset_user_password",
    "scoped_users",
    "set_role_menus",
    "set_role_permissions",
    "set_role_scope",
    "set_user_active",
    "unlock_user",
    "unread_notification_count",
    "update_role",
    "update_user",
]
