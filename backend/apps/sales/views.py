"""销售模块接口：销售订单 / 库存占用 / 发货出库 / 销售退货。

职责边界（任务书 4.3）：

* 视图只做请求解析、权限声明、数据范围校验与调用服务；
* 金额、状态迁移、库存占用与出库全部在 `apps.sales.services` 与统一库存服务内完成；
* 视图**不直接写**库存余额、流水、单据或占用表，也不接受前端传入的金额。

数据范围：订单以 `company_id` 收敛，发货与退货继承订单公司；关联对象
（客户、物料、储位、订单行）逐一做范围校验，避免用他人 ID 越权（任务书 6.4）。
"""

from __future__ import annotations

from typing import Any

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.exceptions import ObjectNotFound, ValidationFailed
from apps.core.selectors import assert_in_scope, scoped_queryset
from apps.core.services import assert_version, idempotent_execute
from apps.core.viewsets import ScopedModelViewSet
from apps.crm.models import Customer
from apps.factory.models import Company
from apps.masterdata.models import Material, UoM
from apps.sales import services
from apps.sales.models import (
    SalesOrder,
    SalesOrderLine,
    SalesReturn,
    SalesShipment,
)
from apps.sales.serializers import (
    InspectReturnSerializer,
    ReasonActionSerializer,
    ReturnUpdateSerializer,
    ReturnWriteSerializer,
    SalesOrderSerializer,
    SalesOrderUpdateSerializer,
    SalesOrderWriteSerializer,
    SalesReturnSerializer,
    SalesShipmentSerializer,
    ShipmentUpdateSerializer,
    ShipmentWriteSerializer,
)
from apps.wms.models import InventoryDocument, Location, Warehouse


def _resolve_company(user: Any, company_id: Any) -> Company:
    """解析并校验目标公司。未传时取当前用户归属公司。"""
    target_id = company_id or getattr(user, "company_id", None)
    if not target_id:
        raise ValidationFailed("缺少公司标识。", code="COMPANY_REQUIRED")
    company = Company.objects.filter(pk=target_id).first()
    if company is None:
        raise ObjectNotFound("公司不存在。", details={"company_id": target_id})
    if not getattr(user, "is_superuser", False):
        assert_in_scope(company, user, company_field="id")
    return company


def _resolve_customer(customer_id: Any, user: Any, company: Company) -> Customer:
    customer = Customer.objects.filter(pk=customer_id).first()
    if customer is None:
        raise ObjectNotFound("客户不存在。", details={"customer_id": customer_id})
    if customer.company_id != company.pk:
        raise ValidationFailed("客户与订单所属公司不一致。", code="COMPANY_CUSTOMER_MISMATCH")
    assert_in_scope(customer, user, company_field="company_id")
    return customer


def _resolve_material(material_id: Any, user: Any) -> Material:
    material = Material.objects.filter(pk=material_id).first()
    if material is None:
        raise ObjectNotFound("物料不存在。", details={"material_id": material_id})
    assert_in_scope(material, user, company_field="company_id")
    return material


def _resolve_uom(uom_id: Any, user: Any) -> UoM | None:
    if not uom_id:
        return None
    uom = UoM.objects.filter(pk=uom_id).first()
    if uom is None:
        raise ObjectNotFound("计量单位不存在。", details={"uom_id": uom_id})
    return uom


def _resolve_location(location_id: Any, user: Any, warehouse: Warehouse) -> Location | None:
    if not location_id:
        return None
    location = Location.objects.filter(pk=location_id).select_related("zone").first()
    if location is None:
        raise ObjectNotFound("储位不存在。", details={"location_id": location_id})
    if location.zone.warehouse_id != warehouse.pk:
        raise ValidationFailed(
            "储位与发货仓库不一致。",
            code="LOCATION_WAREHOUSE_MISMATCH",
            details={"location_id": location_id, "warehouse_id": warehouse.pk},
        )
    return location


def _resolve_warehouse(warehouse_id: Any, user: Any) -> Warehouse | None:
    if not warehouse_id:
        return None
    warehouse = Warehouse.objects.filter(pk=warehouse_id).first()
    if warehouse is None:
        raise ObjectNotFound("仓库不存在。", details={"warehouse_id": warehouse_id})
    assert_in_scope(
        warehouse,
        user,
        company_field="company_id",
        factory_field="factory_id",
        warehouse_field="id",
    )
    return warehouse


def _assert_materials_in_scope(rows: list[dict], user: Any) -> None:
    """逐行校验物料范围。ID 可写不等于可以越权（任务书 6.4）。"""
    for row in rows:
        _resolve_material(row["material_id"], user)


def _order_line_rows(rows: list[dict]) -> list[dict]:
    """把订单输入行映射成服务层键名。"""
    return [
        {
            "material_id": row["material_id"],
            "quantity": row["quantity"],
            "price": row.get("price", 0),
            "sku_id": row.get("sku_id"),
            "uom_id": row.get("uom_id"),
            "expected_date": row.get("expected_date"),
            "remark": row.get("remark", ""),
        }
        for row in rows
    ]

class SalesOrderViewSet(ScopedModelViewSet):
    """销售订单：草稿 → 提交审批 → 批准 → 库存占用 → 发货 → 关闭/取消。"""

    queryset = (
        SalesOrder.objects.select_related("company", "customer", "salesman", "warehouse")
        .prefetch_related(
            "lines__material",
            "lines__sku__color",
            "lines__sku__size",
            "lines__uom",
        )
        .all()
    )
    serializer_class = SalesOrderSerializer
    scope_fields = {"company_field": "company_id", "warehouse_field": "warehouse_id"}
    audit_fields = (
        "order_no",
        "status",
        "customer_id",
        "order_date",
        "expected_date",
        "priority",
        "amount_with_tax",
    )
    search_fields = ["order_no", "customer__name", "remark"]
    filterset_fields = [
        "company_id",
        "customer_id",
        "status",
        "priority",
        "salesman_id",
        "warehouse_id",
    ]
    ordering_fields = [
        "id",
        "order_no",
        "order_date",
        "expected_date",
        "amount_with_tax",
        "created_at",
        "updated_at",
    ]
    uniqueness_error_map = {"uq_sales_order_company_no": "同一公司下销售订单号已存在。"}
    required_permissions = {
        "list": "sales.order.view",
        "retrieve": "sales.order.view",
        "create": "sales.order.create",
        "partial_update": "sales.order.update",
        "submit": "sales.order.submit",
        "cancel": "sales.order.update",
        "close": "sales.order.close",
        # 库存占用经由统一库存服务：跨模块动作必须同时具备库存侧权限（任务书 6.4）
        "reserve": ["sales.order.reserve", "wms.inventory.reserve"],
        "release": ["sales.order.release", "wms.inventory.release"],
        "chain": "sales.order.view",
    }

    def create(self, request, *args, **kwargs) -> Response:
        payload = SalesOrderWriteSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        company = _resolve_company(request.user, request.data.get("company_id"))
        customer = _resolve_customer(data["customer_id"], request.user, company)
        _assert_materials_in_scope(data["lines"], request.user)
        order = services.create_order(
            user=request.user,
            company=company,
            customer=customer,
            lines=_order_line_rows(data["lines"]),
            order_date=data.get("order_date"),
            expected_date=data.get("expected_date"),
            priority=data.get("priority", "normal"),
            warehouse=_resolve_warehouse(data.get("warehouse_id"), request.user),
            salesman=data.get("salesman_id"),
            tax_rate=data.get("tax_rate", 0),
            payment_terms=data.get("payment_terms", ""),
            delivery_address=data.get("delivery_address", ""),
            currency=data.get("currency", "CNY"),
            remark=data.get("remark", ""),
            order_no=data.get("order_no", ""),
        )
        assert_in_scope(order, request.user, **self.scope_fields)
        return Response(self.get_serializer(order).data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs) -> Response:
        order = self.get_object()
        assert_version(order, request.data.get("expected_version"))
        payload = SalesOrderUpdateSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        header: dict[str, Any] = {}
        for field in (
            "order_date",
            "expected_date",
            "priority",
            "currency",
            "payment_terms",
            "delivery_address",
            "remark",
            "salesman_id",
        ):
            if field in data:
                header[field] = data[field]
        if "tax_rate" in data:
            header["tax_rate"] = data["tax_rate"]
        if "warehouse_id" in data:
            warehouse = _resolve_warehouse(data["warehouse_id"], request.user)
            header["warehouse_id"] = getattr(warehouse, "pk", None)
        lines = data.get("lines")
        if lines is not None:
            _assert_materials_in_scope(lines, request.user)
            lines = _order_line_rows(lines)
        order = services.update_order(order, user=request.user, lines=lines, **header)
        return Response(self.get_serializer(order).data)

    @action(detail=True, methods=["post"])
    def submit(self, request, *args, **kwargs) -> Response:
        order = self.get_object()
        payload = ReasonActionSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        order = services.submit_order(
            order, user=request.user, comment=payload.validated_data.get("comment", "")
        )
        return Response(self.get_serializer(order).data)

    @action(detail=True, methods=["post"])
    def cancel(self, request, *args, **kwargs) -> Response:
        order = self.get_object()
        payload = ReasonActionSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        order = services.cancel_order(
            order, user=request.user, reason=payload.validated_data["reason"]
        )
        return Response(self.get_serializer(order).data)

    @action(detail=True, methods=["post"])
    def close(self, request, *args, **kwargs) -> Response:
        order = self.get_object()
        payload = ReasonActionSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        order = services.close_order(
            order, user=request.user, reason=payload.validated_data.get("reason", "")
        )
        return Response(self.get_serializer(order).data)

    @action(detail=True, methods=["post"])
    def reserve(self, request, *args, **kwargs) -> Response:
        """库存占用：按未发货数量占用合格库存（幂等，重复点击不重复占用）。"""
        order = self.get_object()
        payload = ReasonActionSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        reservations = services.reserve_order_stock(
            order, user=request.user, reason=payload.validated_data.get("reason", "")
        )
        return Response(
            {
                "order_id": order.pk,
                "order_no": order.order_no,
                "reserved": [
                    {
                        "reservation_id": item.pk,
                        "material_id": item.material_id,
                        "warehouse_id": item.warehouse_id,
                        "quantity": str(item.quantity),
                        "status": item.status,
                    }
                    for item in reservations
                ],
            }
        )

    @action(detail=True, methods=["post"])
    def release(self, request, *args, **kwargs) -> Response:
        """释放尚未消耗的占用。"""
        order = self.get_object()
        payload = ReasonActionSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        if not payload.validated_data.get("reason"):
            raise ValidationFailed("释放占用必须填写原因。", code="REASON_REQUIRED")
        released = services.release_order_stock(
            order, user=request.user, reason=payload.validated_data["reason"]
        )
        return Response(
            {
                "order_id": order.pk,
                "released": [item.pk for item in released],
                "released_count": len(released),
            }
        )

    @action(detail=True, methods=["get"])
    def chain(self, request, *args, **kwargs) -> Response:
        """订单到交付链路：关联单据与数量（任务书 12.1）。"""
        order = self.get_object()
        order_lines = list(
            order.lines.select_related("material").order_by("line_no")
        )
        documents = InventoryDocument.objects.filter(
            biz_type=services.BIZ_TYPE_ORDER, biz_id=str(order.pk)
        ).order_by("id")
        return Response(
            {
                "order": {
                    "id": order.pk,
                    "order_no": order.order_no,
                    "status": order.status,
                    "status_display": order.get_status_display(),
                    "amount_with_tax": str(order.amount_with_tax),
                },
                "lines": [
                    {
                        "line_id": line.pk,
                        "line_no": line.line_no,
                        "material_id": line.material_id,
                        "material_code": line.material.code,
                        "material_name": line.material.name,
                        "quantity": str(line.quantity),
                        "shipped_quantity": str(line.shipped_quantity),
                        "returned_quantity": str(line.returned_quantity),
                        "remaining_quantity": str(line.remaining_quantity),
                    }
                    for line in order_lines
                ],
                "shipments": [
                    {
                        "id": item.pk,
                        "shipment_no": item.shipment_no,
                        "status": item.status,
                        "shipped_at": item.shipped_at,
                        "issue_document_id": item.issue_document_id,
                    }
                    for item in order.shipments.all().order_by("id")
                ],
                "returns": [
                    {
                        "id": item.pk,
                        "return_no": item.return_no,
                        "status": item.status,
                        "inspection_result": item.inspection_result,
                    }
                    for item in order.returns.all().order_by("id")
                ],
                "inventory_documents": [
                    {
                        "id": item.pk,
                        "document_no": item.document_no,
                        "document_type": item.document_type,
                        "status": item.status,
                    }
                    for item in documents
                ],
            }
        )

class SalesShipmentViewSet(ScopedModelViewSet):
    """发货单：草稿 → 出库过账（消耗本订单占用并扣减库存）。"""

    queryset = (
        SalesShipment.objects.select_related(
            "company", "sales_order", "customer", "warehouse", "shipped_by"
        )
        .prefetch_related("lines__material", "lines__order_line", "lines__location")
        .all()
    )
    serializer_class = SalesShipmentSerializer
    scope_fields = {"company_field": "company_id", "warehouse_field": "warehouse_id"}
    audit_fields = ("shipment_no", "status", "warehouse_id", "tracking_no")
    search_fields = ["shipment_no", "sales_order__order_no", "tracking_no", "remark"]
    filterset_fields = ["company_id", "sales_order_id", "customer_id", "status", "warehouse_id"]
    ordering_fields = ["id", "shipment_no", "created_at", "shipped_at"]
    uniqueness_error_map = {"uq_shipment_company_no": "同一公司下发货单号已存在。"}
    required_permissions = {
        "list": "sales.shipment.view",
        "retrieve": "sales.shipment.view",
        "create": "sales.shipment.create",
        "partial_update": "sales.shipment.update",
        # 出库过账最终由统一库存服务记账：跨模块动作必须同时具备库存侧权限
        "post_shipment": ["sales.shipment.post", "wms.document.create", "wms.document.post"],
        "cancel": "sales.shipment.update",
    }

    def _resolve_order(self, order_id: Any) -> SalesOrder:
        order = scoped_queryset(
            SalesOrder.objects.filter(pk=order_id),
            self.request.user,
            company_field="company_id",
            warehouse_field="warehouse_id",
        ).first()
        if order is None:
            raise ObjectNotFound(
                "销售订单不存在或不在数据范围内。", details={"sales_order_id": order_id}
            )
        return order

    def _build_shipment_lines(
        self, order: SalesOrder, rows: list[dict], warehouse: Warehouse
    ) -> list[dict]:
        line_ids = [row["order_line_id"] for row in rows]
        order_lines = {
            line.pk: line
            for line in SalesOrderLine.objects.filter(pk__in=line_ids, order_id=order.pk)
        }
        missing = [line_id for line_id in line_ids if line_id not in order_lines]
        if missing:
            raise ValidationFailed(
                "发货明细的订单行不属于该销售订单。",
                code="ORDER_LINE_MISMATCH",
                details={"order_line_ids": missing},
            )
        prepared: list[dict] = []
        for row in rows:
            order_line = order_lines[row["order_line_id"]]
            prepared.append(
                {
                    "order_line": order_line,
                    "quantity": row["quantity"],
                    "location": _resolve_location(row.get("location_id"), self.request.user, warehouse),
                    "batch_no": row.get("batch_no", ""),
                    "roll_no": row.get("roll_no", ""),
                    "remark": row.get("remark", ""),
                }
            )
        return prepared

    def create(self, request, *args, **kwargs) -> Response:
        payload = ShipmentWriteSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        order = self._resolve_order(data["sales_order_id"])
        warehouse = _resolve_warehouse(data.get("warehouse_id"), request.user)
        if warehouse is None and order.warehouse_id:
            warehouse = _resolve_warehouse(order.warehouse_id, request.user)
        if warehouse is None:
            raise ValidationFailed(
                "发货必须指定发货仓库（订单未指定仓库时需在发货单上指定）。",
                code="WAREHOUSE_REQUIRED",
            )
        lines = self._build_shipment_lines(order, data["lines"], warehouse)
        shipment = services.create_shipment(
            user=request.user,
            order=order,
            warehouse=warehouse,
            lines=lines,
            receiver_name=data.get("receiver_name", ""),
            receiver_phone=data.get("receiver_phone", ""),
            delivery_address=data.get("delivery_address", ""),
            carrier=data.get("carrier", ""),
            tracking_no=data.get("tracking_no", ""),
            shipment_no=data.get("shipment_no", ""),
            remark=data.get("remark", ""),
        )
        assert_in_scope(shipment, request.user, **self.scope_fields)
        return Response(self.get_serializer(shipment).data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs) -> Response:
        shipment = self.get_object()
        assert_version(shipment, request.data.get("expected_version"))
        payload = ShipmentUpdateSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        header: dict[str, Any] = {}
        for field in (
            "receiver_name",
            "receiver_phone",
            "delivery_address",
            "carrier",
            "tracking_no",
            "remark",
        ):
            if field in data:
                header[field] = data[field]
        lines = None
        if data.get("lines") is not None:
            order = self._resolve_order(shipment.sales_order_id)
            lines = self._build_shipment_lines(order, data["lines"], shipment.warehouse)
        shipment = services.update_shipment(shipment, user=request.user, lines=lines, **header)
        return Response(self.get_serializer(shipment).data)

    @action(detail=True, methods=["post"], url_path="post")
    def post_shipment(self, request, *args, **kwargs) -> Response:
        """发货过账：消耗本订单占用并扣减库存。支持 Idempotency-Key（任务书 7.2）。"""
        shipment = self.get_object()
        idempotency_key = request.headers.get("Idempotency-Key") or None

        def _do_post() -> tuple[int, dict[str, Any]]:
            posted = services.post_shipment(
                shipment, user=request.user, idempotency_key=idempotency_key
            )
            return status.HTTP_200_OK, dict(self.get_serializer(posted).data)

        if idempotency_key:
            status_code, body, replayed = idempotent_execute(
                scope=f"sales.shipment.post:{shipment.pk}",
                key=idempotency_key,
                payload={"shipment_id": shipment.pk, "idempotency_key": idempotency_key},
                func=_do_post,
                user=request.user,
            )
            response = Response(body, status=status_code)
            if replayed:
                # 与其他模块一致：重放历史结果时显式告知调用方（任务书 7.2）
                response["Idempotency-Replayed"] = "true"
            return response
        _status, body = _do_post()
        return Response(body, status=_status)

    @action(detail=True, methods=["post"])
    def cancel(self, request, *args, **kwargs) -> Response:
        shipment = self.get_object()
        payload = ReasonActionSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        shipment = services.cancel_shipment(
            shipment, user=request.user, reason=payload.validated_data["reason"]
        )
        return Response(self.get_serializer(shipment).data)

class SalesReturnViewSet(ScopedModelViewSet):
    """销售退货：草稿 → 收货（待检库存）→ 检验判定（合格回库 / 不合格）。"""

    queryset = (
        SalesReturn.objects.select_related(
            "company",
            "sales_order",
            "shipment",
            "customer",
            "warehouse",
            "received_by",
            "inspected_by",
        )
        .prefetch_related("lines__material", "lines__order_line", "lines__location")
        .all()
    )
    serializer_class = SalesReturnSerializer
    scope_fields = {"company_field": "company_id", "warehouse_field": "warehouse_id"}
    audit_fields = ("return_no", "status", "inspection_result", "warehouse_id")
    search_fields = ["return_no", "sales_order__order_no", "reason", "remark"]
    filterset_fields = [
        "company_id",
        "sales_order_id",
        "shipment_id",
        "customer_id",
        "status",
        "warehouse_id",
        "inspection_result",
    ]
    ordering_fields = ["id", "return_no", "created_at", "received_at", "inspected_at"]
    uniqueness_error_map = {"uq_sales_return_company_no": "同一公司下退货单号已存在。"}
    required_permissions = {
        "list": "sales.return.view",
        "retrieve": "sales.return.view",
        "create": "sales.return.create",
        "partial_update": "sales.return.update",
        # 收货过账与质量放行都由统一库存服务完成，必须同时具备库存侧权限
        "post_return": ["sales.return.post", "wms.document.create", "wms.document.post"],
        "inspect": ["sales.return.inspect", "wms.quality.release"],
        "cancel": "sales.return.update",
    }

    def _resolve_order(self, order_id: Any) -> SalesOrder:
        order = scoped_queryset(
            SalesOrder.objects.filter(pk=order_id),
            self.request.user,
            company_field="company_id",
            warehouse_field="warehouse_id",
        ).first()
        if order is None:
            raise ObjectNotFound(
                "销售订单不存在或不在数据范围内。", details={"sales_order_id": order_id}
            )
        return order

    def _resolve_shipment(self, shipment_id: Any, order: SalesOrder) -> SalesShipment | None:
        if not shipment_id:
            return None
        shipment = SalesShipment.objects.filter(pk=shipment_id, sales_order_id=order.pk).first()
        if shipment is None:
            raise ValidationFailed(
                "原发货单不属于该销售订单。",
                code="SHIPMENT_ORDER_MISMATCH",
                details={"shipment_id": shipment_id},
            )
        return shipment

    def _build_return_lines(
        self, order: SalesOrder, rows: list[dict], warehouse: Warehouse
    ) -> list[dict]:
        line_ids = [row["order_line_id"] for row in rows]
        order_lines = {
            line.pk: line
            for line in SalesOrderLine.objects.filter(pk__in=line_ids, order_id=order.pk)
        }
        missing = [line_id for line_id in line_ids if line_id not in order_lines]
        if missing:
            raise ValidationFailed(
                "退货明细的订单行不属于该销售订单。",
                code="ORDER_LINE_MISMATCH",
                details={"order_line_ids": missing},
            )
        prepared: list[dict] = []
        for row in rows:
            prepared.append(
                {
                    "order_line": order_lines[row["order_line_id"]],
                    "quantity": row["quantity"],
                    "location": _resolve_location(row.get("location_id"), self.request.user, warehouse),
                    "batch_no": row.get("batch_no", ""),
                    "roll_no": row.get("roll_no", ""),
                    "remark": row.get("remark", ""),
                }
            )
        return prepared

    def create(self, request, *args, **kwargs) -> Response:
        payload = ReturnWriteSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        order = self._resolve_order(data["sales_order_id"])
        warehouse = _resolve_warehouse(data.get("warehouse_id"), request.user)
        if warehouse is None and order.warehouse_id:
            warehouse = _resolve_warehouse(order.warehouse_id, request.user)
        if warehouse is None:
            raise ValidationFailed(
                "退货必须指定收货仓库（订单未指定仓库时需在退货单上指定）。",
                code="WAREHOUSE_REQUIRED",
            )
        return_doc = services.create_return(
            user=request.user,
            order=order,
            warehouse=warehouse,
            lines=self._build_return_lines(order, data["lines"], warehouse),
            shipment=self._resolve_shipment(data.get("shipment_id"), order),
            reason=data.get("reason", ""),
            return_no=data.get("return_no", ""),
            remark=data.get("remark", ""),
        )
        assert_in_scope(return_doc, request.user, **self.scope_fields)
        return Response(self.get_serializer(return_doc).data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs) -> Response:
        return_doc = self.get_object()
        assert_version(return_doc, request.data.get("expected_version"))
        payload = ReturnUpdateSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        header: dict[str, Any] = {}
        for field in ("reason", "remark"):
            if field in data:
                header[field] = data[field]
        if "warehouse_id" in data:
            warehouse = _resolve_warehouse(data["warehouse_id"], request.user)
            if warehouse is None:
                raise ValidationFailed("退货收货仓库不能为空。", code="WAREHOUSE_REQUIRED")
            header["warehouse_id"] = warehouse.pk
        lines = None
        if data.get("lines") is not None:
            order = self._resolve_order(return_doc.sales_order_id)
            lines = self._build_return_lines(order, data["lines"], return_doc.warehouse)
        return_doc = services.update_return(return_doc, user=request.user, lines=lines, **header)
        return Response(self.get_serializer(return_doc).data)

    @action(detail=True, methods=["post"], url_path="post")
    def post_return(self, request, *args, **kwargs) -> Response:
        """退货收货过账：退回货物进入**待检**库存，不代表可以直接再销售。"""
        return_doc = self.get_object()
        idempotency_key = request.headers.get("Idempotency-Key") or None

        def _do_post() -> tuple[int, dict[str, Any]]:
            posted = services.post_return(
                return_doc, user=request.user, idempotency_key=idempotency_key
            )
            return status.HTTP_200_OK, dict(self.get_serializer(posted).data)

        if idempotency_key:
            status_code, body, replayed = idempotent_execute(
                scope=f"sales.return.post:{return_doc.pk}",
                key=idempotency_key,
                payload={"return_id": return_doc.pk, "idempotency_key": idempotency_key},
                func=_do_post,
                user=request.user,
            )
            response = Response(body, status=status_code)
            if replayed:
                # 与其他模块一致：重放历史结果时显式告知调用方（任务书 7.2）
                response["Idempotency-Replayed"] = "true"
            return response
        _status, body = _do_post()
        return Response(body, status=_status)

    @action(detail=True, methods=["post"])
    def inspect(self, request, *args, **kwargs) -> Response:
        """退货检验判定：合格回库（可再销售）或判为不合格。"""
        return_doc = self.get_object()
        payload = InspectReturnSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        idempotency_key = request.headers.get("Idempotency-Key") or None
        return_doc = services.inspect_return(
            return_doc,
            user=request.user,
            result=payload.validated_data["result"],
            remark=payload.validated_data.get("remark", ""),
            idempotency_key=idempotency_key,
        )
        return Response(self.get_serializer(return_doc).data)

    @action(detail=True, methods=["post"])
    def cancel(self, request, *args, **kwargs) -> Response:
        return_doc = self.get_object()
        payload = ReasonActionSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        return_doc = services.cancel_return(
            return_doc, user=request.user, reason=payload.validated_data["reason"]
        )
        return Response(self.get_serializer(return_doc).data)
