"""组织与工厂模型：公司、部门、工厂、车间、线体、工位、员工、班组、班次。

首版定位为单企业、多工厂、多部门：模型保留公司归属，但尚不宣称完成
SaaS 多租户隔离。

排班日历 / 排班规则 / 人员排班展开尚未实现，见 docs/progress.md 未完成事项。
"""

from __future__ import annotations

from django.conf import settings
from django.db import models

from apps.core.models import BaseModel, CompanyScopedModel


class Company(BaseModel):
    code = models.CharField("公司编码", max_length=32, unique=True)
    name = models.CharField("公司名称", max_length=128)
    short_name = models.CharField("简称", max_length=64, blank=True, default="")
    address = models.CharField("地址", max_length=255, blank=True, default="")
    contact_person = models.CharField("联系人", max_length=64, blank=True, default="")
    contact_phone = models.CharField("联系电话", max_length=32, blank=True, default="")
    is_active = models.BooleanField("启用", default=True, db_index=True)
    remark = models.TextField("备注", blank=True, default="")

    class Meta:
        verbose_name = "公司"
        verbose_name_plural = "公司"
        ordering = ["code"]

    def __str__(self) -> str:
        return self.name


class Department(BaseModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="departments")
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="children"
    )
    code = models.CharField("部门编码", max_length=32)
    name = models.CharField("部门名称", max_length=128)
    department_type = models.CharField(
        "部门类型",
        max_length=32,
        choices=(
            ("management", "职能部门"),
            ("production", "生产部门"),
            ("quality", "质量部门"),
            ("warehouse", "仓储部门"),
            ("other", "其他"),
        ),
        default="management",
    )
    sort_order = models.IntegerField("排序", default=0)
    is_active = models.BooleanField("启用", default=True, db_index=True)
    remark = models.TextField("备注", blank=True, default="")

    class Meta:
        verbose_name = "部门"
        verbose_name_plural = "部门"
        ordering = ["company_id", "sort_order", "id"]
        constraints = [
            models.UniqueConstraint(fields=["company", "code"], name="uq_department_company_code"),
        ]

    def __str__(self) -> str:
        return f"{self.name}({self.code})"

    def clean(self) -> None:
        """层级合法性：上级部门必须属于同一公司，且不能形成环。"""
        from django.core.exceptions import ValidationError

        if self.parent_id is None:
            return
        if self.parent_id == self.pk:
            raise ValidationError({"parent": "上级部门不能是自己。"})
        if self.parent.company_id != self.company_id:
            raise ValidationError({"parent": "上级部门必须属于同一公司。"})
        ancestor = self.parent
        seen = {self.pk}
        while ancestor is not None:
            if ancestor.pk in seen:
                raise ValidationError({"parent": "部门层级存在循环引用。"})
            seen.add(ancestor.pk)
            ancestor = ancestor.parent


class Factory(CompanyScopedModel):
    code = models.CharField("工厂编码", max_length=32)
    name = models.CharField("工厂名称", max_length=128)
    address = models.CharField("地址", max_length=255, blank=True, default="")
    manager = models.ForeignKey(
        "factory.Employee",
        verbose_name="负责人",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    is_active = models.BooleanField("启用", default=True, db_index=True)
    remark = models.TextField("备注", blank=True, default="")

    class Meta:
        verbose_name = "工厂"
        verbose_name_plural = "工厂"
        ordering = ["company_id", "code"]
        constraints = [
            models.UniqueConstraint(fields=["company", "code"], name="uq_factory_company_code"),
        ]

    def __str__(self) -> str:
        return f"{self.name}({self.code})"


class Workshop(BaseModel):
    factory = models.ForeignKey(Factory, on_delete=models.PROTECT, related_name="workshops")
    code = models.CharField("车间编码", max_length=32)
    name = models.CharField("车间名称", max_length=128)
    workshop_type = models.CharField(
        "车间类型",
        max_length=32,
        choices=(
            ("cutting", "裁剪"),
            ("sewing", "缝制"),
            ("ironing", "整烫"),
            ("inspection", "检验"),
            ("packing", "包装"),
            ("other", "其他"),
        ),
        default="sewing",
    )
    sort_order = models.IntegerField("排序", default=0)
    is_active = models.BooleanField("启用", default=True, db_index=True)
    remark = models.TextField("备注", blank=True, default="")

    class Meta:
        verbose_name = "车间"
        verbose_name_plural = "车间"
        ordering = ["factory_id", "sort_order", "id"]
        constraints = [
            models.UniqueConstraint(fields=["factory", "code"], name="uq_workshop_factory_code"),
        ]

    def __str__(self) -> str:
        return f"{self.name}({self.code})"


class ProductionLine(BaseModel):
    workshop = models.ForeignKey(Workshop, on_delete=models.PROTECT, related_name="lines")
    code = models.CharField("线体编码", max_length=32)
    name = models.CharField("线体名称", max_length=128)
    line_type = models.CharField(
        "线体类型",
        max_length=32,
        choices=(("manual", "人工线"), ("hanging", "吊挂线"), ("automated", "自动化线")),
        default="manual",
    )
    daily_capacity = models.DecimalField(
        "日产能", max_digits=20, decimal_places=6, null=True, blank=True
    )
    is_active = models.BooleanField("启用", default=True, db_index=True)
    remark = models.TextField("备注", blank=True, default="")

    class Meta:
        verbose_name = "线体"
        verbose_name_plural = "线体"
        ordering = ["workshop_id", "code"]
        constraints = [
            models.UniqueConstraint(fields=["workshop", "code"], name="uq_line_workshop_code"),
        ]

    def __str__(self) -> str:
        return f"{self.name}({self.code})"


class Station(BaseModel):
    line = models.ForeignKey(ProductionLine, on_delete=models.PROTECT, related_name="stations")
    code = models.CharField("工位编码", max_length=32)
    name = models.CharField("工位名称", max_length=128)
    process_name = models.CharField("对应工序", max_length=64, blank=True, default="")
    sort_order = models.IntegerField("排序", default=0)
    is_active = models.BooleanField("启用", default=True, db_index=True)
    remark = models.TextField("备注", blank=True, default="")

    class Meta:
        verbose_name = "工位"
        verbose_name_plural = "工位"
        ordering = ["line_id", "sort_order", "id"]
        constraints = [
            models.UniqueConstraint(fields=["line", "code"], name="uq_station_line_code"),
        ]

    def __str__(self) -> str:
        return f"{self.name}({self.code})"


class Employee(CompanyScopedModel):
    """员工档案。与登录账号（identity.User）分离，两者可一对一关联。"""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        verbose_name="关联登录账号",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="employee_profile",
    )
    department = models.ForeignKey(
        Department, verbose_name="所属部门", null=True, blank=True, on_delete=models.PROTECT,
        related_name="employees",
    )
    factory = models.ForeignKey(
        Factory, verbose_name="所属工厂", null=True, blank=True, on_delete=models.PROTECT,
        related_name="employees",
    )
    employee_no = models.CharField("工号", max_length=32)
    name = models.CharField("姓名", max_length=64)
    gender = models.CharField(
        "性别", max_length=8, choices=(("male", "男"), ("female", "女"), ("unknown", "未知")),
        default="unknown",
    )
    phone = models.CharField("联系电话", max_length=32, blank=True, default="")
    email = models.EmailField("邮箱", blank=True, default="")
    position = models.CharField("岗位", max_length=64, blank=True, default="")
    employment_type = models.CharField(
        "用工性质",
        max_length=16,
        choices=(("full_time", "正式"), ("temporary", "临时"), ("intern", "实习"), ("outsourced", "外包")),
        default="full_time",
    )
    hire_date = models.DateField("入职日期", null=True, blank=True)
    leave_date = models.DateField("离职日期", null=True, blank=True)
    status = models.CharField(
        "在职状态",
        max_length=16,
        choices=(("active", "在职"), ("leave", "休假"), ("resigned", "离职")),
        default="active",
        db_index=True,
    )
    is_active = models.BooleanField("启用", default=True, db_index=True)
    remark = models.TextField("备注", blank=True, default="")

    class Meta:
        verbose_name = "员工"
        verbose_name_plural = "员工"
        ordering = ["company_id", "employee_no"]
        constraints = [
            models.UniqueConstraint(fields=["company", "employee_no"], name="uq_employee_company_no"),
        ]

    def __str__(self) -> str:
        return f"{self.name}({self.employee_no})"


class Shift(CompanyScopedModel):
    """班次定义。支持跨夜班（结束时间早于开始时间）。"""

    code = models.CharField("班次编码", max_length=32)
    name = models.CharField("班次名称", max_length=64)
    start_time = models.TimeField("上班时间")
    end_time = models.TimeField("下班时间")
    cross_day = models.BooleanField("跨夜班", default=False)
    break_minutes = models.PositiveIntegerField("休息时长(分钟)", default=0)
    is_active = models.BooleanField("启用", default=True, db_index=True)
    remark = models.TextField("备注", blank=True, default="")

    class Meta:
        verbose_name = "班次"
        verbose_name_plural = "班次"
        ordering = ["company_id", "code"]
        constraints = [
            models.UniqueConstraint(fields=["company", "code"], name="uq_shift_company_code"),
        ]

    def __str__(self) -> str:
        return f"{self.name}({self.code})"

    def save(self, *args, **kwargs):
        # 跨夜班由时间关系推导，避免人工填写与数据不一致
        self.cross_day = self.end_time <= self.start_time
        super().save(*args, **kwargs)


class Team(BaseModel):
    """班组。"""

    workshop = models.ForeignKey(
        Workshop, verbose_name="所属车间", null=True, blank=True, on_delete=models.PROTECT,
        related_name="teams",
    )
    shift = models.ForeignKey(
        Shift, verbose_name="默认班次", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="teams",
    )
    code = models.CharField("班组编码", max_length=32, unique=True)
    name = models.CharField("班组名称", max_length=64)
    leader = models.ForeignKey(
        Employee, verbose_name="班组长", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="leading_teams",
    )
    is_active = models.BooleanField("启用", default=True, db_index=True)
    remark = models.TextField("备注", blank=True, default="")

    class Meta:
        verbose_name = "班组"
        verbose_name_plural = "班组"
        ordering = ["code"]

    def __str__(self) -> str:
        return f"{self.name}({self.code})"


class TeamMember(BaseModel):
    """班组成员。"""

    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="members")
    employee = models.ForeignKey(
        Employee, on_delete=models.PROTECT, related_name="team_memberships"
    )
    role_in_team = models.CharField("班组角色", max_length=32, blank=True, default="")
    start_date = models.DateField("加入日期", null=True, blank=True)
    end_date = models.DateField("退出日期", null=True, blank=True)
    is_active = models.BooleanField("启用", default=True)

    class Meta:
        verbose_name = "班组成员"
        verbose_name_plural = "班组成员"
        ordering = ["team_id", "id"]
        constraints = [
            models.UniqueConstraint(fields=["team", "employee"], name="uq_team_member"),
        ]

    def __str__(self) -> str:
        return f"{self.team_id}-{self.employee_id}"
