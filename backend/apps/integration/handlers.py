"""Outbox 事件处理器。

约定：
* 处理器必须幂等（Outbox 是至少一次投递语义）；
* 处理器不做库存、审批等关键状态迁移，仅做通知、汇总、报表等允许最终一致的动作；
* 未注册处理器的事件不会被静默丢弃，会进入“需人工处理”。
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from django.db import transaction

from apps.core.models import OutboxEvent
from apps.core.services import create_notification
from apps.identity.models import User

logger = logging.getLogger("yishang.integration")

Handler = Callable[[OutboxEvent], None]

_REGISTRY: dict[str, Handler] = {}


def register(event_type: str) -> Callable[[Handler], Handler]:
    def decorator(func: Handler) -> Handler:
        _REGISTRY[event_type] = func
        return func

    return decorator


def get_handler(event_type: str) -> Handler | None:
    return _REGISTRY.get(event_type)


def registered_event_types() -> list[str]:
    return sorted(_REGISTRY)


@register("workflow.approval.submitted")
def handle_approval_submitted(event: OutboxEvent) -> None:
    """审批到达新节点：通知候选审批人。source_event_id 保证重放不重复生成通知。"""
    payload: dict[str, Any] = event.payload or {}
    assignee_ids = payload.get("assignee_user_ids") or []
    if not assignee_ids:
        logger.info("outbox event %s has no assignees, skipped", event.event_id)
        return
    title = f"待审批：{payload.get('title', '')}"
    body = f"单号 {payload.get('biz_no', '')}，节点：{payload.get('step_name', '')}"

    with transaction.atomic():
        for user in User.objects.filter(id__in=assignee_ids, is_active=True):
            create_notification(
                recipient=user,
                title=title,
                body=body,
                biz_type="workflow.ApprovalInstance",
                biz_id=payload.get("instance_id"),
                source_event_id=event.event_id,
            )


@register("workflow.approval.decided")
def handle_approval_decided(event: OutboxEvent) -> None:
    """审批结束：通知申请人结果。"""
    payload: dict[str, Any] = event.payload or {}
    recipient_ids = payload.get("recipient_user_ids") or []
    result = "已通过" if payload.get("result") == "approved" else "已驳回"
    with transaction.atomic():
        for user in User.objects.filter(id__in=recipient_ids, is_active=True):
            create_notification(
                recipient=user,
                title=f"审批{result}：{payload.get('title', '')}",
                body=f"单号 {payload.get('biz_no', '')}",
                biz_type="workflow.ApprovalInstance",
                biz_id=payload.get("instance_id"),
                source_event_id=event.event_id,
            )
