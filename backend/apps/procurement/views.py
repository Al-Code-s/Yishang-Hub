"""采购模块接口：采购申请 / 采购订单 / 到货收货 / 来料检验。

职责边界（任务书 4.3）：

* 视图只做请求解析、权限声明、数据范围校验与调用服务；
* 金额、状态迁移、库存记账全部在 `apps.procurement.services` 与统一库存服务内完成；
* 视图**不直接写**库存余额、流水或单据表，也不接受前端传入的金额。

数据范围：申请与订单以 `company_id` 收敛；收货单继承订单公司。关联对象
（物料、储位、订单行）逐一做范围校验，避免用他人 ID 越权（任务书 6.4）。
"""

from __future__ import annotations

from typing import Any

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.exceptions import ObjectNotFound, ValidationFailed
from apps.core.selectors import assert_in_scope, scoped_queryset
from apps.core.services import idempotent_execute
from apps.core.viewsets import ScopedModelViewSet
from apps.factory.models import Company
from apps.masterdata.models import Material, UoM
from apps.procurement import services
from apps.procurement.models import (
    GoodsReceipt,
    PurchaseOrder,
    PurchaseOrderLine,
    PurchaseRequisition,
)
from apps.procurement.serializers import (
    ConvertRequisitionSerializer,
    InspectReceiptSerializer,
    OrderSerializer,
    OrderUpdateSerializer,
    OrderWriteSerializer,
    ReasonActionSerializer,
    ReceiptSerializer,
    ReceiptUpdateSerializer,
    ReceiptWriteSerializer,
    RequisitionSerializer,
    RequisitionUpdateSerializer,
    RequisitionWriteSerializer,
)
from apps.srm.models import Supplier
from apps.wms.models import Location, Warehouse


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


def _order_line_rows(rows: list[dict]) -> list[dict]:
    """把订单输入行映射成服务层键名（服务层用 `material` / `uom` 等对象键）。"""
    prepared: list[dict] = []
    for row in rows:
        prepared.append(
            {
                "material": row["material_id"],
                "quantity": row["quantity"],
                "price": row.get("price", 0),
                "uom": row.get("uom_id"),
                "expected_date": row.get("expected_date"),
                "warehouse": row.get("warehouse_id"),
                "source_line": row.get("source_line_id"),
                "remark": row.get("remark", ""),
            }
        )
    return prepared


def _requisition_line_rows(rows: list[dict]) -> list[dict]:
    """把申请输入行映射成服务层键名。"""
    return [
        {
            "material_id": row["material_id"],
            "quantity": row["quantity"],
            "uom": row.get("uom_id"),
            "needed_date": row.get("needed_date"),
            "suggested_supplier": row.get("suggested_supplier_id"),
            "remark": row.get("remark", ""),
        }
        for row in rows
    ]


def _assert_materials_in_scope(rows: list[dict], user: Any) -> None:
    """逐行校验物料范围。ID 写入权限不能绕过数据范围（任务书 6.4）。"""
    for row in rows:
        _resolve_material(row["material_id"], user)


def _assert_supplier_in_scope(supplier: Supplier, user: Any) -> Supplier:
    assert_in_scope(supplier, user, company_field="company_id")
    return supplier


def _resolve_department(department_id: Any, user: Any, company: Company) -> Any:
    if not department_id:
        return None
    from apps.factory.models import Department

    department = Department.objects.filter(pk=department_id).first()
    if department is None:
        raise ObjectNotFound("部门不存在。", details={"department_id": department_id})
    if department.company_id != company.pk:
        raise ValidationFailed("申请部门与公司不一致。", code="COMPANY_DEPARTMENT_MISMATCH")
    assert_in_scope(department, user, company_field="company_id", department_field="id")
    return department


def _resolve_factory(factory_id: Any, user: Any, company: Company) -> Any:
    if not factory_id:
        return None
    from apps.factory.models import Factory

    factory = Factory.objects.filter(pk=factory_id).first()
    if factory is None:
        raise ObjectNotFound("工厂不存在。", details={"factory_id": factory_id})
    if factory.company_id != company.pk:
        raise ValidationFailed("需求工厂与公司不一致。", code="COMPANY_FACTORY_MISMATCH")
    assert_in_scope(factory, user, company_field="company_id", factory_field="id")
    return factory


class RequisitionViewSet(ScopedModelViewSet):
    """采购申请：草稿 → 提交审批 → 批准/驳回 → （批准后）转采购订单。"""

    queryset = (
        PurchaseRequisition.objects.select_related("company", "applicant", "department", "factory")
        .prefetch_related("lines__material", "lines__uom", "lines__suggested_supplier")
        .all()
    )
    serializer_class = RequisitionSerializer
    scope_fields = {"company_field": "company_id"}
    audit_fields = (
        "requisition_no",
        "request_type",
        "status",
        "needed_date",
        "purpose",
        "remark",
    )
    search_fields = ["requisition_no", "purpose", "remark"]
    filterset_fields = [
        "company_id",
        "request_type",
        "status",
        "applicant_id",
        "department_id",
        "factory_id",
    ]
    ordering_fields = ["id", "requisition_no", "needed_date", "created_at", "updated_at"]
    uniqueness_error_map = {"uq_requisition_company_no": "同一公司下申请单号已存在。"}
    required_permissions = {
        "list": "procurement.requisition.view",
        "retrieve": "procurement.requisition.view",
        "create": "procurement.requisition.create",
        "partial_update": "procurement.requisition.update",
        "submit": "procurement.requisition.submit",
        "cancel": "procurement.requisition.update",
        "convert": "procurement.order.create",
    }

    def create(self, request, *args, **kwargs) -> Response:
        payload = RequisitionWriteSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        company = _resolve_company(request.user, request.data.get("company_id"))
        _assert_materials_in_scope(data["lines"], request.user)
        requisition = services.create_requisition(
            user=request.user,
            company=company,
            lines=_requisition_line_rows(data["lines"]),
            request_type=data["request_type"],
            needed_date=data.get("needed_date"),
            department=_resolve_department(data.get("department_id"), request.user, company),
            factory=_resolve_factory(data.get("factory_id"), request.user, company),
            purpose=data.get("purpose", ""),
            remark=data.get("remark", ""),
            requisition_no=data.get("requisition_no", ""),
        )
        assert_in_scope(requisition, request.user, **self.scope_fields)
        return Response(self.get_serializer(requisition).data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs) -> Response:
        from apps.core.services import assert_version

        requisition = self.get_object()
        assert_version(requisition, request.data.get("expected_version"))
        payload = RequisitionUpdateSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        header: dict[str, Any] = {}
        for field in ("request_type", "needed_date", "purpose", "remark"):
            if field in data:
                header[field] = data[field]
        if "department_id" in data:
            company = _resolve_company(request.user, requisition.company_id)
            department = _resolve_department(data["department_id"], request.user, company)
            header["department_id"] = getattr(department, "pk", None)
        if "factory_id" in data:
            company = _resolve_company(request.user, requisition.company_id)
            factory = _resolve_factory(data["factory_id"], request.user, company)
            header["factory_id"] = getattr(factory, "pk", None)
        lines = data.get("lines")
        if lines is not None:
            _assert_materials_in_scope(lines, request.user)
            lines = _requisition_line_rows(lines)
        requisition = services.update_requisition(requisition, user=request.user, lines=lines, **header)
        return Response(self.get_serializer(requisition).data)

    @action(detail=True, methods=["post"])
    def submit(self, request, *args, **kwargs) -> Response:
        requisition = self.get_object()
        payload = ReasonActionSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        requisition = services.submit_requisition(
            requisition, user=request.user, comment=payload.validated_data.get("comment", "")
        )
        return Response(self.get_serializer(requisition).data)

    @action(detail=True, methods=["post"])
    def cancel(self, request, *args, **kwargs) -> Response:
        requisition = self.get_object()
        payload = ReasonActionSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        requisition = services.cancel_requisition(
            requisition, user=request.user, reason=payload.validated_data["reason"]
        )
        return Response(self.get_serializer(requisition).data)

    @action(detail=True, methods=["post"])
    def convert(self, request, *args, **kwargs) -> Response:
        """按已批准的采购申请转采购订单（超转/重复转单由服务层拦截）。"""
        requisition = self.get_object()
        payload = ConvertRequisitionSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = dict(payload.validated_data)
        supplier_id = data.pop("supplier_id")
        raw_lines = data.pop("lines", None)
        supplier = Supplier.objects.filter(pk=supplier_id).first()
        if supplier is None:
            raise ObjectNotFound("供应商不存在。", details={"supplier_id": supplier_id})
        if supplier.company_id != requisition.company_id:
            raise ValidationFailed("供应商与申请所属公司不一致。", code="COMPANY_SUPPLIER_MISMATCH")
        _assert_supplier_in_scope(supplier, request.user)
        header: dict[str, Any] = {}
        for field in (
            "order_no",
            "order_date",
            "expected_date",
            "currency",
            "payment_terms",
            "supplier_exception_reason",
            "remark",
        ):
            if field in data and data[field] is not None:
                header[field] = data[field]
        if data.get("tax_rate") is not None:
            header["tax_rate"] = data["tax_rate"]
        if data.get("warehouse_id"):
            header["warehouse"] = _resolve_warehouse(data["warehouse_id"], request.user)
        if data.get("buyer_id"):
            header["buyer"] = data["buyer_id"]
        lines = None
        if raw_lines is not None:
            lines = [_normalise_convert_line(row) for row in raw_lines]
        order = services.create_order_from_requisition(
            requisition, user=request.user, supplier=supplier, lines=lines, **header
        )
        assert_in_scope(order, request.user, **self.scope_fields)
        return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)


def _normalise_convert_line(row: dict) -> dict:
    """把前端行转成服务层可识别的键（`requisition_line` / `price`）。"""
    if "requisition_line" not in row and row.get("requisition_line_id"):
        row = {**row, "requisition_line": row["requisition_line_id"]}
    if "quantity" not in row:
        raise ValidationFailed("转单明细必须包含数量。", code="INVALID_LINE_QUANTITY")
    return row


class PurchaseOrderViewSet(ScopedModelViewSet):
    """采购订单：草稿 → 提交审批 → 批准 → 收货 → 关闭/取消。"""

    queryset = (
        PurchaseOrder.objects.select_related(
            "company", "supplier", "buyer", "warehouse", "source_requisition"
        )
        .prefetch_related("lines__material", "lines__uom")
        .all()
    )
    serializer_class = OrderSerializer
    scope_fields = {
        "company_field": "company_id",
        "warehouse_field": "warehouse_id",
    }
    audit_fields = (
        "order_no",
        "status",
        "supplier_id",
        "order_date",
        "expected_date",
        "total_amount",
        "amount_with_tax",
        "supplier_exception",
    )
    search_fields = ["order_no", "remark", "supplier__name"]
    filterset_fields = [
        "company_id",
        "supplier_id",
        "status",
        "buyer_id",
        "warehouse_id",
        "source_requisition_id",
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
    uniqueness_error_map = {"uq_order_company_no": "同一公司下采购订单号已存在。"}
    required_permissions = {
        "list": "procurement.order.view",
        "retrieve": "procurement.order.view",
        "create": "procurement.order.create",
        "partial_update": "procurement.order.update",
        "submit": "procurement.order.submit",
        "cancel": "procurement.order.update",
        "close": "procurement.order.close",
    }

    def create(self, request, *args, **kwargs) -> Response:
        payload = OrderWriteSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        company = _resolve_company(request.user, request.data.get("company_id"))
        supplier = Supplier.objects.filter(pk=data["supplier_id"]).first()
        if supplier is None:
            raise ObjectNotFound("供应商不存在。", details={"supplier_id": data["supplier_id"]})
        if supplier.company_id != company.pk:
            raise ValidationFailed("供应商与公司不一致。", code="COMPANY_SUPPLIER_MISMATCH")
        _assert_supplier_in_scope(supplier, request.user)
        _assert_materials_in_scope(data["lines"], request.user)
        lines = _order_line_rows(data["lines"])
        source_requisition = None
        if data.get("source_requisition_id"):
            source_requisition = self._resolve_requisition(data["source_requisition_id"])
        order = services.create_order(
            user=request.user,
            company=company,
            supplier=supplier,
            lines=lines,
            order_date=data.get("order_date"),
            expected_date=data.get("expected_date"),
            warehouse=_resolve_warehouse(data.get("warehouse_id"), request.user),
            source_requisition=source_requisition,
            buyer=data.get("buyer_id"),
            tax_rate=data.get("tax_rate", 0),
            payment_terms=data.get("payment_terms", ""),
            currency=data.get("currency", "CNY"),
            supplier_exception_reason=data.get("supplier_exception_reason", ""),
            remark=data.get("remark", ""),
            order_no=data.get("order_no", ""),
        )
        assert_in_scope(order, request.user, **self.scope_fields)
        return Response(self.get_serializer(order).data, status=status.HTTP_201_CREATED)

    def _resolve_requisition(self, requisition_id: Any) -> PurchaseRequisition:
        requisition = scoped_queryset(
            PurchaseRequisition.objects.filter(pk=requisition_id),
            self.request.user,
            **self.scope_fields,
        ).first()
        if requisition is None:
            raise ObjectNotFound(
                "采购申请不存在或不在数据范围内。", details={"requisition_id": requisition_id}
            )
        return requisition

    def partial_update(self, request, *args, **kwargs) -> Response:
        from apps.core.services import assert_version

        order = self.get_object()
        assert_version(order, request.data.get("expected_version"))
        payload = OrderUpdateSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        header: dict[str, Any] = {}
        for field in (
            "order_date",
            "expected_date",
            "buyer_id",
            "currency",
            "payment_terms",
            "supplier_exception_reason",
            "remark",
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
        order = services.cancel_order(order, user=request.user, reason=payload.validated_data["reason"])
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


class GoodsReceiptViewSet(ScopedModelViewSet):
    """到货收货：草稿 → 过账（记入待检库存）→ 检验放行。

    过账与检验是**两个不同动作**，且都调用统一库存服务，视图不直接改库存。
    """

    queryset = (
        GoodsReceipt.objects.select_related(
            "company",
            "purchase_order",
            "supplier",
            "warehouse",
            "received_by",
            "inspected_by",
        )
        .prefetch_related("lines__material", "lines__order_line", "lines__location")
        .all()
    )
    serializer_class = ReceiptSerializer
    scope_fields = {"company_field": "company_id", "warehouse_field": "warehouse_id"}
    audit_fields = ("receipt_no", "status", "inspection_result", "warehouse_id")
    search_fields = ["receipt_no", "supplier_delivery_no", "purchase_order__order_no", "remark"]
    filterset_fields = [
        "company_id",
        "purchase_order_id",
        "supplier_id",
        "status",
        "warehouse_id",
        "inspection_result",
    ]
    ordering_fields = ["id", "receipt_no", "created_at", "inspected_at", "received_at"]
    uniqueness_error_map = {"uq_receipt_company_no": "同一公司下收货单号已存在。"}
    required_permissions = {
        "list": "procurement.receipt.view",
        "retrieve": "procurement.receipt.view",
        "create": "procurement.receipt.create",
        "partial_update": "procurement.receipt.update",
        # 收货过账最终由统一库存服务记账；跨模块动作需要同时具备库存侧权限（任务书 6.4）
        "post_receipt": [
            "procurement.receipt.post",
            "wms.document.create",
            "wms.document.post",
        ],
        # 检验判定最终调用统一库存服务的质量放行，权限必须同时具备（任务书 6.4）
        "inspect": ["procurement.receipt.inspect", "wms.quality.release"],
        "cancel": "procurement.receipt.update",
    }

    def _resolve_order(self, order_id: Any) -> PurchaseOrder:
        order = scoped_queryset(
            PurchaseOrder.objects.filter(pk=order_id),
            self.request.user,
            company_field="company_id",
            warehouse_field="warehouse_id",
        ).first()
        if order is None:
            raise ObjectNotFound("采购订单不存在或不在数据范围内。", details={"purchase_order_id": order_id})
        return order

    def _build_receipt_lines(self, order: PurchaseOrder, rows: list[dict]) -> list[dict]:
        line_ids = [row["order_line_id"] for row in rows]
        order_lines = {
            line.pk: line for line in PurchaseOrderLine.objects.filter(pk__in=line_ids, order_id=order.pk)
        }
        missing = [line_id for line_id in line_ids if line_id not in order_lines]
        if missing:
            raise ValidationFailed(
                "收货明细的订单行不属于该采购订单。",
                code="ORDER_LINE_MISMATCH",
                details={"order_line_ids": missing},
            )
        prepared: list[dict] = []
        for row in rows:
            location = None
            if row.get("location_id"):
                location = Location.objects.filter(pk=row["location_id"]).first()
                if location is None:
                    raise ObjectNotFound("储位不存在。", details={"location_id": row["location_id"]})
            prepared.append(
                {
                    "order_line": order_lines[row["order_line_id"]],
                    "quantity": row["quantity"],
                    "location": location,
                    "batch_no": row.get("batch_no", ""),
                    "roll_no": row.get("roll_no", ""),
                    "remark": row.get("remark", ""),
                }
            )
        return prepared

    def create(self, request, *args, **kwargs) -> Response:
        payload = ReceiptWriteSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        order = self._resolve_order(data["purchase_order_id"])
        warehouse = _resolve_warehouse(data.get("warehouse_id"), request.user)
        if warehouse is None and order.warehouse_id:
            warehouse = _resolve_warehouse(order.warehouse_id, request.user)
        if warehouse is None:
            raise ValidationFailed(
                "收货必须指定收货仓库（订单未指定仓库时需在收货单上指定）。",
                code="WAREHOUSE_REQUIRED",
            )
        lines = self._build_receipt_lines(order, data["lines"])
        receipt = services.create_receipt(
            user=request.user,
            order=order,
            warehouse=warehouse,
            lines=lines,
            supplier_delivery_no=data.get("supplier_delivery_no", ""),
            remark=data.get("remark", ""),
            receipt_no=data.get("receipt_no", ""),
        )
        assert_in_scope(receipt, request.user, **self.scope_fields)
        return Response(self.get_serializer(receipt).data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs) -> Response:
        from apps.core.services import assert_version

        receipt = self.get_object()
        assert_version(receipt, request.data.get("expected_version"))
        payload = ReceiptUpdateSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        header: dict[str, Any] = {}
        for field in ("supplier_delivery_no", "remark"):
            if field in data:
                header[field] = data[field]
        if "warehouse_id" in data:
            warehouse = _resolve_warehouse(data["warehouse_id"], request.user)
            if warehouse is None:
                raise ValidationFailed("收货仓库不能为空。", code="WAREHOUSE_REQUIRED")
            header["warehouse_id"] = warehouse.pk
        lines = None
        if data.get("lines") is not None:
            order = self._resolve_order(receipt.purchase_order_id)
            lines = self._build_receipt_lines(order, data["lines"])
        receipt = services.update_receipt(receipt, user=request.user, lines=lines, **header)
        return Response(self.get_serializer(receipt).data)

    @action(detail=True, methods=["post"], url_path="post")
    def post_receipt(self, request, *args, **kwargs) -> Response:
        """收货过账：记入**待检**库存。支持 Idempotency-Key（任务书 7.2）。"""
        receipt = self.get_object()
        idempotency_key = request.headers.get("Idempotency-Key") or None

        def _do_post() -> tuple[int, dict[str, Any]]:
            posted = services.post_receipt(receipt, user=request.user, idempotency_key=idempotency_key)
            return status.HTTP_200_OK, dict(self.get_serializer(posted).data)

        if idempotency_key:
            status_code, body, replayed = idempotent_execute(
                scope=f"procurement.receipt.post:{receipt.pk}",
                key=idempotency_key,
                payload={"receipt_id": receipt.pk, "idempotency_key": idempotency_key},
                func=_do_post,
                user=request.user,
            )
            response = Response(body, status=status_code)
            if replayed:
                response["Idempotency-Replayed"] = "true"
            return response

        status_code, body = _do_post()
        return Response(body, status=status_code)

    @action(detail=True, methods=["post"])
    def inspect(self, request, *args, **kwargs) -> Response:
        """来料检验判定（人工录入，非自动检测）：待检 → 合格 / 不合格。"""
        receipt = self.get_object()
        payload = InspectReceiptSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        idempotency_key = request.headers.get("Idempotency-Key") or None

        def _do_inspect() -> tuple[int, dict[str, Any]]:
            inspected = services.inspect_receipt(
                receipt,
                user=request.user,
                result=payload.validated_data["result"],
                remark=payload.validated_data["remark"],
                idempotency_key=idempotency_key,
            )
            return status.HTTP_200_OK, dict(self.get_serializer(inspected).data)

        if idempotency_key:
            status_code, body, replayed = idempotent_execute(
                scope=f"procurement.receipt.inspect:{receipt.pk}",
                key=idempotency_key,
                payload={
                    "receipt_id": receipt.pk,
                    "result": payload.validated_data["result"],
                    "idempotency_key": idempotency_key,
                },
                func=_do_inspect,
                user=request.user,
            )
            response = Response(body, status=status_code)
            if replayed:
                response["Idempotency-Replayed"] = "true"
            return response

        status_code, body = _do_inspect()
        return Response(body, status=status_code)

    @action(detail=True, methods=["post"])
    def cancel(self, request, *args, **kwargs) -> Response:
        receipt = self.get_object()
        payload = ReasonActionSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        receipt = services.cancel_receipt(receipt, user=request.user, reason=payload.validated_data["reason"])
        return Response(self.get_serializer(receipt).data)


__all__ = [
    "GoodsReceiptViewSet",
    "PurchaseOrderViewSet",
    "RequisitionViewSet",
]
