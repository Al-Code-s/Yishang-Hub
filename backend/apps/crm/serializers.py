"""客户管理序列化器。

* 枚举字段的中文标签由 ``DisplayLabelsMixin`` 自动补 ``<field>_display``；
* 编号（客户 ``CUS``、投诉 ``CMPL``、评价 ``PRV``）留空时由视图层按编码规则取号；
* ``status`` 一律只读：投诉与评价的状态只能通过动作接口
  （受理 / 登记处理结果 / 关闭 / 回复）由服务层推进，不允许直接 PATCH 跳步。
"""

from __future__ import annotations

from rest_framework import serializers

from apps.core.serializers import ReferenceIdSerializer, ServerDerivedCodeSerializerMixin
from apps.crm.models import Customer, CustomerComplaint, CustomerContact, ProductReview
from apps.factory.models import Employee


def _name_of(instance, attribute: str) -> str:
    related = getattr(instance, attribute, None)
    return str(related) if related is not None else ""


def _employee_field(**kwargs) -> serializers.PrimaryKeyRelatedField:
    return serializers.PrimaryKeyRelatedField(
        queryset=Employee.objects.all(), required=False, allow_null=True, **kwargs
    )


class CustomerSerializer(ReferenceIdSerializer):
    company_name = serializers.SerializerMethodField()
    salesman_name = serializers.SerializerMethodField()
    # 新增时允许留空：由视图层按编码规则（CUS）自动取号；编辑时仍必填，
    # 避免把已有客户改成空编码而破坏「同公司内编码唯一」。
    # `default=""` 而不是 `required=False`：`uq_customer_company_code` 会派生
    # UniqueTogetherValidator，它强制要求 company_id 与 code 同时出现在输入里，
    # 只有带默认值的字段才能合法缺省（默认值随后被视图层替换为真实编码）。
    code = serializers.CharField(allow_blank=True, default="", max_length=32, label="客户编码")

    class Meta:
        model = Customer
        fields = (
            "id", "company_id", "company_name", "code", "name", "short_name",
            "category", "level", "status", "credit_limit", "payment_terms",
            "tax_no", "address", "primary_contact_name", "primary_contact_phone",
            "salesman_id", "salesman_name", "tags", "is_active", "remark",
            "version", "created_at", "updated_at",
        )
        read_only_fields = ("id", "company_name", "salesman_name", "version", "created_at", "updated_at")

    def get_company_name(self, obj: Customer) -> str:
        return obj.company.name if obj.company_id else ""

    def get_salesman_name(self, obj: Customer) -> str:
        return obj.salesman.name if obj.salesman_id else ""

    def validate_code(self, value: str) -> str:
        code = (value or "").strip()
        if not code and self.instance is not None:
            raise serializers.ValidationError("客户编码不能为空。")
        return code

    def validate_credit_limit(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError("信用额度不能为负数。")
        return value

    def validate_tags(self, value):
        if value in (None, ""):
            return []
        if not isinstance(value, list):
            raise serializers.ValidationError("标签必须是字符串数组。")
        cleaned: list[str] = []
        for item in value:
            text = str(item).strip()
            if text:
                cleaned.append(text)
        return cleaned


class CustomerContactSerializer(ReferenceIdSerializer):
    customer_name = serializers.SerializerMethodField()
    company_id = serializers.SerializerMethodField()

    class Meta:
        model = CustomerContact
        fields = (
            "id", "customer_id", "customer_name", "company_id", "name", "position",
            "phone", "email", "is_primary", "is_active", "remark",
            "version", "created_at", "updated_at",
        )
        read_only_fields = (
            "id", "customer_name", "company_id", "version", "created_at", "updated_at",
        )

    def get_customer_name(self, obj: CustomerContact) -> str:
        return obj.customer.name if obj.customer_id else ""

    def get_company_id(self, obj: CustomerContact) -> int | None:
        return obj.customer.company_id if obj.customer_id else None

    def validate_name(self, value: str) -> str:
        name = (value or "").strip()
        if not name:
            raise serializers.ValidationError("联系人姓名不能为空。")
        return name

    def validate(self, attrs):
        customer = attrs.get("customer", getattr(self.instance, "customer", None))
        name = attrs.get("name", getattr(self.instance, "name", None))
        if customer is not None and name:
            duplicated = CustomerContact.objects.filter(customer=customer, name=name)
            if self.instance is not None:
                duplicated = duplicated.exclude(pk=self.instance.pk)
            if duplicated.exists():
                raise serializers.ValidationError({"name": "该客户下已存在同名联系人。"})
        return attrs


class CustomerComplaintSerializer(ServerDerivedCodeSerializerMixin, ReferenceIdSerializer):
    company_name = serializers.SerializerMethodField()
    customer_name = serializers.SerializerMethodField()
    receiver_name = serializers.SerializerMethodField()
    handler_name = serializers.SerializerMethodField()
    # 新增时允许留空：由视图层按编码规则（CMPL）自动取号。
    complaint_no = serializers.CharField(
        allow_blank=True, default="", max_length=32, label="投诉编号"
    )

    class Meta:
        model = CustomerComplaint
        fields = (
            "id", "company_id", "company_name", "complaint_no",
            "customer_id", "customer_name", "complaint_type", "level", "status",
            "source", "title", "content", "complained_at", "reporter", "reporter_phone",
            "related_no", "receiver_id", "receiver_name", "handler_id", "handler_name",
            "accepted_at", "resolved_at", "closed_at", "handle_measure", "satisfaction",
            "remark", "version", "created_at", "updated_at",
        )
        read_only_fields = (
            "id", "company_name", "customer_name", "receiver_name", "handler_name",
            "status", "accepted_at", "resolved_at", "closed_at",
            "version", "created_at", "updated_at",
        )

    def get_company_name(self, obj: CustomerComplaint) -> str:
        return _name_of(obj, "company")

    def get_customer_name(self, obj: CustomerComplaint) -> str:
        return _name_of(obj, "customer")

    def get_receiver_name(self, obj: CustomerComplaint) -> str:
        return _name_of(obj, "receiver")

    def get_handler_name(self, obj: CustomerComplaint) -> str:
        return _name_of(obj, "handler")

    def validate_title(self, value: str) -> str:
        title = (value or "").strip()
        if not title:
            raise serializers.ValidationError("投诉主题不能为空。")
        return title

    def validate_content(self, value: str) -> str:
        content = (value or "").strip()
        if not content:
            raise serializers.ValidationError("投诉内容不能为空。")
        return content

    def validate_satisfaction(self, value: int) -> int:
        score = int(value or 0)
        if not 0 <= score <= 5:
            raise serializers.ValidationError("满意度评分只能是 0（未评价）或 1~5。")
        return score

    def validate_complaint_no(self, value: str) -> str:
        code = (value or "").strip()
        if not code and self.instance is not None:
            raise serializers.ValidationError("投诉编号不能为空。")
        return code

    def validate(self, attrs):
        """客户必须属于所选公司，避免把 A 公司的客户挂到 B 公司的投诉上。"""
        customer = attrs.get("customer", getattr(self.instance, "customer", None))
        company = attrs.get("company", getattr(self.instance, "company", None))
        if customer is not None and company is not None and customer.company_id != company.pk:
            raise serializers.ValidationError({"customer_id": "该客户不属于所选公司。"})
        return attrs


class ProductReviewSerializer(ServerDerivedCodeSerializerMixin, ReferenceIdSerializer):
    company_name = serializers.SerializerMethodField()
    customer_name = serializers.SerializerMethodField()
    sku_code = serializers.SerializerMethodField()
    replier_name = serializers.SerializerMethodField()
    review_no = serializers.CharField(
        allow_blank=True, default="", max_length=32, label="评价编号"
    )

    class Meta:
        model = ProductReview
        fields = (
            "id", "company_id", "company_name", "review_no",
            "customer_id", "customer_name", "sku_id", "sku_code", "product_desc",
            "score", "status", "reviewer_name", "reviewed_at", "content",
            "reply", "replier_id", "replier_name", "replied_at", "closed_at",
            "remark", "version", "created_at", "updated_at",
        )
        read_only_fields = (
            "id", "company_name", "customer_name", "sku_code", "replier_name",
            "status", "replied_at", "closed_at",
            "version", "created_at", "updated_at",
        )

    def get_company_name(self, obj: ProductReview) -> str:
        return _name_of(obj, "company")

    def get_customer_name(self, obj: ProductReview) -> str:
        return _name_of(obj, "customer")

    def get_sku_code(self, obj: ProductReview) -> str:
        sku = getattr(obj, "sku", None)
        return str(getattr(sku, "code", "") or "") if sku is not None else ""

    def get_replier_name(self, obj: ProductReview) -> str:
        return _name_of(obj, "replier")

    def validate_score(self, value: int) -> int:
        score = int(value or 0)
        if not 1 <= score <= 5:
            raise serializers.ValidationError("评分只能是 1~5 分。")
        return score

    def validate_content(self, value: str) -> str:
        content = (value or "").strip()
        if not content:
            raise serializers.ValidationError("评价内容不能为空。")
        return content

    def validate_review_no(self, value: str) -> str:
        code = (value or "").strip()
        if not code and self.instance is not None:
            raise serializers.ValidationError("评价编号不能为空。")
        return code

    def validate(self, attrs):
        """客户必须属于所选公司，避免跨公司引用客户造成数据串档。"""
        customer = attrs.get("customer", getattr(self.instance, "customer", None))
        company = attrs.get("company", getattr(self.instance, "company", None))
        if customer is not None and company is not None and customer.company_id != company.pk:
            raise serializers.ValidationError({"customer_id": "该客户不属于所选公司。"})
        return attrs


# ---------------------------------------------------------------------------
# 动作接口入参
# ---------------------------------------------------------------------------


class ComplaintAcceptSerializer(serializers.Serializer):
    """受理投诉：受理人 / 处理人可留空，留空表示由后续处理时再指定。"""

    receiver_id = _employee_field(label="受理人")
    handler_id = _employee_field(label="处理人")
    measure = serializers.CharField(
        required=False, allow_blank=True, default="", label="初步处理措施"
    )


class ComplaintResolveSerializer(serializers.Serializer):
    measure = serializers.CharField(label="处理措施")
    handler_id = _employee_field(label="处理人")
    satisfaction = serializers.IntegerField(
        required=False, min_value=0, max_value=5, label="客户回访满意度（0 表示未评价）"
    )


class ComplaintCloseSerializer(serializers.Serializer):
    note = serializers.CharField(required=False, allow_blank=True, default="", label="关闭说明")


class ReviewReplySerializer(serializers.Serializer):
    reply = serializers.CharField(label="回复内容")
    replier_id = _employee_field(label="回复人")


class ReviewCloseSerializer(serializers.Serializer):
    note = serializers.CharField(required=False, allow_blank=True, default="", label="关闭说明")
