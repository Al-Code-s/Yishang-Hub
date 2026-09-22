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
from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction
from rest_framework.test import APIClient

from apps.core.models import CodeRule, ResetPeriod
from apps.identity.models import DataScopeType
from apps.srm.models import (
    Supplier,
    SupplierContact,
    SupplierEvaluation,
    SupplierEvaluationLine,
    SupplierEvaluationStatus,
    SupplierEvaluationWeight,
    SupplierQualification,
)
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


# ---------------------------------------------------------------------------
# 五维量化评价与权重配置（任务书 10.4：REQ-10.4-05 ~ 10.4-08）
# ---------------------------------------------------------------------------

WEIGHTS_URL = "/api/v1/srm/supplier-evaluation-weights/"
EVALUATIONS_URL = "/api/v1/srm/supplier-evaluations/"
EVALUATION_STATS_URL = EVALUATIONS_URL + "statistics/"

#: 一版标准权重（合计 100），用于大多数用例
BASE_WEIGHTS = {
    "quality_weight": "30",
    "technology_weight": "20",
    "response_weight": "15",
    "delivery_weight": "25",
    "cost_weight": "10",
}

#: 五个维度全部有数据的原始得分（质量 90 / 技术 80 / 响应 70 / 交付 60 / 成本 50）
FULL_SCORES = {
    "quality": "90",
    "technology": "80",
    "response": "70",
    "delivery": "60",
    "cost": "50",
}

EVALUATION_PERMISSIONS = [
    "srm.supplier.view",
    "srm.evaluation_weight.view",
    "srm.evaluation_weight.create",
    "srm.evaluation_weight.update",
    "srm.evaluation.view",
    "srm.evaluation.create",
    "srm.evaluation.update",
    "srm.evaluation.publish",
    "srm.evaluation.archive",
    "analytics.dashboard.view",
]


@pytest.fixture
def evaluation_code_rules(db):
    """评价单号依赖编码规则；测试库不跑 bootstrap_system，这里显式登记 SEV。"""
    CodeRule.objects.update_or_create(
        code="SEV",
        defaults={
            "name": "供应商评价单号",
            "pattern": "SEV{YYYYMMDD}{SEQ:4}",
            "reset_period": ResetPeriod.DAILY,
            "is_active": True,
        },
    )


@pytest.fixture
def eval_admin(api_client, registry_permissions, company, evaluation_code_rules):
    role = make_role(
        code="test_srm_eval_admin",
        permission_codes=EVALUATION_PERMISSIONS,
        data_scope_type=DataScopeType.COMPANY,
        company=company,
    )
    user = make_user(username="srm_eval_admin_t", role=role, company=company)
    login(api_client, user)
    return api_client


@pytest.fixture
def eval_viewer(registry_permissions, company):
    """独立的 APIClient：同一个测试里同时用管理员与只读用户时，会话不会互相覆盖。"""
    client = APIClient()
    role = make_role(
        code="test_srm_eval_viewer",
        permission_codes=["srm.evaluation.view"],
        data_scope_type=DataScopeType.COMPANY,
        company=company,
    )
    user = make_user(username="srm_eval_viewer_t", role=role, company=company)
    login(client, user)
    return client


def create_weights(eval_admin, company, **overrides):
    payload = {"company_id": company.pk, **BASE_WEIGHTS, **overrides}
    response = eval_admin.post(WEIGHTS_URL, payload, format="json")
    assert response.status_code == 201, response.content
    return response.json()


def create_evaluation(eval_admin, company, supplier, **overrides):
    payload = {"company_id": company.pk, "supplier_id": supplier.pk, **overrides}
    response = eval_admin.post(EVALUATIONS_URL, payload, format="json")
    return response


def put_lines(client, evaluation_id, scores=None, observation=None):
    """默认把五个维度都打上分；``scores`` 里显式给 None 表示该维度**没有数据**。"""
    merged = dict(FULL_SCORES)
    merged.update(scores or {})
    rows = [
        {
            "dimension": dimension,
            "raw_score": value,
            "raw_observation": observation or {},
        }
        for dimension, value in merged.items()
    ]
    return client.post(
        f"{EVALUATIONS_URL}{evaluation_id}/lines/", {"lines": rows}, format="json"
    )


def test_weight_config_total_must_be_exactly_100(eval_admin, company):
    rejected = eval_admin.post(
        WEIGHTS_URL,
        {"company_id": company.pk, **BASE_WEIGHTS, "cost_weight": "9"},
        format="json",
    )
    assert rejected.status_code == 400, rejected.content
    assert rejected.json()["code"] == "WEIGHT_TOTAL_INVALID"
    assert not SupplierEvaluationWeight.objects.filter(company=company).exists()

    created = eval_admin.post(
        WEIGHTS_URL, {"company_id": company.pk, **BASE_WEIGHTS}, format="json"
    )
    assert created.status_code == 201, created.content
    assert created.json()["version_no"] == 1
    assert created.json()["total_weight"] == "100.00"
    assert created.json()["is_active"] is True


def test_weight_range_is_enforced_by_database(company):
    """服务层之外直写越界权重必须被数据库 CHECK 约束拦住。"""
    with pytest.raises(IntegrityError), transaction.atomic():
        SupplierEvaluationWeight.objects.create(
            company=company, quality_weight=Decimal("120"), cost_weight=Decimal("-20")
        )


def test_only_one_active_weight_version_per_company(eval_admin, company):
    first = create_weights(eval_admin, company)
    second = create_weights(eval_admin, company, quality_weight="40", cost_weight="0")

    assert second["version_no"] == 2
    configs = {row.pk: row for row in SupplierEvaluationWeight.objects.filter(company=company)}
    assert configs[first["id"]].is_active is False
    assert configs[second["id"]].is_active is True
    # 旧版本原样保留（留痕），不是被覆盖或删除
    assert configs[first["id"]].quality_weight == Decimal("30.00")


def test_editing_weights_derives_a_new_version_and_keeps_the_old_one(eval_admin, company):
    """权重配置只增不改：PATCH 派生新版本，响应体是新那一条。"""
    original = create_weights(eval_admin, company)
    updated = eval_admin.patch(
        f"{WEIGHTS_URL}{original['id']}/", {"quality_weight": "40", "cost_weight": "0"}, format="json"
    )
    assert updated.status_code == 200, updated.content
    body = updated.json()
    assert body["id"] != original["id"]
    assert body["version_no"] == 2
    assert body["quality_weight"] == "40.00"
    # 未传的项沿用旧版本，不悄悄回落到默认值
    assert body["technology_weight"] == original["technology_weight"]
    assert body["delivery_weight"] == original["delivery_weight"]

    original_row = SupplierEvaluationWeight.objects.get(pk=original["id"])
    assert original_row.quality_weight == Decimal("30.00")
    assert SupplierEvaluationWeight.objects.filter(company=company).count() == 2


def test_evaluation_requires_an_active_weight_config(eval_admin, company):
    supplier = make_supplier(company, "S-E0")
    response = create_evaluation(eval_admin, company, supplier)
    assert response.status_code == 400, response.content
    assert response.json()["code"] == "EVALUATION_WEIGHT_REQUIRED"
    assert not SupplierEvaluation.objects.filter(supplier=supplier).exists()


def test_evaluation_no_is_generated_and_weights_are_snapshotted(eval_admin, company):
    config = create_weights(eval_admin, company)
    supplier = make_supplier(company, "S-E1")

    response = create_evaluation(eval_admin, company, supplier)
    assert response.status_code == 201, response.content
    body = response.json()
    assert body["evaluation_no"].startswith("SEV")
    assert body["weight_config_id"] == config["id"]
    assert body["weight_config_version"] == 1
    assert body["weight_snapshot"]["quality"] == "30.00"
    assert body["weight_snapshot"]["cost"] == "10.00"
    assert body["status"] == SupplierEvaluationStatus.DRAFT
    assert body["total_score"] is None
    assert body["is_editable"] is True


def test_total_score_is_computed_by_backend_and_client_value_is_ignored(eval_admin, company):
    """客户端传上来的 total_score 不生效：总分只能由服务层按权重快照算。"""
    create_weights(eval_admin, company)
    supplier = make_supplier(company, "S-E2")

    created = create_evaluation(eval_admin, company, supplier, total_score="99", grade="A")
    assert created.status_code == 201, created.content
    evaluation_id = created.json()["id"]
    assert created.json()["total_score"] is None
    assert created.json()["grade"] == ""

    scored = put_lines(eval_admin, evaluation_id)
    assert scored.status_code == 200, scored.content
    body = scored.json()
    # 90x30% + 80x20% + 70x15% + 60x25% + 50x10% = 73.50
    assert body["total_score"] == "73.50"
    assert body["grade"] == "C"
    assert body["missing_dimensions"] == []
    assert body["effective_weight_total"] == "100.00"
    lines = {row["dimension"]: row for row in body["lines"]}
    assert lines["quality"]["weighted_score"] == "27.00"
    assert lines["quality"]["effective_weight"] == "30.00"
    # 原始观测值与计算过程都留痕，不允许只存一个最终分数
    assert lines["quality"]["weight"] == "30.00"


def test_lines_require_all_five_dimensions(eval_admin, company):
    create_weights(eval_admin, company)
    supplier = make_supplier(company, "S-E3")
    evaluation_id = create_evaluation(eval_admin, company, supplier).json()["id"]

    response = eval_admin.post(
        f"{EVALUATIONS_URL}{evaluation_id}/lines/",
        {"lines": [{"dimension": "quality", "raw_score": "90"}]},
        format="json",
    )
    assert response.status_code == 400, response.content
    assert response.json()["code"] == "DIMENSION_ROWS_INCOMPLETE"
    assert not SupplierEvaluationLine.objects.filter(evaluation_id=evaluation_id).exists()


def test_duplicate_dimension_and_out_of_range_score_are_rejected(eval_admin, company):
    create_weights(eval_admin, company)
    supplier = make_supplier(company, "S-E4")
    evaluation_id = create_evaluation(eval_admin, company, supplier).json()["id"]

    duplicated = eval_admin.post(
        f"{EVALUATIONS_URL}{evaluation_id}/lines/",
        {
            "lines": [
                {"dimension": "quality", "raw_score": "90"},
                {"dimension": "quality", "raw_score": "80"},
                {"dimension": "technology", "raw_score": "80"},
                {"dimension": "response", "raw_score": "70"},
                {"dimension": "delivery", "raw_score": "60"},
                {"dimension": "cost", "raw_score": "50"},
            ]
        },
        format="json",
    )
    assert duplicated.status_code == 400, duplicated.content
    assert duplicated.json()["code"] == "DUPLICATED_DIMENSION"

    out_of_range = put_lines(eval_admin, evaluation_id, {"quality": "101"})
    assert out_of_range.status_code == 400, out_of_range.content
    assert out_of_range.json()["code"] == "INVALID_SCORE"


def test_missing_dimension_mark_missing_keeps_partial_total_and_no_grade(eval_admin, company):
    """「标注缺失」不重分配权重：总分口径不完整，因此不给等级。"""
    create_weights(eval_admin, company)
    supplier = make_supplier(company, "S-E5")
    evaluation_id = create_evaluation(
        eval_admin, company, supplier, missing_dimension_policy="mark_missing"
    ).json()["id"]

    body = put_lines(eval_admin, evaluation_id, {"cost": None}).json()
    assert body["missing_dimensions"] == ["cost"]
    assert body["effective_weight_total"] == "90.00"
    # 27 + 16 + 10.5 + 15 = 68.50（成本的 10% 权重空着，没有被摊给别人）
    assert body["total_score"] == "68.50"
    assert body["grade"] == ""
    lines = {row["dimension"]: row for row in body["lines"]}
    assert lines["cost"]["is_missing"] is True
    assert lines["cost"]["effective_weight"] == "0.00"
    assert lines["cost"]["weighted_score"] is None
    # 有数据的维度权重不变，说明确实没重分配
    assert lines["quality"]["effective_weight"] == "30.00"


def test_missing_dimension_redistribute_renormalizes_effective_weights(eval_admin, company):
    """「重新分配有效权重」把缺数据维度的权重按比例摊给有数据的维度，合计仍为 100。"""
    create_weights(eval_admin, company)
    supplier = make_supplier(company, "S-E6")
    evaluation_id = create_evaluation(
        eval_admin, company, supplier, missing_dimension_policy="redistribute"
    ).json()["id"]

    body = put_lines(eval_admin, evaluation_id, {"cost": None}).json()
    lines = {row["dimension"]: row for row in body["lines"]}
    assert body["missing_dimensions"] == ["cost"]
    assert body["effective_weight_total"] == "100.00"
    # 90 的有效权重是 100 - (22.22 + 16.67 + 27.78) = 33.33
    assert lines["quality"]["effective_weight"] == "33.33"
    assert lines["technology"]["effective_weight"] == "22.22"
    assert lines["response"]["effective_weight"] == "16.67"
    assert lines["delivery"]["effective_weight"] == "27.78"
    assert lines["cost"]["effective_weight"] == "0.00"
    # 30.00 + 17.78 + 11.67 + 16.67 = 76.12，口径完整因此有等级
    assert body["total_score"] == "76.12"
    assert body["grade"] == "B"


def test_changing_weight_config_does_not_rewrite_history(eval_admin, company):
    """历史评分沿用评分时的权重快照：后来改权重不回头改已生效的评价。"""
    create_weights(eval_admin, company)
    supplier = make_supplier(company, "S-E7")
    evaluation_id = create_evaluation(eval_admin, company, supplier).json()["id"]
    assert put_lines(eval_admin, evaluation_id).status_code == 200
    published = eval_admin.post(f"{EVALUATIONS_URL}{evaluation_id}/publish/", {}, format="json")
    assert published.status_code == 200, published.content
    assert published.json()["total_score"] == "73.50"
    assert published.json()["status"] == SupplierEvaluationStatus.EFFECTIVE

    # 派生新版权重（质量 40 / 成本 0，合计仍 100），历史评价的权重与总分必须原样不变
    derived = eval_admin.patch(
        f"{WEIGHTS_URL}{published.json()['weight_config_id']}/",
        {"quality_weight": "40", "cost_weight": "0"},
        format="json",
    )
    assert derived.status_code == 200, derived.content
    assert derived.json()["version_no"] == 2

    detail = eval_admin.get(f"{EVALUATIONS_URL}{evaluation_id}/")
    assert detail.status_code == 200, detail.content
    body = detail.json()
    assert body["weight_snapshot"]["quality"] == "30.00"
    assert body["weight_snapshot"]["cost"] == "10.00"
    assert body["weight_config_version"] == 1
    assert body["total_score"] == "73.50"

    # 新评价用新版本权重
    fresh = create_evaluation(eval_admin, company, supplier).json()
    assert fresh["weight_config_version"] == 2
    assert fresh["weight_snapshot"]["quality"] == "40.00"
    assert fresh["weight_snapshot"]["cost"] == "0.00"


def test_evaluation_is_locked_after_publish(eval_admin, company):
    create_weights(eval_admin, company)
    supplier = make_supplier(company, "S-E8")
    evaluation_id = create_evaluation(eval_admin, company, supplier).json()["id"]

    no_lines = eval_admin.post(f"{EVALUATIONS_URL}{evaluation_id}/publish/", {}, format="json")
    assert no_lines.status_code == 409, no_lines.content
    assert no_lines.json()["code"] == "EVALUATION_LINES_REQUIRED"

    put_lines(eval_admin, evaluation_id)
    assert eval_admin.post(
        f"{EVALUATIONS_URL}{evaluation_id}/publish/", {}, format="json"
    ).status_code == 200

    again = eval_admin.post(f"{EVALUATIONS_URL}{evaluation_id}/publish/", {}, format="json")
    assert again.status_code == 409, again.content
    assert again.json()["code"] == "EVALUATION_STATUS_INVALID"

    locked_lines = put_lines(eval_admin, evaluation_id, {"quality": "100"})
    assert locked_lines.status_code == 409, locked_lines.content
    assert locked_lines.json()["code"] == "EVALUATION_LOCKED"

    locked_header = eval_admin.patch(
        f"{EVALUATIONS_URL}{evaluation_id}/", {"remark": "事后备注"}, format="json"
    )
    assert locked_header.status_code == 409, locked_header.content

    archived = eval_admin.post(f"{EVALUATIONS_URL}{evaluation_id}/archive/", {}, format="json")
    assert archived.status_code == 200, archived.content
    assert archived.json()["status"] == SupplierEvaluationStatus.ARCHIVED
    rearchived = eval_admin.post(f"{EVALUATIONS_URL}{evaluation_id}/archive/", {}, format="json")
    assert rearchived.status_code == 409, rearchived.content


def test_draft_header_can_be_changed_and_policy_switch_recalculates(eval_admin, company):
    create_weights(eval_admin, company)
    supplier = make_supplier(company, "S-E9")
    evaluation_id = create_evaluation(eval_admin, company, supplier).json()["id"]
    put_lines(eval_admin, evaluation_id, {"cost": None})
    assert eval_admin.get(f"{EVALUATIONS_URL}{evaluation_id}/").json()["total_score"] == "68.50"

    switched = eval_admin.patch(
        f"{EVALUATIONS_URL}{evaluation_id}/",
        {"missing_dimension_policy": "redistribute", "remark": "改口径"},
        format="json",
    )
    assert switched.status_code == 200, switched.content
    body = switched.json()
    assert body["missing_dimension_policy"] == "redistribute"
    assert body["total_score"] == "76.12"
    assert body["grade"] == "B"
    assert body["remark"] == "改口径"


def test_invalid_period_range_is_rejected(eval_admin, company):
    create_weights(eval_admin, company)
    supplier = make_supplier(company, "S-E10")
    response = create_evaluation(
        eval_admin, company, supplier, period_start="2026-06-30", period_end="2026-06-01"
    )
    assert response.status_code == 400, response.content
    assert response.json()["code"] == "INVALID_PERIOD_RANGE"


def test_evaluation_is_company_scoped_and_needs_permissions(eval_admin, eval_viewer, company, other_company):
    create_weights(eval_admin, company)
    foreign_supplier = make_supplier(other_company, "S-FOREIGN-E")
    foreign_evaluation = SupplierEvaluation.objects.create(
        company=other_company,
        evaluation_no="SEV-OTH-1",
        supplier=foreign_supplier,
        weight_config=SupplierEvaluationWeight.objects.create(
            company=other_company, quality_weight=100, version_no=1
        ),
    )

    # 跨公司发起评价：供应商与公司不一致，直接拒绝
    mismatched = create_evaluation(eval_admin, company, foreign_supplier)
    assert mismatched.status_code == 400, mismatched.content
    assert mismatched.json()["code"] == "COMPANY_SUPPLIER_MISMATCH"

    # 写入其它公司的归属被数据范围拦住
    out_of_scope = create_evaluation(eval_admin, other_company, foreign_supplier)
    assert out_of_scope.status_code == 403, out_of_scope.content
    assert out_of_scope.json()["code"] == "OUT_OF_DATA_SCOPE"

    # 列表只看到本公司的评价
    listed = eval_admin.get(EVALUATIONS_URL)
    assert listed.status_code == 200, listed.content
    ids = {row["id"] for row in listed.json()["results"]}
    assert foreign_evaluation.pk not in ids

    # 只读用户能看不能写
    assert eval_viewer.get(EVALUATIONS_URL).status_code == 200
    denied = eval_viewer.post(EVALUATIONS_URL, {"supplier_id": 1}, format="json")
    assert denied.status_code == 403, denied.content


def test_viewer_without_weight_permission_cannot_read_or_write_weights(eval_viewer):
    assert eval_viewer.get(WEIGHTS_URL).status_code == 403
    assert eval_viewer.post(WEIGHTS_URL, BASE_WEIGHTS, format="json").status_code == 403


def test_evaluation_statistics_separate_incomplete_from_complete(eval_admin, company):
    """平均分只统计口径完整的评价；「没有数据」的维度单独计数，不记 0 分。"""
    create_weights(eval_admin, company)
    complete = create_evaluation(eval_admin, company, make_supplier(company, "S-S1")).json()["id"]
    put_lines(eval_admin, complete)
    eval_admin.post(f"{EVALUATIONS_URL}{complete}/publish/", {}, format="json")

    partial = create_evaluation(
        eval_admin, company, make_supplier(company, "S-S2"),
        missing_dimension_policy="mark_missing",
    ).json()["id"]
    put_lines(eval_admin, partial, {"cost": None})

    stats = eval_admin.get(EVALUATION_STATS_URL)
    assert stats.status_code == 200, stats.content
    body = stats.json()
    assert body["total"] == 2
    assert body["effective_total"] == 1
    assert body["draft_total"] == 1
    assert body["ungraded_total"] == 1
    assert body["avg_total_score"] == "73.50"
    assert body["line_total"] == 10
    assert body["line_missing_total"] == 1
    by_grade = {row["value"]: row["total"] for row in body["by_grade"]}
    assert by_grade["C"] == 1
    # 只有口径完整的那条被赋予了等级；缺数据的评价不会被贴一个等级
    assert sum(by_grade.values()) == 1
    by_dimension = {row["value"]: row for row in body["by_dimension"]}
    assert by_dimension["cost"]["scored_total"] == 1
    assert by_dimension["cost"]["missing_total"] == 1
    assert by_dimension["cost"]["avg_score"] == "50.00"
    assert by_dimension["quality"]["avg_score"] == "90.00"
