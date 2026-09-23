"""能源管理接口用例（基础管理 / 抄表 / 运行记录 / 报警 / 统计与报表）。

覆盖要点：
* 数据范围在「列表 / 详情 / 抄表 / 运行记录」上一致生效，越权仪表被拦截；
* 仪表编码留空时按编码规则（EM）自动取号；
* 抄表由服务层按上次读数算用量，读数回退被拒绝（防止月报被冲成负数）；
* 越限报警由真实抄表路径触发，同一仪表同一类型同一天只报一次（去重窗口）；
* 离线报警由扫描服务生成，同时把仪表置为离线；
* 运行记录「开始 → 结束」算出运行时长与单耗，单耗超限再触发单耗报警；
* 报警处理/关闭必须走动作接口，直接 PATCH status 无效，未说明不能关闭；
* 能耗报表按日汇总，未维护单价时标记「未维护」且费用为 0，维护后按单价折算；
* 报表可导出真正的 xlsx（openpyxl 生成，不是改后缀的 CSV）。

全部走 HTTP 接口与真实 MySQL 约束，不使用 mock。
* 能耗报表 / 能耗统计的时间维度按 (时间, 介质, 单位) 分行，「全部介质」不合并成一行；
"""

from __future__ import annotations

import re
from datetime import timedelta

import pytest

from apps.core.models import CodeRule, ResetPeriod
from apps.core.services import business_now, business_today
from apps.ems.models import (
    AlarmStatus,
    AlarmType,
    EnergyAlarm,
    EnergyMeter,
    EnergyPrice,
    EnergyRunRecord,
    EnergyThreshold,
    MeterReading,
    MeterStatus,
    RunStatus,
    TariffPeriod,
)
from apps.identity.models import DataScopeType
from tests.conftest import make_role, make_user

pytestmark = pytest.mark.django_db

BASE = "/api/v1/ems"
METERS_URL = BASE + "/meters/"
PRICES_URL = BASE + "/prices/"
THRESHOLDS_URL = BASE + "/thresholds/"
READINGS_URL = BASE + "/readings/"
RECORD_READING_URL = BASE + "/readings/record/"
RUN_RECORDS_URL = BASE + "/run-records/"
ALARMS_URL = BASE + "/alarms/"
REPORT_URL = BASE + "/report/"
STATISTICS_URL = BASE + "/statistics/"
LOGIN_URL = "/api/v1/identity/auth/login/"
PASSWORD = "Tst!Passw0rd2026"


def login(client, user) -> None:
    response = client.post(
        LOGIN_URL, {"username": user.username, "password": PASSWORD}, format="json"
    )
    assert response.status_code == 200, response.content


def ems_codes(registry_permissions) -> list[str]:
    return sorted(code for code in registry_permissions if code.startswith("ems."))


@pytest.fixture
def ems_code_rules(db):
    """取号依赖编码规则；测试库不跑 bootstrap_system，这里显式登记能源模块的规则。"""
    rules = {
        "EM": ("EM{YYYY}{SEQ:4}", ResetPeriod.YEARLY),
        "EAL": ("EAL{YYYYMMDD}{SEQ:4}", ResetPeriod.DAILY),
        "ERN": ("ERN{YYYYMMDD}{SEQ:4}", ResetPeriod.DAILY),
    }
    for code, (pattern, period) in rules.items():
        CodeRule.objects.update_or_create(
            code=code,
            defaults={"name": code, "pattern": pattern, "reset_period": period, "is_active": True},
        )


@pytest.fixture
def ems_admin(api_client, registry_permissions, company):
    role = make_role(
        code="test_ems_admin",
        permission_codes=ems_codes(registry_permissions),
        data_scope_type=DataScopeType.COMPANY,
        company=company,
    )
    user = make_user(username="ems_admin_t", role=role, company=company)
    login(api_client, user)
    return api_client


@pytest.fixture
def ems_viewer(api_client, registry_permissions, company):
    role = make_role(
        code="test_ems_viewer",
        permission_codes=[code for code in ems_codes(registry_permissions) if code.endswith(".view")],
        data_scope_type=DataScopeType.COMPANY,
        company=company,
    )
    user = make_user(username="ems_viewer_t", role=role, company=company)
    login(api_client, user)
    return api_client


@pytest.fixture
def electricity_meter(company):
    return EnergyMeter.objects.create(
        company=company, code="EM-T001", name="一号车间总表", medium="electricity", unit="kWh"
    )


def create_reading(client, meter, reading: str, **extra):
    return client.post(
        RECORD_READING_URL,
        {"meter_id": meter.pk, "reading": reading, **extra},
        format="json",
    )


def test_unauthenticated_ems_access_is_denied(api_client):
    assert api_client.get(METERS_URL).status_code in (401, 403)


def test_meter_list_and_detail_are_company_scoped(
    ems_admin, company, other_company, electricity_meter
):
    foreign = EnergyMeter.objects.create(
        company=other_company, code="EM-OTH", name="对照仪表", medium="water", unit="m3"
    )

    listed = ems_admin.get(METERS_URL)
    assert listed.status_code == 200, listed.content
    codes = {row["code"] for row in listed.json()["results"]}
    assert "EM-T001" in codes
    assert "EM-OTH" not in codes

    assert ems_admin.get(METERS_URL + str(electricity_meter.pk) + "/").status_code == 200
    assert ems_admin.get(METERS_URL + str(foreign.pk) + "/").status_code == 404


def test_cannot_create_meter_outside_company_scope(ems_admin, ems_code_rules, other_company):
    response = ems_admin.post(
        METERS_URL,
        {"company_id": other_company.pk, "name": "越权仪表", "medium": "electricity"},
        format="json",
    )
    assert response.status_code == 403, response.content
    assert response.json()["code"] == "OUT_OF_DATA_SCOPE"
    assert not EnergyMeter.objects.filter(name="越权仪表").exists()


def test_meter_code_is_generated_when_omitted(ems_admin, ems_code_rules, company):
    created = ems_admin.post(
        METERS_URL,
        {"company_id": company.pk, "name": "自动编号仪表", "medium": "water", "unit": "m3"},
        format="json",
    )
    assert created.status_code == 201, created.content
    year = business_today().year
    assert re.fullmatch(r"EM" + str(year) + r"\d{4}", created.json()["code"]), created.json()


def test_reading_consumption_uses_multiplier_and_previous_reading(
    ems_admin, company, electricity_meter
):
    electricity_meter.multiplier = "10"
    electricity_meter.save(update_fields=["multiplier"])

    first = create_reading(ems_admin, electricity_meter, "1000")
    assert first.status_code == 201, first.content
    # 首次抄表没有可比的上次读数，用量记 0 而不是把表底值当用量
    assert first.json()["consumption"] == "0.000000"

    second = create_reading(ems_admin, electricity_meter, "1050")
    assert second.status_code == 201, second.content
    assert second.json()["consumption"] == "500.000000"

    electricity_meter.refresh_from_db()
    assert electricity_meter.status == MeterStatus.ONLINE
    assert electricity_meter.last_reading_at is not None


def test_reading_rollback_is_rejected(ems_admin, electricity_meter):
    assert create_reading(ems_admin, electricity_meter, "500").status_code == 201

    rolled_back = create_reading(ems_admin, electricity_meter, "480")
    assert rolled_back.status_code == 400, rolled_back.content
    assert rolled_back.json()["code"] == "READING_ROLLBACK"
    assert MeterReading.objects.filter(meter=electricity_meter).count() == 1


def test_readings_are_append_only(ems_admin, electricity_meter):
    """读数一经录入即事实：只读列表 + 抄表动作，不提供 PATCH。"""
    created = create_reading(ems_admin, electricity_meter, "120")
    assert created.status_code == 201
    reading_id = created.json()["id"]

    assert ems_admin.get(READINGS_URL).status_code == 200
    patched = ems_admin.patch(
        READINGS_URL + str(reading_id) + "/", {"reading": "1"}, format="json"
    )
    assert patched.status_code == 405, patched.content


def test_over_limit_alarm_is_raised_once_per_day(
    ems_admin, ems_code_rules, company, electricity_meter
):
    EnergyThreshold.objects.create(
        company=company,
        name="电表读数上限",
        medium="electricity",
        upper_limit="100",
        alarm_level="critical",
    )

    assert create_reading(ems_admin, electricity_meter, "150").status_code == 201
    assert create_reading(ems_admin, electricity_meter, "200").status_code == 201

    alarms = EnergyAlarm.objects.filter(meter=electricity_meter, alarm_type=AlarmType.OVER_LIMIT)
    assert alarms.count() == 1
    alarm = alarms.get()
    assert alarm.status == AlarmStatus.PENDING
    assert alarm.level == "critical"


def test_alarm_handle_then_close_via_actions(ems_admin, company, electricity_meter):
    alarm = EnergyAlarm.objects.create(
        company=company,
        alarm_no="EAL-TEST-1",
        meter=electricity_meter,
        alarm_type=AlarmType.OVER_LIMIT,
        status=AlarmStatus.PENDING,
        source="auto",
        occurred_at=business_now(),
        message="测试报警",
    )

    # 直接 PATCH status 无效：状态只能由动作接口推进
    patched = ems_admin.patch(
        ALARMS_URL + str(alarm.pk) + "/", {"status": "closed"}, format="json"
    )
    assert patched.status_code == 200, patched.content
    alarm.refresh_from_db()
    assert alarm.status == AlarmStatus.PENDING

    handled = ems_admin.post(
        ALARMS_URL + str(alarm.pk) + "/handle/", {"note": "已到现场"}, format="json"
    )
    assert handled.status_code == 200, handled.content
    assert handled.json()["status"] == AlarmStatus.HANDLING

    # 关闭必须写处理说明，否则拒绝
    assert (
        ems_admin.post(ALARMS_URL + str(alarm.pk) + "/close/", {"note": "  "}, format="json").status_code
        == 400
    )
    closed = ems_admin.post(
        ALARMS_URL + str(alarm.pk) + "/close/", {"note": "已更换电表"}, format="json"
    )
    assert closed.status_code == 200, closed.content
    assert closed.json()["status"] == AlarmStatus.CLOSED


def test_scan_offline_creates_alarm_and_marks_meter_offline(ems_admin, ems_code_rules, company):
    meter = EnergyMeter.objects.create(
        company=company,
        code="EM-OFF1",
        name="久未抄表仪表",
        medium="water",
        unit="m3",
        install_date=business_today() - timedelta(days=30),
    )
    EnergyThreshold.objects.create(
        company=company, name="水表离线阈值", medium="water", offline_minutes=60
    )

    scanned = ems_admin.post(ALARMS_URL + "scan-offline/", {"company_id": company.pk}, format="json")
    assert scanned.status_code == 200, scanned.content
    assert scanned.json()["created"] == 1
    assert scanned.json()["alarms"][0]["message"]

    meter.refresh_from_db()
    assert meter.status == MeterStatus.OFFLINE
    assert EnergyAlarm.objects.filter(meter=meter, alarm_type=AlarmType.OFFLINE).count() == 1

    # 再扫一次不重复报警（去重窗口内）
    again = ems_admin.post(ALARMS_URL + "scan-offline/", {"company_id": company.pk}, format="json")
    assert again.status_code == 200
    assert again.json()["created"] == 0


def test_run_record_finish_computes_unit_consumption_and_alarms(
    ems_admin, ems_code_rules, company, electricity_meter
):
    EnergyThreshold.objects.create(
        company=company,
        name="单耗上限",
        medium="electricity",
        unit_consumption_limit="0.3",
    )
    started_at = business_now() - timedelta(hours=2)
    started = ems_admin.post(
        RUN_RECORDS_URL + "start/",
        {"meter_id": electricity_meter.pk, "started_at": started_at.isoformat()},
        format="json",
    )
    assert started.status_code == 201, started.content
    record_id = started.json()["id"]
    assert started.json()["status"] == RunStatus.RUNNING

    # 同一仪表不允许两条未结束的记录
    duplicated = ems_admin.post(
        RUN_RECORDS_URL + "start/", {"meter_id": electricity_meter.pk}, format="json"
    )
    assert duplicated.status_code == 409, duplicated.content
    assert duplicated.json()["code"] == "RUN_ALREADY_OPEN"

    finished = ems_admin.post(
        RUN_RECORDS_URL + str(record_id) + "/finish/",
        {
            "finished_at": (started_at + timedelta(minutes=120)).isoformat(),
            "energy_consumption": "100",
            "output_qty": "250",
        },
        format="json",
    )
    assert finished.status_code == 200, finished.content
    body = finished.json()
    assert body["status"] == RunStatus.FINISHED
    assert body["run_minutes"] == 120
    assert body["unit_consumption"] == "0.400000"
    assert EnergyAlarm.objects.filter(
        meter=electricity_meter, alarm_type=AlarmType.UNIT_CONSUMPTION
    ).count() == 1


def test_run_record_status_cannot_be_patched(
    ems_admin, ems_code_rules, company, electricity_meter
):
    record = EnergyRunRecord.objects.create(
        company=company,
        record_no="ERN-TEST-1",
        meter=electricity_meter,
        status=RunStatus.RUNNING,
        started_at=business_now(),
    )
    patched = ems_admin.patch(
        RUN_RECORDS_URL + str(record.pk) + "/", {"status": "finished"}, format="json"
    )
    assert patched.status_code in (200, 405), patched.content
    record.refresh_from_db()
    assert record.status == RunStatus.RUNNING


def test_report_prices_consumption_and_exports_xlsx(
    ems_admin, ems_code_rules, company, electricity_meter
):
    assert create_reading(ems_admin, electricity_meter, "100").status_code == 201
    assert create_reading(ems_admin, electricity_meter, "180").status_code == 201

    today = business_today().isoformat()
    unpriced = ems_admin.get(REPORT_URL, {"period": "day", "medium": "electricity"})
    assert unpriced.status_code == 200, unpriced.content
    rows = unpriced.json()["rows"]
    assert rows and rows[-1]["consumption"] == "80.000000"
    assert rows[-1]["priced"] is False
    assert rows[-1]["cost"] == "0.0000"

    EnergyPrice.objects.create(
        company=company,
        medium="electricity",
        tariff_period=TariffPeriod.FLAT,
        name="平段电价",
        unit_price="0.8000",
        effective_from=business_today() - timedelta(days=1),
    )
    priced = ems_admin.get(REPORT_URL, {"period": "day", "medium": "electricity"})
    assert priced.status_code == 200, priced.content
    row = priced.json()["rows"][-1]
    assert row["priced"] is True
    assert row["cost"] == "64.0000"
    assert priced.json()["totals"]["unpriced"] == 0

    exported = ems_admin.get(REPORT_URL, {"period": "day", "export": "xlsx", "start": today})
    assert exported.status_code == 200, exported.content
    assert exported["Content-Type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert exported.content[:2] == b"PK"  # 真正的 zip(xlsx) 头，不是 CSV


def test_statistics_covers_all_media(ems_admin, ems_code_rules, company, electricity_meter):
    """水/电/气/液共用同一统计接口，按 medium 参数区分。"""
    water = EnergyMeter.objects.create(
        company=company, code="EM-W001", name="水表", medium="water", unit="m3"
    )
    assert create_reading(ems_admin, electricity_meter, "10").status_code == 201
    assert create_reading(ems_admin, water, "5").status_code == 201

    overall = ems_admin.get(STATISTICS_URL, {"dimension": "meter"})
    assert overall.status_code == 200, overall.content
    assert overall.json()["dimension"] == "meter"
    assert {row["medium"] for row in overall.json()["rows"]} == {"electricity", "water"}

    water_only = ems_admin.get(STATISTICS_URL, {"dimension": "meter", "medium": "water"})
    assert water_only.status_code == 200
    assert {row["label"] for row in water_only.json()["rows"]} == {"水表"}


def test_viewer_cannot_record_reading(ems_viewer, electricity_meter):
    response = create_reading(ems_viewer, electricity_meter, "10")
    assert response.status_code == 403, response.content
    assert MeterReading.objects.count() == 0


def test_period_rows_split_by_medium(ems_admin, ems_code_rules, company, electricity_meter):
    """时间维度按 (时间, 介质, 单位) 分行，不把水 / 电 / 气 / 液合并成一行。

    回归用例：「全部介质」时原先把同一段时间的不同介质并成一行，
    介质列只标其中一种、单位列是空串，用量却是各介质之和 ——
    数字看着正常，口径却是错的。
    """
    water = EnergyMeter.objects.create(
        company=company, code="EM-W001", name="水表", medium="water", unit="m3"
    )
    assert create_reading(ems_admin, electricity_meter, "100").status_code == 201
    assert create_reading(ems_admin, electricity_meter, "180").status_code == 201
    assert create_reading(ems_admin, water, "5").status_code == 201
    assert create_reading(ems_admin, water, "8").status_code == 201

    today = business_today().isoformat()
    daily = ems_admin.get(REPORT_URL, {"period": "day", "start": today})
    assert daily.status_code == 200, daily.content
    rows = daily.json()["rows"]
    # 同一天两条：电 80 kWh 与 水 3 m3，介质与单位各自正确，而不是一行 83 标成「电」
    assert {(row["medium"], row["unit"]) for row in rows} == {
        ("electricity", "kWh"),
        ("water", "m3"),
    }
    usage = {row["medium"]: row["consumption"] for row in rows}
    assert usage["electricity"] == "80.000000"
    assert usage["water"] == "3.000000"
    assert all(row["unit"] for row in rows)

    monthly = ems_admin.get(REPORT_URL, {"period": "month"})
    assert monthly.status_code == 200, monthly.content
    month_rows = monthly.json()["rows"]
    assert {(row["medium"], row["unit"]) for row in month_rows} == {
        ("electricity", "kWh"),
        ("water", "m3"),
    }
    month_usage = {row["medium"]: row["consumption"] for row in month_rows}
    assert month_usage["electricity"] == "80.000000"
    assert month_usage["water"] == "3.000000"
