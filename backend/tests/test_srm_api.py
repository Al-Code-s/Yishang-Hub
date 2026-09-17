"""供应商主数据用例（任务书 10.4 供应商档案/资质、14.2 第 3/4 条）。

覆盖要点：
* 供应商及其联系人/资质都按公司数据范围过滤，写入同样受范围约束；
* 供应商编码在同一公司内唯一；
* 资质证书编号的规范化去重键设计：填写编号时按「供应商+类型+编号(忽略大小写)」
  判重，未填写编号时 dedup_key 为 NULL，允许同类型多条并存
  （任务书 5.4：MySQL 中含 NULL 的唯一索引不会互相冲突，必须显式设计）；
* 到期日期不得早于发证日期；
* 剩余天数与是否过期由后端计算，未登记到期日时返回 null 而不是「未过期」；
* 同一供应商下只能有一个主联系人。

全部走 HTTP 接口与真实 MySQL 约束，不使用 mock。
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from django.db import IntegrityError, transaction

from apps.identity.models import DataScopeType
from apps.srm.models import Supplier, SupplierContact, SupplierQualification
from tests.conftest import make_role, make_user

pytestmark = pytest.mark.django_db

SUPPLIERS_URL = "/api/v1/srm/suppliers/"
CONTACTS_URL = "/api/v1/srm/supplier-contacts/"
QUALIFICATIONS_URL = "/api/v1/srm/supplier-qualifications/"
LOGIN_URL = "/api/v1/identity/auth/login/"
PASSWORD = "Tst!Passw0rd2026"

SRM_ADMIN_PERMISSIONS = [
    "srm.supplier.view",
    "srm.supplier.create",
    "srm.supplier.update",
    "srm.supplier.deactivate",
    "srm.supplier_contact.view",
    "srm.supplier_contact.create",
    "srm.supplier_contact.update",
    "srm.supplier_qualification.view",
    "srm.supplier_qualification.create",
    "srm.supplier_qualification.update",
    "analytics.dashboard.view",
]


def login(client, user) -> None:
    response = client.post(
        LOGIN_URL, {"username": user.username, "password": PASSWORD}, format="json"
    )
    assert response.status_code == 200, response.content


@pytest.fixture
def srm_admin(api_client, registry_permissions, company):
    role = make_role(
        code="test_srm_admin",
        permission_codes=SRM_ADMIN_PERMISSIONS,
        data_scope_type=DataScopeType.COMPANY,
        company=company,
    )
    user = make_user(username="srm_admin_t", role=role, company=company)
    login(api_client, user)
    return api_client


@pytest.fixture
def srm_viewer(api_client, registry_permissions, company):
    role = make_role(
        code="test_srm_viewer",
        permission_codes=["srm.supplier.view"],
        data_scope_type=DataScopeType.COMPANY,
        company=company,
    )
    user = make_user(username="srm_viewer_t", role=role, company=company)
    login(api_client, user)
    return api_client


def make_supplier(company, code: str, name: str = "", **extra) -> Supplier:
    return Supplier.objects.create(company=company, code=code, name=name or f"供应商{code}", **extra)
def test_unauthenticated_supplier_access_is_denied(api_client):
    assert api_client.get(SUPPLIERS_URL).status_code in (401, 403)


def test_supplier_list_and_detail_are_company_scoped(srm_admin, company, other_company):
    mine = make_supplier(company, "S-MINE")
    foreign = make_supplier(other_company, "S-FOREIGN")

    listed = srm_admin.get(SUPPLIERS_URL)
    assert listed.status_code == 200, listed.content
    codes = {row["code"] for row in listed.json()["results"]}
    assert "S-MINE" in codes
    assert "S-FOREIGN" not in codes

    assert srm_admin.get(f"{SUPPLIERS_URL}{mine.pk}/").status_code == 200
    assert srm_admin.get(f"{SUPPLIERS_URL}{foreign.pk}/").status_code == 404


def test_cannot_create_supplier_outside_company_scope(srm_admin, other_company):
    response = srm_admin.post(
        SUPPLIERS_URL,
        {"company_id": other_company.pk, "code": "S-X", "name": "越权供应商"},
        format="json",
    )
    assert response.status_code == 403, response.content
    assert response.json()["code"] == "OUT_OF_DATA_SCOPE"
    assert not Supplier.objects.filter(code="S-X").exists()


def test_supplier_code_is_unique_per_company(srm_admin, company, other_company):
    payload = {"company_id": company.pk, "code": "S-001", "name": "面料供应商"}
    first = srm_admin.post(SUPPLIERS_URL, payload, format="json")
    assert first.status_code == 201, first.content

    duplicate = srm_admin.post(
        SUPPLIERS_URL, {**payload, "name": "重复供应商"}, format="json"
    )
    assert duplicate.status_code in (400, 409), duplicate.content

    make_supplier(other_company, "S-001", "对照公司同码供应商")
    assert Supplier.objects.filter(code="S-001").count() == 2

    with pytest.raises(IntegrityError), transaction.atomic():
        make_supplier(company, "S-001", "数据库层重复")


def test_supplier_contact_and_qualification_inherit_supplier_scope(
    srm_admin, company, other_company
):
    mine = make_supplier(company, "S-S1")
    foreign = make_supplier(other_company, "S-S2")
    mine_contact = SupplierContact.objects.create(supplier=mine, name="我方业务员")
    foreign_contact = SupplierContact.objects.create(supplier=foreign, name="他方业务员")
    mine_qualification = SupplierQualification.objects.create(
        supplier=mine, qualification_type="business_license", certificate_no="BL-MINE"
    )
    foreign_qualification = SupplierQualification.objects.create(
        supplier=foreign, qualification_type="business_license", certificate_no="BL-FOREIGN"
    )

    contacts = srm_admin.get(CONTACTS_URL).json()["results"]
    assert {row["name"] for row in contacts} == {"我方业务员"}
    assert srm_admin.get(f"{CONTACTS_URL}{mine_contact.pk}/").status_code == 200
    assert srm_admin.get(f"{CONTACTS_URL}{foreign_contact.pk}/").status_code == 404

    qualifications = srm_admin.get(QUALIFICATIONS_URL).json()["results"]
    assert {row["certificate_no"] for row in qualifications} == {"BL-MINE"}
    assert srm_admin.get(f"{QUALIFICATIONS_URL}{mine_qualification.pk}/").status_code == 200
    assert srm_admin.get(f"{QUALIFICATIONS_URL}{foreign_qualification.pk}/").status_code == 404

    denied = srm_admin.post(
        CONTACTS_URL, {"supplier_id": foreign.pk, "name": "越权联系人"}, format="json"
    )
    assert denied.status_code == 403, denied.content
    assert not SupplierContact.objects.filter(name="越权联系人").exists()


def test_single_primary_supplier_contact_via_api(srm_admin, company):
    supplier = make_supplier(company, "S-P1")
    first = srm_admin.post(
        CONTACTS_URL,
        {"supplier_id": supplier.pk, "name": "甲", "is_primary": True},
        format="json",
    )
    assert first.status_code == 201, first.content
    second = srm_admin.post(
        CONTACTS_URL,
        {"supplier_id": supplier.pk, "name": "乙", "is_primary": True},
        format="json",
    )
    assert second.status_code == 201, second.content

    assert SupplierContact.objects.get(pk=second.json()["id"]).is_primary is True
    assert SupplierContact.objects.get(pk=first.json()["id"]).is_primary is False
    assert SupplierContact.objects.filter(supplier=supplier, is_primary=True).count() == 1
def test_qualification_certificate_no_deduplicated_case_insensitively(srm_admin, company):
    supplier = make_supplier(company, "S-Q1")
    first = srm_admin.post(
        QUALIFICATIONS_URL,
        {
            "supplier_id": supplier.pk,
            "qualification_type": "business_license",
            "certificate_no": "BL-2026-001",
        },
        format="json",
    )
    assert first.status_code == 201, first.content

    duplicate = srm_admin.post(
        QUALIFICATIONS_URL,
        {
            "supplier_id": supplier.pk,
            "qualification_type": "business_license",
            "certificate_no": "bl-2026-001",
        },
        format="json",
    )
    assert duplicate.status_code in (400, 409), duplicate.content
    assert SupplierQualification.objects.count() == 1

    # 模型层去重键同样忽略大小写：绕过接口直写也必须被唯一索引拦住
    with pytest.raises(IntegrityError), transaction.atomic():
        SupplierQualification.objects.create(
            supplier=supplier,
            qualification_type="business_license",
            certificate_no="BL-2026-001",
        )


def test_qualification_without_certificate_no_allows_multiple_rows(srm_admin, company):
    """未填写证书编号时 dedup_key 为 NULL，MySQL 唯一索引允许并列多条。"""
    supplier = make_supplier(company, "S-Q2")
    for index in range(2):
        created = srm_admin.post(
            QUALIFICATIONS_URL,
            {
                "supplier_id": supplier.pk,
                "qualification_type": "test_report",
                "certificate_no": "",
                "issued_by": f"检测机构{index}",
            },
            format="json",
        )
        assert created.status_code == 201, created.content
    assert SupplierQualification.objects.filter(supplier=supplier).count() == 2
    assert set(
        SupplierQualification.objects.filter(supplier=supplier).values_list("dedup_key", flat=True)
    ) == {None}


def test_qualification_expiry_cannot_precede_issue_date(srm_admin, company):
    supplier = make_supplier(company, "S-Q3")
    response = srm_admin.post(
        QUALIFICATIONS_URL,
        {
            "supplier_id": supplier.pk,
            "qualification_type": "quality_system",
            "issued_date": "2026-01-10",
            "expiry_date": "2026-01-01",
        },
        format="json",
    )
    assert response.status_code == 400, response.content
    assert "expiry_date" in response.json()["details"]
    assert not SupplierQualification.objects.filter(supplier=supplier).exists()


def test_qualification_expiry_days_are_computed_by_backend(srm_admin, company):
    supplier = make_supplier(company, "S-Q4")
    today = date.today()

    future = srm_admin.post(
        QUALIFICATIONS_URL,
        {
            "supplier_id": supplier.pk,
            "qualification_type": "business_license",
            "expiry_date": (today + timedelta(days=30)).isoformat(),
        },
        format="json",
    )
    assert future.status_code == 201, future.content
    assert future.json()["days_to_expiry"] == 30
    assert future.json()["is_expired"] is False

    expired = srm_admin.post(
        QUALIFICATIONS_URL,
        {
            "supplier_id": supplier.pk,
            "qualification_type": "test_report",
            "expiry_date": (today - timedelta(days=5)).isoformat(),
        },
        format="json",
    )
    assert expired.status_code == 201, expired.content
    assert expired.json()["days_to_expiry"] == -5
    assert expired.json()["is_expired"] is True

    # 未登记到期日：必须返回 null，不能被当成「未过期」
    unknown = srm_admin.post(
        QUALIFICATIONS_URL,
        {"supplier_id": supplier.pk, "qualification_type": "environmental"},
        format="json",
    )
    assert unknown.status_code == 201, unknown.content
    assert unknown.json()["expiry_date"] is None
    assert unknown.json()["days_to_expiry"] is None
    assert unknown.json()["is_expired"] is None


def test_viewer_without_create_permission_is_rejected(srm_viewer, company):
    assert srm_viewer.get(SUPPLIERS_URL).status_code == 200
    denied = srm_viewer.post(
        SUPPLIERS_URL,
        {"company_id": company.pk, "code": "S-V", "name": "无权限供应商"},
        format="json",
    )
    assert denied.status_code == 403, denied.content
    assert not Supplier.objects.filter(code="S-V").exists()
