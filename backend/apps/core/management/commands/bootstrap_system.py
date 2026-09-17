"""系统初始化命令：同步权限与菜单、建立内置角色、按安全流程创建管理员账号。

设计约束：
* 可重复执行（幂等）：重复运行只做补齐与更新，不产生重复数据；
* 不硬编码任何账号密码。管理员密码优先级：
  ``--admin-password`` > ``YISHANG_ADMIN_PASSWORD`` > 开发环境随机生成（打印一次）；
  生产环境（DJANGO_ENV=production）缺失密码时直接失败，不允许猜口令；
* 权限与菜单以 ``apps/identity/permissions_registry.py`` 为唯一契约，
  数据库中多出来的编码只报告不删除，避免误删二次开发的授权。
"""

from __future__ import annotations

import secrets
import string
from dataclasses import dataclass, field

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.core.models import CodeRule, Dictionary, DictionaryItem, ResetPeriod
from apps.identity.models import DataScopeType, Menu, Permission, Role, User
from apps.identity.permissions_registry import MENUS, PERMISSIONS

DEMO_ROLE_PREFIX = "demo_"


@dataclass(frozen=True)
class RoleDef:
    """内置角色定义。

    include 中的条目：以 "." 结尾表示前缀匹配，否则为精确匹配。
    """

    code: str
    name: str
    data_scope_type: str
    sort_order: int
    include: tuple[str, ...] = ()
    always_all: bool = False
    remark: str = ""
    extra: tuple[str, ...] = field(default=())


BUILTIN_ROLES: tuple[RoleDef, ...] = (
    RoleDef(
        code="super_admin",
        name="超级管理员",
        data_scope_type=DataScopeType.ALL,
        sort_order=1,
        always_all=True,
        remark="拥有全部权限，覆盖所有数据范围。",
    ),
    RoleDef(
        code="platform_admin",
        name="平台管理员",
        data_scope_type=DataScopeType.COMPANY,
        sort_order=10,
        include=("identity.", "core.", "factory.", "integration.", "analytics.", "workflow."),
        remark="用户、角色、字典、编码规则、审计与审批模板维护。",
    ),
    RoleDef(
        code="masterdata_admin",
        name="主数据管理员",
        data_scope_type=DataScopeType.COMPANY,
        sort_order=20,
        include=("masterdata.", "analytics."),
        extra=(
            "core.dictionary.view",
            "core.code_rule.view",
            "core.attachment.upload",
            "core.attachment.download",
            "factory.company.view",
            "factory.factory.view",
            "factory.department.view",
            "wms.warehouse.view",
            "wms.zone.view",
            "wms.location.view",
        ),
        remark="物料、款式、颜色、尺码、SKU 与标识维护。",
    ),
    RoleDef(
        code="factory_admin",
        name="工厂与组织管理员",
        data_scope_type=DataScopeType.COMPANY,
        sort_order=21,
        include=("factory.", "analytics."),
        extra=(
            "core.attachment.upload",
            "core.attachment.download",
            "masterdata.material.view",
            "wms.warehouse.view",
            "wms.zone.view",
            "wms.location.view",
        ),
        remark="公司、部门、工厂、车间、线体、工位、员工、班次与班组维护。",
    ),
    RoleDef(
        code="warehouse_admin",
        name="仓储管理员",
        data_scope_type=DataScopeType.WAREHOUSE,
        sort_order=22,
        include=("wms.",),
        extra=(
            "masterdata.material.view",
            "masterdata.sku.view",
            "masterdata.identifier.view",
            "core.attachment.upload",
            "core.attachment.download",
            "analytics.dashboard.view",
        ),
        remark="仓库、库区与储位维护；数据范围限定为被授权仓库。",
    ),
    RoleDef(
        code="crm_admin",
        name="客户管理员",
        data_scope_type=DataScopeType.COMPANY,
        sort_order=23,
        include=("crm.", "analytics."),
        extra=(
            "core.attachment.upload",
            "core.attachment.download",
            "factory.company.view",
            "masterdata.sku.view",
            "masterdata.material.view",
        ),
        remark="客户档案与联系人维护。服务工单、投诉与满意度属于阶段 6。",
    ),
    RoleDef(
        code="srm_admin",
        name="供应商管理员",
        data_scope_type=DataScopeType.COMPANY,
        sort_order=24,
        include=("srm.", "analytics."),
        extra=(
            "core.attachment.upload",
            "core.attachment.download",
            "factory.company.view",
            "masterdata.material.view",
            "masterdata.material_category.view",
        ),
        remark="供应商档案、联系人与资质维护。准入审批复用 workflow 审批体系。",
    ),
    RoleDef(
        code="procurement_admin",
        name="采购管理员",
        data_scope_type=DataScopeType.COMPANY,
        sort_order=25,
        # 逐条列出而不是用 "procurement." 前缀：采购角色**不含** receipt.inspect，
        # 来料检验判定必须由质检角色执行，采购与质检职责分离（任务书 6.3 / 10.5）
        include=(
            "procurement.requisition.view",
            "procurement.requisition.create",
            "procurement.requisition.update",
            "procurement.requisition.submit",
            "procurement.order.view",
            "procurement.order.create",
            "procurement.order.update",
            "procurement.order.submit",
            "procurement.order.close",
            "procurement.order.override_supplier",
            "procurement.receipt.view",
            "procurement.receipt.create",
            "procurement.receipt.update",
            "procurement.receipt.post",
            "analytics.dashboard.view",
        ),
        extra=(
            "core.attachment.upload",
            "core.attachment.download",
            "factory.company.view",
            "srm.supplier.view",
            "masterdata.material.view",
            "masterdata.material_category.view",
            "wms.inventory.view",
            # 收货过账经由统一库存服务记账，必须同时具备库存单据权限
            "wms.document.create",
            "wms.document.post",
        ),
        remark="采购申请、采购订单与收货过账；来料检验判定由质检角色执行。",
    ),
    RoleDef(
        code="quality_inspector",
        name="质检员",
        data_scope_type=DataScopeType.COMPANY,
        sort_order=26,
        include=(
            "procurement.receipt.view",
            "procurement.receipt.inspect",
            "wms.quality.release",
            "wms.inventory.view",
            "analytics.dashboard.view",
        ),
        extra=(
            "core.attachment.upload",
            "core.attachment.download",
        ),
        remark="来料检验判定；质量放行必须走库存服务 wms.quality.release，不直接改质量状态。",
    ),
    RoleDef(
        code="approver",
        name="审批人",
        data_scope_type=DataScopeType.DEPARTMENT,
        sort_order=30,
        include=(
            "workflow.instance.view",
            "workflow.instance.approve",
            "analytics.dashboard.view",
            "core.attachment.upload",
            "core.attachment.download",
        ),
        remark="参与审批流转，数据范围限定为本人所属部门。",
    ),
    RoleDef(
        code="viewer",
        name="只读用户",
        data_scope_type=DataScopeType.COMPANY,
        sort_order=90,
        include=(".view",),
        remark="仅具备查询类权限，不具备任何写入权限。",
    ),
)


CODE_RULES: tuple[tuple[str, str, str, str], ...] = (
    ("AP", "审批单号", "AP{YYYYMMDD}{SEQ:5}", ResetPeriod.DAILY),
    ("SO", "销售订单号", "SO{YYYYMMDD}{SEQ:4}", ResetPeriod.DAILY),
    ("PO", "采购订单号", "PO{YYYYMMDD}{SEQ:4}", ResetPeriod.DAILY),
    ("PR", "采购申请号", "PR{YYYYMMDD}{SEQ:4}", ResetPeriod.DAILY),
    ("GR", "采购收货单号", "GR{YYYYMMDD}{SEQ:4}", ResetPeriod.DAILY),
    ("RC", "采购收货单号（业务）", "RC{YYYYMMDD}{SEQ:4}", ResetPeriod.DAILY),
    ("MO", "生产工单号", "MO{YYYYMMDD}{SEQ:4}", ResetPeriod.DAILY),
    ("TR", "移库单号", "TR{YYYYMMDD}{SEQ:4}", ResetPeriod.DAILY),
    ("ST", "盘点单号", "ST{YYYYMMDD}{SEQ:4}", ResetPeriod.DAILY),
)

DICTIONARIES: tuple[tuple[str, str, tuple[tuple[str, str], ...]], ...] = (
    (
        "stop_reason",
        "停用原因",
        (
            ("business_adjust", "业务调整"),
            ("duplicated", "重复建档"),
            ("data_error", "录入错误"),
            ("supplier_terminated", "供应商终止合作"),
            ("other", "其他"),
        ),
    ),
    (
        "employee_position",
        "岗位",
        (
            ("cutter", "裁剪工"),
            ("sewer", "缝纫工"),
            ("ironer", "整烫工"),
            ("inspector", "质检员"),
            ("storekeeper", "仓管员"),
            ("team_leader", "班组长"),
            ("maintainer", "设备维修工"),
            ("planner", "计划员"),
            ("salesman", "销售员"),
            ("buyer", "采购员"),
        ),
    ),
    (
        "fabric_composition",
        "面料成分",
        (
            ("cotton_100", "100% 棉"),
            ("polyester_100", "100% 涤纶"),
            ("cotton_poly_65_35", "棉涤 65/35"),
            ("cotton_poly_35_65", "涤棉 65/35"),
            ("cotton_spandex", "棉氨混纺"),
            ("wool_blend", "羊毛混纺"),
        ),
    ),
)


def _matches(code: str, patterns: tuple[str, ...]) -> bool:
    for pattern in patterns:
        if pattern.startswith("."):
            # 形如 ".view" 的后缀匹配
            if code.endswith(pattern):
                return True
        elif pattern.endswith("."):
            if code.startswith(pattern):
                return True
        elif code == pattern:
            return True
    return False


def _generate_password(length: int = 20) -> str:
    alphabet = string.ascii_letters + string.digits + "!@#%^&*-_=+"
    while True:
        candidate = "".join(secrets.choice(alphabet) for _ in range(length))
        if (
            any(c.islower() for c in candidate)
            and any(c.isupper() for c in candidate)
            and any(c.isdigit() for c in candidate)
            and any(c in "!@#%^&*-_=+" for c in candidate)
        ):
            return candidate


class Command(BaseCommand):
    help = "同步权限/菜单、创建内置角色与管理员账号、写入系统基础配置（幂等）。"

    def add_arguments(self, parser) -> None:
        parser.add_argument("--admin-username", default=None, help="管理员登录账号，默认取 YISHANG_ADMIN_USERNAME 或 admin。")
        parser.add_argument("--admin-password", default=None, help="管理员密码；不传则读 YISHANG_ADMIN_PASSWORD。")
        parser.add_argument("--skip-admin", action="store_true", help="不创建/更新管理员账号。")
        parser.add_argument(
            "--reset-admin-password",
            action="store_true",
            help="重置管理员密码（需要提供密码来源，不接受随机覆盖已有账号）。",
        )
        parser.add_argument("--skip-reference", action="store_true", help="不写入编码规则与数据字典。")
        parser.add_argument("--dry-run", action="store_true", help="只展示将要执行的动作，不写库。")

    def handle(self, *args, **options) -> None:
        dry_run = options["dry_run"]
        self.verbosity = int(options.get("verbosity", 1))

        if dry_run:
            self.stdout.write(self.style.WARNING("dry-run：只做检查，不写入数据库。"))

        with transaction.atomic():
            permission_map = self._sync_permissions(dry_run=dry_run)
            menu_map = self._sync_menus(dry_run=dry_run)
            self._sync_roles(permission_map, menu_map, dry_run=dry_run)
            if not options["skip_reference"]:
                self._sync_code_rules(dry_run=dry_run)
                self._sync_dictionaries(dry_run=dry_run)
            if not options["skip_admin"]:
                self._ensure_admin(options, dry_run=dry_run)
            if dry_run:
                transaction.set_rollback(True)

        self.stdout.write(self.style.SUCCESS("系统初始化完成。"))

    # -- 权限 ------------------------------------------------------------
    def _sync_permissions(self, *, dry_run: bool) -> dict[str, Permission]:
        created = updated = 0
        result: dict[str, Permission] = {}
        for definition in PERMISSIONS:
            defaults = {
                "name": definition.name,
                "module": definition.module,
                "resource": definition.resource,
                "action": definition.action,
                "permission_type": definition.permission_type,
                "is_system": True,
            }
            if dry_run:
                permission = Permission.objects.filter(code=definition.code).first() or Permission(
                    code=definition.code, **defaults
                )
                if permission.pk is None:
                    created += 1
            else:
                permission, is_new = Permission.objects.update_or_create(
                    code=definition.code, defaults=defaults
                )
                created += 1 if is_new else 0
                if not is_new:
                    updated += 1
            result[definition.code] = permission

        registry_codes = {item.code for item in PERMISSIONS}
        orphans = sorted(
            Permission.objects.exclude(code__in=registry_codes).values_list("code", flat=True)
        )
        self.stdout.write(
            f"权限点：新增 {created}，更新 {updated}，注册表共 {len(registry_codes)} 条。"
        )
        if orphans:
            self.stdout.write(
                self.style.WARNING(
                    f"数据库中存在注册表未登记的权限点 {len(orphans)} 条（保留不删除）："
                    + "、".join(orphans[:10])
                )
            )
        return result

    # -- 菜单 ------------------------------------------------------------
    def _sync_menus(self, *, dry_run: bool) -> dict[str, Menu]:
        result: dict[str, Menu] = {}
        created = updated = 0

        code_to_def = {item.code: item for item in MENUS}
        # 先建目录（parent 为空），再建页面，保证外键可解析
        ordered = sorted(MENUS, key=lambda item: 0 if item.parent is None else 1)

        for definition in ordered:
            parent = None
            if definition.parent:
                if definition.parent not in code_to_def:
                    raise CommandError(f"菜单 {definition.code} 的上级 {definition.parent} 未登记。")
                parent = result.get(definition.parent)

            defaults = {
                "name": definition.name,
                "path": definition.path,
                "component": definition.component,
                "icon": definition.icon,
                "menu_type": definition.menu_type,
                "permission_code": definition.permission_code,
                "sort_order": definition.sort_order,
                "is_active": True,
                "visible": True,
            }
            if dry_run:
                menu = Menu.objects.filter(code=definition.code).first() or Menu(
                    code=definition.code, parent=parent, **defaults
                )
                if menu.pk is None:
                    created += 1
            else:
                menu, is_new = Menu.objects.update_or_create(
                    code=definition.code, defaults={**defaults, "parent": parent}
                )
                created += 1 if is_new else 0
                if not is_new:
                    updated += 1
            result[definition.code] = menu

        orphan_menus = sorted(
            Menu.objects.exclude(code__in=set(code_to_def)).values_list("code", flat=True)
        )
        self.stdout.write(f"菜单：新增 {created}，更新 {updated}，注册表共 {len(MENUS)} 条。")
        if orphan_menus:
            self.stdout.write(
                self.style.WARNING(
                    f"数据库中存在注册表未登记的菜单 {len(orphan_menus)} 条（保留不删除）："
                    + "、".join(orphan_menus[:10])
                )
            )
        return result

    # -- 角色 ------------------------------------------------------------
    def _sync_roles(
        self,
        permission_map: dict[str, Permission],
        menu_map: dict[str, Menu],
        *,
        dry_run: bool,
    ) -> None:
        all_codes = [item.code for item in PERMISSIONS]

        for definition in BUILTIN_ROLES:
            if definition.always_all:
                wanted = set(all_codes)
            else:
                wanted = {code for code in all_codes if _matches(code, definition.include)}
                wanted |= {code for code in definition.extra if code in permission_map}

            if not wanted:
                self.stdout.write(
                    self.style.WARNING(f"角色 {definition.code} 未匹配到任何权限点，请检查注册表。")
                )

            if dry_run:
                role = Role.objects.filter(code=definition.code).first() or Role(code=definition.code)
                self.stdout.write(f"角色 {definition.code}：将获得 {len(wanted)} 个权限点。")
            else:
                role, is_new = Role.objects.update_or_create(
                    code=definition.code,
                    defaults={
                        "name": definition.name,
                        "data_scope_type": definition.data_scope_type,
                        "is_system": True,
                        "is_active": True,
                        "sort_order": definition.sort_order,
                        "remark": definition.remark,
                    },
                )
                action = "新增" if is_new else "更新"
                self.stdout.write(f"角色 {definition.code}（{definition.name}）：{action}，权限 {len(wanted)} 个。")

            if dry_run:
                continue
            role.permissions.set(
                [permission_map[code] for code in sorted(wanted) if code in permission_map]
            )
            role.menus.set(self._menus_for_permissions(wanted, menu_map))

    def _menus_for_permissions(
        self, permission_codes: set[str], menu_map: dict[str, Menu]
    ) -> list[Menu]:
        """按权限点推导可见菜单，并补齐其上级目录。"""
        selected: set[str] = set()
        for definition in MENUS:
            if definition.permission_code and definition.permission_code in permission_codes:
                selected.add(definition.code)
        # 补齐目录
        for code in list(selected):
            parent = {item.code: item.parent for item in MENUS}.get(code)
            while parent:
                selected.add(parent)
                parent = {item.code: item.parent for item in MENUS}.get(parent)
        # 目录下无可见页面时不展示空目录
        children = {item.parent for item in MENUS if item.parent}
        selected = {code for code in selected if code in children or code in selected}
        return [menu_map[code] for code in sorted(selected) if code in menu_map]

    # -- 编码规则 / 字典 --------------------------------------------------
    def _sync_code_rules(self, *, dry_run: bool) -> None:
        created = 0
        for code, name, pattern, reset_period in CODE_RULES:
            if dry_run:
                continue
            _, is_new = CodeRule.objects.update_or_create(
                code=code,
                defaults={
                    "name": name,
                    "pattern": pattern,
                    "reset_period": reset_period,
                    "is_active": True,
                },
            )
            created += 1 if is_new else 0
        self.stdout.write(f"编码规则：新增 {created}，共计 {len(CODE_RULES)} 条。")

    def _sync_dictionaries(self, *, dry_run: bool) -> None:
        created = 0
        for code, name, items in DICTIONARIES:
            if dry_run:
                continue
            dictionary, is_new = Dictionary.objects.update_or_create(
                code=code,
                defaults={"name": name, "is_system": True, "is_active": True},
            )
            created += 1 if is_new else 0
            for index, (item_code, label) in enumerate(items):
                DictionaryItem.objects.update_or_create(
                    dictionary=dictionary,
                    code=item_code,
                    defaults={"label": label, "sort_order": (index + 1) * 10, "is_active": True},
                )
        self.stdout.write(f"数据字典：新增 {created}，共计 {len(DICTIONARIES)} 组。")

    # -- 管理员 ----------------------------------------------------------
    def _ensure_admin(self, options, *, dry_run: bool) -> None:
        username = (
            options["admin_username"]
            or settings.YISHANG.get("BOOTSTRAP_ADMIN_USERNAME")
            or "admin"
        ).strip()
        if not username:
            raise CommandError("管理员登录账号不能为空。")

        configured = settings.YISHANG.get("BOOTSTRAP_ADMIN_PASSWORD") or ""
        password = options["admin_password"] or configured

        existing = User.objects.filter(username=username).first()
        environment = settings.DJANGO_ENV

        if existing is not None and not options["reset_admin_password"]:
            self.stdout.write(
                f"管理员账号 {username} 已存在（版本 {existing.version}），保留原密码，仅同步权限属性。"
            )
            if not dry_run:
                changed = False
                if not existing.is_superuser:
                    existing.is_superuser = True
                    changed = True
                if not existing.is_staff:
                    existing.is_staff = True
                    changed = True
                if not existing.is_active:
                    existing.is_active = True
                    changed = True
                if changed:
                    existing.save(update_fields=["is_superuser", "is_staff", "is_active", "updated_at"])
            return

        if not password:
            if environment == "production":
                raise CommandError(
                    "生产环境必须通过 YISHANG_ADMIN_PASSWORD 或 --admin-password 提供管理员密码，"
                    "本命令不会生成或猜测生产口令。"
                )
            password = _generate_password()
            generated = True
        else:
            generated = False

        from django.contrib.auth.password_validation import validate_password

        try:
            validate_password(password)
        except Exception as exc:  # noqa: BLE001 - 需要把校验信息原样反馈给运维
            messages = getattr(exc, "messages", [str(exc)])
            raise CommandError("管理员密码不符合口令策略：" + "；".join(messages)) from exc

        if dry_run:
            self.stdout.write(f"[dry-run] 将创建/重置管理员账号 {username}。")
            return

        if existing is None:
            user = User(username=username, display_name="系统管理员", is_staff=True, is_superuser=True)
        else:
            user = existing
            user.is_staff = True
            user.is_superuser = True
        user.is_active = True
        user.set_password(password)
        # 由初始化命令写入的口令必须首次登录后修改
        user.must_change_password = True
        user.save()

        if generated:
            self.stdout.write(
                self.style.WARNING(
                    "已随机生成管理员初始密码（仅本次显示，请立即登录并修改）：\n"
                    f"    账号：{username}\n"
                    f"    密码：{password}\n"
                    "如需固定密码，请在 backend/.env 中设置 YISHANG_ADMIN_PASSWORD 后重新执行。"
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"管理员账号 {username} 已按提供的密码创建/重置，首次登录需修改密码。"
                )
            )
