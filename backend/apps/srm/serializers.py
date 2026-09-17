from __future__ import annotations

from datetime import date

from rest_framework import serializers

from apps.core.serializers import ReferenceIdSerializer
from apps.srm.models import Supplier, SupplierContact, SupplierQualification


class SupplierSerializer(ReferenceIdSerializer):
    company_name = serializers.SerializerMethodField()
    buyer_name = serializers.SerializerMethodField()

    class Meta:
        model = Supplier
        fields = (
            "id", "company_id", "company_name", "code", "name", "short_name",
            "category", "grade", "admission_status", "payment_terms", "tax_no",
            "address", "primary_contact_name", "primary_contact_phone",
            "buyer_id", "buyer_name", "tags", "is_active", "remark",
            "version", "created_at", "updated_at",
        )
        read_only_fields = ("id", "company_name", "buyer_name", "version", "created_at", "updated_at")

    def get_company_name(self, obj: Supplier) -> str:
        return obj.company.name if obj.company_id else ""

    def get_buyer_name(self, obj: Supplier) -> str:
        return obj.buyer.name if obj.buyer_id else ""

    def validate_code(self, value: str) -> str:
        code = (value or "").strip()
        if not code:
            raise serializers.ValidationError("供应商编码不能为空。")
        return code

    def validate_tags(self, value):
        if value in (None, ""):
            return []
        if not isinstance(value, list):
            raise serializers.ValidationError("标签必须是字符串数组。")
        return [str(item).strip() for item in value if str(item).strip()]


class SupplierContactSerializer(ReferenceIdSerializer):
    supplier_name = serializers.SerializerMethodField()
    company_id = serializers.SerializerMethodField()

    class Meta:
        model = SupplierContact
        fields = (
            "id", "supplier_id", "supplier_name", "company_id", "name", "position",
            "phone", "email", "is_primary", "is_active", "remark",
            "version", "created_at", "updated_at",
        )
        read_only_fields = (
            "id", "supplier_name", "company_id", "version", "created_at", "updated_at",
        )

    def get_supplier_name(self, obj: SupplierContact) -> str:
        return obj.supplier.name if obj.supplier_id else ""

    def get_company_id(self, obj: SupplierContact) -> int | None:
        return obj.supplier.company_id if obj.supplier_id else None

    def validate(self, attrs):
        supplier = attrs.get("supplier", getattr(self.instance, "supplier", None))
        name = attrs.get("name", getattr(self.instance, "name", None))
        if supplier is not None and name:
            duplicated = SupplierContact.objects.filter(supplier=supplier, name=name)
            if self.instance is not None:
                duplicated = duplicated.exclude(pk=self.instance.pk)
            if duplicated.exists():
                raise serializers.ValidationError({"name": "该供应商下已存在同名联系人。"})
        return attrs


class SupplierQualificationSerializer(ReferenceIdSerializer):
    supplier_name = serializers.SerializerMethodField()
    company_id = serializers.SerializerMethodField()
    days_to_expiry = serializers.SerializerMethodField()
    is_expired = serializers.SerializerMethodField()

    class Meta:
        model = SupplierQualification
        fields = (
            "id", "supplier_id", "supplier_name", "company_id", "qualification_type",
            "certificate_no", "issued_by", "issued_date", "expiry_date",
            "days_to_expiry", "is_expired", "is_active", "remark",
            "version", "created_at", "updated_at",
        )
        read_only_fields = (
            "id", "supplier_name", "company_id", "days_to_expiry", "is_expired",
            "version", "created_at", "updated_at",
        )

    def get_supplier_name(self, obj: SupplierQualification) -> str:
        return obj.supplier.name if obj.supplier_id else ""

    def get_company_id(self, obj: SupplierQualification) -> int | None:
        return obj.supplier.company_id if obj.supplier_id else None

    def get_days_to_expiry(self, obj: SupplierQualification) -> int | None:
        """剩余有效天数；未填写到期日时返回 null（前端显示「未登记到期日」）。"""
        if not obj.expiry_date:
            return None
        return (obj.expiry_date - date.today()).days

    def get_is_expired(self, obj: SupplierQualification) -> bool | None:
        if not obj.expiry_date:
            return None
        return obj.expiry_date < date.today()

    def validate(self, attrs):
        issued = attrs.get("issued_date", getattr(self.instance, "issued_date", None))
        expiry = attrs.get("expiry_date", getattr(self.instance, "expiry_date", None))
        if issued and expiry and expiry < issued:
            raise serializers.ValidationError({"expiry_date": "到期日期不能早于发证日期。"})
        supplier = attrs.get("supplier", getattr(self.instance, "supplier", None))
        certificate_no = attrs.get(
            "certificate_no", getattr(self.instance, "certificate_no", "")
        )
        qualification_type = attrs.get(
            "qualification_type", getattr(self.instance, "qualification_type", "")
        )
        if supplier is not None and certificate_no:
            duplicated = SupplierQualification.objects.filter(
                supplier=supplier,
                qualification_type=qualification_type,
                certificate_no__iexact=str(certificate_no).strip(),
            )
            if self.instance is not None:
                duplicated = duplicated.exclude(pk=self.instance.pk)
            if duplicated.exists():
                raise serializers.ValidationError(
                    {"certificate_no": "该供应商下同类型资质已存在相同证书编号。"}
                )
        return attrs
