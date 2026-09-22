"""设备数采用例（任务书 11.3「首版必须实现」清单）。

覆盖要点：
* 采集入口**只认设备令牌**，员工登录会话进不来（不复用人员凭证）；
* 令牌明文只在生成时返回一次，库里只留 SHA-256 摘要，轮换后旧令牌立即失效；
* 批次上限、按网关限流、未实现协议都要被明确拒绝（不是静默丢数据）；
* 报文按 message_id 判重、读数按「测点 + 设备时间」二次判重，重复上报不产生第二条读数；
* 处理失败的报文留在采集日志里（含失败原因），失败不会被伪装成成功；
* 模拟数据全程带 is_simulated 标记，来源为模拟器；
* 越限报警按「测点」去重（同一测点一小时内只报一次），离线检测只针对真实设备；
* 数采设备 / 读数 / 报文都按公司收敛数据范围，测点的公司归属由设备推导。

全部走 HTTP 接口与真实 MySQL 约束，不使用 mock。
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from apps.core.models import CodeRule, ResetPeriod
from apps.core.services import business_now, business_today
from apps.ems.models import AlarmType, EnergyAlarm
from apps.identity.models import DataScopeType
from apps.iot import services
from apps.iot.models import (
    GatewayStatus,
    IoTGateway,
    IoTMessage,
    IoTPoint,
    IoTReading,
    MessageStatus,
    ReadingSource,
)
from tests.conftest import make_role, make_user

pytestmark = pytest.mark.django_db

BASE = "/api/v1/iot"
CONNECTIONS_URL = BASE + "/connections/"
GATEWAYS_URL = BASE + "/gateways/"
POINTS_URL = BASE + "/points/"
READINGS_URL = BASE + "/readings/"
MESSAGES_URL = BASE + "/messages/"
INGEST_URL = BASE + "/ingest/"
MONITOR_URL = BASE + "/monitor/"
STATISTICS_URL = BASE + "/statistics/"
LOGIN_URL = "/api/v1/identity/auth/login/"
META_URL = "/api/v1/meta/"
PASSWORD = "Tst!Passw0rd2026"


def login(client, user) -> None:
    response = client.post(
        LOGIN_URL, {"username": user.username, "password": PASSWORD}, format="json"
    )
    assert response.status_code == 200, response.content


@pytest.fixture
def iot_code_rules(db):
    """取号与报警编号依赖编码规则；测试库不跑 bootstrap_system，这里显式登记。"""
    rules = {
        "IOTCN": ("IOTCN{YYYY}{SEQ:4}", ResetPeriod.YEARLY),
        "IOTGW": ("IOTGW{YYYY}{SEQ:4}", ResetPeriod.YEARLY),
        "IOTPT": ("IOTPT{YYYY}{SEQ:4}", ResetPeriod.YEARLY),
        "EAL": ("EAL{YYYYMMDD}{SEQ:4}", ResetPeriod.DAILY),
    }
    for code, (pattern, period) in rules.items():
        CodeRule.objects.update_or_create(
            code=code,
            defaults={"name": code, "pattern": pattern, "reset_period": period, "is_active": True},
        )


@pytest.fixture
def iot_admin(api_client, registry_permissions, company):
    codes = sorted(code for code in registry_permissions if code.startswith("iot."))
    role = make_role(
        code="test_iot_admin",
        permission_codes=codes,
        data_scope_type=DataScopeType.COMPANY,
        company=company,
    )
    user = make_user(username="iot_admin_t", role=role, company=company)
    login(api_client, user)
    return api_client


@pytest.fixture
def iot_viewer(api_client, registry_permissions, company):
    role = make_role(
        code="test_iot_viewer",
        permission_codes=["iot.reading.view"],
        data_scope_type=DataScopeType.COMPANY,
        company=company,
    )
    user = make_user(username="iot_viewer_t", role=role, company=company)
    login(api_client, user)
    return api_client


def make_gateway(company, *, code="GW-01", **extra) -> IoTGateway:
    return IoTGateway.objects.create(
        company=company, code=code, name=f"网关{code}", **extra
    )


def make_point(gateway, *, code="T1", **extra) -> IoTPoint:
    return IoTPoint.objects.create(
        company=gateway.company,
        gateway=gateway,
        code=code,
        name=f"测点{code}",
        unit=extra.pop("unit", "℃"),
        **extra,
    )


def device_token(gateway) -> str:
    return services.issue_device_token(gateway)


def post_report(client, token: str, payload: dict):
    return client.post(INGEST_URL, payload, format="json", HTTP_X_DEVICE_TOKEN=token)


def test_unauthenticated_iot_access_is_denied(api_client):
    assert api_client.get(GATEWAYS_URL).status_code in (401, 403)


def test_ingest_requires_device_token(api_client, company):
    gateway = make_gateway(company)
    payload = {"message_id": "M-1", "points": [{"code": "T1", "value": "1"}]}

    missing = api_client.post(INGEST_URL, payload, format="json")
    assert missing.status_code == 401, missing.content
    assert missing.json()["code"] == "DEVICE_TOKEN_MISSING"

    wrong = api_client.post(INGEST_URL, payload, format="json", HTTP_X_DEVICE_TOKEN="ysiot_nope")
    assert wrong.status_code == 401, wrong.content
    assert wrong.json()["code"] == "DEVICE_TOKEN_INVALID"
    assert gateway.readings.count() == 0


def test_ingest_rejects_employee_session(api_client, iot_admin, company):
    """员工登录会话不能当设备凭证用：硬件上报必须走独立令牌。"""
    make_gateway(company)
    response = iot_admin.post(
        INGEST_URL, {"message_id": "M-1", "points": [{"code": "T1", "value": "1"}]}, format="json"
    )
    assert response.status_code == 401, response.content
    assert response.json()["code"] == "DEVICE_TOKEN_MISSING"
    assert not IoTReading.objects.exists()


def test_device_token_is_stored_as_hash_only(iot_admin, company):
    gateway = make_gateway(company)
    raw = device_token(gateway)
    gateway.refresh_from_db()
    assert raw.startswith("ysiot_")
    assert gateway.token_hash == services.hash_device_token(raw)
    assert raw not in gateway.token_hash
    assert len(gateway.token_hash) == 64


def test_ingest_stores_readings_and_dedupes(api_client, company):
    gateway = make_gateway(company)
    point_a = make_point(gateway, code="T1")
    point_b = make_point(gateway, code="V1", unit="V")
    token = device_token(gateway)
    moment = business_now().replace(microsecond=0)

    first = post_report(
        api_client,
        token,
        {
            "message_id": "M-100",
            "device_time": moment.isoformat(),
            "points": [
                {"code": "T1", "value": "36.500"},
                {"code": "V1", "value": "220.100"},
            ],
        },
    )
    assert first.status_code == 200, first.content
    assert first.json()["status"] == "processed"
    assert first.json()["accepted"] == 2
    assert IoTReading.objects.count() == 2
    assert IoTReading.objects.get(point=point_a).value == Decimal("36.500000")

    # 同一个 message_id 再发一次：判为重复报文，不产生新读数
    duplicated = post_report(
        api_client,
        token,
        {
            "message_id": "M-100",
            "device_time": moment.isoformat(),
            "points": [{"code": "T1", "value": "36.500"}],
        },
    )
    assert duplicated.status_code == 200, duplicated.content
    assert duplicated.json()["status"] == "duplicated"
    assert IoTReading.objects.count() == 2

    # 新的 message_id 但设备时间相同：由「测点 + 设备时间」唯一约束兜底
    same_time = post_report(
        api_client,
        token,
        {
            "message_id": "M-101",
            "device_time": moment.isoformat(),
            "points": [{"code": "T1", "value": "99.000"}],
        },
    )
    assert same_time.status_code == 200, same_time.content
    assert same_time.json()["accepted"] == 0
    assert same_time.json()["status"] == MessageStatus.FAILED
    assert IoTReading.objects.get(point=point_b).value == Decimal("220.100000")
    assert IoTReading.objects.count() == 2

    gateway.refresh_from_db()
    assert gateway.status == GatewayStatus.ONLINE
    assert gateway.last_seen_at is not None


def test_ingest_marks_simulated_payload(api_client, company):
    gateway = make_gateway(company)
    make_point(gateway, code="T1")
    token = device_token(gateway)

    response = post_report(
        api_client,
        token,
        {
            "message_id": "SIM-1",
            "simulated": True,
            "points": [{"code": "T1", "value": "20.000"}],
        },
    )
    assert response.status_code == 200, response.content
    assert response.json()["is_simulated"] is True
    reading = IoTReading.objects.get()
    assert reading.is_simulated is True
    assert reading.source == ReadingSource.SIMULATOR
    assert IoTMessage.objects.get().is_simulated is True


def test_ingest_keeps_failure_log(api_client, company):
    gateway = make_gateway(company)
    make_point(gateway, code="T1")
    token = device_token(gateway)

    response = post_report(
        api_client,
        token,
        {
            "message_id": "M-BAD",
            "points": [
                {"code": "UNKNOWN", "value": "1"},
                {"code": "T1", "value": "not-a-number"},
            ],
        },
    )
    assert response.status_code == 200, response.content
    assert response.json()["status"] == MessageStatus.FAILED
    assert response.json()["accepted"] == 0
    message = IoTMessage.objects.get()
    assert message.status == MessageStatus.FAILED
    assert "未登记" in message.error_message
    assert "不是合法数值" in message.error_message


def test_ingest_rejects_batch_overflow_and_bad_protocol(api_client, company):
    from apps.iot.models import IoTConnection, IoTProtocol

    connection = IoTConnection.objects.create(
        company=company,
        code="CN-1",
        name="HTTP 连接",
        protocol=IoTProtocol.HTTP,
        batch_limit=2,
    )
    gateway = make_gateway(company, connection=connection)
    for code in ("T1", "T2", "T3"):
        make_point(gateway, code=code)
    token = device_token(gateway)

    overflow = post_report(
        api_client,
        token,
        {
            "message_id": "M-BIG",
            "points": [
                {"code": "T1", "value": "1"},
                {"code": "T2", "value": "1"},
                {"code": "T3", "value": "1"},
            ],
        },
    )
    assert overflow.status_code == 400, overflow.content
    assert overflow.json()["code"] == "BATCH_TOO_LARGE"
    assert not IoTMessage.objects.exists()

    connection.protocol = IoTProtocol.MQTT
    connection.save(update_fields=["protocol", "updated_at"])
    unsupported = post_report(
        api_client, token, {"message_id": "M-MQTT", "points": [{"code": "T1", "value": "1"}]}
    )
    assert unsupported.status_code == 409, unsupported.content
    assert unsupported.json()["code"] == "PROTOCOL_NOT_IMPLEMENTED"


def test_ingest_is_rate_limited_per_gateway(api_client, company):
    from apps.iot.models import IoTConnection, IoTProtocol

    connection = IoTConnection.objects.create(
        company=company,
        code="CN-RL",
        name="限流连接",
        protocol=IoTProtocol.HTTP,
        rate_limit_per_minute=2,
    )
    gateway = make_gateway(company, connection=connection)
    make_point(gateway, code="T1")
    token = device_token(gateway)

    for index in range(2):
        ok = post_report(
            api_client,
            token,
            {
                "message_id": f"M-RL-{index}",
                "device_time": (business_now() + timedelta(seconds=index)).isoformat(),
                "points": [{"code": "T1", "value": str(index)}],
            },
        )
        assert ok.status_code == 200, ok.content

    blocked = post_report(
        api_client, token, {"message_id": "M-RL-X", "points": [{"code": "T1", "value": "9"}]}
    )
    assert blocked.status_code == 429, blocked.content
    assert blocked.json()["code"] == "RATE_LIMIT_EXCEEDED"
    assert blocked.json()["details"]["limit_per_minute"] == 2


def test_over_limit_creates_one_alarm_per_point(api_client, iot_code_rules, company):
    gateway = make_gateway(company)
    point = make_point(gateway, code="T1", upper_limit=Decimal("50"), lower_limit=Decimal("0"))
    token = device_token(gateway)
    moment = business_now().replace(microsecond=0)

    first = post_report(
        api_client,
        token,
        {
            "message_id": "M-AL-1",
            "device_time": moment.isoformat(),
            "points": [{"code": "T1", "value": "80.000"}],
        },
    )
    assert first.status_code == 200, first.content
    assert first.json()["alarms"] == 1

    second = post_report(
        api_client,
        token,
        {
            "message_id": "M-AL-2",
            "device_time": (moment + timedelta(minutes=5)).isoformat(),
            "points": [{"code": "T1", "value": "90.000"}],
        },
    )
    assert second.status_code == 200, second.content
    assert second.json()["alarms"] == 0

    alarms = EnergyAlarm.objects.filter(alarm_type=AlarmType.OVER_LIMIT)
    assert alarms.count() == 1
    alarm = alarms.get()
    assert alarm.source_ref == f"iot:{gateway.code}:{point.code}"
    assert "超过上限" in alarm.message
    assert alarm.triggered_value == Decimal("80.000000")


def test_offline_check_skips_simulated_gateways(iot_code_rules, company):
    real = make_gateway(company, code="GW-REAL", offline_minutes=30)
    simulated = make_gateway(company, code="GW-SIM", offline_minutes=30, is_simulated=True)
    stale = business_now() - timedelta(hours=3)
    IoTGateway.objects.filter(pk__in=[real.pk, simulated.pk]).update(last_seen_at=stale)

    result = services.detect_offline_gateways(company_id=company.pk)
    assert result["offline"] == 1
    real.refresh_from_db()
    simulated.refresh_from_db()
    assert real.status == GatewayStatus.OFFLINE
    assert simulated.status != GatewayStatus.OFFLINE
    alarms = EnergyAlarm.objects.filter(alarm_type=AlarmType.OFFLINE)
    assert alarms.count() == 1
    assert alarms.get().source_ref == f"iot:{real.code}"

    # 重复扫描不会重复报警
    services.detect_offline_gateways(company_id=company.pk)
    assert EnergyAlarm.objects.filter(alarm_type=AlarmType.OFFLINE).count() == 1


def test_recently_seen_gateway_is_not_offline(iot_code_rules, company):
    gateway = make_gateway(company, code="GW-FRESH", offline_minutes=60)
    IoTGateway.objects.filter(pk=gateway.pk).update(last_seen_at=business_now() - timedelta(minutes=5))
    result = services.detect_offline_gateways(company_id=company.pk)
    assert result["offline"] == 0
    gateway.refresh_from_db()
    assert gateway.status != GatewayStatus.OFFLINE


def test_rotate_token_invalidates_previous_token(iot_admin, api_client, company):
    gateway = make_gateway(company)
    make_point(gateway, code="T1")
    old_token = device_token(gateway)

    rotated = iot_admin.post(
        f"{GATEWAYS_URL}{gateway.pk}/rotate-token/", {"reason": "设备更换"}, format="json"
    )
    assert rotated.status_code == 200, rotated.content
    new_token = rotated.json()["token"]
    assert new_token != old_token
    assert rotated.json()["token_prefix"] == new_token[: len("ysiot_") + 6]
    assert "只在此处返回一次" in rotated.json()["note"]

    gateway.refresh_from_db()
    assert gateway.token_hash == services.hash_device_token(new_token)

    # 旧令牌立即失效
    stale = post_report(
        api_client, old_token, {"message_id": "M-OLD", "points": [{"code": "T1", "value": "1"}]}
    )
    assert stale.status_code == 401, stale.content

    fresh = post_report(
        api_client, new_token, {"message_id": "M-NEW", "points": [{"code": "T1", "value": "1"}]}
    )
    assert fresh.status_code == 200, fresh.content


def test_point_company_is_derived_from_gateway(iot_admin, company, other_company):
    gateway = make_gateway(company, code="GW-MINE")
    created = iot_admin.post(
        POINTS_URL,
        {"gateway_id": gateway.pk, "code": "T9", "name": "温度", "unit": "℃"},
        format="json",
    )
    assert created.status_code == 201, created.content
    assert created.json()["company_id"] == company.pk
    assert created.json()["gateway_code"] == gateway.code

    foreign = make_gateway(other_company, code="GW-FOREIGN")
    denied = iot_admin.post(
        POINTS_URL,
        {"gateway_id": foreign.pk, "code": "T1", "name": "越权测点"},
        format="json",
    )
    assert denied.status_code == 403, denied.content
    assert denied.json()["code"] == "OUT_OF_DATA_SCOPE"
    assert not IoTPoint.objects.filter(code="T1").exists()


def test_iot_codes_are_generated_when_omitted(iot_admin, iot_code_rules, company):
    year = business_today().year

    connection = iot_admin.post(
        CONNECTIONS_URL, {"company_id": company.pk, "name": "厂区 HTTP 连接"}, format="json"
    )
    assert connection.status_code == 201, connection.content
    assert re.fullmatch(rf"IOTCN{year}\d{{4}}", connection.json()["code"])

    gateway = iot_admin.post(
        GATEWAYS_URL, {"company_id": company.pk, "name": "1 号采集网关"}, format="json"
    )
    assert gateway.status_code == 201, gateway.content
    assert re.fullmatch(rf"IOTGW{year}\d{{4}}", gateway.json()["code"])
    assert gateway.json()["has_token"] is False

    point = iot_admin.post(
        POINTS_URL,
        {"gateway_id": gateway.json()["id"], "name": "温度", "quantity": "temperature", "unit": "℃"},
        format="json",
    )
    assert point.status_code == 201, point.content
    assert re.fullmatch(rf"IOTPT{year}\d{{4}}", point.json()["code"])


def test_iot_lists_are_company_scoped(iot_admin, company, other_company):
    mine = make_gateway(company, code="GW-MINE")
    theirs = make_gateway(other_company, code="GW-THEIRS")
    make_point(mine, code="T1")
    make_point(theirs, code="T1")

    listed = iot_admin.get(GATEWAYS_URL)
    assert listed.status_code == 200, listed.content
    assert {row["code"] for row in listed.json()["results"]} == {"GW-MINE"}
    assert iot_admin.get(f"{GATEWAYS_URL}{theirs.pk}/").status_code == 404

    points = iot_admin.get(POINTS_URL)
    assert points.status_code == 200, points.content
    assert {row["gateway_code"] for row in points.json()["results"]} == {"GW-MINE"}


def test_iot_requires_permission(iot_viewer, company):
    make_gateway(company, code="GW-PERM")
    denied = iot_viewer.get(GATEWAYS_URL)
    assert denied.status_code == 403, denied.content
    assert denied.json()["code"] == "PERMISSION_DENIED"
    assert iot_viewer.get(READINGS_URL).status_code == 200


def test_device_monitor_returns_status_and_latest_readings(iot_admin, company):
    gateway = make_gateway(company, code="GW-MON", offline_minutes=30)
    point = make_point(gateway, code="T1", upper_limit=Decimal("50"))
    IoTReading.objects.create(
        company=company,
        gateway=gateway,
        point=point,
        device_time=business_now().replace(microsecond=0),
        received_at=business_now(),
        value=Decimal("80.000"),
        unit="℃",
    )
    IoTMessage.objects.create(
        company=company,
        gateway=gateway,
        message_id="M-MON",
        received_at=business_now(),
        status=MessageStatus.FAILED,
        error_message="测点未登记",
    )

    response = iot_admin.get(MONITOR_URL)
    assert response.status_code == 200, response.content
    body = response.json()
    assert body["summary"]["gateway_total"] == 1
    assert body["summary"]["failed_messages_24h"] == 1
    row = body["gateways"][0]
    assert row["code"] == "GW-MON"
    assert row["points"][0]["latest_value"] == "80.000000"
    assert row["points"][0]["is_over_limit"] is True
    assert body["recent_readings"][0]["point_code"] == "T1"


def make_reading(gateway, point, *, value: str, device_time, is_simulated: bool = False):
    return IoTReading.objects.create(
        company=gateway.company,
        gateway=gateway,
        point=point,
        device_time=device_time,
        received_at=device_time,
        value=Decimal(value),
        unit=point.unit,
        is_simulated=is_simulated,
    )


def test_statistics_requires_reading_permission(api_client, registry_permissions, company):
    """采集统计与采集读数同权限：只有监控权限的账号既看不到统计，也看不到读数明细。"""
    role = make_role(
        code="test_iot_monitor_only",
        permission_codes=["iot.monitor.view"],
        data_scope_type=DataScopeType.COMPANY,
        company=company,
    )
    user = make_user(username="iot_monitor_only_t", role=role, company=company)
    login(api_client, user)

    denied = api_client.get(STATISTICS_URL)
    assert denied.status_code == 403, denied.content
    assert denied.json()["code"] == "PERMISSION_DENIED"
    assert api_client.get(READINGS_URL).status_code == 403
    assert api_client.get(MONITOR_URL).status_code == 200


def test_statistics_buckets_by_business_timezone(iot_viewer, company):
    """按天分桶以业务时区为界：UTC 15:30 与 17:30 同属 UTC 的 09-20，却分属上海的两天。"""
    gateway = make_gateway(company, code="GW-STAT")
    point = make_point(gateway, code="T1", upper_limit=Decimal("50"))
    make_reading(
        gateway, point, value="36.500", device_time=datetime(2026, 9, 20, 15, 30, tzinfo=UTC)
    )
    make_reading(
        gateway, point, value="41.500", device_time=datetime(2026, 9, 20, 17, 30, tzinfo=UTC)
    )
    make_reading(
        gateway, point, value="60.000", device_time=datetime(2026, 9, 20, 18, 0, tzinfo=UTC)
    )

    response = iot_viewer.get(
        STATISTICS_URL, {"granularity": "day", "since": "2026-09-19", "until": "2026-09-21"}
    )
    assert response.status_code == 200, response.content
    body = response.json()
    assert body["granularity"] == "day"
    assert body["totals"]["sample_count"] == 3
    assert body["totals"]["point_count"] == 1
    # 桶起点是「上海当天 00:00」对应的 UTC 时刻
    assert [row["bucket"] for row in body["rows"]] == [
        "2026-09-20T16:00:00+00:00",
        "2026-09-19T16:00:00+00:00",
    ]
    newest, older = body["rows"]
    assert newest["sample_count"] == 2
    assert newest["value_sum"] == "101.500000"
    assert newest["value_min"] == "41.500000"
    assert newest["value_max"] == "60.000000"
    assert newest["value_avg"] == "50.750000"
    assert newest["is_over_limit"] is True
    assert older["sample_count"] == 1
    assert older["is_over_limit"] is False
    assert body["buckets"][0]["bucket"] == "2026-09-20T16:00:00+00:00"
    assert body["buckets"][0]["sample_count"] == 2
    # 统计读的是明细，不落汇总表：删掉明细后统计跟着变
    IoTReading.objects.filter(device_time__gte=datetime(2026, 9, 20, 17, 0, tzinfo=UTC)).delete()
    after = iot_viewer.get(
        STATISTICS_URL, {"granularity": "day", "since": "2026-09-19", "until": "2026-09-21"}
    ).json()
    assert after["totals"]["sample_count"] == 1


def test_statistics_filters_and_simulated_flag(iot_viewer, company):
    """按设备 / 测点 / 模拟标识过滤，并单独统计模拟样本。"""
    gateway = make_gateway(company, code="GW-STAT2")
    other = make_gateway(company, code="GW-STAT3")
    point = make_point(gateway, code="T1")
    other_point = make_point(other, code="T2")
    # 取「上一个完整小时」作为锚点，保证四条读数落在同一个小时桶里
    anchor = (business_now() - timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
    make_reading(gateway, point, value="10.000", device_time=anchor + timedelta(minutes=10))
    make_reading(gateway, point, value="12.000", device_time=anchor + timedelta(minutes=20))
    make_reading(
        gateway,
        point,
        value="11.000",
        device_time=anchor + timedelta(minutes=30),
        is_simulated=True,
    )
    make_reading(other, other_point, value="99.000", device_time=anchor + timedelta(minutes=40))

    all_rows = iot_viewer.get(STATISTICS_URL, {"granularity": "hour"}).json()
    assert all_rows["totals"]["sample_count"] == 4
    assert all_rows["totals"]["gateway_count"] == 2
    assert all_rows["totals"]["simulated_count"] == 1
    assert len(all_rows["buckets"]) == 1

    filtered = iot_viewer.get(
        STATISTICS_URL, {"granularity": "hour", "gateway_id": gateway.pk, "point_id": point.pk}
    ).json()
    assert filtered["totals"]["sample_count"] == 3
    assert filtered["totals"]["gateway_count"] == 1
    bucket = filtered["rows"][0]
    assert bucket["sample_count"] == 3
    assert bucket["simulated_count"] == 1
    assert bucket["value_min"] == "10.000000"
    assert bucket["value_max"] == "12.000000"
    assert bucket["value_avg"] == "11.000000"
    assert bucket["is_simulated"] is False  # 同一桶里混有真实读数时不标成「纯模拟」

    only_real = iot_viewer.get(STATISTICS_URL, {"granularity": "hour", "is_simulated": "false"}).json()
    assert only_real["totals"]["sample_count"] == 3
    assert only_real["totals"]["simulated_count"] == 0


def test_statistics_rejects_bad_granularity_and_wide_range(iot_viewer, company):
    unsupported = iot_viewer.get(STATISTICS_URL, {"granularity": "week"})
    assert unsupported.status_code == 400, unsupported.content
    assert unsupported.json()["code"] == "GRANULARITY_NOT_SUPPORTED"

    too_wide = iot_viewer.get(
        STATISTICS_URL, {"granularity": "hour", "since": "2026-01-01", "until": "2026-06-01"}
    )
    assert too_wide.status_code == 400, too_wide.content
    assert too_wide.json()["code"] == "TIME_RANGE_TOO_WIDE"

    inverted = iot_viewer.get(
        STATISTICS_URL, {"granularity": "day", "since": "2026-06-01", "until": "2026-05-01"}
    )
    assert inverted.status_code == 400, inverted.content
    assert inverted.json()["code"] == "INVALID_TIME_RANGE"

    # 非法时间不被静默当成「没传」：宁可报错，也不给一个用户没要过的区间
    bad_time = iot_viewer.get(STATISTICS_URL, {"granularity": "day", "since": "上个月"})
    assert bad_time.status_code == 400, bad_time.content
    assert bad_time.json()["code"] == "INVALID_TIME_RANGE"


def test_statistics_is_company_scoped(iot_viewer, company, other_company):
    mine = make_gateway(company, code="GW-SCOPE")
    theirs = make_gateway(other_company, code="GW-SCOPE-THEIRS")
    make_reading(mine, make_point(mine, code="T1"), value="1.000", device_time=business_now())
    make_reading(theirs, make_point(theirs, code="T1"), value="2.000", device_time=business_now())

    body = iot_viewer.get(STATISTICS_URL, {"granularity": "day"}).json()
    assert body["totals"]["sample_count"] == 1
    assert {row["gateway_code"] for row in body["rows"]} == {"GW-SCOPE"}


def test_device_monitor_picks_latest_reading_per_point(iot_admin, company):
    """监控页的「最新读数」必须取每个测点最新的一条（含无读数的测点）。"""
    gateway = make_gateway(company, code="GW-LATEST")
    silent = make_point(gateway, code="T0")
    point = make_point(gateway, code="T1")
    moment = business_now().replace(microsecond=0)
    make_reading(gateway, point, value="1.000", device_time=moment - timedelta(hours=3))
    make_reading(gateway, point, value="2.000", device_time=moment - timedelta(hours=2))
    make_reading(gateway, point, value="3.000", device_time=moment - timedelta(hours=1))

    body = iot_admin.get(MONITOR_URL).json()
    points = {row["code"]: row for row in body["gateways"][0]["points"]}
    assert points["T1"]["latest_value"] == "3.000000"
    # 接口按 UTC 输出时间戳（前端负责转本地显示）：这里比对**时刻**而不是
    # 本地日期的字符串前缀，否则在北京时间 00:00~09:00 之间跑用例会因
    # 「UTC 日期与本地日期不同」而误报失败。
    latest_device_time = datetime.fromisoformat(points["T1"]["latest_device_time"])
    assert latest_device_time == (moment - timedelta(hours=1)).astimezone(UTC)
    assert points["T0"]["latest_value"] is None
    assert points["T0"]["latest_device_time"] is None
    assert silent.pk  # 没有读数的测点也要出现在监控里，而不是被跳过


def test_simulator_command_marks_data_as_simulated(iot_code_rules, company):
    from django.core.management import call_command

    make_gateway(company, code="GW-CMD", is_simulated=True)
    gateway = IoTGateway.objects.get(code="GW-CMD")
    make_point(gateway, code="T1", range_min=Decimal("0"), range_max=Decimal("50"))

    call_command("iot_simulate", "--gateway", "GW-CMD", "--rounds", "1", company=company.pk)
    reading = IoTReading.objects.get()
    assert reading.is_simulated is True
    assert reading.source == ReadingSource.SIMULATOR
    assert Decimal("0") <= reading.value <= Decimal("50")

    call_command("iot_offline_check", "--company", str(company.pk))
    # 模拟设备不参与离线判定
    assert not EnergyAlarm.objects.filter(alarm_type=AlarmType.OFFLINE).exists()


def test_meta_exposes_iot_enums(iot_admin):
    response = iot_admin.get(META_URL)
    assert response.status_code == 200, response.content
    body = response.json()
    for key in (
        "iot_protocols",
        "iot_gateway_types",
        "iot_gateway_statuses",
        "iot_point_quantities",
        "iot_message_statuses",
        "iot_reading_qualities",
        "iot_reading_sources",
    ):
        assert body.get(key), f"meta 缺少枚举 {key}"
    assert {item["value"] for item in body["iot_gateway_statuses"]} >= {"online", "offline"}
    assert {item["value"] for item in body["iot_message_statuses"]} == {
        "received",
        "processed",
        "duplicated",
        "failed",
    }
