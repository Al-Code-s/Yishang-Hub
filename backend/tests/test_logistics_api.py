"""生产物流接口用例（自动化设备台账 / 任务状态机 / 操作日志）。

覆盖要点：
* 数据范围在设备与任务上一致生效，越权对象按「不存在」处理；
* 设备编号（AD）与任务编号（LT）留空时按编码规则自动取号；
* 任务只能按「待下发 → 已下发 → 执行中 → 已完成」推进，跳步 / 逆序一律 409；
* 故障或保养中的设备不能被下发任务，同一设备不能同时有两个执行中任务；
* 开始执行把设备置为「作业中」，完成 / 取消把设备恢复「空闲」；
* 取消任务必须写明原因；
* 每一次状态流转都写操作日志，日志接口只读；
* 直接 PATCH 任务状态不会生效。

全部走 HTTP 接口与真实 MySQL 约束，不使用 mock。
"""

from __future__ import annotations

import re

import pytest

from apps.core.models import CodeRule, ResetPeriod
from apps.core.services import business_today
from apps.identity.models import DataScopeType
from apps.logistics.models import (
    AutomationDevice,
    AutomationDeviceStatus,
    LogisticsOperationLog,
    LogisticsTask,
    LogisticsTaskStatus,
)
from tests.conftest import make_role, make_user

pytestmark = pytest.mark.django_db

BASE = "/api/v1/logistics"
DEVICES_URL = BASE + "/automation-devices/"
TASKS_URL = BASE + "/tasks/"
LOGS_URL = BASE + "/operation-logs/"
LOGIN_URL = "/api/v1/identity/auth/login/"
PASSWORD = "Tst!Passw0rd2026"


def login(client, user) -> None:
    response = client.post(
        LOGIN_URL, {"username": user.username, "password": PASSWORD}, format="json"
    )
    assert response.status_code == 200, response.content


def logistics_codes(registry_permissions) -> list[str]:
    return sorted(code for code in registry_permissions if code.startswith("logistics."))


@pytest.fixture
def logistics_code_rules(db):
    """取号依赖编码规则；测试库不跑 bootstrap_system，这里显式登记物流模块的规则。"""
    rules = {
        "AD": ("AD{YYYY}{SEQ:4}", ResetPeriod.YEARLY),
        "LT": ("LT{YYYYMMDD}{SEQ:4}", ResetPeriod.DAILY),
    }
    for code, (pattern, period) in rules.items():
        CodeRule.objects.update_or_create(
            code=code,
            defaults={"name": code, "pattern": pattern, "reset_period": period, "is_active": True},
        )


@pytest.fixture
def logistics_admin(api_client, registry_permissions, company):
    role = make_role(
        code="test_logistics_admin",
        permission_codes=logistics_codes(registry_permissions),
        data_scope_type=DataScopeType.COMPANY,
        company=company,
    )
    user = make_user(username="lg_admin_t", role=role, company=company)
    login(api_client, user)
    return api_client


@pytest.fixture
def logistics_viewer(api_client, registry_permissions, company):
    role = make_role(
        code="test_logistics_viewer",
        permission_codes=[
            code for code in logistics_codes(registry_permissions) if code.endswith(".view")
        ],
        data_scope_type=DataScopeType.COMPANY,
        company=company,
    )
    user = make_user(username="lg_viewer_t", role=role, company=company)
    login(api_client, user)
    return api_client


@pytest.fixture
def device(company):
    return AutomationDevice.objects.create(
        company=company, code="AD-T001", name="一号 AGV", device_type="agv"
    )


def create_task(client, company, **extra):
    return client.post(
        TASKS_URL, {"company_id": company.pk, "task_type": "move", **extra}, format="json"
    )


def test_unauthenticated_logistics_access_is_denied(api_client):
    assert api_client.get(DEVICES_URL).status_code in (401, 403)


def test_device_and_task_lists_are_company_scoped(
    logistics_admin, company, other_company, device
):
    foreign = AutomationDevice.objects.create(
        company=other_company, code="AD-OTH", name="对照 AGV", device_type="agv"
    )
    LogisticsTask.objects.create(company=company, task_no="LT-T001", task_type="move")
    LogisticsTask.objects.create(company=other_company, task_no="LT-OTH", task_type="move")

    devices = logistics_admin.get(DEVICES_URL)
    assert devices.status_code == 200, devices.content
    assert {row["code"] for row in devices.json()["results"]} == {"AD-T001"}
    assert logistics_admin.get(DEVICES_URL + str(foreign.pk) + "/").status_code == 404

    tasks = logistics_admin.get(TASKS_URL)
    assert tasks.status_code == 200, tasks.content
    assert {row["task_no"] for row in tasks.json()["results"]} == {"LT-T001"}


def test_device_and_task_codes_are_generated_when_omitted(
    logistics_admin, logistics_code_rules, company
):
    created = logistics_admin.post(
        DEVICES_URL,
        {"company_id": company.pk, "name": "自动编号设备", "device_type": "stacker"},
        format="json",
    )
    assert created.status_code == 201, created.content
    year = business_today().year
    assert re.fullmatch(r"AD" + str(year) + r"\d{4}", created.json()["code"]), created.json()

    task = create_task(logistics_admin, company)
    assert task.status_code == 201, task.content
    assert re.fullmatch(
        r"LT" + business_today().strftime("%Y%m%d") + r"\d{4}", task.json()["task_no"]
    ), task.json()


def test_task_state_machine_rejects_skipping_steps(
    logistics_admin, logistics_code_rules, company, device
):
    task_id = create_task(logistics_admin, company, device_id=device.pk).json()["id"]

    # 未下发不能直接开始
    skipped = logistics_admin.post(TASKS_URL + str(task_id) + "/start/", {}, format="json")
    assert skipped.status_code == 409, skipped.content
    assert skipped.json()["code"] == "TASK_STATUS_INVALID"

    dispatched = logistics_admin.post(
        TASKS_URL + str(task_id) + "/dispatch/", {"device_id": device.pk}, format="json"
    )
    assert dispatched.status_code == 200, dispatched.content
    assert dispatched.json()["status"] == LogisticsTaskStatus.DISPATCHED

    started = logistics_admin.post(TASKS_URL + str(task_id) + "/start/", {}, format="json")
    assert started.status_code == 200, started.content
    assert started.json()["status"] == LogisticsTaskStatus.EXECUTING
    device.refresh_from_db()
    assert device.status == AutomationDeviceStatus.RUNNING

    finished = logistics_admin.post(
        TASKS_URL + str(task_id) + "/finish/", {"result": "已入库", "quantity": "12"}, format="json"
    )
    assert finished.status_code == 200, finished.content
    assert finished.json()["status"] == LogisticsTaskStatus.FINISHED
    assert finished.json()["quantity"] == "12.000000"
    device.refresh_from_db()
    assert device.status == AutomationDeviceStatus.IDLE

    # 已完成的任务不能再次完成
    assert (
        logistics_admin.post(TASKS_URL + str(task_id) + "/finish/", {}, format="json").status_code
        == 409
    )


def test_status_cannot_be_patched_directly(
    logistics_admin, logistics_code_rules, company, device
):
    task_id = create_task(logistics_admin, company, device_id=device.pk).json()["id"]
    patched = logistics_admin.patch(
        TASKS_URL + str(task_id) + "/", {"status": "finished"}, format="json"
    )
    assert patched.status_code == 200, patched.content
    assert LogisticsTask.objects.get(pk=task_id).status == LogisticsTaskStatus.PENDING


def test_task_cannot_be_dispatched_to_faulty_device(
    logistics_admin, logistics_code_rules, company, device
):
    device.status = AutomationDeviceStatus.FAULT
    device.save(update_fields=["status"])
    task_id = create_task(logistics_admin, company).json()["id"]

    response = logistics_admin.post(
        TASKS_URL + str(task_id) + "/dispatch/", {"device_id": device.pk}, format="json"
    )
    assert response.status_code == 409, response.content
    assert response.json()["code"] == "DEVICE_NOT_AVAILABLE"
    assert LogisticsTask.objects.get(pk=task_id).status == LogisticsTaskStatus.PENDING


def test_device_cannot_hold_two_executing_tasks(
    logistics_admin, logistics_code_rules, company, device
):
    first = create_task(logistics_admin, company, device_id=device.pk).json()["id"]
    assert (
        logistics_admin.post(
            TASKS_URL + str(first) + "/dispatch/", {"device_id": device.pk}, format="json"
        ).status_code
        == 200
    )
    assert logistics_admin.post(TASKS_URL + str(first) + "/start/", {}, format="json").status_code == 200

    second = create_task(logistics_admin, company, device_id=device.pk).json()["id"]
    conflict = logistics_admin.post(
        TASKS_URL + str(second) + "/dispatch/", {"device_id": device.pk}, format="json"
    )
    assert conflict.status_code == 409, conflict.content
    assert conflict.json()["code"] == "DEVICE_BUSY"


def test_cancel_requires_reason_and_frees_device(
    logistics_admin, logistics_code_rules, company, device
):
    task_id = create_task(logistics_admin, company, device_id=device.pk).json()["id"]
    logistics_admin.post(TASKS_URL + str(task_id) + "/dispatch/", {"device_id": device.pk}, format="json")
    logistics_admin.post(TASKS_URL + str(task_id) + "/start/", {}, format="json")

    blank = logistics_admin.post(
        TASKS_URL + str(task_id) + "/cancel/", {"reason": " "}, format="json"
    )
    assert blank.status_code == 400, blank.content
    assert LogisticsTask.objects.get(pk=task_id).status == LogisticsTaskStatus.EXECUTING

    cancelled = logistics_admin.post(
        TASKS_URL + str(task_id) + "/cancel/", {"reason": "设备故障改人工搬运"}, format="json"
    )
    assert cancelled.status_code == 200, cancelled.content
    assert cancelled.json()["status"] == LogisticsTaskStatus.CANCELLED
    device.refresh_from_db()
    assert device.status == AutomationDeviceStatus.IDLE


def test_device_status_action_writes_operation_log(logistics_admin, company, device):
    changed = logistics_admin.post(
        DEVICES_URL + str(device.pk) + "/set-status/",
        {"status": "charging", "battery_level": 18, "detail": "回桩充电"},
        format="json",
    )
    assert changed.status_code == 200, changed.content
    assert changed.json()["status"] == AutomationDeviceStatus.CHARGING
    assert changed.json()["battery_level"] == 18

    logs = logistics_admin.get(LOGS_URL, {"device_id": device.pk})
    assert logs.status_code == 200, logs.content
    rows = logs.json()["results"]
    assert rows and rows[0]["action"] == "status_change"
    assert rows[0]["detail"] == "回桩充电"


def test_operation_log_is_read_only(logistics_admin):
    assert logistics_admin.post(LOGS_URL, {"detail": "伪造日志"}, format="json").status_code == 405
    assert LogisticsOperationLog.objects.count() == 0


def test_viewer_cannot_execute_task(logistics_viewer, company, device):
    task = LogisticsTask.objects.create(
        company=company, task_no="LT-V001", task_type="move", status=LogisticsTaskStatus.DISPATCHED
    )
    response = logistics_viewer.post(TASKS_URL + str(task.pk) + "/start/", {}, format="json")
    assert response.status_code == 403, response.content
    task.refresh_from_db()
    assert task.status == LogisticsTaskStatus.DISPATCHED
