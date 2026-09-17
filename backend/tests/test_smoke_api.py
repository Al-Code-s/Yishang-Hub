"""接口冒烟：确认阶段 1 的主要接口在真实数据库上可用。

这些用例不追求覆盖率，而是防止“页面存在但接口不可用”的假完成。
"""

from __future__ import annotations

import pytest

from apps.factory.models import Department
from apps.masterdata.models import Color, Material, MaterialCategory, Size, Style, UoM

pytestmark = pytest.mark.django_db


@pytest.fixture
def super_client(api_client, registry_permissions, company):
    from tests.conftest import make_user

    user = make_user(username="smoke_admin", company=company, is_superuser=True)
    api_client.force_authenticate(user=user)
    return api_client


def test_session_requires_authentication(api_client):
    response = api_client.get("/api/v1/identity/auth/session/")
    assert response.status_code in (401, 403)


def test_health_endpoints_are_public(api_client):
    assert api_client.get("/healthz").status_code == 200
    assert api_client.get("/readyz").status_code == 200


def test_meta_exposes_choices(super_client):
    response = super_client.get("/api/v1/meta/")
    assert response.status_code == 200, response.content
    body = response.json()
    assert "warehouse_types" in body
    assert body["identifier_types"]


def test_masterdata_reference_crud(super_client):
    created = super_client.post(
        "/api/v1/masterdata/uoms/", {"code": "TSTU", "name": "测试单位"}, format="json"
    )
    assert created.status_code == 201, created.content
    assert created.json()["code"] == "TSTU"

    duplicated = super_client.post(
        "/api/v1/masterdata/uoms/", {"code": "TSTU", "name": "重复"}, format="json"
    )
    # 简单唯一字段由 DRF 序列化器给出字段级 400；模型级唯一约束才映射为 409
    assert duplicated.status_code == 400, duplicated.content
    assert "code" in duplicated.json()["details"]

    listed = super_client.get("/api/v1/masterdata/uoms/", {"search": "TSTU"})
    assert listed.status_code == 200
    assert listed.json()["count"] == 1


def test_company_scoped_material_crud(super_client, company):
    category = MaterialCategory.objects.create(code="TC1", name="测试面料", category_type="fabric")
    uom = UoM.objects.create(code="TKG", name="公斤", category="weight")

    response = super_client.post(
        "/api/v1/masterdata/materials/",
        {
            "company_id": company.pk,
            "code": "MAT-T-001",
            "name": "测试物料",
            "category_id": category.pk,
            "base_uom_id": uom.pk,
        },
        format="json",
    )
    assert response.status_code == 201, response.content
    material = Material.objects.get(code="MAT-T-001")
    assert material.company_id == company.pk


def test_department_tree_and_factory(super_client, company):
    parent = Department.objects.create(company=company, code="P1", name="一级部门")
    response = super_client.post(
        "/api/v1/factory/departments/",
        {"company_id": company.pk, "parent_id": parent.pk, "code": "P1A", "name": "二级部门"},
        format="json",
    )
    assert response.status_code == 201, response.content

    detail = super_client.get(f"/api/v1/factory/departments/{response.json()['id']}/")
    assert detail.status_code == 200
    assert detail.json()["parent_id"] == parent.pk


def test_warehouse_zone_location_tree(super_client, company, department_factory):
    warehouse = super_client.post(
        "/api/v1/wms/warehouses/",
        {
            "company_id": company.pk,
            "factory_id": department_factory["factories"]["F01"].pk,
            "code": "WH-T-01",
            "name": "测试仓",
            "warehouse_type": "raw",
        },
        format="json",
    )
    assert warehouse.status_code == 201, warehouse.content
    warehouse_id = warehouse.json()["id"]

    zone = super_client.post(
        "/api/v1/wms/zones/",
        {"warehouse_id": warehouse_id, "code": "Z1", "name": "存储区", "zone_type": "storage"},
        format="json",
    )
    assert zone.status_code == 201, zone.content
    zone_id = zone.json()["id"]

    location = super_client.post(
        "/api/v1/wms/locations/",
        {"zone_id": zone_id, "code": "A01-01-01", "name": "1排1列1层"},
        format="json",
    )
    assert location.status_code == 201, location.content

    tree = super_client.get("/api/v1/wms/locations/tree/")
    assert tree.status_code == 200, tree.content
    payload = tree.json()
    assert payload[0]["code"] == "WH-T-01"
    assert payload[0]["zones"][0]["locations"][0]["code"] == "A01-01-01"


def test_sku_generate_endpoint(super_client, company):
    category = MaterialCategory.objects.create(code="TFG", name="成品", category_type="finished")
    uom = UoM.objects.create(code="TPC", name="件", category="quantity")
    style = Style.objects.create(company=company, code="ST-1", name="测试款式", category=category)
    color = Color.objects.create(code="BK", name="黑色")
    size = Size.objects.create(code="M", name="M", size_group="women")

    response = super_client.post(
        "/api/v1/masterdata/skus/generate/",
        {
            "style_id": style.pk,
            "color_ids": [color.pk],
            "size_ids": [size.pk],
            "create_material": True,
            "material_category_id": category.pk,
            "base_uom_id": uom.pk,
        },
        format="json",
    )
    assert response.status_code == 201, response.content
    assert response.json()["created"] == ["ST-1-BK-M"]

    again = super_client.post(
        "/api/v1/masterdata/skus/generate/",
        {
            "style_id": style.pk,
            "color_ids": [color.pk],
            "size_ids": [size.pk],
            "create_material": True,
            "material_category_id": category.pk,
            "base_uom_id": uom.pk,
        },
        format="json",
    )
    assert again.status_code == 200
    assert again.json()["skipped"] == ["ST-1-BK-M"]


def test_dashboard_endpoint(super_client):
    response = super_client.get("/api/v1/analytics/dashboard/")
    assert response.status_code == 200, response.content
    assert "cards" in response.json() or "generated_at" in response.json()
