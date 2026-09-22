"""生产执行接口：工单（用料 / 工序 / 下达 / 领料 / 报工 / 完工 / 入库 / 关闭 / 取消）与报工台账。

状态推进一律走动作接口（POST），PATCH 只能改草稿工单的表头字段——
把状态机开放给 PATCH 就等于允许跳步，这是本仓库明令禁止的。
"""

from __future__ import annotations

from typing import Any

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.exceptions import StateConflict, ValidationFailed
from apps.core.permissions import require_codes
from apps.core.services import idempotent_execute
from apps.core.viewsets import ActiveFilterMixin, ReadOnlyScopedViewSet, ScopedModelViewSet
from apps.mes import selectors, services
from apps.mes.models import ProductionOrder, ProductionOrderStatus, ProductionReport
from apps.mes.serializers import (
    IssueMaterialsInputSerializer,
    ProductionMaterialsInputSerializer,
    ProductionOrderMaterialSerializer,
    ProductionOrderSerializer,
    ProductionOrderStepSerializer,
    ProductionReportInputSerializer,
    ProductionReportSerializer,
    ReasonActionSerializer,
    ReceiptInputSerializer,
    ReportActionInputSerializer,
)


def _int_or_none(value: Any) -> int | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return int(text)
    except ValueError as exc:
        raise ValidationFailed(f"参数应为整数：{value}。", code="INVALID_QUERY_PARAM") from exc


class ProductionOrderViewSet(ActiveFilterMixin, ScopedModelViewSet):
    """生产工单：草稿 → 下达 → 生产中 → 已完工 → 已关闭；草稿 / 已下达可取消。"""

    queryset = (
        ProductionOrder.objects.select_related(
            "company", "style", "sku", "product_material", "factory", "workshop",
            "production_line", "material_warehouse", "receipt_warehouse", "owner",
            "issue_document", "receipt_document",
        )
        .prefetch_related("materials__material", "steps__inspection_order", "reports")
        .all()
    )
    serializer_class = ProductionOrderSerializer
    scope_fields = {"company_field": "company_id", "factory_field": "factory_id"}
    audit_fields = (
        "order_no", "source_type", "source_no", "style_id", "sku_id", "product_material_id",
        "quantity", "unit", "factory_id", "workshop_id", "production_line_id",
        "material_warehouse_id", "receipt_warehouse_id", "planned_start", "planned_end",
        "owner_id", "is_active",
    )
    search_fields = ["order_no", "source_no", "style__code", "style__name", "remark"]
    filterset_fields = [
        "company_id", "status", "source_type", "style_id", "factory_id", "workshop_id",
        "production_line_id", "is_active",
    ]
    ordering_fields = ["id", "order_no", "planned_start", "planned_end", "created_at"]
    uniqueness_error_map = {"uq_mes_order_company_no": "同一公司下工单号已存在。"}
    required_permissions = {
        "list": "mes.order.view",
        "retrieve": "mes.order.view",
        "create": "mes.order.create",
        "partial_update": "mes.order.update",
        "set_active": "mes.order.update",
        # materials 一个 action 同时服务查看（GET）与替换（POST）：权限按 self.action
        # 解析，同一个 action 只能声明一份编码，写路径在方法内用 require_codes 二次校验。
        "materials": "mes.order.view",
        "steps": "mes.order.view",
        "statistics": "mes.order.view",
        "release": "mes.order.release",
        "issue_materials": "mes.order.issue",
        "report": "mes.report.create",
        "complete": "mes.order.complete",
        "receipt": "mes.order.complete",
        "close": "mes.order.close",
        "cancel": "mes.order.cancel",
    }

    def perform_create(self, serializer) -> None:
        data = serializer.validated_data
        data["order_no"] = str(data.get("order_no") or "").strip() or services.next_order_no()
        super().perform_create(serializer)

    def perform_update(self, serializer) -> None:
        """表头只允许在草稿上改：已下达工单的计划数量、用料与工序已经冻结。"""
        order = serializer.instance
        if order is not None and order.status != ProductionOrderStatus.DRAFT:
            raise StateConflict(
                f"工单当前状态为「{order.get_status_display()}」，只有草稿工单可以修改表头。",
                code="STATE_CONFLICT",
                details={"order_no": order.order_no, "status": order.status},
            )
        super().perform_update(serializer)

    def _reload(self, order: ProductionOrder) -> ProductionOrder:
        """动作改过明细后重新取一次，避免把 prefetch 的旧快照返回给前端。"""
        return self.get_queryset().get(pk=order.pk)

    @extend_schema(responses={200: dict})
    @action(detail=False, methods=["get"], url_path="statistics")
    def statistics(self, request, *args, **kwargs) -> Response:
        """生产执行看板：工单量、产出与合格、工序报废与未判定质检点（实时聚合）。"""
        params = request.query_params
        return Response(
            selectors.production_statistics(
                request.user,
                since=params.get("since"),
                until=params.get("until"),
                company_id=_int_or_none(params.get("company_id")),
                workshop_id=_int_or_none(params.get("workshop_id")),
            )
        )

    @extend_schema(responses={200: ProductionOrderMaterialSerializer(many=True)})
    @action(detail=True, methods=["get", "post"], url_path="materials")
    def materials(self, request, *args, **kwargs) -> Response:
        """查看（GET）或整表替换（POST）工单用料。只有草稿工单可以改。"""
        order = self.get_object()
        if request.method == "POST":
            require_codes(request.user, "mes.order.update")
            payload = ProductionMaterialsInputSerializer(data=request.data)
            payload.is_valid(raise_exception=True)
            order = services.update_order(
                order, user=request.user, materials=payload.validated_data["materials"]
            )
            order = self._reload(order)
        return Response(ProductionOrderMaterialSerializer(order.materials.all(), many=True).data)

    @extend_schema(responses={200: ProductionOrderStepSerializer(many=True)})
    @action(detail=True, methods=["get"], url_path="steps")
    def steps(self, request, *args, **kwargs) -> Response:
        """查看工单工序（下达时按工艺路线快照生成，工单侧只读）。"""
        order = self.get_object()
        return Response(ProductionOrderStepSerializer(order.steps.all(), many=True).data)

    @extend_schema(request=None, responses={200: ProductionOrderSerializer})
    @action(detail=True, methods=["post"], url_path="release")
    def release(self, request, *args, **kwargs) -> Response:
        """下达工单：冻结 BOM / 工艺路线快照并生成工序与用料行。"""
        order = self.get_object()
        updated = services.release_order(order, user=request.user)
        return Response(self.get_serializer(self._reload(updated)).data)

    @extend_schema(
        request=IssueMaterialsInputSerializer, responses={200: ProductionOrderSerializer}
    )
    @action(detail=True, methods=["post"], url_path="issue-materials")
    def issue_materials(self, request, *args, **kwargs) -> Response:
        """工单领料：生成并过账库存出库单据（支持 Idempotency-Key）。"""
        order = self.get_object()
        payload = IssueMaterialsInputSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        lines = payload.validated_data.get("lines")
        idempotency_key = request.headers.get("Idempotency-Key") or None

        def _do_issue() -> tuple[int, dict[str, Any]]:
            updated, _document = services.issue_materials(
                order, user=request.user, lines=lines, idempotency_key=idempotency_key
            )
            return status.HTTP_200_OK, dict(self.get_serializer(self._reload(updated)).data)

        if idempotency_key:
            code, body, replayed = idempotent_execute(
                scope=f"mes.order.issue:{order.pk}",
                key=idempotency_key,
                payload={"order_id": order.pk, "idempotency_key": idempotency_key},
                func=_do_issue,
                user=request.user,
            )
            response = Response(body, status=code)
            if replayed:
                response["Idempotency-Replayed"] = "true"
            return response
        _code, body = _do_issue()
        return Response(body, status=_code)

    @extend_schema(
        request=ProductionReportInputSerializer, responses={200: ProductionOrderSerializer}
    )
    @action(detail=True, methods=["post"], url_path="report")
    def report(self, request, *args, **kwargs) -> Response:
        """按工序报工：推进工序与工单进度，质检点报满时自动生成 QMS 检验单。"""
        order = self.get_object()
        payload = ProductionReportInputSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = dict(payload.validated_data)
        declared_order = data.pop("order", None)
        if declared_order is not None and declared_order.pk != order.pk:
            raise ValidationFailed("报工工单与请求路径不一致。", code="ORDER_MISMATCH")
        _report, updated = services.report_production(order, user=request.user, **data)
        return Response(self.get_serializer(self._reload(updated)).data)

    @extend_schema(request=ReportActionInputSerializer, responses={200: ProductionOrderSerializer})
    @action(detail=True, methods=["post"], url_path="complete")
    def complete(self, request, *args, **kwargs) -> Response:
        """工单完工：要求全部工序报满且质检点检验单判定合格 / 让步接收。"""
        order = self.get_object()
        payload = ReportActionInputSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        updated = services.complete_order(
            order, user=request.user, remark=payload.validated_data.get("remark") or ""
        )
        return Response(self.get_serializer(self._reload(updated)).data)

    @extend_schema(request=ReceiptInputSerializer, responses={200: ProductionOrderSerializer})
    @action(detail=True, methods=["post"], url_path="receipt")
    def receipt(self, request, *args, **kwargs) -> Response:
        """完工入库：按合格数量生成并过账库存入库单据（支持 Idempotency-Key）。"""
        order = self.get_object()
        payload = ReceiptInputSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        idempotency_key = request.headers.get("Idempotency-Key") or None

        def _do_receipt() -> tuple[int, dict[str, Any]]:
            updated, _document = services.receipt_finished_goods(
                order,
                user=request.user,
                location=data.get("location"),
                batch_no=data.get("batch_no") or "",
                idempotency_key=idempotency_key,
            )
            return status.HTTP_200_OK, dict(self.get_serializer(self._reload(updated)).data)

        if idempotency_key:
            code, body, replayed = idempotent_execute(
                scope=f"mes.order.receipt:{order.pk}",
                key=idempotency_key,
                payload={"order_id": order.pk, "idempotency_key": idempotency_key},
                func=_do_receipt,
                user=request.user,
            )
            response = Response(body, status=code)
            if replayed:
                response["Idempotency-Replayed"] = "true"
            return response
        _code, body = _do_receipt()
        return Response(body, status=_code)

    @extend_schema(request=ReportActionInputSerializer, responses={200: ProductionOrderSerializer})
    @action(detail=True, methods=["post"], url_path="close")
    def close(self, request, *args, **kwargs) -> Response:
        """关闭工单：已完工 → 已关闭。"""
        order = self.get_object()
        payload = ReportActionInputSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        updated = services.close_order(
            order, user=request.user, remark=payload.validated_data.get("remark") or ""
        )
        return Response(self.get_serializer(self._reload(updated)).data)

    @extend_schema(request=ReasonActionSerializer, responses={200: ProductionOrderSerializer})
    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request, *args, **kwargs) -> Response:
        """取消工单：必须写原因；已开工工单不能取消。"""
        order = self.get_object()
        payload = ReasonActionSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        updated = services.cancel_order(
            order, user=request.user, reason=payload.validated_data["reason"]
        )
        return Response(self.get_serializer(self._reload(updated)).data)


class ProductionReportViewSet(ReadOnlyScopedViewSet):
    """生产报工台账：可查可新增，**不提供修改与删除**（原始记录不可回改）。"""

    queryset = ProductionReport.objects.select_related(
        "company", "order", "step", "operator", "equipment"
    ).all()
    serializer_class = ProductionReportSerializer
    http_method_names = ["get", "post", "head", "options"]
    scope_fields = {"company_field": "company_id", "factory_field": "order__factory_id"}
    search_fields = ["report_no", "order__order_no", "step__name", "remark"]
    filterset_fields = [
        "company_id", "order_id", "step_id", "report_type", "operator_id", "equipment_id",
    ]
    ordering_fields = ["id", "report_no", "reported_at", "created_at"]
    uniqueness_error_map = {"uq_mes_report_company_no": "同一公司下报工单号已存在。"}
    required_permissions = {
        "list": "mes.report.view",
        "retrieve": "mes.report.view",
        "create": "mes.report.create",
    }

    @extend_schema(
        request=ProductionReportInputSerializer, responses={201: ProductionReportSerializer}
    )
    def create(self, request, *args, **kwargs) -> Response:
        """新增报工：数量口径由服务层校验，报工单号由服务层取号。"""
        payload = ProductionReportInputSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = dict(payload.validated_data)
        order = data.pop("order", None)
        if order is None:
            raise ValidationFailed("报工必须指定生产工单。", code="ORDER_REQUIRED")
        report, _updated = services.report_production(order, user=request.user, **data)
        return Response(ProductionReportSerializer(report).data, status=201)
