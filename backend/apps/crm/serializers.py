from __future__ import annotations

from rest_framework import serializers

from apps.core.serializers import ReferenceIdSerializer
from apps.crm.models import Customer, CustomerContact


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
