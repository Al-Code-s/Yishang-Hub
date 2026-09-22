"""设备模块的领域规则。

设备编号与备件编号统一走 `core.services.generate_code`（按编码规则表取号），
规则本体登记在 `bootstrap_system.CODE_RULES`，可在「系统管理 → 编码规则」调整，
这里**不硬编码格式**，避免出现「改了规则却不生效」的两套口径。
"""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

from django.utils import timezone

from apps.core.exceptions import StateConflict, ValidationFailed
from apps.core.services import business_today, generate_code
from apps.equipment.models import (
    AbnormalRecord,
    AbnormalStatus,
    AbnormalTask,
    FaultLevel,
    FaultReport,
    FaultReportStatus,
    InspectionRecord,
    MaintenancePlan,
    MaintenanceRecord,
    MaintenanceTask,
    RepairRecord,
    RepairTask,
    TaskStatus,
)

EQUIPMENT_CODE_RULE = "EQ"
SPARE_PART_CODE_RULE = "SP"


def next_equipment_code() -> str:
    """按编码规则取下一个设备编号。"""
    return generate_code(EQUIPMENT_CODE_RULE)


def next_spare_part_code() -> str:
    """按编码规则取下一个备件编号。"""
    return generate_code(SPARE_PART_CODE_RULE)


MAINTENANCE_PLAN_CODE_RULE = "MP"
MAINTENANCE_TASK_CODE_RULE = "MT"
MAINTENANCE_RECORD_CODE_RULE = "MR"
FAULT_REPORT_CODE_RULE = "FR"
REPAIR_TASK_CODE_RULE = "RT"
REPAIR_RECORD_CODE_RULE = "RR"
INSPECTION_TASK_CODE_RULE = "IT"
INSPECTION_RECORD_CODE_RULE = "IR"
ABNORMAL_TASK_CODE_RULE = "AT"
ABNORMAL_RECORD_CODE_RULE = "AR"

#: 单次「生成保养任务」最多补生成的条数。
#:
#: 计划长期未维护时（例如停用一年后重启），按周期逐条补齐可能一次生成上百条任务；
#: 这里设上限并在返回结果里告知实际生成条数，避免一次请求把库打满。
MAX_TASKS_PER_GENERATION = 60


def next_maintenance_plan_no() -> str:
    """按编码规则取下一个保养计划编号。"""
    return generate_code(MAINTENANCE_PLAN_CODE_RULE)


def next_maintenance_task_no() -> str:
    return generate_code(MAINTENANCE_TASK_CODE_RULE)


def next_maintenance_record_no() -> str:
    return generate_code(MAINTENANCE_RECORD_CODE_RULE)


def next_fault_report_no() -> str:
    return generate_code(FAULT_REPORT_CODE_RULE)


def next_repair_task_no() -> str:
    return generate_code(REPAIR_TASK_CODE_RULE)


def next_repair_record_no() -> str:
    return generate_code(REPAIR_RECORD_CODE_RULE)


def next_inspection_task_no() -> str:
    return generate_code(INSPECTION_TASK_CODE_RULE)


def next_inspection_record_no() -> str:
    return generate_code(INSPECTION_RECORD_CODE_RULE)


def next_abnormal_task_no() -> str:
    return generate_code(ABNORMAL_TASK_CODE_RULE)


def next_abnormal_record_no() -> str:
    return generate_code(ABNORMAL_RECORD_CODE_RULE)


def _save(instance, fields: tuple[str, ...]) -> None:
    """按指定字段保存，并同步 BaseModel 的版本号与更新人。"""
    instance.save(update_fields=[*fields, "updated_at", "updated_by", "version"])


# ---------------------------------------------------------------------------
# 保养计划 → 保养任务
# ---------------------------------------------------------------------------


def generate_maintenance_tasks(
    plan: MaintenancePlan, *, until_date=None, assignee=None
) -> list[MaintenanceTask]:
    """按计划周期补生成到期（含已过期）的保养任务。

    规则：
    * 从计划的「下次保养日期」起逐周期推进，直到 ``until_date``（默认今天）；
    * 同一计划同一天只生成一条任务，重复调用不会重复生成（唯一约束 + 先查后建）；
    * 一次最多生成 ``MAX_TASKS_PER_GENERATION`` 条，剩余部分由下次调用继续补；
    * 计划的下次保养日期随之推进，保证「点一次生成就等于把账做平」。
    """
    if plan.cycle_days <= 0:
        raise ValidationFailed("保养周期必须大于 0 天。", code="INVALID_MAINTENANCE_CYCLE")
    limit = until_date or business_today()
    cursor = plan.next_date
    if cursor is None:
        return []

    existing = set(
        MaintenanceTask.objects.filter(plan=plan).values_list("plan_date", flat=True)
    )
    created: list[MaintenanceTask] = []
    while cursor <= limit and len(created) < MAX_TASKS_PER_GENERATION:
        if cursor not in existing:
            created.append(
                MaintenanceTask.objects.create(
                    company=plan.company,
                    plan=plan,
                    equipment=plan.equipment,
                    plan_date=cursor,
                    assignee=assignee if assignee is not None else plan.responsible_employee,
                    task_no=next_maintenance_task_no(),
                )
            )
            existing.add(cursor)
        cursor = cursor + timedelta(days=plan.cycle_days)

    if cursor != plan.next_date:
        plan.next_date = cursor
        _save(plan, ("next_date",))
    return created


# ---------------------------------------------------------------------------
# 任务状态流转
# ---------------------------------------------------------------------------


def start_equipment_task(task, *, timestamp: datetime | None = None) -> None:
    """把任务从「待执行」推进到「进行中」。已在进行中时保持幂等。"""
    if task.status == TaskStatus.IN_PROGRESS:
        return
    if task.status != TaskStatus.PENDING:
        raise StateConflict(
            "只有「待执行」的任务可以开始。",
            code="TASK_NOT_STARTABLE",
            details={"status": task.status},
        )
    task.status = TaskStatus.IN_PROGRESS
    task.started_at = timestamp or timezone.now()
    _save(task, ("status", "started_at"))


def cancel_equipment_task(task, *, reason: str = "") -> None:
    """取消任务。已完成 / 已取消的任务不允许再取消。"""
    if task.status == TaskStatus.CANCELLED:
        return
    if task.status == TaskStatus.COMPLETED:
        raise StateConflict("已完成的任务不能取消。", code="TASK_NOT_CANCELLABLE")
    task.status = TaskStatus.CANCELLED
    if reason:
        task.remark = f"{task.remark}\n取消原因：{reason}".strip()
    _save(task, ("status", "remark"))


def _finish(task, *, timestamp: datetime | None = None) -> None:
    task.status = TaskStatus.COMPLETED
    task.finished_at = timestamp or timezone.now()


def complete_maintenance_task(
    task: MaintenanceTask,
    *,
    executor=None,
    content: str = "",
    result: str = "",
    is_qualified: bool = True,
    cost: Decimal | None = None,
    maintain_date=None,
) -> MaintenanceRecord:
    """完成保养任务并生成保养记录（任务与记录同事务写入）。"""
    if task.status == TaskStatus.CANCELLED:
        raise StateConflict("已取消的任务不能完成。", code="TASK_NOT_COMPLETABLE")
    _finish(task)
    task.result = result or task.result
    _save(task, ("status", "finished_at", "result"))
    return MaintenanceRecord.objects.create(
        company=task.company,
        task=task,
        equipment=task.equipment,
        item=task.item,
        maintain_date=maintain_date or business_today(),
        executor=executor if executor is not None else task.assignee,
        content=content,
        result=result,
        is_qualified=is_qualified,
        cost=cost if cost is not None else Decimal("0"),
        record_no=next_maintenance_record_no(),
    )


def complete_repair_task(
    task: RepairTask,
    *,
    repairer=None,
    fault_reason: str = "",
    solution: str = "",
    parts_used: str = "",
    cost: Decimal | None = None,
    downtime_minutes: int | None = None,
    result: str = "",
    repair_date=None,
) -> RepairRecord:
    """完成维修任务、生成维修记录，并同步关闭来源故障保修单。"""
    if task.status == TaskStatus.CANCELLED:
        raise StateConflict("已取消的任务不能完成。", code="TASK_NOT_COMPLETABLE")
    _finish(task)
    minutes = task.downtime_minutes if downtime_minutes is None else downtime_minutes
    task.downtime_minutes = minutes
    _save(task, ("status", "finished_at", "downtime_minutes"))

    record = RepairRecord.objects.create(
        company=task.company,
        task=task,
        equipment=task.equipment,
        repair_date=repair_date or business_today(),
        repairer=repairer if repairer is not None else task.assignee,
        fault_reason=fault_reason,
        solution=solution,
        parts_used=parts_used,
        cost=cost if cost is not None else Decimal("0"),
        downtime_minutes=minutes,
        result=result,
        record_no=next_repair_record_no(),
    )
    if task.fault_report_id:
        close_fault_report(task.fault_report)
    return record


def close_fault_report(report: FaultReport) -> FaultReport:
    """关闭保修单。维修任务结束时调用，重复调用不改变已关闭的关闭时间。"""
    if report.status == FaultReportStatus.CLOSED:
        return report
    report.status = FaultReportStatus.CLOSED
    report.closed_at = timezone.now()
    _save(report, ("status", "closed_at"))
    return report


def sync_fault_report_progress(report: FaultReport, task: RepairTask) -> FaultReport:
    """按维修任务进度回写保修单状态：派工 → 已派工，开工 → 维修中。"""
    if report.status in (FaultReportStatus.CLOSED, FaultReportStatus.CANCELLED):
        return report
    target = (
        FaultReportStatus.REPAIRING
        if task.status == TaskStatus.IN_PROGRESS
        else FaultReportStatus.ASSIGNED
    )
    if report.status != target:
        report.status = target
        _save(report, ("status",))
    return report


def raise_fault_report(
    *,
    equipment,
    description: str,
    level: str = FaultLevel.MEDIUM,
    reporter=None,
    company=None,
    remark: str = "",
) -> FaultReport:
    """登记故障保修单。点巡检异常转报修也走这里，保证单号与字段口径一致。"""
    return FaultReport.objects.create(
        company=company or equipment.company,
        equipment=equipment,
        level=level,
        description=description,
        reporter=reporter,
        report_no=next_fault_report_no(),
        remark=remark,
    )


def raise_fault_from_inspection(
    record: InspectionRecord, *, level: str = FaultLevel.MEDIUM, reporter=None
) -> FaultReport:
    """点巡检记录判定异常后一键转报修。

    描述由「设备 + 项目 + 实测值 + 异常描述」拼成，避免报修单里只有一句「有异常」，
    维修人员无法判断现场情况。
    """
    item_name = record.item.name if record.item_id else "点巡检项目"
    parts = [f"{record.equipment.name} 点巡检发现异常：{item_name}"]
    if record.measured_value is not None:
        parts.append(f"实测值 {record.measured_value}")
    if record.abnormal_desc:
        parts.append(record.abnormal_desc)
    return raise_fault_report(
        equipment=record.equipment,
        description="；".join(parts),
        level=level,
        reporter=reporter if reporter is not None else record.inspector,
        company=record.company,
        remark=f"来源点巡检记录：{record.record_no}",
    )


def assign_abnormal_task(task: AbnormalTask, *, handler, deadline=None) -> AbnormalTask:
    """分派异常任务。"""
    if task.status in (AbnormalStatus.CLOSED, AbnormalStatus.CANCELLED):
        raise StateConflict("已关闭或已取消的异常任务不能分派。", code="ABNORMAL_NOT_ASSIGNABLE")
    task.handler = handler
    task.deadline = deadline if deadline is not None else task.deadline
    task.status = AbnormalStatus.ASSIGNED
    _save(task, ("handler", "deadline", "status"))
    return task


def start_abnormal_handling(task: AbnormalTask, *, action: str = "") -> AbnormalTask:
    if task.status in (AbnormalStatus.CLOSED, AbnormalStatus.CANCELLED):
        raise StateConflict("已关闭或已取消的异常任务不能处理。", code="ABNORMAL_NOT_HANDLEABLE")
    if action:
        task.handling = action
    task.status = AbnormalStatus.HANDLING
    _save(task, ("handling", "status"))
    return task


def close_abnormal_task(
    task: AbnormalTask, *, action: str = "", result: str = "", handle_date=None, handler=None
) -> AbnormalRecord:
    """关闭异常任务并生成异常记录。"""
    if task.status == AbnormalStatus.CLOSED:
        raise StateConflict("该异常任务已关闭。", code="ABNORMAL_ALREADY_CLOSED")
    if task.status == AbnormalStatus.CANCELLED:
        raise StateConflict("已取消的异常任务不能关闭。", code="ABNORMAL_NOT_CLOSABLE")
    if action:
        task.handling = action
    if handler is not None:
        task.handler = handler
    task.status = AbnormalStatus.CLOSED
    task.closed_at = timezone.now()
    _save(task, ("handling", "handler", "status", "closed_at"))
    return AbnormalRecord.objects.create(
        company=task.company,
        task=task,
        abnormal_type=task.abnormal_type,
        equipment=task.equipment,
        handle_date=handle_date or business_today(),
        handler=task.handler,
        action=action or task.handling,
        result=result,
        record_no=next_abnormal_record_no(),
    )
def finish_equipment_task(task, *, result: str = "", timestamp: datetime | None = None) -> None:
    """结束任务但不生成记录。

    点巡检任务走这条路径：一次巡检要检查多个项目，记录是**逐项登记**的，
    一次性生成一条汇总记录反而会让「本项检了什么、数值多少」丢失。
    """
    if task.status == TaskStatus.CANCELLED:
        raise StateConflict("已取消的任务不能完成。", code="TASK_NOT_COMPLETABLE")
    _finish(task, timestamp=timestamp)
    if result:
        task.result = result
    _save(task, ("status", "finished_at", "result"))


def create_repair_task_from_report(
    report: FaultReport,
    *,
    assignee=None,
    level: str | None = None,
    symptom: str = "",
    assigned_date=None,
    remark: str = "",
) -> RepairTask:
    """故障保修单派工：生成维修任务并把保修单推进到「已派工」。"""
    if report.status in (FaultReportStatus.CLOSED, FaultReportStatus.CANCELLED):
        raise StateConflict(
            "已关闭或已取消的保修单不能派工。",
            code="FAULT_REPORT_NOT_DISPATCHABLE",
            details={"status": report.status},
        )
    task = RepairTask.objects.create(
        company=report.company,
        fault_report=report,
        equipment=report.equipment,
        symptom=symptom or report.description,
        level=level or report.level,
        assignee=assignee,
        assigned_date=assigned_date or business_today(),
        task_no=next_repair_task_no(),
        remark=remark,
    )
    if report.status != FaultReportStatus.ASSIGNED:
        report.status = FaultReportStatus.ASSIGNED
        _save(report, ("status",))
    return task
