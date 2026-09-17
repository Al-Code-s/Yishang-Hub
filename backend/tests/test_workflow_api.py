"""审批流程接口用例（对应任务书 10.1 / 12.1 审批闭环与 14.2 必测案例）。

覆盖点：
* 顺序多级审批：第一级通过后才点亮第二级；
* 条件路由（金额 / 部门），未命中节点直接拒绝提交，绝不静默跳过；
* 默认禁止申请人审批自己的单据，模板显式开启后才允许；
* 驳回必须填写意见；撤回只能由申请人本人发起；
* 提交时写入模板快照，模板后续修改不影响历史实例；
* 待办列表只对真实候选审批人可见。
"""

from __future__ import annotations

import pytest

from apps.identity.models import DataScopeType
from apps.workflow.models import ApprovalInstance, InstanceStatus, StepStatus
from tests.conftest import make_role, make_user

pytestmark = pytest.mark.django_db

TEMPLATES_URL = "/api/v1/workflow/templates/"
INSTANCES_URL = "/api/v1/workflow/instances/"


def _login(client, user, password="Tst!Passw0rd2026"):
    response = client.post(
        "/api/v1/identity/auth/login/",
        {"username": user.username, "password": password},
        format="json",
    )
    assert response.status_code == 200, response.content
    return response


def _template_payload(code: str, nodes: list[dict], **extra) -> dict:
    return {
        "code": code,
        "name": f"模板-{code}",
        "biz_type": "generic.request",
        "description": "测试模板",
        "nodes": nodes,
        **extra,
    }

@pytest.fixture
def workflow_env(registry_permissions, company, department_factory):
    """申请人 / 一级审批人 / 二级审批人 / 无关用户，以及模板维护管理员。"""
    permissions = [
        "workflow.template.view", "workflow.template.create", "workflow.template.update",
        "workflow.instance.view", "workflow.instance.submit", "workflow.instance.approve",
        "workflow.instance.withdraw",
    ]
    applicant_role = make_role(
        code="wf_applicant",
        permission_codes=[
            "workflow.instance.view", "workflow.instance.submit", "workflow.instance.approve",
            "workflow.instance.withdraw",
        ],
        data_scope_type=DataScopeType.COMPANY, company=company,
    )
    l1_role = make_role(
        code="wf_l1",
        # 审批人通常同时可以撤回自己发起的申请，用它验证「非申请人不能撤回」
        permission_codes=[
            "workflow.instance.view", "workflow.instance.approve", "workflow.instance.withdraw",
        ],
        data_scope_type=DataScopeType.COMPANY, company=company,
    )
    l2_role = make_role(
        code="wf_l2", permission_codes=["workflow.instance.view", "workflow.instance.approve"],
        data_scope_type=DataScopeType.COMPANY, company=company,
    )
    admin_role = make_role(
        code="wf_admin", permission_codes=permissions,
        data_scope_type=DataScopeType.COMPANY, company=company,
    )
    return {
        "company": company,
        "departments": department_factory["departments"],
        "applicant_role": applicant_role,
        "l1_role": l1_role,
        "l2_role": l2_role,
        "admin_role": admin_role,
        "applicant": make_user(username="wf_applicant_u", role=applicant_role, company=company),
        "l1": make_user(username="wf_l1_u", role=l1_role, company=company),
        "l2": make_user(username="wf_l2_u", role=l2_role, company=company),
        "outsider": make_user(username="wf_outsider_u", role=applicant_role, company=company),
        "admin": make_user(username="wf_admin_u", role=admin_role, company=company),
    }


def _make_template(client, env, *, code="TPL1", nodes=None, **extra):
    nodes = nodes if nodes is not None else [
        {"seq": 1, "name": "一级审批", "approver_type": "role",
         "approver_role_id": env["l1_role"].pk},
        {"seq": 2, "name": "二级审批", "approver_type": "role",
         "approver_role_id": env["l2_role"].pk},
    ]
    _login(client, env["admin"])
    response = client.post(TEMPLATES_URL, _template_payload(code, nodes, **extra), format="json")
    assert response.status_code == 201, response.content
    return response.json()


def _create_instance(client, env, *, title="测试申请", amount=None, department_id=None, template_code="TPL1"):
    _login(client, env["applicant"])
    payload = {"title": title, "template_code": template_code, "biz_type": "generic.request"}
    if amount is not None:
        payload["amount"] = str(amount)
    if department_id is not None:
        payload["department_id"] = department_id
    response = client.post(INSTANCES_URL, payload, format="json")
    assert response.status_code in (200, 201), response.content
    return response.json()

def test_two_level_sequential_approval(api_client, workflow_env):
    _make_template(api_client, workflow_env)
    body = _create_instance(api_client, workflow_env, amount=1000)
    instance_id = body["id"]
    assert body["status"] == InstanceStatus.DRAFT

    response = api_client.post(f"{INSTANCES_URL}{instance_id}/submit/", {}, format="json")
    assert response.status_code == 200, response.content
    data = response.json()
    assert data["status"] == InstanceStatus.PENDING
    assert data["current_seq"] == 1
    assert [step["status"] for step in data["steps"]] == [StepStatus.PENDING, StepStatus.WAITING]

    _login(api_client, workflow_env["l2"])
    forbidden = api_client.post(f"{INSTANCES_URL}{instance_id}/approve/", {}, format="json")
    assert forbidden.status_code == 403
    assert forbidden.json()["code"] == "NOT_CURRENT_APPROVER"

    _login(api_client, workflow_env["l1"])
    first = api_client.post(f"{INSTANCES_URL}{instance_id}/approve/", {"comment": "一级同意"}, format="json")
    assert first.status_code == 200, first.content
    assert first.json()["current_seq"] == 2
    assert first.json()["status"] == InstanceStatus.PENDING

    _login(api_client, workflow_env["l2"])
    second = api_client.post(f"{INSTANCES_URL}{instance_id}/approve/", {"comment": "二级同意"}, format="json")
    assert second.status_code == 200, second.content
    final = second.json()
    assert final["status"] == InstanceStatus.APPROVED
    assert [step["status"] for step in final["steps"]] == [StepStatus.APPROVED, StepStatus.APPROVED]
    assert [log["action"] for log in final["logs"]] == ["submit", "approve", "approve"]


def test_amount_route_skips_unmatched_nodes(api_client, workflow_env):
    """金额 10 万以上才需要二级审批；小额申请只生成一个节点。"""
    _make_template(
        api_client, workflow_env, code="TPL_AMOUNT",
        nodes=[
            {"seq": 1, "name": "一级审批", "approver_type": "role",
             "approver_role_id": workflow_env["l1_role"].pk},
            {"seq": 2, "name": "大额复核", "approver_type": "role",
             "approver_role_id": workflow_env["l2_role"].pk, "amount_min": "100000"},
        ],
    )
    body = _create_instance(api_client, workflow_env, amount=500, template_code="TPL_AMOUNT")
    response = api_client.post(f"{INSTANCES_URL}{body['id']}/submit/", {}, format="json")
    assert response.status_code == 200, response.content
    assert len(response.json()["steps"]) == 1


def test_submit_rejected_when_no_node_matches(api_client, workflow_env):
    """模板设置了金额区间但申请金额不命中：拒绝提交，单据保持草稿。"""
    _make_template(
        api_client, workflow_env, code="TPL_HIGH",
        nodes=[
            {"seq": 1, "name": "大额审批", "approver_type": "role",
             "approver_role_id": workflow_env["l1_role"].pk, "amount_min": "100000"},
        ],
    )
    body = _create_instance(api_client, workflow_env, amount=1, template_code="TPL_HIGH")
    response = api_client.post(f"{INSTANCES_URL}{body['id']}/submit/", {}, format="json")
    assert response.status_code == 400
    assert response.json()["code"] == "APPROVAL_NO_MATCHING_NODE"
    assert ApprovalInstance.objects.get(pk=body["id"]).status == InstanceStatus.DRAFT

def test_self_approval_blocked_then_allowed_by_template_flag(api_client, workflow_env):
    """申请人自己也是审批人：默认必须被拒绝，模板显式开启后才放行。"""
    _make_template(
        api_client, workflow_env, code="TPL_SELF",
        nodes=[{"seq": 1, "name": "自审", "approver_type": "role",
                "approver_role_id": workflow_env["applicant_role"].pk}],
    )
    body = _create_instance(api_client, workflow_env, template_code="TPL_SELF")
    server = api_client.post(f"{INSTANCES_URL}{body['id']}/submit/", {}, format="json")
    assert server.status_code == 200, server.content

    blocked = api_client.post(f"{INSTANCES_URL}{body['id']}/approve/", {}, format="json")
    assert blocked.status_code == 403
    assert blocked.json()["code"] == "SELF_APPROVAL_FORBIDDEN"

    _login(api_client, workflow_env["admin"])
    patched = api_client.patch(
        f"{TEMPLATES_URL}{server.json()['template_id']}/",
        {"allow_self_approval": True}, format="json",
    )
    assert patched.status_code == 200, patched.content

    _login(api_client, workflow_env["applicant"])
    allowed = api_client.post(f"{INSTANCES_URL}{body['id']}/approve/", {"comment": "自审通过"}, format="json")
    assert allowed.status_code == 200, allowed.content
    assert allowed.json()["status"] == InstanceStatus.APPROVED


def test_reject_requires_comment(api_client, workflow_env):
    _make_template(api_client, workflow_env, code="TPL_REJ")
    body = _create_instance(api_client, workflow_env, template_code="TPL_REJ")
    api_client.post(f"{INSTANCES_URL}{body['id']}/submit/", {}, format="json")

    _login(api_client, workflow_env["l1"])
    empty = api_client.post(f"{INSTANCES_URL}{body['id']}/reject/", {"comment": "   "}, format="json")
    assert empty.status_code == 400
    assert empty.json()["code"] == "REJECT_COMMENT_REQUIRED"

    ok = api_client.post(f"{INSTANCES_URL}{body['id']}/reject/", {"comment": "金额不符"}, format="json")
    assert ok.status_code == 200, ok.content
    assert ok.json()["status"] == InstanceStatus.REJECTED

    again = api_client.post(f"{INSTANCES_URL}{body['id']}/approve/", {}, format="json")
    assert again.status_code == 409
    assert again.json()["code"] == "APPROVAL_NOT_PENDING"

def test_only_applicant_can_withdraw(api_client, workflow_env):
    _make_template(api_client, workflow_env, code="TPL_WD")
    body = _create_instance(api_client, workflow_env, template_code="TPL_WD")
    api_client.post(f"{INSTANCES_URL}{body['id']}/submit/", {}, format="json")

    _login(api_client, workflow_env["l1"])
    denied = api_client.post(f"{INSTANCES_URL}{body['id']}/withdraw/", {}, format="json")
    assert denied.status_code == 403
    assert denied.json()["code"] == "NOT_APPLICANT"

    _login(api_client, workflow_env["applicant"])
    ok = api_client.post(
        f"{INSTANCES_URL}{body['id']}/withdraw/", {"comment": "信息有误"}, format="json"
    )
    assert ok.status_code == 200, ok.content
    data = ok.json()
    assert data["status"] == InstanceStatus.WITHDRAWN
    assert data["steps"][0]["status"] == StepStatus.CANCELLED


def test_template_snapshot_survives_template_change(api_client, workflow_env):
    """提交后修改模板节点，历史实例的步骤与版本快照不变。"""
    template = _make_template(
        api_client, workflow_env, code="TPL_SNAP",
        nodes=[{"seq": 1, "name": "一级审批", "approver_type": "role",
                "approver_role_id": workflow_env["l1_role"].pk}],
    )
    body = _create_instance(api_client, workflow_env, template_code="TPL_SNAP")
    submitted = api_client.post(f"{INSTANCES_URL}{body['id']}/submit/", {}, format="json").json()
    assert submitted["template_version"] == 1
    assert len(submitted["steps"]) == 1

    _login(api_client, workflow_env["admin"])
    changed = api_client.patch(
        f"{TEMPLATES_URL}{template['id']}/",
        {"nodes": [{"seq": 1, "name": "改名后节点", "approver_type": "role",
                    "approver_role_id": workflow_env["l2_role"].pk}]},
        format="json",
    )
    assert changed.status_code == 200, changed.content
    assert changed.json()["version_no"] == 2

    instance = ApprovalInstance.objects.get(pk=body["id"])
    snapshot = instance.template_snapshot
    assert instance.template_version == 1
    assert snapshot["version_no"] == 1
    assert snapshot["nodes"][0]["approver_role_id"] == workflow_env["l1_role"].pk
    assert snapshot["nodes"][0]["name"] == "一级审批"
    assert instance.steps.get(seq=1).approver_role_id == workflow_env["l1_role"].pk


def test_todo_and_mine_visibility(api_client, workflow_env):
    _make_template(api_client, workflow_env, code="TPL_TODO")
    body = _create_instance(api_client, workflow_env, template_code="TPL_TODO")

    mine_before = api_client.get(f"{INSTANCES_URL}mine/")
    assert mine_before.status_code == 200
    assert [row["id"] for row in mine_before.json()["results"]] == [body["id"]]

    api_client.post(f"{INSTANCES_URL}{body['id']}/submit/", {}, format="json")

    _login(api_client, workflow_env["l1"])
    todo = api_client.get(f"{INSTANCES_URL}todo/")
    assert todo.status_code == 200
    assert [row["id"] for row in todo.json()["results"]] == [body["id"]]

    _login(api_client, workflow_env["l2"])
    assert api_client.get(f"{INSTANCES_URL}todo/").json()["results"] == []

    _login(api_client, workflow_env["applicant"])
    assert api_client.get(f"{INSTANCES_URL}todo/").json()["results"] == []
    summary = api_client.get(f"{INSTANCES_URL}pending-summary/")
    assert summary.json() == {"todo_count": 0}


def test_approval_actions_require_permission(api_client, registry_permissions, workflow_env, company):
    """只有 view 权限的用户既不能提交也不能审批。"""
    viewer_role = make_role(
        code="wf_viewer", permission_codes=["workflow.instance.view"],
        data_scope_type=DataScopeType.COMPANY, company=company,
    )
    viewer = make_user(username="wf_viewer_u", role=viewer_role, company=company)
    _make_template(api_client, workflow_env, code="TPL_PERM")
    body = _create_instance(api_client, workflow_env, template_code="TPL_PERM")

    _login(api_client, viewer)
    create_denied = api_client.post(
        INSTANCES_URL, {"title": "越权创建", "template_code": "TPL_PERM"}, format="json"
    )
    assert create_denied.status_code == 403
    assert create_denied.json()["code"] == "PERMISSION_DENIED"

    submit_denied = api_client.post(f"{INSTANCES_URL}{body['id']}/submit/", {}, format="json")
    assert submit_denied.status_code == 403
    assert submit_denied.json()["code"] == "PERMISSION_DENIED"

    _login(api_client, workflow_env["applicant"])
    assert api_client.post(f"{INSTANCES_URL}{body['id']}/submit/", {}, format="json").status_code == 200

    _login(api_client, viewer)
    approve_denied = api_client.post(f"{INSTANCES_URL}{body['id']}/approve/", {}, format="json")
    assert approve_denied.status_code == 403
    assert approve_denied.json()["code"] == "PERMISSION_DENIED"


def test_participant_can_add_comment(api_client, workflow_env):
    _make_template(api_client, workflow_env, code="TPL_CMT")
    body = _create_instance(api_client, workflow_env, template_code="TPL_CMT")
    empty = api_client.post(f"{INSTANCES_URL}{body['id']}/comment/", {"comment": ""}, format="json")
    assert empty.status_code == 400
    assert empty.json()["code"] == "COMMENT_REQUIRED"

    ok = api_client.post(
        f"{INSTANCES_URL}{body['id']}/comment/", {"comment": "补充说明"}, format="json"
    )
    assert ok.status_code == 201 or ok.status_code == 200, ok.content
    detail = api_client.get(f"{INSTANCES_URL}{body['id']}/").json()
    assert detail["logs"][-1]["comment"] == "补充说明"
