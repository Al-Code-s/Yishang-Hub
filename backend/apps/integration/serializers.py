from __future__ import annotations

from rest_framework import serializers

from apps.core.models import OutboxEvent
from apps.core.serializers import ReferenceIdSerializer
from apps.integration.models import DocumentLink


class OutboxEventSerializer(ReferenceIdSerializer):
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = OutboxEvent
        fields = (
            "id", "event_id", "event_type", "aggregate_type", "aggregate_id", "payload",
            "status", "status_display", "attempts", "max_attempts", "next_retry_at",
            "last_error", "dedup_key", "created_at", "processed_at",
        )
        read_only_fields = fields


class DocumentLinkSerializer(ReferenceIdSerializer):
    class Meta:
        model = DocumentLink
        fields = (
            "id", "source_type", "source_id", "source_no", "target_type", "target_id",
            "target_no", "relation", "quantity", "remark", "created_at",
        )
        read_only_fields = ("id", "created_at")
