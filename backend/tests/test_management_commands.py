"""初始化与演示数据命令用例。

对应任务书 15「命令具备重复执行保护 / seed_demo 禁止在生产环境误执行 /
不在代码中硬编码公开管理员密码」。全部真实执行命令，不使用 mock。
"""

from __future__ import annotations

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.core.models import CodeRule, Dictionary
from apps.identity.models import Menu, Permission, Role, User
from apps.identity.permissions_registry import MENUS, PERMISSIONS

pytestmark = pytest.mark.django_db


def test_bootstrap_system_is_idempotent():
    call_command("bootstrap_system", "--admin-password", "Boot!Str0ng2026", verbosity=0)

    assert Permission.objects.count() == len(PERMISSIONS)
    assert Menu.objects.count() == len(MENUS)
    assert User.objects.get(username="admin").check_password("Boot!Str0ng2026") is True
    role_codes = set(Role.objects.values_list("code", flat=True))
    assert {"super_admin", "platform_admin", "masterdata_admin"} <= role_codes

    permission_count = Permission.objects.count()
    role_count = Role.objects.count()
    code_rule_count = CodeRule.objects.count()
    dictionary_count = Dictionary.objects.count()

    # 再跑一次：只补齐与更新，不产生重复数据
    call_command("bootstrap_system", "--skip-admin", verbosity=0)
    assert Permission.objects.count() == permission_count
    assert Role.objects.count() == role_count
    assert CodeRule.objects.count() == code_rule_count
    assert Dictionary.objects.count() == dictionary_count


def test_bootstrap_system_does_not_overwrite_password_without_flag():
    call_command("bootstrap_system", "--admin-password", "First!Passw0rd", verbosity=0)
    call_command("bootstrap_system", verbosity=0)

    admin = User.objects.get(username="admin")
    assert admin.check_password("First!Passw0rd") is True


def test_bootstrap_system_requires_password_in_production(settings):
    settings.DJANGO_ENV = "production"
    settings.YISHANG = {**settings.YISHANG, "BOOTSTRAP_ADMIN_PASSWORD": ""}
    with pytest.raises(CommandError):
        call_command("bootstrap_system", verbosity=0)


def test_bootstrap_system_registers_every_permission_used_by_menus():
    """菜单声明了权限编码就必须存在对应权限点，避免菜单永远不可见。"""
    call_command("bootstrap_system", "--skip-admin", verbosity=0)
    missing = {
        item.permission_code
        for item in MENUS
        if item.permission_code and not Permission.objects.filter(code=item.permission_code).exists()
    }
    assert missing == set()


def test_seed_demo_refuses_production(settings):
    settings.DJANGO_ENV = "production"
    with pytest.raises(CommandError, match="禁止在生产环境执行"):
        call_command("seed_demo", verbosity=0)


def test_seed_demo_requires_confirmation_outside_dev(settings):
    settings.DJANGO_ENV = "staging"
    with pytest.raises(CommandError, match="--yes"):
        call_command("seed_demo", verbosity=0)


def test_seed_demo_is_idempotent(settings):
    from apps.factory.models import Company
    from apps.masterdata.models import Material, Sku, Style
    from apps.wms.models import Location, Warehouse

    settings.DJANGO_ENV = "test"
    settings.YISHANG = {**settings.YISHANG, "DEMO_PASSWORD": "Demo!Passw0rd2026"}
    call_command("bootstrap_system", "--skip-admin", verbosity=0)
    call_command("seed_demo", verbosity=0)

    counts = {
        "companies": Company.objects.count(),
        "warehouses": Warehouse.objects.count(),
        "locations": Location.objects.count(),
        "materials": Material.objects.count(),
        "styles": Style.objects.count(),
        "skus": Sku.objects.count(),
    }
    assert counts["companies"] >= 1
    assert counts["skus"] >= 30
    # 演示数据与真实数据必须可区分
    assert Material.objects.filter(remark="演示数据").exists()

    call_command("seed_demo", verbosity=0)
    assert counts == {
        "companies": Company.objects.count(),
        "warehouses": Warehouse.objects.count(),
        "locations": Location.objects.count(),
        "materials": Material.objects.count(),
        "styles": Style.objects.count(),
        "skus": Sku.objects.count(),
    }


def test_seed_demo_does_not_reset_existing_demo_passwords(settings):
    settings.DJANGO_ENV = "test"
    settings.YISHANG = {**settings.YISHANG, "DEMO_PASSWORD": "Demo!Passw0rd2026"}
    call_command("bootstrap_system", "--skip-admin", verbosity=0)
    call_command("seed_demo", verbosity=0)

    user = User.objects.filter(is_superuser=False, username__isnull=False).exclude(username="admin").first()
    if user is None:
        pytest.skip("演示账号未创建，跳过口令保持用例")
    user.set_password("Changed!Passw0rd9")
    user.save()

    call_command("seed_demo", verbosity=0)
    user.refresh_from_db()
    assert user.check_password("Changed!Passw0rd9") is True
