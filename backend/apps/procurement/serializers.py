"""采购模块序列化器。

约定：

* 只读序列化器返回中文标签字段（`*_display`）供列表展示，前端不硬编码标签；
* 输入序列器只接受业务字段，**金额一律不接受前端提交**（`amount`、`total_amount`
  等由服务层计算）；
* 收货数量、已收数量等派生字段只读，防止前端绕过累计逻辑。
"""

from __future__ import annotations

from rest_framework import serializers

from apps.core.serializers import ReferenceIdSerializer
from apps.procurement.models import (
    GoodsReceipt,
    GoodsReceiptLine,
    PurchaseOrder,
    PurchaseOrderLine,
    PurchaseRequisition,
    PurchaseRequisitionLine,
)

READ_ONLY = ("id", "version", "created_at", "updated_at")


def _user_name(account) -> str:
    if account is None:
        return ""
    return account.display_name or account.username


class RequisitionLineSerializer(ReferenceIdSerializer):
    material_code = serializers.CharField(source="material.code", read_only=True)
    material_name = serializers.CharField(source="material.name", read_only=True)
    uom_name = serializers.CharField(source="uom.name", read_only=True, default="")
    suggested_supplier_name = serializers.CharField(
        source="suggested_supplier.name", read_only=True, default=""
    )

    class Meta:
        model = PurchaseRequisitionLine
        fields = (
            "id",
            "requisition_id",
            "line_no",
            "material_id",
            "material_code",
            "material_name",
            "quantity",
            "uom_id",
            "uom_name",
            "needed_date",
            "suggested_supplier_id",
            "suggested_supplier_name",
            "ordered_quantity",
            "remark",
            "version",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "line_no", "ordered_quantity", *READ_ONLY[1:])


class RequisitionSerializer(ReferenceIdSerializer):
    lines = RequisitionLineSerializer(many=True, read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    request_type_display = serializers.CharField(source="get_request_type_display", read_only=True)
    applicant_name = serializers.SerializerMethodField()
    company_name = serializers.CharField(source="company.name", read_only=True)

    class Meta:
        model = PurchaseRequisition
        fields = (
            "id",
            "company_id",
            "company_name",
            "requisition_no",
            "request_type",
            "request_type_display",
            "status",
            "status_display",
            "applicant_id",
            "applicant_name",
            "department_id",
            "factory_id",
            "needed_date",
            "purpose",
            "approval_instance_id",
            "approved_at",
            "remark",
            "lines",
            "version",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "requisition_no",
            "status",
            "applicant_id",
            "applicant_name",
            "approval_instance_id",
            "approved_at",
            "company_name",
            "lines",
            *READ_ONLY[1:],
        )

    def get_applicant_name(self, obj: PurchaseRequisition) -> str:
        if not obj.applicant_id:
            return ""
        return obj.applicant.display_name or obj.applicant.username


class RequisitionLineInputSerializer(serializers.Serializer):
    material_id = serializers.IntegerField(min_value=1)
    quantity = serializers.DecimalField(max_digits=20, decimal_places=6)
    uom_id = serializers.IntegerField(required=False, allow_null=True)
    needed_date = serializers.DateField(required=False, allow_null=True)
    suggested_supplier_id = serializers.IntegerField(required=False, allow_null=True)
    remark = serializers.CharField(required=False, allow_blank=True, default="", max_length=255)

    def validate_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError("申请数量必须大于 0。")
        return value


class RequisitionWriteSerializer(serializers.Serializer):
    requisition_no = serializers.CharField(required=False, allow_blank=True, max_length=32)
    request_type = serializers.ChoiceField(
        choices=["normal", "planned", "urgent"], required=False, default="normal"
    )
    needed_date = serializers.DateField(required=False, allow_null=True)
    department_id = serializers.IntegerField(required=False, allow_null=True)
    factory_id = serializers.IntegerField(required=False, allow_null=True)
    purpose = serializers.CharField(required=False, allow_blank=True, default="", max_length=255)
    remark = serializers.CharField(required=False, allow_blank=True, default="")
    lines = RequisitionLineInputSerializer(many=True)


class RequisitionUpdateSerializer(serializers.Serializer):
    request_type = serializers.ChoiceField(choices=["normal", "planned", "urgent"], required=False)
    needed_date = serializers.DateField(required=False, allow_null=True)
    department_id = serializers.IntegerField(required=False, allow_null=True)
    factory_id = serializers.IntegerField(required=False, allow_null=True)
    purpose = serializers.CharField(required=False, allow_blank=True, max_length=255)
    remark = serializers.CharField(required=False, allow_blank=True)
    lines = RequisitionLineInputSerializer(many=True, required=False)


class OrderLineSerializer(ReferenceIdSerializer):
    material_code = serializers.CharField(source="material.code", read_only=True)
    material_name = serializers.CharField(source="material.name", read_only=True)
    uom_name = serializers.CharField(source="uom.name", read_only=True, default="")
    remaining_quantity = serializers.DecimalField(max_digits=20, decimal_places=6, read_only=True)

    class Meta:
        model = PurchaseOrderLine
        fields = (
            "id",
            "order_id",
            "line_no",
            "material_id",
            "material_code",
            "material_name",
            "quantity",
            "received_quantity",
            "remaining_quantity",
            "price",
            "amount",
            "uom_id",
            "uom_name",
            "expected_date",
            "warehouse_id",
            "source_line_id",
            "remark",
            "version",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "line_no",
            "received_quantity",
            "amount",
            *READ_ONLY[1:],
        )


class OrderSerializer(ReferenceIdSerializer):
    lines = OrderLineSerializer(many=True, read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    supplier_name = serializers.CharField(source="supplier.name", read_only=True)
    company_name = serializers.CharField(source="company.name", read_only=True)
    warehouse_name = serializers.CharField(source="warehouse.name", read_only=True, default="")
    buyer_name = serializers.CharField(source="buyer.name", read_only=True, default="")
    source_requisition_no = serializers.CharField(
        source="source_requisition.requisition_no", read_only=True, default=""
    )

    class Meta:
        model = PurchaseOrder
        fields = (
            "id",
            "company_id",
            "company_name",
            "order_no",
            "supplier_id",
            "supplier_name",
            "status",
            "status_display",
            "source_requisition_id",
            "source_requisition_no",
            "buyer_id",
            "buyer_name",
            "order_date",
            "expected_date",
            "warehouse_id",
            "warehouse_name",
            "currency",
            "tax_rate",
            "payment_terms",
            "total_amount",
            "tax_amount",
            "amount_with_tax",
            "supplier_exception",
            "supplier_exception_reason",
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
            "supplier_exception",
            "total_amount",
            "tax_amount",
            "amount_with_tax",
            "approval_instance_id",
            "approved_at",
            "closed_at",
            "company_name",
            "supplier_name",
            "warehouse_name",
            "buyer_name",
            "source_requisition_no",
            "lines",
            *READ_ONLY[1:],
        )


class OrderLineInputSerializer(serializers.Serializer):
    material_id = serializers.IntegerField(min_value=1)
    quantity = serializers.DecimalField(max_digits=20, decimal_places=6)
    price = serializers.DecimalField(max_digits=20, decimal_places=6, default=0)
    uom_id = serializers.IntegerField(required=False, allow_null=True)
    expected_date = serializers.DateField(required=False, allow_null=True)
    warehouse_id = serializers.IntegerField(required=False, allow_null=True)
    source_line_id = serializers.IntegerField(required=False, allow_null=True)
    remark = serializers.CharField(required=False, allow_blank=True, default="", max_length=255)

    def validate_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError("订单数量必须大于 0。")
        return value

    def validate_price(self, value):
        if value < 0:
            raise serializers.ValidationError("未税单价不能为负。")
        return value


class OrderWriteSerializer(serializers.Serializer):
    order_no = serializers.CharField(required=False, allow_blank=True, max_length=32)
    supplier_id = serializers.IntegerField(min_value=1)
    order_date = serializers.DateField(required=False, allow_null=True)
    expected_date = serializers.DateField(required=False, allow_null=True)
    warehouse_id = serializers.IntegerField(required=False, allow_null=True)
    buyer_id = serializers.IntegerField(required=False, allow_null=True)
    source_requisition_id = serializers.IntegerField(required=False, allow_null=True)
    currency = serializers.CharField(required=False, allow_blank=True, default="CNY", max_length=8)
    tax_rate = serializers.DecimalField(max_digits=18, decimal_places=10, required=False, default=0)
    payment_terms = serializers.CharField(required=False, allow_blank=True, default="", max_length=64)
    supplier_exception_reason = serializers.CharField(required=False, allow_blank=True, default="")
    remark = serializers.CharField(required=False, allow_blank=True, default="")
    lines = OrderLineInputSerializer(many=True)


class OrderUpdateSerializer(serializers.Serializer):
    order_date = serializers.DateField(required=False, allow_null=True)
    expected_date = serializers.DateField(required=False, allow_null=True)
    warehouse_id = serializers.IntegerField(required=False, allow_null=True)
    buyer_id = serializers.IntegerField(required=False, allow_null=True)
    currency = serializers.CharField(required=False, allow_blank=True, max_length=8)
    tax_rate = serializers.DecimalField(max_digits=18, decimal_places=10, required=False, allow_null=True)
    payment_terms = serializers.CharField(required=False, allow_blank=True, max_length=64)
    supplier_exception_reason = serializers.CharField(required=False, allow_blank=True)
    remark = serializers.CharField(required=False, allow_blank=True)
    lines = OrderLineInputSerializer(many=True, required=False)


class ConvertRequisitionSerializer(OrderWriteSerializer):
    """按申请转订单：供应商必填，行可选（不传表示按申请行未转数量全额转）。"""

    order_no = serializers.CharField(required=False, allow_blank=True, max_length=32)
    lines = serializers.ListField(child=serializers.DictField(), required=False)


class ReceiptLineSerializer(ReferenceIdSerializer):
    material_code = serializers.CharField(source="material.code", read_only=True)
    material_name = serializers.CharField(source="material.name", read_only=True)
    order_line_no = serializers.IntegerField(source="order_line.line_no", read_only=True)
    location_name = serializers.CharField(source="location.name", read_only=True, default="")

    class Meta:
        model = GoodsReceiptLine
        fields = (
            "id",
            "receipt_id",
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


class ReceiptSerializer(ReferenceIdSerializer):
    lines = ReceiptLineSerializer(many=True, read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    inspection_result_display = serializers.CharField(source="get_inspection_result_display", read_only=True)
    order_no = serializers.CharField(source="purchase_order.order_no", read_only=True)
    supplier_name = serializers.CharField(source="supplier.name", read_only=True)
    company_name = serializers.CharField(source="company.name", read_only=True)
    warehouse_name = serializers.CharField(source="warehouse.name", read_only=True, default="")
    received_by_name = serializers.SerializerMethodField()
    inspected_by_name = serializers.SerializerMethodField()

    class Meta:
        model = GoodsReceipt
        fields = (
            "id",
            "company_id",
            "company_name",
            "receipt_no",
            "purchase_order_id",
            "order_no",
            "supplier_id",
            "supplier_name",
            "status",
            "status_display",
            "warehouse_id",
            "warehouse_name",
            "received_at",
            "received_by_name",
            "supplier_delivery_no",
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
        read_only_fields = fields

    def get_received_by_name(self, obj: GoodsReceipt) -> str:
        return _user_name(obj.received_by)

    def get_inspected_by_name(self, obj: GoodsReceipt) -> str:
        return _user_name(obj.inspected_by)


class ReceiptLineInputSerializer(serializers.Serializer):
    order_line_id = serializers.IntegerField(min_value=1)
    quantity = serializers.DecimalField(max_digits=20, decimal_places=6)
    location_id = serializers.IntegerField(required=False, allow_null=True)
    batch_no = serializers.CharField(required=False, allow_blank=True, default="", max_length=64)
    roll_no = serializers.CharField(required=False, allow_blank=True, default="", max_length=64)
    remark = serializers.CharField(required=False, allow_blank=True, default="", max_length=255)

    def validate_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError("收货数量必须大于 0。")
        return value


class ReceiptWriteSerializer(serializers.Serializer):
    receipt_no = serializers.CharField(required=False, allow_blank=True, max_length=32)
    purchase_order_id = serializers.IntegerField(min_value=1)
    warehouse_id = serializers.IntegerField(required=False, allow_null=True)
    supplier_delivery_no = serializers.CharField(required=False, allow_blank=True, default="", max_length=64)
    remark = serializers.CharField(required=False, allow_blank=True, default="")
    lines = ReceiptLineInputSerializer(many=True)


class ReceiptUpdateSerializer(serializers.Serializer):
    warehouse_id = serializers.IntegerField(required=False, allow_null=True)
    supplier_delivery_no = serializers.CharField(required=False, allow_blank=True, max_length=64)
    remark = serializers.CharField(required=False, allow_blank=True)
    lines = ReceiptLineInputSerializer(many=True, required=False)


class ReasonActionSerializer(serializers.Serializer):
    """撤回/取消/关闭类动作：原因必填，便于审计追溯。"""

    reason = serializers.CharField(allow_blank=True, default="", max_length=255)
    comment = serializers.CharField(allow_blank=True, default="", max_length=255)


class InspectReceiptSerializer(serializers.Serializer):
    result = serializers.ChoiceField(choices=["qualified", "rejected"])
    remark = serializers.CharField(allow_blank=False, max_length=2000)
