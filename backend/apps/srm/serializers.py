from __future__ import annotations

from datetime import date

from rest_framework import serializers

from apps.core.serializers import ReferenceIdSerializer
from apps.srm.models import (
    EvaluationDimension,
    MissingDimensionPolicy,
    Supplier,
    SupplierContact,
    SupplierEvaluation,
    SupplierEvaluationLine,
    SupplierEvaluationWeight,
    SupplierQualification,
)


class SupplierSerializer(ReferenceIdSerializer):
    company_name = serializers.SerializerMethodField()
    buyer_name = serializers.SerializerMethodField()

    class Meta:
        model = Supplier
        fields = (
            "id", "company_id", "company_name", "code", "name", "short_name",
            "category", "grade", "admission_status", "payment_terms", "tax_no",
            "address", "primary_contact_name", "primary_contact_phone",
            "buyer_id", "buyer_name", "tags", "is_active", "remark",
            "version", "created_at", "updated_at",
        )
        read_only_fields = ("id", "company_name", "buyer_name", "version", "created_at", "updated_at")

    def get_company_name(self, obj: Supplier) -> str:
        return obj.company.name if obj.company_id else ""

    def get_buyer_name(self, obj: Supplier) -> str:
        return obj.buyer.name if obj.buyer_id else ""

    def validate_code(self, value: str) -> str:
        code = (value or "").strip()
        if not code:
            raise serializers.ValidationError("供应商编码不能为空。")
        return code

    def validate_tags(self, value):
        if value in (None, ""):
            return []
        if not isinstance(value, list):
            raise serializers.ValidationError("标签必须是字符串数组。")
        return [str(item).strip() for item in value if str(item).strip()]


class SupplierContactSerializer(ReferenceIdSerializer):
    supplier_name = serializers.SerializerMethodField()
    company_id = serializers.SerializerMethodField()

    class Meta:
        model = SupplierContact
        fields = (
            "id", "supplier_id", "supplier_name", "company_id", "name", "position",
            "phone", "email", "is_primary", "is_active", "remark",
            "version", "created_at", "updated_at",
        )
        read_only_fields = (
            "id", "supplier_name", "company_id", "version", "created_at", "updated_at",
        )

    def get_supplier_name(self, obj: SupplierContact) -> str:
        return obj.supplier.name if obj.supplier_id else ""

    def get_company_id(self, obj: SupplierContact) -> int | None:
        return obj.supplier.company_id if obj.supplier_id else None

    def validate(self, attrs):
        supplier = attrs.get("supplier", getattr(self.instance, "supplier", None))
        name = attrs.get("name", getattr(self.instance, "name", None))
        if supplier is not None and name:
            duplicated = SupplierContact.objects.filter(supplier=supplier, name=name)
            if self.instance is not None:
                duplicated = duplicated.exclude(pk=self.instance.pk)
            if duplicated.exists():
                raise serializers.ValidationError({"name": "该供应商下已存在同名联系人。"})
        return attrs


class SupplierQualificationSerializer(ReferenceIdSerializer):
    supplier_name = serializers.SerializerMethodField()
    company_id = serializers.SerializerMethodField()
    days_to_expiry = serializers.SerializerMethodField()
    is_expired = serializers.SerializerMethodField()

    class Meta:
        model = SupplierQualification
        fields = (
            "id", "supplier_id", "supplier_name", "company_id", "qualification_type",
            "certificate_no", "issued_by", "issued_date", "expiry_date",
            "days_to_expiry", "is_expired", "is_active", "remark",
            "version", "created_at", "updated_at",
        )
        read_only_fields = (
            "id", "supplier_name", "company_id", "days_to_expiry", "is_expired",
            "version", "created_at", "updated_at",
        )

    def get_supplier_name(self, obj: SupplierQualification) -> str:
        return obj.supplier.name if obj.supplier_id else ""

    def get_company_id(self, obj: SupplierQualification) -> int | None:
        return obj.supplier.company_id if obj.supplier_id else None

    def get_days_to_expiry(self, obj: SupplierQualification) -> int | None:
        """剩余有效天数；未填写到期日时返回 null（前端显示「未登记到期日」）。"""
        if not obj.expiry_date:
            return None
        return (obj.expiry_date - date.today()).days

    def get_is_expired(self, obj: SupplierQualification) -> bool | None:
        if not obj.expiry_date:
            return None
        return obj.expiry_date < date.today()

    def validate(self, attrs):
        issued = attrs.get("issued_date", getattr(self.instance, "issued_date", None))
        expiry = attrs.get("expiry_date", getattr(self.instance, "expiry_date", None))
        if issued and expiry and expiry < issued:
            raise serializers.ValidationError({"expiry_date": "到期日期不能早于发证日期。"})
        supplier = attrs.get("supplier", getattr(self.instance, "supplier", None))
        certificate_no = attrs.get(
            "certificate_no", getattr(self.instance, "certificate_no", "")
        )
        qualification_type = attrs.get(
            "qualification_type", getattr(self.instance, "qualification_type", "")
        )
        if supplier is not None and certificate_no:
            duplicated = SupplierQualification.objects.filter(
                supplier=supplier,
                qualification_type=qualification_type,
                certificate_no__iexact=str(certificate_no).strip(),
            )
            if self.instance is not None:
                duplicated = duplicated.exclude(pk=self.instance.pk)
            if duplicated.exists():
                raise serializers.ValidationError(
                    {"certificate_no": "该供应商下同类型资质已存在相同证书编号。"}
                )
        return attrs


class SupplierEvaluationWeightSerializer(ReferenceIdSerializer):
    """权重配置（只读视图）。写入走 `EvaluationWeightWriteSerializer` + 服务层。"""

    company_name = serializers.SerializerMethodField()
    total_weight = serializers.SerializerMethodField()

    class Meta:
        model = SupplierEvaluationWeight
        fields = (
            "id", "company_id", "company_name", "version_no",
            "quality_weight", "technology_weight", "response_weight",
            "delivery_weight", "cost_weight", "total_weight",
            "is_active", "remark", "version", "created_at", "updated_at",
        )
        read_only_fields = fields

    def get_company_name(self, obj: SupplierEvaluationWeight) -> str:
        return obj.company.name if obj.company_id else ""

    def get_total_weight(self, obj: SupplierEvaluationWeight) -> str:
        return str(obj.total_weight)


class SupplierEvaluationLineSerializer(ReferenceIdSerializer):
    class Meta:
        model = SupplierEvaluationLine
        fields = (
            "id", "evaluation_id", "dimension", "raw_score", "raw_observation",
            "weight", "effective_weight", "weighted_score", "is_missing", "remark",
            "version", "created_at", "updated_at",
        )
        read_only_fields = fields


class SupplierEvaluationSerializer(ReferenceIdSerializer):
    company_name = serializers.SerializerMethodField()
    supplier_name = serializers.SerializerMethodField()
    supplier_code = serializers.SerializerMethodField()
    weight_config_version = serializers.SerializerMethodField()
    evaluated_by_name = serializers.SerializerMethodField()
    is_editable = serializers.BooleanField(read_only=True)
    lines = serializers.SerializerMethodField()

    class Meta:
        model = SupplierEvaluation
        fields = (
            "id", "company_id", "company_name", "evaluation_no",
            "supplier_id", "supplier_name", "supplier_code",
            "weight_config_id", "weight_config_version", "weight_snapshot",
            "missing_dimension_policy", "period_start", "period_end",
            "evaluated_by_id", "evaluated_by_name", "evaluated_at",
            "status", "total_score", "effective_weight_total", "grade",
            "missing_dimensions", "is_editable", "lines", "remark", "is_active",
            "version", "created_at", "updated_at",
        )
        read_only_fields = fields

    def get_company_name(self, obj: SupplierEvaluation) -> str:
        return obj.company.name if obj.company_id else ""

    def get_supplier_name(self, obj: SupplierEvaluation) -> str:
        return obj.supplier.name if obj.supplier_id else ""

    def get_supplier_code(self, obj: SupplierEvaluation) -> str:
        return obj.supplier.code if obj.supplier_id else ""

    def get_weight_config_version(self, obj: SupplierEvaluation) -> int | None:
        return obj.weight_config.version_no if obj.weight_config_id else None

    def get_evaluated_by_name(self, obj: SupplierEvaluation) -> str:
        return obj.evaluated_by.name if obj.evaluated_by_id else ""

    def get_lines(self, obj: SupplierEvaluation) -> list[dict]:
        return SupplierEvaluationLineSerializer(obj.lines.all(), many=True).data


class EvaluationWeightWriteSerializer(serializers.Serializer):
    """新建权重配置的入参；五项权重省略即视为 0，由服务层校验合计 100%。"""

    company_id = serializers.IntegerField(required=False, allow_null=True)
    quality_weight = serializers.DecimalField(
        max_digits=5, decimal_places=2, required=False, allow_null=True
    )
    technology_weight = serializers.DecimalField(
        max_digits=5, decimal_places=2, required=False, allow_null=True
    )
    response_weight = serializers.DecimalField(
        max_digits=5, decimal_places=2, required=False, allow_null=True
    )
    delivery_weight = serializers.DecimalField(
        max_digits=5, decimal_places=2, required=False, allow_null=True
    )
    cost_weight = serializers.DecimalField(
        max_digits=5, decimal_places=2, required=False, allow_null=True
    )
    is_active = serializers.BooleanField(required=False, default=True)
    remark = serializers.CharField(required=False, allow_blank=True, default="")


class EvaluationWeightUpdateSerializer(serializers.Serializer):
    """修改权重 = 派生新版本：只接收需要调整的项，其余沿用旧版本。

    注意：这里**不能**给字段设 ``default``，否则「没传」会被当成「改成默认值」，
    ``is_active`` 上的默认值尤其危险（会把停用的版本悄悄重新启用）。
    """

    quality_weight = serializers.DecimalField(
        max_digits=5, decimal_places=2, required=False, allow_null=True
    )
    technology_weight = serializers.DecimalField(
        max_digits=5, decimal_places=2, required=False, allow_null=True
    )
    response_weight = serializers.DecimalField(
        max_digits=5, decimal_places=2, required=False, allow_null=True
    )
    delivery_weight = serializers.DecimalField(
        max_digits=5, decimal_places=2, required=False, allow_null=True
    )
    cost_weight = serializers.DecimalField(
        max_digits=5, decimal_places=2, required=False, allow_null=True
    )
    is_active = serializers.BooleanField(required=False)
    remark = serializers.CharField(required=False, allow_blank=True)


class EvaluationWriteSerializer(serializers.Serializer):
    company_id = serializers.IntegerField(required=False, allow_null=True)
    evaluation_no = serializers.CharField(
        required=False, allow_blank=True, default="", max_length=32
    )
    supplier_id = serializers.IntegerField()
    weight_config_id = serializers.IntegerField(required=False, allow_null=True)
    missing_dimension_policy = serializers.ChoiceField(
        choices=MissingDimensionPolicy.choices,
        required=False,
        default=MissingDimensionPolicy.MARK_MISSING,
    )
    period_start = serializers.DateField(required=False, allow_null=True)
    period_end = serializers.DateField(required=False, allow_null=True)
    evaluated_by_id = serializers.IntegerField(required=False, allow_null=True)
    evaluated_at = serializers.DateTimeField(required=False, allow_null=True)
    remark = serializers.CharField(required=False, allow_blank=True, default="")


class EvaluationUpdateSerializer(serializers.Serializer):
    """草稿表头修改：只有期间、缺数据口径与备注可改（明细走 `lines` 动作）。"""

    missing_dimension_policy = serializers.ChoiceField(
        choices=MissingDimensionPolicy.choices, required=False
    )
    period_start = serializers.DateField(required=False, allow_null=True)
    period_end = serializers.DateField(required=False, allow_null=True)
    remark = serializers.CharField(required=False, allow_blank=True)


class EvaluationLineInputSerializer(serializers.Serializer):
    dimension = serializers.ChoiceField(choices=EvaluationDimension.choices)
    # 原始得分留空 = 该维度没有数据（会被标记缺失，不会当成 0 分）
    raw_score = serializers.DecimalField(
        max_digits=5, decimal_places=2, required=False, allow_null=True
    )
    raw_observation = serializers.JSONField(required=False)
    remark = serializers.CharField(required=False, allow_blank=True, default="")


class EvaluationLinesInputSerializer(serializers.Serializer):
    """五个维度必须各给一行：没有数据的维度把 raw_score 留空。"""

    lines = EvaluationLineInputSerializer(many=True, allow_empty=False)
