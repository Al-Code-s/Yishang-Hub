"""公共业务服务：审计、发件箱、编码规则、幂等、乐观锁。

约定：所有写操作的服务函数必须由 View 层显式调用，不使用 signals 隐式触发关键业务。
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from collections.abc import Callable, Iterable, Mapping, Sequence
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db import IntegrityError, models, transaction
from django.db.models import F
from django.utils import timezone

from apps.core.exceptions import (
    APIError,
    IdempotencyConflict,
    ObjectNotFound,
    OptimisticLockConflict,
    StateConflict,
    ValidationFailed,
)
from apps.core.logging import (
    get_current_user,
    get_request_id,
    get_request_ip,
    get_user_agent,
)
from apps.core.models import (
    AuditAction,
    AuditLog,
    CodeRule,
    CodeSequence,
    IdempotencyRecord,
    Notification,
    OutboxEvent,
    OutboxStatus,
    ResetPeriod,
)

logger = logging.getLogger("yishang.audit")

# --------------------------------------------------------------------------
# 时间
# --------------------------------------------------------------------------


def business_timezone() -> ZoneInfo:
    return ZoneInfo(settings.YISHANG["BUSINESS_TIME_ZONE"])


def business_now() -> datetime:
    """业务界面时区的当前时间（存储仍是 UTC）。"""
    return timezone.now().astimezone(business_timezone())


def business_today() -> date:
    return business_now().date()


# --------------------------------------------------------------------------
# 审计
# --------------------------------------------------------------------------


def serialise_value(value: Any) -> Any:
    """把字段值转为可 JSON 序列化的形式，供审计摘要使用。"""
    if value is None or isinstance(value, bool | int | float | str):
        return value
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, models.Model):
        return str(value.pk)
    if isinstance(value, Mapping):
        return {str(k): serialise_value(v) for k, v in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, str | bytes):
        return [serialise_value(item) for item in value]
    return str(value)


def snapshot_fields(instance: models.Model, fields: Iterable[str]) -> dict[str, Any]:
    """按字段名抓取快照，用于计算变更摘要。"""
    snapshot: dict[str, Any] = {}
    for field in fields:
        value = getattr(instance, field, None)
        snapshot[field] = serialise_value(value)
    return snapshot


def build_changes(before: Mapping[str, Any], after: Mapping[str, Any]) -> dict[str, Any]:
    """比较前后快照，返回 {字段: {"before": x, "after": y}}。"""
    changes: dict[str, Any] = {}
    for key in after:
        old = before.get(key)
        new = after[key]
        if old != new:
            changes[key] = {"before": old, "after": new}
    return changes


def record_audit(
    *,
    action: str | AuditAction,
    instance: models.Model | None = None,
    object_type: str = "",
    object_id: str = "",
    object_repr: str = "",
    changes: Mapping[str, Any] | None = None,
    reason: str = "",
    approval_basis: str = "",
    company: models.Model | None = None,
    actor: models.Model | None = None,
) -> AuditLog:
    """写入审计日志。

    必须在与业务操作相同的事务内调用，保证业务成功即审计成功。
    """
    user = actor if actor is not None else get_current_user()

    if instance is not None:
        meta = instance._meta
        object_type = object_type or f"{meta.app_label}.{meta.object_name}"
        object_id = object_id or str(instance.pk)
        object_repr = object_repr or str(instance)
        if company is None:
            company = getattr(instance, "company", None)

    if company is None and user is not None:
        company = getattr(user, "company", None)

    log = AuditLog(
        request_id=get_request_id(),
        action=str(action),
        actor=user if getattr(user, "pk", None) else None,
        actor_username=getattr(user, "username", "") or "",
        actor_name=getattr(user, "display_name", "") or "",
        company=company if getattr(company, "pk", None) else None,
        object_type=object_type[:128],
        object_id=str(object_id)[:64],
        object_repr=object_repr[:255],
        changes=serialise_value(dict(changes)) if changes else {},
        reason=reason,
        approval_basis=approval_basis[:255],
        ip_address=get_request_ip() or None,
        user_agent=get_user_agent()[:255],
    )
    log.save()
    return log


# --------------------------------------------------------------------------
# 发件箱
# --------------------------------------------------------------------------


def publish_event(
    *,
    event_type: str,
    aggregate_type: str,
    aggregate_id: Any,
    payload: Mapping[str, Any] | None = None,
    dedup_key: str | None = None,
) -> OutboxEvent:
    """写入发件箱事件。必须与业务数据在同一事务内调用。"""
    data = serialise_value(dict(payload or {}))
    event = OutboxEvent(
        event_type=event_type,
        aggregate_type=aggregate_type,
        aggregate_id=str(aggregate_id),
        payload=data,
        dedup_key=dedup_key,
    )
    try:
        with transaction.atomic():
            event.save()
    except IntegrityError:
        # dedup_key 冲突：同一业务动作重复发事件，直接复用既有事件
        if dedup_key:
            existing = OutboxEvent.objects.filter(dedup_key=dedup_key).first()
            if existing is not None:
                return existing
        raise
    return event


def mark_event_done(event: OutboxEvent) -> None:
    event.status = OutboxStatus.DONE
    event.processed_at = timezone.now()
    event.last_error = ""
    event.save(update_fields=["status", "processed_at", "last_error"])


def mark_event_failed(event: OutboxEvent, error: str) -> None:
    event.attempts = (event.attempts or 0) + 1
    event.last_error = error[:2000]
    if event.attempts >= event.max_attempts:
        event.status = OutboxStatus.DEAD
        event.next_retry_at = None
    else:
        event.status = OutboxStatus.FAILED
        # 退避重试：10s, 20s, 40s ...
        delay = 10 * (2 ** (event.attempts - 1))
        event.next_retry_at = timezone.now() + timedelta(seconds=delay)
    event.save(update_fields=["attempts", "last_error", "status", "next_retry_at"])


def requeue_event(event: OutboxEvent) -> OutboxEvent:
    """人工重放：重置为待处理，保留历史尝试次数以便追溯。"""
    event.status = OutboxStatus.PENDING
    event.next_retry_at = timezone.now()
    event.last_error = ""
    event.save(update_fields=["status", "next_retry_at", "last_error"])
    return event


# --------------------------------------------------------------------------
# 通知
# --------------------------------------------------------------------------


def create_notification(
    *,
    recipient: models.Model,
    title: str,
    body: str = "",
    biz_type: str = "",
    biz_id: Any = "",
    source_event_id: Any = None,
) -> Notification | None:
    """创建站内通知。

    source_event_id 唯一约束保证 Outbox 至少一次投递下不会重复产生通知。
    """
    try:
        with transaction.atomic():
            return Notification.objects.create(
                recipient=recipient,
                title=title[:200],
                body=body,
                biz_type=biz_type[:128],
                biz_id=str(biz_id)[:64],
                source_event_id=source_event_id,
            )
    except IntegrityError:
        return None


# --------------------------------------------------------------------------
# 编码规则
# --------------------------------------------------------------------------

_SEQ_PATTERN = re.compile(r"\{SEQ:(\d+)\}")
_SEQ_ANY_PATTERN = re.compile(r"\{SEQ(?::\d+)?\}")
_DATE_TOKENS = ("{YYYYMMDD}", "{YYYYMM}", "{YYYY}", "{YY}", "{MM}", "{DD}")


def _period_key(reset_period: str, on_date: date) -> str:
    if reset_period == ResetPeriod.DAILY:
        return f"{on_date:%Y%m%d}"
    if reset_period == ResetPeriod.MONTHLY:
        return f"{on_date:%Y%m}"
    if reset_period == ResetPeriod.YEARLY:
        return f"{on_date:%Y}"
    return "ALL"


def assert_code_pattern_supported(pattern: str) -> None:
    """校验编号格式：必须含流水占位符，且不含未识别的占位符。

    没有流水占位符的格式无法保证编号唯一，必须在配置阶段就拒绝，
    否则会在业务单据落库时才以唯一约束冲突的形式暴露。
    """
    if not _SEQ_ANY_PATTERN.search(pattern):
        raise ValidationFailed(
            "编号格式必须包含流水占位符 {SEQ} 或 {SEQ:n}，否则无法保证编号唯一。",
            code="CODE_PATTERN_SEQ_REQUIRED",
        )
    probe = pattern
    for token in _DATE_TOKENS:
        probe = probe.replace(token, "")
    probe = _SEQ_ANY_PATTERN.sub("", probe)
    unknown = re.findall(r"\{[^}]*\}", probe)
    if unknown:
        raise ValidationFailed(
            f"编号格式存在未识别的占位符：{'、'.join(sorted(set(unknown)))}；"
            "支持的占位符为 {YYYYMMDD}、{YYYYMM}、{YYYY}、{YY}、{MM}、{DD}、{SEQ}、{SEQ:n}。",
            code="INVALID_CODE_PATTERN",
        )


def _render_pattern(pattern: str, on_date: date, sequence: int) -> str:
    assert_code_pattern_supported(pattern)
    rendered = pattern
    rendered = rendered.replace("{YYYYMMDD}", f"{on_date:%Y%m%d}")
    rendered = rendered.replace("{YYYYMM}", f"{on_date:%Y%m}")
    rendered = rendered.replace("{YYYY}", f"{on_date:%Y}")
    rendered = rendered.replace("{YY}", f"{on_date:%y}")
    rendered = rendered.replace("{MM}", f"{on_date:%m}")
    rendered = rendered.replace("{DD}", f"{on_date:%d}")
    rendered = _SEQ_PATTERN.sub(lambda m: str(sequence).zfill(int(m.group(1))), rendered)
    rendered = rendered.replace("{SEQ}", str(sequence))
    return rendered


@transaction.atomic
def generate_code(rule_code: str, *, on_date: date | None = None) -> str:
    """按编码规则取号。

    先锁定规则行再锁定流水行，固定加锁顺序以降低死锁风险；
    流水行不存在时依赖 (rule, period_key) 唯一约束 + get_or_create 并发安全创建。
    """
    rule = (
        CodeRule.objects.select_for_update()
        .filter(code=rule_code, is_active=True)
        .first()
    )
    if rule is None:
        raise ObjectNotFound(
            f"编码规则不存在或已停用：{rule_code}",
            code="CODE_RULE_NOT_FOUND",
        )

    target_date = on_date or business_today()
    key = _period_key(rule.reset_period, target_date)
    CodeSequence.objects.get_or_create(rule=rule, period_key=key)
    sequence = CodeSequence.objects.select_for_update().get(rule=rule, period_key=key)

    next_value = (sequence.last_value or 0) + 1
    sequence.last_value = next_value
    sequence.save(update_fields=["last_value", "updated_at"])

    return _render_pattern(rule.pattern, target_date, next_value)


# --------------------------------------------------------------------------
# 乐观锁
# --------------------------------------------------------------------------


def assert_version(instance: models.Model, expected: int | None) -> None:
    """校验客户端提交的版本号，用于乐观并发控制。"""
    if expected is None:
        return
    current = getattr(instance, "version", None)
    if current is None:
        return
    if int(expected) != int(current):
        raise OptimisticLockConflict(
            details={
                "object": str(instance.pk),
                "expected_version": int(expected),
                "current_version": int(current),
            }
        )


def bump_version(instance: models.Model) -> None:
    """在并发更新路径上原子自增版本号。"""
    type(instance).objects.filter(pk=instance.pk).update(version=F("version") + 1)
    instance.refresh_from_db(fields=["version"])


# --------------------------------------------------------------------------
# 幂等
# --------------------------------------------------------------------------


def _hash_payload(payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def idempotent_execute(
    *,
    scope: str,
    key: str | None,
    payload: Any,
    func: Callable[[], tuple[int, dict[str, Any]]],
    user: models.Model | None = None,
) -> tuple[int, dict[str, Any], bool]:
    """按幂等标识执行操作。

    返回 (HTTP 状态码, 响应体, 是否为历史结果重放)。

    语义：
    * 幂等标识、业务操作、幂等结果在同一事务内提交，业务回滚则标识一并释放；
    * 同一标识重复调用返回首次结果，不重复产生业务副作用；
    * 同一标识但请求内容不同时拒绝处理。
    """
    if not key:
        raise ValidationFailed(
            "该操作必须提供 Idempotency-Key 请求头。",
            code="IDEMPOTENCY_KEY_REQUIRED",
        )
    if len(key) > 128:
        raise ValidationFailed("Idempotency-Key 长度不能超过 128。", code="IDEMPOTENCY_KEY_TOO_LONG")

    request_hash = _hash_payload(payload)
    ttl = timedelta(hours=settings.YISHANG["IDEMPOTENCY_TTL_HOURS"])

    try:
        with transaction.atomic():
            record = IdempotencyRecord.objects.create(
                scope=scope,
                key=key,
                user=user if getattr(user, "pk", None) else None,
                request_hash=request_hash,
                expires_at=timezone.now() + ttl,
            )
            status_code, body = func()
            record.status_code = status_code
            record.response_body = serialise_value(body)
            record.save(update_fields=["status_code", "response_body"])
            return status_code, body, False
    except IntegrityError as exc:
        if not _is_duplicate_key(exc):
            raise
        existing = IdempotencyRecord.objects.filter(scope=scope, key=key).first()
        if existing is None:
            raise StateConflict(
                "相同幂等标识的请求正在处理中，请稍后重试。",
                code="IDEMPOTENCY_IN_PROGRESS",
            ) from exc
        if existing.request_hash != request_hash:
            raise IdempotencyConflict(
                "该幂等标识已用于不同的请求内容。",
                details={"scope": scope, "key": key},
            ) from exc
        if existing.status_code is None:
            raise StateConflict(
                "相同幂等标识的请求正在处理中，请稍后重试。",
                code="IDEMPOTENCY_IN_PROGRESS",
            ) from exc
        return existing.status_code, dict(existing.response_body or {}), True


def _is_duplicate_key(exc: IntegrityError) -> bool:
    text = str(exc).lower()
    return "duplicate" in text or "1062" in text


def cleanup_expired_idempotency_records(batch_size: int = 1000) -> int:
    """清理过期幂等记录，分批删除避免长事务。"""
    cutoff = timezone.now()
    total = 0
    while True:
        ids = list(
            IdempotencyRecord.objects.filter(expires_at__lt=cutoff).values_list("id", flat=True)[
                :batch_size
            ]
        )
        if not ids:
            return total
        deleted, _ = IdempotencyRecord.objects.filter(id__in=ids).delete()
        total += deleted


# --------------------------------------------------------------------------
# 通用幂等异常
# --------------------------------------------------------------------------


def require_object(model: type[models.Model], pk: Any, *, code: str = "NOT_FOUND") -> Any:
    """按主键取对象，不存在时抛标准业务异常。"""
    obj = model.objects.filter(pk=pk).first()
    if obj is None:
        raise ObjectNotFound(f"{model._meta.verbose_name}不存在：{pk}", code=code)
    return obj


def ensure_single_primary(
    model: type[models.Model],
    *,
    instance: models.Model,
    scope_field: str,
    scope_id: Any,
    flag_field: str = "is_primary",
) -> None:
    """保证同一归属下只有一个「主要」标记（如客户/供应商的主要联系人）。

    MySQL 不支持带条件的部分唯一索引（Django 的 ``UniqueConstraint(condition=...)``
    在 MySQL 上不被支持），所以这类「同一归属下唯一」的规则不能靠数据库约束表达，
    必须在事务内由服务层保证，并由测试覆盖。

    与写入同一事务执行，避免出现「两个主要联系人」的中间态。
    """
    with transaction.atomic():
        (
            model._default_manager.filter(**{scope_field: scope_id, flag_field: True})
            .exclude(pk=instance.pk)
            .update(**{flag_field: False})
        )


__all__ = [
    "APIError",
    "assert_code_pattern_supported",
    "assert_version",
    "build_changes",
    "bump_version",
    "business_now",
    "business_today",
    "cleanup_expired_idempotency_records",
    "create_notification",
    "ensure_single_primary",
    "generate_code",
    "idempotent_execute",
    "mark_event_done",
    "mark_event_failed",
    "publish_event",
    "record_audit",
    "requeue_event",
    "require_object",
    "serialise_value",
    "snapshot_fields",
]

def preview_code(rule_code: str, *, on_date: date | None = None, sample: int = 1) -> str:
    """按规则预演一个编号，不消耗流水。"""
    rule = CodeRule.objects.filter(code=rule_code, is_active=True).first()
    if rule is None:
        raise ObjectNotFound(f"编码规则不存在或已停用：{rule_code}", code="CODE_RULE_NOT_FOUND")
    return _render_pattern(rule.pattern, on_date or business_today(), sample)


def render_code_pattern(pattern: str, *, on_date: date | None = None, sample: int = 1) -> str:
    """按给定编号格式预演结果，用于规则配置时的即时校验。"""
    return _render_pattern(pattern, on_date or business_today(), sample)
