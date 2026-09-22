"""安全环保管理（EHS）数据模型。

模块覆盖四块：**安全管理、环保管理、消防管理、设备设施安全**，外加统一的
操作日志。设计取舍：

* 「动火 / 检维修 / 防爆防静电 / 受限空间」共用一张 ``WorkPermit`` 表，
  用 ``permit_type`` 区分——它们本质是同一套「作业许可」流程，
  拆成四张表只会让审批、监护、验收逻辑复制四遍；
* 「本质安全 / 防爆防静电 / 防火防爆」共用一张 ``SafetyCheck`` 表（``check_type``），
  同理：都是「按检查表检查 → 发现问题 → 整改 → 关闭」；
* 特种设备检验通过 ``equipment`` 关联设备台账（``is_special`` 的设备），
  不复制设备信息；
* 需要过程闭环的对象（隐患、事故、作业许可）状态只能由服务层推进，
  每次推进写一条 ``EhsOperationLog``；台账类对象（制度、培训、设施）只做登记与状态维护。
"""

from __future__ import annotations

from decimal import Decimal

from django.db import models
from django.db.models import Q

from apps.core.constants import quantity_field, rate_field
from apps.core.models import CompanyScopedModel


class EhsDomain(models.TextChoices):
    """操作日志的归属域，与菜单四大块一一对应。"""

    SAFETY = "safety", "安全管理"
    ENVIRONMENT = "environment", "环保管理"
    FIRE = "fire", "消防管理"
    EQUIPMENT_SAFETY = "equipment_safety", "设备设施安全"


# ---------------------------------------------------------------------------
# 安全管理
# ---------------------------------------------------------------------------


class RegulationStatus(models.TextChoices):
    DRAFT = "draft", "草稿"
    EFFECTIVE = "effective", "生效"
    REVISED = "revised", "已修订"
    ABOLISHED = "abolished", "已废止"


class RegulationCategory(models.TextChoices):
    SYSTEM = "system", "管理制度"
    OPERATION = "operation", "操作规程"
    EMERGENCY = "emergency", "应急制度"
    OTHER = "other", "其他"


class TrainingType(models.TextChoices):
    INDUCTION = "induction", "入职三级教育"
    SPECIAL = "special", "专项培训"
    REFRESHER = "refresher", "复训"
    DRILL = "drill", "演练培训"


class TrainingStatus(models.TextChoices):
    PLANNED = "planned", "计划中"
    ONGOING = "ongoing", "进行中"
    FINISHED = "finished", "已完成"
    CANCELLED = "cancelled", "已取消"


class HazardLevel(models.TextChoices):
    LOW = "low", "低"
    MEDIUM = "medium", "中"
    HIGH = "high", "高"
    MAJOR = "major", "重大"


class HazardSource(models.TextChoices):
    INSPECTION = "inspection", "检查发现"
    REPORT = "report", "员工上报"
    EXTERNAL = "external", "外部检查"
    OTHER = "other", "其他"


class HazardStatus(models.TextChoices):
    REPORTED = "reported", "待整改"
    RECTIFYING = "rectifying", "整改中"
    VERIFYING = "verifying", "待验收"
    CLOSED = "closed", "已关闭"


class AccidentCategory(models.TextChoices):
    INJURY = "injury", "人身伤害"
    EQUIPMENT = "equipment", "设备事故"
    FIRE = "fire", "火灾事故"
    ENVIRONMENT = "environment", "环境事故"
    OTHER = "other", "其他"


class AccidentLevel(models.TextChoices):
    MINOR = "minor", "轻微"
    GENERAL = "general", "一般"
    SERIOUS = "serious", "较大"
    MAJOR = "major", "重大"


class AccidentStatus(models.TextChoices):
    REPORTED = "reported", "已上报"
    INVESTIGATING = "investigating", "调查中"
    RECTIFIED = "rectified", "已整改"
    CLOSED = "closed", "已关闭"


class ResponseLevel(models.TextChoices):
    COMPANY = "company", "公司级"
    WORKSHOP = "workshop", "车间级"
    TEAM = "team", "班组级"


class EmergencyPlanType(models.TextChoices):
    FIRE = "fire", "火灾"
    PRODUCTION = "production", "生产安全事故"
    ENVIRONMENT = "environment", "突发环境事件"
    OCCUPATION = "occupation", "职业健康"
    OTHER = "other", "其他"


class SafetyRegulation(CompanyScopedModel):
    """安全管理制度 / 操作规程 / 应急制度。"""

    code = models.CharField("制度编号", max_length=32)
    name = models.CharField("制度名称", max_length=128)
    category = models.CharField(
        "制度类别", max_length=16, choices=RegulationCategory.choices, db_index=True
    )
    version_no = models.CharField("版本号", max_length=16, blank=True, default="")
    issue_org = models.CharField("发布单位", max_length=64, blank=True, default="")
    issue_date = models.DateField("发布日期", null=True, blank=True)
    effective_date = models.DateField("生效日期", null=True, blank=True)
    status = models.CharField(
        "状态", max_length=16, choices=RegulationStatus.choices,
        default=RegulationStatus.DRAFT, db_index=True,
    )
    owner_department = models.ForeignKey(
        "factory.Department", verbose_name="归口部门", null=True, blank=True,
        on_delete=models.PROTECT, related_name="+",
    )
    owner_employee = models.ForeignKey(
        "factory.Employee", verbose_name="责任人", null=True, blank=True,
        on_delete=models.PROTECT, related_name="+",
    )
    remark = models.TextField("备注", blank=True, default="")
    is_active = models.BooleanField("启用", default=True, db_index=True)

    class Meta:
        verbose_name = "安全制度"
        verbose_name_plural = "安全制度"
        ordering = ["code"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "code"], name="uq_safety_regulation_company_code"
            )
        ]

    def __str__(self) -> str:
        return f"{self.code} {self.name}"


class SafetyTraining(CompanyScopedModel):
    """安全培训：计划、实施与考核结果登记。"""

    training_no = models.CharField("培训编号", max_length=32)
    topic = models.CharField("培训主题", max_length=128)
    training_type = models.CharField(
        "培训类别", max_length=16, choices=TrainingType.choices, default=TrainingType.SPECIAL
    )
    trainer = models.CharField("讲师", max_length=64, blank=True, default="")
    department = models.ForeignKey(
        "factory.Department", verbose_name="组织部门", null=True, blank=True,
        on_delete=models.PROTECT, related_name="+",
    )
    planned_date = models.DateField("计划日期", null=True, blank=True)
    actual_date = models.DateField("实际日期", null=True, blank=True, db_index=True)
    duration_hours = rate_field("学时", default=Decimal("0"))
    participant_count = models.PositiveIntegerField("参训人数", default=0)
    passed_count = models.PositiveIntegerField("考核通过人数", default=0)
    status = models.CharField(
        "状态", max_length=16, choices=TrainingStatus.choices,
        default=TrainingStatus.PLANNED, db_index=True,
    )
    remark = models.TextField("备注", blank=True, default="")

    class Meta:
        verbose_name = "安全培训"
        verbose_name_plural = "安全培训"
        ordering = ["-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "training_no"], name="uq_safety_training_company_no"
            ),
            models.CheckConstraint(
                condition=Q(passed_count__lte=models.F("participant_count")),
                name="ck_safety_training_passed_lte_participants",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.training_no} {self.topic}"


class HazardRecord(CompanyScopedModel):
    """隐患排查治理：发现 → 整改 → 验收 → 关闭。"""

    hazard_no = models.CharField("隐患编号", max_length=32)
    title = models.CharField("隐患标题", max_length=128)
    description = models.TextField("隐患描述", blank=True, default="")
    level = models.CharField(
        "隐患级别", max_length=16, choices=HazardLevel.choices,
        default=HazardLevel.MEDIUM, db_index=True,
    )
    source = models.CharField(
        "来源", max_length=16, choices=HazardSource.choices, default=HazardSource.INSPECTION
    )
    location = models.CharField("发现地点", max_length=128, blank=True, default="")
    department = models.ForeignKey(
        "factory.Department", verbose_name="责任部门", null=True, blank=True,
        on_delete=models.PROTECT, related_name="+", db_index=True,
    )
    reported_by = models.ForeignKey(
        "factory.Employee", verbose_name="上报人", null=True, blank=True,
        on_delete=models.PROTECT, related_name="+",
    )
    found_date = models.DateField("发现日期", db_index=True)
    due_date = models.DateField("整改期限", null=True, blank=True, db_index=True)
    status = models.CharField(
        "状态", max_length=16, choices=HazardStatus.choices,
        default=HazardStatus.REPORTED, db_index=True,
    )
    rectify_measure = models.TextField("整改措施", blank=True, default="")
    rectified_by = models.ForeignKey(
        "factory.Employee", verbose_name="整改人", null=True, blank=True,
        on_delete=models.PROTECT, related_name="+",
    )
    rectified_date = models.DateField("整改完成日期", null=True, blank=True)
    verify_result = models.CharField("验收结论", max_length=255, blank=True, default="")
    verified_by = models.ForeignKey(
        "factory.Employee", verbose_name="验收人", null=True, blank=True,
        on_delete=models.PROTECT, related_name="+",
    )
    verified_date = models.DateField("验收日期", null=True, blank=True)
    remark = models.TextField("备注", blank=True, default="")

    class Meta:
        verbose_name = "隐患排查"
        verbose_name_plural = "隐患排查"
        ordering = ["-found_date", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "hazard_no"], name="uq_hazard_record_company_no"
            )
        ]
        indexes = [models.Index(fields=["company", "status"], name="idx_hazard_status")]

    def __str__(self) -> str:
        return f"{self.hazard_no} {self.title}"


class EmergencyPlan(CompanyScopedModel):
    """应急预案：编制、评审与演练周期。"""

    code = models.CharField("预案编号", max_length=32)
    name = models.CharField("预案名称", max_length=128)
    plan_type = models.CharField(
        "预案类型", max_length=16, choices=EmergencyPlanType.choices,
        default=EmergencyPlanType.FIRE,
    )
    response_level = models.CharField(
        "响应级别", max_length=16, choices=ResponseLevel.choices, default=ResponseLevel.COMPANY
    )
    issue_date = models.DateField("发布/修订日期", null=True, blank=True)
    review_date = models.DateField("评审日期", null=True, blank=True)
    drill_cycle_days = models.PositiveIntegerField("演练周期（天）", default=365)
    next_drill_date = models.DateField("下次演练日期", null=True, blank=True, db_index=True)
    status = models.CharField(
        "状态", max_length=16, choices=RegulationStatus.choices,
        default=RegulationStatus.DRAFT, db_index=True,
    )
    owner_employee = models.ForeignKey(
        "factory.Employee", verbose_name="负责人", null=True, blank=True,
        on_delete=models.PROTECT, related_name="+",
    )
    remark = models.TextField("备注", blank=True, default="")
    is_active = models.BooleanField("启用", default=True, db_index=True)

    class Meta:
        verbose_name = "应急预案"
        verbose_name_plural = "应急预案"
        ordering = ["code"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "code"], name="uq_emergency_plan_company_code"
            ),
            models.CheckConstraint(
                condition=Q(drill_cycle_days__gt=0), name="ck_emergency_plan_cycle_positive"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.code} {self.name}"


class AccidentRecord(CompanyScopedModel):
    """事故处理：上报 → 调查 → 整改 → 关闭。"""

    accident_no = models.CharField("事故编号", max_length=32)
    title = models.CharField("事故标题", max_length=128)
    category = models.CharField(
        "事故类别", max_length=16, choices=AccidentCategory.choices,
        default=AccidentCategory.INJURY,
    )
    level = models.CharField(
        "事故等级", max_length=16, choices=AccidentLevel.choices,
        default=AccidentLevel.MINOR, db_index=True,
    )
    occurred_at = models.DateTimeField("发生时间", db_index=True)
    location = models.CharField("发生地点", max_length=128, blank=True, default="")
    department = models.ForeignKey(
        "factory.Department", verbose_name="责任部门", null=True, blank=True,
        on_delete=models.PROTECT, related_name="+",
    )
    injured_count = models.PositiveIntegerField("受伤人数", default=0)
    lost_days = models.PositiveIntegerField("损失工日", default=0)
    loss_amount = quantity_field("直接损失金额", default=Decimal("0"))
    description = models.TextField("事故经过", blank=True, default="")
    causes = models.TextField("原因分析", blank=True, default="")
    measures = models.TextField("整改与预防措施", blank=True, default="")
    reporter = models.ForeignKey(
        "factory.Employee", verbose_name="上报人", null=True, blank=True,
        on_delete=models.PROTECT, related_name="+",
    )
    reported_at = models.DateTimeField("上报时间", null=True, blank=True)
    investigator = models.ForeignKey(
        "factory.Employee", verbose_name="调查负责人", null=True, blank=True,
        on_delete=models.PROTECT, related_name="+",
    )
    investigation_result = models.TextField("调查结论", blank=True, default="")
    status = models.CharField(
        "状态", max_length=16, choices=AccidentStatus.choices,
        default=AccidentStatus.REPORTED, db_index=True,
    )
    closed_date = models.DateField("关闭日期", null=True, blank=True)
    remark = models.TextField("备注", blank=True, default="")

    class Meta:
        verbose_name = "事故记录"
        verbose_name_plural = "事故记录"
        ordering = ["-occurred_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "accident_no"], name="uq_accident_record_company_no"
            ),
            models.CheckConstraint(
                condition=Q(loss_amount__gte=0), name="ck_accident_loss_non_negative"
            ),
        ]
        indexes = [models.Index(fields=["company", "status"], name="idx_accident_status")]

    def __str__(self) -> str:
        return f"{self.accident_no} {self.title}"


# ---------------------------------------------------------------------------
# 环保管理
# ---------------------------------------------------------------------------


class EnvironmentMedium(models.TextChoices):
    WASTE_WATER = "waste_water", "废水"
    WASTE_GAS = "waste_gas", "废气"
    NOISE = "noise", "噪声"
    OTHER = "other", "其他"


class WasteType(models.TextChoices):
    GENERAL = "general", "一般固废"
    HAZARDOUS = "hazardous", "危险废物"


class WasteStatus(models.TextChoices):
    STORED = "stored", "厂内暂存"
    TRANSFERRED = "transferred", "已转移"
    DISPOSED = "disposed", "已处置"


class ComplianceResult(models.TextChoices):
    COMPLIANT = "compliant", "符合"
    PARTIAL = "partial", "部分符合"
    NON_COMPLIANT = "non_compliant", "不符合"


class ComplianceStatus(models.TextChoices):
    PENDING = "pending", "待整改"
    RECTIFIED = "rectified", "已整改"
    CLOSED = "closed", "已关闭"


class ComplianceCheckType(models.TextChoices):
    SELF = "self", "内部自查"
    GOVERNMENT = "government", "政府检查"
    THIRD_PARTY = "third_party", "第三方审核"
    PERMIT = "permit", "排污许可核查"


class EnvironmentMonitor(CompanyScopedModel):
    """排污与废水废气监测记录：一次监测一行，超限自动判为不达标。"""

    monitor_no = models.CharField("监测编号", max_length=32)
    medium = models.CharField(
        "排放介质", max_length=16, choices=EnvironmentMedium.choices,
        default=EnvironmentMedium.WASTE_WATER, db_index=True,
    )
    point_name = models.CharField("监测点位", max_length=64)
    pollutant = models.CharField("监测项目", max_length=64)
    limit_value = quantity_field("排放限值", null=True, blank=True)
    measured_value = quantity_field("实测值", null=True, blank=True)
    unit = models.CharField("计量单位", max_length=16, blank=True, default="")
    is_compliant = models.BooleanField("是否达标", default=True, db_index=True)
    monitored_at = models.DateTimeField("监测时间", db_index=True)
    permit_no = models.CharField("排污许可证号", max_length=64, blank=True, default="")
    monitor_org = models.CharField("监测单位", max_length=64, blank=True, default="")
    remark = models.TextField("备注", blank=True, default="")

    class Meta:
        verbose_name = "排污监测"
        verbose_name_plural = "排污监测"
        ordering = ["-monitored_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "monitor_no"], name="uq_env_monitor_company_no"
            )
        ]

    def __str__(self) -> str:
        return f"{self.monitor_no} {self.point_name}-{self.pollutant}"


class WasteRecord(CompanyScopedModel):
    """固废 / 危废台账：产生、暂存、转移与处置全过程留痕。"""

    waste_no = models.CharField("台账编号", max_length=32)
    waste_name = models.CharField("废物名称", max_length=64)
    waste_type = models.CharField(
        "废物类别", max_length=16, choices=WasteType.choices,
        default=WasteType.GENERAL, db_index=True,
    )
    waste_code = models.CharField("危废代码", max_length=32, blank=True, default="")
    quantity = quantity_field("产生量", default=Decimal("0"))
    unit = models.CharField("计量单位", max_length=16, blank=True, default="吨")
    produced_date = models.DateField("产生日期", db_index=True)
    storage_location = models.CharField("暂存地点", max_length=128, blank=True, default="")
    disposal_method = models.CharField("处置方式", max_length=64, blank=True, default="")
    disposal_org = models.CharField("处置单位", max_length=128, blank=True, default="")
    transfer_no = models.CharField("转移联单号", max_length=64, blank=True, default="")
    disposed_date = models.DateField("处置日期", null=True, blank=True)
    status = models.CharField(
        "状态", max_length=16, choices=WasteStatus.choices,
        default=WasteStatus.STORED, db_index=True,
    )
    remark = models.TextField("备注", blank=True, default="")

    class Meta:
        verbose_name = "固废危废台账"
        verbose_name_plural = "固废危废台账"
        ordering = ["-produced_date", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "waste_no"], name="uq_waste_record_company_no"
            ),
            models.CheckConstraint(
                condition=Q(quantity__gte=0), name="ck_waste_quantity_non_negative"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.waste_no} {self.waste_name}"


class ComplianceCheck(CompanyScopedModel):
    """环保合规检查：内外部检查结论与整改闭环。"""

    check_no = models.CharField("检查编号", max_length=32)
    title = models.CharField("检查事项", max_length=128)
    check_type = models.CharField(
        "检查类型", max_length=16, choices=ComplianceCheckType.choices,
        default=ComplianceCheckType.SELF,
    )
    check_date = models.DateField("检查日期", db_index=True)
    organization = models.CharField("检查单位", max_length=128, blank=True, default="")
    checker = models.ForeignKey(
        "factory.Employee", verbose_name="检查人", null=True, blank=True,
        on_delete=models.PROTECT, related_name="+",
    )
    result = models.CharField(
        "检查结论", max_length=16, choices=ComplianceResult.choices,
        default=ComplianceResult.COMPLIANT, db_index=True,
    )
    issues = models.TextField("发现问题", blank=True, default="")
    rectify_due_date = models.DateField("整改期限", null=True, blank=True)
    status = models.CharField(
        "整改状态", max_length=16, choices=ComplianceStatus.choices,
        default=ComplianceStatus.PENDING, db_index=True,
    )
    rectified_date = models.DateField("整改完成日期", null=True, blank=True)
    owner_employee = models.ForeignKey(
        "factory.Employee", verbose_name="整改责任人", null=True, blank=True,
        on_delete=models.PROTECT, related_name="+",
    )
    remark = models.TextField("备注", blank=True, default="")

    class Meta:
        verbose_name = "环保合规检查"
        verbose_name_plural = "环保合规检查"
        ordering = ["-check_date", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "check_no"], name="uq_compliance_check_company_no"
            )
        ]

    def __str__(self) -> str:
        return f"{self.check_no} {self.title}"


# ---------------------------------------------------------------------------
# 消防管理
# ---------------------------------------------------------------------------


class FireFacilityType(models.TextChoices):
    EXTINGUISHER = "extinguisher", "灭火器"
    HYDRANT = "hydrant", "消火栓"
    ALARM = "alarm", "火灾自动报警"
    SPRINKLER = "sprinkler", "自动喷淋"
    EXIT = "exit", "疏散设施"
    OTHER = "other", "其他"


class FireFacilityStatus(models.TextChoices):
    NORMAL = "normal", "正常"
    DUE = "due", "待检"
    EXPIRED = "expired", "已过期"
    SCRAPPED = "scrapped", "已报废"


class FireDrillType(models.TextChoices):
    EXTINGUISHER = "extinguisher", "灭火实操"
    EVACUATION = "evacuation", "疏散演练"
    JOINT = "joint", "联合演练"
    OTHER = "other", "其他"


class PermitType(models.TextChoices):
    HOT_WORK = "hot_work", "动火作业"
    MAINTENANCE = "maintenance", "检维修作业"
    EXPLOSION_PROOF = "explosion_proof", "防爆防静电作业"
    CONFINED_SPACE = "confined_space", "受限空间作业"


class PermitRiskLevel(models.TextChoices):
    LOW = "low", "低风险"
    MEDIUM = "medium", "中风险"
    HIGH = "high", "高风险"


class PermitStatus(models.TextChoices):
    APPLIED = "applied", "待审批"
    APPROVED = "approved", "已批准"
    WORKING = "working", "作业中"
    FINISHED = "finished", "已完工"
    ACCEPTED = "accepted", "已验收"
    REJECTED = "rejected", "已驳回"


class FireFacility(CompanyScopedModel):
    """消防设施台账：灭火器、消火栓、报警、喷淋、疏散设施。"""

    code = models.CharField("设施编号", max_length=32)
    name = models.CharField("设施名称", max_length=64)
    facility_type = models.CharField(
        "设施类型", max_length=16, choices=FireFacilityType.choices,
        default=FireFacilityType.EXTINGUISHER, db_index=True,
    )
    location = models.CharField("设置位置", max_length=128, blank=True, default="")
    quantity = models.PositiveIntegerField("数量", default=1)
    unit = models.CharField("单位", max_length=16, blank=True, default="具")
    last_check_date = models.DateField("上次检查日期", null=True, blank=True)
    next_check_date = models.DateField("下次检查日期", null=True, blank=True, db_index=True)
    status = models.CharField(
        "状态", max_length=16, choices=FireFacilityStatus.choices,
        default=FireFacilityStatus.NORMAL, db_index=True,
    )
    department = models.ForeignKey(
        "factory.Department", verbose_name="责任部门", null=True, blank=True,
        on_delete=models.PROTECT, related_name="+",
    )
    owner_employee = models.ForeignKey(
        "factory.Employee", verbose_name="责任人", null=True, blank=True,
        on_delete=models.PROTECT, related_name="+",
    )
    remark = models.TextField("备注", blank=True, default="")
    is_active = models.BooleanField("启用", default=True, db_index=True)

    class Meta:
        verbose_name = "消防设施"
        verbose_name_plural = "消防设施"
        ordering = ["code"]
        constraints = [
            models.UniqueConstraint(fields=["company", "code"], name="uq_fire_facility_company_code")
        ]

    def __str__(self) -> str:
        return f"{self.code} {self.name}"


class FireDrill(CompanyScopedModel):
    """消防演练记录。"""

    drill_no = models.CharField("演练编号", max_length=32)
    topic = models.CharField("演练主题", max_length=128)
    drill_type = models.CharField(
        "演练类型", max_length=16, choices=FireDrillType.choices,
        default=FireDrillType.EXTINGUISHER,
    )
    planned_date = models.DateField("计划日期", null=True, blank=True)
    actual_date = models.DateField("实际日期", null=True, blank=True, db_index=True)
    organizer = models.CharField("组织者", max_length=64, blank=True, default="")
    participant_count = models.PositiveIntegerField("参与人数", default=0)
    duration_minutes = models.PositiveIntegerField("时长（分钟）", default=0)
    assessment = models.TextField("评估结论", blank=True, default="")
    issues = models.TextField("发现问题", blank=True, default="")
    plan = models.ForeignKey(
        EmergencyPlan, verbose_name="关联预案", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="drills",
    )
    remark = models.TextField("备注", blank=True, default="")

    class Meta:
        verbose_name = "消防演练"
        verbose_name_plural = "消防演练"
        ordering = ["-id"]
        constraints = [
            models.UniqueConstraint(fields=["company", "drill_no"], name="uq_fire_drill_company_no")
        ]

    def __str__(self) -> str:
        return f"{self.drill_no} {self.topic}"


class WorkPermit(CompanyScopedModel):
    """作业许可：动火 / 检维修 / 防爆防静电 / 受限空间共用一套审批与监护流程。"""

    permit_no = models.CharField("作业许可编号", max_length=32)
    permit_type = models.CharField(
        "作业类型", max_length=24, choices=PermitType.choices,
        default=PermitType.HOT_WORK, db_index=True,
    )
    status = models.CharField(
        "状态", max_length=16, choices=PermitStatus.choices,
        default=PermitStatus.APPLIED, db_index=True,
    )
    work_content = models.TextField("作业内容")
    work_location = models.CharField("作业地点", max_length=128, blank=True, default="")
    risk_level = models.CharField(
        "风险等级", max_length=16, choices=PermitRiskLevel.choices,
        default=PermitRiskLevel.MEDIUM,
    )
    protective_measures = models.TextField("安全防护措施", blank=True, default="")
    applicant = models.ForeignKey(
        "factory.Employee", verbose_name="申请人", null=True, blank=True,
        on_delete=models.PROTECT, related_name="+",
    )
    department = models.ForeignKey(
        "factory.Department", verbose_name="申请部门", null=True, blank=True,
        on_delete=models.PROTECT, related_name="+",
    )
    start_at = models.DateTimeField("计划开始时间", null=True, blank=True)
    end_at = models.DateTimeField("计划结束时间", null=True, blank=True)
    approver = models.ForeignKey(
        "factory.Employee", verbose_name="审批人", null=True, blank=True,
        on_delete=models.PROTECT, related_name="+",
    )
    approved_at = models.DateTimeField("审批时间", null=True, blank=True)
    guardian = models.ForeignKey(
        "factory.Employee", verbose_name="监护人", null=True, blank=True,
        on_delete=models.PROTECT, related_name="+",
    )
    started_at = models.DateTimeField("实际开始时间", null=True, blank=True)
    finished_at = models.DateTimeField("实际结束时间", null=True, blank=True)
    accepted_by = models.ForeignKey(
        "factory.Employee", verbose_name="验收人", null=True, blank=True,
        on_delete=models.PROTECT, related_name="+",
    )
    accepted_at = models.DateTimeField("验收时间", null=True, blank=True)
    result = models.TextField("完工与验收结论", blank=True, default="")
    remark = models.TextField("备注", blank=True, default="")

    class Meta:
        verbose_name = "作业许可"
        verbose_name_plural = "作业许可"
        ordering = ["-id"]
        constraints = [
            models.UniqueConstraint(fields=["company", "permit_no"], name="uq_work_permit_company_no")
        ]
        indexes = [models.Index(fields=["company", "status"], name="idx_work_permit_status")]

    def __str__(self) -> str:
        return f"{self.permit_no} {self.get_permit_type_display()}"


# ---------------------------------------------------------------------------
# 设备设施安全
# ---------------------------------------------------------------------------


class SafetyCheckType(models.TextChoices):
    INTRINSIC = "intrinsic", "本质安全检查"
    EXPLOSION_PROOF = "explosion_proof", "防爆防静电检查"
    FIRE_PROOF = "fire_proof", "防火防爆检查"


class SafetyCheckStatus(models.TextChoices):
    NORMAL = "normal", "正常"
    ABNORMAL = "abnormal", "发现问题"
    RECTIFIED = "rectified", "已整改"
    CLOSED = "closed", "已关闭"


class SpecialEquipmentResult(models.TextChoices):
    QUALIFIED = "qualified", "合格"
    CONDITIONAL = "conditional", "带条件合格"
    UNQUALIFIED = "unqualified", "不合格"


class SafetyCheck(CompanyScopedModel):
    """安全检查：本质安全 / 防爆防静电 / 防火防爆，同一套「检查—整改—关闭」。"""

    check_no = models.CharField("检查编号", max_length=32)
    check_type = models.CharField(
        "检查类型", max_length=24, choices=SafetyCheckType.choices,
        default=SafetyCheckType.INTRINSIC, db_index=True,
    )
    title = models.CharField("检查主题", max_length=128)
    check_date = models.DateField("检查日期", db_index=True)
    checker = models.ForeignKey(
        "factory.Employee", verbose_name="检查人", null=True, blank=True,
        on_delete=models.PROTECT, related_name="+",
    )
    department = models.ForeignKey(
        "factory.Department", verbose_name="受检部门", null=True, blank=True,
        on_delete=models.PROTECT, related_name="+",
    )
    equipment = models.ForeignKey(
        "equipment.Equipment", verbose_name="关联设备", null=True, blank=True,
        on_delete=models.PROTECT, related_name="safety_checks",
    )
    check_content = models.TextField("检查内容", blank=True, default="")
    problem_count = models.PositiveIntegerField("发现问题数", default=0)
    conclusion = models.TextField("检查结论", blank=True, default="")
    status = models.CharField(
        "状态", max_length=16, choices=SafetyCheckStatus.choices,
        default=SafetyCheckStatus.NORMAL, db_index=True,
    )
    rectify_requirement = models.TextField("整改要求", blank=True, default="")
    rectified_date = models.DateField("整改完成日期", null=True, blank=True)
    remark = models.TextField("备注", blank=True, default="")

    class Meta:
        verbose_name = "安全检查"
        verbose_name_plural = "安全检查"
        ordering = ["-check_date", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["company", "check_no"], name="uq_safety_check_company_no")
        ]

    def __str__(self) -> str:
        return f"{self.check_no} {self.title}"


class SpecialEquipmentInspection(CompanyScopedModel):
    """特种设备检验：关联设备台账中的特种设备，跟踪下次检验日期。"""

    certificate_no = models.CharField("检验报告编号", max_length=32)
    equipment = models.ForeignKey(
        "equipment.Equipment", verbose_name="特种设备", null=True, blank=True,
        on_delete=models.PROTECT, related_name="inspections", db_index=True,
    )
    equipment_name = models.CharField("设备名称", max_length=64, blank=True, default="")
    inspection_org = models.CharField("检验机构", max_length=128, blank=True, default="")
    inspection_date = models.DateField("检验日期", db_index=True)
    next_inspection_date = models.DateField("下次检验日期", null=True, blank=True, db_index=True)
    result = models.CharField(
        "检验结论", max_length=16, choices=SpecialEquipmentResult.choices,
        default=SpecialEquipmentResult.QUALIFIED, db_index=True,
    )
    inspector = models.CharField("检验人员", max_length=64, blank=True, default="")
    issue_date = models.DateField("报告出具日期", null=True, blank=True)
    remark = models.TextField("备注", blank=True, default="")

    class Meta:
        verbose_name = "特种设备检验"
        verbose_name_plural = "特种设备检验"
        ordering = ["-inspection_date", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "certificate_no"], name="uq_special_equipment_cert_company_no"
            )
        ]

    def __str__(self) -> str:
        return f"{self.certificate_no} {self.equipment_name or ''}".strip()


class EhsOperationLog(CompanyScopedModel):
    """安全环保操作日志：由服务层写入，只读展示。"""

    domain = models.CharField("业务域", max_length=24, choices=EhsDomain.choices, db_index=True)
    business_type = models.CharField("业务类型", max_length=64)
    business_label = models.CharField("业务对象", max_length=128, blank=True, default="")
    action = models.CharField("操作", max_length=32, db_index=True)
    operator = models.ForeignKey(
        "factory.Employee", verbose_name="操作人", null=True, blank=True,
        on_delete=models.PROTECT, related_name="+",
    )
    occurred_at = models.DateTimeField("操作时间", db_index=True)
    detail = models.TextField("操作说明", blank=True, default="")
    payload = models.JSONField("附加数据", default=dict, blank=True)

    class Meta:
        verbose_name = "安全环保操作日志"
        verbose_name_plural = "安全环保操作日志"
        ordering = ["-occurred_at", "-id"]
        indexes = [models.Index(fields=["company", "domain"], name="idx_ehs_log_domain")]

    def __str__(self) -> str:
        return f"{self.business_label or self.business_type} {self.action}"
