"""设备管理接口用例（设备台账 / 保养 / 维修 / 点巡检 / 异常上报 / 备件库存台账）。

覆盖要点：
* 公司数据范围在「列表 / 详情 / 写入」三处同时生效，越权写入整体回滚；
* 设备、备件、保养计划与任务、报修单、维修与点巡检记录等编号留空时按编码规则自动取号；
* 保养计划「生成到期任务」幂等：重复调用不会重复生成同一天的任务，下次保养日期同步推进；
* 保养 / 维修任务完成时在同一事务里生成记录，并把来源报修单推进到「已关闭」；
* 点巡检异常记录可一键转报修，形成「点检发现 -> 报修 -> 维修」闭环；
* 状态只能由动作接口推进，直接 PATCH status 不会生效；
* 无写权限的账号不能调用写接口；
* 备件现存量（库存台账）只读，数据范围按公司收敛，库存数字来自仓储的统一库存余额。

全部走 HTTP 接口与真实 MySQL 约束，不使用 mock。
"""

from __future__ import annotations

import re
from datetime import timedelta

import pytest

from apps.core.models import CodeRule, ResetPeriod
from apps.core.services import business_today
from apps.equipment.models import (
    AbnormalRecord,
    AbnormalType,
    Equipment,
    EquipmentType,
    FaultReport,
    FaultReportStatus,
    InspectionRecord,
    InspectionResult,
    MaintenanceRecord,
    MaintenanceTask,
    RepairRecord,
    RepairTask,
    SparePart,
    TaskStatus,
)
from apps.identity.models import DataScopeType
from apps.masterdata.models import Material, MaterialCategory, UoM
from tests.conftest import make_role, make_user

pytestmark = pytest.mark.django_db

BASE = "/api/v1/equipment"
EQUIPMENTS_URL = BASE + "/equipments/"
PLANS_URL = BASE + "/maintenance-plans/"
TASKS_URL = BASE + "/maintenance-tasks/"
RECORDS_URL = BASE + "/maintenance-records/"
FAULTS_URL = BASE + "/fault-reports/"
REPAIR_TASKS_URL = BASE + "/repair-tasks/"
REPAIR_RECORDS_URL = BASE + "/repair-records/"
INSPECTION_TASKS_URL = BASE + "/inspection-tasks/"
INSPECTION_RECORDS_URL = BASE + "/inspection-records/"
ABNORMAL_TASKS_URL = BASE + "/abnormal-tasks/"
SPARE_PARTS_URL = BASE + "/spare-parts/"
STOCK_URL = BASE + "/spare-part-stock/"
LOGIN_URL = "/api/v1/identity/auth/login/"
PASSWORD = "Tst!Passw0rd2026"


def login(client, user) -> None:
    response = client.post(
        LOGIN_URL, {"username": user.username, "password": PASSWORD}, format="json"
    )
    assert response.status_code == 200, response.content


def equipment_codes(registry_permissions) -> list[str]:
    return sorted(code for code in registry_permissions if code.startswith("equipment."))


@pytest.fixture
def equipment_code_rules(db):
    """取号依赖编码规则；测试库不跑 bootstrap_system，这里显式登记设备模块的规则。"""
    rules = {
        "EQ": ("EQ{YYYY}{SEQ:4}", ResetPeriod.YEARLY),
        "SP": ("SP{YYYY}{SEQ:4}", ResetPeriod.YEARLY),
        "MP": ("MP{YYYY}{SEQ:4}", ResetPeriod.YEARLY),
        "MT": ("MT{YYYYMMDD}{SEQ:4}", ResetPeriod.DAILY),
        "MR": ("MR{YYYYMMDD}{SEQ:4}", ResetPeriod.DAILY),
        "FR": ("FR{YYYYMMDD}{SEQ:4}", ResetPeriod.DAILY),
        "RT": ("RT{YYYYMMDD}{SEQ:4}", ResetPeriod.DAILY),
        "RR": ("RR{YYYYMMDD}{SEQ:4}", ResetPeriod.DAILY),
        "IT": ("IT{YYYYMMDD}{SEQ:4}", ResetPeriod.DAILY),
        "IR": ("IR{YYYYMMDD}{SEQ:4}", ResetPeriod.DAILY),
        "AT": ("AT{YYYYMMDD}{SEQ:4}", ResetPeriod.DAILY),
        "AR": ("AR{YYYYMMDD}{SEQ:4}", ResetPeriod.DAILY),
    }
    for code, (pattern, period) in rules.items():
        CodeRule.objects.update_or_create(
            code=code,
            defaults={"name": code, "pattern": pattern, "reset_period": period, "is_active": True},
        )


@pytest.fixture
def equipment_admin(api_client, registry_permissions, company):
    role = make_role(
        code="test_equipment_admin",
        permission_codes=equipment_codes(registry_permissions),
        data_scope_type=DataScopeType.COMPANY,
        company=company,
    )
    user = make_user(username="eq_admin_t", role=role, company=company)
    login(api_client, user)
    return api_client


@pytest.fixture
def equipment_viewer(api_client, registry_permissions, company):
    role = make_role(
        code="test_equipment_viewer",
        permission_codes=[code for code in equipment_codes(registry_permissions) if code.endswith(".view")],
        data_scope_type=DataScopeType.COMPANY,
        company=company,
    )
    user = make_user(username="eq_viewer_t", role=role, company=company)
    login(api_client, user)
    return api_client


@pytest.fixture
def equipment_type(db):
    return EquipmentType.objects.create(code="ET-SEW", name="缝纫设备")


@pytest.fixture
def equipment(company, equipment_type):
    return Equipment.objects.create(
        company=company, code="EQ-A001", name="平缝机 A", equipment_type=equipment_type
    )


def test_unauthenticated_equipment_access_is_denied(api_client):
    response = api_client.get(EQUIPMENTS_URL)
    assert response.status_code in (401, 403), response.content


def test_equipment_list_and_detail_are_company_scoped(
    equipment_admin, company, other_company, equipment, equipment_type
):
    foreign = Equipment.objects.create(
        company=other_company, code="EQ-OTH", name="对照设备", equipment_type=equipment_type
    )

    listed = equipment_admin.get(EQUIPMENTS_URL)
    assert listed.status_code == 200, listed.content
    codes = {row["code"] for row in listed.json()["results"]}
    assert "EQ-A001" in codes
    assert "EQ-OTH" not in codes

    assert equipment_admin.get(EQUIPMENTS_URL + str(equipment.pk) + "/").status_code == 200
    # 越权详情按「不存在」处理，不泄露其他公司是否存在该设备
    assert equipment_admin.get(EQUIPMENTS_URL + str(foreign.pk) + "/").status_code == 404


def test_cannot_create_equipment_outside_company_scope(
    equipment_admin, equipment_code_rules, other_company, equipment_type
):
    response = equipment_admin.post(
        EQUIPMENTS_URL,
        {"company_id": other_company.pk, "name": "越权设备", "equipment_type_id": equipment_type.pk},
        format="json",
    )
    assert response.status_code == 403, response.content
    assert response.json()["code"] == "OUT_OF_DATA_SCOPE"
    assert not Equipment.objects.filter(name="越权设备").exists()


def test_equipment_and_spare_part_codes_are_generated_when_omitted(
    equipment_admin, equipment_code_rules, company, equipment_type
):
    created = equipment_admin.post(
        EQUIPMENTS_URL,
        {"company_id": company.pk, "name": "自动编号设备", "equipment_type_id": equipment_type.pk},
        format="json",
    )
    assert created.status_code == 201, created.content
    assert re.fullmatch(r"EQ" + str(business_today().year) + r"\d{4}", created.json()["code"]), created.json()

    part = equipment_admin.post(
        SPARE_PARTS_URL,
        {"company_id": company.pk, "name": "自动编号备件"},
        format="json",
    )
    assert part.status_code == 201, part.content
    assert re.fullmatch(r"SP" + str(business_today().year) + r"\d{4}", part.json()["code"]), part.json()


def test_maintenance_plan_generates_due_tasks_idempotently(
    equipment_admin, equipment_code_rules, company, equipment
):
    today = business_today()
    start = today - timedelta(days=21)
    created = equipment_admin.post(
        PLANS_URL,
        {
            "company_id": company.pk,
            "name": "周保养",
            "equipment_id": equipment.pk,
            "cycle_days": 7,
            "start_date": start.isoformat(),
            "next_date": start.isoformat(),
        },
        format="json",
    )
    assert created.status_code == 201, created.content
    plan = created.json()
    assert re.fullmatch(r"MP" + str(today.year) + r"\d{4}", plan["plan_no"]), plan

    first = equipment_admin.post(
        PLANS_URL + str(plan["id"]) + "/generate-tasks/",
        {"until_date": today.isoformat()},
        format="json",
    )
    assert first.status_code == 200, first.content
    assert first.json()["created_count"] == 4, first.json()
    assert MaintenanceTask.objects.filter(plan_id=plan["id"]).count() == 4

    # 再点一次不会重复生成：同一天同一计划只有一条任务
    second = equipment_admin.post(
        PLANS_URL + str(plan["id"]) + "/generate-tasks/",
        {"until_date": today.isoformat()},
        format="json",
    )
    assert second.status_code == 200, second.content
    assert second.json()["created_count"] == 0, second.json()
    assert MaintenanceTask.objects.filter(plan_id=plan["id"]).count() == 4


def test_maintenance_task_lifecycle_creates_record(
    equipment_admin, equipment_code_rules, company, equipment
):
    created = equipment_admin.post(
        TASKS_URL,
        {"equipment_id": equipment.pk, "plan_date": business_today().isoformat()},
        format="json",
    )
    assert created.status_code == 201, created.content
    task = created.json()
    assert re.fullmatch(r"MT\d{8}\d{4}", task["task_no"]), task
    assert task["status"] == TaskStatus.PENDING

    started = equipment_admin.post(TASKS_URL + str(task["id"]) + "/start/", {}, format="json")
    assert started.status_code == 200, started.content
    assert started.json()["status"] == TaskStatus.IN_PROGRESS

    completed = equipment_admin.post(
        TASKS_URL + str(task["id"]) + "/complete/",
        {"content": "清洁导轨并加注润滑油", "result": "运转正常"},
        format="json",
    )
    assert completed.status_code == 200, completed.content
    body = completed.json()
    assert body["task"]["status"] == TaskStatus.COMPLETED
    record = MaintenanceRecord.objects.get(task_id=task["id"])
    assert record.record_no == body["record"]["record_no"]
    assert record.company_id == company.pk


def test_fault_report_dispatch_and_repair_completion_closes_report(
    equipment_admin, equipment_code_rules, equipment
):
    report = equipment_admin.post(
        FAULTS_URL,
        {"equipment_id": equipment.pk, "description": "运转时有异响"},
        format="json",
    )
    assert report.status_code == 201, report.content
    report_body = report.json()
    assert re.fullmatch(r"FR\d{8}\d{4}", report_body["report_no"]), report_body
    assert report_body["status"] == FaultReportStatus.REPORTED

    dispatched = equipment_admin.post(
        FAULTS_URL + str(report_body["id"]) + "/dispatch/",
        {"symptom": "主轴轴承异响"},
        format="json",
    )
    assert dispatched.status_code == 201, dispatched.content
    task = dispatched.json()
    assert re.fullmatch(r"RT\d{8}\d{4}", task["task_no"]), task
    assert FaultReport.objects.get(pk=report_body["id"]).status == FaultReportStatus.ASSIGNED

    assert equipment_admin.post(
        REPAIR_TASKS_URL + str(task["id"]) + "/start/", {}, format="json"
    ).status_code == 200

    completed = equipment_admin.post(
        REPAIR_TASKS_URL + str(task["id"]) + "/complete/",
        {"fault_reason": "轴承磨损", "solution": "更换轴承", "downtime_minutes": 45},
        format="json",
    )
    assert completed.status_code == 200, completed.content
    assert RepairTask.objects.get(pk=task["id"]).status == TaskStatus.COMPLETED
    assert RepairRecord.objects.filter(task_id=task["id"]).exists()
    # 维修完成即关闭来源报修单，不需要再手工关一次
    assert FaultReport.objects.get(pk=report_body["id"]).status == FaultReportStatus.CLOSED


def test_inspection_abnormal_record_can_raise_fault(
    equipment_admin, equipment_code_rules, equipment
):
    created = equipment_admin.post(
        INSPECTION_TASKS_URL,
        {
            "equipment_id": equipment.pk,
            "plan_date": business_today().isoformat(),
            "task_type": "point",
        },
        format="json",
    )
    assert created.status_code == 201, created.content
    task = created.json()
    assert re.fullmatch(r"IT\d{8}\d{4}", task["task_no"]), task

    assert equipment_admin.post(
        INSPECTION_TASKS_URL + str(task["id"]) + "/start/", {}, format="json"
    ).status_code == 200
    finished = equipment_admin.post(
        INSPECTION_TASKS_URL + str(task["id"]) + "/complete/",
        {"result": "发现异常"},
        format="json",
    )
    assert finished.status_code == 200, finished.content
    assert finished.json()["status"] == TaskStatus.COMPLETED

    record = equipment_admin.post(
        INSPECTION_RECORDS_URL,
        {
            "equipment_id": equipment.pk,
            "result": InspectionResult.ABNORMAL,
            "abnormal_desc": "油位偏低",
        },
        format="json",
    )
    assert record.status_code == 201, record.content
    record_body = record.json()
    assert re.fullmatch(r"IR\d{8}\d{4}", record_body["record_no"]), record_body

    raised = equipment_admin.post(
        INSPECTION_RECORDS_URL + str(record_body["id"]) + "/raise-fault/", {}, format="json"
    )
    assert raised.status_code == 201, raised.content
    assert "点巡检发现异常" in raised.json()["description"]
    assert FaultReport.objects.filter(equipment=equipment).count() == 1

    normal = InspectionRecord.objects.create(
        company=equipment.company,
        equipment=equipment,
        record_no="IR-NORMAL",
        result=InspectionResult.NORMAL,
    )
    rejected = equipment_admin.post(
        INSPECTION_RECORDS_URL + str(normal.pk) + "/raise-fault/", {}, format="json"
    )
    assert rejected.status_code == 409, rejected.content
    assert rejected.json()["code"] == "NOT_ABNORMAL_RECORD"


def test_abnormal_task_flow_creates_record(
    equipment_admin, equipment_code_rules, company, equipment
):
    abnormal_type = AbnormalType.objects.create(code="AT-OIL", name="漏油")
    created = equipment_admin.post(
        ABNORMAL_TASKS_URL,
        {
            "equipment_id": equipment.pk,
            "abnormal_type_id": abnormal_type.pk,
            "description": "设备下方有油迹",
        },
        format="json",
    )
    assert created.status_code == 201, created.content
    task = created.json()
    assert re.fullmatch(r"AT\d{8}\d{4}", task["task_no"]), task

    assert equipment_admin.post(
        ABNORMAL_TASKS_URL + str(task["id"]) + "/assign/", {}, format="json"
    ).status_code == 200
    handling = equipment_admin.post(
        ABNORMAL_TASKS_URL + str(task["id"]) + "/handle/",
        {"action": "更换密封圈"},
        format="json",
    )
    assert handling.status_code == 200, handling.content
    assert handling.json()["status"] == "handling"

    closed = equipment_admin.post(
        ABNORMAL_TASKS_URL + str(task["id"]) + "/close/",
        {"result": "已更换密封圈，观察 24 小时无渗漏"},
        format="json",
    )
    assert closed.status_code == 200, closed.content
    record = AbnormalRecord.objects.get(task_id=task["id"])
    assert record.record_no == closed.json()["record"]["record_no"]
    assert record.company_id == company.pk


def test_status_cannot_be_changed_by_patch(equipment_admin, equipment, equipment_code_rules):
    created = equipment_admin.post(
        TASKS_URL,
        {"equipment_id": equipment.pk, "plan_date": business_today().isoformat()},
        format="json",
    )
    task_id = created.json()["id"]
    patched = equipment_admin.patch(
        TASKS_URL + str(task_id) + "/", {"status": TaskStatus.COMPLETED}, format="json"
    )
    assert patched.status_code == 200, patched.content
    # 状态是只读字段：PATCH 不会把它推进到已完成，必须走动作接口
    assert MaintenanceTask.objects.get(pk=task_id).status == TaskStatus.PENDING


def test_viewer_cannot_write(equipment_viewer, equipment):
    response = equipment_viewer.post(
        FAULTS_URL, {"equipment_id": equipment.pk, "description": "越权报修"}, format="json"
    )
    assert response.status_code == 403, response.content
    assert not FaultReport.objects.filter(description="越权报修").exists()


def test_spare_part_stock_is_company_scoped_and_read_only(
    equipment_admin, api_client, registry_permissions, company, other_company
):
    category = MaterialCategory.objects.create(code="MC-SP", name="备件")
    uom = UoM.objects.create(code="PCS", name="个")
    material = Material.objects.create(
        company=company, code="M-SP-1", name="轴承", category=category, base_uom=uom
    )
    SparePart.objects.create(
        company=company, code="SP-MINE", name="主轴轴承", material=material, safety_stock=10
    )
    foreign_material = Material.objects.create(
        company=other_company, code="M-SP-2", name="对照轴承", category=category, base_uom=uom
    )
    SparePart.objects.create(
        company=other_company, code="SP-FOREIGN", name="对照备件", material=foreign_material
    )

    listed = equipment_admin.get(STOCK_URL)
    assert listed.status_code == 200, listed.content
    rows = listed.json()["results"]
    codes = {row["code"] for row in rows}
    assert "SP-MINE" in codes
    assert "SP-FOREIGN" not in codes
    mine = next(row for row in rows if row["code"] == "SP-MINE")
    # 从没入过库的备件也要出现，且库存为 0、低于安全库存
    assert mine["on_hand"] == "0"
    assert mine["below_safety"] is True

    # 库存台账是只读汇总，没有新增/修改接口
    assert equipment_admin.post(STOCK_URL, {"code": "SP-NEW"}, format="json").status_code == 405
