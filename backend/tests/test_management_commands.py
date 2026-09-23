"""初始化与演示数据命令用例。

对应任务书 15「命令具备重复执行保护 / seed_demo 禁止在生产环境误执行 /
不在代码中硬编码公开管理员密码」。全部真实执行命令，不使用 mock。
"""

from __future__ import annotations

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.core.models import CodeRule, Dictionary
from apps.identity.models import Menu, Permission, Role, User, UserRole
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
    """``seed_demo`` 是 ``seed_demo_xjys`` 的兼容入口：只写一家公司，且幂等。"""
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
    # 平台只保留一家公司（新疆意尚智造科技有限公司）
    assert counts["companies"] == 1
    assert Company.objects.get().code == "XJYS"
    assert counts["skus"] >= 30
    # 演示数据与真实数据必须可区分
    assert Material.objects.filter(remark__contains="演示数据").exists()

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


def test_bootstrap_system_binds_super_admin_role_to_admin_account():
    """管理员账号必须挂上内置的「超级管理员」角色。

    账号的权限来自 ``is_superuser``（后端 ``permission_codes()`` 直接返回 ``{"*"}``），
    但角色绑定让「角色 → 权限」矩阵与账号实际能力一致：
    个人中心与用户管理里能看到真实角色，而不是「未分配」。

    用户反馈过「超级管理员好像什么也新增不了」——那是前端把 ``["*"]`` 当成普通编码
    比较导致按钮被隐藏（已在 ``frontend/tests/auth-store.spec.ts`` 加回归用例），
    与本用例一起保证「账号 → 角色 → 权限」三段都可核对。
    """
    call_command("bootstrap_system", "--admin-password", "Boot!Str0ng2026", verbosity=0)

    admin = User.objects.get(username="admin")
    role = Role.objects.get(code="super_admin")

    assert admin.roles.filter(code="super_admin").exists()
    assert role.data_scope_type == "all"
    assert role.permissions.count() == len(PERMISSIONS)
    assert admin.has_permission_codes(["wms.warehouse.create", "identity.role.create"]) is True

    # 幂等：重复执行只补齐，不产生重复绑定
    call_command("bootstrap_system", "--admin-password", "Boot!Str0ng2026", verbosity=0)
    assert UserRole.objects.filter(user=admin, role=role).count() == 1

# ---------------------------------------------------------------------------
# 新疆意尚智造演示数据（seed_demo_xjys）
# ---------------------------------------------------------------------------


def test_seed_demo_xjys_refuses_production(settings):
    settings.DJANGO_ENV = "production"
    with pytest.raises(CommandError, match="禁止在生产环境执行"):
        call_command("seed_demo_xjys", verbosity=0)


def test_seed_demo_xjys_requires_confirmation_outside_dev(settings):
    settings.DJANGO_ENV = "staging"
    with pytest.raises(CommandError, match="--yes"):
        call_command("seed_demo_xjys", verbosity=0)


def test_seed_demo_xjys_fills_every_module_and_is_idempotent(settings):
    """新疆公司的演示数据必须覆盖各业务模块，且重复执行不新增记录。"""
    from datetime import date

    from apps.crm.models import CustomerComplaint, ProductReview
    from apps.ehs.models import HazardRecord, SafetyTraining, WorkPermit
    from apps.ems.models import EnergyMeter, MeterReading
    from apps.equipment.models import Equipment, InspectionRecord, MaintenanceTask
    from apps.factory.models import Company
    from apps.iot.models import IoTReading
    from apps.logistics.models import AutomationDevice, LogisticsTask
    from apps.mes.models import ProductionOrder
    from apps.qms.models import QualityInspectionOrder
    from apps.sales.models import SalesOrder
    from apps.srm.models import SupplierEvaluation
    from apps.wms.models import InventoryBalance, InventoryDocument

    settings.DJANGO_ENV = "test"
    settings.YISHANG = {**settings.YISHANG, "DEMO_PASSWORD": "Demo!Passw0rd2026"}
    call_command("bootstrap_system", "--skip-admin", verbosity=0)
    call_command("seed_demo_xjys", verbosity=0)

    company = Company.objects.get(code="XJYS")
    models = (
        Equipment,
        MaintenanceTask,
        InspectionRecord,
        EnergyMeter,
        MeterReading,
        IoTReading,
        InventoryDocument,
        InventoryBalance,
        SalesOrder,
        ProductionOrder,
        QualityInspectionOrder,
        SupplierEvaluation,
        CustomerComplaint,
        ProductReview,
        SafetyTraining,
        HazardRecord,
        WorkPermit,
        AutomationDevice,
        LogisticsTask,
    )
    counts = {model._meta.label: model.objects.filter(company=company).count() for model in models}
    for label, number in counts.items():
        assert number > 0, f"{label} 没有演示数据"

    # 演示数据必须可区分，且业务日期不早于 2026-01-01
    assert Equipment.objects.filter(company=company, remark__contains="演示数据").exists()
    assert not MaintenanceTask.objects.filter(
        company=company, plan_date__lt=date(2026, 1, 1)
    ).exists()

    call_command("seed_demo_xjys", verbosity=0)
    assert counts == {
        model._meta.label: model.objects.filter(company=company).count() for model in models
    }
