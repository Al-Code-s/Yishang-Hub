from __future__ import annotations

from rest_framework import serializers

from apps.core.serializers import ReferenceIdSerializer
from apps.masterdata.models import (
    Color,
    FabricProfile,
    Identifier,
    Material,
    MaterialCategory,
    Size,
    Sku,
    Style,
    UoM,
    UoMConversion,
)


class UoMSerializer(ReferenceIdSerializer):
    class Meta:
        model = UoM
        fields = (
            "id", "code", "name", "category", "decimal_places", "is_active", "remark",
            "version", "created_at", "updated_at",
        )
        read_only_fields = ("id", "version", "created_at", "updated_at")


class UoMConversionSerializer(ReferenceIdSerializer):
    from_uom_name = serializers.SerializerMethodField()
    to_uom_name = serializers.SerializerMethodField()

    class Meta:
        model = UoMConversion
        fields = (
            "id", "from_uom_id", "from_uom_name", "to_uom_id", "to_uom_name", "factor",
            "is_fixed", "is_active", "remark", "version", "created_at", "updated_at",
        )
        read_only_fields = ("id", "from_uom_name", "to_uom_name", "version", "created_at", "updated_at")

    def get_from_uom_name(self, obj: UoMConversion) -> str:
        return obj.from_uom.name if obj.from_uom_id else ""

    def get_to_uom_name(self, obj: UoMConversion) -> str:
        return obj.to_uom.name if obj.to_uom_id else ""

    def validate(self, attrs):
        source = attrs.get("from_uom", getattr(self.instance, "from_uom", None))
        target = attrs.get("to_uom", getattr(self.instance, "to_uom", None))
        if source is not None and target is not None and source.pk == target.pk:
            raise serializers.ValidationError({"to_uom_id": "换算的源单位与目标单位不能相同。"})
        return attrs


class MaterialCategorySerializer(ReferenceIdSerializer):
    parent_name = serializers.SerializerMethodField()

    class Meta:
        model = MaterialCategory
        fields = (
            "id", "parent_id", "parent_name", "code", "name", "category_type",
            "sort_order", "is_active", "remark", "version", "created_at", "updated_at",
        )
        read_only_fields = ("id", "parent_name", "version", "created_at", "updated_at")

    def get_parent_name(self, obj: MaterialCategory) -> str:
        return obj.parent.name if obj.parent_id else ""


class FabricProfileSerializer(ReferenceIdSerializer):
    class Meta:
        model = FabricProfile
        fields = (
            "id", "composition", "width_cm", "gram_weight", "default_color_no",
            "dye_lot_required", "shrinkage_rate",
        )
        read_only_fields = ("id",)


class MaterialSerializer(ReferenceIdSerializer):
    category_name = serializers.SerializerMethodField()
    category_type = serializers.SerializerMethodField()
    base_uom_name = serializers.SerializerMethodField()
    purchase_uom_name = serializers.SerializerMethodField()
    sales_uom_name = serializers.SerializerMethodField()
    company_name = serializers.SerializerMethodField()
    fabric_profile = FabricProfileSerializer(required=False, allow_null=True)

    class Meta:
        model = Material
        fields = (
            "id", "company_id", "company_name", "code", "name", "category_id", "category_name",
            "category_type", "spec", "base_uom_id", "base_uom_name", "purchase_uom_id",
            "purchase_uom_name", "purchase_factor", "sales_uom_id", "sales_uom_name",
            "sales_factor", "is_batch_managed", "is_roll_managed", "is_serial_managed",
            "safe_stock", "purchase_price", "reference_cost", "brand", "season", "year",
            "series", "image", "is_active", "remark", "fabric_profile",
            "version", "created_at", "updated_at",
        )
        read_only_fields = (
            "id", "company_name", "category_name", "category_type", "base_uom_name",
            "purchase_uom_name", "sales_uom_name", "version", "created_at", "updated_at",
        )

    def get_category_name(self, obj: Material) -> str:
        return obj.category.name if obj.category_id else ""

    def get_category_type(self, obj: Material) -> str:
        return obj.category.category_type if obj.category_id else ""

    def get_base_uom_name(self, obj: Material) -> str:
        return obj.base_uom.name if obj.base_uom_id else ""

    def get_purchase_uom_name(self, obj: Material) -> str:
        return obj.purchase_uom.name if obj.purchase_uom_id else ""

    def get_sales_uom_name(self, obj: Material) -> str:
        return obj.sales_uom.name if obj.sales_uom_id else ""

    def get_company_name(self, obj: Material) -> str:
        return obj.company.name if obj.company_id else ""

    def validate(self, attrs):
        category = attrs.get("category", getattr(self.instance, "category", None))
        profile = attrs.get("fabric_profile")
        is_roll = attrs.get("is_roll_managed", getattr(self.instance, "is_roll_managed", False))
        if profile and category is not None and category.category_type != "fabric" and not is_roll:
            raise serializers.ValidationError(
                {"fabric_profile": "仅面料类物料可维护面料属性。"}
            )
        return attrs

    def create(self, validated_data):
        profile_data = validated_data.pop("fabric_profile", None)
        material = Material.objects.create(**validated_data)
        if profile_data:
            FabricProfile.objects.create(material=material, **profile_data)
        return material

    def update(self, instance, validated_data):
        profile_data = validated_data.pop("fabric_profile", None)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()
        if profile_data is not None:
            FabricProfile.objects.update_or_create(material=instance, defaults=profile_data)
        return instance

    def to_representation(self, instance):
        data = super().to_representation(instance)
        profile = getattr(instance, "fabric_profile", None)
        data["fabric_profile"] = FabricProfileSerializer(profile).data if profile else None
        return data


class ColorSerializer(ReferenceIdSerializer):
    class Meta:
        model = Color
        fields = (
            "id", "code", "name", "hex_code", "sort_order", "is_active", "remark",
            "version", "created_at", "updated_at",
        )
        read_only_fields = ("id", "version", "created_at", "updated_at")


class SizeSerializer(ReferenceIdSerializer):
    class Meta:
        model = Size
        fields = (
            "id", "code", "name", "size_group", "sort_order", "is_active", "remark",
            "version", "created_at", "updated_at",
        )
        read_only_fields = ("id", "version", "created_at", "updated_at")


class StyleSerializer(ReferenceIdSerializer):
    company_name = serializers.SerializerMethodField()
    category_name = serializers.SerializerMethodField()
    sku_count = serializers.SerializerMethodField()

    class Meta:
        model = Style
        fields = (
            "id", "company_id", "company_name", "code", "name", "category_id", "category_name",
            "size_group", "brand", "season", "year", "series", "description", "image",
            "sku_count", "is_active", "remark", "version", "created_at", "updated_at",
        )
        read_only_fields = (
            "id", "company_name", "category_name", "sku_count", "version", "created_at", "updated_at",
        )

    def get_company_name(self, obj: Style) -> str:
        return obj.company.name if obj.company_id else ""

    def get_category_name(self, obj: Style) -> str:
        return obj.category.name if obj.category_id else ""

    def get_sku_count(self, obj: Style) -> int:
        return obj.skus.count()


class SkuSerializer(ReferenceIdSerializer):
    style_code = serializers.SerializerMethodField()
    style_name = serializers.SerializerMethodField()
    color_name = serializers.SerializerMethodField()
    size_name = serializers.SerializerMethodField()
    material_code = serializers.SerializerMethodField()
    company_name = serializers.SerializerMethodField()

    class Meta:
        model = Sku
        fields = (
            "id", "company_id", "company_name", "style_id", "style_code", "style_name",
            "color_id", "color_name", "size_id", "size_name", "code", "barcode",
            "material_id", "material_code", "is_active", "remark",
            "version", "created_at", "updated_at",
        )
        read_only_fields = (
            "id", "company_name", "style_code", "style_name", "color_name", "size_name",
            "material_code", "version", "created_at", "updated_at",
        )

    def get_style_code(self, obj: Sku) -> str:
        return obj.style.code if obj.style_id else ""

    def get_style_name(self, obj: Sku) -> str:
        return obj.style.name if obj.style_id else ""

    def get_color_name(self, obj: Sku) -> str:
        return obj.color.name if obj.color_id else ""

    def get_size_name(self, obj: Sku) -> str:
        return obj.size.name if obj.size_id else ""

    def get_material_code(self, obj: Sku) -> str:
        return obj.material.code if obj.material_id else ""

    def get_company_name(self, obj: Sku) -> str:
        return obj.company.name if obj.company_id else ""


class SkuGenerateSerializer(serializers.Serializer):
    """按款式批量生成 SKU（颜色 × 尺码）。"""

    style_id = serializers.IntegerField()
    color_ids = serializers.ListField(child=serializers.IntegerField(), allow_empty=False)
    size_ids = serializers.ListField(child=serializers.IntegerField(), allow_empty=False)
    create_material = serializers.BooleanField(
        default=False, help_text="是否为每个 SKU 同时创建对应的成品库存物料"
    )
    category_id = serializers.IntegerField(
        required=False, allow_null=True, help_text="create_material=true 时使用的成品分类"
    )
    base_uom_id = serializers.IntegerField(
        required=False, allow_null=True, help_text="create_material=true 时使用的单位"
    )


class IdentifierSerializer(ReferenceIdSerializer):
    sku_code = serializers.SerializerMethodField()
    material_code = serializers.SerializerMethodField()

    class Meta:
        model = Identifier
        fields = (
            "id", "identifier_type", "value", "sku_id", "sku_code", "material_id",
            "material_code", "batch_no", "extra", "is_active", "remark",
            "version", "created_at", "updated_at",
        )
        read_only_fields = (
            "id", "sku_code", "material_code", "version", "created_at", "updated_at",
        )

    def get_sku_code(self, obj: Identifier) -> str:
        return obj.sku.code if obj.sku_id else ""

    def get_material_code(self, obj: Identifier) -> str:
        return obj.material.code if obj.material_id else ""

    def validate(self, attrs):
        identifier_type = attrs.get(
            "identifier_type", getattr(self.instance, "identifier_type", None)
        )
        sku = attrs.get("sku", getattr(self.instance, "sku", None))
        if identifier_type == "sku_barcode" and sku is None:
            raise serializers.ValidationError({"sku_id": "SKU 条码必须关联 SKU。"})
        if identifier_type == "batch" and not attrs.get("batch_no", ""):
            raise serializers.ValidationError({"batch_no": "批次码必须填写批次号。"})
        return attrs
