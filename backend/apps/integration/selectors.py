from __future__ import annotations

from django.db.models import Count, Q

from apps.core.models import OutboxEvent, OutboxStatus


def outbox_health() -> dict[str, int]:
    """发件箱健康度：供运维看板与告警使用。"""
    rows = OutboxEvent.objects.values("status").annotate(total=Count("id"))
    counts = {row["status"]: row["total"] for row in rows}
    return {
        "pending": counts.get(OutboxStatus.PENDING, 0),
        "processing": counts.get(OutboxStatus.PROCESSING, 0),
        "failed": counts.get(OutboxStatus.FAILED, 0),
        "dead": counts.get(OutboxStatus.DEAD, 0),
        "done": counts.get(OutboxStatus.DONE, 0),
    }


def failing_outbox_queryset():
    return OutboxEvent.objects.filter(
        Q(status=OutboxStatus.FAILED) | Q(status=OutboxStatus.DEAD)
    ).order_by("-id")
