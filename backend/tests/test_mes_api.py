"""生产执行（MES）接口用例：工单 / 用料 / 工序 / 下达 / 领料 / 报工 / 完工 / 入库。

覆盖要点：

* 工单号留空时按编码规则（MO）取号，报工单号按 RPT 取号；
* **状态机只能由动作接口推进**：PATCH 传 status 被忽略，跳步一律 409；
* 下达需要「生效工艺路线」+「生效 BOM 或手工用料」，两者缺一分别报
  ROUTING_REQUIRED / BOM_REQUIRED；下达即冻结快照并生成工序与用料行；
* BOM 展开的用料数量 = 含损耗用量 x 计划数量，快照落库后不再随工程数据变化；
* 报工数量守恒（QUANTITY_MISMATCH）、不得超计划（OVER_PRODUCTION）、
  已完工工序不能继续报（STEP_ALREADY_COMPLETED）；
* 质检点报满自动生成 QMS 检验单，未判定不能完工（QUALITY_GATE_NOT_PASSED），
  判定合格后可完工；报工质检点需要 qms.inspection.create，缺权限整笔回滚；
* 领料与完工入库**只能经统一库存服务**：生成并过账库存单据、余额随动，
  重复领料 / 重复入库被拒，Idempotency-Key 重放不重复过账；
* 公司数据范围在工单与报工台账上一致生效；只读角色不能写；报工不可改（405）。

数据构造说明：BOM / 工艺路线是被测模块的**上游夹具**，这里直接经 ORM 按
approved 状态构造（与 MRP 用例同一口径）；库存余额经统一库存服务入库产生。
MES 自身的读写全部走 HTTP 接口。
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.core.models import CodeRule, ResetPeriod
from apps.factory.models import Workshop
from apps.identity.models import DataScopeType
from apps.masterdata.models import Color, Material, MaterialCategory, Size, Sku, Style, UoM
from apps.mes.models import (
    ProductionOrder,
    ProductionOrderStatus,
    ProductionOrderStep,
    ProductionReport,
    ProductionStepStatus,
)
from apps.planning.models import Bom, BomLine, BomStatus, Routing, RoutingStatus, RoutingStep
from apps.qms import services as qms_services
from apps.qms.models import (
    QualityInspectionItem,
    QualityInspectionOrder,
    QualityJudgement,
)
from apps.wms.models import DocumentType, InventoryBalance, Location, QualityStatus, Warehouse, Zone
from apps.wms.services import stock
from tests.conftest import make_role, make_user

pytestmark = pytest.mark.django_db

BASE = "/api/v1/mes"
ORDERS_URL = BASE + "/orders/"
REPORTS_URL = BASE + "/reports/"
STATS_URL = ORDERS_URL + "statistics/"
LOGIN_URL = "/api/v1/identity/auth/login/"
PASSWORD = "Tst!Passw0rd2026"
TODAY = date(2026, 9, 1)

MES_PERMISSIONS = [
    "mes.order.view",
    "mes.order.create",
    "mes.order.update",
    "mes.order.release",
    "mes.order.issue",
    "mes.order.complete",
    "mes.order.close",
    "mes.order.cancel",
    "mes.report.view",
    "mes.report.create",
    "wms.document.create",
    "wms.document.post",
    "qms.inspection.create",
]


def login(client, user) -> None:
    response = client.post(
        LOGIN_URL, {"username": user.username, "password": PASSWORD}, format="json"
    )
    assert response.status_code == 200, response.content


@pytest.fixture
def mes_code_rules(db):
    """取号依赖编码规则；测试库不跑 bootstrap_system，这里显式建规则。"""
    rules = (
        ("MO", "生产工单号", "MO{YYYYMMDD}{SEQ:4}"),
        ("RPT", "生产报工单号", "RPT{YYYYMMDD}{SEQ:4}"),
        ("BOM", "BOM 编号", "BOM{YYYYMMDD}{SEQ:4}"),
        ("ROUTING", "工艺路线编号", "RT{YYYYMMDD}{SEQ:4}"),
        ("GR", "采购收货单号", "GR{YYYYMMDD}{SEQ:4}"),
        ("ST", "出库单号", "ST{YYYYMMDD}{SEQ:4}"),
        ("QC", "检验单号", "QC{YYYYMMDD}{SEQ:4}"),
    )
    for code, name, pattern in rules:
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
def env(company, other_company, department_factory, mes_code_rules):
    """最小生产环境：物料 / 款式 / SKU / 车间 / 仓库 / 生效 BOM 与工艺路线。"""
    category = MaterialCategory.objects.create(code="MES-FAB", name="面料", category_type="fabric")
    uom_m = UoM.objects.create(code="MES-M", name="米", category="length")
    uom_pc = UoM.objects.create(code="MES-PC", name="件", category="quantity")
    fabric = Material.objects.create(
        company=company, code="MES-FAB-1", name="主面料", category=category, base_uom=uom_m
    )
    button = Material.objects.create(
        company=company, code="MES-BTN-1", name="纽扣", category=category, base_uom=uom_pc
    )
    finished = Material.objects.create(
        company=company, code="MES-FIN-1", name="成品衬衫", category=category, base_uom=uom_pc
    )
    color = Color.objects.create(code="MES-BK", name="黑色")
    size = Size.objects.create(code="MES-L", name="L")
    factory = department_factory["factories"]["F01"]
    workshop = Workshop.objects.create(
        factory=factory, code="MES-SEW", name="缝制车间", workshop_type="sewing"
    )

    def _style(code: str) -> tuple[Style, Sku]:
        style = Style.objects.create(company=company, code=code, name=f"款式{code}")
        sku = Sku.objects.create(
            company=company, style=style, color=color, size=size, code=f"{code}-BK-L"
        )
        return style, sku

    style, sku = _style("MES-ST1")
    style_no_routing, sku_no_routing = _style("MES-ST2")
    style_no_bom, sku_no_bom = _style("MES-ST3")

    routing = Routing.objects.create(
        company=company,
        code="MES-RT-1",
        style=style,
        version_no=1,
        status=RoutingStatus.APPROVED,
        effective_from=TODAY,
    )
    RoutingStep.objects.create(
        routing=routing, sequence=1, name="缝制", workshop=workshop, standard_hours="0.5"
    )
    RoutingStep.objects.create(routing=routing, sequence=2, name="检验", is_quality_gate=True)
    # 无 BOM 的款式也要有工艺路线，才能把「缺 BOM」与「缺工艺」两个分支分开
    routing_no_bom = Routing.objects.create(
        company=company,
        code="MES-RT-2",
        style=style_no_bom,
        version_no=1,
        status=RoutingStatus.APPROVED,
        effective_from=TODAY,
    )
    RoutingStep.objects.create(routing=routing_no_bom, sequence=1, name="缝制")

    bom = Bom.objects.create(
        company=company,
        code="MES-BOM-1",
        style=style,
        version_no=1,
        status=BomStatus.APPROVED,
        effective_from=TODAY,
    )
    BomLine.objects.create(
        bom=bom,
        line_no=1,
        material=fabric,
        quantity=Decimal("2.8"),
        loss_rate=Decimal("0.06"),
        uom=uom_m,
    )
    BomLine.objects.create(bom=bom, line_no=2, material=button, quantity=Decimal("4"), uom=uom_pc)

    warehouses = {}
    locations = {}
    for key, code in (("raw", "MES-WH-RAW"), ("fg", "MES-WH-FG")):
        warehouse = Warehouse.objects.create(
            company=company, code=code, name=f"仓库{code}", factory=factory
        )
        zone = Zone.objects.create(warehouse=warehouse, code="Z1", name="存储区")
        warehouses[key] = warehouse
        locations[key] = Location.objects.create(zone=zone, code="L1", name="储位1")

    svc_user = make_user(username="mes_svc", company=company, is_superuser=True)
    # 让工单领料有货可领：经统一库存服务入库
    for material, quantity in ((fabric, "100"), (button, "100")):
        document = stock.create_document(
            document_type=DocumentType.RECEIPT,
            company=company,
            warehouse=warehouses["raw"],
            user=svc_user,
            lines=[
                {
                    "material_id": material.pk,
                    "location_id": locations["raw"].pk,
                    "quality_status": QualityStatus.QUALIFIED,
                    "quantity": quantity,
                }
            ],
        )
        stock.post_document(document, user=svc_user)

    return {
        "company": company,
        "other_company": other_company,
        "fabric": fabric,
        "button": button,
        "finished": finished,
        "style": style,
        "sku": sku,
        "style_no_routing": style_no_routing,
        "sku_no_routing": sku_no_routing,
        "style_no_bom": style_no_bom,
        "sku_no_bom": sku_no_bom,
        "workshop": workshop,
        "raw_warehouse": warehouses["raw"],
        "fg_warehouse": warehouses["fg"],
        "raw_location": locations["raw"],
        "fg_location": locations["fg"],
        "svc_user": svc_user,
    }


@pytest.fixture
def mes_admin(api_client, registry_permissions, company):
    role = make_role(
        code="test_mes_admin",
        permission_codes=MES_PERMISSIONS,
        data_scope_type=DataScopeType.COMPANY,
        company=company,
    )
    user = make_user(username="mes_admin_t", role=role, company=company)
    login(api_client, user)
    return api_client


@pytest.fixture
def mes_viewer(api_client, registry_permissions, company):
    role = make_role(
        code="test_mes_viewer",
        permission_codes=["mes.order.view", "mes.report.view"],
        data_scope_type=DataScopeType.COMPANY,
        company=company,
    )
    user = make_user(username="mes_viewer_t", role=role, company=company)
    login(api_client, user)
    return api_client


@pytest.fixture
def mes_no_quality(registry_permissions, company):
    """能报工但**没有** qms.inspection.create 的角色：质检点报工必须整笔回滚。"""
    perms = [code for code in MES_PERMISSIONS if code != "qms.inspection.create"]
    role = make_role(
        code="test_mes_no_quality",
        permission_codes=perms,
        data_scope_type=DataScopeType.COMPANY,
        company=company,
    )
    user = make_user(username="mes_no_quality_t", role=role, company=company)
    client = APIClient()
    login(client, user)
    return client


def order_payload(env, *, style=None, sku=None, quantity="10", **extra) -> dict:
    payload = {
        "company_id": env["company"].pk,
        "style_id": (style or env["style"]).pk,
        "sku_id": (sku or env["sku"]).pk,
        "product_material_id": env["finished"].pk,
        "quantity": quantity,
        "unit": "件",
        "workshop_id": env["workshop"].pk,
        "material_warehouse_id": env["raw_warehouse"].pk,
        "receipt_warehouse_id": env["fg_warehouse"].pk,
    }
    payload.update(extra)
    return payload


def create_order(client, env, **extra):
    return client.post(ORDERS_URL, order_payload(env, **extra), format="json")


def set_materials(client, order_id, rows):
    return client.post(ORDERS_URL + f"{order_id}/materials/", {"materials": rows}, format="json")


def release(client, order_id, **kwargs):
    return client.post(ORDERS_URL + f"{order_id}/release/", {}, format="json", **kwargs)


def report(client, order_id, step_id, *, quantity="10", qualified="10", **extra):
    payload = {"step_id": step_id, "quantity": quantity, "qualified_quantity": qualified}
    payload.update(extra)
    return client.post(ORDERS_URL + f"{order_id}/report/", payload, format="json")


def manual_materials(env) -> list[dict]:
    return [
        {
            "material_id": env["fabric"].pk,
            "required_quantity": "28",
            "location_id": env["raw_location"].pk,
        },
        {
            "material_id": env["button"].pk,
            "required_quantity": "40",
            "location_id": env["raw_location"].pk,
        },
    ]


def prepared_order(client, env, *, quantity="10"):
    """建单 -> 手工用料 -> 下达，返回工单 id（用料行带储位，便于领料）。"""
    created = create_order(client, env, quantity=quantity)
    assert created.status_code == 201, created.content
    order_id = created.json()["id"]
    assert set_materials(client, order_id, manual_materials(env)).status_code == 200
    assert release(client, order_id).status_code == 200
    return order_id


def steps_of(client, order_id) -> list[dict]:
    response = client.get(ORDERS_URL + f"{order_id}/steps/")
    assert response.status_code == 200, response.content
    return response.json()


def balance_of(env, material) -> Decimal:
    return InventoryBalance.objects.get(
        material=material, location=env["raw_location"], quality_status=QualityStatus.QUALIFIED
    ).on_hand


def pass_quality_gate(client, order_id, env, *, code="QIT-MES-1"):
    """把工单质检点的自动检验单判定为合格。"""
    gate = steps_of(client, order_id)[1]
    inspection = QualityInspectionOrder.objects.get(pk=gate["inspection_order_id"])
    item = QualityInspectionItem.objects.create(
        company=env["company"], code=code, name="外观", category="appearance"
    )
    qms_services.record_results(inspection, [{"item": item, "measured_value": "1"}])
    qms_services.submit_order(inspection)
    qms_services.judge_order(inspection)
    inspection.refresh_from_db()
    assert inspection.judgement == QualityJudgement.PASSED


def complete_order(client, env, order_id) -> dict:
    flow = client.post(ORDERS_URL + f"{order_id}/complete/", {}, format="json")
    assert flow.status_code == 200, flow.content
    return flow.json()


# ---------------------------------------------------------------------------
# 认证、权限与数据范围
# ---------------------------------------------------------------------------


def test_endpoints_require_login(api_client):
    assert api_client.get(ORDERS_URL).status_code in {401, 403}
    assert api_client.get(REPORTS_URL).status_code in {401, 403}
    assert api_client.get(STATS_URL).status_code in {401, 403}


def test_viewer_cannot_write(mes_viewer, env):
    denied = create_order(mes_viewer, env)
    assert denied.status_code == 403, denied.content
    assert mes_viewer.get(ORDERS_URL).status_code == 200
    assert mes_viewer.get(STATS_URL).status_code == 200


def test_company_scope_hides_other_company_orders(mes_admin, env):
    foreign = ProductionOrder.objects.create(
        company=env["other_company"],
        order_no="MO-OTHER",
        style=env["style"],
        quantity=Decimal("1"),
    )
    assert mes_admin.get(ORDERS_URL + f"{foreign.pk}/").status_code == 404
    listed = mes_admin.get(ORDERS_URL)
    assert listed.status_code == 200
    assert listed.json()["count"] == 0


# ---------------------------------------------------------------------------
# 建单与状态机
# ---------------------------------------------------------------------------


def test_order_number_is_generated_from_code_rule(mes_admin, env):
    created = create_order(mes_admin, env)
    assert created.status_code == 201, created.content
    body = created.json()
    assert body["order_no"].startswith("MO")
    assert body["status"] == ProductionOrderStatus.DRAFT
    assert body["progress_rate"] == "0.00"
    assert body["materials"] == []


def test_status_cannot_be_patched(mes_admin, env):
    order_id = create_order(mes_admin, env).json()["id"]
    patched = mes_admin.patch(ORDERS_URL + f"{order_id}/", {"status": "completed"}, format="json")
    assert patched.status_code == 200, patched.content
    assert patched.json()["status"] == ProductionOrderStatus.DRAFT
    assert ProductionOrder.objects.get(pk=order_id).status == ProductionOrderStatus.DRAFT


def test_header_cannot_be_patched_after_release(mes_admin, env):
    """已下达工单的用料与计划数量已冻结，表头不能再改（只有草稿可以）。"""
    order_id = prepared_order(mes_admin, env)
    rejected = mes_admin.patch(ORDERS_URL + f"{order_id}/", {"quantity": "99"}, format="json")
    assert rejected.status_code == 409, rejected.content
    assert rejected.json()["code"] == "STATE_CONFLICT"
    assert ProductionOrder.objects.get(pk=order_id).quantity == Decimal("10.000000")

    draft_id = create_order(mes_admin, env).json()["id"]
    updated = mes_admin.patch(ORDERS_URL + f"{draft_id}/", {"quantity": "12"}, format="json")
    assert updated.status_code == 200, updated.content
    assert updated.json()["quantity"] == "12.000000"


def test_actions_reject_wrong_state(mes_admin, env):
    order_id = create_order(mes_admin, env).json()["id"]
    # 草稿不能领料、不能完工、不能入库、不能关闭
    assert (
        mes_admin.post(ORDERS_URL + f"{order_id}/issue-materials/", {}, format="json").status_code
        == 409
    )
    assert (
        mes_admin.post(ORDERS_URL + f"{order_id}/complete/", {}, format="json").status_code == 409
    )
    assert mes_admin.post(ORDERS_URL + f"{order_id}/close/", {}, format="json").status_code == 409
    assert mes_admin.post(ORDERS_URL + f"{order_id}/receipt/", {}, format="json").status_code == 409


# ---------------------------------------------------------------------------
# 下达：需要工艺路线与用料
# ---------------------------------------------------------------------------


def test_release_requires_effective_routing(mes_admin, env):
    created = create_order(mes_admin, env, style=env["style_no_routing"], sku=env["sku_no_routing"])
    assert created.status_code == 201, created.content
    rejected = release(mes_admin, created.json()["id"])
    assert rejected.status_code == 400, rejected.content
    assert rejected.json()["code"] == "ROUTING_REQUIRED"


def test_release_requires_bom_or_manual_materials(mes_admin, env):
    created = create_order(mes_admin, env, style=env["style_no_bom"], sku=env["sku_no_bom"])
    order_id = created.json()["id"]
    rejected = release(mes_admin, order_id)
    assert rejected.status_code == 400, rejected.content
    assert rejected.json()["code"] == "BOM_REQUIRED"

    # 手工用料可以替代 BOM：仍有工艺路线即可下达
    replaced = set_materials(mes_admin, order_id, manual_materials(env))
    assert replaced.status_code == 200, replaced.content
    assert [row["source"] for row in replaced.json()] == ["manual", "manual"]
    assert release(mes_admin, order_id).status_code == 200


def test_release_requires_positive_quantity(mes_admin, env):
    created = create_order(mes_admin, env, quantity="0")
    assert created.status_code == 201, created.content
    rejected = release(mes_admin, created.json()["id"])
    assert rejected.status_code == 400, rejected.content
    assert rejected.json()["code"] == "INVALID_QUANTITY"


def test_release_freezes_snapshot_and_expands_bom(mes_admin, env):
    created = create_order(mes_admin, env, quantity="10")
    order_id = created.json()["id"]
    released = release(mes_admin, order_id)
    assert released.status_code == 200, released.content
    body = released.json()
    assert body["status"] == ProductionOrderStatus.RELEASED
    assert body["released_at"] is not None
    assert body["routing_snapshot"]["steps"]
    assert body["bom_snapshot"]["lines"]

    steps = steps_of(mes_admin, order_id)
    assert [step["name"] for step in steps] == ["缝制", "检验"]
    assert [step["is_quality_gate"] for step in steps] == [False, True]
    assert steps[0]["status"] == ProductionStepStatus.PENDING

    materials = mes_admin.get(ORDERS_URL + f"{order_id}/materials/").json()
    by_code = {row["material_code"]: row for row in materials}
    # 2.8 含 6% 损耗 -> 2.968；再乘计划数量 10
    assert Decimal(by_code["MES-FAB-1"]["required_quantity"]) == Decimal("29.680000")
    assert Decimal(by_code["MES-BTN-1"]["required_quantity"]) == Decimal("40.000000")
    assert {row["source"] for row in materials} == {"bom"}

    # 工单已下达后不能再改用料
    blocked = set_materials(mes_admin, order_id, manual_materials(env))
    assert blocked.status_code == 409, blocked.content


def test_release_twice_is_rejected(mes_admin, env):
    order_id = prepared_order(mes_admin, env)
    again = release(mes_admin, order_id)
    assert again.status_code == 409, again.content


# ---------------------------------------------------------------------------
# 报工
# ---------------------------------------------------------------------------


def test_report_quantity_must_be_conserved(mes_admin, env):
    order_id = prepared_order(mes_admin, env)
    step_id = steps_of(mes_admin, order_id)[0]["id"]
    rejected = report(mes_admin, order_id, step_id, quantity="10", qualified="8")
    assert rejected.status_code == 400, rejected.content
    assert rejected.json()["code"] == "QUANTITY_MISMATCH"


def test_report_cannot_exceed_planned_quantity(mes_admin, env):
    order_id = prepared_order(mes_admin, env)
    step_id = steps_of(mes_admin, order_id)[0]["id"]
    assert report(mes_admin, order_id, step_id, quantity="8", qualified="8").status_code == 200
    rejected = report(mes_admin, order_id, step_id, quantity="5", qualified="5")
    assert rejected.status_code == 400, rejected.content
    assert rejected.json()["code"] == "OVER_PRODUCTION"


def test_report_advances_order_and_writes_report_row(mes_admin, env):
    order_id = prepared_order(mes_admin, env)
    step_id = steps_of(mes_admin, order_id)[0]["id"]
    reported = report(
        mes_admin, order_id, step_id, quantity="6", qualified="5", scrap_quantity="1"
    )
    assert reported.status_code == 200, reported.content
    body = reported.json()
    assert body["status"] == ProductionOrderStatus.IN_PROGRESS
    assert body["report_count"] == 1

    rows = mes_admin.get(REPORTS_URL, {"order_id": order_id}).json()["results"]
    assert len(rows) == 1
    assert rows[0]["report_no"].startswith("RPT")
    assert rows[0]["scrap_quantity"] == "1.000000"


def test_completed_step_cannot_be_reported_again(mes_admin, env):
    order_id = prepared_order(mes_admin, env)
    step_id = steps_of(mes_admin, order_id)[0]["id"]
    assert report(mes_admin, order_id, step_id, quantity="10", qualified="10").status_code == 200
    rejected = report(mes_admin, order_id, step_id, quantity="1", qualified="1")
    assert rejected.status_code == 409, rejected.content
    assert rejected.json()["code"] == "STEP_ALREADY_COMPLETED"


def test_report_step_of_other_order_is_rejected(mes_admin, env):
    first = prepared_order(mes_admin, env)
    second = prepared_order(mes_admin, env)
    foreign_step = steps_of(mes_admin, second)[0]["id"]
    rejected = report(mes_admin, first, foreign_step, quantity="1", qualified="1")
    assert rejected.status_code == 400, rejected.content
    assert rejected.json()["code"] == "STEP_ORDER_MISMATCH"


def test_gate_report_requires_inspection_permission(mes_no_quality, env):
    order_id = prepared_order(mes_no_quality, env)
    steps = steps_of(mes_no_quality, order_id)
    assert report(mes_no_quality, order_id, steps[0]["id"], quantity="10").status_code == 200
    denied = report(mes_no_quality, order_id, steps[1]["id"], quantity="10")
    assert denied.status_code == 403, denied.content
    # 整笔回滚：检验单与第二次报工都没有落库
    assert QualityInspectionOrder.objects.count() == 0
    assert ProductionReport.objects.filter(order_id=order_id).count() == 1
    assert ProductionOrderStep.objects.get(pk=steps[1]["id"]).reported_quantity == Decimal("0")


# ---------------------------------------------------------------------------
# 质检门与完工
# ---------------------------------------------------------------------------


def complete_flow(client, env) -> int:
    order_id = prepared_order(client, env)
    for step in steps_of(client, order_id):
        response = report(client, order_id, step["id"], quantity="10", qualified="10")
        assert response.status_code == 200, response.content
    return order_id


def test_gate_report_creates_inspection_order(mes_admin, env):
    order_id = complete_flow(mes_admin, env)
    gate = steps_of(mes_admin, order_id)[1]
    assert gate["inspection_order_id"] is not None
    assert gate["inspection_order_no"].startswith("QC")
    assert gate["inspection_judgement"] == "待判定"
    inspection = QualityInspectionOrder.objects.get(pk=gate["inspection_order_id"])
    assert inspection.source_no == ProductionOrder.objects.get(pk=order_id).order_no


def test_complete_blocked_until_gate_passed(mes_admin, env):
    order_id = complete_flow(mes_admin, env)
    blocked = mes_admin.post(ORDERS_URL + f"{order_id}/complete/", {}, format="json")
    assert blocked.status_code == 409, blocked.content
    assert blocked.json()["code"] == "QUALITY_GATE_NOT_PASSED"

    pass_quality_gate(mes_admin, order_id, env)
    body = complete_order(mes_admin, env, order_id)
    assert body["status"] == ProductionOrderStatus.COMPLETED
    assert body["qualified_quantity"] == "10.000000"
    assert body["scrap_quantity"] == "0.000000"
    assert body["progress_rate"] == "100.00"


def test_complete_requires_all_steps_finished(mes_admin, env):
    order_id = prepared_order(mes_admin, env)
    steps = steps_of(mes_admin, order_id)
    assert report(mes_admin, order_id, steps[0]["id"], quantity="10").status_code == 200
    blocked = mes_admin.post(ORDERS_URL + f"{order_id}/complete/", {}, format="json")
    assert blocked.status_code == 409, blocked.content
    assert blocked.json()["code"] == "STEPS_NOT_FINISHED"


# ---------------------------------------------------------------------------
# 领料与完工入库（统一库存服务）
# ---------------------------------------------------------------------------


def test_issue_materials_posts_issue_document(mes_admin, env):
    order_id = prepared_order(mes_admin, env)
    fabric_before = balance_of(env, env["fabric"])
    button_before = balance_of(env, env["button"])

    issued = mes_admin.post(ORDERS_URL + f"{order_id}/issue-materials/", {}, format="json")
    assert issued.status_code == 200, issued.content
    body = issued.json()
    assert body["issue_document_no"].startswith("ST")
    assert Decimal(balance_of(env, env["fabric"])) == fabric_before - Decimal("28")
    assert Decimal(balance_of(env, env["button"])) == button_before - Decimal("40")

    materials = mes_admin.get(ORDERS_URL + f"{order_id}/materials/").json()
    assert all(Decimal(row["issued_quantity"]) > 0 for row in materials)


def test_issue_materials_twice_is_rejected(mes_admin, env):
    order_id = prepared_order(mes_admin, env)
    assert (
        mes_admin.post(ORDERS_URL + f"{order_id}/issue-materials/", {}, format="json").status_code
        == 200
    )
    again = mes_admin.post(ORDERS_URL + f"{order_id}/issue-materials/", {}, format="json")
    assert again.status_code == 409, again.content
    assert again.json()["code"] == "MATERIAL_ALREADY_ISSUED"
    assert Decimal(balance_of(env, env["fabric"])) == Decimal("72")


def test_issue_materials_without_post_permission_is_rejected(env, registry_permissions, company):
    perms = [code for code in MES_PERMISSIONS if code != "wms.document.post"]
    role = make_role(
        code="test_mes_no_stock_post",
        permission_codes=perms,
        data_scope_type=DataScopeType.COMPANY,
        company=company,
    )
    client = APIClient()
    login(client, make_user(username="mes_no_post_t", role=role, company=company))
    order_id = prepared_order(client, env)
    denied = client.post(ORDERS_URL + f"{order_id}/issue-materials/", {}, format="json")
    assert denied.status_code == 403, denied.content


def test_receipt_creates_inbound_document_and_is_idempotent(mes_admin, env):
    order_id = complete_flow(mes_admin, env)
    pass_quality_gate(mes_admin, order_id, env)
    complete_order(mes_admin, env, order_id)

    headers = {"HTTP_IDEMPOTENCY_KEY": "mes-receipt-key-1"}
    payload = {"location_id": env["fg_location"].pk}
    first = mes_admin.post(ORDERS_URL + f"{order_id}/receipt/", payload, format="json", **headers)
    assert first.status_code == 200, first.content
    assert first.json()["receipt_document_no"].startswith("GR")
    balance = InventoryBalance.objects.get(
        material=env["finished"], location=env["fg_location"], quality_status=QualityStatus.QUALIFIED
    )
    assert balance.on_hand == Decimal("10")

    replay = mes_admin.post(ORDERS_URL + f"{order_id}/receipt/", payload, format="json", **headers)
    assert replay.status_code == 200, replay.content
    assert replay.headers.get("Idempotency-Replayed") == "true"
    assert (
        InventoryBalance.objects.get(
            material=env["finished"], location=env["fg_location"]
        ).on_hand
        == Decimal("10")
    )


def test_receipt_twice_is_rejected_without_idempotency_key(mes_admin, env):
    order_id = complete_flow(mes_admin, env)
    pass_quality_gate(mes_admin, order_id, env)
    complete_order(mes_admin, env, order_id)

    payload = {"location_id": env["fg_location"].pk}
    assert (
        mes_admin.post(ORDERS_URL + f"{order_id}/receipt/", payload, format="json").status_code == 200
    )
    again = mes_admin.post(ORDERS_URL + f"{order_id}/receipt/", payload, format="json")
    assert again.status_code == 409, again.content
    assert again.json()["code"] == "RECEIPT_ALREADY_POSTED"


def test_receipt_requires_finished_status(mes_admin, env):
    order_id = prepared_order(mes_admin, env)
    blocked = mes_admin.post(
        ORDERS_URL + f"{order_id}/receipt/", {"location_id": env["fg_location"].pk}, format="json"
    )
    assert blocked.status_code == 409, blocked.content


# ---------------------------------------------------------------------------
# 关闭、取消与统计
# ---------------------------------------------------------------------------


def test_close_requires_completed_status(mes_admin, env):
    order_id = complete_flow(mes_admin, env)
    blocked = mes_admin.post(ORDERS_URL + f"{order_id}/close/", {}, format="json")
    assert blocked.status_code == 409, blocked.content

    pass_quality_gate(mes_admin, order_id, env, code="QIT-MES-CLOSE")
    complete_order(mes_admin, env, order_id)
    closed = mes_admin.post(ORDERS_URL + f"{order_id}/close/", {}, format="json")
    assert closed.status_code == 200, closed.content
    assert closed.json()["status"] == ProductionOrderStatus.CLOSED


def test_cancel_requires_reason_and_rejects_started_order(mes_admin, env):
    order_id = create_order(mes_admin, env).json()["id"]
    missing = mes_admin.post(ORDERS_URL + f"{order_id}/cancel/", {}, format="json")
    # 请求体缺少 reason 时由序列化器直接拦截（服务层的 REASON_REQUIRED 是第二道闸）
    assert missing.status_code == 400, missing.content

    cancelled = mes_admin.post(
        ORDERS_URL + f"{order_id}/cancel/", {"reason": "客户撤单"}, format="json"
    )
    assert cancelled.status_code == 200, cancelled.content
    assert cancelled.json()["status"] == ProductionOrderStatus.CANCELLED

    started = prepared_order(mes_admin, env)
    step_id = steps_of(mes_admin, started)[0]["id"]
    assert report(mes_admin, started, step_id, quantity="1", qualified="1").status_code == 200
    blocked = mes_admin.post(ORDERS_URL + f"{started}/cancel/", {"reason": "改单"}, format="json")
    assert blocked.status_code == 409, blocked.content


def test_statistics_aggregates_live_details(mes_admin, env):
    order_id = prepared_order(mes_admin, env)
    steps = steps_of(mes_admin, order_id)
    assert (
        report(
            mes_admin,
            order_id,
            steps[0]["id"],
            quantity="10",
            qualified="9",
            scrap_quantity="1",
        ).status_code
        == 200
    )
    assert (
        report(mes_admin, order_id, steps[1]["id"], quantity="10", qualified="10").status_code == 200
    )

    response = mes_admin.get(STATS_URL)
    assert response.status_code == 200, response.content
    body = response.json()
    assert body["total"] == 1
    assert body["in_progress_total"] == 1
    assert body["planned_quantity"] == "10.000000"
    assert body["output_quantity"] == "10.000000"
    assert body["qualified_quantity"] == "10.000000"
    assert body["final_yield_rate"] == "100.00"
    assert body["process_reported_quantity"] == "20.000000"
    assert body["process_scrap_quantity"] == "1.000000"
    assert body["process_scrap_rate"] == "5.00"
    assert body["pending_gate_total"] == 1
    assert body["report_total"] == 2
    assert [row["value"] for row in body["by_status"]] == [
        "draft",
        "released",
        "in_progress",
        "completed",
        "closed",
        "cancelled",
    ]
    assert body["scrap_by_step"][0]["step_name"] == "缝制"


def test_report_ledger_is_read_only(mes_admin, env):
    order_id = prepared_order(mes_admin, env)
    step_id = steps_of(mes_admin, order_id)[0]["id"]
    created = mes_admin.post(
        REPORTS_URL,
        {"order_id": order_id, "step_id": step_id, "quantity": "3", "qualified_quantity": "3"},
        format="json",
    )
    assert created.status_code == 201, created.content
    report_id = created.json()["id"]

    assert (
        mes_admin.patch(
            REPORTS_URL + f"{report_id}/", {"quantity": "99"}, format="json"
        ).status_code
        == 405
    )
    assert mes_admin.delete(REPORTS_URL + f"{report_id}/").status_code == 405


def test_report_endpoint_requires_order(mes_admin, env):
    order_id = prepared_order(mes_admin, env)
    step_id = steps_of(mes_admin, order_id)[0]["id"]
    rejected = mes_admin.post(
        REPORTS_URL, {"step_id": step_id, "quantity": "1", "qualified_quantity": "1"}, format="json"
    )
    assert rejected.status_code == 400, rejected.content
    assert rejected.json()["code"] == "ORDER_REQUIRED"
