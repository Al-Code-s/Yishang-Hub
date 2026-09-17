"""供应商主数据接口。

供应商归属公司，按数据范围过滤；联系人与资质通过 `supplier__company_id`
继承同一范围，避免「看不到供应商、却能读到其联系人/资质」的越权读取。
"""

from __future__ import annotations

from apps.core.viewsets import ActiveFilterMixin, ScopedModelViewSet
from apps.srm.models import Supplier, SupplierContact, SupplierQualification
from apps.srm.serializers import (
    SupplierContactSerializer,
    SupplierQualificationSerializer,
    SupplierSerializer,
)
from apps.srm.services import ensure_single_primary_contact


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
