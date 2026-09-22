"""质量管理序列化器。"""

from __future__ import annotations

from rest_framework import serializers

from apps.core.serializers import ReferenceIdSerializer, ServerDerivedCodeSerializerMixin
from apps.factory.models import Company, Employee
from apps.qms.models import (
    QualityAlert,
    QualityAlertLevel,
    QualityInspectionItem,
    QualityInspectionOrder,
    QualityInspectionResult,
    QualityIssue,
    QualityJudgement,
)

_company_id = serializers.PrimaryKeyRelatedField(
    source="company", queryset=Company.objects.all(), required=False, label="所属公司"
)


def _name_of(instance, attribute: str) -> str:
    related = getattr(instance, attribute, None)
    return str(related) if related is not None else ""


class QualityInspectionItemSerializer(
    ServerDerivedCodeSerializerMixin, ReferenceIdSerializer
):
    company_id = _company_id
    company_name = serializers.SerializerMethodField()
    code = serializers.CharField(allow_blank=True, default="", max_length=32, label="项目编码")

    class Meta:
        model = QualityInspectionItem
        fields = (
            "id", "company_id", "company_name", "code", "name", "category", "value_type",
            "unit", "method", "standard_text", "lower_limit", "upper_limit", "is_active",
            "remark", "version", "created_at", "updated_at",
        )
        read_only_fields = (
            "id", "company_name", "version", "created_at", "updated_at",
        )

    def get_company_name(self, obj: QualityInspectionItem) -> str:
        return _name_of(obj, "company")

    def validate_code(self, value: str) -> str:
        code = (value or "").strip()
        if not code and self.instance is not None:
            raise serializers.ValidationError("项目编码不能为空。")
        return code

    def validate(self, attrs):
        """限量口径必须自洽：定量项目要有可比对的界限，下限不能大于上限。"""
        item = self.instance
        value_type = attrs.get("value_type", getattr(item, "value_type", None))
        lower = attrs.get("lower_limit", getattr(item, "lower_limit", None))
        upper = attrs.get("upper_limit", getattr(item, "upper_limit", None))
        if lower is not None and upper is not None and lower > upper:
            raise serializers.ValidationError({"upper_limit": "标准上限不能小于标准下限。"})
        if value_type == "quantitative" and lower is None and upper is None:
            raise serializers.ValidationError(
                {"lower_limit": "定量项目至少要给出上限或下限之一，否则无法自动判定。"}
            )
        return attrs


class QualityInspectionResultSerializer(ReferenceIdSerializer):
    item_code = serializers.SerializerMethodField()
    item_name = serializers.SerializerMethodField()
    item_category = serializers.SerializerMethodField()
    item_category_display = serializers.SerializerMethodField()
    unit = serializers.SerializerMethodField()
    lower_limit = serializers.SerializerMethodField()
    upper_limit = serializers.SerializerMethodField()
    method = serializers.SerializerMethodField()

    class Meta:
        model = QualityInspectionResult
        fields = (
            "id", "order_id", "item_id", "item_code", "item_name", "item_category",
            "item_category_display", "unit", "lower_limit", "upper_limit", "method",
            "measured_value", "text_value", "is_qualified", "remark", "sort_order",
        )
        read_only_fields = fields

    def get_item_code(self, obj: QualityInspectionResult) -> str:
        return obj.item.code if obj.item_id else ""

    def get_item_name(self, obj: QualityInspectionResult) -> str:
        return obj.item.name if obj.item_id else ""

    def get_item_category(self, obj: QualityInspectionResult) -> str:
        return obj.item.category if obj.item_id else ""

    def get_item_category_display(self, obj: QualityInspectionResult) -> str:
        return obj.item.get_category_display() if obj.item_id else ""

    def get_unit(self, obj: QualityInspectionResult) -> str:
        return obj.item.unit if obj.item_id else ""

    def get_lower_limit(self, obj: QualityInspectionResult):
        return obj.item.lower_limit if obj.item_id else None

    def get_upper_limit(self, obj: QualityInspectionResult):
        return obj.item.upper_limit if obj.item_id else None

    def get_method(self, obj: QualityInspectionResult) -> str:
        return obj.item.method if obj.item_id else ""


class QualityInspectionOrderSerializer(
    ServerDerivedCodeSerializerMixin, ReferenceIdSerializer
):
    company_id = _company_id
    company_name = serializers.SerializerMethodField()
    material_name = serializers.SerializerMethodField()
    supplier_name = serializers.SerializerMethodField()
    workshop_name = serializers.SerializerMethodField()
    production_line_name = serializers.SerializerMethodField()
    equipment_name = serializers.SerializerMethodField()
    inspector_name = serializers.SerializerMethodField()
    results = QualityInspectionResultSerializer(many=True, read_only=True)
    result_count = serializers.SerializerMethodField()
    failed_count = serializers.SerializerMethodField()
    order_no = serializers.CharField(allow_blank=True, default="", max_length=32, label="检验单号")

    class Meta:
        model = QualityInspectionOrder
        fields = (
            "id", "company_id", "company_name", "order_no", "inspection_type", "status",
            "judgement", "source_no", "material_id", "material_name", "product_desc",
            "batch_no", "supplier_id", "supplier_name", "workshop_id", "workshop_name",
            "production_line_id", "production_line_name", "equipment_id", "equipment_name",
            "quantity", "sample_quantity", "unit", "inspector_id", "inspector_name",
            "inspected_at", "judge_remark", "judged_at", "results", "result_count",
            "failed_count", "is_active", "remark", "version", "created_at", "updated_at",
        )
        read_only_fields = (
            "id", "company_name", "material_name", "supplier_name", "workshop_name",
            "production_line_name", "equipment_name", "inspector_name", "status",
            "judgement", "judged_at", "results", "result_count", "failed_count",
            "version", "created_at", "updated_at",
        )

    def get_company_name(self, obj: QualityInspectionOrder) -> str:
        return _name_of(obj, "company")

    def get_material_name(self, obj: QualityInspectionOrder) -> str:
        return _name_of(obj, "material")

    def get_supplier_name(self, obj: QualityInspectionOrder) -> str:
        return _name_of(obj, "supplier")

    def get_workshop_name(self, obj: QualityInspectionOrder) -> str:
        return _name_of(obj, "workshop")

    def get_production_line_name(self, obj: QualityInspectionOrder) -> str:
        return _name_of(obj, "production_line")

    def get_equipment_name(self, obj: QualityInspectionOrder) -> str:
        return _name_of(obj, "equipment")

    def get_inspector_name(self, obj: QualityInspectionOrder) -> str:
        return _name_of(obj, "inspector")

    def get_result_count(self, obj: QualityInspectionOrder) -> int:
        return len(obj.results.all())

    def get_failed_count(self, obj: QualityInspectionOrder) -> int:
        return sum(1 for row in obj.results.all() if not row.is_qualified)

    def validate_order_no(self, value: str) -> str:
        code = (value or "").strip()
        if not code and self.instance is not None:
            raise serializers.ValidationError("检验单号不能为空。")
        return code

    def validate(self, attrs):
        """物料 / 供应商必须属于所选公司，避免把 A 公司的档案挂到 B 公司的检验单上。"""
        company = attrs.get("company", getattr(self.instance, "company", None))
        for field_name, label in (("material", "物料"), ("supplier", "供应商")):
            related = attrs.get(field_name, getattr(self.instance, field_name, None))
            if related is not None and company is not None and related.company_id != company.pk:
                raise serializers.ValidationError({f"{field_name}_id": f"该{label}不属于所选公司。"})
        return attrs


class InspectionResultRowSerializer(serializers.Serializer):
    """录入检验结果的一行。定量项目的 ``is_qualified`` 由服务层忽略。"""

    item_id = serializers.PrimaryKeyRelatedField(
        source="item", queryset=QualityInspectionItem.objects.all(), label="检验项目"
    )
    measured_value = serializers.DecimalField(
        max_digits=20, decimal_places=6, required=False, allow_null=True, label="实测值"
    )
    text_value = serializers.CharField(required=False, allow_blank=True, default="", label="实测描述")
    is_qualified = serializers.BooleanField(required=False, allow_null=True, default=None, label="是否合格")
    remark = serializers.CharField(required=False, allow_blank=True, default="", label="备注")
    sort_order = serializers.IntegerField(required=False, min_value=0, default=0, label="排序")


class InspectionResultsInputSerializer(serializers.Serializer):
    results = InspectionResultRowSerializer(many=True, allow_empty=False, label="检验结果")


class OrderJudgeSerializer(serializers.Serializer):
    judgement = serializers.ChoiceField(
        choices=QualityJudgement.choices, required=False, allow_blank=True, label="判定结论"
    )
    judge_remark = serializers.CharField(required=False, allow_blank=True, default="", label="判定说明")
    inspector_id = serializers.PrimaryKeyRelatedField(
        source="inspector", queryset=Employee.objects.all(), required=False, allow_null=True,
        label="检验员",
    )
    inspected_at = serializers.DateTimeField(required=False, allow_null=True, label="检验时间")


class QualityAlertSerializer(ServerDerivedCodeSerializerMixin, ReferenceIdSerializer):
    company_id = _company_id
    company_name = serializers.SerializerMethodField()
    order_no = serializers.SerializerMethodField()
    material_name = serializers.SerializerMethodField()
    handler_name = serializers.SerializerMethodField()
    alert_no = serializers.CharField(allow_blank=True, default="", max_length=32, label="报警编号")

    class Meta:
        model = QualityAlert
        fields = (
            "id", "company_id", "company_name", "alert_no", "order_id", "order_no", "level",
            "status", "title", "description", "material_id", "material_name", "batch_no",
            "handler_id", "handler_name", "handled_at", "close_remark", "closed_at",
            "version", "created_at", "updated_at",
        )
        read_only_fields = (
            "id", "company_name", "order_no", "material_name", "handler_name", "status",
            "handled_at", "closed_at", "version", "created_at", "updated_at",
        )

    def get_company_name(self, obj: QualityAlert) -> str:
        return _name_of(obj, "company")

    def get_order_no(self, obj: QualityAlert) -> str:
        return obj.order.order_no if obj.order_id else ""

    def get_material_name(self, obj: QualityAlert) -> str:
        return _name_of(obj, "material")

    def get_handler_name(self, obj: QualityAlert) -> str:
        return _name_of(obj, "handler")

    def validate_alert_no(self, value: str) -> str:
        code = (value or "").strip()
        if not code and self.instance is not None:
            raise serializers.ValidationError("报警编号不能为空。")
        return code


class AlertHandleSerializer(serializers.Serializer):
    handler_id = serializers.PrimaryKeyRelatedField(
        source="handler", queryset=Employee.objects.all(), required=False, allow_null=True,
        label="处理人",
    )


class AlertCloseSerializer(serializers.Serializer):
    remark = serializers.CharField(label="处理说明")


class CreateIssueFromAlertSerializer(serializers.Serializer):
    title = serializers.CharField(label="问题标题")
    category = serializers.CharField(required=False, allow_blank=True, default="", label="问题分类")
    severity = serializers.ChoiceField(
        choices=QualityAlertLevel.choices, required=False, allow_blank=True, label="严重程度"
    )
    cause = serializers.CharField(required=False, allow_blank=True, default="", label="原因分析")
    corrective_action = serializers.CharField(
        required=False, allow_blank=True, default="", label="纠正措施"
    )
    preventive_action = serializers.CharField(
        required=False, allow_blank=True, default="", label="预防措施"
    )
    tags = serializers.ListField(
        child=serializers.CharField(max_length=32), required=False, default=list, label="标签"
    )


class QualityIssueSerializer(ServerDerivedCodeSerializerMixin, ReferenceIdSerializer):
    company_id = _company_id
    company_name = serializers.SerializerMethodField()
    material_name = serializers.SerializerMethodField()
    source_order_no = serializers.SerializerMethodField()
    source_alert_no = serializers.SerializerMethodField()
    issue_no = serializers.CharField(allow_blank=True, default="", max_length=32, label="问题编号")

    class Meta:
        model = QualityIssue
        fields = (
            "id", "company_id", "company_name", "issue_no", "title", "category", "severity",
            "phenomenon", "cause", "corrective_action", "preventive_action", "material_id",
            "material_name", "product_desc", "tags", "source_order_id", "source_order_no",
            "source_alert_id", "source_alert_no", "status", "published_at", "is_active",
            "remark", "version", "created_at", "updated_at",
        )
        read_only_fields = (
            "id", "company_name", "material_name", "source_order_no", "source_alert_no",
            "status", "published_at", "version", "created_at", "updated_at",
        )

    def get_company_name(self, obj: QualityIssue) -> str:
        return _name_of(obj, "company")

    def get_material_name(self, obj: QualityIssue) -> str:
        return _name_of(obj, "material")

    def get_source_order_no(self, obj: QualityIssue) -> str:
        return obj.source_order.order_no if obj.source_order_id else ""

    def get_source_alert_no(self, obj: QualityIssue) -> str:
        return obj.source_alert.alert_no if obj.source_alert_id else ""

    def validate_issue_no(self, value: str) -> str:
        code = (value or "").strip()
        if not code and self.instance is not None:
            raise serializers.ValidationError("问题编号不能为空。")
        return code

    def validate_phenomenon(self, value: str) -> str:
        text = (value or "").strip()
        if not text:
            raise serializers.ValidationError("问题现象不能为空。")
        return text


__all__ = [
    "AlertCloseSerializer",
    "AlertHandleSerializer",
    "CreateIssueFromAlertSerializer",
    "InspectionResultRowSerializer",
    "InspectionResultsInputSerializer",
    "OrderJudgeSerializer",
    "QualityAlertSerializer",
    "QualityInspectionItemSerializer",
    "QualityInspectionOrderSerializer",
    "QualityInspectionResultSerializer",
    "QualityIssueSerializer",
]
