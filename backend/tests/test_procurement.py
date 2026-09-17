"""采购模块用例（任务书 10.5、12.1、14.2 第 5/9/10 条）。

覆盖：

* 申请 →（审批）→ 订单 → 到货收货 → 待检库存 → 来料检验放行/不合格的完整链路；
* **金额一律由后端计算**，前端传入的金额被忽略；
* 供应商未准入/停用不能下单；有 `override_supplier` 权限并填写例外原因时可以例外并留痕；
* **不允许超收**，且草稿收货单也占用订单未收数量；
* 过账后库存为 `quarantine`，此时**出库必须被拒绝**；只有放行后才可领用；
* 收货过账与检验判定的幂等（`Idempotency-Key`）与状态机约束；
* 操作权限、数据范围与跨公司隔离。

库存变动全部经由统一库存服务，测试直接读取 `InventoryBalance` 校验事实，
不写死期望值以外的假设。
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from apps.core.exceptions import InsufficientStock, ValidationFailed
from apps.core.models import AuditLog, CodeRule, ResetPeriod
from apps.identity.models import DataScopeType
from apps.masterdata.models import Material, MaterialCategory, UoM
from apps.procurement.models import (
    GoodsReceipt,
    OrderStatus,
    PurchaseOrder,
    PurchaseRequisition,
    ReceiptStatus,
    RequisitionStatus,
)
from apps.srm.models import Supplier
from apps.wms.models import (
    DocumentType,
    InventoryBalance,
    InventoryDocument,
    Location,
    QualityStatus,
    Warehouse,
    Zone,
)
from apps.wms.services import stock
from tests.conftest import make_role, make_user

pytestmark = pytest.mark.django_db

REQUISITIONS_URL = "/api/v1/procurement/requisitions/"
ORDERS_URL = "/api/v1/procurement/orders/"
RECEIPTS_URL = "/api/v1/procurement/receipts/"
INSTANCES_URL = "/api/v1/workflow/instances/"
LOGIN_URL = "/api/v1/identity/auth/login/"
PASSWORD = "Tst!Passw0rd2026"

PROCUREMENT_PERMISSIONS = [
    "procurement.requisition.view",
    "procurement.requisition.create",
    "procurement.requisition.update",
    "procurement.requisition.submit",
    "procurement.order.view",
    "procurement.order.create",
    "procurement.order.update",
    "procurement.order.submit",
    "procurement.order.close",
    "procurement.receipt.view",
    "procurement.receipt.create",
    "procurement.receipt.update",
    "procurement.receipt.post",
    "procurement.receipt.inspect",
    "srm.supplier.view",
    "masterdata.material.view",
    "wms.inventory.view",
    "wms.document.create",
    "wms.document.post",
    "wms.document.view",
]


def login(client, user) -> None:
    response = client.post(LOGIN_URL, {"username": user.username, "password": PASSWORD}, format="json")
    assert response.status_code == 200, response.content


@pytest.fixture
def procurement_code_rules(db):
    """取号依赖编码规则；测试库不跑 bootstrap_system，这里显式建规则。"""
    for code, name, pattern in (
        ("PR", "采购申请单号", "PR{YYYYMMDD}{SEQ:4}"),
        ("PO", "采购订单号", "PO{YYYYMMDD}{SEQ:4}"),
        ("RC", "采购收货单号", "RC{YYYYMMDD}{SEQ:4}"),
        ("GR", "采购入库单号", "GR{YYYYMMDD}{SEQ:4}"),
        # 质量放行会生成质量转换类库存单据（ST），取号同样依赖编码规则
        ("ST", "质量转换单号", "ST{YYYYMMDD}{SEQ:4}"),
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
def env(company, other_company, department_factory, procurement_code_rules):
    """最小采购环境：物料 + 仓库/储位 + 已准入供应商 + 超级管理员（服务层调用）。"""
    category = MaterialCategory.objects.create(code="PRC-CAT", name="采购物料分类", category_type="fabric")
    uom = UoM.objects.create(code="PRC-M", name="米", category="length")
    material = Material.objects.create(
        company=company,
        code="PRC-M1",
        name="采购面料",
        category=category,
        base_uom=uom,
        purchase_price=Decimal("12.500000"),
    )
    warehouse = Warehouse.objects.create(
        company=company,
        code="PRC-WH",
        name="原料仓",
        warehouse_type="raw",
        factory=department_factory["factories"]["F01"],
    )
    zone = Zone.objects.create(warehouse=warehouse, code="Z1", name="存储区")
    location = Location.objects.create(zone=zone, code="L1", name="储位1")
    supplier = Supplier.objects.create(
        company=company, code="PRC-S1", name="主供应商", admission_status="admitted"
    )
    return {
        "company": company,
        "other_company": other_company,
        "material": material,
        "uom": uom,
        "warehouse": warehouse,
        "location": location,
        "supplier": supplier,
        "svc_user": make_user(username="prc_svc", company=company, is_superuser=True),
    }


def _make_api_user(registry_permissions, company, username: str, perms: list[str]):
    role = make_role(
        code=f"test_prc_{username}",
        permission_codes=perms,
        data_scope_type=DataScopeType.COMPANY,
        company=company,
    )
    return role, make_user(username=username, role=role, company=company)


@pytest.fixture
def buyer_user(registry_permissions, company):
    return _make_api_user(registry_permissions, company, "prc_buyer", PROCUREMENT_PERMISSIONS)[1]


@pytest.fixture
def api_user_client(registry_permissions, company):
    """为一个测试身份创建**独立**的 APIClient。

    多个身份共用同一个 `api_client` 会让后一次登录覆盖前一次会话，导致用例
    以错误身份发请求（例如用采购员身份调用质检接口）。因此每个身份一个客户端。
    """
    from rest_framework.test import APIClient

    def _make(username: str, perms: list[str]):
        user = _make_api_user(registry_permissions, company, username, perms)[1]
        client = APIClient()
        login(client, user)
        return client

    return _make


@pytest.fixture
def buyer_client(api_user_client):
    return api_user_client("prc_buyer", PROCUREMENT_PERMISSIONS)


@pytest.fixture
def approver_role(registry_permissions, company):
    return _make_api_user(
        registry_permissions,
        company,
        "prc_approver",
        ["workflow.instance.view", "workflow.instance.approve", "procurement.order.view"],
    )[0]


@pytest.fixture
def approver_client(registry_permissions, company, approver_role):
    from rest_framework.test import APIClient

    client = APIClient()
    login(client, make_user(username="prc_approver_u", role=approver_role, company=company))
    return client


@pytest.fixture
def order_template(db, approver_role):
    from apps.workflow.models import ApprovalTemplate, ApprovalTemplateNode

    template = ApprovalTemplate.objects.create(
        code="TPL-PO-T", name="采购订单审批", biz_type="procurement.order", is_active=True
    )
    ApprovalTemplateNode.objects.create(
        template=template,
        seq=1,
        name="采购主管审批",
        approver_type="role",
        approver_role=approver_role,
    )
    return template


def _order_payload(env, *, quantity="10", price="12.5", **extra) -> dict:
    payload = {
        "supplier_id": env["supplier"].pk,
        "lines": [
            {"material_id": env["material"].pk, "quantity": quantity, "price": price},
        ],
    }
    payload.update(extra)
    return payload


def _create_order(client, env, **extra) -> PurchaseOrder:
    response = client.post(ORDERS_URL, _order_payload(env, **extra), format="json")
    assert response.status_code == 201, response.content
    return PurchaseOrder.objects.get(pk=response.json()["id"])


def _approve(client, order: PurchaseOrder, approver_client) -> dict:
    submitted = client.post(f"{ORDERS_URL}{order.pk}/submit/", {}, format="json")
    assert submitted.status_code == 200, submitted.content
    instance_id = submitted.json()["approval_instance_id"]
    approved = approver_client.post(
        f"{INSTANCES_URL}{instance_id}/approve/", {"comment": "同意"}, format="json"
    )
    assert approved.status_code == 200, approved.content
    return approved.json()


@pytest.fixture
def receipt_client(api_user_client):
    """同时具备采购与库存放行权限的收货/质检员。"""
    perms = [
        "procurement.receipt.view",
        "procurement.receipt.create",
        "procurement.receipt.update",
        "procurement.receipt.post",
        "procurement.receipt.inspect",
        "procurement.order.view",
        "wms.inventory.view",
        # 过账 / 放行经由统一库存服务，需要库存侧权限（与 bootstrap 内置角色一致）
        "wms.document.create",
        "wms.document.post",
        "wms.quality.release",
    ]
    return api_user_client("prc_receiver", perms)


def _balance(env, **filters) -> InventoryBalance:
    return InventoryBalance.objects.get(material=env["material"], warehouse=env["warehouse"], **filters)


def _issue(env, quantity, *, user, quality=QualityStatus.QUALIFIED, batch_no=""):
    document = stock.create_document(
        document_type=DocumentType.ISSUE,
        company=env["company"].pk,
        warehouse=env["warehouse"],
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
        user=user,
    )
    return stock.post_document(document, user=user)


# ---------------------------------------------------------------------------
# 认证与权限
# ---------------------------------------------------------------------------


def test_procurement_endpoints_require_authentication(api_client):
    assert api_client.get(REQUISITIONS_URL).status_code in (401, 403)
    assert api_client.get(ORDERS_URL).status_code in (401, 403)
    assert api_client.get(RECEIPTS_URL).status_code in (401, 403)


def test_view_only_user_cannot_create_order(api_client, registry_permissions, company, env):
    user = _make_api_user(registry_permissions, company, "prc_viewer", ["procurement.order.view"])[1]
    login(api_client, user)
    assert api_client.get(ORDERS_URL).status_code == 200
    response = api_client.post(ORDERS_URL, _order_payload(env), format="json")
    assert response.status_code == 403, response.content


# ---------------------------------------------------------------------------
# 采购申请与金额计算
# ---------------------------------------------------------------------------


def test_requisition_create_persists_lines_and_generates_no(buyer_client, env):
    response = buyer_client.post(
        REQUISITIONS_URL,
        {
            "request_type": "normal",
            "purpose": "秋季新款面料备料",
            "lines": [
                {"material_id": env["material"].pk, "quantity": "120.5"},
                {"material_id": env["material"].pk, "quantity": "30"},
            ],
        },
        format="json",
    )
    assert response.status_code == 201, response.content
    body = response.json()
    assert body["requisition_no"].startswith("PR")
    assert body["status"] == RequisitionStatus.DRAFT
    assert [line["quantity"] for line in body["lines"]] == ["120.500000", "30.000000"]
    # 未转单时 ordered_quantity 恒为 0，且行号由服务层编排
    assert [line["line_no"] for line in body["lines"]] == [1, 2]
    assert all(line["ordered_quantity"] == "0.000000" for line in body["lines"])
    assert AuditLog.objects.filter(object_type__endswith="PurchaseRequisition").exists()


def test_order_amount_is_computed_by_backend(buyer_client, env):
    """前端提交的金额被忽略，金额与税额由后端 ROUND_HALF_UP 计算。"""
    response = buyer_client.post(
        ORDERS_URL,
        {
            **_order_payload(env, quantity="3", price="10.0001"),
            "tax_rate": "13",
            # 恶意/错误的客户端金额必须被忽略
            "total_amount": "999999",
            "amount_with_tax": "999999",
            "lines": [
                {
                    "material_id": env["material"].pk,
                    "quantity": "3",
                    "price": "10.0001",
                    "amount": "888888",
                }
            ],
        },
        format="json",
    )
    assert response.status_code == 201, response.content
    body = response.json()
    assert body["total_amount"] == "30.0003"
    assert body["tax_amount"] == "3.9000"
    assert body["amount_with_tax"] == "33.9003"
    assert body["lines"][0]["amount"] == "30.0003"


def test_order_tax_rounding_is_half_up(buyer_client, env):
    """税额 0.12345 按 ROUND_HALF_UP 进位到 0.1235（银行家舍入会得到 0.1234）。"""
    response = buyer_client.post(
        ORDERS_URL,
        {**_order_payload(env, quantity="1", price="1"), "tax_rate": "12.345"},
        format="json",
    )
    assert response.status_code == 201, response.content
    assert response.json()["tax_amount"] == "0.1235"
    assert response.json()["amount_with_tax"] == "1.1235"


def test_order_rejects_non_positive_quantity(buyer_client, env):
    response = buyer_client.post(ORDERS_URL, _order_payload(env, quantity="0"), format="json")
    assert response.status_code == 400, response.content


# ---------------------------------------------------------------------------
# 供应商准入例外
# ---------------------------------------------------------------------------


def test_suspended_supplier_cannot_be_used_without_reason(buyer_client, env):
    env["supplier"].admission_status = "suspended"
    env["supplier"].save(update_fields=["admission_status"])
    response = buyer_client.post(ORDERS_URL, _order_payload(env), format="json")
    assert response.status_code == 400, response.content
    assert response.json()["code"] == "SUPPLIER_NOT_USABLE"


def test_inactive_supplier_needs_override_permission(buyer_client, env):
    """有原因但无 override 权限：仍然拒绝（例外是权限而不是口头说明）。"""
    env["supplier"].is_active = False
    env["supplier"].save(update_fields=["is_active"])
    response = buyer_client.post(
        ORDERS_URL, _order_payload(env, supplier_exception_reason="总经理特批"), format="json"
    )
    assert response.status_code == 403, response.content
    assert response.json()["code"] == "PERMISSION_DENIED"


def test_override_supplier_requires_reason_and_is_audited(api_client, registry_permissions, company, env):
    env["supplier"].admission_status = "suspended"
    env["supplier"].save(update_fields=["admission_status"])
    user = _make_api_user(
        registry_permissions,
        company,
        "prc_override",
        [*PROCUREMENT_PERMISSIONS, "procurement.order.override_supplier"],
    )[1]
    login(api_client, user)

    without_reason = api_client.post(ORDERS_URL, _order_payload(env), format="json")
    assert without_reason.status_code == 400, without_reason.content

    response = api_client.post(
        ORDERS_URL,
        _order_payload(env, supplier_exception_reason="生产急件，总经理口头批准，后补审批"),
        format="json",
    )
    assert response.status_code == 201, response.content
    assert response.json()["supplier_exception"] is True
    log = AuditLog.objects.filter(object_type__endswith="PurchaseOrder", action="create").latest("id")
    assert log.reason.strip() != ""
    assert log.changes["supplier_exception"]["after"] is True


# ---------------------------------------------------------------------------
# 审批回写（workflow.registry）
# ---------------------------------------------------------------------------


def test_order_submit_then_approve_writes_back_status(buyer_client, approver_client, env, order_template):
    order = _create_order(buyer_client, env)
    body = _approve(buyer_client, order, approver_client)
    assert body["status"] == "approved"
    order.refresh_from_db()
    assert order.status == OrderStatus.APPROVED
    assert order.approval_instance_id is not None
    assert order.approved_at is not None


def test_order_approval_rejection_writes_back_rejected(buyer_client, approver_client, env, order_template):
    order = _create_order(buyer_client, env)
    submitted = buyer_client.post(f"{ORDERS_URL}{order.pk}/submit/", {}, format="json")
    instance_id = submitted.json()["approval_instance_id"]
    rejected = approver_client.post(
        f"{INSTANCES_URL}{instance_id}/reject/", {"comment": "价格超标"}, format="json"
    )
    assert rejected.status_code == 200, rejected.content
    order.refresh_from_db()
    assert order.status == OrderStatus.REJECTED


def test_requisition_approval_writes_back_status(buyer_client, approver_client, env, approver_role):
    from apps.workflow.models import ApprovalTemplate, ApprovalTemplateNode

    template = ApprovalTemplate.objects.create(
        code="TPL-PR-T", name="采购申请审批", biz_type="procurement.requisition", is_active=True
    )
    ApprovalTemplateNode.objects.create(
        template=template,
        seq=1,
        name="采购主管审批",
        approver_type="role",
        approver_role=approver_role,
    )
    created = buyer_client.post(
        REQUISITIONS_URL,
        {"purpose": "备料", "lines": [{"material_id": env["material"].pk, "quantity": "5"}]},
        format="json",
    )
    requisition_id = created.json()["id"]
    submitted = buyer_client.post(f"{REQUISITIONS_URL}{requisition_id}/submit/", {}, format="json")
    assert submitted.status_code == 200, submitted.content
    instance_id = submitted.json()["approval_instance_id"]
    approved = approver_client.post(
        f"{INSTANCES_URL}{instance_id}/approve/", {"comment": "同意"}, format="json"
    )
    assert approved.status_code == 200, approved.content
    requisition = PurchaseRequisition.objects.get(pk=requisition_id)
    assert requisition.status == RequisitionStatus.APPROVED


# ---------------------------------------------------------------------------
# 收货：数量约束、待检库存、质量放行
# ---------------------------------------------------------------------------


@pytest.fixture
def approved_order(buyer_client, approver_client, env, order_template):
    """一张已批准、数量 10 的采购订单（走真实提交+审批路径）。"""
    order = _create_order(buyer_client, env, quantity="10", price="12.5")
    _approve(buyer_client, order, approver_client)
    order.refresh_from_db()
    assert order.status == OrderStatus.APPROVED
    return order


def _receipt_payload(env, order, *, quantity="4", order_line=None, **extra) -> dict:
    line = order_line or order.lines.order_by("line_no").first()
    payload = {
        "purchase_order_id": order.pk,
        "warehouse_id": env["warehouse"].pk,
        "lines": [
            {
                "order_line_id": line.pk,
                "quantity": quantity,
                "location_id": env["location"].pk,
                "batch_no": "B20260917",
            }
        ],
    }
    payload.update(extra)
    return payload


def _create_receipt(client, env, order, **extra) -> GoodsReceipt:
    response = client.post(RECEIPTS_URL, _receipt_payload(env, order, **extra), format="json")
    assert response.status_code == 201, response.content
    return GoodsReceipt.objects.get(pk=response.json()["id"])


def test_receipt_over_order_quantity_is_rejected(receipt_client, approved_order, env):
    response = receipt_client.post(
        RECEIPTS_URL, _receipt_payload(env, approved_order, quantity="10.000001"), format="json"
    )
    assert response.status_code == 400, response.content
    assert response.json()["code"] == "OVER_RECEIPT"


def test_draft_receipts_reserve_remaining_quantity(receipt_client, approved_order, env):
    """两张草稿收货单合计不得超过未收数量：草稿也占用额度。"""
    _create_receipt(receipt_client, env, approved_order, quantity="6")
    second = receipt_client.post(
        RECEIPTS_URL, _receipt_payload(env, approved_order, quantity="5"), format="json"
    )
    assert second.status_code == 400, second.content
    assert second.json()["code"] == "OVER_RECEIPT"


def test_receipt_line_must_belong_to_the_order(
    receipt_client, approved_order, env, buyer_client, order_template
):
    other_order = _create_order(buyer_client, env, quantity="3", price="1")
    _create_receipt(receipt_client, env, approved_order, quantity="1")
    foreign_line = other_order.lines.order_by("line_no").first()
    response = receipt_client.post(
        RECEIPTS_URL,
        {
            "purchase_order_id": approved_order.pk,
            "warehouse_id": env["warehouse"].pk,
            "lines": [{"order_line_id": foreign_line.pk, "quantity": "1"}],
        },
        format="json",
    )
    assert response.status_code == 400, response.content
    assert response.json()["code"] == "ORDER_LINE_MISMATCH"


def test_post_receipt_creates_quarantine_stock_and_blocks_issue(receipt_client, approved_order, env):
    receipt = _create_receipt(receipt_client, env, approved_order, quantity="4")
    posted = receipt_client.post(f"{RECEIPTS_URL}{receipt.pk}/post/", {}, format="json")
    assert posted.status_code == 200, posted.content
    assert posted.json()["status"] == ReceiptStatus.POSTED
    assert posted.json()["receipt_document_id"] is not None

    balance = _balance(env, quality_status=QualityStatus.QUARANTINE, batch_no="B20260917")
    assert balance.on_hand == Decimal("4.000000")
    approved_order.refresh_from_db()
    assert approved_order.lines.first().received_quantity == Decimal("4.000000")
    assert approved_order.status == OrderStatus.PARTIALLY_RECEIVED

    with pytest.raises((InsufficientStock, ValidationFailed)):
        _issue(env, "1", user=env["svc_user"], batch_no="B20260917")


def test_inspect_qualified_releases_stock_for_issue(receipt_client, approved_order, env):
    receipt = _create_receipt(receipt_client, env, approved_order, quantity="4")
    receipt_client.post(f"{RECEIPTS_URL}{receipt.pk}/post/", {}, format="json")
    inspected = receipt_client.post(
        f"{RECEIPTS_URL}{receipt.pk}/inspect/",
        {"result": "qualified", "remark": "外观、幅宽、克重符合标准"},
        format="json",
    )
    assert inspected.status_code == 200, inspected.content
    assert inspected.json()["inspection_result"] == "qualified"
    assert inspected.json()["quality_document_id"] is not None

    assert not InventoryBalance.objects.filter(
        material=env["material"], quality_status=QualityStatus.QUARANTINE, on_hand__gt=0
    ).exists()
    released = _balance(env, quality_status=QualityStatus.QUALIFIED, batch_no="B20260917")
    assert released.on_hand == Decimal("4.000000")

    # 放行后可以领用
    _issue(env, "1.5", user=env["svc_user"], batch_no="B20260917")
    released.refresh_from_db()
    assert released.on_hand == Decimal("2.500000")


def test_inspect_rejected_keeps_stock_blocked(receipt_client, approved_order, env):
    receipt = _create_receipt(receipt_client, env, approved_order, quantity="2")
    receipt_client.post(f"{RECEIPTS_URL}{receipt.pk}/post/", {}, format="json")
    inspected = receipt_client.post(
        f"{RECEIPTS_URL}{receipt.pk}/inspect/",
        {"result": "rejected", "remark": "色差超标准，判不合格"},
        format="json",
    )
    assert inspected.status_code == 200, inspected.content
    assert inspected.json()["inspection_result"] == "rejected"
    rejected = _balance(env, quality_status=QualityStatus.REJECTED, batch_no="B20260917")
    assert rejected.on_hand == Decimal("2.000000")
    with pytest.raises((InsufficientStock, ValidationFailed)):
        _issue(env, "1", user=env["svc_user"], batch_no="B20260917")


def test_inspect_requires_posted_state(receipt_client, approved_order, env):
    receipt = _create_receipt(receipt_client, env, approved_order, quantity="1")
    response = receipt_client.post(
        f"{RECEIPTS_URL}{receipt.pk}/inspect/",
        {"result": "qualified", "remark": "未过账直接判定"},
        format="json",
    )
    assert response.status_code == 409, response.content
    assert response.json()["code"] == "STATE_CONFLICT"


def test_inspect_requires_remark(receipt_client, approved_order, env):
    receipt = _create_receipt(receipt_client, env, approved_order, quantity="1")
    receipt_client.post(f"{RECEIPTS_URL}{receipt.pk}/post/", {}, format="json")
    response = receipt_client.post(
        f"{RECEIPTS_URL}{receipt.pk}/inspect/", {"result": "qualified", "remark": ""}, format="json"
    )
    assert response.status_code == 400, response.content


def test_repeated_inspect_is_rejected(receipt_client, approved_order, env):
    receipt = _create_receipt(receipt_client, env, approved_order, quantity="1")
    receipt_client.post(f"{RECEIPTS_URL}{receipt.pk}/post/", {}, format="json")
    payload = {"result": "qualified", "remark": "首次判定合格"}
    first = receipt_client.post(f"{RECEIPTS_URL}{receipt.pk}/inspect/", payload, format="json")
    assert first.status_code == 200, first.content
    second = receipt_client.post(
        f"{RECEIPTS_URL}{receipt.pk}/inspect/",
        {"result": "rejected", "remark": "试图重复判定"},
        format="json",
    )
    assert second.status_code == 409, second.content
    assert second.json()["code"] == "ALREADY_INSPECTED"


def test_posted_receipt_cannot_be_cancelled(receipt_client, approved_order, env):
    receipt = _create_receipt(receipt_client, env, approved_order, quantity="1")
    receipt_client.post(f"{RECEIPTS_URL}{receipt.pk}/post/", {}, format="json")
    response = receipt_client.post(f"{RECEIPTS_URL}{receipt.pk}/cancel/", {"reason": "作废"}, format="json")
    assert response.status_code == 409, response.content


def test_receipt_cancel_requires_reason(receipt_client, approved_order, env):
    receipt = _create_receipt(receipt_client, env, approved_order, quantity="1")
    response = receipt_client.post(f"{RECEIPTS_URL}{receipt.pk}/cancel/", {}, format="json")
    assert response.status_code == 400, response.content


def test_receipt_post_is_idempotent_with_header(receipt_client, approved_order, env):
    receipt = _create_receipt(receipt_client, env, approved_order, quantity="3")
    headers = {"HTTP_IDEMPOTENCY_KEY": "prc-key-0001"}
    first = receipt_client.post(f"{RECEIPTS_URL}{receipt.pk}/post/", {}, format="json", **headers)
    assert first.status_code == 200, first.content
    second = receipt_client.post(f"{RECEIPTS_URL}{receipt.pk}/post/", {}, format="json", **headers)
    assert second.status_code == 200, second.content
    assert second.headers.get("Idempotency-Replayed") == "true"

    balance = _balance(env, quality_status=QualityStatus.QUARANTINE, batch_no="B20260917")
    assert balance.on_hand == Decimal("3.000000")
    assert approved_order.lines.first().received_quantity == Decimal("3.000000")


def test_order_cannot_be_cancelled_once_receipt_exists(buyer_client, approved_order, env):
    receipt = _create_receipt(buyer_client, env, approved_order, quantity="1")
    response = buyer_client.post(
        f"{ORDERS_URL}{approved_order.pk}/cancel/", {"reason": "不再需要"}, format="json"
    )
    assert response.status_code == 409, response.content
    assert receipt.status == ReceiptStatus.DRAFT


def test_order_can_be_closed_after_receipt(buyer_client, approved_order):
    response = buyer_client.post(
        f"{ORDERS_URL}{approved_order.pk}/close/", {"reason": "余量不再到货"}, format="json"
    )
    assert response.status_code == 200, response.content
    assert response.json()["status"] == OrderStatus.CLOSED


# ---------------------------------------------------------------------------
# 按申请转订单
# ---------------------------------------------------------------------------


@pytest.fixture
def approved_requisition(buyer_client, approver_client, env, approver_role):
    from apps.workflow.models import ApprovalTemplate, ApprovalTemplateNode

    template = ApprovalTemplate.objects.create(
        code="TPL-PR-CONV", name="采购申请审批", biz_type="procurement.requisition", is_active=True
    )
    ApprovalTemplateNode.objects.create(
        template=template,
        seq=1,
        name="采购主管审批",
        approver_type="role",
        approver_role=approver_role,
    )
    created = buyer_client.post(
        REQUISITIONS_URL,
        {
            "purpose": "备料",
            "lines": [
                {"material_id": env["material"].pk, "quantity": "10"},
                {"material_id": env["material"].pk, "quantity": "5"},
            ],
        },
        format="json",
    )
    assert created.status_code == 201, created.content
    requisition_id = created.json()["id"]
    submitted = buyer_client.post(f"{REQUISITIONS_URL}{requisition_id}/submit/", {}, format="json")
    instance_id = submitted.json()["approval_instance_id"]
    approved = approver_client.post(
        f"{INSTANCES_URL}{instance_id}/approve/", {"comment": "同意"}, format="json"
    )
    assert approved.status_code == 200, approved.content
    requisition = PurchaseRequisition.objects.get(pk=requisition_id)
    assert requisition.status == RequisitionStatus.APPROVED
    return requisition


def test_convert_requisition_to_order_and_block_duplicates(buyer_client, env, approved_requisition):
    response = buyer_client.post(
        f"{REQUISITIONS_URL}{approved_requisition.pk}/convert/",
        {"supplier_id": env["supplier"].pk, "tax_rate": "13"},
        format="json",
    )
    assert response.status_code == 201, response.content
    body = response.json()
    assert body["order_no"].startswith("PO")
    assert body["source_requisition_id"] == approved_requisition.pk
    assert [line["quantity"] for line in body["lines"]] == ["10.000000", "5.000000"]

    approved_requisition.refresh_from_db()
    ordered = {line.pk: line.ordered_quantity for line in approved_requisition.lines.order_by("line_no")}
    assert list(ordered.values()) == [Decimal("10.000000"), Decimal("5.000000")]

    # 重复转单：未转数量为 0，没有可转明细
    again = buyer_client.post(
        f"{REQUISITIONS_URL}{approved_requisition.pk}/convert/",
        {"supplier_id": env["supplier"].pk},
        format="json",
    )
    assert again.status_code == 400, again.content
    assert again.json()["code"] == "NOTHING_TO_CONVERT"

    # 超转：显式指定数量超过未转数量
    line = approved_requisition.lines.order_by("line_no").first()
    over = buyer_client.post(
        f"{REQUISITIONS_URL}{approved_requisition.pk}/convert/",
        {
            "supplier_id": env["supplier"].pk,
            "lines": [{"requisition_line": line.pk, "quantity": "1", "price": "2"}],
        },
        format="json",
    )
    assert over.status_code == 400, over.content
    assert over.json()["code"] == "OVER_CONVERT"


def test_draft_requisition_cannot_be_converted(buyer_client, env):
    created = buyer_client.post(
        REQUISITIONS_URL,
        {"lines": [{"material_id": env["material"].pk, "quantity": "1"}]},
        format="json",
    )
    requisition_id = created.json()["id"]
    response = buyer_client.post(
        f"{REQUISITIONS_URL}{requisition_id}/convert/",
        {"supplier_id": env["supplier"].pk},
        format="json",
    )
    assert response.status_code == 409, response.content
    assert response.json()["code"] == "REQUISITION_NOT_APPROVED"


# ---------------------------------------------------------------------------
# 数据范围与跨公司隔离
# ---------------------------------------------------------------------------


def test_orders_are_company_scoped(buyer_client, env, other_company):
    from apps.procurement.models import PurchaseOrderLine

    foreign = PurchaseOrder.objects.create(
        company=other_company,
        order_no="PO-FOREIGN",
        supplier=env["supplier"],
        status=OrderStatus.APPROVED,
    )
    PurchaseOrderLine.objects.create(
        order=foreign,
        line_no=1,
        material=env["material"],
        quantity=Decimal("1"),
        price=Decimal("1"),
        amount=Decimal("1"),
    )
    mine = _create_order(buyer_client, env)

    listed = buyer_client.get(ORDERS_URL)
    assert listed.status_code == 200, listed.content
    numbers = {row["order_no"] for row in listed.json()["results"]}
    assert mine.order_no in numbers
    assert "PO-FOREIGN" not in numbers

    assert buyer_client.get(f"{ORDERS_URL}{foreign.pk}/").status_code == 404
    assert buyer_client.get(f"{ORDERS_URL}{mine.pk}/").status_code == 200


def test_receipt_permission_is_enforced(api_client, registry_permissions, company, env, approved_order):
    """有 view/create 但没有 post 权限时，过账必须被拒绝。"""
    user = _make_api_user(
        registry_permissions,
        company,
        "prc_receiver_nopost",
        ["procurement.receipt.view", "procurement.receipt.create", "procurement.order.view"],
    )[1]
    login(api_client, user)
    created = api_client.post(
        RECEIPTS_URL, _receipt_payload(env, approved_order, quantity="1"), format="json"
    )
    assert created.status_code == 201, created.content
    receipt_id = created.json()["id"]
    response = api_client.post(f"{RECEIPTS_URL}{receipt_id}/post/", {}, format="json")
    assert response.status_code == 403, response.content


def test_receipts_of_other_company_orders_are_not_visible(buyer_client, env, other_company):
    from apps.procurement.models import PurchaseOrderLine

    foreign = PurchaseOrder.objects.create(
        company=other_company,
        order_no="PO-FOREIGN-2",
        supplier=env["supplier"],
        status=OrderStatus.APPROVED,
        warehouse=env["warehouse"],
    )
    PurchaseOrderLine.objects.create(
        order=foreign,
        line_no=1,
        material=env["material"],
        quantity=Decimal("1"),
        price=Decimal("1"),
        amount=Decimal("1"),
    )
    response = buyer_client.post(
        RECEIPTS_URL,
        {
            "purchase_order_id": foreign.pk,
            "warehouse_id": env["warehouse"].pk,
            "lines": [{"order_line_id": foreign.lines.first().pk, "quantity": "1"}],
        },
        format="json",
    )
    assert response.status_code == 404, response.content


def test_unapproved_order_cannot_be_received(buyer_client, env):
    order = _create_order(buyer_client, env, quantity="5")
    assert order.status == OrderStatus.DRAFT
    response = buyer_client.post(RECEIPTS_URL, _receipt_payload(env, order, quantity="1"), format="json")
    assert response.status_code == 409, response.content
    assert response.json()["code"] == "ORDER_NOT_RECEIVABLE"



# ---------------------------------------------------------------------------
# 多行收货：逐行放行，幂等键按行隔离
# ---------------------------------------------------------------------------


@pytest.fixture
def second_material(env):
    """第二行物料（与首行同一分类、同一单位）。"""
    return Material.objects.create(
        company=env["company"],
        code="PRC-M2",
        name="采购里布",
        category=env["material"].category,
        base_uom=env["uom"],
        purchase_price=Decimal("5.000000"),
    )


@pytest.fixture
def two_line_order(buyer_client, approver_client, env, second_material, order_template):
    """一张已批准、两行不同物料的采购订单。"""
    response = buyer_client.post(
        ORDERS_URL,
        {
            "supplier_id": env["supplier"].pk,
            "lines": [
                {"material_id": env["material"].pk, "quantity": "10", "price": "10"},
                {"material_id": second_material.pk, "quantity": "20", "price": "5"},
            ],
        },
        format="json",
    )
    assert response.status_code == 201, response.content
    order = PurchaseOrder.objects.get(pk=response.json()["id"])
    _approve(buyer_client, order, approver_client)
    order.refresh_from_db()
    assert order.status == OrderStatus.APPROVED
    return order


def test_multi_line_receipt_inspect_releases_every_line_once(
    receipt_client, two_line_order, second_material, env
):
    """多行收货单：一次检验判定放行**每一行**，且传入的 Idempotency-Key 不会互相顶掉。"""
    order_lines = list(two_line_order.lines.order_by("line_no"))
    assert len(order_lines) == 2
    response = receipt_client.post(
        RECEIPTS_URL,
        {
            "purchase_order_id": two_line_order.pk,
            "warehouse_id": env["warehouse"].pk,
            "lines": [
                {
                    "order_line_id": order_lines[0].pk,
                    "quantity": "10",
                    "location_id": env["location"].pk,
                    "batch_no": "MB-01",
                },
                {
                    "order_line_id": order_lines[1].pk,
                    "quantity": "20",
                    "location_id": env["location"].pk,
                    "batch_no": "MB-02",
                },
            ],
        },
        format="json",
    )
    assert response.status_code == 201, response.content
    receipt = GoodsReceipt.objects.get(pk=response.json()["id"])

    posted = receipt_client.post(
        f"{RECEIPTS_URL}{receipt.pk}/post/", {}, format="json", HTTP_IDEMPOTENCY_KEY="mb-post-1"
    )
    assert posted.status_code == 200, posted.content
    assert posted.json()["receipt_document_id"] is not None

    inspected = receipt_client.post(
        f"{RECEIPTS_URL}{receipt.pk}/inspect/",
        {"result": "qualified", "remark": "两行来料外观、幅宽检验合格"},
        format="json",
        HTTP_IDEMPOTENCY_KEY="mb-inspect-shared",
    )
    assert inspected.status_code == 200, inspected.content
    assert inspected.json()["quality_document_id"] is not None
    receipt.refresh_from_db()

    released = InventoryBalance.objects.filter(
        warehouse=env["warehouse"], quality_status=QualityStatus.QUALIFIED, batch_no__in=["MB-01", "MB-02"]
    ).order_by("batch_no")
    assert [(row.batch_no, row.on_hand) for row in released] == [
        ("MB-01", Decimal("10.000000")),
        ("MB-02", Decimal("20.000000")),
    ]
    assert not InventoryBalance.objects.filter(
        warehouse=env["warehouse"], quality_status=QualityStatus.QUARANTINE, on_hand__gt=0
    ).exists()

    # quality_document_id 记录的是**最后一次**放行生成的库存单据（第二行）
    last_document = InventoryDocument.objects.get(pk=receipt.quality_document_id)
    assert last_document.lines.get().material_id == second_material.pk
    # 每行各生成一张质量转换单据，共两张
    assert InventoryDocument.objects.filter(
        document_type=DocumentType.QUALITY, biz_type="procurement.receipt", biz_id=str(receipt.pk)
    ).count() == 2


def test_inspect_with_idempotency_key_replays_without_second_release(
    receipt_client, approved_order, env
):
    """同一 Idempotency-Key 重复调用检验判定：返回首次结果，不重复放行。"""
    receipt = _create_receipt(receipt_client, env, approved_order, quantity="3")
    receipt_client.post(f"{RECEIPTS_URL}{receipt.pk}/post/", {}, format="json")
    payload = {"result": "qualified", "remark": "首次判定合格"}

    first = receipt_client.post(
        f"{RECEIPTS_URL}{receipt.pk}/inspect/", payload, format="json", HTTP_IDEMPOTENCY_KEY="insp-1"
    )
    assert first.status_code == 200, first.content
    second = receipt_client.post(
        f"{RECEIPTS_URL}{receipt.pk}/inspect/", payload, format="json", HTTP_IDEMPOTENCY_KEY="insp-1"
    )
    assert second.status_code == 200, second.content
    assert second["Idempotency-Replayed"] == "true"

    released = _balance(env, quality_status=QualityStatus.QUALIFIED, batch_no="B20260917")
    assert released.on_hand == Decimal("3.000000")
    assert (
        InventoryDocument.objects.filter(
            document_type=DocumentType.QUALITY, biz_type="procurement.receipt", biz_id=str(receipt.pk)
        ).count()
        == 1
    )
def test_meta_exposes_procurement_enums(api_client, registry_permissions, company):
    """前端不硬编码采购枚举：`/api/v1/meta/` 必须下发全部采购枚举键。"""
    user = make_user(username="prc_meta", company=company, is_superuser=True)
    api_client.force_authenticate(user=user)
    response = api_client.get("/api/v1/meta/")
    assert response.status_code == 200, response.content
    body = response.json()
    for key in (
        "requisition_types",
        "requisition_statuses",
        "purchase_order_statuses",
        "receipt_statuses",
        "inspection_results",
    ):
        assert body.get(key), f"meta 缺少枚举 {key}"
    assert {item["value"] for item in body["requisition_types"]} == {
        "normal",
        "planned",
        "urgent",
    }
    assert {item["value"] for item in body["purchase_order_statuses"]} >= {
        "draft",
        "submitted",
        "approved",
        "partially_received",
        "received",
        "closed",
    }
    assert {item["value"] for item in body["inspection_results"]} == {
        "none",
        "qualified",
        "rejected",
    }
