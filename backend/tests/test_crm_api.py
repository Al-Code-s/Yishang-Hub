"""客户主数据用例（任务书 10.2、14.2 第 3/4 条与 6.4「权限执行位置」）。

覆盖要点：
* 公司数据范围在「列表 / 详情 / 写入」三处同时生效（不能只过滤列表）；
* 客户联系人继承所属客户的公司范围，避免「看不到客户却看得到联系人」；
* 客户编码在同一公司内唯一，跨公司允许同码；
* 同一客户下只能有一个主联系人，切换主联系人会取消原标记；
* 无操作权限的账号不能调用写接口；
* 新增客户写入审计日志。

全部走 HTTP 接口与真实 MySQL 约束，不使用 mock。
"""

from __future__ import annotations

import pytest
from django.db import IntegrityError, transaction

from apps.core.models import AuditLog
from apps.crm.models import Customer, CustomerContact
from apps.crm.services import ensure_single_primary_contact
from apps.identity.models import DataScopeType
from tests.conftest import make_role, make_user

pytestmark = pytest.mark.django_db

CUSTOMERS_URL = "/api/v1/crm/customers/"
CONTACTS_URL = "/api/v1/crm/customer-contacts/"
LOGIN_URL = "/api/v1/identity/auth/login/"
META_URL = "/api/v1/meta/"
PASSWORD = "Tst!Passw0rd2026"

CRM_ADMIN_PERMISSIONS = [
    "crm.customer.view",
    "crm.customer.create",
    "crm.customer.update",
    "crm.customer.deactivate",
    "crm.customer_contact.view",
    "crm.customer_contact.create",
    "crm.customer_contact.update",
    "analytics.dashboard.view",
]


def login(client, user) -> None:
    response = client.post(
        LOGIN_URL, {"username": user.username, "password": PASSWORD}, format="json"
    )
    assert response.status_code == 200, response.content


@pytest.fixture
def crm_admin(api_client, registry_permissions, company):
    role = make_role(
        code="test_crm_admin",
        permission_codes=CRM_ADMIN_PERMISSIONS,
        data_scope_type=DataScopeType.COMPANY,
        company=company,
    )
    user = make_user(username="crm_admin_t", role=role, company=company)
    login(api_client, user)
    return api_client


@pytest.fixture
def crm_viewer(api_client, registry_permissions, company):
    role = make_role(
        code="test_crm_viewer",
        permission_codes=["crm.customer.view", "crm.customer_contact.view"],
        data_scope_type=DataScopeType.COMPANY,
        company=company,
    )
    user = make_user(username="crm_viewer_t", role=role, company=company)
    login(api_client, user)
    return api_client


@pytest.fixture
def super_client(api_client, registry_permissions, company):
    user = make_user(username="crm_meta_admin", company=company, is_superuser=True)
    api_client.force_authenticate(user=user)
    return api_client


def make_customer(company, code: str, name: str = "", **extra) -> Customer:
    return Customer.objects.create(company=company, code=code, name=name or f"客户{code}", **extra)
def test_unauthenticated_customer_access_is_denied(api_client):
    response = api_client.get(CUSTOMERS_URL)
    assert response.status_code in (401, 403), response.content


def test_customer_list_and_detail_are_company_scoped(crm_admin, company, other_company):
    mine = make_customer(company, "C-MINE")
    foreign = make_customer(other_company, "C-FOREIGN")

    listed = crm_admin.get(CUSTOMERS_URL)
    assert listed.status_code == 200, listed.content
    codes = {row["code"] for row in listed.json()["results"]}
    assert "C-MINE" in codes
    assert "C-FOREIGN" not in codes

    assert crm_admin.get(f"{CUSTOMERS_URL}{mine.pk}/").status_code == 200
    # 越权详情按「不存在」处理，不泄露其他公司是否存在该客户
    assert crm_admin.get(f"{CUSTOMERS_URL}{foreign.pk}/").status_code == 404


def test_cannot_create_customer_outside_company_scope(crm_admin, other_company):
    response = crm_admin.post(
        CUSTOMERS_URL,
        {"company_id": other_company.pk, "code": "C-X", "name": "越权客户"},
        format="json",
    )
    assert response.status_code == 403, response.content
    assert response.json()["code"] == "OUT_OF_DATA_SCOPE"
    # 越权写入必须整体回滚，不能留下半条记录
    assert not Customer.objects.filter(code="C-X").exists()


def test_customer_code_is_unique_per_company(crm_admin, company, other_company):
    first = crm_admin.post(
        CUSTOMERS_URL,
        {"company_id": company.pk, "code": "C-001", "name": "客户一"},
        format="json",
    )
    assert first.status_code == 201, first.content

    duplicate = crm_admin.post(
        CUSTOMERS_URL,
        {"company_id": company.pk, "code": "C-001", "name": "客户二"},
        format="json",
    )
    # 同一公司内重复编码被拒绝：DRF 唯一性校验给出 400，模型约束兜底为 409
    assert duplicate.status_code in (400, 409), duplicate.content

    # 唯一性按公司隔离：另一家公司允许使用相同编码
    make_customer(other_company, "C-001", "对照公司同码客户")
    assert Customer.objects.filter(code="C-001").count() == 2

    # 绕过接口直写数据库也必须被约束拦住
    with pytest.raises(IntegrityError), transaction.atomic():
        make_customer(company, "C-001", "重复客户")


def test_customer_create_is_audited(crm_admin, company):
    created = crm_admin.post(
        CUSTOMERS_URL,
        {"company_id": company.pk, "code": "C-AUD", "name": "审计客户"},
        format="json",
    )
    assert created.status_code == 201, created.content
    log = AuditLog.objects.filter(
        object_type="crm.Customer", object_id=str(created.json()["id"]), action="create"
    ).first()
    assert log is not None, "新增客户必须写入审计日志"
    assert log.actor_username == "crm_admin_t"
    assert log.company_id == company.pk
def test_contact_inherits_customer_company_scope(crm_admin, company, other_company):
    mine = make_customer(company, "C-S1")
    foreign = make_customer(other_company, "C-S2")
    mine_contact = CustomerContact.objects.create(customer=mine, name="我方联系人")
    foreign_contact = CustomerContact.objects.create(customer=foreign, name="他方联系人")

    listed = crm_admin.get(CONTACTS_URL)
    assert listed.status_code == 200, listed.content
    names = {row["name"] for row in listed.json()["results"]}
    assert "我方联系人" in names
    assert "他方联系人" not in names

    assert crm_admin.get(f"{CONTACTS_URL}{mine_contact.pk}/").status_code == 200
    assert crm_admin.get(f"{CONTACTS_URL}{foreign_contact.pk}/").status_code == 404

    # 关联对象选择校验：不能把联系人挂到范围外的客户上
    denied = crm_admin.post(
        CONTACTS_URL, {"customer_id": foreign.pk, "name": "越权联系人"}, format="json"
    )
    assert denied.status_code == 403, denied.content
    assert not CustomerContact.objects.filter(name="越权联系人").exists()


def test_single_primary_contact_via_api(crm_admin, company):
    customer = make_customer(company, "C-P1")
    first = crm_admin.post(
        CONTACTS_URL,
        {"customer_id": customer.pk, "name": "王主管", "is_primary": True},
        format="json",
    )
    assert first.status_code == 201, first.content
    second = crm_admin.post(
        CONTACTS_URL,
        {"customer_id": customer.pk, "name": "李经理", "is_primary": True},
        format="json",
    )
    assert second.status_code == 201, second.content

    assert CustomerContact.objects.get(pk=second.json()["id"]).is_primary is True
    assert CustomerContact.objects.get(pk=first.json()["id"]).is_primary is False
    assert CustomerContact.objects.filter(customer=customer, is_primary=True).count() == 1


def test_service_demotes_previous_primary_contact(company):
    customer = make_customer(company, "C-P2")
    old = CustomerContact.objects.create(customer=customer, name="原主联系人", is_primary=True)
    new = CustomerContact.objects.create(customer=customer, name="新主联系人", is_primary=True)

    ensure_single_primary_contact(new)

    old.refresh_from_db()
    new.refresh_from_db()
    assert old.is_primary is False
    assert new.is_primary is True


def test_contact_name_unique_within_customer_only(crm_admin, company):
    customer = make_customer(company, "C-N1")
    first = crm_admin.post(
        CONTACTS_URL, {"customer_id": customer.pk, "name": "张三"}, format="json"
    )
    assert first.status_code == 201, first.content

    duplicate = crm_admin.post(
        CONTACTS_URL, {"customer_id": customer.pk, "name": "张三"}, format="json"
    )
    assert duplicate.status_code in (400, 409), duplicate.content

    # 不同客户下允许同名联系人
    other = make_customer(company, "C-N2")
    allowed = crm_admin.post(
        CONTACTS_URL, {"customer_id": other.pk, "name": "张三"}, format="json"
    )
    assert allowed.status_code == 201, allowed.content


def test_viewer_without_create_permission_is_rejected(crm_viewer, company):
    assert crm_viewer.get(CUSTOMERS_URL).status_code == 200
    denied = crm_viewer.post(
        CUSTOMERS_URL,
        {"company_id": company.pk, "code": "C-V", "name": "无权限客户"},
        format="json",
    )
    assert denied.status_code == 403, denied.content
    assert not Customer.objects.filter(code="C-V").exists()


def test_meta_exposes_crm_and_srm_enums(super_client):
    response = super_client.get(META_URL)
    assert response.status_code == 200, response.content
    body = response.json()
    for key in (
        "customer_categories",
        "customer_levels",
        "customer_statuses",
        "supplier_categories",
        "supplier_grades",
        "admission_statuses",
        "qualification_types",
    ):
        assert body.get(key), f"meta 缺少枚举 {key}"
    assert {item["value"] for item in body["customer_levels"]} == {"A", "B", "C", "D"}
    assert {item["value"] for item in body["customer_statuses"]} >= {"potential", "active"}
