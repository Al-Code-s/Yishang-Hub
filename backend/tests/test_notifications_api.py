"""站内通知与待办联动用例。

对应任务书 7.3「Outbox 至少一次投递，消费者必须幂等」与 10.1「消息与待办」。
"""

from __future__ import annotations

import uuid

import pytest

from apps.core.models import Notification, OutboxEvent
from apps.core.services import create_notification
from apps.identity.models import DataScopeType
from apps.integration.tasks import dispatch_due_events
from tests.conftest import make_role, make_user

pytestmark = pytest.mark.django_db

NOTIFICATIONS_URL = "/api/v1/identity/notifications/"


def _login(client, user, password="Tst!Passw0rd2026"):
    assert client.post(
        "/api/v1/identity/auth/login/",
        {"username": user.username, "password": password},
        format="json",
    ).status_code == 200


def test_create_notification_is_idempotent_per_source_event(company):
    user = make_user(username="notify_u", company=company)
    event_a = uuid.uuid4()
    first = create_notification(
        recipient=user, title="待审批", body="您有一条待办。",
        biz_type="workflow.ApprovalInstance", biz_id="1", source_event_id=event_a,
    )
    replay = create_notification(
        recipient=user, title="待审批", body="您有一条待办。",
        biz_type="workflow.ApprovalInstance", biz_id="1", source_event_id=event_a,
    )
    assert first is not None
    assert replay is None or replay.pk == first.pk
    assert Notification.objects.filter(recipient=user).count() == 1


def test_dispatch_is_at_least_once_but_notification_not_duplicated(registry_permissions, company):
    """同一 Outbox 事件重复分发，通知只产生一条。"""
    role = make_role(
        code="notify_role", permission_codes=["core.notification.view"],
        data_scope_type=DataScopeType.COMPANY, company=company,
    )
    make_user(username="notify_target", role=role, company=company)

    from apps.core.services import publish_event

    event = publish_event(
        event_type="workflow.approval.submitted",
        aggregate_type="workflow.ApprovalInstance",
        aggregate_id=999,
        payload={
            "title": "有一笔申请待审批",
            "biz_no": "SP00000999",
            "assignee_user_ids": [_target_pk()],
            "step_name": "一级审批",
        },
        dedup_key="notify-api-test:1",
    )
    assert OutboxEvent.objects.filter(pk=event.pk).count() == 1

    dispatched = dispatch_due_events()
    assert dispatched.get("done", 0) >= 1, dispatched
    count_after_first = Notification.objects.filter(recipient_id=_target_pk()).count()
    assert count_after_first == 1

    # 手工把事件重置为待处理，模拟至少一次投递下的重复分发
    OutboxEvent.objects.filter(pk=event.pk).update(status="pending", processed_at=None)
    dispatch_due_events()
    assert Notification.objects.filter(recipient_id=_target_pk()).count() == count_after_first


def _target_pk() -> int:
    from apps.identity.models import User

    return User.objects.get(username="notify_target").pk


def test_notification_apis_are_scoped_to_current_user(api_client, registry_permissions, company):
    role = make_role(
        code="notify_viewer", permission_codes=["core.notification.view"],
        data_scope_type=DataScopeType.COMPANY, company=company,
    )
    owner = make_user(username="notify_owner", role=role, company=company)
    other = make_user(username="notify_other", role=role, company=company)

    create_notification(recipient=owner, title="我的通知", body="内容")
    create_notification(
        recipient=other, title="他人通知", body="内容", source_event_id=uuid.uuid4()
    )

    _login(api_client, owner)
    listed = api_client.get(NOTIFICATIONS_URL)
    assert listed.status_code == 200
    titles = [row["title"] for row in listed.json()["results"]]
    assert titles == ["我的通知"]

    unread = api_client.get(f"{NOTIFICATIONS_URL}unread-count/")
    assert unread.json() == {"count": 1}

    notification_id = listed.json()["results"][0]["id"]
    marked = api_client.post(f"{NOTIFICATIONS_URL}{notification_id}/read/", {}, format="json")
    assert marked.status_code == 200

    # 他人的通知 ID 直接猜地址访问 → 404，不能越权读取
    other_notification = Notification.objects.get(recipient=other)
    cross = api_client.get(f"{NOTIFICATIONS_URL}{other_notification.pk}/")
    assert cross.status_code == 404

    assert api_client.post(f"{NOTIFICATIONS_URL}read-all/", {}, format="json").status_code == 200
    assert api_client.get(f"{NOTIFICATIONS_URL}unread-count/").json() == {"count": 0}
