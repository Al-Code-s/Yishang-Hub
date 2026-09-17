"""客户主数据接口。

客户归属公司，按数据范围过滤；联系人通过 `customer__company_id` 继承同一范围，
避免出现「看不到客户、却能看到其联系人」的越权读取。
"""

from __future__ import annotations

from apps.core.viewsets import ActiveFilterMixin, ScopedModelViewSet
from apps.crm.models import Customer, CustomerContact
from apps.crm.serializers import CustomerContactSerializer, CustomerSerializer
from apps.crm.services import ensure_single_primary_contact


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
