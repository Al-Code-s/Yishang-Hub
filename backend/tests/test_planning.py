"""计划模块用例（任务书 9.5、10.6、14.2 案例 13）。

覆盖：

* BOM / 工艺路线的版本化：草稿可改、提交冻结、审核通过后唯一生效，
  变更只能派生新版本（已审核版本的内容与快照不受影响）；
* 版本号在同一「款式 + SKU 范围」内自增，并由 (company, scope_key, version_no) 唯一约束兜底；
* 损耗率边界 [0, 1)、含损耗用量由后端计算、替代料行校验、工序顺序重复与标工非负；
* 审批通过时旧版本自动转 `obsolete`（只改状态，内容不动）；
* 作废必须填原因；审核中不允许派生新版本或作废；
* 快照内容与版本一致，且不随派生新版本而变化；
* 操作权限、数据范围、跨公司隔离与乐观锁。

库存无关：本模块不触碰库存服务，因此不涉及库存余额断言。
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction

from apps.core.exceptions import ValidationFailed
from apps.core.models import AuditLog, CodeRule, ResetPeriod
from apps.factory.models import Workshop
from apps.identity.models import DataScopeType, ScopeDimension
from apps.masterdata.models import Color, Material, MaterialCategory, Size, Sku, Style, UoM
from apps.planning import services
from apps.planning.models import Bom, BomLineType, BomStatus, Routing, RoutingStatus
from tests.conftest import make_role, make_user

pytestmark = pytest.mark.django_db

BOMS_URL = "/api/v1/planning/boms/"
ROUTINGS_URL = "/api/v1/planning/routings/"
INSTANCES_URL = "/api/v1/workflow/instances/"
META_URL = "/api/v1/meta/"
LOGIN_URL = "/api/v1/identity/auth/login/"
PASSWORD = "Tst!Passw0rd2026"

PLANNING_PERMISSIONS = [
    "planning.bom.view",
    "planning.bom.create",
    "planning.bom.update",
    "planning.bom.submit",
    "planning.bom.obsolete",
    "planning.routing.view",
    "planning.routing.create",
    "planning.routing.update",
    "planning.routing.submit",
    "planning.routing.obsolete",
    "workflow.instance.view",
    "workflow.instance.withdraw",
    "masterdata.style.view",
    "masterdata.sku.view",
    "masterdata.material.view",
]


def login(client, user) -> None:
    response = client.post(LOGIN_URL, {"username": user.username, "password": PASSWORD}, format="json")
    assert response.status_code == 200, response.content


@pytest.fixture
def planning_code_rules(db):
    """取号依赖编码规则；测试库不跑 bootstrap_system，这里显式建规则。"""
    for code, name, pattern in (
        ("BOM", "BOM 编号", "BOM{YYYYMMDD}{SEQ:4}"),
        ("ROUTING", "工艺路线编号", "RT{YYYYMMDD}{SEQ:4}"),
    ):
        CodeRule.objects.update_or_create(
            code=code,
            defaults={
                "name": name,
                "pattern": pattern,
                "reset_period": ResetPeriod.DAILY,
                "is_active": True,
            },
        )


@pytest.fixture
def env(company, other_company, department_factory, planning_code_rules):
    """最小计划环境：款式 / SKU / 物料 / 车间 + 服务层超级管理员。"""
    category = MaterialCategory.objects.create(
        code="PLN-CAT", name="计划物料分类", category_type="fabric"
    )
    other_category = MaterialCategory.objects.create(
        code="PLN-OTH-CAT", name="对照分类", category_type="fabric"
    )
    uom_kg = UoM.objects.create(code="PLN-KG", name="千克", category="weight")
    uom_pc = UoM.objects.create(code="PLN-PC", name="件", category="quantity")
    fabric = Material.objects.create(
        company=company, code="PLN-FAB", name="计划面料", category=category, base_uom=uom_kg
    )
    button = Material.objects.create(
        company=company, code="PLN-BTN", name="计划纽扣", category=category, base_uom=uom_pc
    )
    thread = Material.objects.create(
        company=company, code="PLN-THR", name="计划缝纫线", category=category, base_uom=uom_pc
    )
    other_material = Material.objects.create(
        company=other_company,
        code="PLN-OTH",
        name="对照物料",
        category=other_category,
        base_uom=uom_kg,
    )
    style = Style.objects.create(company=company, code="PLN-ST1", name="计划款式", size_group="women")
    other_style = Style.objects.create(company=other_company, code="PLN-ST2", name="对照款式")
    color = Color.objects.create(code="PLN-BK", name="黑色")
    size = Size.objects.create(code="PLN-M", name="M")
    sku = Sku.objects.create(
        company=company, style=style, color=color, size=size, code="PLN-ST1-BK-M"
    )
    workshop = Workshop.objects.create(
        factory=department_factory["factories"]["F01"],
        code="PLN-SEW",
        name="缝制车间",
        workshop_type="sewing",
    )
    return {
        "company": company,
        "other_company": other_company,
        "category": category,
        "uom_kg": uom_kg,
        "uom_pc": uom_pc,
        "fabric": fabric,
        "button": button,
        "thread": thread,
        "other_material": other_material,
        "style": style,
        "other_style": other_style,
        "sku": sku,
        "workshop": workshop,
        "svc_user": make_user(username="pln_svc", company=company, is_superuser=True),
    }

def _make_api_user(registry_permissions, company, username: str, perms: list[str]):
    role = make_role(
        code=f"test_pln_{username}",
        permission_codes=perms,
        data_scope_type=DataScopeType.COMPANY,
        company=company,
    )
    return role, make_user(username=username, role=role, company=company)


@pytest.fixture
def api_user_client(registry_permissions, company):
    """每个身份一个独立 APIClient，避免会话互相覆盖。"""
    from rest_framework.test import APIClient

    def _make(username: str, perms: list[str]):
        user = _make_api_user(registry_permissions, company, username, perms)[1]
        client = APIClient()
        login(client, user)
        return client

    return _make


@pytest.fixture
def planner_client(api_user_client):
    return api_user_client("pln_planner", PLANNING_PERMISSIONS)


@pytest.fixture
def approver_role(registry_permissions, company):
    return _make_api_user(
        registry_permissions,
        company,
        "pln_approver",
        ["workflow.instance.view", "workflow.instance.approve", "planning.bom.view"],
    )[0]


@pytest.fixture
def approver_client(registry_permissions, company, approver_role):
    from rest_framework.test import APIClient

    client = APIClient()
    login(client, make_user(username="pln_approver_u", role=approver_role, company=company))
    return client


@pytest.fixture
def planning_templates(db, approver_role):
    """BOM 与工艺路线各一个单节点审批模板（与 seed_demo 的 AP-BOM / AP-ROUTING 同构）。"""
    from apps.workflow.models import ApprovalTemplate, ApprovalTemplateNode

    for code, name, biz_type in (
        ("TPL-BOM-T", "BOM 审批", services.BIZ_TYPE_BOM),
        ("TPL-RT-T", "工艺路线审批", services.BIZ_TYPE_ROUTING),
    ):
        template = ApprovalTemplate.objects.create(
            code=code, name=name, biz_type=biz_type, is_active=True
        )
        ApprovalTemplateNode.objects.create(
            template=template,
            seq=1,
            name="部门主管审批",
            approver_type="role",
            approver_role=approver_role,
        )


def _bom_payload(env, **extra) -> dict:
    payload = {
        "style_id": env["style"].pk,
        "lines": [
            {"material_id": env["fabric"].pk, "quantity": "0.280000", "loss_rate": "0.060000"},
            {"material_id": env["button"].pk, "quantity": "4"},
        ],
    }
    payload.update(extra)
    return payload


def _routing_payload(env, **extra) -> dict:
    payload = {"style_id": env["style"].pk}
    payload.update(extra)
    return payload


def _create_bom(client, env, **extra) -> dict:
    response = client.post(BOMS_URL, _bom_payload(env, **extra), format="json")
    assert response.status_code == 201, response.content
    return response.json()


def _create_routing(client, env, **extra) -> dict:
    response = client.post(ROUTINGS_URL, _routing_payload(env, **extra), format="json")
    assert response.status_code == 201, response.content
    return response.json()


def _approve(client, url: str, pk: int, approver_client) -> dict:
    submitted = client.post(f"{url}{pk}/submit/", {}, format="json")
    assert submitted.status_code == 200, submitted.content
    instance_id = submitted.json()["approval_instance_id"]
    approved = approver_client.post(
        f"{INSTANCES_URL}{instance_id}/approve/", {"comment": "同意"}, format="json"
    )
    assert approved.status_code == 200, approved.content
    return approved.json()


# ---------------------------------------------------------------------------
# 认证与权限
# ---------------------------------------------------------------------------


def test_planning_endpoints_require_authentication(api_client):
    assert api_client.get(BOMS_URL).status_code in (401, 403)
    assert api_client.get(ROUTINGS_URL).status_code in (401, 403)


def test_view_only_user_cannot_create_bom(api_client, registry_permissions, company, env):
    user = _make_api_user(registry_permissions, company, "pln_viewer", ["planning.bom.view"])[1]
    login(api_client, user)
    assert api_client.get(BOMS_URL).status_code == 200
    response = api_client.post(BOMS_URL, _bom_payload(env), format="json")
    assert response.status_code == 403, response.content


def test_routing_permission_does_not_grant_bom_write(api_client, registry_permissions, company, env):
    """权限按编码逐条生效：只有工艺路线权限不能新增 BOM。"""
    user = _make_api_user(
        registry_permissions, company, "pln_rt_only", ["planning.routing.view"]
    )[1]
    login(api_client, user)
    assert api_client.get(ROUTINGS_URL).status_code == 200
    assert api_client.post(BOMS_URL, _bom_payload(env), format="json").status_code == 403
    assert api_client.get(BOMS_URL).status_code == 403


def test_cross_company_objects_are_rejected(planner_client, env):
    """跨公司 ID 不能绕过数据范围：款式与物料都必须属于目标公司。"""
    response = planner_client.post(
        BOMS_URL,
        {
            "style_id": env["other_style"].pk,
            "lines": [{"material_id": env["fabric"].pk, "quantity": "1"}],
        },
        format="json",
    )
    assert response.status_code == 400
    assert response.json()["code"] == "COMPANY_STYLE_MISMATCH"

    response = planner_client.post(
        BOMS_URL,
        {
            "style_id": env["style"].pk,
            "lines": [{"material_id": env["other_material"].pk, "quantity": "1"}],
        },
        format="json",
    )
    assert response.status_code == 400
    assert response.json()["code"] == "COMPANY_MATERIAL_MISMATCH"

# ---------------------------------------------------------------------------
# BOM 创建与校验
# ---------------------------------------------------------------------------


def test_create_bom_persists_lines_and_computes_gross_quantity(planner_client, env):
    body = _create_bom(planner_client, env)
    assert body["code"].startswith("BOM")
    assert body["status"] == BomStatus.DRAFT
    assert body["version_no"] == 1
    assert body["scope_label"] == "款式通用"
    assert body["line_count"] == 2
    first = body["lines"][0]
    # 含损耗用量由后端计算：0.28 × 1.06 = 0.2968
    assert first["gross_quantity"] == "0.296800"
    assert first["uom_id"] == env["uom_kg"].pk  # 未指定单位时回落物料基本单位
    assert body["lines"][1]["loss_rate"] == "0.0000000000"
    assert [line["line_no"] for line in body["lines"]] == [1, 2]


def test_client_supplied_gross_quantity_is_ignored(planner_client, env):
    """派生值不接受前端提交：传了也被后端覆盖。"""
    body = _create_bom(
        planner_client,
        env,
        lines=[
            {
                "material_id": env["fabric"].pk,
                "quantity": "1",
                "loss_rate": "0.5",
                "gross_quantity": "999999",
            }
        ],
    )
    assert body["lines"][0]["gross_quantity"] == "1.500000"


@pytest.mark.parametrize("loss_rate", ["1", "1.5", "-0.1"])
def test_bom_loss_rate_out_of_range_is_rejected(planner_client, env, loss_rate):
    response = planner_client.post(
        BOMS_URL,
        {
            "style_id": env["style"].pk,
            "lines": [
                {"material_id": env["fabric"].pk, "quantity": "1", "loss_rate": loss_rate}
            ],
        },
        format="json",
    )
    assert response.status_code == 400, response.content


def test_bom_quantity_must_be_positive(planner_client, env):
    response = planner_client.post(
        BOMS_URL,
        {
            "style_id": env["style"].pk,
            "lines": [{"material_id": env["fabric"].pk, "quantity": "0"}],
        },
        format="json",
    )
    assert response.status_code == 400


def test_bom_without_lines_is_rejected(planner_client, env):
    response = planner_client.post(
        BOMS_URL, {"style_id": env["style"].pk, "lines": []}, format="json"
    )
    assert response.status_code == 400


def test_duplicate_normal_material_is_rejected(planner_client, env):
    response = planner_client.post(
        BOMS_URL,
        {
            "style_id": env["style"].pk,
            "lines": [
                {"material_id": env["fabric"].pk, "quantity": "1"},
                {"material_id": env["fabric"].pk, "quantity": "2"},
            ],
        },
        format="json",
    )
    assert response.status_code == 400
    assert "重复" in response.json()["message"]


def test_substitute_line_links_to_normal_line(planner_client, env):
    body = _create_bom(
        planner_client,
        env,
        lines=[
            {"material_id": env["fabric"].pk, "quantity": "1"},
            {"material_id": env["thread"].pk, "quantity": "2", "line_type": "normal"},
            {
                "material_id": env["button"].pk,
                "quantity": "3",
                "line_type": "substitute",
                "substitute_for_line_no": 2,
            },
        ],
    )
    substitute = [line for line in body["lines"] if line["line_type"] == BomLineType.SUBSTITUTE]
    assert len(substitute) == 1
    assert substitute[0]["substitute_for_line_no"] == 2


def test_substitute_for_unknown_line_is_rejected(planner_client, env):
    response = planner_client.post(
        BOMS_URL,
        {
            "style_id": env["style"].pk,
            "lines": [
                {"material_id": env["fabric"].pk, "quantity": "1"},
                {
                    "material_id": env["button"].pk,
                    "quantity": "1",
                    "line_type": "substitute",
                    "substitute_for_line_no": 99,
                },
            ],
        },
        format="json",
    )
    assert response.status_code == 400
    assert response.json()["code"] == "INVALID_SUBSTITUTE"


def test_normal_line_cannot_reference_substitute_target(planner_client, env):
    response = planner_client.post(
        BOMS_URL,
        {
            "style_id": env["style"].pk,
            "lines": [
                {
                    "material_id": env["fabric"].pk,
                    "quantity": "1",
                    "substitute_for_line_no": 1,
                }
            ],
        },
        format="json",
    )
    assert response.status_code == 400


def test_bom_effective_range_must_be_ordered(planner_client, env):
    response = planner_client.post(
        BOMS_URL,
        _bom_payload(env, effective_from="2026-05-01", effective_to="2026-04-01"),
        format="json",
    )
    assert response.status_code == 400


def test_inactive_style_cannot_be_used(planner_client, env):
    env["style"].is_active = False
    env["style"].save(update_fields=["is_active", "updated_at"])
    response = planner_client.post(BOMS_URL, _bom_payload(env), format="json")
    assert response.status_code == 400
    assert response.json()["code"] == "STYLE_INACTIVE"


def test_sku_must_belong_to_style(planner_client, env, company):
    other_style = Style.objects.create(company=company, code="PLN-ST9", name="另一个款式")
    other_sku = Sku.objects.create(
        company=company,
        style=other_style,
        color=Color.objects.create(code="PLN-WH", name="白色"),
        size=Size.objects.create(code="PLN-L", name="L"),
        code="PLN-ST9-WH-L",
    )
    response = planner_client.post(
        BOMS_URL,
        {
            "style_id": env["style"].pk,
            "sku_id": other_sku.pk,
            "lines": [{"material_id": env["fabric"].pk, "quantity": "1"}],
        },
        format="json",
    )
    assert response.status_code == 400
    assert response.json()["code"] == "SKU_STYLE_MISMATCH"

# ---------------------------------------------------------------------------
# 版本、审核与快照
# ---------------------------------------------------------------------------


def test_version_no_increments_within_scope(planner_client, env):
    first = _create_bom(planner_client, env)
    second = _create_bom(planner_client, env)
    assert (first["version_no"], second["version_no"]) == (1, 2)
    # SKU 差异版本使用独立范围，重新从 1 开始
    third = _create_bom(planner_client, env, sku_id=env["sku"].pk)
    assert third["version_no"] == 1
    assert third["scope_label"] == f"SKU {env['sku'].pk}"


def test_scope_version_unique_constraint_is_enforced(env):
    """即使服务层判断失效，数据库唯一约束也必须兜底（MySQL 联合唯一 + 非空 scope_key）。"""
    Bom.objects.create(
        company=env["company"], code="BOM-DUP-1", style=env["style"], version_no=1
    )
    with pytest.raises(IntegrityError), transaction.atomic():
        Bom.objects.create(
            company=env["company"], code="BOM-DUP-2", style=env["style"], version_no=1
        )


def test_draft_can_be_updated_but_submitted_cannot(planner_client, env, planning_templates, approver_client):
    body = _create_bom(planner_client, env)
    response = planner_client.patch(
        f"{BOMS_URL}{body['id']}/",
        {"remark": "调整损耗", "lines": [{"material_id": env["fabric"].pk, "quantity": "0.5"}]},
        format="json",
    )
    assert response.status_code == 200, response.content
    assert response.json()["remark"] == "调整损耗"
    assert response.json()["line_count"] == 1

    submitted = planner_client.post(f"{BOMS_URL}{body['id']}/submit/", {}, format="json")
    assert submitted.status_code == 200
    assert submitted.json()["status"] == BomStatus.SUBMITTED

    locked = planner_client.patch(
        f"{BOMS_URL}{body['id']}/",
        {"lines": [{"material_id": env["fabric"].pk, "quantity": "9"}]},
        format="json",
    )
    assert locked.status_code == 409
    assert locked.json()["code"] == "BOM_LOCKED"


def test_optimistic_lock_rejects_stale_version(planner_client, env):
    body = _create_bom(planner_client, env)
    response = planner_client.patch(
        f"{BOMS_URL}{body['id']}/", {"remark": "x", "expected_version": 999}, format="json"
    )
    assert response.status_code == 409


def test_submit_requires_approval_template(planner_client, env):
    """没有可用模板时明确拒绝，而不是静默跳过审批。"""
    body = _create_bom(planner_client, env)
    response = planner_client.post(f"{BOMS_URL}{body['id']}/submit/", {}, format="json")
    assert response.status_code == 404
    assert response.json()["code"] == "APPROVAL_TEMPLATE_NOT_FOUND"


def test_approve_activates_version_and_obsoletes_previous(
    planner_client, env, planning_templates, approver_client
):
    first = _create_bom(planner_client, env)
    _approve(planner_client, BOMS_URL, first["id"], approver_client)
    first_row = Bom.objects.get(pk=first["id"])
    assert first_row.status == BomStatus.APPROVED
    assert first_row.approved_at is not None
    assert first_row.approved_by_id is not None

    # 派生新版本并审核通过 → 旧版本自动作废，内容不变
    second = planner_client.post(f"{BOMS_URL}{first['id']}/new-version/", {}, format="json")
    assert second.status_code == 201, second.content
    assert second.json()["version_no"] == 2
    assert second.json()["status"] == BomStatus.DRAFT
    _approve(planner_client, BOMS_URL, second.json()["id"], approver_client)

    first_row.refresh_from_db()
    second_row = Bom.objects.get(pk=second.json()["id"])
    assert second_row.status == BomStatus.APPROVED
    assert first_row.status == BomStatus.OBSOLETE
    # 旧版本内容不得被改写
    assert first_row.lines.count() == 2
    assert [str(line.quantity) for line in first_row.lines.order_by("line_no")] == [
        "0.280000",
        "4.000000",
    ]


def test_new_version_from_submitted_is_rejected(planner_client, env, planning_templates):
    body = _create_bom(planner_client, env)
    planner_client.post(f"{BOMS_URL}{body['id']}/submit/", {}, format="json")
    response = planner_client.post(f"{BOMS_URL}{body['id']}/new-version/", {}, format="json")
    assert response.status_code == 409


def test_snapshot_matches_version_and_survives_new_version(
    planner_client, env, planning_templates, approver_client
):
    body = _create_bom(planner_client, env)
    _approve(planner_client, BOMS_URL, body["id"], approver_client)

    snapshot = planner_client.get(f"{BOMS_URL}{body['id']}/snapshot/")
    assert snapshot.status_code == 200, snapshot.content
    data = snapshot.json()
    assert data["bom_code"] == body["code"]
    assert data["status"] == BomStatus.APPROVED
    assert data["version_no"] == 1
    assert data["line_count"] == 2
    assert data["lines"][0]["gross_quantity"] == "0.296800"
    assert data["lines"][0]["material_code"] == env["fabric"].code

    planner_client.post(f"{BOMS_URL}{body['id']}/new-version/", {}, format="json")
    again = planner_client.get(f"{BOMS_URL}{body['id']}/snapshot/").json()
    assert again == data


def test_bom_snapshot_service_equals_api(planner_client, env, planning_templates, approver_client):
    body = _create_bom(planner_client, env)
    _approve(planner_client, BOMS_URL, body["id"], approver_client)
    row = Bom.objects.get(pk=body["id"])
    assert services.build_bom_snapshot(row) == planner_client.get(
        f"{BOMS_URL}{body['id']}/snapshot/"
    ).json()


def test_obsolete_requires_reason(planner_client, env):
    body = _create_bom(planner_client, env)
    response = planner_client.post(f"{BOMS_URL}{body['id']}/obsolete/", {}, format="json")
    assert response.status_code == 400


def test_obsolete_marks_version_inactive(planner_client, env, planning_templates, approver_client):
    body = _create_bom(planner_client, env)
    _approve(planner_client, BOMS_URL, body["id"], approver_client)
    response = planner_client.post(
        f"{BOMS_URL}{body['id']}/obsolete/", {"reason": "款式停产"}, format="json"
    )
    assert response.status_code == 200, response.content
    row = Bom.objects.get(pk=body["id"])
    assert row.status == BomStatus.OBSOLETE
    assert row.is_active is False
    # 生效版本查询不再返回它
    assert services.get_effective_bom(env["company"], env["style"]) is None


def test_obsolete_submitted_is_rejected(planner_client, env, planning_templates):
    body = _create_bom(planner_client, env)
    planner_client.post(f"{BOMS_URL}{body['id']}/submit/", {}, format="json")
    response = planner_client.post(
        f"{BOMS_URL}{body['id']}/obsolete/", {"reason": "不再需要"}, format="json"
    )
    assert response.status_code == 409


def test_reject_returns_document_to_rejected_state(
    planner_client, env, planning_templates, approver_client
):
    body = _create_bom(planner_client, env)
    submitted = planner_client.post(f"{BOMS_URL}{body['id']}/submit/", {}, format="json")
    instance_id = submitted.json()["approval_instance_id"]
    rejected = approver_client.post(
        f"{INSTANCES_URL}{instance_id}/reject/", {"comment": "用量待确认"}, format="json"
    )
    assert rejected.status_code == 200, rejected.content
    assert Bom.objects.get(pk=body["id"]).status == BomStatus.REJECTED


def test_withdraw_returns_document_to_draft(
    planner_client, env, planning_templates, approver_client
):
    body = _create_bom(planner_client, env)
    submitted = planner_client.post(f"{BOMS_URL}{body['id']}/submit/", {}, format="json")
    instance_id = submitted.json()["approval_instance_id"]
    withdrawn = planner_client.post(
        f"{INSTANCES_URL}{instance_id}/withdraw/", {"comment": "先撤回"}, format="json"
    )
    assert withdrawn.status_code == 200, withdrawn.content
    assert Bom.objects.get(pk=body["id"]).status == BomStatus.DRAFT


def test_effective_bom_returns_approved_only(planner_client, env, planning_templates, approver_client):
    draft = _create_bom(planner_client, env)
    assert services.get_effective_bom(env["company"], env["style"]) is None
    _approve(planner_client, BOMS_URL, draft["id"], approver_client)
    effective = services.get_effective_bom(env["company"], env["style"])
    assert effective is not None and effective.pk == draft["id"]
    # 其他公司查不到本公司的生效版本
    assert services.get_effective_bom(env["other_company"], env["style"]) is None


def test_key_actions_are_audited(planner_client, env, planning_templates, approver_client):
    body = _create_bom(planner_client, env)
    _approve(planner_client, BOMS_URL, body["id"], approver_client)
    actions = set(
        AuditLog.objects.filter(object_type="planning.Bom", object_id=str(body["id"])).values_list(
            "action", flat=True
        )
    )
    assert {"create", "submit", "approve"} <= actions

# ---------------------------------------------------------------------------
# 工艺路线
# ---------------------------------------------------------------------------


def test_create_routing_applies_default_steps(planner_client, env):
    body = _create_routing(planner_client, env)
    assert body["code"].startswith("RT")
    assert body["status"] == RoutingStatus.DRAFT
    assert body["version_no"] == 1
    # 任务书 9.5 默认工艺：裁剪 → 缝制 → 整烫 → 检验 → 包装
    assert [step["name"] for step in body["steps"]] == ["裁剪", "缝制", "整烫", "检验", "包装"]
    assert body["step_count"] == 5
    assert body["quality_gate_count"] == 1
    assert [step["is_quality_gate"] for step in body["steps"]] == [
        False,
        False,
        False,
        True,
        False,
    ]


def test_create_routing_with_explicit_steps(planner_client, env):
    body = _create_routing(
        planner_client,
        env,
        steps=[
            {
                "sequence": 10,
                "name": "裁剪",
                "workshop_id": env["workshop"].pk,
                "workcenter": "一号裁剪线",
                "standard_hours": "0.08",
                "is_quality_gate": True,
            },
            {"name": "缝制", "standard_hours": "0.35"},
        ],
    )
    steps = body["steps"]
    # 步骤按工序顺序返回；未提供 sequence 的行按行序自动编排（第二行 → 2）
    assert [step["sequence"] for step in steps] == [2, 10]
    by_name = {step["name"]: step for step in steps}
    assert by_name["裁剪"]["workshop_id"] == env["workshop"].pk
    assert by_name["裁剪"]["standard_hours"] == "0.080000"
    assert by_name["裁剪"]["is_quality_gate"] is True
    assert by_name["缝制"]["workshop_id"] is None


def test_duplicate_routing_sequence_is_rejected(planner_client, env):
    response = planner_client.post(
        ROUTINGS_URL,
        _routing_payload(
            env,
            steps=[
                {"sequence": 1, "name": "裁剪"},
                {"sequence": 1, "name": "缝制"},
            ],
        ),
        format="json",
    )
    assert response.status_code == 400
    assert response.json()["code"] == "DUPLICATE_SEQUENCE"


def test_negative_standard_hours_is_rejected(planner_client, env):
    response = planner_client.post(
        ROUTINGS_URL,
        _routing_payload(env, steps=[{"sequence": 1, "name": "裁剪", "standard_hours": "-1"}]),
        format="json",
    )
    assert response.status_code == 400


def test_routing_requires_at_least_one_step(planner_client, env):
    response = planner_client.post(ROUTINGS_URL, _routing_payload(env, steps=[]), format="json")
    assert response.status_code == 400


def test_routing_submit_and_approve(planner_client, env, planning_templates, approver_client):
    body = _create_routing(planner_client, env)
    approved = _approve(planner_client, ROUTINGS_URL, body["id"], approver_client)
    assert approved["status"] == RoutingStatus.APPROVED
    row = Routing.objects.get(pk=body["id"])
    assert row.approved_at is not None
    assert services.get_effective_routing(env["company"], env["style"]).pk == row.pk


def test_routing_new_version_copies_steps_and_obsoletes_previous(
    planner_client, env, planning_templates, approver_client
):
    body = _create_routing(planner_client, env)
    _approve(planner_client, ROUTINGS_URL, body["id"], approver_client)
    derived = planner_client.post(f"{ROUTINGS_URL}{body['id']}/new-version/", {}, format="json")
    assert derived.status_code == 201, derived.content
    assert derived.json()["version_no"] == 2
    assert [step["name"] for step in derived.json()["steps"]] == [
        "裁剪",
        "缝制",
        "整烫",
        "检验",
        "包装",
    ]
    _approve(planner_client, ROUTINGS_URL, derived.json()["id"], approver_client)
    assert Routing.objects.get(pk=body["id"]).status == RoutingStatus.OBSOLETE
    assert Routing.objects.get(pk=derived.json()["id"]).status == RoutingStatus.APPROVED


def test_routing_snapshot_contains_quality_gate(planner_client, env, planning_templates, approver_client):
    body = _create_routing(planner_client, env)
    _approve(planner_client, ROUTINGS_URL, body["id"], approver_client)
    snapshot = planner_client.get(f"{ROUTINGS_URL}{body['id']}/snapshot/")
    assert snapshot.status_code == 200, snapshot.content
    data = snapshot.json()
    assert data["routing_code"] == body["code"]
    assert data["step_count"] == 5
    assert data["steps"][3]["name"] == "检验"
    assert data["steps"][3]["is_quality_gate"] is True
    assert data["steps"][0]["standard_hours"] == "0.000000"


def test_routing_update_locks_after_submit(planner_client, env, planning_templates):
    body = _create_routing(planner_client, env)
    planner_client.post(f"{ROUTINGS_URL}{body['id']}/submit/", {}, format="json")
    response = planner_client.patch(
        f"{ROUTINGS_URL}{body['id']}/", {"remark": "改", "steps": [{"name": "裁剪"}]}, format="json"
    )
    assert response.status_code == 409
    assert response.json()["code"] == "ROUTING_LOCKED"


def test_routing_obsolete_requires_reason(planner_client, env):
    body = _create_routing(planner_client, env)
    assert planner_client.post(f"{ROUTINGS_URL}{body['id']}/obsolete/", {}, format="json").status_code == 400
    ok = planner_client.post(
        f"{ROUTINGS_URL}{body['id']}/obsolete/", {"reason": "工艺调整"}, format="json"
    )
    assert ok.status_code == 200, ok.content
    assert ok.json()["status"] == RoutingStatus.OBSOLETE


def test_routing_step_workshop_outside_scope_is_rejected(
    api_client, registry_permissions, company, department_factory, env
):
    """车间属于另一个工厂时，限定工厂范围的角色不能引用它（任务书 6.4）。"""
    from apps.factory.models import Factory

    other_factory = Factory.objects.create(company=company, code="F99", name="对照工厂")
    outside = Workshop.objects.create(
        factory=other_factory, code="PLN-OUT", name="范围外车间", workshop_type="sewing"
    )
    role = make_role(
        code="test_pln_scoped",
        permission_codes=PLANNING_PERMISSIONS,
        data_scope_type=DataScopeType.CUSTOM,
        company=company,
        grants=[(ScopeDimension.FACTORY, department_factory["factories"]["F01"].pk)],
    )
    login(api_client, make_user(username="pln_scoped", role=role, company=company))

    rejected = api_client.post(
        ROUTINGS_URL,
        _routing_payload(env, steps=[{"sequence": 1, "name": "裁剪", "workshop_id": outside.pk}]),
        format="json",
    )
    assert rejected.status_code == 403, rejected.content
    assert rejected.json()["code"] == "OUT_OF_DATA_SCOPE"

    # 范围内的车间可以正常引用
    accepted = api_client.post(
        ROUTINGS_URL,
        _routing_payload(env, steps=[{"sequence": 1, "name": "裁剪", "workshop_id": env["workshop"].pk}]),
        format="json",
    )
    assert accepted.status_code == 201, accepted.content


# ---------------------------------------------------------------------------
# 元数据
# ---------------------------------------------------------------------------


def test_meta_exposes_planning_enums(planner_client):
    response = planner_client.get(META_URL)
    assert response.status_code == 200, response.content
    body = response.json()
    assert {item["value"] for item in body["bom_statuses"]} == {
        "draft",
        "submitted",
        "approved",
        "rejected",
        "obsolete",
    }
    assert {item["value"] for item in body["routing_statuses"]} == {
        "draft",
        "submitted",
        "approved",
        "rejected",
        "obsolete",
    }
    assert {item["value"] for item in body["bom_line_types"]} == {"normal", "substitute"}


# ---------------------------------------------------------------------------
# 服务层防线（绕过接口直接调用）
# ---------------------------------------------------------------------------


def test_service_rejects_style_from_another_company(env):
    with pytest.raises(ValidationFailed):
        services.create_bom(
            user=env["svc_user"],
            company=env["other_company"],
            style=env["style"],
            lines=[{"material": env["fabric"], "quantity": Decimal("1")}],
        )


def test_service_rejects_material_from_another_company(env):
    with pytest.raises(ValidationFailed):
        services.create_bom(
            user=env["svc_user"],
            company=env["company"],
            style=env["style"],
            lines=[{"material": env["other_material"], "quantity": Decimal("1")}],
        )


def test_service_rejects_out_of_range_loss_rate(env):
    bom = services.create_bom(
        user=env["svc_user"],
        company=env["company"],
        style=env["style"],
        lines=[{"material": env["fabric"], "quantity": Decimal("1")}],
    )
    with pytest.raises(ValidationFailed):
        services.update_bom(
            bom,
            user=env["svc_user"],
            lines=[
                {
                    "material": env["fabric"],
                    "quantity": Decimal("1"),
                    "loss_rate": Decimal("2"),
                }
            ],
        )


def test_service_requires_reason_to_obsolete(env):
    bom = services.create_bom(
        user=env["svc_user"],
        company=env["company"],
        style=env["style"],
        lines=[{"material": env["fabric"], "quantity": Decimal("1")}],
    )
    with pytest.raises(ValidationFailed):
        services.obsolete_bom(bom, user=env["svc_user"], reason="   ")
