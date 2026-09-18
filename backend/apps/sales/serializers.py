"""销售模块序列化器。

约定（与采购模块一致）：

* 只读序列化器返回中文标签字段（`*_display`）供列表展示，前端不硬编码标签；
* 输入序列器只接受业务字段，**金额一律不接受前端提交**（`amount`、`total_amount`
  等由服务层计算）；
* `shipped_quantity` / `returned_quantity` 等派生字段只读，防止前端绕过累计逻辑。
"""

from __future__ import annotations

from rest_framework import serializers

from apps.core.serializers import ReferenceIdSerializer
from apps.sales.models import (
    SalesOrder,
    SalesOrderLine,
    SalesReturn,
    SalesReturnLine,
    SalesShipment,
    SalesShipmentLine,
)

READ_ONLY = ("id", "version", "created_at", "updated_at")


def _account_name(account) -> str:
    if account is None:
        return ""
    return account.display_name or account.username


class OrderLineSerializer(ReferenceIdSerializer):
    material_code = serializers.CharField(source="material.code", read_only=True)
    material_name = serializers.CharField(source="material.name", read_only=True)
    sku_code = serializers.CharField(source="sku.code", read_only=True, default="")
    color_name = serializers.CharField(source="sku.color.name", read_only=True, default="")
    size_name = serializers.CharField(source="sku.size.name", read_only=True, default="")
    uom_name = serializers.CharField(source="uom.name", read_only=True, default="")
    remaining_quantity = serializers.DecimalField(max_digits=20, decimal_places=6, read_only=True)
    returnable_quantity = serializers.DecimalField(max_digits=20, decimal_places=6, read_only=True)

    class Meta:
        model = SalesOrderLine
        fields = (
            "id",
            "order_id",
            "line_no",
            "material_id",
            "material_code",
            "material_name",
            "sku_id",
            "sku_code",
            "color_name",
            "size_name",
            "quantity",
            "shipped_quantity",
            "returned_quantity",
            "remaining_quantity",
            "returnable_quantity",
            "price",
            "amount",
            "uom_id",
            "uom_name",
            "expected_date",
            "remark",
            "version",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "line_no",
            "shipped_quantity",
            "returned_quantity",
            "remaining_quantity",
            "returnable_quantity",
            "amount",
            *READ_ONLY[1:],
        )


class SalesOrderSerializer(ReferenceIdSerializer):
    lines = OrderLineSerializer(many=True, read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    priority_display = serializers.CharField(source="get_priority_display", read_only=True)
    customer_name = serializers.CharField(source="customer.name", read_only=True)
    customer_code = serializers.CharField(source="customer.code", read_only=True)
    company_name = serializers.CharField(source="company.name", read_only=True)
    warehouse_name = serializers.CharField(source="warehouse.name", read_only=True, default="")
    salesman_name = serializers.SerializerMethodField()

    class Meta:
        model = SalesOrder
        fields = (
            "id",
            "company_id",
            "company_name",
            "order_no",
            "customer_id",
            "customer_code",
            "customer_name",
            "status",
            "status_display",
            "salesman_id",
            "salesman_name",
            "order_date",
            "expected_date",
            "priority",
            "priority_display",
            "warehouse_id",
            "warehouse_name",
            "currency",
            "tax_rate",
            "payment_terms",
            "delivery_address",
            "total_amount",
            "tax_amount",
            "amount_with_tax",
            "approval_instance_id",
            "approved_at",
            "closed_at",
            "remark",
            "lines",
            "version",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "order_no",
            "status",
            "salesman_id",
            "salesman_name",
            "total_amount",
            "tax_amount",
            "amount_with_tax",
            "approval_instance_id",
            "approved_at",
            "closed_at",
            "company_name",
            "customer_code",
            "customer_name",
            "warehouse_name",
            "lines",
            *READ_ONLY[1:],
        )

    def get_salesman_name(self, obj: SalesOrder) -> str:
        return _account_name(obj.salesman)


class OrderLineInputSerializer(serializers.Serializer):
    material_id = serializers.IntegerField(min_value=1)
    quantity = serializers.DecimalField(max_digits=20, decimal_places=6)
    sku_id = serializers.IntegerField(required=False, allow_null=True)
    price = serializers.DecimalField(
        max_digits=20, decimal_places=6, required=False, default=0, min_value=0
    )
    uom_id = serializers.IntegerField(required=False, allow_null=True)
    expected_date = serializers.DateField(required=False, allow_null=True)
    remark = serializers.CharField(required=False, allow_blank=True, default="", max_length=255)

    def validate_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError("订单数量必须大于 0。")
        return value


class SalesOrderWriteSerializer(serializers.Serializer):
    order_no = serializers.CharField(required=False, allow_blank=True, max_length=32)
    customer_id = serializers.IntegerField(min_value=1)
    order_date = serializers.DateField(required=False, allow_null=True)
    expected_date = serializers.DateField(required=False, allow_null=True)
    priority = serializers.ChoiceField(choices=["normal", "urgent"], required=False, default="normal")
    warehouse_id = serializers.IntegerField(required=False, allow_null=True)
    salesman_id = serializers.IntegerField(required=False, allow_null=True)
    currency = serializers.CharField(required=False, allow_blank=True, default="CNY", max_length=8)
    tax_rate = serializers.DecimalField(
        max_digits=18, decimal_places=10, required=False, default=0
    )
    payment_terms = serializers.CharField(required=False, allow_blank=True, default="", max_length=64)
    delivery_address = serializers.CharField(
        required=False, allow_blank=True, default="", max_length=255
    )
    remark = serializers.CharField(required=False, allow_blank=True, default="")
    lines = OrderLineInputSerializer(many=True)


class SalesOrderUpdateSerializer(serializers.Serializer):
    order_date = serializers.DateField(required=False, allow_null=True)
    expected_date = serializers.DateField(required=False, allow_null=True)
    priority = serializers.ChoiceField(choices=["normal", "urgent"], required=False)
    warehouse_id = serializers.IntegerField(required=False, allow_null=True)
    salesman_id = serializers.IntegerField(required=False, allow_null=True)
    currency = serializers.CharField(required=False, allow_blank=True, max_length=8)
    tax_rate = serializers.DecimalField(
        max_digits=18, decimal_places=10, required=False, allow_null=True
    )
    payment_terms = serializers.CharField(required=False, allow_blank=True, max_length=64)
    delivery_address = serializers.CharField(
        required=False, allow_blank=True, max_length=255
    )
    remark = serializers.CharField(required=False, allow_blank=True)
    lines = OrderLineInputSerializer(many=True, required=False)


class ReasonActionSerializer(serializers.Serializer):
    """带原因/说明的通用动作入参。"""

    reason = serializers.CharField(required=False, allow_blank=True, default="")
    comment = serializers.CharField(required=False, allow_blank=True, default="")

class ShipmentLineSerializer(ReferenceIdSerializer):
    material_code = serializers.CharField(source="material.code", read_only=True)
    material_name = serializers.CharField(source="material.name", read_only=True)
    order_line_no = serializers.IntegerField(source="order_line.line_no", read_only=True)
    location_name = serializers.CharField(source="location.name", read_only=True, default="")

    class Meta:
        model = SalesShipmentLine
        fields = (
            "id",
            "shipment_id",
            "line_no",
            "order_line_id",
            "order_line_no",
            "material_id",
            "material_code",
            "material_name",
            "quantity",
            "location_id",
            "location_name",
            "batch_no",
            "roll_no",
            "remark",
            "version",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "line_no",
            "order_line_no",
            "material_code",
            "material_name",
            "location_name",
            *READ_ONLY[1:],
        )


class SalesShipmentSerializer(ReferenceIdSerializer):
    lines = ShipmentLineSerializer(many=True, read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    order_no = serializers.CharField(source="sales_order.order_no", read_only=True)
    customer_name = serializers.CharField(source="customer.name", read_only=True)
    company_name = serializers.CharField(source="company.name", read_only=True)
    warehouse_name = serializers.CharField(source="warehouse.name", read_only=True, default="")
    shipped_by_name = serializers.SerializerMethodField()

    class Meta:
        model = SalesShipment
        fields = (
            "id",
            "company_id",
            "company_name",
            "shipment_no",
            "sales_order_id",
            "order_no",
            "customer_id",
            "customer_name",
            "status",
            "status_display",
            "warehouse_id",
            "warehouse_name",
            "shipped_at",
            "shipped_by_name",
            "receiver_name",
            "receiver_phone",
            "delivery_address",
            "carrier",
            "tracking_no",
            "issue_document_id",
            "remark",
            "lines",
            "version",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "shipment_no",
            "customer_id",
            "customer_name",
            "status",
            "shipped_at",
            "shipped_by_name",
            "issue_document_id",
            "company_name",
            "warehouse_name",
            "order_no",
            "lines",
            *READ_ONLY[1:],
        )

    def get_shipped_by_name(self, obj: SalesShipment) -> str:
        return _account_name(obj.shipped_by)


class ShipmentLineInputSerializer(serializers.Serializer):
    order_line_id = serializers.IntegerField(min_value=1)
    quantity = serializers.DecimalField(max_digits=20, decimal_places=6)
    location_id = serializers.IntegerField(required=False, allow_null=True)
    batch_no = serializers.CharField(required=False, allow_blank=True, default="", max_length=64)
    roll_no = serializers.CharField(required=False, allow_blank=True, default="", max_length=64)
    remark = serializers.CharField(required=False, allow_blank=True, default="", max_length=255)

    def validate_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError("发货数量必须大于 0。")
        return value


class ShipmentWriteSerializer(serializers.Serializer):
    shipment_no = serializers.CharField(required=False, allow_blank=True, max_length=32)
    sales_order_id = serializers.IntegerField(min_value=1)
    warehouse_id = serializers.IntegerField(required=False, allow_null=True)
    receiver_name = serializers.CharField(required=False, allow_blank=True, default="", max_length=64)
    receiver_phone = serializers.CharField(required=False, allow_blank=True, default="", max_length=32)
    delivery_address = serializers.CharField(
        required=False, allow_blank=True, default="", max_length=255
    )
    carrier = serializers.CharField(required=False, allow_blank=True, default="", max_length=64)
    tracking_no = serializers.CharField(required=False, allow_blank=True, default="", max_length=64)
    remark = serializers.CharField(required=False, allow_blank=True, default="")
    lines = ShipmentLineInputSerializer(many=True)


class ShipmentUpdateSerializer(serializers.Serializer):
    receiver_name = serializers.CharField(required=False, allow_blank=True, max_length=64)
    receiver_phone = serializers.CharField(required=False, allow_blank=True, max_length=32)
    delivery_address = serializers.CharField(required=False, allow_blank=True, max_length=255)
    carrier = serializers.CharField(required=False, allow_blank=True, max_length=64)
    tracking_no = serializers.CharField(required=False, allow_blank=True, max_length=64)
    remark = serializers.CharField(required=False, allow_blank=True)
    lines = ShipmentLineInputSerializer(many=True, required=False)


class ReturnLineSerializer(ReferenceIdSerializer):
    material_code = serializers.CharField(source="material.code", read_only=True)
    material_name = serializers.CharField(source="material.name", read_only=True)
    order_line_no = serializers.IntegerField(source="order_line.line_no", read_only=True)
    location_name = serializers.CharField(source="location.name", read_only=True, default="")

    class Meta:
        model = SalesReturnLine
        fields = (
            "id",
            "return_doc_id",
            "line_no",
            "order_line_id",
            "order_line_no",
            "material_id",
            "material_code",
            "material_name",
            "quantity",
            "location_id",
            "location_name",
            "batch_no",
            "roll_no",
            "remark",
            "version",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "line_no",
            "order_line_no",
            "material_code",
            "material_name",
            "location_name",
            *READ_ONLY[1:],
        )


class SalesReturnSerializer(ReferenceIdSerializer):
    lines = ReturnLineSerializer(many=True, read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    inspection_result_display = serializers.CharField(
        source="get_inspection_result_display", read_only=True
    )
    order_no = serializers.CharField(source="sales_order.order_no", read_only=True)
    shipment_no = serializers.CharField(source="shipment.shipment_no", read_only=True, default="")
    customer_name = serializers.CharField(source="customer.name", read_only=True)
    company_name = serializers.CharField(source="company.name", read_only=True)
    warehouse_name = serializers.CharField(source="warehouse.name", read_only=True, default="")
    received_by_name = serializers.SerializerMethodField()
    inspected_by_name = serializers.SerializerMethodField()

    class Meta:
        model = SalesReturn
        fields = (
            "id",
            "company_id",
            "company_name",
            "return_no",
            "sales_order_id",
            "order_no",
            "shipment_id",
            "shipment_no",
            "customer_id",
            "customer_name",
            "status",
            "status_display",
            "warehouse_id",
            "warehouse_name",
            "reason",
            "received_at",
            "received_by_name",
            "inspection_result",
            "inspection_result_display",
            "inspected_at",
            "inspected_by_name",
            "inspection_remark",
            "receipt_document_id",
            "quality_document_id",
            "remark",
            "lines",
            "version",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "return_no",
            "customer_id",
            "customer_name",
            "status",
            "received_at",
            "received_by_name",
            "inspection_result",
            "inspected_at",
            "inspected_by_name",
            "inspection_remark",
            "receipt_document_id",
            "quality_document_id",
            "company_name",
            "warehouse_name",
            "order_no",
            "shipment_no",
            "lines",
            *READ_ONLY[1:],
        )

    def get_received_by_name(self, obj: SalesReturn) -> str:
        return _account_name(obj.received_by)

    def get_inspected_by_name(self, obj: SalesReturn) -> str:
        return _account_name(obj.inspected_by)


class ReturnLineInputSerializer(serializers.Serializer):
    order_line_id = serializers.IntegerField(min_value=1)
    quantity = serializers.DecimalField(max_digits=20, decimal_places=6)
    location_id = serializers.IntegerField(required=False, allow_null=True)
    batch_no = serializers.CharField(required=False, allow_blank=True, default="", max_length=64)
    roll_no = serializers.CharField(required=False, allow_blank=True, default="", max_length=64)
    remark = serializers.CharField(required=False, allow_blank=True, default="", max_length=255)

    def validate_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError("退货数量必须大于 0。")
        return value


class ReturnWriteSerializer(serializers.Serializer):
    return_no = serializers.CharField(required=False, allow_blank=True, max_length=32)
    sales_order_id = serializers.IntegerField(min_value=1)
    shipment_id = serializers.IntegerField(required=False, allow_null=True)
    warehouse_id = serializers.IntegerField(required=False, allow_null=True)
    reason = serializers.CharField(required=False, allow_blank=True, default="", max_length=255)
    remark = serializers.CharField(required=False, allow_blank=True, default="")
    lines = ReturnLineInputSerializer(many=True)


class ReturnUpdateSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, max_length=255)
    warehouse_id = serializers.IntegerField(required=False, allow_null=True)
    remark = serializers.CharField(required=False, allow_blank=True)
    lines = ReturnLineInputSerializer(many=True, required=False)


class InspectReturnSerializer(serializers.Serializer):
    result = serializers.ChoiceField(choices=["qualified", "rejected"])
    remark = serializers.CharField(required=False, allow_blank=True, default="")
