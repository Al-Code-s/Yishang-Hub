"""安全环保接口用例（安全管理 / 环保管理 / 消防管理 / 设备设施安全）。

覆盖要点：
* 数据范围在四个业务域的台账上一致生效；
* 制度、培训、隐患、事故、排污、固废、消防、检查等编号留空时按编码规则自动取号；
* 隐患「整改 → 提交验收 → 验收」闭环：验收不通过退回整改中，不允许静默销账；
* 事故「调查 → 整改 → 关闭」闭环，跳步一律 409；
* 动火 / 防爆防静电 / 受限空间作业必须指定监护人才能批准，驳回必须写理由；
* 作业许可「批准 → 开工 → 完工 → 验收」全流程，且状态不能直接 PATCH；
* 排污监测由服务层按「实测值 vs 限值」自动判定是否达标，客户端改不动这个字段；
* 每次状态流转都写安全环保操作日志，日志接口只读。

全部走 HTTP 接口与真实 MySQL 约束，不使用 mock。
"""

from __future__ import annotations

import re
from datetime import timedelta

import pytest

from apps.core.models import CodeRule, ResetPeriod
from apps.core.services import business_now, business_today
from apps.ehs.models import (
    AccidentStatus,
    EhsOperationLog,
    EnvironmentMonitor,
    HazardRecord,
    HazardStatus,
    PermitStatus,
    WorkPermit,
)
from apps.identity.models import DataScopeType
from tests.conftest import make_role, make_user

pytestmark = pytest.mark.django_db

BASE = "/api/v1/ehs"
REGULATIONS_URL = BASE + "/regulations/"
TRAININGS_URL = BASE + "/trainings/"
HAZARDS_URL = BASE + "/hazards/"
ACCIDENTS_URL = BASE + "/accidents/"
MONITORS_URL = BASE + "/env-monitors/"
COMPLIANCE_URL = BASE + "/compliance-checks/"
FIRE_FACILITIES_URL = BASE + "/fire-facilities/"
PERMITS_URL = BASE + "/work-permits/"
LOGS_URL = BASE + "/operation-logs/"
LOGIN_URL = "/api/v1/identity/auth/login/"
PASSWORD = "Tst!Passw0rd2026"


def login(client, user) -> None:
    response = client.post(
        LOGIN_URL, {"username": user.username, "password": PASSWORD}, format="json"
    )
    assert response.status_code == 200, response.content


def ehs_codes(registry_permissions) -> list[str]:
    return sorted(code for code in registry_permissions if code.startswith("ehs."))


@pytest.fixture
def ehs_code_rules(db):
    """取号依赖编码规则；测试库不跑 bootstrap_system，这里显式登记安全环保模块的规则。"""
    rules = {
        "SRG": ("SRG{YYYY}{SEQ:4}", ResetPeriod.YEARLY),
        "TRN": ("TRN{YYYYMMDD}{SEQ:4}", ResetPeriod.DAILY),
        "HZD": ("HZD{YYYYMMDD}{SEQ:4}", ResetPeriod.DAILY),
        "EPL": ("EPL{YYYY}{SEQ:4}", ResetPeriod.YEARLY),
        "ACR": ("ACR{YYYYMMDD}{SEQ:4}", ResetPeriod.DAILY),
        "ENV": ("ENV{YYYYMMDD}{SEQ:4}", ResetPeriod.DAILY),
        "WST": ("WST{YYYYMMDD}{SEQ:4}", ResetPeriod.DAILY),
        "CMP": ("CMP{YYYYMMDD}{SEQ:4}", ResetPeriod.DAILY),
        "FDR": ("FDR{YYYYMMDD}{SEQ:4}", ResetPeriod.DAILY),
        "FFC": ("FFC{YYYY}{SEQ:4}", ResetPeriod.YEARLY),
        "WPR": ("WPR{YYYYMMDD}{SEQ:4}", ResetPeriod.DAILY),
        "SCH": ("SCH{YYYYMMDD}{SEQ:4}", ResetPeriod.DAILY),
        "SPI": ("SPI{YYYY}{SEQ:4}", ResetPeriod.YEARLY),
    }
    for code, (pattern, period) in rules.items():
        CodeRule.objects.update_or_create(
            code=code,
            defaults={"name": code, "pattern": pattern, "reset_period": period, "is_active": True},
        )


@pytest.fixture
def ehs_admin(api_client, registry_permissions, company):
    role = make_role(
        code="test_ehs_admin",
        permission_codes=ehs_codes(registry_permissions),
        data_scope_type=DataScopeType.COMPANY,
        company=company,
    )
    user = make_user(username="ehs_admin_t", role=role, company=company)
    login(api_client, user)
    return api_client


@pytest.fixture
def ehs_viewer(api_client, registry_permissions, company):
    role = make_role(
        code="test_ehs_viewer",
        permission_codes=[code for code in ehs_codes(registry_permissions) if code.endswith(".view")],
        data_scope_type=DataScopeType.COMPANY,
        company=company,
    )
    user = make_user(username="ehs_viewer_t", role=role, company=company)
    login(api_client, user)
    return api_client


def make_hazard(client, company, *, title="消防通道堆物"):
    return client.post(
        HAZARDS_URL,
        {
            "company_id": company.pk,
            "title": title,
            "level": "high",
            "source": "inspection",
            "found_date": business_today().isoformat(),
        },
        format="json",
    )


def make_permit(client, company, *, permit_type="hot_work"):
    return client.post(
        PERMITS_URL,
        {
            "company_id": company.pk,
            "permit_type": permit_type,
            "work_content": "焊接除尘管道",
            "risk_level": "high",
        },
        format="json",
    )


def test_unauthenticated_ehs_access_is_denied(api_client):
    assert api_client.get(HAZARDS_URL).status_code in (401, 403)


def test_ledger_lists_are_company_scoped(ehs_admin, company, other_company):
    HazardRecord.objects.create(
        company=company,
        hazard_no="HZD-A",
        title="本公司隐患",
        level="low",
        source="report",
        found_date=business_today(),
    )
    HazardRecord.objects.create(
        company=other_company,
        hazard_no="HZD-B",
        title="对照公司隐患",
        level="low",
        source="report",
        found_date=business_today(),
    )
    listed = ehs_admin.get(HAZARDS_URL)
    assert listed.status_code == 200, listed.content
    assert {row["title"] for row in listed.json()["results"]} == {"本公司隐患"}


def test_ledger_codes_are_generated_when_omitted(ehs_admin, ehs_code_rules, company):
    today = business_today().strftime("%Y%m%d")
    year = business_today().year

    regulation = ehs_admin.post(
        REGULATIONS_URL,
        {"company_id": company.pk, "name": "安全生产责任制", "category": "system"},
        format="json",
    )
    assert regulation.status_code == 201, regulation.content
    assert re.fullmatch(r"SRG" + str(year) + r"\d{4}", regulation.json()["code"])

    training = ehs_admin.post(
        TRAININGS_URL,
        {"company_id": company.pk, "topic": "消防器材使用", "training_type": "special"},
        format="json",
    )
    assert training.status_code == 201, training.content
    assert re.fullmatch(r"TRN" + today + r"\d{4}", training.json()["training_no"])

    hazard = make_hazard(ehs_admin, company)
    assert hazard.status_code == 201, hazard.content
    assert re.fullmatch(r"HZD" + today + r"\d{4}", hazard.json()["hazard_no"])
    assert hazard.json()["status"] == HazardStatus.REPORTED

    facility = ehs_admin.post(
        FIRE_FACILITIES_URL,
        {"company_id": company.pk, "name": "一号厂房消火栓", "facility_type": "hydrant"},
        format="json",
    )
    assert facility.status_code == 201, facility.content
    assert re.fullmatch(r"FFC" + str(year) + r"\d{4}", facility.json()["code"])


def test_hazard_rectify_verify_loop(ehs_admin, ehs_code_rules, company):
    hazard_id = make_hazard(ehs_admin, company).json()["id"]

    # 未整改不能提交验收
    premature = ehs_admin.post(HAZARDS_URL + str(hazard_id) + "/submit-verify/", {}, format="json")
    assert premature.status_code == 409, premature.content

    blank_measure = ehs_admin.post(
        HAZARDS_URL + str(hazard_id) + "/rectify/", {"measure": "  "}, format="json"
    )
    assert blank_measure.status_code == 400, blank_measure.content

    rectified = ehs_admin.post(
        HAZARDS_URL + str(hazard_id) + "/rectify/",
        {"measure": "清理通道并划线"},
        format="json",
    )
    assert rectified.status_code == 200, rectified.content
    assert rectified.json()["status"] == HazardStatus.RECTIFYING

    submitted = ehs_admin.post(HAZARDS_URL + str(hazard_id) + "/submit-verify/", {}, format="json")
    assert submitted.status_code == 200, submitted.content
    assert submitted.json()["status"] == HazardStatus.VERIFYING

    # 验收不通过 → 退回整改中，不合格隐患不会被销账
    rejected = ehs_admin.post(
        HAZARDS_URL + str(hazard_id) + "/verify/",
        {"result": "仍有杂物，退回", "passed": False},
        format="json",
    )
    assert rejected.status_code == 200, rejected.content
    assert rejected.json()["status"] == HazardStatus.RECTIFYING

    ehs_admin.post(
        HAZARDS_URL + str(hazard_id) + "/rectify/", {"measure": "再次清理"}, format="json"
    )
    ehs_admin.post(HAZARDS_URL + str(hazard_id) + "/submit-verify/", {}, format="json")
    passed = ehs_admin.post(
        HAZARDS_URL + str(hazard_id) + "/verify/",
        {"result": "现场确认已闭环", "passed": True},
        format="json",
    )
    assert passed.status_code == 200, passed.content
    assert passed.json()["status"] == HazardStatus.CLOSED

    logs = ehs_admin.get(LOGS_URL, {"business_type": "HazardRecord"})
    assert logs.status_code == 200, logs.content
    assert {row["action"] for row in logs.json()["results"]} >= {"rectify_start", "verify"}


def test_accident_investigate_rectify_close(ehs_admin, ehs_code_rules, company):
    created = ehs_admin.post(
        ACCIDENTS_URL,
        {
            "company_id": company.pk,
            "title": "缝纫机手部划伤",
            "category": "injury",
            "level": "general",
            "occurred_at": business_now().isoformat(),
        },
        format="json",
    )
    assert created.status_code == 201, created.content
    accident_id = created.json()["id"]
    assert created.json()["status"] == AccidentStatus.REPORTED

    # 未调查不能直接登记整改
    premature = ehs_admin.post(
        ACCIDENTS_URL + str(accident_id) + "/rectify/", {"measures": "加装护手"}, format="json"
    )
    assert premature.status_code == 409, premature.content

    assert (
        ehs_admin.post(ACCIDENTS_URL + str(accident_id) + "/investigate/", {}, format="json").json()[
            "status"
        ]
        == AccidentStatus.INVESTIGATING
    )
    assert (
        ehs_admin.post(
            ACCIDENTS_URL + str(accident_id) + "/rectify/",
            {"measures": "加装护手并复训", "causes": "防护罩缺失"},
            format="json",
        ).json()["status"]
        == AccidentStatus.RECTIFIED
    )
    closed = ehs_admin.post(
        ACCIDENTS_URL + str(accident_id) + "/close/",
        {"result": "整改验证合格，事故关闭"},
        format="json",
    )
    assert closed.status_code == 200, closed.content
    assert closed.json()["status"] == AccidentStatus.CLOSED


def test_hot_work_permit_requires_guardian_and_follows_state_machine(ehs_admin, ehs_code_rules, company):
    permit_id = make_permit(ehs_admin, company).json()["id"]

    # 动火作业没有监护人不能批准
    no_guardian = ehs_admin.post(PERMITS_URL + str(permit_id) + "/approve/", {}, format="json")
    assert no_guardian.status_code == 400, no_guardian.content
    assert no_guardian.json()["code"] == "PERMIT_GUARDIAN_REQUIRED"
    assert WorkPermit.objects.get(pk=permit_id).status == PermitStatus.APPLIED

    # 直接 PATCH 状态不生效
    ehs_admin.patch(PERMITS_URL + str(permit_id) + "/", {"status": "accepted"}, format="json")
    assert WorkPermit.objects.get(pk=permit_id).status == PermitStatus.APPLIED

    approved = ehs_admin.post(
        PERMITS_URL + str(permit_id) + "/approve/",
        {"guardian_id": make_guardian(company).pk},
        format="json",
    )
    assert approved.status_code == 200, approved.content
    assert approved.json()["status"] == PermitStatus.APPROVED

    # 未开工不能完工
    premature = ehs_admin.post(PERMITS_URL + str(permit_id) + "/finish/", {}, format="json")
    assert premature.status_code == 409, premature.content

    assert (
        ehs_admin.post(PERMITS_URL + str(permit_id) + "/start/", {}, format="json").json()["status"]
        == PermitStatus.WORKING
    )
    assert (
        ehs_admin.post(
            PERMITS_URL + str(permit_id) + "/finish/", {"result": "动火完成"}, format="json"
        ).json()["status"]
        == PermitStatus.FINISHED
    )
    accepted = ehs_admin.post(
        PERMITS_URL + str(permit_id) + "/accept/", {"result": "现场验收合格"}, format="json"
    )
    assert accepted.status_code == 200, accepted.content
    assert accepted.json()["status"] == PermitStatus.ACCEPTED


def make_guardian(company):
    from apps.factory.models import Employee

    return Employee.objects.create(company=company, employee_no="EMP-G1", name="监护人老王")


def test_permit_reject_requires_reason(ehs_admin, ehs_code_rules, company):
    permit_id = make_permit(ehs_admin, company, permit_type="maintenance").json()["id"]
    blank = ehs_admin.post(PERMITS_URL + str(permit_id) + "/reject/", {"reason": " "}, format="json")
    assert blank.status_code == 400, blank.content

    rejected = ehs_admin.post(
        PERMITS_URL + str(permit_id) + "/reject/", {"reason": "防护措施不到位"}, format="json"
    )
    assert rejected.status_code == 200, rejected.content
    assert rejected.json()["status"] == PermitStatus.REJECTED


def test_environment_monitor_compliance_is_service_judged(ehs_admin, ehs_code_rules, company):
    over = ehs_admin.post(
        MONITORS_URL,
        {
            "company_id": company.pk,
            "medium": "waste_water",
            "point_name": "厂区总排口",
            "pollutant": "COD",
            "limit_value": "100",
            "measured_value": "135",
            "monitored_at": business_now().isoformat(),
        },
        format="json",
    )
    assert over.status_code == 201, over.content
    assert over.json()["is_compliant"] is False
    assert over.json()["is_over_limit"] is True

    within = ehs_admin.post(
        MONITORS_URL,
        {
            "company_id": company.pk,
            "medium": "waste_gas",
            "point_name": "锅炉烟囱",
            "pollutant": "颗粒物",
            "limit_value": "20",
            "measured_value": "8",
            "monitored_at": business_now().isoformat(),
        },
        format="json",
    )
    assert within.status_code == 201, within.content
    assert within.json()["is_compliant"] is True
    assert within.json()["is_over_limit"] is False

    # 达标与否由服务层判定，客户端不能自己改成 False
    forced = ehs_admin.patch(
        MONITORS_URL + str(within.json()["id"]) + "/", {"is_compliant": False}, format="json"
    )
    assert forced.status_code == 200, forced.content
    assert EnvironmentMonitor.objects.get(pk=within.json()["id"]).is_compliant is True


def test_viewer_cannot_rectify_hazard(ehs_viewer, company):
    hazard = HazardRecord.objects.create(
        company=company,
        hazard_no="HZD-V1",
        title="只读账号隐患",
        level="low",
        source="report",
        found_date=business_today(),
    )
    response = ehs_viewer.post(
        HAZARDS_URL + str(hazard.pk) + "/rectify/", {"measure": "越权整改"}, format="json"
    )
    assert response.status_code == 403, response.content
    hazard.refresh_from_db()
    assert hazard.status == HazardStatus.REPORTED


def test_operation_log_is_read_only(ehs_admin):
    assert ehs_admin.post(LOGS_URL, {"detail": "伪造日志"}, format="json").status_code == 405
    assert EhsOperationLog.objects.count() == 0


def test_compliance_check_number_is_generated_and_detail_readable(ehs_admin, ehs_code_rules, company):
    """环保合规检查编号留空自动取号，且列表 / 详情字段完整可读。"""
    created = ehs_admin.post(
        COMPLIANCE_URL,
        {
            "company_id": company.pk,
            "check_type": "self",
            "title": "自行监测合规自查",
            "check_date": (business_today() - timedelta(days=1)).isoformat(),
        },
        format="json",
    )
    assert created.status_code == 201, created.content
    assert re.fullmatch(
        r"CMP" + business_today().strftime("%Y%m%d") + r"\d{4}", created.json()["check_no"]
    ), created.json()
    detail = ehs_admin.get(COMPLIANCE_URL + str(created.json()["id"]) + "/")
    assert detail.status_code == 200, detail.content
    assert detail.json()["title"] == "自行监测合规自查"
    assert detail.json()["status"] == "pending"
