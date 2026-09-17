"""仓储接口：仓库结构主数据 + 库存单据/余额/流水。

阶段 1 只提供仓库/库区/储位主数据；阶段 2 增加库存单据录入、过账、冲销与查询。
库存余额与流水的**写入**全部经由 `apps/wms/services/stock.py`，视图不直接改表。
"""

from __future__ import annotations

from typing import Any

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.exceptions import ObjectNotFound, StateConflict, ValidationFailed
from apps.core.selectors import assert_in_scope, scoped_queryset
from apps.core.services import idempotent_execute
from apps.core.viewsets import ActiveFilterMixin, ReadOnlyScopedViewSet, ScopedModelViewSet
from apps.masterdata.models import Material
from apps.wms import services as stock_services
from apps.wms.models import (
    InventoryBalance,
    InventoryDocument,
    InventoryTransaction,
    Location,
    Warehouse,
    Zone,
)
from apps.wms.serializers import (
    DocumentActionSerializer,
    InventoryBalanceSerializer,
    InventoryDocumentCreateSerializer,
    InventoryDocumentSerializer,
    InventoryDocumentUpdateSerializer,
    InventoryTransactionSerializer,
    LocationSerializer,
    QualityReleaseSerializer,
    WarehouseSerializer,
    ZoneSerializer,
)


class WarehouseViewSet(ActiveFilterMixin, ScopedModelViewSet):
    queryset = Warehouse.objects.select_related("company", "factory", "department").all()
    serializer_class = WarehouseSerializer
    scope_fields = {"company_field": "company_id", "factory_field": "factory_id", "warehouse_field": "id"}
    audit_fields = (
        "code", "name", "warehouse_type", "factory_id", "department_id",
        "allow_negative_stock", "is_active",
    )
    search_fields = ["code", "name", "manager_name"]
    filterset_fields = ["company_id", "factory_id", "warehouse_type", "allow_negative_stock"]
    ordering_fields = ["id", "code", "name"]
    uniqueness_error_map = {"uq_warehouse_company_code": "同一公司下仓库编码已存在。"}
    required_permissions = {
        "list": "wms.warehouse.view",
        "retrieve": "wms.warehouse.view",
        "create": "wms.warehouse.create",
        "partial_update": "wms.warehouse.update",
        "set_active": "wms.warehouse.update",
    }


class ZoneViewSet(ActiveFilterMixin, ScopedModelViewSet):
    queryset = Zone.objects.select_related("warehouse").all()
    serializer_class = ZoneSerializer
    scope_fields = {
        "company_field": "warehouse__company_id",
        "factory_field": "warehouse__factory_id",
        "warehouse_field": "warehouse_id",
    }
    audit_fields = ("warehouse_id", "code", "name", "zone_type", "allow_mixed_batch", "is_active")
    search_fields = ["code", "name"]
    filterset_fields = ["warehouse_id", "zone_type"]
    ordering_fields = ["id", "code", "sort_order"]
    uniqueness_error_map = {"uq_zone_warehouse_code": "同一仓库下库区编码已存在。"}
    required_permissions = {
        "list": "wms.zone.view",
        "retrieve": "wms.zone.view",
        "create": "wms.zone.create",
        "partial_update": "wms.zone.update",
        "set_active": "wms.zone.update",
    }


class LocationViewSet(ActiveFilterMixin, ScopedModelViewSet):
    queryset = Location.objects.select_related("zone", "zone__warehouse").all()
    serializer_class = LocationSerializer
    scope_fields = {
        "company_field": "zone__warehouse__company_id",
        "factory_field": "zone__warehouse__factory_id",
        "warehouse_field": "zone__warehouse_id",
    }
    audit_fields = (
        "zone_id", "code", "name", "location_type", "capacity", "is_locked", "is_active",
    )
    search_fields = ["code", "name", "row_no", "column_no"]
    filterset_fields = ["zone_id", "location_type", "is_locked", "zone__warehouse_id"]
    ordering_fields = ["id", "code"]
    uniqueness_error_map = {"uq_location_zone_code": "同一库区内储位编码已存在。"}
    required_permissions = {
        "list": "wms.location.view",
        "retrieve": "wms.location.view",
        "create": "wms.location.create",
        "partial_update": "wms.location.update",
        "set_active": "wms.location.update",
        "tree": "wms.location.view",
    }

    @action(detail=False, methods=["get"])
    def tree(self, request, *args, **kwargs):
        """仓库 → 库区 → 储位 的树形结构，供储位选择与看板使用。"""
        # 不复用本视图的 filterset（其过滤字段属于 Location），改为按仓库维度直接收敛
        warehouses = list(
            scoped_queryset(
                Warehouse.objects.select_related("company"),
                request.user,
                company_field="company_id",
                factory_field="factory_id",
                warehouse_field="id",
            ).order_by("code")
        )
        # 已按数据范围过滤仓库，库区与储位随仓库一并收敛
        warehouse_ids = [item.id for item in warehouses]
        zones = list(
            Zone.objects.filter(warehouse_id__in=warehouse_ids).order_by(
                "warehouse_id", "sort_order", "id"
            )
        )
        zone_ids = [item.id for item in zones]
        locations = list(
            Location.objects.filter(zone_id__in=zone_ids).order_by("zone_id", "code")
        )
        return Response(_build_warehouse_tree(warehouses, zones, locations))


def _build_warehouse_tree(warehouses, zones, locations) -> list[dict]:
    location_map: dict[int, list[dict]] = {}
    for location in locations:
        location_map.setdefault(location.zone_id, []).append(
            {
                "id": location.id,
                "code": location.code,
                "name": location.name,
                "is_locked": location.is_locked,
                "is_active": location.is_active,
            }
        )
    zone_map: dict[int, list[dict]] = {}
    for zone in zones:
        zone_map.setdefault(zone.warehouse_id, []).append(
            {
                "id": zone.id,
                "code": zone.code,
                "name": zone.name,
                "zone_type": zone.zone_type,
                "locations": location_map.get(zone.id, []),
            }
        )
    return [
        {
            "id": warehouse.id,
            "code": warehouse.code,
            "name": warehouse.name,
            "warehouse_type": warehouse.warehouse_type,
            "zones": zone_map.get(warehouse.id, []),
        }
        for warehouse in warehouses
    ]

# ---------------------------------------------------------------------------
# 库存余额 / 流水 / 单据（阶段 2 统一库存服务）
# ---------------------------------------------------------------------------


class InventoryBalanceViewSet(ReadOnlyScopedViewSet):
    """库存余额查询。余额只能由统一库存服务改写，因此本视图完全只读。"""

    queryset = InventoryBalance.objects.select_related(
        "company", "material", "warehouse", "location"
    ).all()
    serializer_class = InventoryBalanceSerializer
    scope_fields = {
        "company_field": "company_id",
        "factory_field": "warehouse__factory_id",
        "warehouse_field": "warehouse_id",
    }
    search_fields = ["material__code", "material__name", "batch_no", "roll_no"]
    filterset_fields = {
        "company_id": ["exact"],
        "material_id": ["exact"],
        "warehouse_id": ["exact"],
        "location_id": ["exact"],
        "quality_status": ["exact"],
        "batch_no": ["exact", "icontains"],
        "roll_no": ["exact", "icontains"],
        "updated_at": ["gte", "lte"],
    }
    ordering_fields = ["id", "on_hand", "frozen", "reserved", "updated_at"]
    required_permissions = {
        "list": "wms.inventory.view",
        "retrieve": "wms.inventory.view",
    }

    def filter_queryset(self, queryset):
        queryset = super().filter_queryset(queryset)
        raw = self.request.query_params.get("has_stock")
        if raw is None or raw == "":
            return queryset
        if raw.lower() in {"1", "true", "yes"}:
            return queryset.filter(on_hand__gt=0)
        if raw.lower() in {"0", "false", "no"}:
            return queryset.filter(on_hand__lte=0)
        raise StateConflict("has_stock 参数取值不合法。", code="INVALID_FILTER")


class InventoryTransactionViewSet(ReadOnlyScopedViewSet):
    """库存流水查询。流水为只追加记录，不提供任何写接口。"""

    queryset = InventoryTransaction.objects.select_related(
        "company", "material", "warehouse", "location", "document", "operator"
    ).all()
    serializer_class = InventoryTransactionSerializer
    scope_fields = {
        "company_field": "company_id",
        "factory_field": "warehouse__factory_id",
        "warehouse_field": "warehouse_id",
    }
    search_fields = ["material__code", "material__name", "document__document_no", "reason"]
    filterset_fields = {
        "company_id": ["exact"],
        "material_id": ["exact"],
        "warehouse_id": ["exact"],
        "location_id": ["exact"],
        "document_id": ["exact"],
        "transaction_type": ["exact"],
        "quality_status": ["exact"],
        "batch_no": ["exact", "icontains"],
        "roll_no": ["exact", "icontains"],
        "created_at": ["gte", "lte"],
    }
    ordering_fields = ["id", "created_at", "quantity"]
    required_permissions = {
        "list": "wms.inventory.view",
        "retrieve": "wms.inventory.view",
    }
class InventoryDocumentViewSet(ScopedModelViewSet):
    """库存单据：录入 → 过账 → 冲销。

    写操作全部走 `apps/wms/services/stock.py`，视图不直接改余额或流水。
    """

    queryset = InventoryDocument.objects.select_related(
        "company", "warehouse", "posted_by", "reversed_by"
    ).prefetch_related("lines").all()
    serializer_class = InventoryDocumentSerializer
    scope_fields = {
        "company_field": "company_id",
        "factory_field": "warehouse__factory_id",
        "warehouse_field": "warehouse_id",
    }
    search_fields = ["document_no", "biz_no", "remark"]
    filterset_fields = ["company_id", "document_type", "status", "warehouse_id", "biz_type", "biz_id"]
    ordering_fields = ["id", "document_no", "created_at", "posted_at"]
    audit_fields = ("document_type", "status", "warehouse_id", "remark")
    required_permissions = {
        "list": "wms.document.view",
        "retrieve": "wms.document.view",
        "create": "wms.document.create",
        "partial_update": "wms.document.update",
        "post_document": "wms.document.post",
        "reverse": "wms.document.reverse",
        "release_quality": "wms.quality.release",
    }

    def _resolve_warehouse(self, warehouse_id: int) -> Warehouse:
        warehouse = Warehouse.objects.filter(pk=warehouse_id).first()
        if warehouse is None:
            raise ObjectNotFound("仓库不存在。", details={"warehouse_id": warehouse_id})
        assert_in_scope(
            warehouse,
            self.request.user,
            company_field="company_id",
            factory_field="factory_id",
            warehouse_field="id",
        )
        return warehouse

    def create(self, request, *args, **kwargs) -> Response:
        payload = InventoryDocumentCreateSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        warehouse = self._resolve_warehouse(data["warehouse_id"])
        company_id = data.get("company_id") or warehouse.company_id
        if company_id != warehouse.company_id:
            raise ValidationFailed(
                "公司标识与仓库所属公司不一致。",
                code="COMPANY_WAREHOUSE_MISMATCH",
                details={"company_id": company_id, "warehouse_id": warehouse.pk},
            )
        document = stock_services.create_document(
            document_type=data["document_type"],
            company=company_id,
            warehouse=warehouse,
            lines=data["lines"],
            user=request.user,
            biz_type=data["biz_type"],
            biz_id=data["biz_id"],
            biz_no=data["biz_no"],
            remark=data["remark"],
        )
        assert_in_scope(document, request.user, **self.scope_fields)
        return Response(self.get_serializer(document).data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs) -> Response:
        document = self.get_object()
        payload = InventoryDocumentUpdateSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        header: dict[str, Any] = {}
        if "warehouse_id" in data:
            header["warehouse_id"] = self._resolve_warehouse(data["warehouse_id"]).pk
        for field in ("biz_no", "remark"):
            if field in data:
                header[field] = data[field]
        document = stock_services.update_draft_document(
            document, user=request.user, lines=data.get("lines"), **header
        )
        return Response(self.get_serializer(document).data)

    @action(detail=True, methods=["post"], url_path="post")
    def post_document(self, request, *args, **kwargs) -> Response:
        """过账。支持 Idempotency-Key 请求头（任务书 7.2）。"""
        document = self.get_object()
        payload = DocumentActionSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        reason = payload.validated_data.get("reason", "")
        idempotency_key = request.headers.get("Idempotency-Key") or None

        def _do_post() -> tuple[int, dict[str, Any]]:
            posted = stock_services.post_document(
                document, user=request.user, idempotency_key=idempotency_key, reason=reason
            )
            return status.HTTP_200_OK, dict(self.get_serializer(posted).data)

        if idempotency_key:
            status_code, body, replayed = idempotent_execute(
                scope=f"wms.document.post:{document.pk}",
                key=idempotency_key,
                payload={"document_id": document.pk, "idempotency_key": idempotency_key},
                func=_do_post,
                user=request.user,
            )
            response = Response(body, status=status_code)
            if replayed:
                response["Idempotency-Replayed"] = "true"
            return response

        status_code, body = _do_post()
        return Response(body, status=status_code)

    @action(detail=True, methods=["post"], url_path="reverse")
    def reverse(self, request, *args, **kwargs) -> Response:
        document = self.get_object()
        payload = DocumentActionSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        reversed_document = stock_services.reverse_document(
            document, user=request.user, reason=payload.validated_data.get("reason", "")
        )
        return Response(self.get_serializer(reversed_document).data)

    @action(detail=False, methods=["post"], url_path="release-quality")
    def release_quality(self, request, *args, **kwargs) -> Response:
        """质量放行：创建并立即过账一张质量转换单，返回新单据。"""
        payload = QualityReleaseSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        warehouse = self._resolve_warehouse(data["warehouse_id"])
        company_id = data.get("company_id") or warehouse.company_id
        if company_id != warehouse.company_id:
            raise ValidationFailed(
                "公司标识与仓库所属公司不一致。",
                code="COMPANY_WAREHOUSE_MISMATCH",
                details={"company_id": company_id, "warehouse_id": warehouse.pk},
            )
        material = Material.objects.filter(pk=data["material_id"]).first()
        if material is None:
            raise ObjectNotFound("物料不存在。", details={"material_id": data["material_id"]})
        location = None
        if data.get("location_id"):
            location = Location.objects.filter(pk=data["location_id"]).first()
            if location is None:
                raise ObjectNotFound("储位不存在。", details={"location_id": data["location_id"]})
        document = stock_services.release_quality(
            user=request.user,
            company=company_id,
            warehouse=warehouse,
            material=material,
            quantity=data["quantity"],
            location=location,
            batch_no=data["batch_no"],
            roll_no=data["roll_no"],
            from_status=data["from_status"],
            to_status=data["to_status"],
            biz_type=data["biz_type"],
            biz_id=data["biz_id"],
            biz_no=data["biz_no"],
            reason=data["reason"],
            idempotency_key=request.headers.get("Idempotency-Key") or None,
        )
        return Response(self.get_serializer(document).data, status=status.HTTP_201_CREATED)
