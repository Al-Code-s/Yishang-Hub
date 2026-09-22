"""安全环保业务服务。

三条真实的闭环流程（状态只能由服务层推进）：

* 隐患：待整改 → 整改中 → 待验收 → 已关闭（验收不通过退回整改中）；
* 事故：已上报 → 调查中 → 已整改 → 已关闭；
* 作业许可：待审批 → 已批准 → 作业中 → 已完工 → 已验收（可驳回）。

其余对象（制度、培训、预案、消防设施、排污监测、固废台账、合规检查、安全检查、
特种设备检验）继续沿用「登记 + 状态维护 + 操作日志」的轻量做法：它们是一次性事实
或周期台账，没有必须由服务强制的中间状态，硬造状态机反而会让录入变麻烦。
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from django.db import transaction

from apps.core.exceptions import StateConflict, ValidationFailed
from apps.core.services import business_now, generate_code
from apps.ehs.models import (
    AccidentRecord,
    AccidentStatus,
    ComplianceStatus,
    EhsDomain,
    EhsOperationLog,
    EnvironmentMonitor,
    HazardRecord,
    HazardStatus,
    PermitStatus,
    WorkPermit,
)

# 编码规则（在 bootstrap_system.CODE_RULES 中登记）
REGULATION_CODE_RULE = "SRG"
TRAINING_CODE_RULE = "TRN"
HAZARD_CODE_RULE = "HZD"
PLAN_CODE_RULE = "EPL"
ACCIDENT_CODE_RULE = "ACR"
MONITOR_CODE_RULE = "ENV"
WASTE_CODE_RULE = "WST"
COMPLIANCE_CODE_RULE = "CMP"
DRILL_CODE_RULE = "FDR"
FIRE_FACILITY_CODE_RULE = "FFC"
PERMIT_CODE_RULE = "WPR"
SAFETY_CHECK_CODE_RULE = "SCH"
SPECIAL_CERT_CODE_RULE = "SPI"


def _next(rule: str) -> str:
    return generate_code(rule)


def next_regulation_code() -> str:
    """安全制度编号。"""
    return _next(REGULATION_CODE_RULE)


def next_training_no() -> str:
    """安全培训编号。"""
    return _next(TRAINING_CODE_RULE)


def next_hazard_no() -> str:
    """隐患编号。"""
    return _next(HAZARD_CODE_RULE)


def next_plan_code() -> str:
    """应急预案编号。"""
    return _next(PLAN_CODE_RULE)


def next_accident_no() -> str:
    """事故编号。"""
    return _next(ACCIDENT_CODE_RULE)


def next_monitor_no() -> str:
    """排污监测编号。"""
    return _next(MONITOR_CODE_RULE)


def next_waste_no() -> str:
    """固废危废台账编号。"""
    return _next(WASTE_CODE_RULE)


def next_compliance_no() -> str:
    """环保合规检查编号。"""
    return _next(COMPLIANCE_CODE_RULE)


def next_drill_no() -> str:
    """消防演练编号。"""
    return _next(DRILL_CODE_RULE)


def next_fire_facility_code() -> str:
    """消防设施编号。"""
    return _next(FIRE_FACILITY_CODE_RULE)


def next_permit_no() -> str:
    """作业许可编号。"""
    return _next(PERMIT_CODE_RULE)


def next_safety_check_no() -> str:
    """安全检查编号。"""
    return _next(SAFETY_CHECK_CODE_RULE)


def next_special_cert_no() -> str:
    """特种设备检验报告编号。"""
    return _next(SPECIAL_CERT_CODE_RULE)


def log_operation(
    *,
    company_id: int,
    domain: str,
    business_type: str,
    action: str,
    business_label: str = "",
    operator: Any = None,
    detail: str = "",
    payload: dict[str, Any] | None = None,
) -> EhsOperationLog:
    """写一条安全环保操作日志（必须在业务事务内调用）。"""
    return EhsOperationLog.objects.create(
        company_id=company_id,
        domain=domain,
        business_type=business_type,
        business_label=business_label[:128],
        action=action,
        operator=operator,
        occurred_at=business_now(),
        detail=detail[:2000],
        payload=payload or {},
    )


# ---------------------------------------------------------------------------
# 隐患排查治理
# ---------------------------------------------------------------------------


@transaction.atomic
def start_hazard_rectify(
    hazard: HazardRecord, *, measure: str, operator: Any = None, rectified_by: Any = None
) -> HazardRecord:
    """开始整改：待整改 / 待验收（退回）→ 整改中。"""
    if hazard.status not in {HazardStatus.REPORTED, HazardStatus.VERIFYING}:
        if hazard.status == HazardStatus.RECTIFYING:
            raise StateConflict("该隐患已在整改中。", code="HAZARD_STATUS_INVALID")
        raise StateConflict("已关闭的隐患不能再次整改。", code="HAZARD_STATUS_INVALID")
    text = (measure or "").strip()
    if not text:
        raise ValidationFailed("开始整改必须填写整改措施。", code="HAZARD_MEASURE_REQUIRED")
    hazard.rectify_measure = text
    hazard.status = HazardStatus.RECTIFYING
    if rectified_by is not None:
        hazard.rectified_by = rectified_by
    hazard.save(update_fields=["rectify_measure", "status", "rectified_by", "updated_at"])
    log_operation(
        company_id=hazard.company_id,
        domain=EhsDomain.SAFETY,
        business_type="HazardRecord",
        business_label=hazard.hazard_no,
        action="rectify_start",
        operator=operator,
        detail=f"隐患 {hazard.hazard_no} 进入整改：{text}",
    )
    return hazard


@transaction.atomic
def submit_hazard_verify(
    hazard: HazardRecord, *, operator: Any = None, rectified_date: date | None = None
) -> HazardRecord:
    """提交验收：整改中 → 待验收。"""
    if hazard.status != HazardStatus.RECTIFYING:
        raise StateConflict("只有整改中的隐患可以提交验收。", code="HAZARD_STATUS_INVALID")
    hazard.status = HazardStatus.VERIFYING
    hazard.rectified_date = rectified_date or business_now().date()
    hazard.save(update_fields=["status", "rectified_date", "updated_at"])
    log_operation(
        company_id=hazard.company_id,
        domain=EhsDomain.SAFETY,
        business_type="HazardRecord",
        business_label=hazard.hazard_no,
        action="rectify_submit",
        operator=operator,
        detail=f"隐患 {hazard.hazard_no} 提交验收",
    )
    return hazard


@transaction.atomic
def verify_hazard(
    hazard: HazardRecord,
    *,
    result: str,
    passed: bool,
    operator: Any = None,
    verified_by: Any = None,
) -> HazardRecord:
    """验收隐患：通过则关闭，不通过退回「整改中」，避免不合格隐患被静默销账。"""
    if hazard.status != HazardStatus.VERIFYING:
        raise StateConflict("只有待验收的隐患可以验收。", code="HAZARD_STATUS_INVALID")
    text = (result or "").strip()
    if not text:
        raise ValidationFailed("验收必须填写验收结论。", code="HAZARD_VERIFY_REQUIRED")
    hazard.verify_result = text
    hazard.verified_date = business_now().date()
    if verified_by is not None:
        hazard.verified_by = verified_by
    hazard.status = HazardStatus.CLOSED if passed else HazardStatus.RECTIFYING
    hazard.save(
        update_fields=["verify_result", "verified_date", "verified_by", "status", "updated_at"]
    )
    log_operation(
        company_id=hazard.company_id,
        domain=EhsDomain.SAFETY,
        business_type="HazardRecord",
        business_label=hazard.hazard_no,
        action="verify",
        operator=operator,
        detail=f"隐患 {hazard.hazard_no} 验收{'通过' if passed else '不通过'}：{text}",
        payload={"passed": passed},
    )
    return hazard


# ---------------------------------------------------------------------------
# 事故处理
# ---------------------------------------------------------------------------


@transaction.atomic
def start_accident_investigation(
    accident: AccidentRecord, *, investigator: Any = None, operator: Any = None
) -> AccidentRecord:
    """启动事故调查：已上报 → 调查中。"""
    if accident.status != AccidentStatus.REPORTED:
        raise StateConflict("只有已上报的事故可以启动调查。", code="ACCIDENT_STATUS_INVALID")
    accident.status = AccidentStatus.INVESTIGATING
    if investigator is not None:
        accident.investigator = investigator
    accident.save(update_fields=["status", "investigator", "updated_at"])
    log_operation(
        company_id=accident.company_id,
        domain=EhsDomain.SAFETY,
        business_type="AccidentRecord",
        business_label=accident.accident_no,
        action="investigate_start",
        operator=operator,
        detail=f"事故 {accident.accident_no} 进入调查",
    )
    return accident


@transaction.atomic
def rectify_accident(
    accident: AccidentRecord, *, measures: str, causes: str = "", operator: Any = None
) -> AccidentRecord:
    """登记整改与预防措施：调查中 → 已整改。"""
    if accident.status != AccidentStatus.INVESTIGATING:
        raise StateConflict("只有调查中的事故可以登记整改。", code="ACCIDENT_STATUS_INVALID")
    text = (measures or "").strip()
    if not text:
        raise ValidationFailed("登记整改必须填写整改措施。", code="ACCIDENT_MEASURE_REQUIRED")
    accident.measures = text
    if causes:
        accident.causes = causes
    accident.status = AccidentStatus.RECTIFIED
    accident.save(update_fields=["measures", "causes", "status", "updated_at"])
    log_operation(
        company_id=accident.company_id,
        domain=EhsDomain.SAFETY,
        business_type="AccidentRecord",
        business_label=accident.accident_no,
        action="rectify",
        operator=operator,
        detail=f"事故 {accident.accident_no} 完成整改：{text}",
    )
    return accident


@transaction.atomic
def close_accident(
    accident: AccidentRecord, *, result: str, operator: Any = None, closed_date: date | None = None
) -> AccidentRecord:
    """关闭事故：已整改 → 已关闭，必须填写调查结论。"""
    if accident.status != AccidentStatus.RECTIFIED:
        raise StateConflict("只有已整改的事故可以关闭。", code="ACCIDENT_STATUS_INVALID")
    text = (result or accident.investigation_result or "").strip()
    if not text:
        raise ValidationFailed("关闭事故必须填写调查结论。", code="ACCIDENT_RESULT_REQUIRED")
    accident.investigation_result = text
    accident.status = AccidentStatus.CLOSED
    accident.closed_date = closed_date or business_now().date()
    accident.save(update_fields=["investigation_result", "status", "closed_date", "updated_at"])
    log_operation(
        company_id=accident.company_id,
        domain=EhsDomain.SAFETY,
        business_type="AccidentRecord",
        business_label=accident.accident_no,
        action="close",
        operator=operator,
        detail=f"事故 {accident.accident_no} 关闭：{text}",
    )
    return accident


# ---------------------------------------------------------------------------
# 作业许可（动火 / 检维修 / 防爆防静电 / 受限空间）
# ---------------------------------------------------------------------------


@transaction.atomic
def approve_permit(
    permit: WorkPermit, *, approver: Any = None, guardian: Any = None, note: str = ""
) -> WorkPermit:
    """批准作业许可：待审批 → 已批准。"""
    if permit.status != PermitStatus.APPLIED:
        raise StateConflict("只有待审批的作业许可可以批准。", code="PERMIT_STATUS_INVALID")
    if permit.permit_type in {"hot_work", "explosion_proof", "confined_space"} and guardian is None:
        # 动火、防爆防静电、受限空间作业必须有监护人（安全硬要求）
        raise ValidationFailed("该类作业必须指定监护人。", code="PERMIT_GUARDIAN_REQUIRED")
    permit.status = PermitStatus.APPROVED
    if approver is not None:
        permit.approver = approver
    if guardian is not None:
        permit.guardian = guardian
    if note:
        permit.result = note
    permit.approved_at = business_now()
    permit.save(
        update_fields=["status", "approver", "guardian", "result", "approved_at", "updated_at"]
    )
    log_operation(
        company_id=permit.company_id,
        domain=_permit_domain(permit),
        business_type="WorkPermit",
        business_label=permit.permit_no,
        action="approve",
        operator=approver,
        detail=f"{permit.get_permit_type_display()} {permit.permit_no} 已批准",
    )
    return permit


@transaction.atomic
def reject_permit(permit: WorkPermit, *, reason: str, approver: Any = None) -> WorkPermit:
    """驳回作业许可：待审批 → 已驳回，必须写明理由。"""
    if permit.status != PermitStatus.APPLIED:
        raise StateConflict("只有待审批的作业许可可以驳回。", code="PERMIT_STATUS_INVALID")
    text = (reason or "").strip()
    if not text:
        raise ValidationFailed("驳回作业许可必须填写理由。", code="PERMIT_REASON_REQUIRED")
    permit.status = PermitStatus.REJECTED
    if approver is not None:
        permit.approver = approver
    permit.approved_at = business_now()
    permit.result = text
    permit.save(update_fields=["status", "approver", "approved_at", "result", "updated_at"])
    log_operation(
        company_id=permit.company_id,
        domain=_permit_domain(permit),
        business_type="WorkPermit",
        business_label=permit.permit_no,
        action="reject",
        operator=approver,
        detail=f"{permit.get_permit_type_display()} {permit.permit_no} 被驳回：{text}",
    )
    return permit


@transaction.atomic
def start_permit_work(permit: WorkPermit, *, operator: Any = None) -> WorkPermit:
    """开始作业：已批准 → 作业中。"""
    if permit.status != PermitStatus.APPROVED:
        raise StateConflict("只有已批准的作业许可可以开始作业。", code="PERMIT_STATUS_INVALID")
    permit.status = PermitStatus.WORKING
    permit.started_at = business_now()
    permit.save(update_fields=["status", "started_at", "updated_at"])
    log_operation(
        company_id=permit.company_id,
        domain=_permit_domain(permit),
        business_type="WorkPermit",
        business_label=permit.permit_no,
        action="start",
        operator=operator,
        detail=f"{permit.get_permit_type_display()} {permit.permit_no} 开始作业",
    )
    return permit


@transaction.atomic
def finish_permit_work(permit: WorkPermit, *, result: str = "", operator: Any = None) -> WorkPermit:
    """完工：作业中 → 已完工。"""
    if permit.status != PermitStatus.WORKING:
        raise StateConflict("只有作业中的许可可以完工。", code="PERMIT_STATUS_INVALID")
    permit.status = PermitStatus.FINISHED
    permit.finished_at = business_now()
    if result:
        permit.result = result
    permit.save(update_fields=["status", "finished_at", "result", "updated_at"])
    log_operation(
        company_id=permit.company_id,
        domain=_permit_domain(permit),
        business_type="WorkPermit",
        business_label=permit.permit_no,
        action="finish",
        operator=operator,
        detail=f"{permit.get_permit_type_display()} {permit.permit_no} 完工",
    )
    return permit


@transaction.atomic
def accept_permit(
    permit: WorkPermit, *, result: str, accepted_by: Any = None, operator: Any = None
) -> WorkPermit:
    """现场验收：已完工 → 已验收，必须填写验收结论。"""
    if permit.status != PermitStatus.FINISHED:
        raise StateConflict("只有已完工的许可可以验收。", code="PERMIT_STATUS_INVALID")
    text = (result or "").strip()
    if not text:
        raise ValidationFailed("验收作业许可必须填写结论。", code="PERMIT_RESULT_REQUIRED")
    permit.status = PermitStatus.ACCEPTED
    permit.result = text
    if accepted_by is not None:
        permit.accepted_by = accepted_by
    permit.accepted_at = business_now()
    permit.save(update_fields=["status", "result", "accepted_by", "accepted_at", "updated_at"])
    log_operation(
        company_id=permit.company_id,
        domain=_permit_domain(permit),
        business_type="WorkPermit",
        business_label=permit.permit_no,
        action="accept",
        operator=operator or accepted_by,
        detail=f"{permit.get_permit_type_display()} {permit.permit_no} 验收：{text}",
    )
    return permit


def _permit_domain(permit: WorkPermit) -> str:
    """作业许可归属业务域：动火属于消防管理，其余属于设备设施安全。"""
    if permit.permit_type == "hot_work":
        return EhsDomain.FIRE
    return EhsDomain.EQUIPMENT_SAFETY


# ---------------------------------------------------------------------------
# 环保监测合规判定
# ---------------------------------------------------------------------------


def apply_monitor_compliance(monitor: EnvironmentMonitor) -> EnvironmentMonitor:
    """按「实测值 vs 排放限值」自动判定是否达标（没有限值时保留录入值）。"""
    if monitor.limit_value is None or monitor.measured_value is None:
        return monitor
    compliant = Decimal(monitor.measured_value) <= Decimal(monitor.limit_value)
    if compliant != monitor.is_compliant:
        monitor.is_compliant = compliant
        monitor.save(update_fields=["is_compliant", "updated_at"])
    return monitor


def close_compliance_check(
    check: Any, *, operator: Any = None, rectified_date: date | None = None
) -> Any:
    """关闭环保合规检查：待整改 / 已整改 → 已关闭。"""
    if check.status == ComplianceStatus.CLOSED:
        raise StateConflict("该检查已关闭，无需重复关闭。", code="COMPLIANCE_STATUS_INVALID")
    check.status = ComplianceStatus.CLOSED
    check.rectified_date = rectified_date or check.rectified_date or business_now().date()
    check.save(update_fields=["status", "rectified_date", "updated_at"])
    log_operation(
        company_id=check.company_id,
        domain=EhsDomain.ENVIRONMENT,
        business_type="ComplianceCheck",
        business_label=check.check_no,
        action="close",
        operator=operator,
        detail=f"环保合规检查 {check.check_no} 已关闭",
    )
    return check
