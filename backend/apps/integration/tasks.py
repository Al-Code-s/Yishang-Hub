"""Outbox 投递任务。

至少一次投递：消费者必须幂等，重复投递不会产生重复业务结果。
"""

from __future__ import annotations

import logging

from celery import shared_task
from django.db.models import Q
from django.utils import timezone

from apps.core.models import OutboxEvent, OutboxStatus
from apps.core.services import mark_event_done, mark_event_failed

logger = logging.getLogger("yishang.integration")

BATCH_SIZE = 200


def dispatch_due_events(limit: int = BATCH_SIZE) -> dict[str, int]:
    """把到期的事件投递给已注册处理器。"""
    from apps.integration.handlers import get_handler

    now = timezone.now()
    candidates = (
        OutboxEvent.objects.filter(
            Q(status=OutboxStatus.PENDING) | Q(status=OutboxStatus.FAILED),
        )
        .filter(Q(next_retry_at__isnull=True) | Q(next_retry_at__lte=now))
        .order_by("id")[:limit]
    )

    claimed = done = failed = 0
    for event in candidates:
        # 原子抢占，避免多 worker 重复处理同一事件
        updated = OutboxEvent.objects.filter(
            pk=event.pk, status__in=[OutboxStatus.PENDING, OutboxStatus.FAILED]
        ).update(status=OutboxStatus.PROCESSING)
        if not updated:
            continue
        claimed += 1
        event.refresh_from_db()

        handler = get_handler(event.event_type)
        if handler is None:
            mark_event_failed(event, f"未注册的事件类型：{event.event_type}")
            failed += 1
            continue

        try:
            handler(event)
        except Exception as exc:  # noqa: BLE001 - 需要记录任意处理器异常并重试
            logger.exception("outbox handler failed: %s", event.event_type)
            mark_event_failed(event, f"{type(exc).__name__}: {exc}")
            failed += 1
        else:
            mark_event_done(event)
            done += 1

    return {"claimed": claimed, "done": done, "failed": failed}


@shared_task(name="integration.dispatch_outbox_events")
def dispatch_outbox_events_task(limit: int = BATCH_SIZE) -> dict[str, int]:
    return dispatch_due_events(limit)
