"""销售模块用例（任务书 10.3、12.1、14.2 第 5/6/7/9 条）。

覆盖：

* 销售订单 草稿 → 提交审批 → 批准 → 库存占用 → 发货出库 → 退货的完整链路；
* **金额一律由后端计算**，前端传入的金额字段被忽略；
* 停用/终止客户不能下单（与采购侧供应商停用规则对应）；
* **占用幂等**：重复点击「库存占用」不重复扣减可用量，且**不改实存量**；
* 只能占用**合格**库存；待检 / 不合格库存不能用于销售（任务书 10.8、14.2 第 9 条）；
* **未占用不允许发货**（`RESERVATION_REQUIRED`），发货必须消耗本订单占用；
* 发货过账幂等（`Idempotency-Key`）：重复提交不重复扣库存；
* 退货「先收货待检、再检验判定」；退货数量不得超过「已发货 - 已退货」；
* 操作权限、职责分离、数据范围与跨公司隔离。

库存事实全部通过统一库存服务（`apps.wms.services.stock`）产生，测试直接读取
`InventoryBalance` / `InventoryTransaction` 校验，不新建任何库存体系。
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from apps.core.exceptions import StateConflict
from apps.core.models import AuditLog, CodeRule, ResetPeriod
from apps.crm.models import Customer, CustomerStatus
from apps.identity.models import DataScopeType
from apps.masterdata.models import Material, MaterialCategory, UoM
from apps.sales.models import (
    ReturnDisposition,
    ReturnStatus,
    SalesOrder,
    SalesOrderStatus,
    SalesShipment,
    ShipmentStatus,
)
from apps.wms.models import (
    DocumentType,
    InventoryBalance,
    InventoryTransaction,
    Location,
    QualityStatus,
    ReservationStatus,
    StockReservation,
    Warehouse,
    Zone,
)
from apps.wms.services import stock
from tests.conftest import make_role, make_user

pytestmark = pytest.mark.django_db

ORDERS_URL = "/api/v1/sales/orders/"
SHIPMENTS_URL = "/api/v1/sales/shipments/"
RETURNS_URL = "/api/v1/sales/returns/"
INSTANCES_URL = "/api/v1/workflow/instances/"
LOGIN_URL = "/api/v1/identity/auth/login/"
PASSWORD = "Tst!Passw0rd2026"

SALES_PERMISSIONS = [
    "sales.order.view",
    "sales.order.create",
    "sales.order.update",
    "sales.order.submit",
    "sales.order.close",
    "sales.order.reserve",
    "sales.order.release",
    "sales.shipment.view",
    "sales.shipment.create",
    "sales.shipment.update",
    "sales.shipment.post",
    "sales.return.view",
    "sales.return.create",
    "sales.return.update",
    "sales.return.post",
    "crm.customer.view",
    "masterdata.material.view",
    "wms.inventory.view",
    "wms.document.view",
    # 占用、过账、质量转换最终都由统一库存服务记账：跨模块动作必须同时具备库存侧权限
    "wms.inventory.reserve",
    "wms.inventory.release",
    "wms.document.create",
    "wms.document.post",
    "wms.quality.release",
]

# 与 bootstrap_system 内置「质检员」角色一致：质量放行要经统一库存服务落库，
# 因此除业务权限外还必须有 wms.quality.release + wms.document.create/post。
INSPECT_PERMISSIONS = [
    "sales.return.view",
    "sales.return.inspect",
    "wms.inventory.view",
    "wms.quality.release",
    "wms.document.create",
    "wms.document.post",
]


def login(client, user) -> None:
    response = client.post(
        LOGIN_URL, {"username": user.username, "password": PASSWORD}, format="json"
    )
    assert response.status_code == 200, response.content


@pytest.fixture
def sales_code_rules(db):
    """取号依赖编码规则；测试库不跑 bootstrap_system，这里显式建规则。"""
    for code, name, pattern in (
        ("SO", "销售订单号", "SO{YYYYMMDD}{SEQ:4}"),
        ("SH", "销售发货单号", "SH{YYYYMMDD}{SEQ:4}"),
        ("SR", "销售退货单号", "SR{YYYYMMDD}{SEQ:4}"),
        ("ST", "质量转换单号", "ST{YYYYMMDD}{SEQ:4}"),
        ("GR", "采购入库单号", "GR{YYYYMMDD}{SEQ:4}"),
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
def env(company, other_company, department_factory, sales_code_rules):
    """最小销售环境：物料 + 仓库/储位 + 客户 + 100 合格库存 + 服务层调用用户。"""
    category = MaterialCategory.objects.create(
        code="SAL-CAT", name="销售物料分类", category_type="finished"
    )
    uom = UoM.objects.create(code="SAL-PCS", name="件", category="quantity")
    material = Material.objects.create(
        company=company,
        code="SAL-M1",
        name="女士风衣",
        category=category,
        base_uom=uom,
        purchase_price=Decimal("199.000000"),
    )
    warehouse = Warehouse.objects.create(
        company=company,
        code="SAL-WH",
        name="成品仓",
        warehouse_type="finished",
        factory=department_factory["factories"]["F01"],
    )
    zone = Zone.objects.create(warehouse=warehouse, code="Z1", name="成品区")
    location = Location.objects.create(zone=zone, code="L1", name="发货暂存位")
    customer = Customer.objects.create(
        company=company, code="SAL-C1", name="杭州示例服饰有限公司", status=CustomerStatus.ACTIVE
    )
    suspended = Customer.objects.create(
        company=company, code="SAL-C2", name="已停用客户", status=CustomerStatus.SUSPENDED
    )
    svc_user = make_user(username="sal_svc", company=company, is_superuser=True)
    # 合格库存 100 件直接由统一库存服务写入，避免测试绕过库存服务造数
    document = stock.create_document(
        document_type=DocumentType.RECEIPT,
        company=company.pk,
        warehouse=warehouse,
        user=svc_user,
        lines=[
            {
                "material_id": material.pk,
                "location_id": location.pk,
                "quality_status": QualityStatus.QUALIFIED,
                "direction": "in",
                "quantity": Decimal("100"),
            }
        ],
    )
    stock.post_document(document, user=svc_user)
    return {
        "company": company,
        "other_company": other_company,
        "category": category,
        "material": material,
        "uom": uom,
        "warehouse": warehouse,
        "location": location,
        "customer": customer,
        "suspended_customer": suspended,
        "svc_user": svc_user,
    }


def _make_api_user(registry_permissions, company, username: str, perms: list[str]):
    role = make_role(
        code=f"test_sal_{username}",
        permission_codes=perms,
        data_scope_type=DataScopeType.COMPANY,
        company=company,
    )
    return role, make_user(username=username, role=role, company=company)


@pytest.fixture
def api_user_client(registry_permissions, company):
    """为一个测试身份创建**独立**的 APIClient，避免会话互相覆盖。"""
    from rest_framework.test import APIClient

    def _make(username: str, perms: list[str]):
        user = _make_api_user(registry_permissions, company, username, perms)[1]
        client = APIClient()
        login(client, user)
        return client

    return _make


@pytest.fixture
def sales_client(api_user_client):
    return api_user_client("sal_clerk", SALES_PERMISSIONS)


@pytest.fixture
def inspector_client(api_user_client):
    """质检员：只有检验判定权限，不能新建/修改销售单据（职责分离）。"""
    return api_user_client("sal_inspector", INSPECT_PERMISSIONS)


@pytest.fixture
def approver_role(registry_permissions, company):
    return _make_api_user(
        registry_permissions,
        company,
        "sal_approver",
        ["workflow.instance.view", "workflow.instance.approve", "sales.order.view"],
    )[0]


@pytest.fixture
def approver_client(registry_permissions, company, approver_role):
    from rest_framework.test import APIClient

    client = APIClient()
    login(client, make_user(username="sal_approver_u", role=approver_role, company=company))
    return client


@pytest.fixture
def order_template(db, approver_role):
    from apps.workflow.models import ApprovalTemplate, ApprovalTemplateNode

    template = ApprovalTemplate.objects.create(
        code="TPL-SO-T", name="销售订单审批", biz_type="sales.order", is_active=True
    )
    ApprovalTemplateNode.objects.create(
        template=template,
        seq=1,
        name="销售主管审批",
        approver_type="role",
        approver_role=approver_role,
    )
    return template
# ---------------------------------------------------------------------------
# 公共辅助
# ---------------------------------------------------------------------------


def _order_payload(env, *, quantity="10", price="199", material=None, **extra) -> dict:
    payload = {
        "customer_id": env["customer"].pk,
        "warehouse_id": env["warehouse"].pk,
        "lines": [
            {
                "material_id": (material or env["material"]).pk,
                "quantity": quantity,
                "price": price,
            }
        ],
    }
    payload.update(extra)
    return payload


def _create_order(client, env, **extra) -> SalesOrder:
    response = client.post(ORDERS_URL, _order_payload(env, **extra), format="json")
    assert response.status_code == 201, response.content
    return SalesOrder.objects.get(pk=response.json()["id"])


def _approve(client, order: SalesOrder, approver_client) -> dict:
    submitted = client.post(f"{ORDERS_URL}{order.pk}/submit/", {}, format="json")
    assert submitted.status_code == 200, submitted.content
    instance_id = submitted.json()["approval_instance_id"]
    approved = approver_client.post(
        f"{INSTANCES_URL}{instance_id}/approve/", {"comment": "同意"}, format="json"
    )
    assert approved.status_code == 200, approved.content
    return approved.json()


def _balance(env, *, quality=QualityStatus.QUALIFIED, location=None) -> InventoryBalance:
    return InventoryBalance.objects.get(
        material=env["material"],
        warehouse=env["warehouse"],
        location=location if location is not None else env["location"],
        quality_status=quality,
    )


def _shipment_payload(env, order: SalesOrder, *, quantity="10", location=None, **extra) -> dict:
    line = order.lines.order_by("line_no").first()
    payload = {
        "sales_order_id": order.pk,
        "warehouse_id": env["warehouse"].pk,
        "lines": [{"order_line_id": line.pk, "quantity": quantity}],
    }
    if location is not None:
        payload["lines"][0]["location_id"] = location.pk
    payload.update(extra)
    return payload


def _create_shipment(client, env, order, **extra) -> SalesShipment:
    response = client.post(SHIPMENTS_URL, _shipment_payload(env, order, **extra), format="json")
    assert response.status_code == 201, response.content
    return SalesShipment.objects.get(pk=response.json()["id"])


def _return_payload(env, order: SalesOrder, *, quantity="10", location=None, **extra) -> dict:
    line = order.lines.order_by("line_no").first()
    payload = {
        "sales_order_id": order.pk,
        "warehouse_id": env["warehouse"].pk,
        "reason": "客户反馈尺码不符",
        "lines": [{"order_line_id": line.pk, "quantity": quantity}],
    }
    if location is not None:
        payload["lines"][0]["location_id"] = location.pk
    payload.update(extra)
    return payload


def _create_return(client, env, order, **extra):
    response = client.post(RETURNS_URL, _return_payload(env, order, **extra), format="json")
    assert response.status_code == 201, response.content
    return response.json()


def _issue(env, quantity, *, user, quality=QualityStatus.QUALIFIED, batch_no=""):
    """直接走统一库存服务做一张出库单，用于验证质量门禁（不是业务链路）。"""
    document = stock.create_document(
        document_type=DocumentType.ISSUE,
        company=env["company"].pk,
        warehouse=env["warehouse"],
        user=user,
        lines=[
            {
                "material_id": env["material"].pk,
                "location_id": env["location"].pk,
                "batch_no": batch_no,
                "quality_status": quality,
                "direction": "out",
                "quantity": Decimal(str(quantity)),
            }
        ],
    )
    return stock.post_document(document, user=user)


def _reserve(client, order: SalesOrder) -> dict:
    response = client.post(f"{ORDERS_URL}{order.pk}/reserve/", {}, format="json")
    assert response.status_code == 200, response.content
    return response.json()


@pytest.fixture
def approved_order(sales_client, approver_client, env, order_template):
    """一张已批准、数量 10 的销售订单（走真实提交 + 审批路径）。"""
    order = _create_order(sales_client, env, quantity="10", price="199")
    _approve(sales_client, order, approver_client)
    order.refresh_from_db()
    assert order.status == SalesOrderStatus.APPROVED
    return order


@pytest.fixture
def shipped_order(sales_client, env, approved_order):
    """已占用并全部发货 10 件的订单，用于退货链路。"""
    _reserve(sales_client, approved_order)
    shipment = _create_shipment(sales_client, env, approved_order, quantity="10")
    response = sales_client.post(
        f"{SHIPMENTS_URL}{shipment.pk}/post/",
        {},
        format="json",
        HTTP_IDEMPOTENCY_KEY=f"fixture-ship-{shipment.pk}",
    )
    assert response.status_code == 200, response.content
    approved_order.refresh_from_db()
    assert approved_order.status == SalesOrderStatus.SHIPPED
    return approved_order


# ---------------------------------------------------------------------------
# 认证与权限
# ---------------------------------------------------------------------------


def test_sales_endpoints_require_authentication(api_client):
    assert api_client.get(ORDERS_URL).status_code in (401, 403)
    assert api_client.get(SHIPMENTS_URL).status_code in (401, 403)
    assert api_client.get(RETURNS_URL).status_code in (401, 403)


def test_view_only_user_cannot_create_order(api_client, registry_permissions, company, env):
    user = _make_api_user(registry_permissions, company, "sal_viewer", ["sales.order.view"])[1]
    login(api_client, user)
    assert api_client.get(ORDERS_URL).status_code == 200
    response = api_client.post(ORDERS_URL, _order_payload(env), format="json")
    assert response.status_code == 403, response.content


def test_user_without_reserve_permission_cannot_reserve(api_client, registry_permissions, company, env):
    """有销售订单查看权限但没有库存占用权限时，占用接口必须被拒绝。"""
    user = _make_api_user(
        registry_permissions, company, "sal_no_reserve", ["sales.order.view"]
    )[1]
    login(api_client, user)
    order = SalesOrder.objects.create(
        company=company, order_no="SO-NOPERM", customer=env["customer"], status=SalesOrderStatus.APPROVED
    )
    response = api_client.post(f"{ORDERS_URL}{order.pk}/reserve/", {}, format="json")
    assert response.status_code == 403, response.content
    assert _balance(env).reserved == Decimal("0.000000")


# ---------------------------------------------------------------------------
# 销售订单：金额、校验、审批
# ---------------------------------------------------------------------------


def test_order_amount_is_computed_by_backend(sales_client, env):
    """前端提交的金额被忽略，金额与税额由后端 ROUND_HALF_UP 计算。"""
    response = sales_client.post(
        ORDERS_URL,
        {
            **_order_payload(env, quantity="3", price="199.0001"),
            "tax_rate": "13",
            "total_amount": "999999",
            "amount_with_tax": "999999",
            "lines": [
                {
                    "material_id": env["material"].pk,
                    "quantity": "3",
                    "price": "199.0001",
                    "amount": "888888",
                }
            ],
        },
        format="json",
    )
    assert response.status_code == 201, response.content
    body = response.json()
    assert body["total_amount"] == "597.0003"
    assert body["tax_amount"] == "77.6100"
    assert body["amount_with_tax"] == "674.6103"
    assert body["lines"][0]["amount"] == "597.0003"


def test_order_rejects_non_positive_quantity(sales_client, env):
    response = sales_client.post(ORDERS_URL, _order_payload(env, quantity="0"), format="json")
    assert response.status_code == 400, response.content


def test_suspended_customer_cannot_be_used(sales_client, env):
    response = sales_client.post(
        ORDERS_URL,
        {**_order_payload(env), "customer_id": env["suspended_customer"].pk},
        format="json",
    )
    assert response.status_code == 409, response.content
    assert response.json()["code"] == "CUSTOMER_INACTIVE"


def test_order_submit_then_approve_writes_back_status(
    sales_client, approver_client, env, order_template
):
    order = _create_order(sales_client, env)
    submitted = sales_client.post(f"{ORDERS_URL}{order.pk}/submit/", {}, format="json")
    assert submitted.status_code == 200, submitted.content
    assert submitted.json()["status"] == SalesOrderStatus.SUBMITTED
    instance_id = submitted.json()["approval_instance_id"]
    approved = approver_client.post(
        f"{INSTANCES_URL}{instance_id}/approve/", {"comment": "同意"}, format="json"
    )
    assert approved.status_code == 200, approved.content
    order.refresh_from_db()
    assert order.status == SalesOrderStatus.APPROVED
    assert order.approved_at is not None
    assert AuditLog.objects.filter(
        approval_basis=f"workflow.ApprovalInstance#{instance_id}"
    ).exists()


def test_order_approval_rejection_writes_back_rejected(
    sales_client, approver_client, env, order_template
):
    order = _create_order(sales_client, env)
    submitted = sales_client.post(f"{ORDERS_URL}{order.pk}/submit/", {}, format="json")
    instance_id = submitted.json()["approval_instance_id"]
    rejected = approver_client.post(
        f"{INSTANCES_URL}{instance_id}/reject/", {"comment": "价格超标"}, format="json"
    )
    assert rejected.status_code == 200, rejected.content
    order.refresh_from_db()
    assert order.status == SalesOrderStatus.REJECTED
# ---------------------------------------------------------------------------
# 库存占用：幂等、只动占用量、只能占合格库存
# ---------------------------------------------------------------------------


def test_reserve_requires_approved_order(sales_client, env, order_template):
    order = _create_order(sales_client, env)
    response = sales_client.post(f"{ORDERS_URL}{order.pk}/reserve/", {}, format="json")
    assert response.status_code == 409, response.content
    assert response.json()["code"] == "ORDER_NOT_RESERVABLE"


def test_reserve_moves_available_to_reserved_without_touching_on_hand(
    sales_client, approved_order, env
):
    """占用只改可用量：实存量不变，且**不写库存流水**（流水只记实存量增减）。"""
    transaction_count = InventoryTransaction.objects.count()
    response = sales_client.post(f"{ORDERS_URL}{approved_order.pk}/reserve/", {}, format="json")
    assert response.status_code == 200, response.content
    reserved_rows = response.json()["reserved"]
    assert len(reserved_rows) == 1
    assert reserved_rows[0]["quantity"] == "10.000000"
    assert reserved_rows[0]["status"] == ReservationStatus.ACTIVE

    balance = _balance(env)
    assert balance.on_hand == Decimal("100.000000")
    assert balance.reserved == Decimal("10.000000")
    assert balance.available == Decimal("90.000000")
    assert InventoryTransaction.objects.count() == transaction_count

    reservation = StockReservation.objects.get(pk=reserved_rows[0]["reservation_id"])
    assert reservation.open_quantity == Decimal("10.000000")
    assert reservation.consumed_quantity == Decimal("0.000000")


def test_reserve_is_idempotent(sales_client, approved_order, env):
    """重复点击「库存占用」不重复扣减可用量（任务书 7.2）。"""
    first = _reserve(sales_client, approved_order)
    second = _reserve(sales_client, approved_order)
    assert first["reserved"][0]["reservation_id"] == second["reserved"][0]["reservation_id"]
    assert _balance(env).reserved == Decimal("10.000000")
    assert StockReservation.objects.filter(biz_id=str(approved_order.pk)).count() == 1


def test_reserve_rejects_insufficient_available(sales_client, approver_client, env, order_template):
    order = _create_order(sales_client, env, quantity="150", price="199")
    _approve(sales_client, order, approver_client)
    response = sales_client.post(f"{ORDERS_URL}{order.pk}/reserve/", {}, format="json")
    assert response.status_code == 409, response.content
    assert response.json()["code"] == "INSUFFICIENT_STOCK"
    # 失败必须整体回滚：不能留下半截占用，也不能改动可用量
    assert not StockReservation.objects.filter(biz_id=str(order.pk)).exists()
    assert _balance(env).reserved == Decimal("0.000000")


def test_reserve_rejects_quarantine_stock(
    sales_client, approver_client, env, order_template
):
    """待检库存不能用于销售占用（任务书 10.8 / 14.2 第 9 条）。"""
    material = Material.objects.create(
        company=env["company"],
        code="SAL-M2",
        name="待检成品",
        category=env["category"],
        base_uom=env["uom"],
    )
    document = stock.create_document(
        document_type=DocumentType.RECEIPT,
        company=env["company"].pk,
        warehouse=env["warehouse"],
        user=env["svc_user"],
        lines=[
            {
                "material_id": material.pk,
                "location_id": env["location"].pk,
                "quality_status": QualityStatus.QUARANTINE,
                "direction": "in",
                "quantity": Decimal("50"),
            }
        ],
    )
    stock.post_document(document, user=env["svc_user"])
    order = _create_order(sales_client, env, quantity="5", material=material)
    _approve(sales_client, order, approver_client)
    response = sales_client.post(f"{ORDERS_URL}{order.pk}/reserve/", {}, format="json")
    assert response.status_code == 409, response.content
    assert response.json()["code"] == "INSUFFICIENT_STOCK"
    assert Decimal(response.json()["details"]["available"]) == Decimal("0")


def test_reserve_uses_matching_batch_dimension(
    sales_client, approver_client, env, order_template
):
    """按批次存放的成品：占用维度（储位 + 批次）必须与出库维度一致。

    演示数据里的成品就是按批次入库的，若占用与出库维度不一致，
    `require_full_reservation` 会误判为「占用覆盖不足」。
    """
    material = Material.objects.create(
        company=env["company"],
        code="SAL-M3",
        name="批次成品",
        category=env["category"],
        base_uom=env["uom"],
    )
    document = stock.create_document(
        document_type=DocumentType.RECEIPT,
        company=env["company"].pk,
        warehouse=env["warehouse"],
        user=env["svc_user"],
        lines=[
            {
                "material_id": material.pk,
                "location_id": env["location"].pk,
                "batch_no": "FG-B1",
                "quality_status": QualityStatus.QUALIFIED,
                "direction": "in",
                "quantity": Decimal("30"),
            }
        ],
    )
    stock.post_document(document, user=env["svc_user"])

    order = _create_order(sales_client, env, quantity="20", price="99", material=material)
    _approve(sales_client, order, approver_client)
    _reserve(sales_client, order)
    reservation = StockReservation.objects.get(biz_id=str(order.pk))
    assert reservation.batch_no == "FG-B1"
    assert reservation.location_id == env["location"].pk

    # 发货单行不填储位 / 批次：后端按占用维度出库
    shipment = _create_shipment(sales_client, env, order, quantity="20")
    response = sales_client.post(
        f"{SHIPMENTS_URL}{shipment.pk}/post/",
        {},
        format="json",
        HTTP_IDEMPOTENCY_KEY=f"sal-ship-batch-{shipment.pk}",
    )
    assert response.status_code == 200, response.content
    balance = InventoryBalance.objects.get(
        material=material,
        warehouse=env["warehouse"],
        location=env["location"],
        batch_no="FG-B1",
        quality_status=QualityStatus.QUALIFIED,
    )
    assert balance.on_hand == Decimal("10.000000")
    assert balance.reserved == Decimal("0.000000")


def test_release_order_stock_returns_available(sales_client, approved_order, env):
    _reserve(sales_client, approved_order)
    response = sales_client.post(
        f"{ORDERS_URL}{approved_order.pk}/release/", {"reason": "订单暂缓发货"}, format="json"
    )
    assert response.status_code == 200, response.content
    assert response.json()["released_count"] == 1
    balance = _balance(env)
    assert balance.on_hand == Decimal("100.000000")
    assert balance.reserved == Decimal("0.000000")
    assert balance.available == Decimal("100.000000")
    assert StockReservation.objects.get(biz_id=str(approved_order.pk)).status == (
        ReservationStatus.CANCELLED
    )


def test_cancel_order_releases_open_reservations(sales_client, approved_order, env):
    _reserve(sales_client, approved_order)
    response = sales_client.post(
        f"{ORDERS_URL}{approved_order.pk}/cancel/", {"reason": "客户取消订单"}, format="json"
    )
    assert response.status_code == 200, response.content
    assert response.json()["status"] == SalesOrderStatus.CANCELLED
    assert _balance(env).reserved == Decimal("0.000000")


# ---------------------------------------------------------------------------
# 销售发货：必须先占用，过账幂等
# ---------------------------------------------------------------------------


def test_shipment_requires_reservation(sales_client, approved_order, env):
    """未占用不允许出库：占用覆盖校验在锁内执行。"""
    shipment = _create_shipment(sales_client, env, approved_order, quantity="10")
    response = sales_client.post(
        f"{SHIPMENTS_URL}{shipment.pk}/post/",
        {},
        format="json",
        HTTP_IDEMPOTENCY_KEY=f"sal-ship-norsv-{shipment.pk}",
    )
    assert response.status_code == 409, response.content
    assert response.json()["code"] == "RESERVATION_REQUIRED"
    # 拒绝后库存与单据状态都必须回滚
    shipment.refresh_from_db()
    assert shipment.status == ShipmentStatus.DRAFT
    assert _balance(env).on_hand == Decimal("100.000000")


def test_shipment_quantity_cannot_exceed_remaining(sales_client, approved_order, env):
    response = sales_client.post(
        SHIPMENTS_URL, _shipment_payload(env, approved_order, quantity="10.000001"), format="json"
    )
    assert response.status_code == 400, response.content
    assert response.json()["code"] == "OVER_SHIPMENT"


def test_shipment_post_consumes_reservation_and_decrements_on_hand(
    sales_client, approved_order, env
):
    _reserve(sales_client, approved_order)
    shipment = _create_shipment(sales_client, env, approved_order, quantity="10")
    response = sales_client.post(
        f"{SHIPMENTS_URL}{shipment.pk}/post/",
        {},
        format="json",
        HTTP_IDEMPOTENCY_KEY=f"sal-ship-post-{shipment.pk}",
    )
    assert response.status_code == 200, response.content
    body = response.json()
    assert body["status"] == ShipmentStatus.POSTED
    assert body["issue_document_id"]

    balance = _balance(env)
    assert balance.on_hand == Decimal("90.000000")
    assert balance.reserved == Decimal("0.000000")
    assert balance.available == Decimal("90.000000")

    reservation = StockReservation.objects.get(biz_id=str(approved_order.pk))
    assert reservation.status == ReservationStatus.CLOSED
    assert reservation.consumed_quantity == Decimal("10.000000")

    approved_order.refresh_from_db()
    assert approved_order.status == SalesOrderStatus.SHIPPED
    assert approved_order.lines.first().shipped_quantity == Decimal("10.000000")


def test_shipment_post_is_idempotent(sales_client, approved_order, env):
    """同一 Idempotency-Key 重放不重复扣库存；已过账单据再次过账也不重复扣。"""
    _reserve(sales_client, approved_order)
    shipment = _create_shipment(sales_client, env, approved_order, quantity="6")
    headers = {"HTTP_IDEMPOTENCY_KEY": f"sal-ship-idem-{shipment.pk}"}
    first = sales_client.post(f"{SHIPMENTS_URL}{shipment.pk}/post/", {}, format="json", **headers)
    assert first.status_code == 200, first.content
    second = sales_client.post(f"{SHIPMENTS_URL}{shipment.pk}/post/", {}, format="json", **headers)
    assert second.status_code == 200, second.content
    assert second.headers.get("Idempotency-Replayed") == "true"
    third = sales_client.post(
        f"{SHIPMENTS_URL}{shipment.pk}/post/",
        {},
        format="json",
        HTTP_IDEMPOTENCY_KEY=f"sal-ship-idem-retry-{shipment.pk}",
    )
    assert third.status_code == 200, third.content

    assert _balance(env).on_hand == Decimal("94.000000")
    approved_order.refresh_from_db()
    assert approved_order.lines.first().shipped_quantity == Decimal("6.000000")
    assert approved_order.status == SalesOrderStatus.PARTIALLY_SHIPPED


def test_order_without_warehouse_cannot_reserve(sales_client, approver_client, env, order_template):
    """订单未指定发货仓库时不能占用，错误必须明确而不是静默占用到默认仓。"""
    order = _create_order(sales_client, env, warehouse_id=None, quantity="2")
    _approve(sales_client, order, approver_client)
    response = sales_client.post(f"{ORDERS_URL}{order.pk}/reserve/", {}, format="json")
    assert response.status_code == 400, response.content
    assert response.json()["code"] == "WAREHOUSE_REQUIRED"
# ---------------------------------------------------------------------------
# 销售退货：先收货待检、再检验判定
# ---------------------------------------------------------------------------


def test_return_requires_posted_shipment(sales_client, approved_order, env):
    response = sales_client.post(
        RETURNS_URL, _return_payload(env, approved_order, quantity="1"), format="json"
    )
    assert response.status_code == 409, response.content
    assert response.json()["code"] == "NO_SHIPMENT"


def test_return_quantity_cannot_exceed_shipped(sales_client, shipped_order, env):
    response = sales_client.post(
        RETURNS_URL, _return_payload(env, shipped_order, quantity="10.000001"), format="json"
    )
    assert response.status_code == 400, response.content
    assert response.json()["code"] == "OVER_RETURN"


def test_return_must_be_posted_before_inspect(sales_client, inspector_client, shipped_order, env):
    return_doc = _create_return(sales_client, env, shipped_order, quantity="4")
    response = inspector_client.post(
        f"{RETURNS_URL}{return_doc['id']}/inspect/",
        {"result": "qualified", "remark": "外观检查合格"},
        format="json",
    )
    assert response.status_code == 409, response.content
    assert response.json()["code"] == "STATE_CONFLICT"


def test_inspect_requires_remark(sales_client, inspector_client, shipped_order, env):
    return_doc = _create_return(sales_client, env, shipped_order, quantity="4")
    sales_client.post(f"{RETURNS_URL}{return_doc['id']}/post/", {}, format="json")
    response = inspector_client.post(
        f"{RETURNS_URL}{return_doc['id']}/inspect/", {"result": "qualified", "remark": ""}, format="json"
    )
    assert response.status_code == 400, response.content
    assert response.json()["code"] == "REASON_REQUIRED"


def test_return_post_lands_in_quarantine(sales_client, shipped_order, env):
    """退货收货只把货物计入**待检**库存，此时不能再销售。"""
    return_doc = _create_return(
        sales_client, env, shipped_order, quantity="4", location=env["location"]
    )
    response = sales_client.post(f"{RETURNS_URL}{return_doc['id']}/post/", {}, format="json")
    assert response.status_code == 200, response.content
    body = response.json()
    assert body["status"] == ReturnStatus.POSTED
    assert body["inspection_result"] == ReturnDisposition.NONE

    quarantine = _balance(env, quality=QualityStatus.QUARANTINE)
    assert quarantine.on_hand == Decimal("4.000000")
    # 可用量是纯数量口径（实存-冻结-占用）；待检库存的「不可动用」由质量门禁执行，
    # 因此这里断言待检库存确实无法出库，而不是断言 available=0。
    with pytest.raises(StateConflict) as excinfo:
        _issue(env, 1, user=env["svc_user"], quality=QualityStatus.QUARANTINE)
    assert excinfo.value.code == "QUALITY_NOT_RELEASED"
    # 已发货 10、已退货 4 → 可退 6
    shipped_order.refresh_from_db()
    line = shipped_order.lines.first()
    assert line.returned_quantity == Decimal("4.000000")
    assert line.returnable_quantity == Decimal("6.000000")


def test_return_inherits_original_batch(sales_client, approver_client, env, order_template):
    """退货入库继承原发货批次：行上不填批次时不会落到「无批次」维度（任务书 9.4）。"""
    material = Material.objects.create(
        company=env["company"],
        code="SAL-M4",
        name="批次退货成品",
        category=env["category"],
        base_uom=env["uom"],
    )
    document = stock.create_document(
        document_type=DocumentType.RECEIPT,
        company=env["company"].pk,
        warehouse=env["warehouse"],
        user=env["svc_user"],
        lines=[
            {
                "material_id": material.pk,
                "location_id": env["location"].pk,
                "batch_no": "FG-B2",
                "quality_status": QualityStatus.QUALIFIED,
                "direction": "in",
                "quantity": Decimal("30"),
            }
        ],
    )
    stock.post_document(document, user=env["svc_user"])

    order = _create_order(sales_client, env, quantity="10", price="99", material=material)
    _approve(sales_client, order, approver_client)
    _reserve(sales_client, order)
    shipment = _create_shipment(sales_client, env, order, quantity="10")
    posted = sales_client.post(
        f"{SHIPMENTS_URL}{shipment.pk}/post/",
        {},
        format="json",
        HTTP_IDEMPOTENCY_KEY=f"sal-ret-batch-{shipment.pk}",
    )
    assert posted.status_code == 200, posted.content

    return_doc = _create_return(sales_client, env, order, quantity="4", shipment_id=shipment.pk)
    assert return_doc["lines"][0]["batch_no"] == ""
    received = sales_client.post(f"{RETURNS_URL}{return_doc['id']}/post/", {}, format="json")
    assert received.status_code == 200, received.content

    quarantine = InventoryBalance.objects.get(
        material=material,
        warehouse=env["warehouse"],
        location=env["location"],
        batch_no="FG-B2",
        quality_status=QualityStatus.QUARANTINE,
    )
    assert quarantine.on_hand == Decimal("4.000000")


def test_inspect_qualified_returns_stock_to_qualified(
    sales_client, inspector_client, shipped_order, env
):
    return_doc = _create_return(
        sales_client, env, shipped_order, quantity="4", location=env["location"]
    )
    sales_client.post(f"{RETURNS_URL}{return_doc['id']}/post/", {}, format="json")
    response = inspector_client.post(
        f"{RETURNS_URL}{return_doc['id']}/inspect/",
        {"result": "qualified", "remark": "复检合格，可再销售"},
        format="json",
        HTTP_IDEMPOTENCY_KEY=f"sal-ret-insp-{return_doc['id']}",
    )
    assert response.status_code == 200, response.content
    body = response.json()
    assert body["status"] == ReturnStatus.INSPECTED
    assert body["inspection_result"] == ReturnDisposition.QUALIFIED
    assert body["inspected_by_name"]

    assert _balance(env, quality=QualityStatus.QUARANTINE).on_hand == Decimal("0.000000")
    assert _balance(env, quality=QualityStatus.QUALIFIED).on_hand == Decimal("94.000000")
    assert _balance(env, quality=QualityStatus.QUALIFIED).available == Decimal("94.000000")


def test_inspect_rejected_keeps_stock_unusable(sales_client, inspector_client, shipped_order, env):
    return_doc = _create_return(
        sales_client, env, shipped_order, quantity="4", location=env["location"]
    )
    sales_client.post(f"{RETURNS_URL}{return_doc['id']}/post/", {}, format="json")
    response = inspector_client.post(
        f"{RETURNS_URL}{return_doc['id']}/inspect/",
        {"result": "rejected", "remark": "面料色差，判定不合格"},
        format="json",
    )
    assert response.status_code == 200, response.content
    assert response.json()["inspection_result"] == ReturnDisposition.REJECTED

    rejected = _balance(env, quality=QualityStatus.REJECTED)
    assert rejected.on_hand == Decimal("4.000000")
    # 不合格库存不可动用：合格库存仍是发货后的 90，且不合格维度出库被拒绝
    assert _balance(env, quality=QualityStatus.QUALIFIED).on_hand == Decimal("90.000000")
    with pytest.raises(StateConflict) as excinfo:
        _issue(env, 1, user=env["svc_user"], quality=QualityStatus.REJECTED)
    assert excinfo.value.code == "QUALITY_NOT_RELEASED"


def test_repeated_inspect_is_rejected(sales_client, inspector_client, shipped_order, env):
    return_doc = _create_return(
        sales_client, env, shipped_order, quantity="2", location=env["location"]
    )
    sales_client.post(f"{RETURNS_URL}{return_doc['id']}/post/", {}, format="json")
    payload = {"result": "qualified", "remark": "合格"}
    first = inspector_client.post(f"{RETURNS_URL}{return_doc['id']}/inspect/", payload, format="json")
    assert first.status_code == 200, first.content
    second = inspector_client.post(
        f"{RETURNS_URL}{return_doc['id']}/inspect/", payload, format="json"
    )
    assert second.status_code == 409, second.content
    assert second.json()["code"] == "ALREADY_INSPECTED"
    assert _balance(env, quality=QualityStatus.QUALIFIED).on_hand == Decimal("92.000000")


def test_sales_clerk_cannot_inspect_returns(sales_client, shipped_order, env):
    """职责分离：销售岗位可以登记退货但不能做质量判定（判定需要质检权限）。"""
    return_doc = _create_return(
        sales_client, env, shipped_order, quantity="2", location=env["location"]
    )
    sales_client.post(f"{RETURNS_URL}{return_doc['id']}/post/", {}, format="json")
    response = sales_client.post(
        f"{RETURNS_URL}{return_doc['id']}/inspect/",
        {"result": "qualified", "remark": "自己做判定"},
        format="json",
    )
    assert response.status_code == 403, response.content


# ---------------------------------------------------------------------------
# 订单到交付链路（任务书 12.1）与数据范围
# ---------------------------------------------------------------------------


def test_chain_endpoint_lists_related_documents(sales_client, shipped_order, env):
    response = sales_client.get(f"{ORDERS_URL}{shipped_order.pk}/chain/")
    assert response.status_code == 200, response.content
    body = response.json()
    assert body["order"]["order_no"] == shipped_order.order_no
    assert len(body["shipments"]) == 1
    assert body["shipments"][0]["status"] == ShipmentStatus.POSTED
    assert body["shipments"][0]["issue_document_id"]
    assert body["lines"][0]["shipped_quantity"] == "10.000000"
    assert body["lines"][0]["remaining_quantity"] == "0.000000"
    assert len(body["inventory_documents"]) >= 1
    assert body["inventory_documents"][0]["document_type"] == DocumentType.ISSUE


def test_orders_are_company_scoped(sales_client, env, other_company):
    """跨公司不可见：其他公司的销售订单不出现在列表里。"""
    SalesOrder.objects.create(
        company=other_company,
        order_no="SO-OTHER-1",
        customer=env["customer"],
        status=SalesOrderStatus.APPROVED,
    )
    response = sales_client.get(ORDERS_URL)
    assert response.status_code == 200, response.content
    order_nos = {row["order_no"] for row in response.json()["results"]}
    assert "SO-OTHER-1" not in order_nos


def test_meta_exposes_sales_enums(api_client, registry_permissions, company):
    """前端不硬编码销售枚举：`/api/v1/meta/` 必须下发全部销售枚举键。"""
    user = make_user(username="sal_meta", company=company, is_superuser=True)
    api_client.force_authenticate(user=user)
    response = api_client.get("/api/v1/meta/")
    assert response.status_code == 200, response.content
    body = response.json()
    for key in (
        "sales_order_statuses",
        "sales_order_priorities",
        "shipment_statuses",
        "return_statuses",
        "return_dispositions",
        "reservation_statuses",
    ):
        assert body.get(key), f"meta 缺少枚举 {key}"
    assert {item["value"] for item in body["sales_order_statuses"]} >= {
        "draft",
        "submitted",
        "approved",
        "partially_shipped",
        "shipped",
        "closed",
        "rejected",
        "cancelled",
    }
    assert {item["value"] for item in body["return_dispositions"]} == {
        "none",
        "qualified",
        "rejected",
    }
