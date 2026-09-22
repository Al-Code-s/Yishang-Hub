"""生产执行（MES）序列化器。"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from rest_framework import serializers

from apps.core.constants import QUANTITY_DECIMAL_PLACES, QUANTITY_MAX_DIGITS
from apps.core.serializers import ReferenceIdSerializer, ServerDerivedCodeSerializerMixin
from apps.equipment.models import Equipment
from apps.factory.models import Company, Employee
from apps.masterdata.models import Material
from apps.mes.models import (
    ProductionOrder,
    ProductionOrderMaterial,
    ProductionOrderStep,
    ProductionReport,
)
from apps.wms.models import Location

_company_id = serializers.PrimaryKeyRelatedField(
    source="company", queryset=Company.objects.all(), required=False, label="所属公司"
)

_PERCENT = Decimal("0.01")


def _percent(value: Decimal) -> str:
    """比率转百分比字符串（保留 2 位），与看板里的合格率 / 报废率同一口径。"""
    return str((Decimal(value) * 100).quantize(_PERCENT, rounding=ROUND_HALF_UP))


def _quantity(**kwargs) -> serializers.DecimalField:
    kwargs.setdefault("max_digits", QUANTITY_MAX_DIGITS)
    kwargs.setdefault("decimal_places", QUANTITY_DECIMAL_PLACES)
    return serializers.DecimalField(**kwargs)


def _name_of(instance, attribute: str) -> str:
    related = getattr(instance, attribute, None)
    return str(related) if related is not None else ""


class ProductionOrderMaterialSerializer(ReferenceIdSerializer):
    material_code = serializers.SerializerMethodField()
    material_name = serializers.SerializerMethodField()
    location_name = serializers.SerializerMethodField()
    source_display = serializers.CharField(source="get_source_display", read_only=True)

    class Meta:
        model = ProductionOrderMaterial
        fields = (
            "id", "order_id", "line_no", "material_id", "material_code", "material_name",
            "source", "source_display", "required_quantity", "issued_quantity", "unit",
            "location_id", "location_name", "remark",
        )
        read_only_fields = fields

    def get_material_code(self, obj: ProductionOrderMaterial) -> str:
        return obj.material.code if obj.material_id else ""

    def get_material_name(self, obj: ProductionOrderMaterial) -> str:
        return obj.material.name if obj.material_id else ""

    def get_location_name(self, obj: ProductionOrderMaterial) -> str:
        return _name_of(obj, "location")


class ProductionOrderStepSerializer(ReferenceIdSerializer):
    workshop_name = serializers.SerializerMethodField()
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    inspection_order_no = serializers.SerializerMethodField()
    inspection_judgement = serializers.SerializerMethodField()

    class Meta:
        model = ProductionOrderStep
        fields = (
            "id", "order_id", "sequence", "name", "workshop_id", "workshop_name",
            "workcenter", "equipment_requirement", "standard_hours", "is_quality_gate",
            "is_outsourced", "status", "status_display", "reported_quantity",
            "qualified_quantity", "scrap_quantity", "started_at", "finished_at",
            "inspection_order_id", "inspection_order_no", "inspection_judgement", "remark",
        )
        read_only_fields = fields

    def get_workshop_name(self, obj: ProductionOrderStep) -> str:
        return _name_of(obj, "workshop")

    def get_inspection_order_no(self, obj: ProductionOrderStep) -> str:
        return obj.inspection_order.order_no if obj.inspection_order_id else ""

    def get_inspection_judgement(self, obj: ProductionOrderStep) -> str:
        if not obj.inspection_order_id:
            return ""
        return obj.inspection_order.get_judgement_display()


class ProductionReportSerializer(ReferenceIdSerializer):
    company_name = serializers.SerializerMethodField()
    order_no = serializers.SerializerMethodField()
    step_name = serializers.SerializerMethodField()
    step_sequence = serializers.SerializerMethodField()
    report_type_display = serializers.CharField(source="get_report_type_display", read_only=True)
    operator_name = serializers.SerializerMethodField()
    equipment_name = serializers.SerializerMethodField()

    class Meta:
        model = ProductionReport
        fields = (
            "id", "company_id", "company_name", "report_no", "order_id", "order_no",
            "step_id", "step_name", "step_sequence", "report_type", "report_type_display",
            "quantity", "qualified_quantity", "rework_quantity", "scrap_quantity",
            "operator_id", "operator_name", "equipment_id", "equipment_name", "work_hours",
            "started_at", "finished_at", "reported_at", "remark", "created_at", "updated_at",
        )
        read_only_fields = fields

    def get_company_name(self, obj: ProductionReport) -> str:
        return _name_of(obj, "company")

    def get_order_no(self, obj: ProductionReport) -> str:
        return obj.order.order_no if obj.order_id else ""

    def get_step_name(self, obj: ProductionReport) -> str:
        return obj.step.name if obj.step_id else ""

    def get_step_sequence(self, obj: ProductionReport) -> int | None:
        return obj.step.sequence if obj.step_id else None

    def get_operator_name(self, obj: ProductionReport) -> str:
        return _name_of(obj, "operator")

    def get_equipment_name(self, obj: ProductionReport) -> str:
        return _name_of(obj, "equipment")


class ProductionOrderSerializer(ServerDerivedCodeSerializerMixin, ReferenceIdSerializer):
    company_id = _company_id
    company_name = serializers.SerializerMethodField()
    style_name = serializers.SerializerMethodField()
    sku_name = serializers.SerializerMethodField()
    product_material_name = serializers.SerializerMethodField()
    factory_name = serializers.SerializerMethodField()
    workshop_name = serializers.SerializerMethodField()
    production_line_name = serializers.SerializerMethodField()
    owner_name = serializers.SerializerMethodField()
    material_warehouse_name = serializers.SerializerMethodField()
    receipt_warehouse_name = serializers.SerializerMethodField()
    issue_document_no = serializers.SerializerMethodField()
    receipt_document_no = serializers.SerializerMethodField()
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    source_type_display = serializers.CharField(source="get_source_type_display", read_only=True)
    progress_rate = serializers.SerializerMethodField()
    order_no = serializers.CharField(allow_blank=True, default="", max_length=32, label="工单号")
    materials = ProductionOrderMaterialSerializer(many=True, read_only=True)
    steps = ProductionOrderStepSerializer(many=True, read_only=True)
    report_count = serializers.SerializerMethodField()

    class Meta:
        model = ProductionOrder
        fields = (
            "id", "company_id", "company_name", "order_no", "source_type",
            "source_type_display", "source_no", "factory_id", "factory_name", "workshop_id",
            "workshop_name", "production_line_id", "production_line_name", "style_id",
            "style_name", "sku_id", "sku_name", "product_material_id", "product_material_name",
            "quantity", "completed_quantity", "qualified_quantity", "scrap_quantity", "unit",
            "status", "status_display", "planned_start", "planned_end", "actual_start",
            "actual_end", "material_warehouse_id", "material_warehouse_name",
            "receipt_warehouse_id", "receipt_warehouse_name", "bom_snapshot",
            "routing_snapshot", "owner_id", "owner_name", "released_at", "closed_at",
            "cancel_reason", "issue_document_id", "issue_document_no", "receipt_document_id",
            "receipt_document_no", "progress_rate", "materials", "steps", "report_count",
            "is_active", "remark", "version", "created_at", "updated_at",
        )
        read_only_fields = (
            "id", "company_name", "status", "completed_quantity", "qualified_quantity",
            "scrap_quantity", "bom_snapshot", "routing_snapshot", "released_at", "closed_at",
            "cancel_reason", "issue_document_id", "receipt_document_id", "materials", "steps",
            "style_name", "sku_name", "product_material_name", "factory_name", "workshop_name",
            "production_line_name", "owner_name", "material_warehouse_name",
            "receipt_warehouse_name", "issue_document_no", "receipt_document_no",
            "progress_rate", "report_count", "version", "created_at", "updated_at",
        )

    def get_company_name(self, obj: ProductionOrder) -> str:
        return _name_of(obj, "company")

    def get_style_name(self, obj: ProductionOrder) -> str:
        return _name_of(obj, "style")

    def get_sku_name(self, obj: ProductionOrder) -> str:
        return _name_of(obj, "sku")

    def get_product_material_name(self, obj: ProductionOrder) -> str:
        return _name_of(obj, "product_material")

    def get_factory_name(self, obj: ProductionOrder) -> str:
        return _name_of(obj, "factory")

    def get_workshop_name(self, obj: ProductionOrder) -> str:
        return _name_of(obj, "workshop")

    def get_production_line_name(self, obj: ProductionOrder) -> str:
        return _name_of(obj, "production_line")

    def get_owner_name(self, obj: ProductionOrder) -> str:
        return _name_of(obj, "owner")

    def get_material_warehouse_name(self, obj: ProductionOrder) -> str:
        return _name_of(obj, "material_warehouse")

    def get_receipt_warehouse_name(self, obj: ProductionOrder) -> str:
        return _name_of(obj, "receipt_warehouse")

    def get_issue_document_no(self, obj: ProductionOrder) -> str:
        return obj.issue_document.document_no if obj.issue_document_id else ""

    def get_receipt_document_no(self, obj: ProductionOrder) -> str:
        return obj.receipt_document.document_no if obj.receipt_document_id else ""

    def get_progress_rate(self, obj: ProductionOrder) -> str:
        return _percent(obj.progress_rate)

    def get_report_count(self, obj: ProductionOrder) -> int:
        return len(obj.reports.all())

    def validate_order_no(self, value: str) -> str:
        code = (value or "").strip()
        if not code and self.instance is not None:
            raise serializers.ValidationError("工单号不能为空。")
        return code


class ProductionMaterialRowSerializer(serializers.Serializer):
    material_id = serializers.PrimaryKeyRelatedField(
        source="material", queryset=Material.objects.all(), label="物料"
    )
    required_quantity = _quantity(label="用量")
    location_id = serializers.PrimaryKeyRelatedField(
        source="location", queryset=Location.objects.all(), required=False, allow_null=True,
        label="默认领料储位",
    )
    unit = serializers.CharField(required=False, allow_blank=True, default="", label="单位")
    remark = serializers.CharField(required=False, allow_blank=True, default="", label="备注")


class ProductionMaterialsInputSerializer(serializers.Serializer):
    materials = ProductionMaterialRowSerializer(many=True, label="工单用料")


class IssueMaterialRowSerializer(serializers.Serializer):
    material_id = serializers.PrimaryKeyRelatedField(
        source="material", queryset=Material.objects.all(), label="物料"
    )
    quantity = _quantity(label="领料数量")
    location_id = serializers.PrimaryKeyRelatedField(
        source="location", queryset=Location.objects.all(), required=False, allow_null=True,
        label="储位",
    )
    batch_no = serializers.CharField(required=False, allow_blank=True, default="", label="批次号")
    remark = serializers.CharField(required=False, allow_blank=True, default="", label="备注")


class IssueMaterialsInputSerializer(serializers.Serializer):
    """留空 lines 表示按工单用料的未领数量整单领料。"""

    lines = IssueMaterialRowSerializer(many=True, required=False, label="领料明细")


class ProductionReportInputSerializer(serializers.Serializer):
    order_id = serializers.PrimaryKeyRelatedField(
        source="order", queryset=ProductionOrder.objects.all(), required=False, allow_null=True,
        label="生产工单",
    )
    step_id = serializers.PrimaryKeyRelatedField(
        source="step", queryset=ProductionOrderStep.objects.all(), label="工序"
    )
    report_type = serializers.ChoiceField(
        choices=ProductionReport._meta.get_field("report_type").choices,
        required=False,
        default="normal",
        label="报工类型",
    )
    quantity = _quantity(label="报工数量")
    qualified_quantity = _quantity(required=False, default=0, label="合格数量")
    rework_quantity = _quantity(required=False, default=0, label="返工数量")
    scrap_quantity = _quantity(required=False, default=0, label="报废数量")
    operator_id = serializers.PrimaryKeyRelatedField(
        source="operator", queryset=Employee.objects.all(), required=False, allow_null=True,
        label="报工人",
    )
    equipment_id = serializers.PrimaryKeyRelatedField(
        source="equipment", queryset=Equipment.objects.all(), required=False, allow_null=True,
        label="生产设备",
    )
    work_hours = _quantity(required=False, default=0, label="实际工时")
    started_at = serializers.DateTimeField(required=False, allow_null=True, label="开工时间")
    finished_at = serializers.DateTimeField(required=False, allow_null=True, label="完工时间")
    remark = serializers.CharField(required=False, allow_blank=True, default="", label="备注")


class ReportActionInputSerializer(serializers.Serializer):
    remark = serializers.CharField(required=False, allow_blank=True, default="", label="说明")


class ReceiptInputSerializer(serializers.Serializer):
    location_id = serializers.PrimaryKeyRelatedField(
        source="location", queryset=Location.objects.all(), required=False, allow_null=True,
        label="入库储位",
    )
    batch_no = serializers.CharField(required=False, allow_blank=True, default="", label="批次号")


class ReasonActionSerializer(serializers.Serializer):
    """取消 / 作废类动作：必须写原因。"""

    reason = serializers.CharField(label="原因")


__all__ = [
    "IssueMaterialRowSerializer",
    "IssueMaterialsInputSerializer",
    "ProductionMaterialRowSerializer",
    "ProductionMaterialsInputSerializer",
    "ProductionOrderMaterialSerializer",
    "ProductionOrderSerializer",
    "ProductionOrderStepSerializer",
    "ProductionReportInputSerializer",
    "ProductionReportSerializer",
    "ReasonActionSerializer",
    "ReceiptInputSerializer",
    "ReportActionInputSerializer",
]
