"""公共接口：健康检查、数据字典、编码规则、审计日志、附件。"""

from __future__ import annotations

import hashlib
import logging

from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.http import FileResponse, HttpRequest, JsonResponse
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.exceptions import ObjectNotFound, ValidationFailed
from apps.core.models import Attachment, AuditAction, AuditLog, CodeRule, Dictionary, DictionaryItem
from apps.core.permissions import HasRequiredPermissions
from apps.core.selectors import scoped_queryset
from apps.core.serializers import (
    AttachmentSerializer,
    AttachmentUploadSerializer,
    AuditLogSerializer,
    CodeRulePreviewSerializer,
    CodeRuleSerializer,
    DictionaryItemSerializer,
    DictionarySerializer,
)
from apps.core.services import preview_code, record_audit, snapshot_fields
from apps.core.viewsets import ActiveFilterMixin, ScopedModelViewSet

logger = logging.getLogger("yishang.core")

# 常见文件类型的魔数，用于在扩展名之外做一次基本的内容校验
_MAGIC_SIGNATURES: dict[str, tuple[bytes, ...]] = {
    "pdf": (b"%PDF-",),
    "png": (b"\x89PNG\r\n\x1a\n",),
    "jpg": (b"\xff\xd8\xff",),
    "jpeg": (b"\xff\xd8\xff",),
    "gif": (b"GIF87a", b"GIF89a"),
    "webp": (b"RIFF",),
    "zip": (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"),
    "docx": (b"PK\x03\x04",),
    "xlsx": (b"PK\x03\x04",),
}


def health_live(request: HttpRequest) -> JsonResponse:
    """存活探针：不访问外部依赖。"""
    return JsonResponse(
        {
            "status": "ok",
            "service": "yishang-platform",
            "api_prefix": settings.YISHANG["API_PREFIX"],
            "time": timezone.now().isoformat(),
        }
    )


def health_ready(request: HttpRequest) -> JsonResponse:
    """就绪探针：检查数据库与缓存。任一不可用即返回 503。"""
    checks: dict[str, str] = {}
    ready = True

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        checks["database"] = "ok"
    except Exception as exc:  # noqa: BLE001
        ready = False
        checks["database"] = f"error: {type(exc).__name__}"

    try:
        cache.set("yishang:readyz", "1", timeout=10)
        checks["cache"] = "ok" if cache.get("yishang:readyz") == "1" else "error: mismatch"
        ready = ready and checks["cache"] == "ok"
    except Exception as exc:  # noqa: BLE001
        ready = False
        checks["cache"] = f"error: {type(exc).__name__}"

    return JsonResponse(
        {"status": "ok" if ready else "unavailable", "checks": checks, "time": timezone.now().isoformat()},
        status=200 if ready else 503,
    )


def csrf_failure(request: HttpRequest, reason: str = "") -> JsonResponse:
    """CSRF 校验失败时返回与 API 一致的结构。"""
    from apps.core.logging import get_request_id

    return JsonResponse(
        {
            "code": "CSRF_FAILED",
            "message": "CSRF 校验未通过，请刷新页面后重试。",
            "details": {"reason": reason},
            "request_id": get_request_id(),
        },
        status=403,
    )


class DictionaryViewSet(ActiveFilterMixin, ScopedModelViewSet):
    queryset = Dictionary.objects.prefetch_related("items").all()
    serializer_class = DictionarySerializer
    scope_fields = None  # 字典为全局共享基础数据
    audit_fields = ("code", "name", "is_active", "remark")
    search_fields = ["code", "name"]
    ordering_fields = ["id", "code"]
    uniqueness_error_map = {"code": "字典编码已存在。"}
    required_permissions = {
        "list": "core.dictionary.view",
        "retrieve": "core.dictionary.view",
        "create": "core.dictionary.create",
        "partial_update": "core.dictionary.update",
        "set_active": "core.dictionary.update",
    }


class DictionaryItemViewSet(ActiveFilterMixin, ScopedModelViewSet):
    queryset = DictionaryItem.objects.select_related("dictionary").all()
    serializer_class = DictionaryItemSerializer
    scope_fields = None
    audit_fields = ("dictionary_id", "code", "label", "sort_order", "is_active")
    search_fields = ["code", "label"]
    filterset_fields = ["dictionary_id"]
    ordering_fields = ["id", "sort_order"]
    uniqueness_error_map = {"uq_dictionary_item_code": "同一字典下项编码已存在。"}
    required_permissions = {
        "list": "core.dictionary.view",
        "retrieve": "core.dictionary.view",
        "create": "core.dictionary.create",
        "partial_update": "core.dictionary.update",
        "set_active": "core.dictionary.update",
    }


class CodeRuleViewSet(ActiveFilterMixin, ScopedModelViewSet):
    queryset = CodeRule.objects.all()
    serializer_class = CodeRuleSerializer
    scope_fields = None
    audit_fields = ("code", "name", "pattern", "reset_period", "is_active")
    search_fields = ["code", "name", "pattern"]
    ordering_fields = ["id", "code"]
    uniqueness_error_map = {"code": "规则编码已存在。"}
    required_permissions = {
        "list": "core.code_rule.view",
        "retrieve": "core.code_rule.view",
        "create": "core.code_rule.create",
        "partial_update": "core.code_rule.update",
        "set_active": "core.code_rule.update",
        "preview": "core.code_rule.view",
    }

    @action(detail=False, methods=["post"])
    def preview(self, request, *args, **kwargs):
        """预演编号结果，不消耗流水。"""
        serializer = CodeRulePreviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        code = serializer.validated_data["code"]
        sample = serializer.validated_data["sample"]
        rule = CodeRule.objects.filter(code=code, is_active=True).first()
        if rule is None:
            raise ObjectNotFound("编码规则不存在或已停用。", code="CODE_RULE_NOT_FOUND")
        return Response({"preview": preview_code(code, sample=sample)})


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """审计日志：只读，不允许通过任何普通接口修改或删除。"""

    queryset = AuditLog.objects.select_related("actor", "company").all()
    serializer_class = AuditLogSerializer
    permission_classes = [HasRequiredPermissions]
    required_permissions = {
        "list": "core.audit.view",
        "retrieve": "core.audit.view",
    }
    filterset_fields = ["action", "object_type", "object_id", "actor_id", "request_id"]
    search_fields = ["object_repr", "actor_username", "request_id", "reason"]
    ordering_fields = ["id", "created_at"]

    def get_queryset(self):
        return scoped_queryset(
            super().get_queryset(),
            self.request.user,
            company_field="company_id",
            owner_field="actor_id",
        )


class AttachmentViewSet(viewsets.ModelViewSet):
    """业务附件。默认私有：下载必须通过权限校验，不能靠猜测地址绕过。"""

    queryset = Attachment.objects.select_related("created_by").all()
    serializer_class = AttachmentSerializer
    permission_classes = [HasRequiredPermissions]
    parser_classes = [MultiPartParser, FormParser]
    http_method_names = ["get", "post", "delete", "head", "options"]
    required_permissions = {
        "list": "core.attachment.download",
        "create": "core.attachment.upload",
        "retrieve": "core.attachment.download",
        "destroy": "core.attachment.delete",
        "download": "core.attachment.download",
    }
    filterset_fields = ["biz_type", "biz_id"]
    ordering_fields = ["id", "created_at"]

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser or user.has_permission_codes(["core.attachment.download"]):
            return super().get_queryset()
        # 无下载权限的用户只能看到自己上传的附件
        return Attachment.objects.filter(created_by=user)

    def create(self, request, *args, **kwargs):
        serializer = AttachmentUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        upload = serializer.validated_data["file"]
        _validate_upload(upload)

        content = b""
        for chunk in upload.chunks():
            content += chunk
        digest = hashlib.sha256(content).hexdigest()

        attachment = Attachment.objects.create(
            file=upload,
            original_name=upload.name[:255],
            content_type=getattr(upload, "content_type", "") or "",
            size_bytes=len(content),
            sha256=digest,
            biz_type=serializer.validated_data.get("biz_type", ""),
            biz_id=serializer.validated_data.get("biz_id", ""),
            created_by=request.user,
            updated_by=request.user,
        )
        record_audit(
            action=AuditAction.UPLOAD,
            instance=attachment,
            changes=snapshot_fields(attachment, ("original_name", "size_bytes", "sha256", "biz_type", "biz_id")),
            object_repr=attachment.original_name,
        )
        return Response(AttachmentSerializer(attachment).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"])
    def download(self, request, *args, **kwargs):
        attachment = self.get_object()
        if not _can_download(request.user, attachment):
            from apps.core.exceptions import NotPermitted

            raise NotPermitted("没有下载该附件的权限。", code="ATTACHMENT_FORBIDDEN")
        record_audit(
            action=AuditAction.DOWNLOAD,
            instance=attachment,
            object_repr=attachment.original_name,
        )
        return FileResponse(
            attachment.file.open("rb"),
            as_attachment=True,
            filename=attachment.original_name,
            content_type=attachment.content_type or "application/octet-stream",
        )

    def destroy(self, request, *args, **kwargs):
        attachment = self.get_object()
        record_audit(
            action=AuditAction.DELETE,
            instance=attachment,
            object_repr=attachment.original_name,
            reason=str(request.data.get("reason", "") or ""),
        )
        attachment.file.delete(save=False)
        attachment.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


def _can_download(user, attachment: Attachment) -> bool:
    if user.is_superuser:
        return True
    if attachment.created_by_id == user.pk:
        return True
    return bool(user.has_permission_codes(["core.attachment.download"]))


def _validate_upload(upload) -> None:
    """扩展名白名单 + 大小上限 + 魔数校验，避免仅凭扩展名判断文件类型。"""
    limit = settings.YISHANG["ATTACHMENT_MAX_BYTES"]
    if upload.size and upload.size > limit:
        raise ValidationFailed(
            f"附件大小超过上限（{limit // (1024 * 1024)} MB）。",
            code="ATTACHMENT_TOO_LARGE",
            details={"size": upload.size, "limit": limit},
        )

    name = upload.name or ""
    extension = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    allowed = settings.YISHANG["ATTACHMENT_ALLOWED_EXTENSIONS"]
    if extension not in allowed:
        raise ValidationFailed(
            f"不支持的附件类型：{extension or '未知'}。",
            code="ATTACHMENT_TYPE_NOT_ALLOWED",
            details={"allowed": allowed},
        )

    signatures = _MAGIC_SIGNATURES.get(extension)
    if signatures:
        head = upload.read(16)
        upload.seek(0)
        if not any(head.startswith(signature) for signature in signatures):
            raise ValidationFailed(
                "文件内容与扩展名不匹配，已拒绝上传。",
                code="ATTACHMENT_CONTENT_MISMATCH",
            )

class MetaView(APIView):
    """前端表单用的枚举字典。

    集中暴露后端枚举，避免前端硬编码中文标签与取值。
    """

    permission_classes = [HasRequiredPermissions]
    required_permissions: list[str] = []

    def get(self, request, *args, **kwargs) -> Response:
        from apps.crm.models import CustomerCategory, CustomerLevel, CustomerStatus
        from apps.factory.models import Department, Employee, ProductionLine, Workshop
        from apps.identity.models import DataScopeType, PermissionType
        from apps.masterdata.models import IdentifierType, MaterialCategory, UoM
        from apps.planning.models import (
            BomLineType,
            BomStatus,
            MrpBucket,
            MrpDemandSource,
            MrpRunStatus,
            MrpSuggestionStatus,
            MrpSuggestionType,
            MrpSupplySource,
            RoutingStatus,
        )
        from apps.procurement.models import (
            InspectionResult,
            OrderStatus,
            ReceiptStatus,
            RequisitionStatus,
            RequisitionType,
        )
        from apps.sales.models import (
            OrderPriority,
            ReturnDisposition,
            ReturnStatus,
            SalesOrderStatus,
            ShipmentStatus,
        )
        from apps.srm.models import (
            AdmissionStatus,
            QualificationType,
            SupplierCategory,
            SupplierGrade,
        )
        from apps.wms.models import (
            Direction,
            DocumentStatus,
            DocumentType,
            LocationType,
            QualityStatus,
            ReservationStatus,
            TransactionType,
            WarehouseType,
            ZoneType,
        )
        from apps.workflow.models import ApproverType, InstanceStatus, StepStatus

        return Response(
            {
                "department_types": _choices(Department, "department_type"),
                "workshop_types": _choices(Workshop, "workshop_type"),
                "line_types": _choices(ProductionLine, "line_type"),
                "employee_genders": _choices(Employee, "gender"),
                "employment_types": _choices(Employee, "employment_type"),
                "employee_statuses": _choices(Employee, "status"),
                "material_category_types": _choices(MaterialCategory, "category_type"),
                "uom_categories": _choices(UoM, "category"),
                "warehouse_types": [{"value": v, "label": n} for v, n in WarehouseType.choices],
                "zone_types": [{"value": v, "label": n} for v, n in ZoneType.choices],
                "location_types": [{"value": v, "label": n} for v, n in LocationType.choices],
                "quality_statuses": [{"value": v, "label": n} for v, n in QualityStatus.choices],
                "inventory_document_types": [
                    {"value": v, "label": n} for v, n in DocumentType.choices
                ],
                "inventory_document_statuses": [
                    {"value": v, "label": n} for v, n in DocumentStatus.choices
                ],
                "inventory_transaction_types": [
                    {"value": v, "label": n} for v, n in TransactionType.choices
                ],
                "inventory_directions": [{"value": v, "label": n} for v, n in Direction.choices],
                "identifier_types": [{"value": v, "label": n} for v, n in IdentifierType.choices],
                "requisition_types": [
                    {"value": v, "label": n} for v, n in RequisitionType.choices
                ],
                "requisition_statuses": [
                    {"value": v, "label": n} for v, n in RequisitionStatus.choices
                ],
                "purchase_order_statuses": [
                    {"value": v, "label": n} for v, n in OrderStatus.choices
                ],
                "receipt_statuses": [{"value": v, "label": n} for v, n in ReceiptStatus.choices],
                "bom_statuses": [{"value": v, "label": n} for v, n in BomStatus.choices],
                "routing_statuses": [{"value": v, "label": n} for v, n in RoutingStatus.choices],
                "bom_line_types": [{"value": v, "label": n} for v, n in BomLineType.choices],
                "mrp_run_statuses": [{"value": v, "label": n} for v, n in MrpRunStatus.choices],
                "mrp_buckets": [{"value": v, "label": n} for v, n in MrpBucket.choices],
                "mrp_demand_sources": [
                    {"value": v, "label": n} for v, n in MrpDemandSource.choices
                ],
                "mrp_supply_sources": [
                    {"value": v, "label": n} for v, n in MrpSupplySource.choices
                ],
                "mrp_suggestion_types": [
                    {"value": v, "label": n} for v, n in MrpSuggestionType.choices
                ],
                "mrp_suggestion_statuses": [
                    {"value": v, "label": n} for v, n in MrpSuggestionStatus.choices
                ],
                "sales_order_statuses": [
                    {"value": v, "label": n} for v, n in SalesOrderStatus.choices
                ],
                "sales_order_priorities": [
                    {"value": v, "label": n} for v, n in OrderPriority.choices
                ],
                "shipment_statuses": [{"value": v, "label": n} for v, n in ShipmentStatus.choices],
                "return_statuses": [{"value": v, "label": n} for v, n in ReturnStatus.choices],
                "return_dispositions": [
                    {"value": v, "label": n} for v, n in ReturnDisposition.choices
                ],
                "reservation_statuses": [
                    {"value": v, "label": n} for v, n in ReservationStatus.choices
                ],
                "inspection_results": [
                    {"value": v, "label": n} for v, n in InspectionResult.choices
                ],
                "customer_categories": [{"value": v, "label": n} for v, n in CustomerCategory.choices],
                "customer_levels": [{"value": v, "label": n} for v, n in CustomerLevel.choices],
                "customer_statuses": [{"value": v, "label": n} for v, n in CustomerStatus.choices],
                "supplier_categories": [{"value": v, "label": n} for v, n in SupplierCategory.choices],
                "supplier_grades": [{"value": v, "label": n} for v, n in SupplierGrade.choices],
                "admission_statuses": [{"value": v, "label": n} for v, n in AdmissionStatus.choices],
                "qualification_types": [{"value": v, "label": n} for v, n in QualificationType.choices],
                "data_scope_types": [{"value": v, "label": n} for v, n in DataScopeType.choices],
                "permission_types": [{"value": v, "label": n} for v, n in PermissionType.choices],
                "approver_types": [{"value": v, "label": n} for v, n in ApproverType.choices],
                "approval_statuses": [{"value": v, "label": n} for v, n in InstanceStatus.choices],
                "approval_step_statuses": [{"value": v, "label": n} for v, n in StepStatus.choices],
            }
        )


def _choices(model, field_name: str) -> list[dict[str, str]]:
    field = model._meta.get_field(field_name)
    return [{"value": value, "label": label} for value, label in (field.choices or [])]
