"""主数据接口。

计量单位、颜色、尺码、物料分类是全公司共享的参考数据，不做数据范围收敛；
物料、款式、SKU 归属公司，按数据范围过滤。
"""

from __future__ import annotations

from django.db import transaction
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.exceptions import ObjectNotFound, ValidationFailed
from apps.core.models import AuditAction
from apps.core.services import record_audit, snapshot_fields
from apps.core.viewsets import ActiveFilterMixin, ScopedModelViewSet
from apps.masterdata.models import (
    Color,
    Identifier,
    Material,
    MaterialCategory,
    Size,
    Sku,
    Style,
    UoM,
    UoMConversion,
)
from apps.masterdata.serializers import (
    ColorSerializer,
    IdentifierSerializer,
    MaterialCategorySerializer,
    MaterialSerializer,
    SizeSerializer,
    SkuGenerateSerializer,
    SkuSerializer,
    StyleSerializer,
    UoMConversionSerializer,
    UoMSerializer,
)


class UoMViewSet(ActiveFilterMixin, ScopedModelViewSet):
    queryset = UoM.objects.all()
    serializer_class = UoMSerializer
    scope_fields = None  # 全局共享参考数据
    audit_fields = ("code", "name", "category", "decimal_places", "is_active")
    search_fields = ["code", "name"]
    filterset_fields = ["category"]
    ordering_fields = ["id", "code", "category"]
    uniqueness_error_map = {"code": "单位编码已存在。"}
    required_permissions = {
        "list": "masterdata.uom.view",
        "retrieve": "masterdata.uom.view",
        "create": "masterdata.uom.create",
        "partial_update": "masterdata.uom.update",
        "set_active": "masterdata.uom.update",
    }


class UoMConversionViewSet(ActiveFilterMixin, ScopedModelViewSet):
    queryset = UoMConversion.objects.select_related("from_uom", "to_uom").all()
    serializer_class = UoMConversionSerializer
    scope_fields = None
    audit_fields = ("from_uom_id", "to_uom_id", "factor", "is_fixed", "is_active")
    filterset_fields = ["from_uom_id", "to_uom_id", "is_fixed"]
    ordering_fields = ["id"]
    uniqueness_error_map = {"uq_uom_conversion_pair": "该单位换算关系已存在。"}
    required_permissions = {
        "list": "masterdata.uom.view",
        "retrieve": "masterdata.uom.view",
        "create": "masterdata.uom.create",
        "partial_update": "masterdata.uom.update",
        "set_active": "masterdata.uom.update",
    }


class MaterialCategoryViewSet(ActiveFilterMixin, ScopedModelViewSet):
    queryset = MaterialCategory.objects.select_related("parent").all()
    serializer_class = MaterialCategorySerializer
    scope_fields = None
    audit_fields = ("parent_id", "code", "name", "category_type", "sort_order", "is_active")
    search_fields = ["code", "name"]
    filterset_fields = ["category_type", "parent_id"]
    ordering_fields = ["id", "code", "sort_order"]
    uniqueness_error_map = {"code": "分类编码已存在。"}
    required_permissions = {
        "list": "masterdata.material_category.view",
        "retrieve": "masterdata.material_category.view",
        "create": "masterdata.material_category.create",
        "partial_update": "masterdata.material_category.update",
        "set_active": "masterdata.material_category.update",
    }


class MaterialViewSet(ActiveFilterMixin, ScopedModelViewSet):
    queryset = Material.objects.select_related(
        "company", "category", "base_uom", "purchase_uom", "sales_uom", "fabric_profile"
    ).all()
    serializer_class = MaterialSerializer
    scope_fields = {"company_field": "company_id"}
    audit_fields = (
        "code", "name", "category_id", "spec", "base_uom_id", "is_batch_managed",
        "is_roll_managed", "safe_stock", "purchase_price", "is_active",
    )
    search_fields = ["code", "name", "spec", "brand", "series"]
    filterset_fields = ["company_id", "category_id", "category__category_type", "is_batch_managed", "is_roll_managed"]
    ordering_fields = ["id", "code", "name", "updated_at"]
    uniqueness_error_map = {"uq_material_company_code": "同一公司下物料编码已存在。"}
    required_permissions = {
        "list": "masterdata.material.view",
        "retrieve": "masterdata.material.view",
        "create": "masterdata.material.create",
        "partial_update": "masterdata.material.update",
        "set_active": "masterdata.material.deactivate",
    }


class ColorViewSet(ActiveFilterMixin, ScopedModelViewSet):
    queryset = Color.objects.all()
    serializer_class = ColorSerializer
    scope_fields = None
    audit_fields = ("code", "name", "hex_code", "sort_order", "is_active")
    search_fields = ["code", "name"]
    ordering_fields = ["id", "code", "sort_order"]
    uniqueness_error_map = {"code": "颜色编码已存在。"}
    required_permissions = {
        "list": "masterdata.color.view",
        "retrieve": "masterdata.color.view",
        "create": "masterdata.color.create",
        "partial_update": "masterdata.color.update",
        "set_active": "masterdata.color.update",
    }


class SizeViewSet(ActiveFilterMixin, ScopedModelViewSet):
    queryset = Size.objects.all()
    serializer_class = SizeSerializer
    scope_fields = None
    audit_fields = ("code", "name", "size_group", "sort_order", "is_active")
    search_fields = ["code", "name", "size_group"]
    filterset_fields = ["size_group"]
    ordering_fields = ["id", "code", "sort_order"]
    uniqueness_error_map = {"code": "尺码编码已存在。"}
    required_permissions = {
        "list": "masterdata.size.view",
        "retrieve": "masterdata.size.view",
        "create": "masterdata.size.create",
        "partial_update": "masterdata.size.update",
        "set_active": "masterdata.size.update",
    }


class StyleViewSet(ActiveFilterMixin, ScopedModelViewSet):
    queryset = Style.objects.select_related("company", "category").all()
    serializer_class = StyleSerializer
    scope_fields = {"company_field": "company_id"}
    audit_fields = (
        "code", "name", "category_id", "size_group", "brand", "season", "year",
        "series", "is_active",
    )
    search_fields = ["code", "name", "brand", "series"]
    filterset_fields = ["company_id", "category_id", "season", "year", "size_group"]
    ordering_fields = ["id", "code", "name"]
    uniqueness_error_map = {"uq_style_company_code": "同一公司下款式编码已存在。"}
    required_permissions = {
        "list": "masterdata.style.view",
        "retrieve": "masterdata.style.view",
        "create": "masterdata.style.create",
        "partial_update": "masterdata.style.update",
        "set_active": "masterdata.style.update",
    }


class SkuViewSet(ActiveFilterMixin, ScopedModelViewSet):
    queryset = Sku.objects.select_related("company", "style", "color", "size", "material").all()
    serializer_class = SkuSerializer
    scope_fields = {"company_field": "company_id"}
    audit_fields = ("code", "style_id", "color_id", "size_id", "barcode", "material_id", "is_active")
    search_fields = ["code", "barcode", "style__code", "style__name"]
    filterset_fields = ["company_id", "style_id", "color_id", "size_id", "is_active"]
    ordering_fields = ["id", "code"]
    uniqueness_error_map = {
        "uq_sku_company_code": "同一公司下 SKU 编码已存在。",
        "uq_sku_style_color_size": "该款式下“颜色 + 尺码”组合已存在。",
        "uq_sku_style_color_size_dup": "该款式下“颜色 + 尺码”组合已存在。",
    }
    required_permissions = {
        "list": "masterdata.sku.view",
        "retrieve": "masterdata.sku.view",
        "create": "masterdata.sku.create",
        "partial_update": "masterdata.sku.update",
        "set_active": "masterdata.sku.update",
        "generate": "masterdata.sku.generate",
    }

    def perform_create(self, serializer) -> None:
        sku = serializer.save()
        if not sku.barcode:
            sku.barcode = sku.code
            sku.save(update_fields=["barcode", "updated_at"])
        _register_sku_barcode(sku)
        record_audit(
            action=AuditAction.CREATE,
            instance=sku,
            changes=snapshot_fields(sku, self.audit_fields),
            object_repr=str(sku),
        )

    @action(detail=False, methods=["post"])
    def generate(self, request, *args, **kwargs):
        """按款式 + 颜色 × 尺码批量生成 SKU，已存在的组合跳过并回报。"""
        serializer = SkuGenerateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        style = Style.objects.filter(pk=data["style_id"]).first()
        if style is None:
            raise ObjectNotFound("款式不存在。", code="STYLE_NOT_FOUND")
        self._assert_in_scope(style)

        colors = list(Color.objects.filter(id__in=data["color_ids"], is_active=True))
        sizes = list(Size.objects.filter(id__in=data["size_ids"], is_active=True))
        if len(colors) != len(set(data["color_ids"])):
            raise ObjectNotFound("存在无效或已停用的颜色。", code="COLOR_NOT_FOUND")
        if len(sizes) != len(set(data["size_ids"])):
            raise ObjectNotFound("存在无效或已停用的尺码。", code="SIZE_NOT_FOUND")

        material_defaults = None
        if data["create_material"]:
            material_defaults = _resolve_finished_goods_defaults(data, style)

        created: list[str] = []
        skipped: list[str] = []
        barcodes: list[str] = []

        with transaction.atomic():
            for color in colors:
                for size in sizes:
                    code = f"{style.code}-{color.code}-{size.code}".upper()
                    existing = Sku.objects.filter(company=style.company, code=code).first()
                    if existing is not None:
                        skipped.append(code)
                        continue
                    material = None
                    if material_defaults is not None:
                        material = Material.objects.create(
                            company=style.company,
                            code=code,
                            name=f"{style.name} {color.name} {size.name}",
                            category=material_defaults["category"],
                            base_uom=material_defaults["base_uom"],
                            spec=style.size_group,
                            brand=style.brand,
                            season=style.season,
                            year=style.year,
                            series=style.series,
                        )
                    sku = Sku.objects.create(
                        company=style.company,
                        style=style,
                        color=color,
                        size=size,
                        code=code,
                        material=material,
                    )
                    created.append(code)
                    identifier = _register_sku_barcode(sku)
                    if identifier is not None:
                        barcodes.append(identifier.value)

            record_audit(
                action=AuditAction.CREATE,
                instance=style,
                changes={
                    "generated_skus": {"before": [], "after": created},
                    "skipped_skus": {"before": [], "after": skipped},
                },
                reason="按颜色与尺码批量生成 SKU",
                object_repr=str(style),
            )

        return Response(
            {
                "created": created,
                "skipped": skipped,
                "barcodes": barcodes,
                "created_count": len(created),
                "skipped_count": len(skipped),
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    def _assert_in_scope(self, style: Style) -> None:
        from apps.core.selectors import assert_in_scope

        assert_in_scope(style, self.request.user, company_field="company_id")




class IdentifierViewSet(ActiveFilterMixin, ScopedModelViewSet):
    queryset = Identifier.objects.select_related("sku", "material").all()
    serializer_class = IdentifierSerializer
    scope_fields = None  # 标识可指向任意公司物料，读取权限由编码权限控制
    audit_fields = ("identifier_type", "value", "sku_id", "material_id", "batch_no", "is_active")
    search_fields = ["value", "batch_no", "sku__code", "material__code"]
    filterset_fields = ["identifier_type", "sku_id", "material_id", "batch_no"]
    ordering_fields = ["id", "value"]
    uniqueness_error_map = {"uq_identifier_type_value": "同类型下该标识值已存在。"}
    required_permissions = {
        "list": "masterdata.identifier.view",
        "retrieve": "masterdata.identifier.view",
        "create": "masterdata.identifier.create",
        "partial_update": "masterdata.identifier.update",
        "set_active": "masterdata.identifier.deactivate",
        "resolve": "masterdata.identifier.view",
    }

    @action(detail=False, methods=["get"], url_path="resolve")
    def resolve(self, request, *args, **kwargs):
        """按类型 + 标识值解析对象，供扫码与看板使用。

        解析结果不携带任何业务授权：后续操作仍按各自权限校验。
        """
        identifier_type = request.query_params.get("identifier_type", "").strip()
        value = request.query_params.get("value", "").strip()
        if not identifier_type or not value:
            raise ValidationFailed(
                "必须提供 identifier_type 与 value。", code="IDENTIFIER_QUERY_REQUIRED"
            )
        identifier = (
            Identifier.objects.select_related("sku", "material")
            .filter(identifier_type=identifier_type, value=value, is_active=True)
            .first()
        )
        if identifier is None:
            raise ObjectNotFound("未找到对应标识。", code="IDENTIFIER_NOT_FOUND")
        return Response(IdentifierSerializer(identifier).data)


def _register_sku_barcode(sku: Sku):
    """为 SKU 生成条码标识。条码与 SKU 编码一致，避免额外映射。"""
    if not sku.barcode:
        sku.barcode = sku.code
        sku.save(update_fields=["barcode", "updated_at"])
    identifier, _ = Identifier.objects.get_or_create(
        identifier_type="sku_barcode",
        value=sku.barcode,
        defaults={"sku": sku, "material": sku.material},
    )
    return identifier


def _resolve_finished_goods_defaults(data: dict, style: Style) -> dict:
    from apps.masterdata.models import MaterialCategory

    category = None
    if data.get("category_id"):
        category = MaterialCategory.objects.filter(pk=data["category_id"]).first()
    if category is None:
        category = MaterialCategory.objects.filter(category_type="finished", is_active=True).first()
    if category is None:
        raise ValidationFailed(
            "未找到成品分类，无法为 SKU 创建库存物料。", code="FINISHED_CATEGORY_NOT_FOUND"
        )

    base_uom = None
    if data.get("base_uom_id"):
        base_uom = UoM.objects.filter(pk=data["base_uom_id"]).first()
    if base_uom is None:
        base_uom = UoM.objects.filter(code="PCS", is_active=True).first()
    if base_uom is None:
        raise ValidationFailed(
            "未找到基本单位 PCS，无法为 SKU 创建库存物料。", code="BASE_UOM_NOT_FOUND"
        )
    return {"category": category, "base_uom": base_uom}
