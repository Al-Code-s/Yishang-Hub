"""四层权限与数据范围用例（对应任务书 6.3 / 6.4 / 14.2 第 2、3、4、20 条）。

重点验证：
* 无操作权限不能调用接口；
* 工厂 / 仓库范围不能越权，且不能通过传入组织 ID 绕过；
* 缺失维度时「就严不就宽」（fail closed）；
* 角色授权变更后权限缓存立即失效。
"""

from __future__ import annotations

import pytest
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.identity.models import DataScopeType, Role, RoleScopeGrant, ScopeDimension, User
from apps.masterdata.models import Material, MaterialCategory, UoM
from apps.wms.models import Location, Warehouse, Zone
from tests.conftest import make_role, make_user

pytestmark = pytest.mark.django_db

MATERIALS_URL = "/api/v1/masterdata/materials/"
WAREHOUSES_URL = "/api/v1/wms/warehouses/"
LOCATIONS_URL = "/api/v1/wms/locations/"
ATTACHMENTS_URL = "/api/v1/attachments/"


@pytest.fixture
def fixtures_for_scope(company, department_factory):
    category = MaterialCategory.objects.create(code="SC1", name="面料", category_type="fabric")
    uom = UoM.objects.create(code="SKG", name="公斤", category="weight")
    materials = {}
    for code, factory_code in (("M-F01", "F01"), ("M-F02", "F02")):
        materials[factory_code] = Material.objects.create(
            company=company, code=code, name=code, category=category, base_uom=uom
        )

    warehouses = {}
    for code, factory_code in (("WH-F01", "F01"), ("WH-F02", "F02")):
        warehouses[factory_code] = Warehouse.objects.create(
            company=company,
            code=code,
            name=code,
            warehouse_type="raw",
            factory=department_factory["factories"][factory_code],
        )
        zone = Zone.objects.create(warehouse=warehouses[factory_code], code="Z1", name="存储区")
        Location.objects.create(zone=zone, code="L1", name="储位1")

    return {
        "materials": materials,
        "warehouses": warehouses,
        "category": category,
        "uom": uom,
    }


def test_operation_permission_required(api_client, registry_permissions, company):
    role = make_role(code="only_view", permission_codes=["masterdata.uom.view"])
    user = make_user(username="viewer_only", role=role, company=company)
    api_client.force_authenticate(user=user)

    assert api_client.get("/api/v1/masterdata/uoms/").status_code == 200
    denied = api_client.post("/api/v1/masterdata/uoms/", {"code": "X1", "name": "X"}, format="json")
    assert denied.status_code == 403
    assert denied.json()["code"] == "PERMISSION_DENIED"


def test_role_without_permission_sees_no_menu(api_client, registry_permissions, registry_menus, company):
    role = make_role(code="no_perm", permission_codes=[])
    user = make_user(username="no_perm_user", role=role, company=company)
    api_client.force_authenticate(user=user)
    session = api_client.get("/api/v1/identity/auth/session/")
    assert session.status_code == 200
    assert session.json()["permissions"] == []
    assert session.json()["menus"] == []


def test_factory_scope_filters_list_and_blocks_out_of_range_create(
    api_client, registry_permissions, company, department_factory, fixtures_for_scope
):
    factory_f01 = department_factory["factories"]["F01"]
    role = make_role(
        code="wh_f01",
        permission_codes=["wms.warehouse.view", "wms.warehouse.create", "masterdata.material.view"],
        data_scope_type=DataScopeType.FACTORY,
        company=company,
        grants=[(ScopeDimension.FACTORY, factory_f01.pk)],
    )
    user = make_user(username="wh_f01_user", role=role, company=company)
    api_client.force_authenticate(user=user)

    listed = api_client.get(WAREHOUSES_URL)
    assert listed.status_code == 200
    codes = [row["code"] for row in listed.json()["results"]]
    assert codes == ["WH-F01"]

    detail = api_client.get(f"{WAREHOUSES_URL}{fixtures_for_scope['warehouses']['F02'].pk}/")
    assert detail.status_code == 404

    out_of_range = api_client.post(
        WAREHOUSES_URL,
        {
            "company_id": company.pk,
            "factory_id": department_factory["factories"]["F02"].pk,
            "code": "WH-NEW",
            "name": "越权仓",
        },
        format="json",
    )
    assert out_of_range.status_code == 403
    assert out_of_range.json()["code"] == "OUT_OF_DATA_SCOPE"
    assert not Warehouse.objects.filter(code="WH-NEW").exists()


def test_scope_missing_dimension_fails_closed(
    api_client, registry_permissions, company, department_factory, fixtures_for_scope
):
    """Material 上没有 factory 维度：工厂范围的用户应看不到任何物料，而不是看到全部。"""
    role = make_role(
        code="mat_factory_scope",
        permission_codes=["masterdata.material.view"],
        data_scope_type=DataScopeType.FACTORY,
        company=company,
        grants=[(ScopeDimension.FACTORY, department_factory["factories"]["F01"].pk)],
    )
    user = make_user(username="mat_factory_user", role=role, company=company)
    api_client.force_authenticate(user=user)

    response = api_client.get(MATERIALS_URL)
    assert response.status_code == 200
    assert response.json()["count"] == 0


def test_warehouse_scope_limits_locations(api_client, registry_permissions, company, fixtures_for_scope):
    role = make_role(
        code="loc_f01",
        permission_codes=["wms.location.view", "wms.warehouse.view"],
        data_scope_type=DataScopeType.WAREHOUSE,
        company=company,
        grants=[(ScopeDimension.WAREHOUSE, fixtures_for_scope["warehouses"]["F01"].pk)],
    )
    user = make_user(username="loc_f01_user", role=role, company=company)
    api_client.force_authenticate(user=user)

    response = api_client.get(LOCATIONS_URL)
    assert response.status_code == 200
    assert response.json()["count"] == 1

    tree = api_client.get(f"{LOCATIONS_URL}tree/")
    assert tree.status_code == 200
    assert [item["code"] for item in tree.json()] == ["WH-F01"]


def test_company_boundary_is_applied(api_client, registry_permissions, company, other_company, fixtures_for_scope):
    role = make_role(
        code="company_scope",
        permission_codes=["wms.warehouse.view"],
        data_scope_type=DataScopeType.COMPANY,
        company=company,
    )
    other_warehouse = Warehouse.objects.create(
        company=other_company, code="WH-OTH", name="对照仓", warehouse_type="raw"
    )
    user = make_user(username="company_scope_user", role=role, company=company)
    api_client.force_authenticate(user=user)

    response = api_client.get(WAREHOUSES_URL)
    codes = [row["code"] for row in response.json()["results"]]
    assert "WH-F01" in codes
    assert other_warehouse.code not in codes


def test_permission_cache_invalidated_on_role_change(api_client, registry_permissions, company):
    role = make_role(code="uom_admin", permission_codes=["masterdata.uom.view"])
    user = make_user(username="cache_user", role=role, company=company)

    assert user.has_permission_codes(["masterdata.uom.view"])
    assert not user.has_permission_codes(["masterdata.uom.create"])

    # 直接改角色权限（模拟后台配置）后必须自增权限版本，缓存立即失效
    from apps.identity.models import Permission

    role.permissions.add(Permission.objects.get(code="masterdata.uom.create"))
    user.bump_permission_version()
    assert user.has_permission_codes(["masterdata.uom.create"])

    role.permissions.remove(Permission.objects.get(code="masterdata.uom.view"))
    user.bump_permission_version()
    assert not user.has_permission_codes(["masterdata.uom.view"])


def test_deactivating_role_revokes_permissions(registry_permissions, company):
    role = make_role(code="temp_role", permission_codes=["masterdata.uom.view"])
    user = make_user(username="temp_role_user", role=role, company=company)
    assert user.has_permission_codes(["masterdata.uom.view"])

    role.is_active = False
    role.save(update_fields=["is_active"])
    cache.clear()
    assert not user.has_permission_codes(["masterdata.uom.view"])


def test_attachment_download_requires_permission(api_client, registry_permissions, company):
    role = make_role(
        code="no_attachment",
        permission_codes=["masterdata.uom.view"],
    )
    user = make_user(username="no_att_user", role=role, company=company)
    api_client.force_authenticate(user=user)

    uploaded = SimpleUploadedFile("note.txt", b"hello", content_type="text/plain")
    denied = api_client.post(
        ATTACHMENTS_URL,
        {"file": uploaded, "biz_type": "test", "biz_id": "1"},
        format="multipart",
    )
    assert denied.status_code == 403


def test_superuser_bypasses_data_scope(api_client, registry_permissions, company, other_company):
    Warehouse.objects.create(company=company, code="WH-A", name="A", warehouse_type="raw")
    Warehouse.objects.create(company=other_company, code="WH-B", name="B", warehouse_type="raw")
    admin = make_user(username="scope_admin", company=company, is_superuser=True)
    api_client.force_authenticate(user=admin)
    response = api_client.get(WAREHOUSES_URL)
    assert response.json()["count"] == 2


def test_self_scope_only_returns_own_records(registry_permissions, company, fixtures_for_scope):
    from apps.core.selectors import resolve_data_scope, scoped_queryset

    role = make_role(
        code="self_scope",
        permission_codes=["wms.warehouse.view"],
        data_scope_type=DataScopeType.SELF,
    )
    user = make_user(username="self_scope_user", role=role, company=company)
    assert resolve_data_scope(user).scope_type == DataScopeType.SELF
    assert scoped_queryset(Warehouse.objects.all(), user, owner_field="created_by_id").count() == 0

    Warehouse.objects.create(
        company=company, code="WH-OWN", name="本人创建", warehouse_type="raw", created_by=user
    )
    assert scoped_queryset(Warehouse.objects.all(), user, owner_field="created_by_id").count() == 1


def test_user_management_scope_is_enforced(api_client, registry_permissions, company, other_company):
    role = make_role(
        code="user_admin_company",
        permission_codes=[
            "identity.user.view",
            "identity.user.update",
            "identity.user.deactivate",
        ],
        data_scope_type=DataScopeType.COMPANY,
        company=company,
    )
    actor = make_user(username="hr_admin", role=role, company=company)
    outsider = make_user(username="outsider", company=other_company)
    api_client.force_authenticate(user=actor)

    listed = api_client.get("/api/v1/identity/users/")
    usernames = [row["username"] for row in listed.json()["results"]]
    assert "hr_admin" in usernames
    assert "outsider" not in usernames

    # 范围外的对象在查询阶段就被过滤掉，返回 404 而不是 403，避免泄露对象是否存在
    denied = api_client.post(
        f"/api/v1/identity/users/{outsider.pk}/set-active/", {"is_active": False}, format="json"
    )
    assert denied.status_code == 404
    outsider.refresh_from_db()
    assert outsider.is_active is True


def test_unauthenticated_requests_are_rejected(api_client):
    for url in (MATERIALS_URL, WAREHOUSES_URL, "/api/v1/identity/users/", "/api/v1/analytics/dashboard/"):
        assert api_client.get(url).status_code in (401, 403)


def test_role_delete_or_permission_change_affects_session_payload(
    api_client, registry_permissions, registry_menus, company
):
    role = make_role(code="menu_role", permission_codes=["masterdata.uom.view"], menus=["masterdata.uom"])
    user = make_user(username="menu_user", role=role, company=company)
    api_client.force_authenticate(user=user)

    payload = api_client.get("/api/v1/identity/auth/session/").json()
    # 只授权了页面菜单，其上级目录必须自动补齐，否则导航分组会错乱
    assert [menu["code"] for menu in payload["menus"]] == ["masterdata"]
    assert [child["code"] for child in payload["menus"][0]["children"]] == ["masterdata.uom"]

    role.permissions.clear()
    role.menus.clear()
    user.bump_permission_version()
    payload = api_client.get("/api/v1/identity/auth/session/").json()
    assert payload["menus"] == []


def test_role_code_uniqueness(registry_permissions, company):
    make_role(code="dup_role", permission_codes=[])
    from django.db import IntegrityError, transaction

    with pytest.raises(IntegrityError), transaction.atomic():
        Role.objects.create(code="dup_role", name="重复")


def test_role_scope_grant_dimension_validation(registry_permissions, company):
    role = make_role(code="grant_role", permission_codes=[])
    grant = RoleScopeGrant.objects.create(role=role, dimension=ScopeDimension.DEPARTMENT, object_id=1)
    assert grant.dimension == "department"
    assert set(ScopeDimension.values) == {"company", "factory", "department", "warehouse"}


def test_users_have_distinct_roles(registry_permissions, company):
    role_a = make_role(code="ra", permission_codes=["masterdata.uom.view"])
    role_b = make_role(code="rb", permission_codes=["masterdata.uom.create"])
    user = make_user(username="multi_role", role=role_a, company=company)
    from apps.identity.models import UserRole

    UserRole.objects.create(user=user, role=role_b)
    user.bump_permission_version()
    # 多角色：操作权限取并集
    assert user.has_permission_codes(["masterdata.uom.view", "masterdata.uom.create"])
    assert user.active_roles()
    assert User.objects.filter(username="multi_role").exists()
