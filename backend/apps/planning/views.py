"""计划模块接口：BOM（物料清单）、工艺路线与 MRP。

职责边界（任务书 4.3）：

* 视图只做请求解析、权限声明、数据范围校验与调用服务；
* 版本号、状态迁移、损耗计算、审核回写全部在 `apps.planning.services` 内完成；
* 视图**不直接写**单据表、不接收前端传入的版本号与状态，也不接受派生数值（含损耗用量）。

数据范围：BOM / 工艺路线以 `company_id` 收敛；关联对象（款式、SKU、物料、单位、车间）
逐一做范围校验，避免用他人 ID 越权（任务书 6.4）。
"""

from __future__ import annotations

from typing import Any

from django.db.models import Count
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.exceptions import ObjectNotFound, ValidationFailed
from apps.core.pagination import StandardPagination
from apps.core.selectors import assert_in_scope
from apps.core.services import assert_version
from apps.core.viewsets import ScopedModelViewSet
from apps.factory.models import Company, Workshop
from apps.masterdata.models import Material, Sku, Style, UoM
from apps.planning import mrp, services
from apps.planning.models import Bom, MrpRun, MrpSuggestion, Routing
from apps.planning.serializers import (
    BomSerializer,
    BomUpdateSerializer,
    BomWriteSerializer,
    MrpArchiveSerializer,
    MrpCancelSerializer,
    MrpConvertSerializer,
    MrpDemandLineSerializer,
    MrpRunCreateSerializer,
    MrpRunSerializer,
    MrpSuggestionSerializer,
    MrpSupplyLineSerializer,
    NewVersionSerializer,
    ReasonActionSerializer,
    RoutingSerializer,
    RoutingUpdateSerializer,
    RoutingWriteSerializer,
    SubmitActionSerializer,
)


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


def _resolve_style(style_id: Any, user: Any, company: Company) -> Style:
    style = Style.objects.filter(pk=style_id).first()
    if style is None:
        raise ObjectNotFound("款式不存在。", details={"style_id": style_id})
    if style.company_id != company.pk:
        raise ValidationFailed("款式与公司不一致。", code="COMPANY_STYLE_MISMATCH")
    assert_in_scope(style, user, company_field="company_id")
    return style


def _resolve_sku(sku_id: Any, user: Any, company: Company) -> Sku | None:
    if not sku_id:
        return None
    sku = Sku.objects.filter(pk=sku_id).first()
    if sku is None:
        raise ObjectNotFound("SKU 不存在。", details={"sku_id": sku_id})
    if sku.company_id != company.pk:
        raise ValidationFailed("SKU 与公司不一致。", code="COMPANY_SKU_MISMATCH")
    assert_in_scope(sku, user, company_field="company_id")
    return sku


def _resolve_material(material_id: Any, user: Any, company: Company) -> Material:
    material = Material.objects.filter(pk=material_id).first()
    if material is None:
        raise ObjectNotFound("物料不存在。", details={"material_id": material_id})
    if material.company_id != company.pk:
        raise ValidationFailed("物料与公司不一致。", code="COMPANY_MATERIAL_MISMATCH")
    assert_in_scope(material, user, company_field="company_id")
    return material


def _resolve_uom(uom_id: Any, user: Any) -> UoM | None:
    if not uom_id:
        return None
    uom = UoM.objects.filter(pk=uom_id).first()
    if uom is None:
        raise ObjectNotFound("计量单位不存在。", details={"uom_id": uom_id})
    return uom


def _resolve_workshop(workshop_id: Any, user: Any) -> Workshop | None:
    if not workshop_id:
        return None
    workshop = Workshop.objects.filter(pk=workshop_id).first()
    if workshop is None:
        raise ObjectNotFound("车间不存在。", details={"workshop_id": workshop_id})
    assert_in_scope(
        workshop, user, company_field="factory__company_id", factory_field="factory_id"
    )
    return workshop

def _bom_line_rows(rows: list[dict], user: Any, company: Company) -> list[dict]:
    """把接口输入行映射成服务层键名（服务层使用 `material` / `uom` 对象）。"""
    return [
        {
            "material": _resolve_material(row["material_id"], user, company),
            "quantity": row["quantity"],
            "loss_rate": row.get("loss_rate"),
            "uom": _resolve_uom(row.get("uom_id"), user),
            "line_type": row.get("line_type") or "normal",
            "substitute_for_line_no": row.get("substitute_for_line_no"),
            "position": row.get("position", ""),
            "is_key_material": row.get("is_key_material", False),
            "remark": row.get("remark", ""),
        }
        for row in rows
    ]


def _routing_step_rows(rows: list[dict], user: Any) -> list[dict]:
    return [
        {
            "sequence": row.get("sequence"),
            "name": row["name"],
            "workshop": _resolve_workshop(row.get("workshop_id"), user),
            "workcenter": row.get("workcenter", ""),
            "equipment_requirement": row.get("equipment_requirement", ""),
            "standard_hours": row.get("standard_hours"),
            "is_quality_gate": row.get("is_quality_gate", False),
            "is_outsourced": row.get("is_outsourced", False),
            "remark": row.get("remark", ""),
        }
        for row in rows
    ]


class BomViewSet(ScopedModelViewSet):
    """物料清单：草稿 → 提交审批 → 已审核（唯一生效版本）→ 派生新版本 / 作废。

    已审核版本的**内容不可修改**：需要变更只能 `new-version` 派生草稿新版本，
    因此已下达工单引用的版本快照不受影响（任务书 9.5、14.2 案例 13）。
    """

    queryset = (
        Bom.objects.select_related("company", "style", "sku", "approved_by")
        .prefetch_related("lines__material", "lines__uom", "lines__substitute_for")
        .all()
    )
    serializer_class = BomSerializer
    scope_fields = {"company_field": "company_id"}
    audit_fields = (
        "code",
        "version_no",
        "status",
        "style_id",
        "sku_id",
        "effective_from",
        "effective_to",
        "is_active",
    )
    search_fields = ["code", "style__code", "style__name", "sku__code", "remark"]
    filterset_fields = ["company_id", "style_id", "sku_id", "status", "is_active"]
    ordering_fields = ["id", "code", "version_no", "effective_from", "created_at", "updated_at"]
    uniqueness_error_map = {
        "uq_bom_company_code": "同一公司下 BOM 编号已存在。",
        "uq_bom_scope_version": "该款式 / SKU 范围的相同版本号已存在，请派生新版本后重试。",
        "uq_bom_line_no": "BOM 明细行号重复。",
    }
    required_permissions = {
        "list": "planning.bom.view",
        "retrieve": "planning.bom.view",
        "create": "planning.bom.create",
        "partial_update": "planning.bom.update",
        "submit": "planning.bom.submit",
        "obsolete": "planning.bom.obsolete",
        "new_version": "planning.bom.create",
        "snapshot": "planning.bom.view",
    }

    def create(self, request, *args, **kwargs) -> Response:
        payload = BomWriteSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        company = _resolve_company(request.user, request.data.get("company_id"))
        bom = services.create_bom(
            user=request.user,
            company=company,
            style=_resolve_style(data["style_id"], request.user, company),
            sku=_resolve_sku(data.get("sku_id"), request.user, company),
            lines=_bom_line_rows(data["lines"], request.user, company),
            effective_from=data.get("effective_from"),
            effective_to=data.get("effective_to"),
            remark=data.get("remark", ""),
            code=data.get("code", ""),
        )
        assert_in_scope(bom, request.user, **self.scope_fields)
        return Response(self.get_serializer(bom).data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs) -> Response:
        bom = self.get_object()
        assert_version(bom, request.data.get("expected_version"))
        payload = BomUpdateSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        header = {field: data[field] for field in ("effective_from", "effective_to", "remark") if field in data}
        lines = data.get("lines")
        if lines is not None:
            if not lines:
                raise ValidationFailed("BOM 至少需要一行。", code="EMPTY_DOCUMENT")
            lines = _bom_line_rows(lines, request.user, bom.company)
        bom = services.update_bom(bom, user=request.user, header=header, lines=lines)
        return Response(self.get_serializer(bom).data)

    @action(detail=True, methods=["post"])
    def submit(self, request, *args, **kwargs) -> Response:
        bom = self.get_object()
        payload = SubmitActionSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        bom = services.submit_bom(
            bom, user=request.user, comment=payload.validated_data.get("comment", "")
        )
        return Response(self.get_serializer(bom).data)

    @action(detail=True, methods=["post"])
    def obsolete(self, request, *args, **kwargs) -> Response:
        """作废版本：只改状态与启用标记，不物理删除（任务书 5.5）。"""
        bom = self.get_object()
        payload = ReasonActionSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        bom = services.obsolete_bom(bom, user=request.user, reason=payload.validated_data["reason"])
        return Response(self.get_serializer(bom).data)

    @action(detail=True, methods=["post"], url_path="new-version")
    def new_version(self, request, *args, **kwargs) -> Response:
        """派生新草稿版本（唯一允许的变更方式）。"""
        bom = self.get_object()
        payload = NewVersionSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        new_bom = services.create_bom_version(
            bom, user=request.user, effective_from=payload.validated_data.get("effective_from")
        )
        return Response(self.get_serializer(new_bom).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"])
    def snapshot(self, request, *args, **kwargs) -> Response:
        """输出不可变快照。MES 工单下达时保存同一结构（任务书 9.5）。"""
        bom = self.get_object()
        return Response(services.build_bom_snapshot(bom))


class RoutingViewSet(ScopedModelViewSet):
    """工艺路线：与 BOM 相同的版本 / 审核 / 派生规则。"""

    queryset = (
        Routing.objects.select_related("company", "style", "sku", "approved_by")
        .prefetch_related("steps__workshop")
        .all()
    )
    serializer_class = RoutingSerializer
    scope_fields = {"company_field": "company_id"}
    audit_fields = (
        "code",
        "version_no",
        "status",
        "style_id",
        "sku_id",
        "effective_from",
        "effective_to",
        "is_active",
    )
    search_fields = ["code", "style__code", "style__name", "sku__code", "remark"]
    filterset_fields = ["company_id", "style_id", "sku_id", "status", "is_active"]
    ordering_fields = ["id", "code", "version_no", "effective_from", "created_at", "updated_at"]
    uniqueness_error_map = {
        "uq_routing_company_code": "同一公司下工艺编号已存在。",
        "uq_routing_scope_version": "该款式 / SKU 范围的相同版本号已存在，请派生新版本后重试。",
        "uq_routing_step_sequence": "工序顺序重复。",
    }
    required_permissions = {
        "list": "planning.routing.view",
        "retrieve": "planning.routing.view",
        "create": "planning.routing.create",
        "partial_update": "planning.routing.update",
        "submit": "planning.routing.submit",
        "obsolete": "planning.routing.obsolete",
        "new_version": "planning.routing.create",
        "snapshot": "planning.routing.view",
    }

    def create(self, request, *args, **kwargs) -> Response:
        payload = RoutingWriteSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        company = _resolve_company(request.user, request.data.get("company_id"))
        raw_steps = data.get("steps")
        routing = services.create_routing(
            user=request.user,
            company=company,
            style=_resolve_style(data["style_id"], request.user, company),
            sku=_resolve_sku(data.get("sku_id"), request.user, company),
            steps=None if raw_steps is None else _routing_step_rows(raw_steps, request.user),
            effective_from=data.get("effective_from"),
            effective_to=data.get("effective_to"),
            remark=data.get("remark", ""),
            code=data.get("code", ""),
        )
        assert_in_scope(routing, request.user, **self.scope_fields)
        return Response(self.get_serializer(routing).data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs) -> Response:
        routing = self.get_object()
        assert_version(routing, request.data.get("expected_version"))
        payload = RoutingUpdateSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        header = {
            field: data[field]
            for field in ("effective_from", "effective_to", "remark")
            if field in data
        }
        steps = data.get("steps")
        if steps is not None:
            if not steps:
                raise ValidationFailed("工艺路线至少需要一道工序。", code="EMPTY_DOCUMENT")
            steps = _routing_step_rows(steps, request.user)
        routing = services.update_routing(routing, user=request.user, header=header, steps=steps)
        return Response(self.get_serializer(routing).data)

    @action(detail=True, methods=["post"])
    def submit(self, request, *args, **kwargs) -> Response:
        routing = self.get_object()
        payload = SubmitActionSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        routing = services.submit_routing(
            routing, user=request.user, comment=payload.validated_data.get("comment", "")
        )
        return Response(self.get_serializer(routing).data)

    @action(detail=True, methods=["post"])
    def obsolete(self, request, *args, **kwargs) -> Response:
        routing = self.get_object()
        payload = ReasonActionSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        routing = services.obsolete_routing(
            routing, user=request.user, reason=payload.validated_data["reason"]
        )
        return Response(self.get_serializer(routing).data)

    @action(detail=True, methods=["post"], url_path="new-version")
    def new_version(self, request, *args, **kwargs) -> Response:
        routing = self.get_object()
        payload = NewVersionSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        new_routing = services.create_routing_version(
            routing, user=request.user, effective_from=payload.validated_data.get("effective_from")
        )
        return Response(self.get_serializer(new_routing).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"])
    def snapshot(self, request, *args, **kwargs) -> Response:
        routing = self.get_object()
        return Response(services.build_routing_snapshot(routing))

# ---------------------------------------------------------------------------
# MRP（阶段 3 第二步）
# ---------------------------------------------------------------------------


def _resolve_warehouse(warehouse_id: Any, user: Any, company: Company) -> Any | None:
    """解析可选仓库条件（限定某仓库的可用量口径）。"""
    from apps.wms.models import Warehouse

    if not warehouse_id:
        return None
    warehouse = Warehouse.objects.filter(pk=warehouse_id).first()
    if warehouse is None:
        raise ObjectNotFound("仓库不存在。", details={"warehouse_id": warehouse_id})
    if warehouse.company_id != company.pk:
        raise ValidationFailed("仓库与公司不一致。", code="COMPANY_WAREHOUSE_MISMATCH")
    assert_in_scope(warehouse, user, company_field="company_id")
    return warehouse


class MrpRunViewSet(ScopedModelViewSet):
    """MRP 运行：同步计算 + 结果查询（需求 / 供给 / 缺料建议）。

    视图只负责取参数、校验范围、调服务；净算与建议生成全部在 `apps.planning.mrp`。
    """

    queryset = (
        MrpRun.objects.select_related("company", "warehouse", "archived_by")
        .annotate(
            demand_count=Count("demands", distinct=True),
            supply_count=Count("supplies", distinct=True),
            suggestion_count=Count("suggestions", distinct=True),
        )
        .order_by("-id")
    )
    serializer_class = MrpRunSerializer
    scope_fields = {"company_field": "company_id"}
    audit_fields = (
        "run_no",
        "status",
        "bucket",
        "horizon_start",
        "horizon_end",
        "warehouse_id",
    )
    search_fields = ["run_no", "remark"]
    filterset_fields = ["company_id", "status", "bucket", "warehouse_id"]
    ordering_fields = ["id", "run_no", "horizon_start", "horizon_end", "created_at", "finished_at"]
    uniqueness_error_map = {"uq_mrp_run_company_no": "MRP 运行编号已存在，请重试。"}
    required_permissions = {
        "list": "planning.mrp.view",
        "retrieve": "planning.mrp.view",
        "create": "planning.mrp.run",
        "demands": "planning.mrp.view",
        "supplies": "planning.mrp.view",
        "suggestions": "planning.mrp.view",
        "archive": "planning.mrp.archive",
    }

    def create(self, request, *args, **kwargs) -> Response:
        payload = MrpRunCreateSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        company = _resolve_company(request.user, data.get("company_id"))
        warehouse = _resolve_warehouse(data.get("warehouse_id"), request.user, company)
        run = mrp.run_mrp(
            company=company,
            user=request.user,
            horizon_start=data["horizon_start"],
            horizon_end=data["horizon_end"],
            bucket=data["bucket"],
            warehouse=warehouse,
            remark=data.get("remark", ""),
        )
        assert_in_scope(run, request.user, **self.scope_fields)
        serializer = self.get_serializer(
            MrpRun.objects.annotate(
                demand_count=Count("demands", distinct=True),
                supply_count=Count("supplies", distinct=True),
                suggestion_count=Count("suggestions", distinct=True),
            ).get(pk=run.pk)
        )
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def _paginated(self, queryset, serializer_class, request) -> Response:
        paginator = StandardPagination()
        page = paginator.paginate_queryset(queryset, request, view=self)
        serializer = serializer_class(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    @action(detail=True, methods=["get"])
    def demands(self, request, *args, **kwargs) -> Response:
        """展开后的需求行（含来源路径，用于供需追溯）。"""
        run = self.get_object()
        queryset = (
            run.demands.select_related("material", "sku", "style", "warehouse")
            .order_by("line_no")
        )
        return self._paginated(queryset, MrpDemandLineSerializer, request)

    @action(detail=True, methods=["get"])
    def supplies(self, request, *args, **kwargs) -> Response:
        """本次计算认到的供给（现有可用库存 / 采购在途）。"""
        run = self.get_object()
        queryset = run.supplies.select_related("material", "warehouse").order_by("line_no")
        return self._paginated(queryset, MrpSupplyLineSerializer, request)

    @action(detail=True, methods=["get"])
    def suggestions(self, request, *args, **kwargs) -> Response:
        """缺料清单 / 建议清单。"""
        run = self.get_object()
        queryset = (
            run.suggestions.select_related("material", "sku", "style", "warehouse", "uom")
            .order_by("line_no")
        )
        suggestion_type = request.query_params.get("suggestion_type")
        if suggestion_type:
            queryset = queryset.filter(suggestion_type=suggestion_type)
        suggestion_status = request.query_params.get("status")
        if suggestion_status:
            queryset = queryset.filter(status=suggestion_status)
        return self._paginated(queryset, MrpSuggestionSerializer, request)

    @action(detail=True, methods=["post"])
    def archive(self, request, *args, **kwargs) -> Response:
        """归档运行（只改状态，不删明细）。"""
        run = self.get_object()
        payload = MrpArchiveSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        run = mrp.archive_run(run, user=request.user, reason=payload.validated_data.get("reason", ""))
        return Response(self.get_serializer(run).data)


class MrpSuggestionViewSet(ScopedModelViewSet):
    """MRP 建议：查询、转采购申请（草稿）、取消。

    转单后建议状态变为 `converted` 并记录目标单据；重复转单、过期建议（已被更新的运行取代）、
    生产建议（MES 未实现）都会被服务层拒绝。
    """

    queryset = MrpSuggestion.objects.select_related(
        "run", "run__company", "material", "sku", "style", "warehouse", "uom", "converted_by"
    ).order_by("-id")
    serializer_class = MrpSuggestionSerializer
    scope_fields = {"company_field": "run__company_id"}
    audit_fields = ("status", "material_id", "quantity", "bucket_date")
    search_fields = ["material__code", "material__name", "reason", "run__run_no"]
    filterset_fields = ["run_id", "suggestion_type", "status", "material_id", "warehouse_id"]
    ordering_fields = ["id", "line_no", "quantity", "due_date", "bucket_date", "created_at"]
    required_permissions = {
        "list": "planning.mrp.view",
        "retrieve": "planning.mrp.view",
        "convert": "planning.mrp.convert",
        "cancel": "planning.mrp.cancel",
    }

    @action(detail=True, methods=["post"])
    def convert(self, request, *args, **kwargs) -> Response:
        """采购建议 → 草稿采购申请（仍走采购审批；生产建议明确拒绝，不伪造工单）。"""
        suggestion = self.get_object()
        payload = MrpConvertSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        suggestion = mrp.convert_suggestion(
            suggestion,
            user=request.user,
            needed_date=payload.validated_data.get("needed_date"),
            remark=payload.validated_data.get("remark", ""),
        )
        return Response(self.get_serializer(suggestion).data)

    @action(detail=True, methods=["post"])
    def cancel(self, request, *args, **kwargs) -> Response:
        suggestion = self.get_object()
        payload = MrpCancelSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        suggestion = mrp.cancel_suggestion(
            suggestion, user=request.user, reason=payload.validated_data["reason"]
        )
        return Response(self.get_serializer(suggestion).data)
