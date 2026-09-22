"""客户主数据用例（任务书 10.2、14.2 第 3/4 条与 6.4「权限执行位置」）。

覆盖要点：
* 公司数据范围在「列表 / 详情 / 写入」三处同时生效（不能只过滤列表）；
* 客户联系人继承所属客户的公司范围，避免「看不到客户却看得到联系人」；
* 客户编码在同一公司内唯一，跨公司允许同码；
* 同一客户下只能有一个主联系人，切换主联系人会取消原标记；
* 无操作权限的账号不能调用写接口；
* 新增客户写入审计日志；
* 新增客户不必手工输入编码：留空时按编码规则（`CUS`）在事务内自动取号，
  规则可配置（改规则即改编号），显式传入的编码仍然保留，编辑时不允许清空。

全部走 HTTP 接口与真实 MySQL 约束，不使用 mock。
"""

from __future__ import annotations

import re
from datetime import timedelta

import pytest
from django.db import IntegrityError, transaction

from apps.core.models import AuditLog, CodeRule, ResetPeriod
from apps.core.services import business_today
from apps.crm.models import Customer, CustomerComplaint, CustomerContact, ProductReview
from apps.crm.services import ensure_single_primary_contact
from apps.factory.models import Employee
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


# --------------------------------------------------------------------------
# 客户编码自动生成（新增客户不必手工输入编码）
# --------------------------------------------------------------------------


@pytest.fixture
def customer_code_rules(db):
    """取号依赖编码规则；测试库不跑 bootstrap_system，这里显式登记 CUS 规则。"""
    CodeRule.objects.update_or_create(
        code="CUS",
        defaults={
            "name": "客户编码",
            "pattern": "CUS{YYYY}{SEQ:4}",
            "reset_period": ResetPeriod.YEARLY,
            "is_active": True,
        },
    )


def test_customer_code_is_generated_when_omitted(crm_admin, customer_code_rules, company):
    """请求里完全不带 code 也能建档，编码按规则生成并在同一周期内逐号递增。"""
    first = crm_admin.post(
        CUSTOMERS_URL, {"company_id": company.pk, "name": "自动编码客户一"}, format="json"
    )
    assert first.status_code == 201, first.content
    first_code = first.json()["code"]
    assert re.fullmatch(rf"CUS{business_today():%Y}\d{{4}}", first_code), first_code
    assert Customer.objects.get(pk=first.json()["id"]).code == first_code

    second = crm_admin.post(
        CUSTOMERS_URL, {"company_id": company.pk, "name": "自动编码客户二"}, format="json"
    )
    assert second.status_code == 201, second.content
    second_code = second.json()["code"]
    assert int(second_code[7:]) == int(first_code[7:]) + 1, (first_code, second_code)


def test_blank_customer_code_on_create_is_generated(crm_admin, customer_code_rules, company):
    """前端可能提交空串而不是省略字段，空串同样应触发自动取号。"""
    created = crm_admin.post(
        CUSTOMERS_URL,
        {"company_id": company.pk, "code": "   ", "name": "空白编码客户"},
        format="json",
    )
    assert created.status_code == 201, created.content
    assert re.fullmatch(rf"CUS{business_today():%Y}\d{{4}}", created.json()["code"])


def test_customer_code_follows_configured_rule_pattern(crm_admin, customer_code_rules, company):
    """格式来自编码规则表：改规则即改编号，说明代码里没有写死格式。"""
    CodeRule.objects.filter(code="CUS").update(pattern="KH{YY}{SEQ:3}")
    created = crm_admin.post(
        CUSTOMERS_URL, {"company_id": company.pk, "name": "改规则客户"}, format="json"
    )
    assert created.status_code == 201, created.content
    assert re.fullmatch(rf"KH{business_today():%y}\d{{3}}", created.json()["code"]), created.json()


def test_explicit_customer_code_is_still_respected(crm_admin, customer_code_rules, company):
    """显式传入的编码仍然生效，便于历史数据迁移与外部系统对齐。"""
    created = crm_admin.post(
        CUSTOMERS_URL,
        {"company_id": company.pk, "code": "C-LEGACY-01", "name": "手工编码客户"},
        format="json",
    )
    assert created.status_code == 201, created.content
    assert created.json()["code"] == "C-LEGACY-01"


def test_customer_code_cannot_be_cleared_on_update(crm_admin, customer_code_rules, company):
    """编辑时清空编码被拒绝：编码是客户身份，不能变成空值后与别的客户撞唯一键。"""
    created = crm_admin.post(
        CUSTOMERS_URL, {"company_id": company.pk, "name": "待改编码客户"}, format="json"
    )
    assert created.status_code == 201, created.content
    customer_id = created.json()["id"]
    original_code = created.json()["code"]

    cleared = crm_admin.patch(f"{CUSTOMERS_URL}{customer_id}/", {"code": ""}, format="json")
    assert cleared.status_code == 400, cleared.content
    assert Customer.objects.get(pk=customer_id).code == original_code


def test_missing_code_rule_fails_clearly_without_creating_customer(crm_admin, db, company):
    """规则被删除/停用时必须显式报错，而不是落一条空编码客户。"""
    CodeRule.objects.filter(code="CUS").delete()
    before = Customer.objects.count()
    response = crm_admin.post(
        CUSTOMERS_URL, {"company_id": company.pk, "name": "无规则客户"}, format="json"
    )
    assert response.status_code == 404, response.content
    assert response.json()["code"] == "CODE_RULE_NOT_FOUND"
    assert Customer.objects.count() == before


# --------------------------------------------------------------------------
# 客户投诉与产品评价（客户服务流程；状态只能由服务层推进）
# --------------------------------------------------------------------------

COMPLAINTS_URL = "/api/v1/crm/complaints/"
REVIEWS_URL = "/api/v1/crm/product-reviews/"


@pytest.fixture
def crm_flow_code_rules(db):
    """取号依赖编码规则；测试库不跑 bootstrap_system，这里显式登记相关规则。"""
    rules = {
        "CUS": ("CUS{YYYY}{SEQ:4}", ResetPeriod.YEARLY),
        "CMPL": ("CMPL{YYYYMMDD}{SEQ:4}", ResetPeriod.DAILY),
        "PRV": ("PRV{YYYYMMDD}{SEQ:4}", ResetPeriod.DAILY),
    }
    for code, (pattern, period) in rules.items():
        CodeRule.objects.update_or_create(
            code=code,
            defaults={"name": code, "pattern": pattern, "reset_period": period, "is_active": True},
        )


@pytest.fixture
def crm_flow_admin(api_client, registry_permissions, company):
    """具备全部 crm 权限（含投诉 / 评价的动作权限）的账号。"""
    codes = sorted(code for code in registry_permissions if code.startswith("crm."))
    role = make_role(
        code="test_crm_flow_admin",
        permission_codes=codes,
        data_scope_type=DataScopeType.COMPANY,
        company=company,
    )
    user = make_user(username="crm_flow_admin_t", role=role, company=company)
    login(api_client, user)
    return api_client


@pytest.fixture
def crm_flow_viewer(api_client, registry_permissions, company):
    """只有查看权限：能看投诉与评价，但不能受理 / 回复 / 关闭。"""
    codes = sorted(
        code for code in registry_permissions if code.startswith("crm.") and code.endswith(".view")
    )
    role = make_role(
        code="test_crm_flow_viewer",
        permission_codes=codes,
        data_scope_type=DataScopeType.COMPANY,
        company=company,
    )
    user = make_user(username="crm_flow_viewer_t", role=role, company=company)
    login(api_client, user)
    return api_client


def make_complaint(client, company, customer, **extra):
    payload = {
        "company_id": company.pk,
        "customer_id": customer.pk,
        "title": "到货色差",
        "content": "首批到货与确认样存在色差，要求核查并给出处理方案。",
    }
    payload.update(extra)
    return client.post(COMPLAINTS_URL, payload, format="json")


def make_review(client, company, customer, **extra):
    payload = {
        "company_id": company.pk,
        "customer_id": customer.pk,
        "score": 4,
        "reviewed_at": business_today().isoformat(),
        "content": "整体交付及时，包装可以再加固。",
    }
    payload.update(extra)
    return client.post(REVIEWS_URL, payload, format="json")


def test_complaint_no_is_generated_when_omitted(crm_flow_admin, crm_flow_code_rules, company):
    customer = make_customer(company, "C-CMPL")
    created = make_complaint(crm_flow_admin, company, customer)
    assert created.status_code == 201, created.content
    body = created.json()
    assert re.fullmatch(rf"CMPL{business_today():%Y%m%d}\d{{4}}", body["complaint_no"]), body
    assert body["status"] == "pending"
    assert body["satisfaction"] == 0


def test_complaint_full_lifecycle_writes_audit(crm_flow_admin, crm_flow_code_rules, company):
    customer = make_customer(company, "C-FLOW")
    complaint_id = make_complaint(crm_flow_admin, company, customer).json()["id"]
    handler = Employee.objects.create(company=company, employee_no="EMP-CS1", name="客服小李")

    accepted = crm_flow_admin.post(
        f"{COMPLAINTS_URL}{complaint_id}/accept/",
        {"handler_id": handler.pk, "measure": "已安排质量组复核在库同批次"},
        format="json",
    )
    assert accepted.status_code == 200, accepted.content
    assert accepted.json()["status"] == "handling"
    assert accepted.json()["accepted_at"] is not None
    assert accepted.json()["handler_name"].startswith("客服小李")

    resolved = crm_flow_admin.post(
        f"{COMPLAINTS_URL}{complaint_id}/resolve/",
        {"measure": "确认为批次色差，已换货并书面说明", "satisfaction": 4},
        format="json",
    )
    assert resolved.status_code == 200, resolved.content
    assert resolved.json()["status"] == "resolved"
    assert resolved.json()["satisfaction"] == 4
    assert resolved.json()["resolved_at"] is not None

    closed = crm_flow_admin.post(
        f"{COMPLAINTS_URL}{complaint_id}/close/", {"note": "客户确认结案"}, format="json"
    )
    assert closed.status_code == 200, closed.content
    assert closed.json()["status"] == "closed"
    assert closed.json()["closed_at"] is not None

    # 建档 + 受理 + 登记结果 + 关闭：每一步都留痕，且记录了中文原因
    logs = AuditLog.objects.filter(object_type="crm.CustomerComplaint", object_id=str(complaint_id))
    assert logs.count() == 4
    reasons = {log.reason for log in logs}
    assert {"受理客户投诉", "登记投诉处理结果", "客户确认结案"} <= reasons


def test_complaint_cannot_skip_lifecycle_steps(crm_flow_admin, crm_flow_code_rules, company):
    customer = make_customer(company, "C-SKIP")
    complaint_id = make_complaint(crm_flow_admin, company, customer).json()["id"]

    skipped_resolve = crm_flow_admin.post(
        f"{COMPLAINTS_URL}{complaint_id}/resolve/", {"measure": "直接结案"}, format="json"
    )
    assert skipped_resolve.status_code == 409, skipped_resolve.content
    assert skipped_resolve.json()["code"] == "COMPLAINT_STATUS_INVALID"

    skipped_close = crm_flow_admin.post(
        f"{COMPLAINTS_URL}{complaint_id}/close/", {}, format="json"
    )
    assert skipped_close.status_code == 409, skipped_close.content
    assert skipped_close.json()["code"] == "COMPLAINT_STATUS_INVALID"

    accepted = crm_flow_admin.post(f"{COMPLAINTS_URL}{complaint_id}/accept/", {}, format="json")
    assert accepted.status_code == 200, accepted.content

    # 处理中同样不能直接关闭：必须先登记处理结果
    still_skipping = crm_flow_admin.post(
        f"{COMPLAINTS_URL}{complaint_id}/close/", {}, format="json"
    )
    assert still_skipping.status_code == 409, still_skipping.content

    repeated_accept = crm_flow_admin.post(
        f"{COMPLAINTS_URL}{complaint_id}/accept/", {}, format="json"
    )
    assert repeated_accept.status_code == 409, repeated_accept.content
    assert repeated_accept.json()["code"] == "COMPLAINT_STATUS_INVALID"
    assert CustomerComplaint.objects.get(pk=complaint_id).status == "handling"


def test_complaint_resolve_requires_measure(crm_flow_admin, crm_flow_code_rules, company):
    customer = make_customer(company, "C-MEASURE")
    complaint_id = make_complaint(crm_flow_admin, company, customer).json()["id"]
    crm_flow_admin.post(f"{COMPLAINTS_URL}{complaint_id}/accept/", {}, format="json")

    blank = crm_flow_admin.post(
        f"{COMPLAINTS_URL}{complaint_id}/resolve/", {"measure": "   "}, format="json"
    )
    assert blank.status_code == 400, blank.content
    assert CustomerComplaint.objects.get(pk=complaint_id).status == "handling"


def test_complaint_status_is_read_only(crm_flow_admin, crm_flow_code_rules, company):
    """状态不能直接 PATCH：绕开动作接口改状态会被忽略，也必须被忽略。"""
    customer = make_customer(company, "C-PATCH")
    complaint_id = make_complaint(crm_flow_admin, company, customer).json()["id"]

    patched = crm_flow_admin.patch(
        f"{COMPLAINTS_URL}{complaint_id}/", {"status": "closed"}, format="json"
    )
    assert patched.status_code == 200, patched.content
    assert patched.json()["status"] == "pending"
    assert CustomerComplaint.objects.get(pk=complaint_id).status == "pending"


def test_complaint_rejects_customer_from_other_company(
    crm_flow_admin, crm_flow_code_rules, company, other_company
):
    foreign_customer = make_customer(other_company, "C-FOREIGN-2")
    response = make_complaint(crm_flow_admin, company, foreign_customer)
    assert response.status_code == 400, response.content
    assert "不属于所选公司" in str(response.json())


def test_complaints_are_company_scoped(crm_flow_admin, crm_flow_code_rules, company, other_company):
    mine = make_customer(company, "C-SCOPE")
    theirs = make_customer(other_company, "C-SCOPE-X")
    mine_id = make_complaint(crm_flow_admin, company, mine).json()["id"]
    foreign = CustomerComplaint.objects.create(
        company=other_company,
        complaint_no="CMPL-X",
        customer=theirs,
        title="对照公司投诉",
        content="对照数据",
    )

    listed = crm_flow_admin.get(COMPLAINTS_URL)
    assert listed.status_code == 200, listed.content
    assert {row["id"] for row in listed.json()["results"]} == {mine_id}
    assert crm_flow_admin.get(f"{COMPLAINTS_URL}{mine_id}/").status_code == 200
    assert crm_flow_admin.get(f"{COMPLAINTS_URL}{foreign.pk}/").status_code == 404


def test_complaint_actions_require_permission(crm_flow_viewer, crm_flow_code_rules, company):
    customer = make_customer(company, "C-PERM")
    complaint = CustomerComplaint.objects.create(
        company=company,
        complaint_no="CMPL-PERM-1",
        customer=customer,
        title="权限校验用例",
        content="只有查看权限的账号不能受理。",
    )

    listed = crm_flow_viewer.get(COMPLAINTS_URL)
    assert listed.status_code == 200, listed.content

    denied = crm_flow_viewer.post(f"{COMPLAINTS_URL}{complaint.pk}/accept/", {}, format="json")
    assert denied.status_code == 403, denied.content
    assert denied.json()["code"] == "PERMISSION_DENIED"
    assert CustomerComplaint.objects.get(pk=complaint.pk).status == "pending"

    create_denied = make_complaint(crm_flow_viewer, company, customer)
    assert create_denied.status_code == 403, create_denied.content


def test_review_no_is_generated_and_score_is_validated(crm_flow_admin, crm_flow_code_rules, company):
    customer = make_customer(company, "C-REVIEW")
    created = make_review(crm_flow_admin, company, customer)
    assert created.status_code == 201, created.content
    body = created.json()
    assert re.fullmatch(rf"PRV{business_today():%Y%m%d}\d{{4}}", body["review_no"]), body
    assert body["status"] == "pending"

    for invalid in (0, 6):
        bad = make_review(crm_flow_admin, company, customer, score=invalid)
        assert bad.status_code == 400, bad.content


def test_review_lifecycle_reply_then_close(crm_flow_admin, crm_flow_code_rules, company):
    customer = make_customer(company, "C-REVIEW-FLOW")
    review_id = make_review(crm_flow_admin, company, customer).json()["id"]

    premature_close = crm_flow_admin.post(
        f"{REVIEWS_URL}{review_id}/close/", {}, format="json"
    )
    assert premature_close.status_code == 409, premature_close.content
    assert premature_close.json()["code"] == "REVIEW_STATUS_INVALID"

    blank_reply = crm_flow_admin.post(f"{REVIEWS_URL}{review_id}/reply/", {"reply": " "}, format="json")
    assert blank_reply.status_code == 400, blank_reply.content

    replied = crm_flow_admin.post(
        f"{REVIEWS_URL}{review_id}/reply/",
        {"reply": "感谢反馈，已加强外箱缓冲"},
        format="json",
    )
    assert replied.status_code == 200, replied.content
    assert replied.json()["status"] == "replied"
    assert replied.json()["replied_at"] is not None

    repeated = crm_flow_admin.post(
        f"{REVIEWS_URL}{review_id}/reply/", {"reply": "再回一次"}, format="json"
    )
    assert repeated.status_code == 409, repeated.content

    closed = crm_flow_admin.post(f"{REVIEWS_URL}{review_id}/close/", {}, format="json")
    assert closed.status_code == 200, closed.content
    assert closed.json()["status"] == "closed"
    assert closed.json()["closed_at"] is not None

    after_close = crm_flow_admin.post(
        f"{REVIEWS_URL}{review_id}/reply/", {"reply": "关闭后回复"}, format="json"
    )
    assert after_close.status_code == 409, after_close.content
    assert ProductReview.objects.get(pk=review_id).status == "closed"


def test_complaint_statistics_totals_and_distribution(crm_flow_admin, crm_flow_code_rules, company):
    """投诉统计：总量、未关闭、状态/类型/级别分布，满意度只按已回访的算。"""
    customer = make_customer(company, "C-CSTAT")
    first = make_complaint(
        crm_flow_admin, company, customer, title="色差", complaint_type="quality", level="general"
    ).json()
    second = make_complaint(
        crm_flow_admin, company, customer, title="延迟", complaint_type="delivery", level="severe"
    ).json()
    make_complaint(crm_flow_admin, company, customer, title="态度", complaint_type="service")

    crm_flow_admin.post(f"{COMPLAINTS_URL}{first['id']}/accept/", {}, format="json")
    crm_flow_admin.post(
        f"{COMPLAINTS_URL}{first['id']}/resolve/",
        {"measure": "换货并补偿运费", "satisfaction": 5},
        format="json",
    )
    crm_flow_admin.post(f"{COMPLAINTS_URL}{first['id']}/close/", {"note": "客户确认"}, format="json")
    crm_flow_admin.post(f"{COMPLAINTS_URL}{second['id']}/accept/", {}, format="json")

    response = crm_flow_admin.get(f"{COMPLAINTS_URL}statistics/")
    assert response.status_code == 200, response.content
    body = response.json()
    assert body["total"] == 3
    assert body["closed_total"] == 1
    assert body["open_total"] == 2
    assert body["unrated_total"] == 2
    # 没有回访的投诉不计入平均分：不会用 0 分把平均值拉低
    assert body["avg_satisfaction"] == "5.00"
    status = {row["value"]: row["total"] for row in body["by_status"]}
    assert status == {"closed": 1, "handling": 1, "pending": 1}
    types = {row["value"]: row["total"] for row in body["by_type"]}
    assert types["quality"] == 1 and types["delivery"] == 1 and types["service"] == 1
    assert body["by_level"][0] == {"value": "general", "label": "一般", "total": 2}


def test_complaint_statistics_without_ratings_returns_none(crm_flow_admin, crm_flow_code_rules, company):
    """一条都没回访时平均分为 null，而不是 0 分。"""
    customer = make_customer(company, "C-CSTAT2")
    make_complaint(crm_flow_admin, company, customer)

    body = crm_flow_admin.get(f"{COMPLAINTS_URL}statistics/").json()
    assert body["total"] == 1
    assert body["avg_satisfaction"] is None
    assert body["unrated_total"] == 1


def test_statistics_requires_view_permission(crm_admin, company):
    """只有客户主数据权限的账号看不到投诉 / 评价统计。"""
    denied = crm_admin.get(f"{COMPLAINTS_URL}statistics/")
    assert denied.status_code == 403, denied.content
    assert denied.json()["code"] == "PERMISSION_DENIED"
    assert crm_admin.get(f"{REVIEWS_URL}statistics/").status_code == 403


def test_complaint_statistics_is_company_scoped(crm_flow_admin, crm_flow_code_rules, company, other_company):
    mine = make_customer(company, "C-SCOPE1")
    theirs = make_customer(other_company, "C-SCOPE2")
    make_complaint(crm_flow_admin, company, mine)
    CustomerComplaint.objects.create(
        company=other_company,
        customer=theirs,
        complaint_no="CMPL-OTHER",
        title="别家公司的投诉",
        content="不应对当前账号可见",
    )

    body = crm_flow_admin.get(f"{COMPLAINTS_URL}statistics/").json()
    assert body["total"] == 1


def test_product_review_statistics_scores_and_good_rate(crm_flow_admin, crm_flow_code_rules, company):
    """评价统计：平均评分、评分分布与好评率（4 分及以上为好评）。"""
    customer = make_customer(company, "C-RSTAT")
    for score in (5, 4, 2):
        created = make_review(crm_flow_admin, company, customer, score=score)
        assert created.status_code == 201, created.content

    response = crm_flow_admin.get(f"{REVIEWS_URL}statistics/")
    assert response.status_code == 200, response.content
    body = response.json()
    assert body["total"] == 3
    assert body["pending_total"] == 3
    assert body["avg_score"] == "3.67"
    assert body["good_total"] == 2
    assert body["good_rate"] == "66.67"
    assert {row["value"]: row["total"] for row in body["by_score"]} == {1: 0, 2: 1, 3: 0, 4: 1, 5: 1}
    # 分布只列有数据的档位（0 条的档位不占版面），但评分分布是固定 1~5 档
    assert {row["value"]: row["total"] for row in body["by_status"]} == {"pending": 3}


def test_review_statistics_date_filter(crm_flow_admin, crm_flow_code_rules, company):
    """按日期过滤：评价日期在区间外的记录不计入。"""
    customer = make_customer(company, "C-RSTAT2")
    today = business_today()
    make_review(crm_flow_admin, company, customer, score=5, reviewed_at=today.isoformat())
    make_review(
        crm_flow_admin,
        company,
        customer,
        score=1,
        reviewed_at=(today - timedelta(days=30)).isoformat(),
    )

    recent = crm_flow_admin.get(
        f"{REVIEWS_URL}statistics/", {"since": (today - timedelta(days=1)).isoformat()}
    ).json()
    assert recent["total"] == 1
    assert recent["avg_score"] == "5.00"

    everything = crm_flow_admin.get(f"{REVIEWS_URL}statistics/").json()
    assert everything["total"] == 2
    assert everything["good_rate"] == "50.00"


def test_meta_exposes_complaint_and_review_enums(super_client):
    response = super_client.get(META_URL)
    assert response.status_code == 200, response.content
    body = response.json()
    for key in (
        "complaint_types",
        "complaint_levels",
        "complaint_statuses",
        "complaint_sources",
        "product_review_statuses",
    ):
        assert body.get(key), f"meta 缺少枚举 {key}"
    assert {item["value"] for item in body["complaint_statuses"]} == {
        "pending",
        "handling",
        "resolved",
        "closed",
    }
    assert {item["value"] for item in body["product_review_statuses"]} == {
        "pending",
        "replied",
        "closed",
    }
