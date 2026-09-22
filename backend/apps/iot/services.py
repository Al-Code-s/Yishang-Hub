"""设备数采业务服务。

这一层负责三件事，全部与 ``docs/hardware-integration.md`` 的「首版必须实现」一一对应：

1. **设备独立凭证**：``issue_device_token`` 生成明文令牌只返回一次，库里只留 SHA-256
   摘要；``authenticate_device`` 用摘要比对识别网关，**不复用员工登录会话**；
2. **HTTP 采集入口的规则**：``ingest_report`` 负责协议校验、批次上限、按网关限流、
   报文判重、读数标准化（含「测点 + 设备时间」二次去重）与失败留痕；
3. **越限 / 离线报警**：统一调用 ``apps/ems/services.py::raise_alarm`` 写入能源报警台账，
   本模块不直接写 EMS 的表。

未实现的协议（MQTT / Modbus）在这里**明确拒绝**：宁可报「该协议尚未实现」，
也不接受一个没人解析的报文然后假装采集成功。
"""

from __future__ import annotations

import hashlib
import json
import secrets
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.core.exceptions import (
    NotAuthenticated,
    StateConflict,
    TooManyRequests,
    ValidationFailed,
)
from apps.core.services import business_now, generate_code
from apps.ems.models import AlarmType
from apps.ems.services import raise_alarm
from apps.iot.models import (
    GatewayStatus,
    IoTGateway,
    IoTMessage,
    IoTPoint,
    IoTProtocol,
    IoTReading,
    MessageStatus,
    ReadingQuality,
    ReadingSource,
)

CONNECTION_CODE_RULE = "IOTCN"
GATEWAY_CODE_RULE = "IOTGW"
POINT_CODE_RULE = "IOTPT"

TOKEN_PREFIX = "ysiot_"
DEFAULT_BATCH_LIMIT = 200
SUPPORTED_PROTOCOLS = {IoTProtocol.HTTP, IoTProtocol.SIMULATOR}

# 越限报警去重窗口：同一测点一小时内只报一次，避免高频采集把报警刷满屏
LIMIT_ALARM_WINDOW = timedelta(hours=1)


def next_connection_code() -> str:
    """数采连接编码（编码规则 ``IOTCN``）。"""
    return generate_code(CONNECTION_CODE_RULE)


def next_gateway_code() -> str:
    """数采设备编码（编码规则 ``IOTGW``）。"""
    return generate_code(GATEWAY_CODE_RULE)


def next_point_code() -> str:
    """测点编码（编码规则 ``IOTPT``）。"""
    return generate_code(POINT_CODE_RULE)


# ---------------------------------------------------------------------------
# 设备凭证
# ---------------------------------------------------------------------------


def hash_device_token(raw_token: str) -> str:
    """设备令牌的存储形式：SHA-256 摘要（不保存明文）。"""
    return hashlib.sha256((raw_token or "").encode("utf-8")).hexdigest()


def issue_device_token(gateway: IoTGateway, *, rotated_at: datetime | None = None) -> str:
    """生成（或轮换）设备令牌，返回**明文**；库里只留摘要与前缀。

    明文令牌只在这一个返回值里出现，平台不再保存；界面提示用户立即保存。
    轮换即时生效：旧令牌的摘要被覆盖，旧令牌立即失效。
    """
    raw_token = f"{TOKEN_PREFIX}{secrets.token_urlsafe(32)}"
    gateway.token_hash = hash_device_token(raw_token)
    gateway.token_prefix = raw_token[: len(TOKEN_PREFIX) + 6]
    gateway.token_rotated_at = rotated_at or business_now()
    gateway.save(update_fields=["token_hash", "token_prefix", "token_rotated_at", "updated_at"])
    return raw_token


def authenticate_device(raw_token: str) -> IoTGateway:
    """按设备令牌识别网关。

    令牌无效、设备停用或设备已停用时抛 401；这里**不**接受员工账号会话，
    硬件接入与人员登录是两套凭证。
    """
    token = (raw_token or "").strip()
    if not token:
        raise NotAuthenticated("缺少设备令牌。", code="DEVICE_TOKEN_MISSING")
    gateway = IoTGateway.objects.filter(token_hash=hash_device_token(token)).select_related(
        "connection"
    ).first()
    if gateway is None:
        raise NotAuthenticated("设备令牌无效。", code="DEVICE_TOKEN_INVALID")
    if not gateway.is_active:
        raise NotAuthenticated("该数采设备已停用。", code="DEVICE_DISABLED")
    return gateway


# ---------------------------------------------------------------------------
# 采集入口
# ---------------------------------------------------------------------------


def _parse_device_time(value: Any, fallback: datetime) -> datetime:
    if value in (None, ""):
        return fallback
    if isinstance(value, datetime):
        parsed = value
    else:
        text = str(value).strip().replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError as exc:
            raise ValidationFailed(
                "device_time 必须是 ISO 8601 时间字符串。", code="DEVICE_TIME_INVALID"
            ) from exc
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
    return parsed


def enforce_rate_limit(gateway: IoTGateway, *, now: datetime | None = None) -> None:
    """按网关限流：统计最近一分钟的报文数，超过连接配置的上限即拒绝（429）。"""
    connection = gateway.connection
    limit = connection.rate_limit_per_minute if connection is not None else 0
    if not limit:
        return
    moment = now or business_now()
    recent = IoTMessage.objects.filter(
        gateway=gateway, received_at__gte=moment - timedelta(minutes=1)
    ).count()
    if recent >= limit:
        raise TooManyRequests(
            f"该设备一分钟内上报次数已达上限（{limit} 次/分钟）。",
            code="RATE_LIMIT_EXCEEDED",
            details={"limit_per_minute": limit},
        )


@transaction.atomic
def ingest_report(
    gateway: IoTGateway, payload: dict[str, Any], *, source_ip: str | None = None
) -> dict[str, Any]:
    """接收一次 HTTP 上报，返回处理结果摘要。

    流程：协议与批次校验 → 限流 → 报文判重 → 逐点标准化 → 越限判定 → 更新时间戳。
    任何一步失败都会留下一条 ``IoTMessage``（状态为失败或重复），
    保证「设备说发了」与「平台收到了什么」可以对照。
    """
    if not isinstance(payload, dict):
        raise ValidationFailed("报文必须是 JSON 对象。", code="PAYLOAD_INVALID")
    try:
        json.dumps(payload)
    except TypeError as exc:
        # 原始报文要原样存档，不能存进一个序列化不了的 datetime 然后在查询时报错
        raise ValidationFailed(
            "报文必须是可序列化的 JSON 对象（时间请用 ISO 8601 字符串）。",
            code="PAYLOAD_INVALID",
        ) from exc

    connection = gateway.connection
    if connection is not None:
        if not connection.is_enabled:
            raise StateConflict("该连接已停用采集。", code="CONNECTION_DISABLED")
        if connection.protocol not in SUPPORTED_PROTOCOLS:
            raise StateConflict(
                f"协议「{connection.get_protocol_display()}」的采集适配尚未实现，"
                "首版只支持 HTTP 上报与内置模拟器。",
                code="PROTOCOL_NOT_IMPLEMENTED",
                details={"protocol": connection.protocol},
            )

    message_id = str(payload.get("message_id") or "").strip()
    if not message_id:
        raise ValidationFailed("报文必须携带 message_id（用于判重）。", code="MESSAGE_ID_REQUIRED")

    points = payload.get("points")
    if not isinstance(points, list) or not points:
        raise ValidationFailed("报文必须包含至少一个测点读数。", code="POINTS_REQUIRED")

    batch_limit = connection.batch_limit if connection is not None else DEFAULT_BATCH_LIMIT
    if len(points) > batch_limit:
        raise ValidationFailed(
            f"单次上报测点数（{len(points)}）超过上限 {batch_limit} 条。",
            code="BATCH_TOO_LARGE",
            details={"batch_limit": batch_limit, "received": len(points)},
        )

    now = business_now()
    enforce_rate_limit(gateway, now=now)

    device_time = _parse_device_time(payload.get("device_time"), now)
    is_simulated = bool(
        payload.get("simulated")
        or gateway.is_simulated
        or (connection is not None and connection.is_simulated)
    )

    message = IoTMessage.objects.create(
        company_id=gateway.company_id,
        gateway=gateway,
        message_id=message_id[:64],
        received_at=now,
        device_time=device_time,
        source_ip=source_ip or None,
        payload=payload,
        point_count=len(points),
        status=MessageStatus.RECEIVED,
        is_simulated=is_simulated,
    )

    if IoTMessage.objects.filter(gateway=gateway, message_id=message_id[:64]).exclude(
        pk=message.pk
    ).exists():
        message.status = MessageStatus.DUPLICATED
        message.error_message = "该 message_id 之前已接收过，本次不重复入库。"
        message.save(update_fields=["status", "error_message", "updated_at"])
        return {
            "message_id": message.message_id,
            "status": message.status,
            "accepted": 0,
            "skipped": len(points),
            "alarms": [],
            "note": "重复报文：已按去重规则忽略。",
        }

    point_map = {
        point.code: point
        for point in IoTPoint.objects.filter(gateway=gateway, is_active=True)
    }
    accepted = 0
    problems: list[str] = []
    alarm_count = 0

    for item in points:
        if not isinstance(item, dict):
            problems.append("测点条目不是对象")
            continue
        code = str(item.get("code") or "").strip()
        point = point_map.get(code)
        if point is None:
            problems.append(f"测点 {code or '?'} 未登记或已停用")
            continue
        try:
            value = Decimal(str(item.get("value")))
        except (InvalidOperation, TypeError, ValueError):
            problems.append(f"测点 {code} 的读数不是合法数值")
            continue

        reading, created = IoTReading.objects.get_or_create(
            point=point,
            device_time=device_time,
            defaults={
                "company_id": gateway.company_id,
                "gateway": gateway,
                "message": message,
                "received_at": now,
                "value": value,
                "unit": point.unit,
                "quality": ReadingQuality.GOOD,
                "source": ReadingSource.SIMULATOR if is_simulated else ReadingSource.DEVICE,
                "is_simulated": is_simulated,
            },
        )
        if not created:
            problems.append(f"测点 {code} 在该设备时间已有读数，按去重规则跳过")
            continue
        accepted += 1
        alarm_count += len(evaluate_point_limits(reading, point=point))

    if accepted and not problems:
        message.status = MessageStatus.PROCESSED
        message.error_message = ""
    elif accepted:
        message.status = MessageStatus.PROCESSED
        message.error_message = "；".join(problems)[:255]
    else:
        message.status = MessageStatus.FAILED
        message.error_message = "；".join(problems)[:255] or "没有可入库的读数"
    message.save(update_fields=["status", "error_message", "updated_at"])

    gateway.last_seen_at = now
    gateway.status = GatewayStatus.ONLINE
    gateway.save(update_fields=["last_seen_at", "status", "updated_at"])

    return {
        "message_id": message.message_id,
        "status": message.status,
        "accepted": accepted,
        "skipped": len(points) - accepted,
        "alarms": alarm_count,
        "problems": problems,
        "is_simulated": is_simulated,
    }


# ---------------------------------------------------------------------------
# 越限报警
# ---------------------------------------------------------------------------


def evaluate_point_limits(reading: IoTReading, *, point: IoTPoint | None = None) -> list[Any]:
    """按测点上下限判定越限并报警（同一测点一小时内只报一次）。"""
    target = point or reading.point
    if not target.alarm_enabled:
        return []

    alarms: list[Any] = []
    source_ref = f"iot:{target.gateway.code}:{target.code}"
    value = reading.value

    if target.upper_limit is not None and value > target.upper_limit:
        alarm = raise_alarm(
            company_id=reading.company_id,
            alarm_type=AlarmType.OVER_LIMIT,
            message=(
                f"【数采】{target.name}（{target.code}）读数 {value} 超过上限 "
                f"{target.upper_limit}"
            ),
            occurred_at=reading.device_time,
            triggered_value=value,
            threshold_value=target.upper_limit,
            source_ref=source_ref,
            dedupe_window=LIMIT_ALARM_WINDOW,
        )
        if alarm is not None:
            alarms.append(alarm)

    if target.lower_limit is not None and value < target.lower_limit:
        alarm = raise_alarm(
            company_id=reading.company_id,
            alarm_type=AlarmType.OVER_LIMIT,
            message=(
                f"【数采】{target.name}（{target.code}）读数 {value} 低于下限 "
                f"{target.lower_limit}"
            ),
            occurred_at=reading.device_time,
            triggered_value=value,
            threshold_value=target.lower_limit,
            source_ref=source_ref,
            dedupe_window=LIMIT_ALARM_WINDOW,
        )
        if alarm is not None:
            alarms.append(alarm)

    return alarms


# ---------------------------------------------------------------------------
# 离线检测
# ---------------------------------------------------------------------------


@transaction.atomic
def detect_offline_gateways(*, company_id: int | None = None, now: datetime | None = None) -> dict[str, Any]:
    """扫描超时未上报的设备，置为离线并报警。

    由 ``manage.py iot_offline_check`` 调用（可由计划任务定时触发）。
    平台不假装「实时」：判定依据就是「最后一次上报时间」与设备自身配置的离线阈值。
    """
    moment = now or business_now()
    queryset = IoTGateway.objects.filter(
        is_active=True, offline_minutes__gt=0, is_simulated=False
    ).exclude(status=GatewayStatus.DISABLED)
    if company_id is not None:
        queryset = queryset.filter(company_id=company_id)

    offline: list[IoTGateway] = []
    alarms = 0
    for gateway in queryset.select_related("connection"):
        last_seen = gateway.last_seen_at
        threshold = timedelta(minutes=gateway.offline_minutes)
        if last_seen is not None and moment - last_seen <= threshold:
            continue
        # 从未上报过的设备：以建档时间为起点，超过阈值同样算离线
        if (
            last_seen is None
            and gateway.created_at is not None
            and moment - gateway.created_at.replace(microsecond=0) <= threshold
        ):
            continue
        if gateway.status != GatewayStatus.OFFLINE:
            gateway.status = GatewayStatus.OFFLINE
            gateway.save(update_fields=["status", "updated_at"])
        offline.append(gateway)
        alarm = raise_alarm(
            company_id=gateway.company_id,
            alarm_type=AlarmType.OFFLINE,
            message=f"【数采】设备 {gateway.name}（{gateway.code}）超过 {gateway.offline_minutes} 分钟未上报",
            occurred_at=moment,
            source_ref=f"iot:{gateway.code}",
            dedupe_window=timedelta(hours=1),
        )
        if alarm is not None:
            alarms += 1

    return {"checked_at": moment, "offline": len(offline), "alarms": alarms}


__all__ = [
    "authenticate_device",
    "detect_offline_gateways",
    "enforce_rate_limit",
    "evaluate_point_limits",
    "hash_device_token",
    "ingest_report",
    "issue_device_token",
    "next_connection_code",
    "next_gateway_code",
    "next_point_code",
]
