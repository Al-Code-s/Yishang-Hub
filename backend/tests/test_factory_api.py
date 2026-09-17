"""组织、工厂、员工、班次、班组用例（对应任务书 9.1 与 14.2 第 15 条）。

聚焦「层级合法 / 时间冲突 / 快照保留 / 已用数据只能停用」这些真实规则，
不使用 mock，全部走 HTTP 接口与 MySQL 约束。
"""

from __future__ import annotations

import pytest
from django.db import IntegrityError, transaction

from apps.factory.models import Department, Employee, TeamMember
from apps.identity.models import DataScopeType
from tests.conftest import make_role, make_user

pytestmark = pytest.mark.django_db

DEPARTMENTS_URL = "/api/v1/factory/departments/"
EMPLOYEES_URL = "/api/v1/factory/employees/"
SHIFTS_URL = "/api/v1/factory/shifts/"
TEAMS_URL = "/api/v1/factory/teams/"
WORKSHOPS_URL = "/api/v1/factory/workshops/"
LINES_URL = "/api/v1/factory/lines/"
STATIONS_URL = "/api/v1/factory/stations/"
COMPANIES_URL = "/api/v1/factory/companies/"


@pytest.fixture
def admin_client(api_client, registry_permissions, company):
    permission_codes = [
        "factory.company.view", "factory.company.create", "factory.company.update",
        "factory.department.view", "factory.department.create", "factory.department.update",
        "factory.factory.view", "factory.factory.create", "factory.factory.update",
        "factory.workshop.view", "factory.workshop.create", "factory.workshop.update",
        "factory.line.view", "factory.line.create", "factory.line.update",
        "factory.station.view", "factory.station.create", "factory.station.update",
        "factory.employee.view", "factory.employee.create", "factory.employee.update",
        "factory.shift.view", "factory.shift.create", "factory.shift.update",
        "factory.team.view", "factory.team.create", "factory.team.update",
    ]
    role = make_role(
        code="factory_admin",
        permission_codes=permission_codes,
        data_scope_type=DataScopeType.COMPANY,
        company=company,
    )
    user = make_user(username="factory_admin_u", role=role, company=company)
    assert api_client.post(
        "/api/v1/identity/auth/login/",
        {"username": user.username, "password": "Tst!Passw0rd2026"},
        format="json",
    ).status_code == 200
    return api_client
def test_department_tree_and_cycle_rejected(admin_client, company, department_factory):
    parent = department_factory["departments"]["PROD"]
    child = Department.objects.create(company=company, parent=parent, code="PLAN", name="计划科")

    tree = admin_client.get(f"{DEPARTMENTS_URL}tree/")
    assert tree.status_code == 200
    payload = {node["code"]: node for node in tree.json()}
    assert [item["code"] for item in payload["PROD"]["children"]] == ["PLAN"]

    # 把父部门的上级指向自己的子部门 → 形成环，必须被拒绝
    loop = admin_client.patch(f"{DEPARTMENTS_URL}{parent.pk}/", {"parent_id": child.pk}, format="json")
    assert loop.status_code == 400
    assert "循环引用" in str(loop.json())

    parent.refresh_from_db()
    assert parent.parent_id is None


def test_department_parent_must_share_company(admin_client, company, other_company):
    foreign = Department.objects.create(company=other_company, code="OTH1", name="外部部门")
    created = admin_client.post(
        DEPARTMENTS_URL,
        {"company_id": company.pk, "code": "NEW1", "name": "新部门", "parent_id": foreign.pk},
        format="json",
    )
    assert created.status_code == 400
    assert "parent_id" in created.json()["details"]


def test_shift_cross_day_is_derived_not_trusted_from_client(admin_client, company):
    night = admin_client.post(
        SHIFTS_URL,
        {"company_id": company.pk, "code": "N1", "name": "夜班",
         "start_time": "20:00:00", "end_time": "04:00:00", "break_minutes": 30},
        format="json",
    )
    assert night.status_code == 201, night.content
    body = night.json()
    # 客户端没传 cross_day，由后端根据时间推导
    assert body["cross_day"] is True
    # 跨夜 8 小时减去 30 分钟休息\n    assert body["duration_hours"] == "7.50"

    day = admin_client.post(
        SHIFTS_URL,
        {"company_id": company.pk, "code": "D1", "name": "白班",
         "start_time": "08:00:00", "end_time": "17:00:00", "break_minutes": 60},
        format="json",
    )
    assert day.status_code == 201, day.content
    assert day.json()["cross_day"] is False

    same = admin_client.post(
        SHIFTS_URL,
        {"company_id": company.pk, "code": "X1", "name": "异常班次",
         "start_time": "08:00:00", "end_time": "08:00:00"},
        format="json",
    )
    assert same.status_code == 400


def test_employee_no_unique_per_company(admin_client, company, department_factory):
    payload = {
        "company_id": company.pk, "employee_no": "E1001", "name": "张三",
        "department_id": department_factory["departments"]["PROD"].pk,
        "gender": "male", "employment_type": "full_time", "status": "active",
    }
    first = admin_client.post(EMPLOYEES_URL, payload, format="json")
    assert first.status_code == 201, first.content

    duplicate = admin_client.post(EMPLOYEES_URL, {**payload, "name": "李四"}, format="json")
    assert duplicate.status_code == 400


def test_team_members_snapshot_and_replacement(admin_client, company, department_factory):
    workshop_payload = {
        "factory_id": department_factory["factories"]["F01"].pk,
        "code": "WS1", "name": "缝制车间", "workshop_type": "sewing",
    }
    workshop = admin_client.post(WORKSHOPS_URL, workshop_payload, format="json")
    assert workshop.status_code == 201, workshop.content

    line = admin_client.post(
        LINES_URL,
        {"workshop_id": workshop.json()["id"], "code": "L1", "name": "一线", "line_type": "hanging"},
        format="json",
    )
    assert line.status_code == 201, line.content

    station = admin_client.post(
        STATIONS_URL,
        {"line_id": line.json()["id"], "code": "S1", "name": "上领工位", "station_type": "sewing"},
        format="json",
    )
    assert station.status_code == 201, station.content

    employees = [
        Employee.objects.create(
            company=company, department=department_factory["departments"]["PROD"],
            employee_no=f"E20{n:02d}", name=f"员工{n}", status="active",
        )
        for n in range(1, 4)
    ]
    team = admin_client.post(
        TEAMS_URL,
        {"code": "T1", "name": "一组", "workshop_id": workshop.json()["id"]},
        format="json",
    )
    assert team.status_code == 201, team.content
    team_id = team.json()["id"]

    set_members = admin_client.post(
        f"{TEAMS_URL}{team_id}/members/",
        {"members": [
            {"employee_id": employees[0].pk, "role_in_team": "组长"},
            {"employee_id": employees[1].pk},
        ]},
        format="json",
    )
    assert set_members.status_code == 200, set_members.content
    assert TeamMember.objects.filter(team_id=team_id).count() == 2

    replaced = admin_client.post(
        f"{TEAMS_URL}{team_id}/members/",
        {"members": [{"employee_id": employees[2].pk}]},
        format="json",
    )
    assert replaced.status_code == 200, replaced.content
    assert list(
        TeamMember.objects.filter(team_id=team_id).values_list("employee_id", flat=True)
    ) == [employees[2].pk]

    duplicated = admin_client.post(
        f"{TEAMS_URL}{team_id}/members/",
        {"members": [{"employee_id": employees[2].pk}, {"employee_id": employees[2].pk}]},
        format="json",
    )
    assert duplicated.status_code == 400


def test_used_master_data_is_deactivated_not_deleted(admin_client, company, department_factory):
    department = department_factory["departments"]["WH"]
    response = admin_client.delete(f"{DEPARTMENTS_URL}{department.pk}/")
    # 已使用的组织不允许物理删除：接口根本不提供 DELETE
    assert response.status_code == 405

    stopped = admin_client.post(f"{DEPARTMENTS_URL}{department.pk}/set-active/", {"is_active": False}, format="json")
    assert stopped.status_code == 200, stopped.content
    assert stopped.json()["is_active"] is False
    department.refresh_from_db()
    assert department.is_active is False


def test_company_code_unique_enforced_by_database(company):
    from apps.factory.models import Company

    with pytest.raises(IntegrityError), transaction.atomic():
        Company.objects.create(code=company.code, name="重复编码公司")

def test_shift_break_cannot_exceed_span(admin_client, company):
    response = admin_client.post(
        SHIFTS_URL,
        {"company_id": company.pk, "code": "B1", "name": "休息超长",
         "start_time": "08:00:00", "end_time": "09:00:00", "break_minutes": 90},
        format="json",
    )
    assert response.status_code == 400
    assert "break_minutes" in response.json()["details"]
