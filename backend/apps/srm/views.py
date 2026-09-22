"""供应商接口：档案、联系人、资质，以及五维量化评价与权重配置。

供应商归属公司，按数据范围过滤；联系人与资质通过 `supplier__company_id`
继承同一范围，避免「看不到供应商、却能读到其联系人/资质」的越权读取。

评价相关的写入**全部经服务层**：

* 权重配置只增不改——`PATCH` 会用旧版本派生出一个**新版本**（响应体是新的那一条），
  旧版本原样保留，历史评价引用的权重快照因此始终可解释；
* 评价明细经 `lines` 动作整表替换，总分由服务层按权重快照重算，
  客户端传上来的 `total_score` 一律忽略；
* 状态（草稿 → 已生效 → 已归档）只能由 `publish` / `archive` 动作推进。
"""

from __future__ import annotations

from typing import Any

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.exceptions import ObjectNotFound, StateConflict, ValidationFailed
from apps.core.permissions import require_codes
from apps.core.selectors import assert_in_scope
from apps.core.services import assert_version
from apps.core.viewsets import ActiveFilterMixin, ScopedModelViewSet
from apps.factory.models import Company, Employee
from apps.srm import selectors, services
from apps.srm.models import (
    DIMENSION_WEIGHT_FIELD,
    MissingDimensionPolicy,
    Supplier,
    SupplierContact,
    SupplierEvaluation,
    SupplierEvaluationWeight,
    SupplierQualification,
)
from apps.srm.serializers import (
    EvaluationLinesInputSerializer,
    EvaluationUpdateSerializer,
    EvaluationWeightUpdateSerializer,
    EvaluationWeightWriteSerializer,
    EvaluationWriteSerializer,
    SupplierContactSerializer,
    SupplierEvaluationLineSerializer,
    SupplierEvaluationSerializer,
    SupplierEvaluationWeightSerializer,
    SupplierQualificationSerializer,
    SupplierSerializer,
)
from apps.srm.services import ensure_single_primary_contact


def _int_or_none(value: Any) -> int | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return int(text)
    except ValueError as exc:
        raise ValidationFailed(f"参数应为整数：{value}。", code="INVALID_QUERY_PARAM") from exc


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


def _resolve_supplier(supplier_id: Any, user: Any, company: Company) -> Supplier:
    supplier = Supplier.objects.filter(pk=supplier_id).first()
    if supplier is None:
        raise ObjectNotFound("供应商不存在。", details={"supplier_id": supplier_id})
    if supplier.company_id != company.pk:
        raise ValidationFailed("供应商与公司不一致。", code="COMPANY_SUPPLIER_MISMATCH")
    assert_in_scope(supplier, user, company_field="company_id")
    return supplier


def _resolve_weight_config(config_id: Any, user: Any, company: Company) -> SupplierEvaluationWeight:
    config = SupplierEvaluationWeight.objects.filter(pk=config_id).first()
    if config is None:
        raise ObjectNotFound("权重配置不存在。", details={"weight_config_id": config_id})
    if config.company_id != company.pk:
        raise ValidationFailed("权重配置与公司不一致。", code="COMPANY_WEIGHT_MISMATCH")
    assert_in_scope(config, user, company_field="company_id")
    return config


def _resolve_employee(employee_id: Any, user: Any) -> Employee | None:
    if not employee_id:
        return None
    employee = Employee.objects.filter(pk=employee_id).first()
    if employee is None:
        raise ObjectNotFound("员工不存在。", details={"evaluated_by_id": employee_id})
    assert_in_scope(employee, user, company_field="company_id")
    return employee


def _weight_values(data: dict[str, Any]) -> dict[str, Any]:
    """把请求里出现的权重字段映射成「维度 → 值」；未出现的项由服务层沿用/视为 0。"""
    return {
        dimension: data[field]
        for dimension, field in DIMENSION_WEIGHT_FIELD.items()
        if data.get(field) is not None
    }


class SupplierViewSet(ActiveFilterMixin, ScopedModelViewSet):
    queryset = Supplier.objects.select_related("company", "buyer").all()
    serializer_class = SupplierSerializer
    scope_fields = {"company_field": "company_id"}
    audit_fields = (
        "code", "name", "short_name", "category", "grade", "admission_status",
        "payment_terms", "buyer_id", "is_active",
    )
    search_fields = ["code", "name", "short_name", "primary_contact_name"]
    filterset_fields = ["company_id", "category", "grade", "admission_status", "buyer_id"]
    ordering_fields = ["id", "code", "name", "grade", "updated_at"]
    uniqueness_error_map = {"uq_supplier_company_code": "同一公司下供应商编码已存在。"}
    required_permissions = {
        "list": "srm.supplier.view",
        "retrieve": "srm.supplier.view",
        "create": "srm.supplier.create",
        "partial_update": "srm.supplier.update",
        "set_active": "srm.supplier.deactivate",
    }


class SupplierContactViewSet(ActiveFilterMixin, ScopedModelViewSet):
    queryset = SupplierContact.objects.select_related("supplier", "supplier__company").all()
    serializer_class = SupplierContactSerializer
    scope_fields = {"company_field": "supplier__company_id"}
    audit_fields = ("supplier_id", "name", "position", "phone", "email", "is_primary", "is_active")
    search_fields = ["name", "phone", "position"]
    filterset_fields = ["supplier_id", "is_primary"]
    ordering_fields = ["id", "name"]
    uniqueness_error_map = {"uq_supplier_contact_name": "该供应商下已存在同名联系人。"}
    required_permissions = {
        "list": "srm.supplier_contact.view",
        "retrieve": "srm.supplier_contact.view",
        "create": "srm.supplier_contact.create",
        "partial_update": "srm.supplier_contact.update",
        "set_active": "srm.supplier_contact.update",
    }

    def perform_create(self, serializer) -> None:
        super().perform_create(serializer)
        ensure_single_primary_contact(serializer.instance)

    def perform_update(self, serializer) -> None:
        super().perform_update(serializer)
        ensure_single_primary_contact(serializer.instance)


class SupplierQualificationViewSet(ActiveFilterMixin, ScopedModelViewSet):
    queryset = SupplierQualification.objects.select_related("supplier", "supplier__company").all()
    serializer_class = SupplierQualificationSerializer
    scope_fields = {"company_field": "supplier__company_id"}
    audit_fields = (
        "supplier_id", "qualification_type", "certificate_no", "issued_by",
        "issued_date", "expiry_date", "is_active",
    )
    search_fields = ["certificate_no", "issued_by"]
    filterset_fields = ["supplier_id", "qualification_type"]
    ordering_fields = ["id", "expiry_date", "qualification_type"]
    uniqueness_error_map = {"dedup_key": "该供应商下同类型资质已存在相同证书编号。"}
    required_permissions = {
        "list": "srm.supplier_qualification.view",
        "retrieve": "srm.supplier_qualification.view",
        "create": "srm.supplier_qualification.create",
        "partial_update": "srm.supplier_qualification.update",
        "set_active": "srm.supplier_qualification.update",
    }


class SupplierEvaluationWeightViewSet(ActiveFilterMixin, ScopedModelViewSet):
    """五维评价权重配置：只增不改，修改即派生新版本。"""

    queryset = SupplierEvaluationWeight.objects.select_related("company").all()
    serializer_class = SupplierEvaluationWeightSerializer
    scope_fields = {"company_field": "company_id"}
    audit_fields = (
        "version_no", "quality_weight", "technology_weight", "response_weight",
        "delivery_weight", "cost_weight", "is_active",
    )
    search_fields = ["remark"]
    filterset_fields = ["company_id", "is_active"]
    ordering_fields = ["id", "version_no", "created_at"]
    uniqueness_error_map = {
        "uq_srm_eval_weight_company_version": "该公司下的同一权重版本号已存在。",
    }
    required_permissions = {
        "list": "srm.evaluation_weight.view",
        "retrieve": "srm.evaluation_weight.view",
        "create": "srm.evaluation_weight.create",
        "partial_update": "srm.evaluation_weight.update",
        "set_active": "srm.evaluation_weight.update",
    }

    def create(self, request, *args, **kwargs) -> Response:
        payload = EvaluationWeightWriteSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        company = _resolve_company(request.user, request.data.get("company_id"))
        config = services.create_weight_config(
            request.user,
            company=company,
            weights=_weight_values(data),
            remark=data.get("remark", ""),
            activate=data.get("is_active", True),
        )
        assert_in_scope(config, request.user, **self.scope_fields)
        return Response(self.get_serializer(config).data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs) -> Response:
        """修改权重 = 派生新版本：响应体是**新版本**（旧版本保留，供历史评价追溯）。"""
        config = self.get_object()
        assert_version(config, request.data.get("expected_version"))
        payload = EvaluationWeightUpdateSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        derived = services.derive_weight_config(
            request.user,
            config,
            weights=_weight_values(data),
            remark=data.get("remark"),
            # 未显式传 is_active 时沿用旧版本的启停状态，不悄悄把停用版本重新启用
            activate=data.get("is_active", config.is_active),
        )
        return Response(self.get_serializer(derived).data)


class SupplierEvaluationViewSet(ActiveFilterMixin, ScopedModelViewSet):
    """供应商五维量化评价：录入明细 → 生效 → 归档。"""

    queryset = (
        SupplierEvaluation.objects.select_related(
            "company", "supplier", "weight_config", "evaluated_by"
        )
        .prefetch_related("lines")
        .all()
    )
    serializer_class = SupplierEvaluationSerializer
    scope_fields = {"company_field": "company_id"}
    audit_fields = (
        "evaluation_no", "supplier_id", "weight_config_id", "missing_dimension_policy",
        "period_start", "period_end", "evaluated_by_id", "evaluated_at", "status",
        "total_score", "grade", "is_active",
    )
    search_fields = ["evaluation_no", "supplier__code", "supplier__name", "remark"]
    filterset_fields = [
        "company_id", "supplier_id", "status", "grade", "missing_dimension_policy", "is_active",
    ]
    ordering_fields = ["id", "evaluation_no", "evaluated_at", "total_score", "created_at"]
    uniqueness_error_map = {"uq_srm_eval_company_no": "同一公司下评价单号已存在。"}
    required_permissions = {
        "list": "srm.evaluation.view",
        "retrieve": "srm.evaluation.view",
        "create": "srm.evaluation.create",
        "partial_update": "srm.evaluation.update",
        "set_active": "srm.evaluation.update",
        # `lines` 一个 action 同时服务查看（GET）与录入（POST）：写路径在方法内二次校验
        "lines": "srm.evaluation.view",
        "publish": "srm.evaluation.publish",
        "archive": "srm.evaluation.archive",
        "statistics": "srm.evaluation.view",
    }

    def create(self, request, *args, **kwargs) -> Response:
        payload = EvaluationWriteSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        company = _resolve_company(request.user, request.data.get("company_id"))
        config = (
            _resolve_weight_config(data["weight_config_id"], request.user, company)
            if data.get("weight_config_id")
            else None
        )
        evaluation = services.create_evaluation(
            request.user,
            company=company,
            supplier=_resolve_supplier(data["supplier_id"], request.user, company),
            weight_config=config,
            missing_dimension_policy=data.get("missing_dimension_policy")
            or MissingDimensionPolicy.MARK_MISSING,
            period_start=data.get("period_start"),
            period_end=data.get("period_end"),
            evaluated_by=_resolve_employee(data.get("evaluated_by_id"), request.user),
            evaluated_at=data.get("evaluated_at"),
            remark=data.get("remark", ""),
            evaluation_no=data.get("evaluation_no", ""),
        )
        assert_in_scope(evaluation, request.user, **self.scope_fields)
        return Response(self.get_serializer(evaluation).data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs) -> Response:
        """只允许改草稿的表头（期间 / 缺数据口径 / 备注等），明细走 `lines` 动作。"""
        evaluation = self.get_object()
        assert_version(evaluation, request.data.get("expected_version"))
        payload = EvaluationUpdateSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        if not evaluation.is_editable:
            raise StateConflict(
                "只有草稿状态的评价单可以修改；已生效的评价请归档后重新发起。",
                code="EVALUATION_LOCKED",
            )
        for field in ("period_start", "period_end", "remark", "missing_dimension_policy"):
            if field in data:
                setattr(evaluation, field, data[field])
        if (
            ("period_start" in data or "period_end" in data)
            and evaluation.period_start
            and evaluation.period_end
            and evaluation.period_end < evaluation.period_start
        ):
            raise ValidationFailed(
                "评价期间止不得早于评价期间起。", code="INVALID_PERIOD_RANGE"
            )
        evaluation.save()
        # 缺数据口径变了，重算有效权重与总分（口径必须与结果一致）
        if "missing_dimension_policy" in data:
            evaluation = services.recalculate(evaluation)
        return Response(self.get_serializer(evaluation).data)

    @extend_schema(
        request=EvaluationLinesInputSerializer, responses={200: SupplierEvaluationSerializer}
    )
    @action(detail=True, methods=["get", "post"], url_path="lines")
    def lines(self, request, *args, **kwargs) -> Response:
        """查看（GET）或整表替换（POST）评价明细；写操作需要 `srm.evaluation.update`。"""
        evaluation = self.get_object()
        if request.method.lower() == "post":
            require_codes(request.user, "srm.evaluation.update")
            payload = EvaluationLinesInputSerializer(data=request.data)
            payload.is_valid(raise_exception=True)
            evaluation = services.set_evaluation_lines(
                request.user, evaluation, payload.validated_data["lines"]
            )
            return Response(self.get_serializer(evaluation).data)
        lines = evaluation.lines.all().order_by("dimension")
        return Response(SupplierEvaluationLineSerializer(lines, many=True).data)

    @extend_schema(request=None, responses={200: SupplierEvaluationSerializer})
    @action(detail=True, methods=["post"], url_path="publish")
    def publish(self, request, *args, **kwargs) -> Response:
        """生效：草稿 → 已生效。"""
        evaluation = services.publish_evaluation(request.user, self.get_object())
        return Response(self.get_serializer(evaluation).data)

    @extend_schema(request=None, responses={200: SupplierEvaluationSerializer})
    @action(detail=True, methods=["post"], url_path="archive")
    def archive(self, request, *args, **kwargs) -> Response:
        """归档：过时的评价归档而不是删除，保留历史。"""
        evaluation = services.archive_evaluation(request.user, self.get_object())
        return Response(self.get_serializer(evaluation).data)

    @extend_schema(responses={200: dict})
    @action(detail=False, methods=["get"], url_path="statistics")
    def statistics(self, request, *args, **kwargs) -> Response:
        """供应商评价统计（按明细实时聚合，不落汇总表）。"""
        params = request.query_params
        return Response(
            selectors.evaluation_statistics(
                request.user,
                company_id=_int_or_none(params.get("company_id")),
                supplier_id=_int_or_none(params.get("supplier_id")),
                since=params.get("since"),
                until=params.get("until"),
            )
        )


__all__ = [
    "SupplierContactViewSet",
    "SupplierEvaluationViewSet",
    "SupplierEvaluationWeightViewSet",
    "SupplierQualificationViewSet",
    "SupplierViewSet",
]
