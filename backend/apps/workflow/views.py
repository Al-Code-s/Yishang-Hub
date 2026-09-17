"""审批接口。"""

from __future__ import annotations

from django.db import transaction
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.exceptions import ObjectNotFound
from apps.core.models import AuditAction
from apps.core.permissions import HasRequiredPermissions
from apps.core.services import record_audit
from apps.factory.models import Department
from apps.workflow import services
from apps.workflow.models import ApprovalInstance, ApprovalTemplate, ApprovalTemplateNode
from apps.workflow.selectors import (
    my_instances_queryset,
    participated_queryset,
    todo_queryset,
    visible_instances,
)
from apps.workflow.serializers import (
    ApprovalCommentSerializer,
    ApprovalInstanceSerializer,
    ApprovalTemplateSerializer,
    ApprovalTemplateWriteSerializer,
    CreateApprovalInstanceSerializer,
)


class ApprovalTemplateViewSet(viewsets.ModelViewSet):
    queryset = ApprovalTemplate.objects.prefetch_related("nodes", "nodes__approver_role").all()
    serializer_class = ApprovalTemplateSerializer
    permission_classes = [HasRequiredPermissions]
    http_method_names = ["get", "post", "patch", "head", "options"]
    required_permissions = {
        "list": "workflow.template.view",
        "retrieve": "workflow.template.view",
        "create": "workflow.template.create",
        "partial_update": "workflow.template.update",
        "set_active": "workflow.template.update",
    }
    search_fields = ["code", "name", "biz_type"]
    filterset_fields = ["biz_type", "is_active", "company_id"]
    ordering_fields = ["id", "code", "biz_type"]

    def create(self, request, *args, **kwargs):
        serializer = ApprovalTemplateWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        nodes = data.pop("nodes", [])
        with transaction.atomic():
            template = ApprovalTemplate.objects.create(
                code=data["code"],
                name=data["name"],
                biz_type=data["biz_type"],
                company_id=data.get("company_id"),
                allow_self_approval=data.get("allow_self_approval", False),
                description=data.get("description", ""),
                created_by=request.user,
                updated_by=request.user,
            )
            _sync_nodes(template, nodes)
            record_audit(
                action=AuditAction.CREATE,
                instance=template,
                changes={"code": template.code, "name": template.name, "nodes": len(nodes)},
                object_repr=str(template),
            )
        return Response(
            ApprovalTemplateSerializer(template).data, status=status.HTTP_201_CREATED
        )

    def partial_update(self, request, *args, **kwargs):
        template = self.get_object()
        serializer = ApprovalTemplateWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        nodes = data.pop("nodes", None)
        with transaction.atomic():
            for field in ("name", "biz_type", "company_id", "allow_self_approval", "description", "is_active"):
                if field in data:
                    setattr(template, field, data[field])
            template.save()
            if nodes is not None:
                _sync_nodes(template, nodes)
                services.mark_template_changed(request.user, template)
            record_audit(
                action=AuditAction.UPDATE,
                instance=template,
                changes={"nodes_changed": nodes is not None},
                object_repr=str(template),
            )
        return Response(ApprovalTemplateSerializer(template).data)

    @action(detail=True, methods=["post"], url_path="set-active")
    def set_active(self, request, *args, **kwargs):
        template = self.get_object()
        is_active = bool(request.data.get("is_active"))
        template.is_active = is_active
        template.save(update_fields=["is_active", "updated_at"])
        record_audit(
            action=AuditAction.ACTIVATE if is_active else AuditAction.DEACTIVATE,
            instance=template,
            object_repr=str(template),
        )
        return Response(ApprovalTemplateSerializer(template).data)


def _sync_nodes(template: ApprovalTemplate, nodes: list[dict]) -> None:
    """整体替换模板节点，序号不允许重复。"""
    seqs = [node["seq"] for node in nodes]
    if len(seqs) != len(set(seqs)):
        from apps.core.exceptions import ValidationFailed

        raise ValidationFailed("审批节点顺序号不能重复。", code="DUPLICATE_NODE_SEQ")

    template.nodes.all().delete()
    created = []
    for node in nodes:
        created.append(
            ApprovalTemplateNode(
                template=template,
                seq=node["seq"],
                name=node["name"],
                approver_type=node["approver_type"],
                approver_role_id=node.get("approver_role_id"),
                approver_user_id=node.get("approver_user_id"),
                amount_min=node.get("amount_min"),
                amount_max=node.get("amount_max"),
                department_ids=list(node.get("department_ids") or []),
                is_active=node.get("is_active", True),
            )
        )
    if created:
        ApprovalTemplateNode.objects.bulk_create(created)


class ApprovalInstanceViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ApprovalInstance.objects.select_related(
        "template", "applicant", "company", "department"
    ).prefetch_related("steps", "steps__approver_role", "logs")
    serializer_class = ApprovalInstanceSerializer
    permission_classes = [HasRequiredPermissions]
    required_permissions = {
        "list": "workflow.instance.view",
        "retrieve": "workflow.instance.view",
        "create": "workflow.instance.submit",
        "todo": "workflow.instance.view",
        "mine": "workflow.instance.view",
        "participated": "workflow.instance.view",
        "submit": "workflow.instance.submit",
        "approve": "workflow.instance.approve",
        "reject": "workflow.instance.approve",
        "withdraw": "workflow.instance.withdraw",
        "comment": "workflow.instance.view",
        "pending_summary": "workflow.instance.view",
    }
    search_fields = ["biz_no", "title", "summary"]
    filterset_fields = ["status", "biz_type", "template_id"]
    ordering_fields = ["id", "created_at", "submitted_at", "finished_at"]

    def get_queryset(self):
        return visible_instances(self.request.user)

    def _serialize(self, instance) -> Response:
        serializer = ApprovalInstanceSerializer(instance, context={"request": self.request})
        return Response(serializer.data)

    def create(self, request, *args, **kwargs):
        serializer = CreateApprovalInstanceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        department_id = data.pop("department_id", None)
        department = None
        if department_id:
            department = Department.objects.filter(pk=department_id).first()
            if department is None:
                raise ObjectNotFound("部门不存在。", code="DEPARTMENT_NOT_FOUND")
        instance = services.create_instance(
            request.user,
            title=data["title"],
            template_code=data.get("template_code") or None,
            biz_type=data.get("biz_type") or services.GENERIC_BIZ_TYPE,
            biz_id=data.get("biz_id", ""),
            biz_no=data.get("biz_no", ""),
            summary=data.get("summary", ""),
            amount=data.get("amount"),
            department=department,
        )
        return self._serialize(instance)

    @action(detail=False, methods=["get"])
    def todo(self, request, *args, **kwargs):
        queryset = self.filter_queryset(todo_queryset(request.user))
        page = self.paginate_queryset(queryset)
        serializer = ApprovalInstanceSerializer(
            page if page is not None else queryset, many=True, context={"request": request}
        )
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def mine(self, request, *args, **kwargs):
        queryset = self.filter_queryset(my_instances_queryset(request.user))
        page = self.paginate_queryset(queryset)
        serializer = ApprovalInstanceSerializer(
            page if page is not None else queryset, many=True, context={"request": request}
        )
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def participated(self, request, *args, **kwargs):
        queryset = self.filter_queryset(participated_queryset(request.user))
        page = self.paginate_queryset(queryset)
        serializer = ApprovalInstanceSerializer(
            page if page is not None else queryset, many=True, context={"request": request}
        )
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    @action(detail=False, methods=["get"], url_path="pending-summary")
    def pending_summary(self, request, *args, **kwargs):
        return Response({"todo_count": todo_queryset(request.user).count()})

    @action(detail=True, methods=["post"])
    def submit(self, request, *args, **kwargs):
        serializer = ApprovalCommentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = services.submit_instance(
            request.user, self.get_object(), comment=serializer.validated_data["comment"]
        )
        return self._serialize(instance)

    @action(detail=True, methods=["post"])
    def approve(self, request, *args, **kwargs):
        serializer = ApprovalCommentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = services.approve_instance(
            request.user, self.get_object(), comment=serializer.validated_data["comment"]
        )
        return self._serialize(instance)

    @action(detail=True, methods=["post"])
    def reject(self, request, *args, **kwargs):
        serializer = ApprovalCommentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = services.reject_instance(
            request.user, self.get_object(), comment=serializer.validated_data["comment"]
        )
        return self._serialize(instance)

    @action(detail=True, methods=["post"])
    def withdraw(self, request, *args, **kwargs):
        serializer = ApprovalCommentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = services.withdraw_instance(
            request.user, self.get_object(), comment=serializer.validated_data["comment"]
        )
        return self._serialize(instance)

    @action(detail=True, methods=["post"])
    def comment(self, request, *args, **kwargs):
        serializer = ApprovalCommentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.add_comment(
            request.user, self.get_object(), comment=serializer.validated_data["comment"]
        )
        return self._serialize(self.get_object())
