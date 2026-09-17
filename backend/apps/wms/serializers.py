from __future__ import annotations

from rest_framework import serializers

from apps.core.serializers import ReferenceIdSerializer
from apps.wms.models import (
    Direction,
    DocumentType,
    InventoryBalance,
    InventoryDocument,
    InventoryDocumentLine,
    InventoryTransaction,
    Location,
    QualityStatus,
    Warehouse,
    Zone,
)


class WarehouseSerializer(ReferenceIdSerializer):
    company_name = serializers.SerializerMethodField()
    factory_name = serializers.SerializerMethodField()
    department_name = serializers.SerializerMethodField()

    class Meta:
        model = Warehouse
        fields = (
            "id", "company_id", "company_name", "factory_id", "factory_name", "department_id",
            "department_name", "code", "name", "warehouse_type", "address", "manager_name",
            "allow_negative_stock", "is_active", "remark", "version", "created_at", "updated_at",
        )
        read_only_fields = (
            "id", "company_name", "factory_name", "department_name", "version",
            "created_at", "updated_at",
        )

    def get_company_name(self, obj: Warehouse) -> str:
        return obj.company.name if obj.company_id else ""

    def get_factory_name(self, obj: Warehouse) -> str:
        return obj.factory.name if obj.factory_id else ""

    def get_department_name(self, obj: Warehouse) -> str:
        return obj.department.name if obj.department_id else ""


class ZoneSerializer(ReferenceIdSerializer):
    warehouse_name = serializers.SerializerMethodField()
    company_id = serializers.IntegerField(source="warehouse.company_id", read_only=True)
    location_count = serializers.SerializerMethodField()

    class Meta:
        model = Zone
        fields = (
            "id", "warehouse_id", "warehouse_name", "company_id", "code", "name", "zone_type",
            "allow_mixed_batch", "sort_order", "location_count", "is_active", "remark",
            "version", "created_at", "updated_at",
        )
        read_only_fields = (
            "id", "warehouse_name", "company_id", "location_count", "version",
            "created_at", "updated_at",
        )

    def get_warehouse_name(self, obj: Zone) -> str:
        return obj.warehouse.name if obj.warehouse_id else ""

    def get_location_count(self, obj: Zone) -> int:
        return obj.locations.count()


class LocationSerializer(ReferenceIdSerializer):
    zone_name = serializers.SerializerMethodField()
    warehouse_id = serializers.IntegerField(source="zone.warehouse_id", read_only=True)
    warehouse_code = serializers.CharField(source="zone.warehouse.code", read_only=True, default="")

    class Meta:
        model = Location
        fields = (
            "id", "zone_id", "zone_name", "warehouse_id", "warehouse_code", "code", "name",
            "location_type", "row_no", "column_no", "level_no", "capacity", "is_locked",
            "is_active", "remark", "version", "created_at", "updated_at",
        )
        read_only_fields = (
            "id", "zone_name", "warehouse_id", "warehouse_code", "version",
            "created_at", "updated_at",
        )

    def get_zone_name(self, obj: Location) -> str:
        return obj.zone.name if obj.zone_id else ""

class InventoryBalanceSerializer(ReferenceIdSerializer):
    """库存余额。全部只读：余额只能由统一库存服务改写，不提供写入接口。"""

    company_name = serializers.CharField(source="company.name", read_only=True, default="")
    material_code = serializers.CharField(source="material.code", read_only=True, default="")
    material_name = serializers.CharField(source="material.name", read_only=True, default="")
    warehouse_code = serializers.CharField(source="warehouse.code", read_only=True, default="")
    warehouse_name = serializers.CharField(source="warehouse.name", read_only=True, default="")
    location_code = serializers.CharField(source="location.code", read_only=True, default="")
    quality_status_display = serializers.CharField(
        source="get_quality_status_display", read_only=True
    )
    available = serializers.DecimalField(
        max_digits=20, decimal_places=6, read_only=True, coerce_to_string=True
    )

    class Meta:
        model = InventoryBalance
        fields = (
            "id", "company_id", "company_name", "material_id", "material_code", "material_name",
            "warehouse_id", "warehouse_code", "warehouse_name", "location_id", "location_code",
            "batch_no", "roll_no", "quality_status", "quality_status_display", "on_hand", "frozen",
            "reserved", "available", "version", "created_at", "updated_at",
        )
        read_only_fields = fields


class InventoryTransactionSerializer(ReferenceIdSerializer):
    """库存流水。只追加，不提供任何写入接口。"""

    transaction_type_display = serializers.CharField(
        source="get_transaction_type_display", read_only=True
    )
    quality_status_display = serializers.CharField(
        source="get_quality_status_display", read_only=True
    )
    material_code = serializers.CharField(source="material.code", read_only=True, default="")
    material_name = serializers.CharField(source="material.name", read_only=True, default="")
    warehouse_code = serializers.CharField(source="warehouse.code", read_only=True, default="")
    location_code = serializers.CharField(source="location.code", read_only=True, default="")
    document_no = serializers.CharField(source="document.document_no", read_only=True, default="")
    operator_name = serializers.CharField(source="operator.username", read_only=True, default="")

    class Meta:
        model = InventoryTransaction
        fields = (
            "id", "company_id", "document_id", "document_no", "document_line_id",
            "transaction_type", "transaction_type_display", "material_id", "material_code",
            "material_name", "warehouse_id", "warehouse_code", "location_id", "location_code",
            "batch_no", "roll_no", "quality_status", "quality_status_display", "quantity",
            "on_hand_before", "on_hand_after", "frozen_after", "reserved_after", "reason",
            "operator_id", "operator_name", "created_at",
        )
        read_only_fields = fields


class InventoryDocumentLineSerializer(ReferenceIdSerializer):
    material_code = serializers.CharField(source="material.code", read_only=True, default="")
    material_name = serializers.CharField(source="material.name", read_only=True, default="")
    location_code = serializers.CharField(source="location.code", read_only=True, default="")
    target_location_code = serializers.CharField(
        source="target_location.code", read_only=True, default=""
    )
    quality_status_display = serializers.CharField(
        source="get_quality_status_display", read_only=True
    )

    class Meta:
        model = InventoryDocumentLine
        fields = (
            "id", "document_id", "line_no", "material_id", "material_code", "material_name",
            "location_id", "location_code", "target_location_id", "target_location_code",
            "batch_no", "roll_no", "quality_status", "quality_status_display",
            "target_quality_status", "direction", "quantity", "remark", "version",
            "created_at", "updated_at",
        )
        read_only_fields = fields


class InventoryDocumentLineInputSerializer(serializers.Serializer):
    """单据写入用的行输入。用显式字段而不是 ModelSerializer，避免可写字段失控。"""

    material_id = serializers.IntegerField(min_value=1)
    location_id = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    target_location_id = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    batch_no = serializers.CharField(max_length=64, required=False, allow_blank=True, default="")
    roll_no = serializers.CharField(max_length=64, required=False, allow_blank=True, default="")
    quality_status = serializers.ChoiceField(
        choices=QualityStatus.choices, required=False, default=QualityStatus.QUARANTINE
    )
    target_quality_status = serializers.ChoiceField(
        choices=QualityStatus.choices, required=False, allow_blank=True, default=""
    )
    direction = serializers.ChoiceField(
        choices=Direction.choices, required=False, default=Direction.IN
    )
    quantity = serializers.DecimalField(max_digits=20, decimal_places=6)
    remark = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")

    def validate_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError("数量必须大于 0。")
        return value


class InventoryDocumentSerializer(ReferenceIdSerializer):
    lines = InventoryDocumentLineSerializer(many=True, read_only=True)
    document_type_display = serializers.CharField(source="get_document_type_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    warehouse_name = serializers.CharField(source="warehouse.name", read_only=True, default="")
    warehouse_code = serializers.CharField(source="warehouse.code", read_only=True, default="")
    posted_by_name = serializers.CharField(source="posted_by.username", read_only=True, default="")
    reversed_by_name = serializers.CharField(
        source="reversed_by.username", read_only=True, default=""
    )

    class Meta:
        model = InventoryDocument
        fields = (
            "id", "company_id", "document_no", "document_type", "document_type_display", "status",
            "status_display", "warehouse_id", "warehouse_name", "warehouse_code", "biz_type",
            "biz_id", "biz_no", "posted_at", "posted_by_id", "posted_by_name", "reversed_at",
            "reversed_by_id", "reversed_by_name", "reverse_reason", "remark", "lines", "version",
            "created_at", "updated_at",
        )
        read_only_fields = (
            "id", "company_id", "document_no", "document_type_display", "status", "status_display",
            "warehouse_name", "warehouse_code", "posted_at", "posted_by_id", "posted_by_name",
            "reversed_at", "reversed_by_id", "reversed_by_name", "reverse_reason", "lines",
            "version", "created_at", "updated_at",
        )


class InventoryDocumentCreateSerializer(serializers.Serializer):
    document_type = serializers.ChoiceField(choices=DocumentType.choices)
    company_id = serializers.IntegerField(min_value=1, required=False)
    warehouse_id = serializers.IntegerField(min_value=1)
    biz_type = serializers.CharField(max_length=32, required=False, allow_blank=True, default="")
    biz_id = serializers.CharField(max_length=64, required=False, allow_blank=True, default="")
    biz_no = serializers.CharField(max_length=64, required=False, allow_blank=True, default="")
    remark = serializers.CharField(required=False, allow_blank=True, default="")
    lines = InventoryDocumentLineInputSerializer(many=True, allow_empty=False)


class InventoryDocumentUpdateSerializer(serializers.Serializer):
    warehouse_id = serializers.IntegerField(min_value=1, required=False)
    biz_no = serializers.CharField(max_length=64, required=False, allow_blank=True)
    remark = serializers.CharField(required=False, allow_blank=True)
    lines = InventoryDocumentLineInputSerializer(many=True, required=False, allow_empty=False)


class QualityReleaseSerializer(serializers.Serializer):
    # 公司可由仓库归属推导；显式传入时必须与仓库所属公司一致
    company_id = serializers.IntegerField(min_value=1, required=False)
    warehouse_id = serializers.IntegerField(min_value=1)
    material_id = serializers.IntegerField(min_value=1)
    quantity = serializers.DecimalField(max_digits=20, decimal_places=6)
    location_id = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    batch_no = serializers.CharField(max_length=64, required=False, allow_blank=True, default="")
    roll_no = serializers.CharField(max_length=64, required=False, allow_blank=True, default="")
    from_status = serializers.ChoiceField(
        choices=QualityStatus.choices, required=False, default=QualityStatus.QUARANTINE
    )
    to_status = serializers.ChoiceField(
        choices=QualityStatus.choices, required=False, default=QualityStatus.QUALIFIED
    )
    biz_type = serializers.CharField(max_length=32, required=False, allow_blank=True, default="")
    biz_id = serializers.CharField(max_length=64, required=False, allow_blank=True, default="")
    biz_no = serializers.CharField(max_length=64, required=False, allow_blank=True, default="")
    reason = serializers.CharField(required=False, allow_blank=True, default="")

    def validate_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError("放行数量必须大于 0。")
        return value

    def validate(self, attrs):
        if attrs["from_status"] == attrs["to_status"]:
            raise serializers.ValidationError({"to_status": "转出与转入的质量状态不能相同。"})
        return attrs


class DocumentActionSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, default="")
