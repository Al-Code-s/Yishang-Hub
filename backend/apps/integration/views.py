"""内部协同中心接口。普通业务人员只看到与自己相关的业务进度，管理员可处理失败事件。"""

from __future__ import annotations

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.exceptions import StateConflict
from apps.core.models import AuditAction, OutboxEvent, OutboxStatus
from apps.core.permissions import HasRequiredPermissions
from apps.core.services import record_audit, requeue_event
from apps.integration.models import DocumentLink
from apps.integration.selectors import outbox_health
from apps.integration.serializers import DocumentLinkSerializer, OutboxEventSerializer
from apps.integration.tasks import dispatch_due_events


class OutboxEventViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = OutboxEvent.objects.all()
    serializer_class = OutboxEventSerializer
    permission_classes = [HasRequiredPermissions]
    required_permissions = {
        "list": "integration.outbox.view",
        "retrieve": "integration.outbox.view",
        "retry": "integration.outbox.retry",
        "dispatch_now": "integration.outbox.retry",
        "health": "integration.outbox.view",
    }
    filterset_fields = ["status", "event_type", "aggregate_type", "aggregate_id"]
    search_fields = ["event_type", "aggregate_id", "last_error"]
    ordering_fields = ["id", "created_at", "processed_at"]

    @action(detail=True, methods=["post"])
    def retry(self, request, *args, **kwargs):
        """人工重放单个失败事件。"""
        event = self.get_object()
        if event.status == OutboxStatus.DONE:
            raise StateConflict("已完成的事件无需重放。", code="OUTBOX_ALREADY_DONE")
        requeue_event(event)
        record_audit(
            action=AuditAction.UPDATE,
            instance=event,
            reason="人工重放发件箱事件",
            object_repr=str(event),
        )
        return Response(OutboxEventSerializer(event).data)

    @action(detail=False, methods=["post"], url_path="dispatch-now")
    def dispatch_now(self, request, *args, **kwargs):
        """立即投递到期的待处理事件（供管理员排查使用，不替代 beat 轮询）。"""
        result = dispatch_due_events(limit=int(request.query_params.get("limit", 100)))
        return Response(result, status=status.HTTP_200_OK)

    @action(detail=False, methods=["get"])
    def health(self, request, *args, **kwargs):
        return Response(outbox_health())


class DocumentLinkViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = DocumentLink.objects.all()
    serializer_class = DocumentLinkSerializer
    permission_classes = [HasRequiredPermissions]
    required_permissions = {
        "list": "integration.document_link.view",
        "retrieve": "integration.document_link.view",
    }
    filterset_fields = ["source_type", "source_id", "target_type", "target_id", "relation"]
    ordering_fields = ["id", "created_at"]
