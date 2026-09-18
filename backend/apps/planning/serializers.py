"""计划模块序列化器：BOM、工艺路线与 MRP。

约定（与采购 / 销售模块一致）：

* 只读序列化器返回中文标签（``*_display``）与联表名称，前端不硬编码标签；
* 输入序列化器只接受业务字段：**版本号、状态、审核人、含损耗用量等派生字段
  一律不接受前端提交**，由服务层计算或迁移；
* ``gross_quantity`` 由后端按 ``quantity × (1 + loss_rate)`` 计算，前端传入会被忽略；
* 明细行的关联对象（物料、单位、车间）在这里只做类型与存在性校验，
  数据范围由视图逐行校验（任务书 6.4：不能让前端 ID 绕过范围限制）。
"""

from __future__ import annotations

from datetime import timedelta

from rest_framework import serializers

from apps.core.serializers import ReferenceIdSerializer
from apps.core.services import business_today
from apps.planning.models import (
    Bom,
    BomLine,
    MrpBucket,
    MrpDemandLine,
    MrpRun,
    MrpSuggestion,
    MrpSuggestionStatus,
    MrpSuggestionType,
    MrpSupplyLine,
    Routing,
    RoutingStep,
)
from apps.planning.mrp import DEFAULT_HORIZON_DAYS

READ_ONLY = ("id", "version", "created_at", "updated_at")


class BomLineSerializer(ReferenceIdSerializer):
    material_code = serializers.CharField(source="material.code", read_only=True)
    material_name = serializers.CharField(source="material.name", read_only=True)
    uom_name = serializers.CharField(source="uom.name", read_only=True, default="")
    line_type_display = serializers.CharField(source="get_line_type_display", read_only=True)
    substitute_for_line_no = serializers.IntegerField(
        source="substitute_for.line_no", read_only=True, default=None
    )
    gross_quantity = serializers.DecimalField(
        max_digits=20, decimal_places=6, read_only=True
    )

    class Meta:
        model = BomLine
        fields = (
            "id",
            "bom_id",
            "line_no",
            "material_id",
            "material_code",
            "material_name",
            "quantity",
            "loss_rate",
            "gross_quantity",
            "uom_id",
            "uom_name",
            "line_type",
            "line_type_display",
            "substitute_for_id",
            "substitute_for_line_no",
            "position",
            "is_key_material",
            "remark",
            "version",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "line_no",
            "gross_quantity",
            "substitute_for_id",
            *READ_ONLY[1:],
        )

class BomSerializer(ReferenceIdSerializer):
    lines = BomLineSerializer(many=True, read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    company_name = serializers.CharField(source="company.name", read_only=True)
    style_code = serializers.CharField(source="style.code", read_only=True)
    style_name = serializers.CharField(source="style.name", read_only=True)
    sku_code = serializers.CharField(source="sku.code", read_only=True, default="")
    scope_label = serializers.CharField(read_only=True)
    approved_by_name = serializers.SerializerMethodField()
    line_count = serializers.SerializerMethodField()

    class Meta:
        model = Bom
        fields = (
            "id",
            "company_id",
            "company_name",
            "code",
            "style_id",
            "style_code",
            "style_name",
            "sku_id",
            "sku_code",
            "scope_label",
            "version_no",
            "status",
            "status_display",
            "effective_from",
            "effective_to",
            "is_active",
            "approval_instance_id",
            "submitted_at",
            "approved_at",
            "approved_by_id",
            "approved_by_name",
            "remark",
            "lines",
            "line_count",
            "version",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "code",
            "version_no",
            "status",
            "is_active",
            "approval_instance_id",
            "submitted_at",
            "approved_at",
            "approved_by_id",
            "scope_label",
            "lines",
            "line_count",
            *READ_ONLY[1:],
        )

    def get_approved_by_name(self, obj: Bom) -> str:
        if not obj.approved_by_id:
            return ""
        return obj.approved_by.display_name or obj.approved_by.username

    def get_line_count(self, obj: Bom) -> int:
        return len(obj.lines.all())


class BomLineInputSerializer(serializers.Serializer):
    """BOM 明细输入行。含损耗用量不在这里出现（后端计算）。"""

    material_id = serializers.IntegerField(min_value=1)
    quantity = serializers.DecimalField(max_digits=20, decimal_places=6)
    loss_rate = serializers.DecimalField(
        max_digits=18, decimal_places=10, required=False, allow_null=True, default=0
    )
    uom_id = serializers.IntegerField(required=False, allow_null=True)
    line_type = serializers.ChoiceField(
        choices=["normal", "substitute"], required=False, default="normal"
    )
    substitute_for_line_no = serializers.IntegerField(
        required=False, allow_null=True, min_value=1
    )
    position = serializers.CharField(required=False, allow_blank=True, default="", max_length=64)
    is_key_material = serializers.BooleanField(required=False, default=False)
    remark = serializers.CharField(required=False, allow_blank=True, default="", max_length=255)

    def validate_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError("标准用量必须大于 0。")
        return value

    def validate_loss_rate(self, value):
        if value is None:
            return 0
        if value < 0 or value >= 1:
            raise serializers.ValidationError("损耗率必须在 [0, 1) 之间，例如 0.05 表示 5%。")
        return value

    def validate(self, attrs):
        if attrs.get("line_type") == "substitute" and not attrs.get("substitute_for_line_no"):
            raise serializers.ValidationError(
                {"substitute_for_line_no": "替代料行必须指定被替代的用料行号。"}
            )
        if attrs.get("line_type") == "normal" and attrs.get("substitute_for_line_no"):
            raise serializers.ValidationError(
                {"substitute_for_line_no": "只有替代料行才能指定被替代用料行。"}
            )
        return attrs

class BomWriteSerializer(serializers.Serializer):
    code = serializers.CharField(required=False, allow_blank=True, max_length=64)
    style_id = serializers.IntegerField(min_value=1)
    sku_id = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    effective_from = serializers.DateField(required=False, allow_null=True)
    effective_to = serializers.DateField(required=False, allow_null=True)
    remark = serializers.CharField(required=False, allow_blank=True, default="")
    lines = BomLineInputSerializer(many=True)

    def validate(self, attrs):
        start = attrs.get("effective_from")
        end = attrs.get("effective_to")
        if start and end and end < start:
            raise serializers.ValidationError({"effective_to": "失效日期不能早于生效日期。"})
        return attrs


class BomUpdateSerializer(serializers.Serializer):
    """修改草稿 BOM。版本号与状态不可改，只能派生新版本。"""

    effective_from = serializers.DateField(required=False, allow_null=True)
    effective_to = serializers.DateField(required=False, allow_null=True)
    remark = serializers.CharField(required=False, allow_blank=True)
    lines = BomLineInputSerializer(many=True, required=False)


class NewVersionSerializer(serializers.Serializer):
    """派生新版本：可选指定新版本的生效日期。"""

    effective_from = serializers.DateField(required=False, allow_null=True)
    comment = serializers.CharField(required=False, allow_blank=True, default="", max_length=255)


class ReasonActionSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=255)
    comment = serializers.CharField(required=False, allow_blank=True, default="", max_length=255)


class SubmitActionSerializer(serializers.Serializer):
    comment = serializers.CharField(required=False, allow_blank=True, default="", max_length=255)


class RoutingStepSerializer(ReferenceIdSerializer):
    workshop_name = serializers.CharField(source="workshop.name", read_only=True, default="")

    class Meta:
        model = RoutingStep
        fields = (
            "id",
            "routing_id",
            "sequence",
            "name",
            "workshop_id",
            "workshop_name",
            "workcenter",
            "equipment_requirement",
            "standard_hours",
            "is_quality_gate",
            "is_outsourced",
            "remark",
            "version",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", *READ_ONLY[1:])

class RoutingSerializer(ReferenceIdSerializer):
    steps = RoutingStepSerializer(many=True, read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    company_name = serializers.CharField(source="company.name", read_only=True)
    style_code = serializers.CharField(source="style.code", read_only=True)
    style_name = serializers.CharField(source="style.name", read_only=True)
    sku_code = serializers.CharField(source="sku.code", read_only=True, default="")
    scope_label = serializers.CharField(read_only=True)
    approved_by_name = serializers.SerializerMethodField()
    step_count = serializers.SerializerMethodField()
    quality_gate_count = serializers.SerializerMethodField()

    class Meta:
        model = Routing
        fields = (
            "id",
            "company_id",
            "company_name",
            "code",
            "style_id",
            "style_code",
            "style_name",
            "sku_id",
            "sku_code",
            "scope_label",
            "version_no",
            "status",
            "status_display",
            "effective_from",
            "effective_to",
            "is_active",
            "approval_instance_id",
            "submitted_at",
            "approved_at",
            "approved_by_id",
            "approved_by_name",
            "remark",
            "steps",
            "step_count",
            "quality_gate_count",
            "version",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "code",
            "version_no",
            "status",
            "is_active",
            "approval_instance_id",
            "submitted_at",
            "approved_at",
            "approved_by_id",
            "scope_label",
            "steps",
            "step_count",
            "quality_gate_count",
            *READ_ONLY[1:],
        )

    def get_approved_by_name(self, obj: Routing) -> str:
        if not obj.approved_by_id:
            return ""
        return obj.approved_by.display_name or obj.approved_by.username

    def get_step_count(self, obj: Routing) -> int:
        return len(obj.steps.all())

    def get_quality_gate_count(self, obj: Routing) -> int:
        return sum(1 for step in obj.steps.all() if step.is_quality_gate)


class RoutingStepInputSerializer(serializers.Serializer):
    sequence = serializers.IntegerField(required=False, min_value=1)
    name = serializers.CharField(max_length=64)
    workshop_id = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    workcenter = serializers.CharField(required=False, allow_blank=True, default="", max_length=64)
    equipment_requirement = serializers.CharField(
        required=False, allow_blank=True, default="", max_length=128
    )
    standard_hours = serializers.DecimalField(
        max_digits=20, decimal_places=6, required=False, allow_null=True, default=0
    )
    is_quality_gate = serializers.BooleanField(required=False, default=False)
    is_outsourced = serializers.BooleanField(required=False, default=False)
    remark = serializers.CharField(required=False, allow_blank=True, default="", max_length=255)

    def validate_standard_hours(self, value):
        if value is None:
            return 0
        if value < 0:
            raise serializers.ValidationError("标准工时不能为负数。")
        return value


class RoutingWriteSerializer(serializers.Serializer):
    code = serializers.CharField(required=False, allow_blank=True, max_length=64)
    style_id = serializers.IntegerField(min_value=1)
    sku_id = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    effective_from = serializers.DateField(required=False, allow_null=True)
    effective_to = serializers.DateField(required=False, allow_null=True)
    remark = serializers.CharField(required=False, allow_blank=True, default="")
    steps = RoutingStepInputSerializer(many=True, required=False)

    def validate(self, attrs):
        start = attrs.get("effective_from")
        end = attrs.get("effective_to")
        if start and end and end < start:
            raise serializers.ValidationError({"effective_to": "失效日期不能早于生效日期。"})
        return attrs


class RoutingUpdateSerializer(serializers.Serializer):
    effective_from = serializers.DateField(required=False, allow_null=True)
    effective_to = serializers.DateField(required=False, allow_null=True)
    remark = serializers.CharField(required=False, allow_blank=True)
    steps = RoutingStepInputSerializer(many=True, required=False)

# ---------------------------------------------------------------------------
# MRP（阶段 3 第二步）
# ---------------------------------------------------------------------------


class MrpRunSerializer(ReferenceIdSerializer):
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    bucket_display = serializers.CharField(source="get_bucket_display", read_only=True)
    company_name = serializers.CharField(source="company.name", read_only=True)
    warehouse_name = serializers.CharField(source="warehouse.name", read_only=True, default="")
    archived_by_name = serializers.CharField(source="archived_by.username", read_only=True, default="")
    # 由视图 queryset 的 annotate 提供，避免列表 N+1 查询
    demand_count = serializers.IntegerField(read_only=True)
    supply_count = serializers.IntegerField(read_only=True)
    suggestion_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = MrpRun
        fields = (
            "id",
            "company_id",
            "company_name",
            "run_no",
            "status",
            "status_display",
            "bucket",
            "bucket_display",
            "horizon_start",
            "horizon_end",
            "warehouse_id",
            "warehouse_name",
            "parameters",
            "summary",
            "demand_count",
            "supply_count",
            "suggestion_count",
            "started_at",
            "finished_at",
            "error_message",
            "archived_at",
            "archived_by_id",
            "archived_by_name",
            "remark",
            "version",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class MrpDemandLineSerializer(ReferenceIdSerializer):
    source_type_display = serializers.CharField(source="get_source_type_display", read_only=True)
    material_code = serializers.CharField(source="material.code", read_only=True)
    material_name = serializers.CharField(source="material.name", read_only=True)
    sku_code = serializers.CharField(source="sku.code", read_only=True, default="")
    style_code = serializers.CharField(source="style.code", read_only=True, default="")
    warehouse_name = serializers.CharField(source="warehouse.name", read_only=True, default="")

    class Meta:
        model = MrpDemandLine
        fields = (
            "id",
            "run_id",
            "line_no",
            "level",
            "source_type",
            "source_type_display",
            "source_id",
            "source_no",
            "source_line_no",
            "material_id",
            "material_code",
            "material_name",
            "sku_id",
            "sku_code",
            "style_id",
            "style_code",
            "warehouse_id",
            "warehouse_name",
            "quantity",
            "due_date",
            "bucket_date",
            "path",
            "exploded",
            "note",
            "version",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class MrpSupplyLineSerializer(ReferenceIdSerializer):
    source_type_display = serializers.CharField(source="get_source_type_display", read_only=True)
    material_code = serializers.CharField(source="material.code", read_only=True)
    material_name = serializers.CharField(source="material.name", read_only=True)
    warehouse_name = serializers.CharField(source="warehouse.name", read_only=True, default="")

    class Meta:
        model = MrpSupplyLine
        fields = (
            "id",
            "run_id",
            "line_no",
            "source_type",
            "source_type_display",
            "material_id",
            "material_code",
            "material_name",
            "warehouse_id",
            "warehouse_name",
            "quantity",
            "available_date",
            "bucket_date",
            "reference_type",
            "reference_id",
            "reference_no",
            "remark",
            "version",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class MrpSuggestionSerializer(ReferenceIdSerializer):
    suggestion_type_display = serializers.CharField(
        source="get_suggestion_type_display", read_only=True
    )
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    material_code = serializers.CharField(source="material.code", read_only=True)
    material_name = serializers.CharField(source="material.name", read_only=True)
    sku_code = serializers.CharField(source="sku.code", read_only=True, default="")
    style_code = serializers.CharField(source="style.code", read_only=True, default="")
    warehouse_name = serializers.CharField(source="warehouse.name", read_only=True, default="")
    uom_name = serializers.CharField(source="uom.name", read_only=True, default="")
    run_no = serializers.CharField(source="run.run_no", read_only=True)
    run_status = serializers.CharField(source="run.status", read_only=True)
    converted_by_name = serializers.CharField(
        source="converted_by.username", read_only=True, default=""
    )
    convertible = serializers.SerializerMethodField()

    class Meta:
        model = MrpSuggestion
        fields = (
            "id",
            "run_id",
            "line_no",
            "run_no",
            "run_status",
            "suggestion_type",
            "suggestion_type_display",
            "status",
            "status_display",
            "material_id",
            "material_code",
            "material_name",
            "sku_id",
            "sku_code",
            "style_id",
            "style_code",
            "warehouse_id",
            "warehouse_name",
            "quantity",
            "uom_id",
            "uom_name",
            "due_date",
            "bucket_date",
            "reason",
            "detail",
            "converted_document_type",
            "converted_document_id",
            "converted_document_no",
            "converted_at",
            "converted_by_id",
            "converted_by_name",
            "cancel_reason",
            "remark",
            "convertible",
            "version",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def get_convertible(self, obj: MrpSuggestion) -> bool:
        """前端据此禁用按钮；**真正的拦截在后端服务**（前端判断只是提示）。"""
        return (
            obj.status == MrpSuggestionStatus.OPEN
            and obj.suggestion_type == MrpSuggestionType.PURCHASE
        )


class MrpRunCreateSerializer(serializers.Serializer):
    """运行 MRP 的参数。需求区间缺省为「今天起 90 天」。"""

    company_id = serializers.IntegerField(required=False, allow_null=True)
    horizon_start = serializers.DateField(required=False, allow_null=True)
    horizon_end = serializers.DateField(required=False, allow_null=True)
    bucket = serializers.ChoiceField(choices=MrpBucket.choices, required=False, default=MrpBucket.DAY)
    warehouse_id = serializers.IntegerField(required=False, allow_null=True)
    remark = serializers.CharField(required=False, allow_blank=True, max_length=255)

    def validate(self, attrs: dict) -> dict:
        start = attrs.get("horizon_start") or business_today()
        end = attrs.get("horizon_end") or (start + timedelta(days=DEFAULT_HORIZON_DAYS))
        if end < start:
            raise serializers.ValidationError(
                {"horizon_end": "需求区间结束日期不能早于开始日期。"}
            )
        attrs["horizon_start"] = start
        attrs["horizon_end"] = end
        return attrs


class MrpArchiveSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, max_length=255)


class MrpCancelSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=255)


class MrpConvertSerializer(serializers.Serializer):
    needed_date = serializers.DateField(required=False, allow_null=True)
    remark = serializers.CharField(required=False, allow_blank=True, max_length=255)
