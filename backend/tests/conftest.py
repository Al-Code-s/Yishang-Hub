"""pytest 公共夹具。

关键设计：
* 权限点来自 ``apps/identity/permissions_registry``，测试不手写权限字符串之外的东西，
  保证测试与生产使用同一份契约；
* 非超级管理员的能力一律通过“角色 + 数据范围”构造，避免测试绕过真实鉴权路径；
* 所有用例运行在 MySQL 上（config.settings.test 强制 mysql 后端）。
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework.test import APIClient

from apps.identity.models import DataScopeType, Menu, Permission, Role, RoleScopeGrant, ScopeDimension
from apps.identity.permissions_registry import MENUS, PERMISSIONS

User = get_user_model()


@pytest.fixture
def api_client() -> APIClient:
    return APIClient()


@pytest.fixture
def registry_permissions(db) -> dict[str, Permission]:
    """把权限注册表写入数据库，供非超级管理员授权使用。"""
    result: dict[str, Permission] = {}
    for definition in PERMISSIONS:
        permission, _ = Permission.objects.update_or_create(
            code=definition.code,
            defaults={
                "name": definition.name,
                "module": definition.module,
                "resource": definition.resource,
                "action": definition.action,
                "permission_type": definition.permission_type,
                "is_system": True,
            },
        )
        result[definition.code] = permission
    return result


@pytest.fixture
def registry_menus(db) -> dict[str, Menu]:
    result: dict[str, Menu] = {}
    ordered = sorted(MENUS, key=lambda item: 0 if item.parent is None else 1)
    for definition in ordered:
        parent = result.get(definition.parent) if definition.parent else None
        menu, _ = Menu.objects.update_or_create(
            code=definition.code,
            defaults={
                "name": definition.name,
                "parent": parent,
                "path": definition.path,
                "component": definition.component,
                "icon": definition.icon,
                "menu_type": definition.menu_type,
                "permission_code": definition.permission_code,
                "sort_order": definition.sort_order,
                "is_active": True,
                "visible": True,
            },
        )
        result[definition.code] = menu
    return result


@pytest.fixture
def company(db):
    from apps.factory.models import Company

    return Company.objects.create(code="TST", name="测试服饰有限公司", short_name="测试")


@pytest.fixture
def other_company(db):
    from apps.factory.models import Company

    return Company.objects.create(code="OTH", name="对照服饰有限公司", short_name="对照")


@pytest.fixture
def department_factory(company):
    """公司下的部门与工厂，供数据范围用例使用。"""
    from apps.factory.models import Department, Factory

    departments = {}
    for code, name in (("PROD", "生产部"), ("WH", "仓储部"), ("QC", "质量部")):
        departments[code] = Department.objects.create(company=company, code=code, name=name)
    factories = {}
    for code, name in (("F01", "一号工厂"), ("F02", "二号工厂")):
        factories[code] = Factory.objects.create(company=company, code=code, name=name)
    return {"departments": departments, "factories": factories}


def make_role(
    *,
    code: str,
    permission_codes: Iterable[str],
    data_scope_type: str = DataScopeType.COMPANY,
    company: Any = None,
    grants: Iterable[tuple[str, int]] = (),
    menus: Iterable[str] = (),
) -> Role:
    role = Role.objects.create(
        code=code,
        name=code,
        company=company,
        data_scope_type=data_scope_type,
        is_active=True,
    )
    role.permissions.set(Permission.objects.filter(code__in=list(permission_codes)))
    for code_name, object_id in grants:
        RoleScopeGrant.objects.create(role=role, dimension=code_name, object_id=object_id)
    if menus:
        role.menus.set(Menu.objects.filter(code__in=list(menus)))
    return role


def make_user(
    *,
    username: str,
    role: Role | None = None,
    company: Any = None,
    department: Any = None,
    password: str = "Tst!Passw0rd2026",
    is_superuser: bool = False,
    **extra: Any,
) -> User:
    user = User(
        username=username,
        display_name=username,
        company=company,
        department=department,
        is_superuser=is_superuser,
        is_staff=is_superuser,
        **extra,
    )
    user.set_password(password)
    # 自定义 set_password 会把 must_change_password 重置为 False，按传入值回填
    if "must_change_password" in extra:
        user.must_change_password = bool(extra["must_change_password"])
    user.save()
    if role is not None:
        from apps.identity.models import UserRole

        UserRole.objects.create(user=user, role=role)
        user.bump_permission_version()
    return user


def login(client: APIClient, user: User, password: str = "Tst!Passw0rd2026") -> None:
    response = client.post(
        "/api/v1/identity/auth/login/",
        {"username": user.username, "password": password},
        format="json",
    )
    assert response.status_code == 200, response.content


@pytest.fixture
def role_factory(db):
    return make_role


@pytest.fixture
def user_factory(db):
    return make_user


@pytest.fixture
def login_as(db):
    return login


@pytest.fixture
def scoped_user(db, registry_permissions, company, department_factory):
    """拥有主数据读写权限、数据范围为指定工厂的用户。"""
    factory = department_factory["factories"]["F01"]
    role = make_role(
        code="test_masterdata_factory",
        permission_codes=[
            "masterdata.material.view",
            "masterdata.material.create",
            "masterdata.material.update",
            "masterdata.warehouse.view",
            "masterdata.style.view",
            "analytics.dashboard.view",
        ],
        data_scope_type=DataScopeType.FACTORY,
        company=company,
        grants=[(ScopeDimension.FACTORY, factory.pk)],
    )
    return make_user(username="scope_f01", role=role, company=company), factory


@pytest.fixture(autouse=True)
def reset_login_rate_limit() -> None:
    """清空登录限流计数器。

    限流按来源 IP 统计并写入缓存，若不隔离会让「用例执行顺序」决定成败。
    这里只清理限流键，不动权限缓存等其他键。
    """

    def _purge() -> None:
        store = getattr(cache, "_cache", None)
        if not hasattr(store, "keys"):
            # 非本地内存缓存：无法枚举键，退化为删除已知键
            cache.delete("identity:login_rate:127.0.0.1")
            return
        expire_info = getattr(cache, "_expire_info", None)
        # 注意：store 中是「已加前缀」的键，直接调用 cache.delete 会再加一次前缀
        for item in [key for key in list(store.keys()) if "identity:login_rate" in str(key)]:
            store.pop(item, None)
            if hasattr(expire_info, "pop"):
                expire_info.pop(item, None)

    _purge()
    yield
    _purge()
