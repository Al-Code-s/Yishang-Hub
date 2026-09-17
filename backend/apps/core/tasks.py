"""公共维护类定时任务。"""

from __future__ import annotations

import logging

from celery import shared_task

from apps.core.services import cleanup_expired_idempotency_records

logger = logging.getLogger("yishang.core")


@shared_task(name="core.cleanup_expired_idempotency_records")
def cleanup_expired_idempotency_records_task(batch_size: int = 1000) -> int:
    removed = cleanup_expired_idempotency_records(batch_size=batch_size)
    logger.info("purged %s expired idempotency records", removed)
    return removed


@shared_task(name="core.purge_expired_sessions")
def purge_expired_sessions_task() -> int:
    """清理过期会话。不使用 clearsessions 命令行，便于纳入 beat 调度与审计。"""
    from django.contrib.sessions.models import Session
    from django.utils import timezone

    deleted, _ = Session.objects.filter(expire_date__lt=timezone.now()).delete()
    return deleted
