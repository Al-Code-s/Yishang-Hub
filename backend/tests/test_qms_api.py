"""质量管理接口用例（检验项目 / 检验单与判定 / 质量报警 / 问题知识库）。

覆盖要点：
* 数据范围在四个台账上一致生效；
* 检验项目编码、检验单号、报警编号、问题编号留空时按编码规则自动取号；
* **定量项目的合格与否只能由服务层按上下限判定**，客户端传的结论被忽略；
* 存在不合格项时不能判「合格」，全合格时不能判「不合格」，跳步一律 409；
* 判定不合格自动生成一条质量报警，同一检验单重复判定不会重复报警；
* 报警未闭环时检验单关不掉；关闭报警必须写处理说明；
* 报警可以沉淀为知识库条目并保留来源链路；
* 质量信息动态监测的合格率只统计已判定单据，「让步接收」单列。

全部走 HTTP 接口与真实 MySQL 约束，不使用 mock。
"""

from __future__ import annotations

import pytest

from apps.core.models import CodeRule, ResetPeriod
from apps.identity.models import DataScopeType
from apps.masterdata.models import Material, MaterialCategory, UoM
from apps.qms.models import (
    InspectionValueType,
    QualityAlert,
    QualityAlertStatus,
    QualityInspectionItem,
    QualityInspectionOrder,
    QualityInspectionStatus,
    QualityIssue,
    QualityIssueStatus,
    QualityJudgement,
)
from tests.conftest import make_role, make_user

pytestmark = pytest.mark.django_db

BASE = "/api/v1/qms"
ITEMS_URL = BASE + "/inspection-items/"
ORDERS_URL = BASE + "/inspections/"
ALERTS_URL = BASE + "/alerts/"
ISSUES_URL = BASE + "/issues/"
STATS_URL = ORDERS_URL + "statistics/"
LOGIN_URL = "/api/v1/identity/auth/login/"
PASSWORD = "Tst!Passw0rd2026"


def login(client, user) -> None:
    response = client.post(
        LOGIN_URL, {"username": user.username, "password": PASSWORD}, format="json"
    )
    assert response.status_code == 200, response.content


def qms_codes(registry_permissions) -> list[str]:
    return sorted(code for code in registry_permissions if code.startswith("qms."))


@pytest.fixture
def qms_code_rules(db):
    """取号依赖编码规则；测试库不跑 bootstrap_system，这里显式登记质量管理模块的规则。"""
    rules = {
        "QIT": ("QIT{YYYY}{SEQ:4}", ResetPeriod.YEARLY),
        "QC": ("QC{YYYYMMDD}{SEQ:4}", ResetPeriod.DAILY),
        "QAL": ("QAL{YYYYMMDD}{SEQ:4}", ResetPeriod.DAILY),
        "KI": ("KI{YYYYMMDD}{SEQ:4}", ResetPeriod.DAILY),
    }
    for code, (pattern, period) in rules.items():
        CodeRule.objects.update_or_create(
            code=code,
            defaults={"name": code, "pattern": pattern, "reset_period": period, "is_active": True},
        )


@pytest.fixture
def qms_admin(api_client, registry_permissions, company):
    role = make_role(
        code="test_qms_admin",
        permission_codes=qms_codes(registry_permissions),
        data_scope_type=DataScopeType.COMPANY,
        company=company,
    )
    user = make_user(username="qms_admin_t", role=role, company=company)
    login(api_client, user)
    return api_client


@pytest.fixture
def qms_viewer(api_client, registry_permissions, company):
    role = make_role(
        code="test_qms_viewer",
        permission_codes=[code for code in qms_codes(registry_permissions) if code.endswith(".view")],
        data_scope_type=DataScopeType.COMPANY,
        company=company,
    )
    user = make_user(username="qms_viewer_t", role=role, company=company)
    login(api_client, user)
    return api_client


def make_item(client, company, *, code="", name="克重", **extra):
    payload = {
        "company_id": company.pk,
        "code": code,
        "name": name,
        "category": "physical",
        "value_type": InspectionValueType.QUANTITATIVE,
        "unit": "g/m2",
        "lower_limit": "180",
        "upper_limit": "220",
    }
    payload.update(extra)
    return client.post(ITEMS_URL, payload, format="json")


def make_order(client, company, **extra):
    payload = {
        "company_id": company.pk,
        "inspection_type": "iqc",
        "batch_no": "B-001",
    }
    payload.update(extra)
    return client.post(ORDERS_URL, payload, format="json")


def record_results(client, order_id, rows):
    return client.post(ORDERS_URL + f"{order_id}/results/", {"results": rows}, format="json")


def test_inspection_item_code_is_generated_and_company_scoped(
    qms_admin, qms_code_rules, company, other_company
):
    created = make_item(qms_admin, company)
    assert created.status_code == 201, created.content
    assert created.json()["code"].startswith("QIT")
    # 对照公司的项目直接落库：COMPANY 数据范围不允许跨公司新增，只验证「看不到」
    QualityInspectionItem.objects.create(
        company=other_company,
        code="QIT-OTHER",
        name="对照项目",
        category="physical",
        value_type=InspectionValueType.QUANTITATIVE,
        lower_limit="1",
        upper_limit="2",
    )
    listed = qms_admin.get(ITEMS_URL)
    assert listed.status_code == 200, listed.content
    assert {row["company_id"] for row in listed.json()["results"]} == {company.pk}


def test_quantitative_item_requires_at_least_one_limit(qms_admin, qms_code_rules, company):
    rejected = make_item(qms_admin, company, lower_limit=None, upper_limit=None)
    assert rejected.status_code == 400, rejected.content
    # 定性项目不要求数值口径
    qualitative = make_item(
        qms_admin,
        company,
        name="外观",
        value_type=InspectionValueType.QUALITATIVE,
        lower_limit=None,
        upper_limit=None,
    )
    assert qualitative.status_code == 201, qualitative.content


def test_quantitative_result_is_judged_by_server(qms_admin, qms_code_rules, company):
    item_id = make_item(qms_admin, company).json()["id"]
    order_id = make_order(qms_admin, company).json()["id"]

    # 客户端谎报「合格」，实测值超上限：服务层必须按上下限判为不合格
    saved = record_results(
        qms_admin,
        order_id,
        [{"item_id": item_id, "measured_value": "260", "is_qualified": True}],
    )
    assert saved.status_code == 200, saved.content
    row = saved.json()["results"][0]
    assert row["is_qualified"] is False
    assert saved.json()["failed_count"] == 1


def test_qualitative_result_requires_declared_judgement(qms_admin, qms_code_rules, company):
    item_id = make_item(
        qms_admin,
        company,
        name="手感",
        value_type=InspectionValueType.QUALITATIVE,
        lower_limit=None,
        upper_limit=None,
    ).json()["id"]
    order_id = make_order(qms_admin, company).json()["id"]

    missing = record_results(qms_admin, order_id, [{"item_id": item_id, "text_value": "偏硬"}])
    assert missing.status_code == 400, missing.content

    declared = record_results(
        qms_admin, order_id, [{"item_id": item_id, "is_qualified": False, "text_value": "偏硬"}]
    )
    assert declared.status_code == 200, declared.content
    assert declared.json()["results"][0]["is_qualified"] is False


def test_submit_requires_results_and_status_cannot_be_patched(qms_admin, qms_code_rules, company):
    order_id = make_order(qms_admin, company).json()["id"]
    empty = qms_admin.post(ORDERS_URL + f"{order_id}/submit/", {}, format="json")
    assert empty.status_code == 400, empty.content

    patched = qms_admin.patch(
        ORDERS_URL + f"{order_id}/", {"status": QualityInspectionStatus.JUDGED}, format="json"
    )
    assert patched.status_code == 200, patched.content
    assert QualityInspectionOrder.objects.get(pk=order_id).status == QualityInspectionStatus.DRAFT

    skipped = qms_admin.post(ORDERS_URL + f"{order_id}/judge/", {}, format="json")
    assert skipped.status_code == 409, skipped.content


def test_judgement_cannot_contradict_results(qms_admin, qms_code_rules, company):
    item_id = make_item(qms_admin, company).json()["id"]
    order_id = make_order(qms_admin, company).json()["id"]
    record_results(qms_admin, order_id, [{"item_id": item_id, "measured_value": "260"}])
    qms_admin.post(ORDERS_URL + f"{order_id}/submit/", {}, format="json")

    lied = qms_admin.post(
        ORDERS_URL + f"{order_id}/judge/", {"judgement": "passed"}, format="json"
    )
    assert lied.status_code == 409, lied.content
    assert QualityInspectionOrder.objects.get(pk=order_id).judgement == QualityJudgement.PENDING


def test_failed_judgement_creates_single_alert_and_blocks_close(
    qms_admin, qms_code_rules, company
):
    item_id = make_item(qms_admin, company).json()["id"]
    order_id = make_order(qms_admin, company).json()["id"]
    record_results(qms_admin, order_id, [{"item_id": item_id, "measured_value": "260"}])
    qms_admin.post(ORDERS_URL + f"{order_id}/submit/", {}, format="json")

    judged = qms_admin.post(
        ORDERS_URL + f"{order_id}/judge/", {"judgement": "failed"}, format="json"
    )
    assert judged.status_code == 200, judged.content
    body = judged.json()
    assert body["judgement"] == QualityJudgement.FAILED
    assert body["alert_no"].startswith("QAL")
    assert QualityAlert.objects.filter(order_id=order_id).count() == 1

    # 报警没闭环时检验单关不掉
    blocked = qms_admin.post(ORDERS_URL + f"{order_id}/close/", {}, format="json")
    assert blocked.status_code == 409, blocked.content

    alert_id = body["alert_id"]
    # 关闭报警必须写处理说明
    assert (
        qms_admin.post(ALERTS_URL + f"{alert_id}/close/", {"remark": ""}, format="json").status_code
        == 400
    )
    handled = qms_admin.post(ALERTS_URL + f"{alert_id}/handle/", {}, format="json")
    assert handled.status_code == 200, handled.content
    assert handled.json()["status"] == QualityAlertStatus.HANDLING

    closed = qms_admin.post(
        ALERTS_URL + f"{alert_id}/close/", {"remark": "已返工复检合格"}, format="json"
    )
    assert closed.status_code == 200, closed.content
    assert closed.json()["status"] == QualityAlertStatus.CLOSED

    order_closed = qms_admin.post(ORDERS_URL + f"{order_id}/close/", {}, format="json")
    assert order_closed.status_code == 200, order_closed.content
    assert order_closed.json()["status"] == QualityInspectionStatus.CLOSED


def test_concession_requires_remark(qms_admin, qms_code_rules, company):
    item_id = make_item(qms_admin, company).json()["id"]
    order_id = make_order(qms_admin, company).json()["id"]
    record_results(qms_admin, order_id, [{"item_id": item_id, "measured_value": "260"}])
    qms_admin.post(ORDERS_URL + f"{order_id}/submit/", {}, format="json")

    rejected = qms_admin.post(
        ORDERS_URL + f"{order_id}/judge/", {"judgement": "concession"}, format="json"
    )
    assert rejected.status_code == 400, rejected.content

    accepted = qms_admin.post(
        ORDERS_URL + f"{order_id}/judge/",
        {"judgement": "concession", "judge_remark": "客户书面同意，限制使用"},
        format="json",
    )
    assert accepted.status_code == 200, accepted.content
    assert accepted.json()["judgement"] == QualityJudgement.CONCESSION
    # 让步接收不生成报警
    assert QualityAlert.objects.filter(order_id=order_id).count() == 0


def test_alert_can_be_turned_into_knowledge_base_entry(qms_admin, qms_code_rules, company):
    item_id = make_item(qms_admin, company).json()["id"]
    order_id = make_order(qms_admin, company).json()["id"]
    record_results(qms_admin, order_id, [{"item_id": item_id, "measured_value": "260"}])
    qms_admin.post(ORDERS_URL + f"{order_id}/submit/", {}, format="json")
    alert_id = qms_admin.post(
        ORDERS_URL + f"{order_id}/judge/", {"judgement": "failed"}, format="json"
    ).json()["alert_id"]

    created = qms_admin.post(
        ALERTS_URL + f"{alert_id}/create-issue/",
        {"title": "来料克重偏低", "category": "material", "cause": "供应商换批次"},
        format="json",
    )
    assert created.status_code == 201, created.content
    body = created.json()
    assert body["issue_no"].startswith("KI")
    assert body["status"] == QualityIssueStatus.DRAFT
    assert body["source_alert_id"] == alert_id
    assert body["source_order_id"] == order_id


def test_issue_publish_and_archive(qms_admin, qms_code_rules, company):
    created = qms_admin.post(
        ISSUES_URL,
        {"company_id": company.pk, "title": "车缝跳线", "phenomenon": "针距不均"},
        format="json",
    )
    assert created.status_code == 201, created.content
    issue_id = created.json()["id"]
    assert created.json()["issue_no"].startswith("KI")

    published = qms_admin.post(ISSUES_URL + f"{issue_id}/publish/", {}, format="json")
    assert published.status_code == 200, published.content
    assert published.json()["status"] == QualityIssueStatus.PUBLISHED

    # 已发布的条目不能再发布
    again = qms_admin.post(ISSUES_URL + f"{issue_id}/publish/", {}, format="json")
    assert again.status_code == 409, again.content

    archived = qms_admin.post(ISSUES_URL + f"{issue_id}/archive/", {}, format="json")
    assert archived.status_code == 200, archived.content
    assert archived.json()["status"] == QualityIssueStatus.ARCHIVED
    assert QualityIssue.objects.get(pk=issue_id).status == QualityIssueStatus.ARCHIVED


def test_statistics_pass_rate_excludes_undecided_orders(qms_admin, qms_code_rules, company):
    good_item = make_item(qms_admin, company, name="克重").json()["id"]
    bad_item = make_item(qms_admin, company, name="色差", category="appearance").json()["id"]

    passed_order = make_order(qms_admin, company, batch_no="B-OK").json()["id"]
    record_results(qms_admin, passed_order, [{"item_id": good_item, "measured_value": "200"}])
    qms_admin.post(ORDERS_URL + f"{passed_order}/submit/", {}, format="json")
    qms_admin.post(ORDERS_URL + f"{passed_order}/judge/", {}, format="json")

    failed_order = make_order(qms_admin, company, batch_no="B-NG").json()["id"]
    record_results(qms_admin, failed_order, [{"item_id": bad_item, "measured_value": "260"}])
    qms_admin.post(ORDERS_URL + f"{failed_order}/submit/", {}, format="json")
    qms_admin.post(ORDERS_URL + f"{failed_order}/judge/", {}, format="json")

    # 一张还没录入结果的草稿：不得进入合格率分母
    make_order(qms_admin, company, batch_no="B-DRAFT")

    stats = qms_admin.get(STATS_URL)
    assert stats.status_code == 200, stats.content
    body = stats.json()
    assert body["total"] == 3
    assert body["judged_total"] == 2
    assert body["passed_total"] == 1
    assert body["failed_total"] == 1
    assert body["pass_rate"] == "50.00"
    assert body["alert_open_total"] == 1
    assert [row["item_name"] for row in body["failed_items"]] == ["色差"]


def test_company_scope_applies_to_alerts_and_issues(
    qms_admin, qms_code_rules, company, other_company
):
    QualityAlert.objects.create(
        company=company, alert_no="QAL-MINE", title="本公司报警", level="major"
    )
    QualityAlert.objects.create(
        company=other_company, alert_no="QAL-OTHER", title="对照报警", level="major"
    )
    QualityIssue.objects.create(
        company=other_company,
        issue_no="KI-OTHER",
        title="对照问题",
        phenomenon="对照",
    )
    listed = qms_admin.get(ALERTS_URL)
    assert listed.status_code == 200, listed.content
    assert {row["alert_no"] for row in listed.json()["results"]} == {"QAL-MINE"}
    assert qms_admin.get(ISSUES_URL).json()["count"] == 0


def test_viewer_cannot_write(qms_viewer, qms_code_rules, company):
    item = QualityInspectionItem.objects.create(
        company=company,
        code="QIT-RO",
        name="克重",
        category="physical",
        value_type=InspectionValueType.QUANTITATIVE,
        lower_limit="180",
        upper_limit="220",
    )
    order = QualityInspectionOrder.objects.create(
        company=company, order_no="QC-RO", inspection_type="iqc"
    )

    denied = make_item(qms_viewer, company, name="越权项目")
    assert denied.status_code == 403, denied.content
    denied_result = record_results(
        qms_viewer, order.pk, [{"item_id": item.pk, "measured_value": "200"}]
    )
    assert denied_result.status_code == 403, denied_result.content
    # 只读角色仍可查看
    assert qms_viewer.get(ITEMS_URL).status_code == 200


def test_material_must_belong_to_same_company(qms_admin, qms_code_rules, company, other_company):
    category = MaterialCategory.objects.create(code="MC-QMS", name="面料")
    uom = UoM.objects.create(code="M", name="米")
    foreign = Material.objects.create(
        company=other_company, code="M-QMS-1", name="对照面料", category=category, base_uom=uom
    )
    rejected = make_order(qms_admin, company, material_id=foreign.pk)
    assert rejected.status_code == 400, rejected.content
