"""用户、角色、权限、菜单与数据范围模型。

设计要点：
* 从首次迁移即使用自定义 User，避免后期更换困难；
* 用户负责登录与权限，员工档案（factory.Employee）负责组织/岗位，二者可一对一关联，
  且不是所有员工都必须拥有登录账号；
* 四层权限：菜单权限、操作权限、接口权限、数据范围权限。
"""

from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.core.cache import cache
from django.db import models
from django.utils import timezone

PERMISSION_CACHE_TTL_SECONDS = 300


class DataScopeType(models.TextChoices):
    ALL = "all", "全部数据"
    COMPANY = "company", "本公司"
    CUSTOM = "custom", "自定义组织范围"
    FACTORY = "factory", "指定工厂"
    DEPARTMENT = "department", "指定部门"
    WAREHOUSE = "warehouse", "指定仓库"
    SELF = "self", "仅本人"

    @classmethod
    def rank_map(cls) -> dict[str, int]:
        """范围宽窄排序：数值越大范围越宽。用于多角色合并时取最宽档。"""
        return {
            cls.ALL: 100,
            cls.COMPANY: 80,
            cls.CUSTOM: 70,
            cls.FACTORY: 60,
            cls.WAREHOUSE: 50,
            cls.DEPARTMENT: 40,
            cls.SELF: 10,
        }


class ScopeDimension(models.TextChoices):
    COMPANY = "company", "公司"
    FACTORY = "factory", "工厂"
    DEPARTMENT = "department", "部门"
    WAREHOUSE = "warehouse", "仓库"


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, username: str, password: str | None = None, **extra_fields):
        if not username:
            raise ValueError("登录账号不能为空。")
        user = self.model(username=username.strip(), **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, username: str, password: str | None = None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("超级管理员必须 is_superuser=True。")
        return self.create_user(username, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    username = models.CharField("登录账号", max_length=64, unique=True)
    display_name = models.CharField("姓名", max_length=64, blank=True, default="")
    phone = models.CharField("手机号", max_length=32, unique=True, null=True, blank=True)
    email = models.EmailField("邮箱", blank=True, default="")

    company = models.ForeignKey(
        "factory.Company",
        verbose_name="所属公司",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="users",
    )
    department = models.ForeignKey(
        "factory.Department",
        verbose_name="所属部门",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="users",
    )

    is_active = models.BooleanField("启用", default=True)
    is_staff = models.BooleanField("可登录后台", default=False)

    must_change_password = models.BooleanField("需强制修改密码", default=False)
    password_changed_at = models.DateTimeField("密码最后修改时间", null=True, blank=True)

    failed_login_count = models.PositiveIntegerField("连续登录失败次数", default=0)
    locked_until = models.DateTimeField("锁定至", null=True, blank=True)
    last_login_ip = models.GenericIPAddressField("最近登录 IP", null=True, blank=True)

    # 角色/授权变更时自增，使权限缓存立即失效
    permission_version = models.PositiveIntegerField("权限版本", default=0)

    date_joined = models.DateTimeField("创建时间", default=timezone.now)
    updated_at = models.DateTimeField("更新时间", auto_now=True)
    created_by = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    updated_by = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    version = models.PositiveIntegerField("版本号", default=0)
    remark = models.TextField("备注", blank=True, default="")

    objects = UserManager()

    USERNAME_FIELD = "username"
    REQUIRED_FIELDS: list[str] = []

    class Meta:
        verbose_name = "用户"
        verbose_name_plural = "用户"
        ordering = ["username"]

    def __str__(self) -> str:
        return f"{self.display_name or self.username}({self.username})"

    # -- Django 约定方法 -------------------------------------------------
    def get_full_name(self) -> str:
        return self.display_name or self.username

    def get_short_name(self) -> str:
        return self.display_name or self.username

    # -- 登录状态 --------------------------------------------------------
    @property
    def is_locked(self) -> bool:
        return bool(self.locked_until and self.locked_until > timezone.now())

    def register_login_failure(self, *, limit: int, lock_minutes: int) -> None:
        self.failed_login_count = (self.failed_login_count or 0) + 1
        if self.failed_login_count >= limit:
            self.locked_until = timezone.now() + timedelta(minutes=lock_minutes)
        self.save(update_fields=["failed_login_count", "locked_until", "updated_at"])

    def register_login_success(self, *, ip: str | None = None) -> None:
        self.failed_login_count = 0
        self.locked_until = None
        self.last_login = timezone.now()
        self.last_login_ip = ip or None
        self.save(
            update_fields=[
                "failed_login_count",
                "locked_until",
                "last_login",
                "last_login_ip",
                "updated_at",
            ]
        )

    def unlock(self) -> None:
        self.failed_login_count = 0
        self.locked_until = None
        self.save(update_fields=["failed_login_count", "locked_until", "updated_at"])

    def set_password(self, raw_password, *, mark_changed: bool = True):
        super().set_password(raw_password)
        if mark_changed:
            self.password_changed_at = timezone.now()
        self.must_change_password = False

    # -- 权限 ------------------------------------------------------------
    def active_roles(self) -> list[Role]:
        return list(self.roles.filter(is_active=True).order_by("sort_order", "id"))

    def bump_permission_version(self) -> None:
        type(self).objects.filter(pk=self.pk).update(
            permission_version=models.F("permission_version") + 1
        )
        self.refresh_from_db(fields=["permission_version"])

    def permission_codes(self) -> set[str]:
        """当前用户拥有的操作权限编码（带缓存，角色变更即刻失效）。"""
        if not self.is_active:
            return set()
        if self.is_superuser:
            return {"*"}
        cache_key = f"identity:user_perms:{self.pk}:{self.permission_version}"
        cached = cache.get(cache_key)
        if cached is not None:
            return set(cached)
        role_ids = list(self.roles.filter(is_active=True).values_list("id", flat=True))
        codes = (
            set(
                Permission.objects.filter(roles__id__in=role_ids)
                .values_list("code", flat=True)
                .distinct()
            )
            if role_ids
            else set()
        )
        cache.set(cache_key, sorted(codes), PERMISSION_CACHE_TTL_SECONDS)
        return codes

    def has_permission_codes(self, codes) -> bool:
        """同时具备全部编码才通过（AND 语义）。"""
        required = set(codes)
        if not required:
            return True
        owned = self.permission_codes()
        if "*" in owned:
            return True
        return required.issubset(owned)

    def menu_codes(self) -> set[str]:
        if self.is_superuser:
            return set(Menu.objects.values_list("code", flat=True))
        role_ids = list(self.roles.filter(is_active=True).values_list("id", flat=True))
        if not role_ids:
            return set()
        return set(
            Menu.objects.filter(roles__id__in=role_ids, is_active=True)
            .values_list("code", flat=True)
            .distinct()
        )


class PermissionType(models.TextChoices):
    MENU = "menu", "菜单权限"
    ACTION = "action", "操作权限"
    API = "api", "接口权限"
    DATA = "data", "数据范围权限"


class Permission(models.Model):
    """权限点。编码形如 sales.order.approve。"""

    id = models.BigAutoField(primary_key=True)
    code = models.CharField("权限编码", max_length=128, unique=True)
    name = models.CharField("权限名称", max_length=128)
    module = models.CharField("模块", max_length=64, db_index=True)
    resource = models.CharField("资源", max_length=64)
    action = models.CharField("动作", max_length=64)
    permission_type = models.CharField(
        "权限类型", max_length=16, choices=PermissionType.choices, default=PermissionType.ACTION
    )
    is_system = models.BooleanField("系统内置", default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "权限点"
        verbose_name_plural = "权限点"
        ordering = ["module", "resource", "action"]
        indexes = [models.Index(fields=["module", "resource"], name="idx_permission_module_resource")]

    def __str__(self) -> str:
        return self.code


class Menu(models.Model):
    """菜单权限（第一层）。前端按 code 渲染路由。"""

    id = models.BigAutoField(primary_key=True)
    code = models.CharField("菜单编码", max_length=64, unique=True)
    name = models.CharField("菜单名称", max_length=64)
    parent = models.ForeignKey(
        "self", verbose_name="上级菜单", null=True, blank=True, on_delete=models.CASCADE,
        related_name="children",
    )
    path = models.CharField("路由路径", max_length=128, blank=True, default="")
    component = models.CharField("前端组件", max_length=128, blank=True, default="")
    icon = models.CharField("图标", max_length=64, blank=True, default="")
    menu_type = models.CharField(
        "菜单类型",
        max_length=16,
        choices=(("directory", "目录"), ("page", "页面"), ("button", "按钮")),
        default="page",
    )
    permission_code = models.CharField("进入所需权限编码", max_length=128, blank=True, default="")
    sort_order = models.IntegerField("排序", default=0)
    is_active = models.BooleanField("启用", default=True)
    visible = models.BooleanField("显示", default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "菜单"
        verbose_name_plural = "菜单"
        ordering = ["sort_order", "id"]

    def __str__(self) -> str:
        return f"{self.name}({self.code})"


class Role(models.Model):
    """角色：操作权限集合 + 菜单集合 + 数据范围。"""

    id = models.BigAutoField(primary_key=True)
    code = models.CharField("角色编码", max_length=64, unique=True)
    name = models.CharField("角色名称", max_length=64)
    company = models.ForeignKey(
        "factory.Company",
        verbose_name="归属公司",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="roles",
    )
    data_scope_type = models.CharField(
        "数据范围", max_length=16, choices=DataScopeType.choices, default=DataScopeType.SELF
    )
    is_system = models.BooleanField("系统内置", default=False)
    is_active = models.BooleanField("启用", default=True, db_index=True)
    sort_order = models.IntegerField("排序", default=0)
    remark = models.TextField("备注", blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    permissions = models.ManyToManyField(Permission, related_name="roles", blank=True)
    menus = models.ManyToManyField(Menu, related_name="roles", blank=True)
    users = models.ManyToManyField(
        settings.AUTH_USER_MODEL, through="UserRole", related_name="roles", blank=True
    )

    class Meta:
        verbose_name = "角色"
        verbose_name_plural = "角色"
        ordering = ["sort_order", "id"]

    def __str__(self) -> str:
        return f"{self.name}({self.code})"


class RoleScopeGrant(models.Model):
    """自定义数据范围的授权明细。"""

    id = models.BigAutoField(primary_key=True)
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name="scope_grants")
    dimension = models.CharField("范围维度", max_length=16, choices=ScopeDimension.choices)
    object_id = models.PositiveBigIntegerField("对象主键")

    class Meta:
        verbose_name = "角色数据范围"
        verbose_name_plural = "角色数据范围"
        constraints = [
            models.UniqueConstraint(
                fields=["role", "dimension", "object_id"], name="uq_role_scope_grant"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.role_id}:{self.dimension}:{self.object_id}"


class UserRole(models.Model):
    """用户与角色的关联。"""

    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="role_links"
    )
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name="user_links")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "用户角色"
        verbose_name_plural = "用户角色"
        constraints = [models.UniqueConstraint(fields=["user", "role"], name="uq_user_role")]

    def __str__(self) -> str:
        return f"{self.user_id}-{self.role_id}"


class LoginAttempt(models.Model):
    """登录尝试记录，用于限流、失败锁定与安全审计。"""

    id = models.BigAutoField(primary_key=True)
    username = models.CharField("登录账号", max_length=64, db_index=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    ip_address = models.GenericIPAddressField("来源 IP", null=True, blank=True)
    successful = models.BooleanField("是否成功", default=False)
    failure_reason = models.CharField("失败原因", max_length=128, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "登录记录"
        verbose_name_plural = "登录记录"
        ordering = ["-id"]
        indexes = [models.Index(fields=["username", "-created_at"], name="idx_login_attempt_user")]

    def __str__(self) -> str:
        return f"{self.username}@{self.created_at:%Y-%m-%d %H:%M:%S}"
