"""生产物流服务：任务状态机 + 操作日志。

任务流转（非法跃迁一律拒绝，不能靠 PATCH 跳步）::

    pending --dispatch--> dispatched --start--> executing --finish--> finished
       \\___________________ cancel ___________________/

设备侧联动：开始执行把设备置为「作业中」，完成/取消把设备恢复为「空闲」；
设备状态变化同样写操作日志，保证设备状态变化可追溯到人和时间。
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.db import transaction

from apps.core.exceptions import StateConflict, ValidationFailed
from apps.core.services import business_now, generate_code
from apps.logistics.models import (
    AutomationDevice,
    AutomationDeviceStatus,
    LogisticsLogAction,
    LogisticsOperationLog,
    LogisticsTask,
    LogisticsTaskStatus,
)

DEVICE_CODE_RULE = "AD"
TASK_CODE_RULE = "LT"


def next_device_code() -> str:
    """自动化设备编号（编码规则 AD）。"""
    return generate_code(DEVICE_CODE_RULE)


def next_task_no() -> str:
    """物流任务编号（编码规则 LT）。"""
    return generate_code(TASK_CODE_RULE)


def log_operation(
    *,
    company_id: int,
    action: str,
    device: AutomationDevice | None = None,
    task: LogisticsTask | None = None,
    operator: Any = None,
    detail: str = "",
    payload: dict[str, Any] | None = None,
) -> LogisticsOperationLog:
    """写一条操作日志。必须在业务事务内调用（与状态变更同生共死）。"""
    return LogisticsOperationLog.objects.create(
        company_id=company_id,
        device=device,
        task=task,
        action=action,
        operator=operator,
        occurred_at=business_now(),
        detail=detail[:2000],
        payload=payload or {},
    )


@transaction.atomic
def dispatch_task(
    task: LogisticsTask, *, assignee: Any = None, device: AutomationDevice | None = None,
    planned_at=None,
) -> LogisticsTask:
    """下发任务：待下发 → 已下发。"""
    if task.status != LogisticsTaskStatus.PENDING:
        raise StateConflict("只有待下发的任务可以下发。", code="TASK_STATUS_INVALID")
    target_device = device or task.device
    if target_device is None and assignee is None:
        raise ValidationFailed("下发任务必须指定执行设备或执行人。", code="TASK_ASSIGNEE_REQUIRED")
    if target_device is not None:
        if target_device.status in {
            AutomationDeviceStatus.FAULT,
            AutomationDeviceStatus.OFFLINE,
            AutomationDeviceStatus.MAINTENANCE,
        }:
            raise StateConflict(
                f"设备 {target_device.name} 当前状态为「{target_device.get_status_display()}」，不能下发任务。",
                code="DEVICE_NOT_AVAILABLE",
            )
        busy = LogisticsTask.objects.filter(
            device=target_device, status=LogisticsTaskStatus.EXECUTING
        ).exclude(pk=task.pk)
        if busy.exists():
            raise StateConflict("该设备已有执行中的任务，不能重复下发。", code="DEVICE_BUSY")
        task.device = target_device
    if assignee is not None:
        task.assignee = assignee
    if planned_at is not None:
        task.planned_at = planned_at
    task.status = LogisticsTaskStatus.DISPATCHED
    task.dispatched_at = business_now()
    task.save(update_fields=["device", "assignee", "planned_at", "status", "dispatched_at", "updated_at"])
    log_operation(
        company_id=task.company_id,
        action=LogisticsLogAction.DISPATCH,
        device=task.device,
        task=task,
        operator=assignee,
        detail=f"下发任务 {task.task_no}",
    )
    return task


@transaction.atomic
def start_task(task: LogisticsTask, *, operator: Any = None) -> LogisticsTask:
    """开始执行：已下发 → 执行中，设备置为「作业中」。"""
    if task.status != LogisticsTaskStatus.DISPATCHED:
        raise StateConflict("只有已下发的任务可以开始执行。", code="TASK_STATUS_INVALID")
    task.status = LogisticsTaskStatus.EXECUTING
    task.started_at = business_now()
    task.save(update_fields=["status", "started_at", "updated_at"])
    if task.device is not None:
        set_device_status(task.device, AutomationDeviceStatus.RUNNING, operator=operator, detail=f"任务 {task.task_no} 开始执行")
    log_operation(
        company_id=task.company_id,
        action=LogisticsLogAction.START,
        device=task.device,
        task=task,
        operator=operator or task.assignee,
        detail=f"开始执行任务 {task.task_no}",
    )
    return task


@transaction.atomic
def finish_task(
    task: LogisticsTask,
    *,
    result: str = "",
    quantity: Decimal | None = None,
    to_location: Any = None,
    operator: Any = None,
) -> LogisticsTask:
    """完成执行：执行中 → 已完成，设备恢复空闲。"""
    if task.status != LogisticsTaskStatus.EXECUTING:
        raise StateConflict("只有执行中的任务可以完成。", code="TASK_STATUS_INVALID")
    if quantity is not None:
        value = Decimal(quantity)
        if value < 0:
            raise ValidationFailed("完成数量不能为负数。", code="TASK_QUANTITY_NEGATIVE")
        task.quantity = value
    if to_location is not None:
        task.to_location = to_location
    task.status = LogisticsTaskStatus.FINISHED
    task.finished_at = business_now()
    if result:
        task.result = result
    if task.started_at is None:
        task.started_at = task.finished_at
    task.save(
        update_fields=["quantity", "to_location", "status", "finished_at", "result", "started_at", "updated_at"]
    )
    if task.device is not None:
        set_device_status(task.device, AutomationDeviceStatus.IDLE, operator=operator, detail=f"任务 {task.task_no} 已完成")
    log_operation(
        company_id=task.company_id,
        action=LogisticsLogAction.FINISH,
        device=task.device,
        task=task,
        operator=operator or task.assignee,
        detail=f"完成任务 {task.task_no}" + (f"：{result}" if result else ""),
    )
    return task


@transaction.atomic
def cancel_task(task: LogisticsTask, *, reason: str, operator: Any = None) -> LogisticsTask:
    """取消任务：未结束的任务可以取消，必须写明原因。"""
    if task.status not in LogisticsTaskStatus.open_states():
        raise StateConflict("已结束的任务不能取消。", code="TASK_STATUS_INVALID")
    text = (reason or "").strip()
    if not text:
        raise ValidationFailed("取消任务必须填写原因。", code="TASK_REASON_REQUIRED")
    was_executing = task.status == LogisticsTaskStatus.EXECUTING
    task.status = LogisticsTaskStatus.CANCELLED
    task.finished_at = business_now()
    task.remark = f"{task.remark}\n取消原因：{text}".strip()
    task.save(update_fields=["status", "finished_at", "remark", "updated_at"])
    if was_executing and task.device is not None:
        set_device_status(task.device, AutomationDeviceStatus.IDLE, operator=operator, detail=f"任务 {task.task_no} 已取消")
    log_operation(
        company_id=task.company_id,
        action=LogisticsLogAction.CANCEL,
        device=task.device,
        task=task,
        operator=operator,
        detail=f"取消任务 {task.task_no}：{text}",
    )
    return task


@transaction.atomic
def set_device_status(
    device: AutomationDevice,
    status: str,
    *,
    operator: Any = None,
    detail: str = "",
    battery_level: int | None = None,
) -> AutomationDevice:
    """变更设备状态（故障 / 充电 / 保养 / 空闲 …），并留下操作日志。"""
    if status not in AutomationDeviceStatus.values:
        raise ValidationFailed(f"不支持的设备状态：{status}", code="DEVICE_STATUS_INVALID")
    if battery_level is not None:
        if battery_level < 0 or battery_level > 100:
            raise ValidationFailed("电量必须在 0 到 100 之间。", code="BATTERY_LEVEL_INVALID")
        device.battery_level = battery_level
    previous = device.status
    device.status = status
    fields = ["status", "updated_at"]
    if battery_level is not None:
        fields.append("battery_level")
    device.save(update_fields=fields)
    log_operation(
        company_id=device.company_id,
        action=LogisticsLogAction.STATUS_CHANGE,
        device=device,
        operator=operator,
        detail=detail or f"设备状态由「{previous}」变更为「{status}」",
        payload={"previous_status": previous, "status": status},
    )
    return device
