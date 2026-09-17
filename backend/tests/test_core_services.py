"""公共基础服务用例：编码规则、幂等、发件箱、审计不可篡改。

对应任务书 14.2 第 5、7、18 条与 5.4 / 7.2 / 7.3 / 6.6。
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from django.db import IntegrityError, connection, transaction

from apps.core.exceptions import (
    APIError,
    IdempotencyConflict,
    ObjectNotFound,
    ValidationFailed,
)
from apps.core.models import (
    AuditAction,
    AuditLog,
    CodeRule,
    CodeSequence,
    Notification,
    OutboxEvent,
    OutboxStatus,
    ResetPeriod,
)
from apps.core.services import (
    generate_code,
    idempotent_execute,
    mark_event_failed,
    preview_code,
    publish_event,
    record_audit,
    render_code_pattern,
    requeue_event,
)
from tests.conftest import make_user

pytestmark = pytest.mark.django_db


# --------------------------------------------------------------------------
# 编码规则
# --------------------------------------------------------------------------


def test_generate_code_daily_sequence_resets_by_period(db):
    CodeRule.objects.create(
        code="T1", name="测试单号", pattern="T{YYYYMMDD}{SEQ:4}", reset_period=ResetPeriod.DAILY
    )
    first = generate_code("T1", on_date=date(2026, 1, 1))
    second = generate_code("T1", on_date=date(2026, 1, 1))
    next_day = generate_code("T1", on_date=date(2026, 1, 2))

    assert first == "T202601010001"
    assert second == "T202601010002"
    assert next_day == "T202601020001"


def test_generate_code_never_reset(db):
    CodeRule.objects.create(code="T2", name="永不重置", pattern="T2{SEQ:3}", reset_period=ResetPeriod.NEVER)
    assert generate_code("T2", on_date=date(2026, 1, 1)) == "T2001"
    assert generate_code("T2", on_date=date(2030, 5, 5)) == "T2002"


def test_generate_code_rejects_unknown_rule(db):
    with pytest.raises(ObjectNotFound) as excinfo:
        generate_code("NOT_EXIST")
    assert excinfo.value.code == "CODE_RULE_NOT_FOUND"


def test_render_code_pattern_requires_sequence_placeholder(db):
    with pytest.raises(ValidationFailed):
        render_code_pattern("NO-SEQ-HERE")


def test_preview_code_does_not_consume_sequence(db):
    CodeRule.objects.create(code="T3", name="预览", pattern="T3{SEQ:3}", reset_period=ResetPeriod.DAILY)
    assert preview_code("T3") == "T3001"
    assert preview_code("T3") == "T3001"
    assert CodeSequence.objects.filter(rule__code="T3").count() == 0
    assert generate_code("T3") == "T3001"


@pytest.mark.concurrency
def test_generate_code_unique_under_concurrency(transactional_db):
    """两个真实并发事务不能拿到相同的编号（唯一约束兜底 + 行锁）。"""
    import threading

    CodeRule.objects.create(
        code="TC", name="并发", pattern="C{YYYYMMDD}{SEQ:4}", reset_period=ResetPeriod.DAILY
    )
    results: list[str] = []
    errors: list[BaseException] = []
    barrier = threading.Barrier(2)

    def worker() -> None:
        try:
            barrier.wait(timeout=10)
            results.append(generate_code("TC", on_date=date(2026, 3, 3)))
        except BaseException as exc:  # noqa: BLE001 - 需要把线程内的异常带出来
            errors.append(exc)
        finally:
            connection.close()

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    assert not errors, errors
    assert len(results) == 2
    assert len(set(results)) == 2
    assert CodeSequence.objects.get(rule__code="TC", period_key="20260303").last_value >= 2


# --------------------------------------------------------------------------
# 幂等
# --------------------------------------------------------------------------


def test_idempotent_execute_requires_key(db):
    with pytest.raises(ValidationFailed) as excinfo:
        idempotent_execute(scope="test", key=None, payload={}, func=lambda: (200, {}))
    assert excinfo.value.code == "IDEMPOTENCY_KEY_REQUIRED"


def test_idempotent_execute_replays_same_result(db):
    calls: list[int] = []

    def action() -> tuple[int, dict]:
        calls.append(1)
        return 201, {"value": len(calls)}

    status_code, body, replayed = idempotent_execute(
        scope="stock.post", key="k-1", payload={"qty": "1"}, func=action
    )
    assert (status_code, body, replayed) == (201, {"value": 1}, False)

    status_code, body, replayed = idempotent_execute(
        scope="stock.post", key="k-1", payload={"qty": "1"}, func=action
    )
    assert replayed is True
    assert body == {"value": 1}
    assert len(calls) == 1  # 业务函数没有被重复执行


def test_idempotent_execute_rejects_same_key_different_payload(db):
    def action() -> tuple[int, dict]:
        return 200, {"ok": True}

    idempotent_execute(scope="stock.post", key="k-2", payload={"qty": "1"}, func=action)
    with pytest.raises(IdempotencyConflict):
        idempotent_execute(scope="stock.post", key="k-2", payload={"qty": "2"}, func=action)


def test_idempotent_execute_rolls_back_key_on_failure(db):
    def explode() -> tuple[int, dict]:
        raise APIError("业务失败", code="BOOM")

    with pytest.raises(APIError):
        idempotent_execute(scope="stock.post", key="k-3", payload={}, func=explode)

    # 业务回滚后幂等标识一并释放，允许重试
    from apps.core.models import IdempotencyRecord

    assert not IdempotencyRecord.objects.filter(scope="stock.post", key="k-3").exists()

    status_code, body, replayed = idempotent_execute(
        scope="stock.post", key="k-3", payload={}, func=lambda: (200, {"ok": True})
    )
    assert (status_code, replayed) == (200, False)


# --------------------------------------------------------------------------
# 发件箱
# --------------------------------------------------------------------------


def test_publish_event_deduplicates_by_dedup_key(db):
    first = publish_event(
        event_type="test.created", aggregate_type="Test", aggregate_id=1, dedup_key="d-1"
    )
    second = publish_event(
        event_type="test.created", aggregate_type="Test", aggregate_id=1, dedup_key="d-1"
    )
    assert first.pk == second.pk
    assert OutboxEvent.objects.count() == 1


def test_outbox_retry_and_dead_letter(db):
    event = publish_event(event_type="test.retry", aggregate_type="Test", aggregate_id=9)
    assert event.status == OutboxStatus.PENDING

    mark_event_failed(event, "上游超时")
    event.refresh_from_db()
    assert event.status == OutboxStatus.FAILED
    assert event.attempts == 1
    assert event.next_retry_at is not None
    assert "上游超时" in event.last_error

    for _ in range(event.max_attempts):
        mark_event_failed(event, "still failing")
        event.refresh_from_db()

    assert event.status == OutboxStatus.DEAD
    assert event.attempts >= event.max_attempts

    requeued = requeue_event(event)
    requeued.refresh_from_db()
    assert requeued.status == OutboxStatus.PENDING


def test_outbox_dispatch_creates_notification_once(db):
    """重复投递同一事件不产生重复通知（消费者幂等），对应 14.2 第 18 条。"""
    from apps.integration.tasks import dispatch_due_events
    from tests.conftest import make_user as create_user

    user = create_user(username="notify_target")
    event = publish_event(
        event_type="workflow.approval.decided",
        aggregate_type="workflow.ApprovalInstance",
        aggregate_id=123,
        payload={
            "instance_id": 123,
            "biz_no": "AP00000001",
            "title": "测试审批",
            "result": "approved",
            "recipient_user_ids": [user.pk],
        },
        dedup_key="approval:123:decided",
    )

    first = dispatch_due_events()
    assert first["done"] == 1
    assert Notification.objects.filter(recipient=user).count() == 1

    # 人为把事件退回待处理，模拟至少一次投递导致的重复消费
    event.refresh_from_db()
    requeue_event(event)
    dispatch_due_events()
    assert Notification.objects.filter(recipient=user).count() == 1


def test_outbox_unknown_event_type_marks_failed(db):
    from apps.integration.tasks import dispatch_due_events

    publish_event(event_type="nobody.handles.this", aggregate_type="Test", aggregate_id=7)
    result = dispatch_due_events()
    assert result["failed"] == 1
    event = OutboxEvent.objects.get(event_type="nobody.handles.this")
    assert "未注册的事件类型" in event.last_error


# --------------------------------------------------------------------------
# 审计
# --------------------------------------------------------------------------


def test_audit_log_is_write_once(db):
    log = record_audit(action=AuditAction.CREATE, object_type="Test", object_id="1", object_repr="测试")
    log.reason = "被篡改"
    with pytest.raises(RuntimeError):
        log.save()
    with pytest.raises(RuntimeError):
        record_audit(action=AuditAction.UPDATE, object_type="Test", object_id="1").delete()

    log.refresh_from_db()
    assert log.reason == ""


def test_audit_is_rolled_back_with_business_transaction(db):
    """审计与业务同事务：业务回滚则审计一并回滚，不会留下孤立的“已成功”记录。"""
    before = AuditLog.objects.count()
    with pytest.raises(RuntimeError), transaction.atomic():
        record_audit(action=AuditAction.CREATE, object_type="Test", object_id="2")
        assert AuditLog.objects.count() == before + 1
        raise RuntimeError("业务失败")
    assert AuditLog.objects.count() == before


def test_audit_records_actor_and_changes(db):
    user = make_user(username="audit_actor")
    log = record_audit(
        action=AuditAction.UPDATE,
        instance=user,
        changes={"display_name": {"before": "", "after": "新名字"}},
        reason="改名",
        actor=user,
    )
    assert log.actor_id == user.pk
    assert log.actor_username == "audit_actor"
    assert log.object_type == "identity.User"
    assert log.changes["display_name"]["after"] == "新名字"
    # 无 HTTP 上下文时审计仍会分配一个请求追踪标识，便于与业务日志关联
    assert len(log.request_id) == 32


def test_audit_does_not_store_password(db):
    user = make_user(username="audit_pwd")
    log = record_audit(action=AuditAction.UPDATE, instance=user, reason="修改密码")
    assert "password" not in log.changes
    assert "Tst!Passw0rd2026" not in log.reason


# --------------------------------------------------------------------------
# 通用约束
# --------------------------------------------------------------------------


def test_code_sequence_unique_constraint(db):
    rule = CodeRule.objects.create(code="TU", name="唯一", pattern="U{SEQ:3}")
    CodeSequence.objects.create(rule=rule, period_key="20260101", last_value=1)
    with pytest.raises(IntegrityError), transaction.atomic():
        CodeSequence.objects.create(rule=rule, period_key="20260101", last_value=2)


def test_idempotency_scope_key_unique(db):
    from django.utils import timezone

    from apps.core.models import IdempotencyRecord

    IdempotencyRecord.objects.create(
        scope="s", key="k", request_hash="h", expires_at=timezone.now()
    )
    with pytest.raises(IntegrityError), transaction.atomic():
        IdempotencyRecord.objects.create(
            scope="s", key="k", request_hash="h2", expires_at=timezone.now()
        )


def test_decimal_fields_use_decimal_not_float():
    from apps.core.constants import money_field, price_field, quantity_field

    assert quantity_field("数量").decimal_places == 6
    assert quantity_field("数量").max_digits == 20
    assert price_field("单价").decimal_places == 6
    # 金额统一保留 4 位小数（见 docs/data-model.md 的舍入规则）
    assert money_field("金额").decimal_places == 4
    assert money_field("金额").max_digits == 20
    assert isinstance(Decimal("1.10"), Decimal)


def test_business_timezone_helpers():
    from apps.core.services import business_now, business_timezone, business_today

    assert str(business_timezone()) == "Asia/Shanghai"
    now = business_now()
    assert now.tzinfo is not None
    assert now.utcoffset().total_seconds() == 8 * 3600
    assert business_today() == now.date()


def test_health_ready_checks_database(api_client):
    response = api_client.get("/readyz")
    assert response.status_code == 200
