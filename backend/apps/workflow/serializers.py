from __future__ import annotations

from rest_framework import serializers

from apps.core.serializers import ReferenceIdSerializer
from apps.workflow.models import (
    ApprovalInstance,
    ApprovalLog,
    ApprovalStep,
    ApprovalTemplate,
    ApprovalTemplateNode,
)


class ApprovalTemplateNodeSerializer(ReferenceIdSerializer):
    approver_role_name = serializers.SerializerMethodField()
    approver_user_name = serializers.SerializerMethodField()

    class Meta:
        model = ApprovalTemplateNode
        fields = (
            "id", "template_id", "seq", "name", "approver_type", "approver_role_id",
            "approver_role_name", "approver_user_id", "approver_user_name", "amount_min",
            "amount_max", "department_ids", "is_active",
        )
        read_only_fields = ("id", "approver_role_name", "approver_user_name")

    def get_approver_role_name(self, obj: ApprovalTemplateNode) -> str:
        return obj.approver_role.name if obj.approver_role_id else ""

    def get_approver_user_name(self, obj: ApprovalTemplateNode) -> str:
        if not obj.approver_user_id:
            return ""
        return obj.approver_user.display_name or obj.approver_user.username

    def validate(self, attrs):
        approver_type = attrs.get("approver_type", getattr(self.instance, "approver_type", "role"))
        role = attrs.get("approver_role", getattr(self.instance, "approver_role", None))
        user = attrs.get("approver_user", getattr(self.instance, "approver_user", None))
        if approver_type == "role" and role is None:
            raise serializers.ValidationError({"approver_role_id": "按角色审批时必须指定角色。"})
        if approver_type == "user" and user is None:
            raise serializers.ValidationError({"approver_user_id": "指定人员审批时必须选择人员。"})
        amount_min = attrs.get("amount_min", getattr(self.instance, "amount_min", None))
        amount_max = attrs.get("amount_max", getattr(self.instance, "amount_max", None))
        if amount_min is not None and amount_max is not None and amount_min > amount_max:
            raise serializers.ValidationError({"amount_min": "金额下限不能大于上限。"})
        return attrs


class ApprovalTemplateNodeWriteSerializer(serializers.Serializer):
    seq = serializers.IntegerField(min_value=1)
    name = serializers.CharField(max_length=64)
    approver_type = serializers.ChoiceField(choices=["role", "user"])
    approver_role_id = serializers.IntegerField(required=False, allow_null=True)
    approver_user_id = serializers.IntegerField(required=False, allow_null=True)
    amount_min = serializers.DecimalField(max_digits=20, decimal_places=4, required=False, allow_null=True)
    amount_max = serializers.DecimalField(max_digits=20, decimal_places=4, required=False, allow_null=True)
    department_ids = serializers.ListField(child=serializers.IntegerField(), required=False, default=list)
    is_active = serializers.BooleanField(required=False, default=True)


class ApprovalTemplateSerializer(ReferenceIdSerializer):
    nodes = ApprovalTemplateNodeSerializer(many=True, read_only=True)
    company_name = serializers.SerializerMethodField()

    class Meta:
        model = ApprovalTemplate
        fields = (
            "id", "code", "name", "biz_type", "company_id", "company_name",
            "allow_self_approval", "version_no", "description", "is_active", "nodes",
            "version", "created_at", "updated_at",
        )
        read_only_fields = (
            "id", "company_name", "version_no", "nodes", "version", "created_at", "updated_at",
        )

    def get_company_name(self, obj: ApprovalTemplate) -> str:
        return obj.company.name if obj.company_id else ""


class ApprovalTemplateWriteSerializer(serializers.Serializer):
    code = serializers.RegexField(r"^[A-Za-z][A-Za-z0-9_]*$", max_length=64, required=False)
    name = serializers.CharField(max_length=128, required=False)
    biz_type = serializers.CharField(max_length=64, required=False)
    company_id = serializers.IntegerField(required=False, allow_null=True)
    allow_self_approval = serializers.BooleanField(required=False)
    description = serializers.CharField(required=False, allow_blank=True)
    is_active = serializers.BooleanField(required=False)
    nodes = ApprovalTemplateNodeWriteSerializer(many=True, required=False)


class ApprovalStepSerializer(ReferenceIdSerializer):
    approver_role_name = serializers.SerializerMethodField()
    assigned_user_name = serializers.SerializerMethodField()
    decided_by_name = serializers.SerializerMethodField()
    candidate_user_ids = serializers.SerializerMethodField()

    class Meta:
        model = ApprovalStep
        fields = (
            "id", "seq", "name", "approver_type", "approver_role_id", "approver_role_name",
            "assigned_user_id", "assigned_user_name", "candidate_user_ids", "status",
            "decided_by_id", "decided_by_name", "decided_at", "decision", "comment",
        )
        read_only_fields = fields

    def get_approver_role_name(self, obj: ApprovalStep) -> str:
        return obj.approver_role.name if obj.approver_role_id else ""

    def get_assigned_user_name(self, obj: ApprovalStep) -> str:
        if not obj.assigned_user_id:
            return ""
        return obj.assigned_user.display_name or obj.assigned_user.username

    def get_decided_by_name(self, obj: ApprovalStep) -> str:
        if not obj.decided_by_id:
            return ""
        return obj.decided_by.display_name or obj.decided_by.username

    def get_candidate_user_ids(self, obj: ApprovalStep) -> list[int]:
        return obj.candidate_user_ids()


class ApprovalLogSerializer(ReferenceIdSerializer):
    action_display = serializers.CharField(source="get_action_display", read_only=True)

    class Meta:
        model = ApprovalLog
        fields = ("id", "seq", "action", "action_display", "actor_id", "actor_name", "comment", "created_at")
        read_only_fields = fields


class ApprovalInstanceSerializer(ReferenceIdSerializer):
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    applicant_name = serializers.SerializerMethodField()
    current_step_name = serializers.SerializerMethodField()
    template_name = serializers.CharField(source="template.name", read_only=True, default="")
    steps = ApprovalStepSerializer(many=True, read_only=True)
    logs = ApprovalLogSerializer(many=True, read_only=True)
    can_approve = serializers.SerializerMethodField()
    can_withdraw = serializers.SerializerMethodField()

    class Meta:
        model = ApprovalInstance
        fields = (
            "id", "biz_no", "title", "summary", "biz_type", "biz_id", "template_id",
            "template_name", "template_version", "applicant_id", "applicant_name",
            "company_id", "department_id", "amount", "status", "status_display",
            "current_seq", "current_step_name", "steps", "logs", "can_approve",
            "can_withdraw", "submitted_at", "finished_at", "version", "created_at", "updated_at",
        )
        read_only_fields = fields

    def get_applicant_name(self, obj: ApprovalInstance) -> str:
        if not obj.applicant_id:
            return ""
        return obj.applicant.display_name or obj.applicant.username

    def get_current_step_name(self, obj: ApprovalInstance) -> str:
        step = obj.current_step
        return step.name if step is not None else ""

    def _current_step(self, obj: ApprovalInstance) -> ApprovalStep | None:
        step = obj.current_step
        return step if step is not None and step.status == "pending" else None

    def get_can_approve(self, obj: ApprovalInstance) -> bool:
        request = self.context.get("request")
        if request is None or not request.user.is_authenticated:
            return False
        step = self._current_step(obj)
        if step is None:
            return False
        user = request.user
        if user.pk not in set(step.candidate_user_ids()):
            return False
        if user.pk == obj.applicant_id and not obj.template.allow_self_approval:
            return False
        return bool(user.is_superuser or user.has_permission_codes(["workflow.instance.approve"]))

    def get_can_withdraw(self, obj: ApprovalInstance) -> bool:
        request = self.context.get("request")
        if request is None or not request.user.is_authenticated:
            return False
        return obj.status == "pending" and obj.applicant_id == request.user.pk


class CreateApprovalInstanceSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=200)
    template_code = serializers.CharField(max_length=64, required=False, allow_blank=True, default="")
    biz_type = serializers.CharField(max_length=64, required=False, default="generic.request")
    biz_id = serializers.CharField(max_length=64, required=False, allow_blank=True, default="")
    biz_no = serializers.CharField(max_length=64, required=False, allow_blank=True, default="")
    summary = serializers.CharField(required=False, allow_blank=True, default="")
    amount = serializers.DecimalField(max_digits=20, decimal_places=4, required=False, allow_null=True)
    department_id = serializers.IntegerField(required=False, allow_null=True)


class ApprovalCommentSerializer(serializers.Serializer):
    comment = serializers.CharField(required=False, allow_blank=True, default="")
