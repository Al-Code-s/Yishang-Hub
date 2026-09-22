"""客户主数据接口。

客户归属公司，按数据范围过滤；联系人通过 `customer__company_id` 继承同一范围，
避免出现「看不到客户、却能看到其联系人」的越权读取。

客户投诉与产品评价同样按公司收敛范围，状态只能通过动作接口推进：

* 投诉：``accept``（受理）→ ``resolve``（登记处理结果）→ ``close``（关闭）；
* 评价：``reply``（回复）→ ``close``（关闭）。

跳步或重复推进由服务层拒绝（409），不会静默改状态。
"""

from __future__ import annotations

from typing import Any

from drf_spectacular.utils import extend_schema
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.viewsets import ActiveFilterMixin, ScopedModelViewSet
from apps.crm import selectors, services
from apps.crm.models import Customer, CustomerComplaint, CustomerContact, ProductReview
from apps.crm.serializers import (
    ComplaintAcceptSerializer,
    ComplaintCloseSerializer,
    ComplaintResolveSerializer,
    CustomerComplaintSerializer,
    CustomerContactSerializer,
    CustomerSerializer,
    ProductReviewSerializer,
    ReviewCloseSerializer,
    ReviewReplySerializer,
)
from apps.crm.services import ensure_single_primary_contact, next_customer_code


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


class CrmScopedViewSet(ActiveFilterMixin, ScopedModelViewSet):
    """客户管理通用视图基类：按所属公司收敛数据范围。"""

    scope_fields = {"company_field": "company_id"}


class CustomerViewSet(ActiveFilterMixin, ScopedModelViewSet):
    queryset = Customer.objects.select_related("company", "salesman").all()
    serializer_class = CustomerSerializer
    scope_fields = {"company_field": "company_id"}
    audit_fields = (
        "code", "name", "short_name", "category", "level", "status",
        "credit_limit", "payment_terms", "salesman_id", "is_active",
    )
    search_fields = ["code", "name", "short_name", "primary_contact_name"]
    filterset_fields = ["company_id", "category", "level", "status", "salesman_id"]
    ordering_fields = ["id", "code", "name", "level", "updated_at"]
    uniqueness_error_map = {"uq_customer_company_code": "同一公司下客户编码已存在。"}
    required_permissions = {
        "list": "crm.customer.view",
        "retrieve": "crm.customer.view",
        "create": "crm.customer.create",
        "partial_update": "crm.customer.update",
        "set_active": "crm.customer.deactivate",
    }

    def perform_create(self, serializer) -> None:
        """客户编码留空时自动取号。

        规则见 `apps/core/management/commands/bootstrap_system.py::CODE_RULES` 的
        `CUS`（默认 `CUS{YYYY}{SEQ:4}`、按年重置），可在「系统管理 → 编码规则」调整。
        显式传入的编码仍然保留，便于历史数据迁移与外部系统对齐。
        取号发生在 `ScopedModelViewSet.create()` 的 `transaction.atomic()` 内，
        与客户落库同事务：取号成功但客户写入失败时流水会一并回滚。
        """
        code = str(serializer.validated_data.get("code") or "").strip()
        serializer.validated_data["code"] = code or next_customer_code()
        super().perform_create(serializer)


class CustomerContactViewSet(ActiveFilterMixin, ScopedModelViewSet):
    queryset = CustomerContact.objects.select_related("customer", "customer__company").all()
    serializer_class = CustomerContactSerializer
    scope_fields = {"company_field": "customer__company_id"}
    audit_fields = ("customer_id", "name", "position", "phone", "email", "is_primary", "is_active")
    search_fields = ["name", "phone", "position"]
    filterset_fields = ["customer_id", "is_primary"]
    ordering_fields = ["id", "name"]
    uniqueness_error_map = {"uq_customer_contact_name": "该客户下已存在同名联系人。"}
    required_permissions = {
        "list": "crm.customer_contact.view",
        "retrieve": "crm.customer_contact.view",
        "create": "crm.customer_contact.create",
        "partial_update": "crm.customer_contact.update",
        "set_active": "crm.customer_contact.update",
    }

    def perform_create(self, serializer) -> None:
        super().perform_create(serializer)
        ensure_single_primary_contact(serializer.instance)

    def perform_update(self, serializer) -> None:
        super().perform_update(serializer)
        ensure_single_primary_contact(serializer.instance)


class CustomerComplaintViewSet(CrmScopedViewSet):
    queryset = CustomerComplaint.objects.select_related(
        "company", "customer", "receiver", "handler"
    ).all()
    serializer_class = CustomerComplaintSerializer
    audit_fields = (
        "complaint_no", "customer_id", "complaint_type", "level", "status", "source",
        "title", "complained_at", "receiver_id", "handler_id", "satisfaction",
    )
    search_fields = ["complaint_no", "title", "content", "customer__name"]
    filterset_fields = ["company_id", "customer_id", "complaint_type", "level", "status"]
    ordering_fields = ["id", "complaint_no", "complained_at", "resolved_at", "level"]
    uniqueness_error_map = {"uq_customer_complaint_company_no": "同一公司下投诉编号已存在。"}
    required_permissions = {
        "list": "crm.complaint.view",
        "retrieve": "crm.complaint.view",
        "create": "crm.complaint.create",
        "partial_update": "crm.complaint.update",
        "accept": "crm.complaint.handle",
        "resolve": "crm.complaint.handle",
        "close": "crm.complaint.close",
        "statistics": "crm.complaint.view",
    }

    def perform_create(self, serializer) -> None:
        data = serializer.validated_data
        data["complaint_no"] = (
            str(data.get("complaint_no") or "").strip() or services.next_complaint_no()
        )
        super().perform_create(serializer)

    @extend_schema(responses={200: dict})
    @action(detail=False, methods=["get"], url_path="statistics")
    def statistics(self, request, *args, **kwargs) -> Response:
        """投诉统计（只读聚合，不落汇总表）。

        平均满意度只按**已回访**的投诉计算，未回访的条数单独返回（``unrated_total``），
        不会用 0 分把平均值拉低。
        """
        params = request.query_params
        return Response(
            selectors.complaint_statistics(
                request.user,
                since=params.get("since"),
                until=params.get("until"),
                company_id=_int_or_none(params.get("company_id")),
                customer_id=_int_or_none(params.get("customer_id")),
            )
        )

    @extend_schema(request=ComplaintAcceptSerializer, responses={200: CustomerComplaintSerializer})
    @action(detail=True, methods=["post"], url_path="accept")
    def accept(self, request, *args, **kwargs) -> Response:
        """受理投诉：待受理 → 处理中。"""
        complaint = self.get_object()
        payload = ComplaintAcceptSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        updated = services.accept_complaint(
            complaint,
            receiver=payload.validated_data.get("receiver_id"),
            handler=payload.validated_data.get("handler_id"),
            measure=payload.validated_data.get("measure", ""),
        )
        return Response(self.get_serializer(updated).data)

    @extend_schema(request=ComplaintResolveSerializer, responses={200: CustomerComplaintSerializer})
    @action(detail=True, methods=["post"], url_path="resolve")
    def resolve(self, request, *args, **kwargs) -> Response:
        """登记处理结果：处理中 → 已解决。"""
        complaint = self.get_object()
        payload = ComplaintResolveSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        updated = services.resolve_complaint(
            complaint,
            measure=payload.validated_data["measure"],
            handler=payload.validated_data.get("handler_id"),
            satisfaction=payload.validated_data.get("satisfaction"),
        )
        return Response(self.get_serializer(updated).data)

    @extend_schema(request=ComplaintCloseSerializer, responses={200: CustomerComplaintSerializer})
    @action(detail=True, methods=["post"], url_path="close")
    def close(self, request, *args, **kwargs) -> Response:
        """关闭投诉：已解决 → 已关闭。"""
        complaint = self.get_object()
        payload = ComplaintCloseSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        updated = services.close_complaint(complaint, note=payload.validated_data.get("note", ""))
        return Response(self.get_serializer(updated).data)


class ProductReviewViewSet(CrmScopedViewSet):
    queryset = ProductReview.objects.select_related("company", "customer", "sku", "replier").all()
    serializer_class = ProductReviewSerializer
    audit_fields = (
        "review_no", "customer_id", "sku_id", "product_desc", "score", "status",
        "reviewed_at", "replier_id",
    )
    search_fields = ["review_no", "product_desc", "content", "customer__name"]
    filterset_fields = ["company_id", "customer_id", "sku_id", "status", "score"]
    ordering_fields = ["id", "review_no", "reviewed_at", "score"]
    uniqueness_error_map = {"uq_product_review_company_no": "同一公司下评价编号已存在。"}
    required_permissions = {
        "list": "crm.product_review.view",
        "retrieve": "crm.product_review.view",
        "create": "crm.product_review.create",
        "partial_update": "crm.product_review.update",
        "reply": "crm.product_review.reply",
        "close": "crm.product_review.close",
        "statistics": "crm.product_review.view",
    }

    def perform_create(self, serializer) -> None:
        data = serializer.validated_data
        data["review_no"] = str(data.get("review_no") or "").strip() or services.next_review_no()
        super().perform_create(serializer)

    @extend_schema(responses={200: dict})
    @action(detail=False, methods=["get"], url_path="statistics")
    def statistics(self, request, *args, **kwargs) -> Response:
        """评价统计（只读聚合）：平均评分、评分分布与好评率（4 分及以上为好评）。"""
        params = request.query_params
        return Response(
            selectors.product_review_statistics(
                request.user,
                since=params.get("since"),
                until=params.get("until"),
                company_id=_int_or_none(params.get("company_id")),
                customer_id=_int_or_none(params.get("customer_id")),
            )
        )

    @extend_schema(request=ReviewReplySerializer, responses={200: ProductReviewSerializer})
    @action(detail=True, methods=["post"], url_path="reply")
    def reply(self, request, *args, **kwargs) -> Response:
        """回复评价：待回复 → 已回复。"""
        review = self.get_object()
        payload = ReviewReplySerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        updated = services.reply_product_review(
            review,
            reply=payload.validated_data["reply"],
            replier=payload.validated_data.get("replier_id"),
        )
        return Response(self.get_serializer(updated).data)

    @extend_schema(request=ReviewCloseSerializer, responses={200: ProductReviewSerializer})
    @action(detail=True, methods=["post"], url_path="close")
    def close(self, request, *args, **kwargs) -> Response:
        """关闭评价：已回复 → 已关闭。"""
        review = self.get_object()
        payload = ReviewCloseSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        updated = services.close_product_review(review, note=payload.validated_data.get("note", ""))
        return Response(self.get_serializer(updated).data)
