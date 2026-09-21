from __future__ import annotations

from rest_framework import serializers

from apps.core.models import OutboxEvent
from apps.core.serializers import ReferenceIdSerializer
from apps.core.services import object_type_label
from apps.integration.models import DocumentLink


class OutboxEventSerializer(ReferenceIdSerializer):
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    aggregate_type_display = serializers.SerializerMethodField()

    class Meta:
        model = OutboxEvent
        fields = (
            "id", "event_id", "event_type", "aggregate_type", "aggregate_type_display",
            "aggregate_id", "payload",
            "status", "status_display", "attempts", "max_attempts", "next_retry_at",
            "last_error", "dedup_key", "created_at", "processed_at",
        )
        read_only_fields = fields

    def get_aggregate_type_display(self, obj: OutboxEvent) -> str:
        """把 ``sales.SalesOrder`` 这类内部标识换成中文业务对象名。

        原始值仍然返回（排查问题要用），另给一个中文展示值，前端不自己维护翻译表。
        解析不到模型时原样返回，不猜名字（见 ``object_type_label``）。
        """
        return object_type_label(obj.aggregate_type)


class DocumentLinkSerializer(ReferenceIdSerializer):
    class Meta:
        model = DocumentLink
        fields = (
            "id", "source_type", "source_id", "source_no", "target_type", "target_id",
            "target_no", "relation", "quantity", "remark", "created_at",
        )
        read_only_fields = ("id", "created_at")
