"""质量管理接口：检验项目、检验单（含结果录入与判定）、质量报警、质量问题知识库。"""

from __future__ import annotations

from typing import Any

from drf_spectacular.utils import extend_schema
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.exceptions import ValidationFailed
from apps.core.models import AuditAction
from apps.core.permissions import require_codes
from apps.core.services import record_audit
from apps.core.viewsets import ActiveFilterMixin, ScopedModelViewSet
from apps.qms import selectors, services
from apps.qms.models import (
    QualityAlert,
    QualityInspectionItem,
    QualityInspectionOrder,
    QualityIssue,
)
from apps.qms.serializers import (
    AlertCloseSerializer,
    AlertHandleSerializer,
    CreateIssueFromAlertSerializer,
    InspectionResultsInputSerializer,
    OrderJudgeSerializer,
    QualityAlertSerializer,
    QualityInspectionItemSerializer,
    QualityInspectionOrderSerializer,
    QualityIssueSerializer,
)


def _int_or_none(value: Any) -> int | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return int(text)
    except ValueError as exc:
        raise ValidationFailed(f"参数应为整数：{value}。", code="INVALID_QUERY_PARAM") from exc


class QualityInspectionItemViewSet(ActiveFilterMixin, ScopedModelViewSet):
    """检验项目：判定口径的唯一来源。"""

    queryset = QualityInspectionItem.objects.select_related("company").all()
    serializer_class = QualityInspectionItemSerializer
    scope_fields = {"company_field": "company_id"}
    audit_fields = (
        "code", "name", "category", "value_type", "unit", "method", "standard_text",
        "lower_limit", "upper_limit", "is_active",
    )
    search_fields = ["code", "name", "method", "standard_text"]
    filterset_fields = ["company_id", "category", "value_type", "is_active"]
    ordering_fields = ["id", "code", "name", "category"]
    uniqueness_error_map = {"uq_qms_item_company_code": "同一公司下项目编码已存在。"}
    required_permissions = {
        "list": "qms.inspection_item.view",
        "retrieve": "qms.inspection_item.view",
        "create": "qms.inspection_item.create",
        "partial_update": "qms.inspection_item.update",
        "set_active": "qms.inspection_item.update",
    }

    def perform_create(self, serializer) -> None:
        data = serializer.validated_data
        data["code"] = str(data.get("code") or "").strip() or services.next_item_code()
        super().perform_create(serializer)


class QualityInspectionOrderViewSet(ActiveFilterMixin, ScopedModelViewSet):
    """检验单：结果录入 → 提交 → 判定 → 关闭。状态只能由动作接口推进。"""

    queryset = QualityInspectionOrder.objects.select_related(
        "company", "material", "supplier", "workshop", "production_line", "equipment",
        "inspector",
    ).prefetch_related("results__item").all()
    serializer_class = QualityInspectionOrderSerializer
    scope_fields = {"company_field": "company_id"}
    audit_fields = (
        "order_no", "inspection_type", "source_no", "material_id", "batch_no", "supplier_id",
        "workshop_id", "production_line_id", "equipment_id", "quantity", "sample_quantity",
        "unit", "inspector_id", "inspected_at",
    )
    search_fields = ["order_no", "source_no", "batch_no", "product_desc", "material__code",
                     "material__name"]
    filterset_fields = [
        "company_id", "inspection_type", "status", "judgement", "material_id", "supplier_id",
        "batch_no", "is_active",
    ]
    ordering_fields = ["id", "order_no", "inspected_at", "judged_at", "created_at"]
    uniqueness_error_map = {"uq_qms_order_company_no": "同一公司下检验单号已存在。"}
    required_permissions = {
        "list": "qms.inspection.view",
        "retrieve": "qms.inspection.view",
        "create": "qms.inspection.create",
        "partial_update": "qms.inspection.update",
        "set_active": "qms.inspection.update",
        # ``results`` 一个 action 同时服务查看（GET）与录入（POST）：
        # 权限按 ``self.action`` 解析，同一个 action 只能声明一份编码，
        # 因此写路径在方法内部用 require_codes 做二次校验（权限矩阵第二层）。
        "results": "qms.inspection.view",
        "submit": "qms.inspection.submit",
        "judge": "qms.inspection.judge",
        "close": "qms.inspection.close",
        "statistics": "qms.inspection.view",
    }

    def perform_create(self, serializer) -> None:
        data = serializer.validated_data
        data["order_no"] = str(data.get("order_no") or "").strip() or services.next_order_no()
        super().perform_create(serializer)

    @extend_schema(responses={200: dict})
    @action(detail=False, methods=["get"], url_path="statistics")
    def statistics(self, request, *args, **kwargs) -> Response:
        """质量信息动态监测：单据量、合格率、分布与未关闭报警（按明细实时聚合）。"""
        params = request.query_params
        return Response(
            selectors.inspection_statistics(
                request.user,
                since=params.get("since"),
                until=params.get("until"),
                company_id=_int_or_none(params.get("company_id")),
                inspection_type=params.get("inspection_type") or None,
            )
        )

    @extend_schema(responses={200: QualityInspectionOrderSerializer})
    @action(detail=True, methods=["get", "post"], url_path="results")
    def results(self, request, *args, **kwargs) -> Response:
        """查看（GET）或录入 / 覆盖（POST）检验结果。

        写操作走 POST：平台视图只允许 get / post / patch（``apps/core/viewsets.py``）。
        录入时定量项目的合格与否由服务层按项目上下限判定，客户端传的结论不生效。
        """
        order = self.get_object()
        if request.method == "POST":
            require_codes(request.user, "qms.inspection.update")
            payload = InspectionResultsInputSerializer(data=request.data)
            payload.is_valid(raise_exception=True)
            saved = services.record_results(order, payload.validated_data["results"])
            record_audit(
                action=AuditAction.UPDATE,
                instance=order,
                changes={"results": len(saved)},
                object_repr=order.order_no,
            )
            # record_results 新建 / 覆盖了明细行，get_object() 的 prefetch 缓存已经过期，
            # 直接序列化会把旧结果（往往为空）返回给前端，这里重新取一次对象。
            order = self.get_queryset().get(pk=order.pk)
        return Response(self.get_serializer(order).data)

    @extend_schema(request=None, responses={200: QualityInspectionOrderSerializer})
    @action(detail=True, methods=["post"], url_path="submit")
    def submit(self, request, *args, **kwargs) -> Response:
        """提交检验单：草稿 → 已提交（没有检验结果不允许提交）。"""
        order = self.get_object()
        updated = services.submit_order(order)
        record_audit(
            action=AuditAction.SUBMIT,
            instance=updated,
            changes={"status": updated.status},
            object_repr=updated.order_no,
        )
        return Response(self.get_serializer(updated).data)

    @extend_schema(request=OrderJudgeSerializer, responses={200: QualityInspectionOrderSerializer})
    @action(detail=True, methods=["post"], url_path="judge")
    def judge(self, request, *args, **kwargs) -> Response:
        """判定检验单：已提交 → 已判定。存在不合格项时自动生成质量报警。"""
        order = self.get_object()
        payload = OrderJudgeSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        updated, alert = services.judge_order(
            order,
            judgement=data.get("judgement") or None,
            judge_remark=data.get("judge_remark") or "",
            inspector=data.get("inspector_id"),
            inspected_at=data.get("inspected_at"),
        )
        record_audit(
            action=AuditAction.APPROVE if updated.judgement != "failed" else AuditAction.REJECT,
            instance=updated,
            changes={"judgement": updated.judgement, "status": updated.status},
            reason=updated.judge_remark,
            object_repr=updated.order_no,
        )
        body = dict(self.get_serializer(updated).data)
        body["alert_id"] = alert.pk if alert is not None else None
        body["alert_no"] = alert.alert_no if alert is not None else ""
        return Response(body)

    @extend_schema(request=None, responses={200: QualityInspectionOrderSerializer})
    @action(detail=True, methods=["post"], url_path="close")
    def close(self, request, *args, **kwargs) -> Response:
        """关闭检验单：已判定 → 已关闭（不合格报警未闭环时拒绝）。"""
        order = self.get_object()
        updated = services.close_order(order)
        record_audit(
            action=AuditAction.UPDATE,
            instance=updated,
            changes={"status": updated.status},
            object_repr=updated.order_no,
        )
        return Response(self.get_serializer(updated).data)


class QualityAlertViewSet(ScopedModelViewSet):
    """质量报警：由判定不合格自动生成，处理走动作接口。"""

    queryset = QualityAlert.objects.select_related(
        "company", "order", "material", "handler"
    ).all()
    serializer_class = QualityAlertSerializer
    scope_fields = {"company_field": "company_id"}
    audit_fields = ("alert_no", "level", "status", "title", "batch_no")
    search_fields = ["alert_no", "title", "description", "batch_no", "order__order_no"]
    filterset_fields = ["company_id", "level", "status", "order_id", "material_id"]
    ordering_fields = ["id", "alert_no", "level", "created_at"]
    uniqueness_error_map = {"uq_qms_alert_company_no": "报警编号已存在。"}
    required_permissions = {
        "list": "qms.alert.view",
        "retrieve": "qms.alert.view",
        "create": "qms.alert.handle",
        "partial_update": "qms.alert.handle",
        "handle": "qms.alert.handle",
        "close": "qms.alert.close",
        "create_issue": "qms.issue.create",
    }

    def perform_create(self, serializer) -> None:
        data = serializer.validated_data
        data["alert_no"] = str(data.get("alert_no") or "").strip() or services.next_alert_no()
        super().perform_create(serializer)

    @extend_schema(request=AlertHandleSerializer, responses={200: QualityAlertSerializer})
    @action(detail=True, methods=["post"], url_path="handle")
    def handle(self, request, *args, **kwargs) -> Response:
        """开始处理：待处理 → 处理中。"""
        alert = self.get_object()
        payload = AlertHandleSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        updated = services.handle_alert(alert, handler=payload.validated_data.get("handler_id"))
        record_audit(
            action=AuditAction.UPDATE,
            instance=updated,
            changes={"status": updated.status},
            object_repr=updated.alert_no,
        )
        return Response(self.get_serializer(updated).data)

    @extend_schema(request=AlertCloseSerializer, responses={200: QualityAlertSerializer})
    @action(detail=True, methods=["post"], url_path="close")
    def close(self, request, *args, **kwargs) -> Response:
        """关闭质量报警：必须写清处理说明。"""
        alert = self.get_object()
        payload = AlertCloseSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        updated = services.close_alert(alert, remark=payload.validated_data["remark"])
        record_audit(
            action=AuditAction.UPDATE,
            instance=updated,
            changes={"status": updated.status},
            reason=updated.close_remark,
            object_repr=updated.alert_no,
        )
        return Response(self.get_serializer(updated).data)

    @extend_schema(request=CreateIssueFromAlertSerializer, responses={201: QualityIssueSerializer})
    @action(detail=True, methods=["post"], url_path="create-issue")
    def create_issue(self, request, *args, **kwargs) -> Response:
        """把这次报警沉淀成知识库条目（草稿），保留来源链路。"""
        alert = self.get_object()
        payload = CreateIssueFromAlertSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        issue = services.create_issue_from_alert(
            alert,
            title=data["title"],
            category=data.get("category") or "other",
            cause=data.get("cause") or "",
            corrective_action=data.get("corrective_action") or "",
            preventive_action=data.get("preventive_action") or "",
            severity=data.get("severity") or None,
            tags=data.get("tags") or [],
        )
        record_audit(
            action=AuditAction.CREATE,
            instance=issue,
            changes={"issue_no": issue.issue_no, "source_alert": alert.alert_no},
            object_repr=str(issue),
        )
        return Response(QualityIssueSerializer(issue).data, status=201)


class QualityIssueViewSet(ActiveFilterMixin, ScopedModelViewSet):
    """产品质量问题知识库：登记 → 发布 → 归档。"""

    queryset = QualityIssue.objects.select_related(
        "company", "material", "source_order", "source_alert"
    ).all()
    serializer_class = QualityIssueSerializer
    scope_fields = {"company_field": "company_id"}
    audit_fields = (
        "issue_no", "title", "category", "severity", "phenomenon", "cause",
        "corrective_action", "preventive_action", "material_id", "status", "is_active",
    )
    search_fields = ["issue_no", "title", "phenomenon", "cause", "product_desc"]
    filterset_fields = ["company_id", "category", "severity", "status", "material_id", "is_active"]
    ordering_fields = ["id", "issue_no", "severity", "published_at", "created_at"]
    uniqueness_error_map = {"uq_qms_issue_company_no": "同一公司下问题编号已存在。"}
    required_permissions = {
        "list": "qms.issue.view",
        "retrieve": "qms.issue.view",
        "create": "qms.issue.create",
        "partial_update": "qms.issue.update",
        "set_active": "qms.issue.update",
        "publish": "qms.issue.publish",
        "archive": "qms.issue.archive",
    }

    def perform_create(self, serializer) -> None:
        data = serializer.validated_data
        data["issue_no"] = str(data.get("issue_no") or "").strip() or services.next_issue_no()
        super().perform_create(serializer)

    @extend_schema(request=None, responses={200: QualityIssueSerializer})
    @action(detail=True, methods=["post"], url_path="publish")
    def publish(self, request, *args, **kwargs) -> Response:
        """发布：草稿 → 已发布。"""
        issue = self.get_object()
        updated = services.publish_issue(issue)
        record_audit(
            action=AuditAction.UPDATE,
            instance=updated,
            changes={"status": updated.status},
            object_repr=str(updated),
        )
        return Response(self.get_serializer(updated).data)

    @extend_schema(request=None, responses={200: QualityIssueSerializer})
    @action(detail=True, methods=["post"], url_path="archive")
    def archive(self, request, *args, **kwargs) -> Response:
        """归档：过时条目归档而不是删除，保留历史。"""
        issue = self.get_object()
        updated = services.archive_issue(issue)
        record_audit(
            action=AuditAction.UPDATE,
            instance=updated,
            changes={"status": updated.status},
            object_repr=str(updated),
        )
        return Response(self.get_serializer(updated).data)


__all__ = [
    "QualityAlertViewSet",
    "QualityInspectionItemViewSet",
    "QualityInspectionOrderViewSet",
    "QualityIssueViewSet",
]
