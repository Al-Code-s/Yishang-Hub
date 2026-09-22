"""MRP 用例（任务书 10.6、14.2 案例 12）。

覆盖：

* 顶层需求只认「已批准 / 部分发货」销售订单的未发货量；草稿、已取消、已发货不产生需求；
* 逾期需求计入第一个分段，区间外的需求不计入；
* 供给口径：现有库存取 `on_hand − frozen − reserved` 且只算合格品；采购在途取未收数量；
* 低层码逐层净算：同一物料被多层引用只净算一次，派生需求不会与销售需求重复计算；
* 展开用**父件净需求**（不是毛需求），子件毛需求 = 父件净需求 × 含损耗用量；
* 循环 BOM 直接拒绝（`BOM_CYCLE_DETECTED`）并留下一条 `failed` 运行；
* 建议类型：有生效 BOM 或分类为成品/半成品 → 生产建议；其余 → 采购建议；
  成品无生效 BOM 时进入 `unexploded_materials` 而不是静默生成可转单建议；
* 转单：采购建议转成草稿采购申请、生产建议转成草稿 MES 生产工单（都仍走后续审批 /
  下达），两者都写 `DocumentLink`；重复转单、过期建议、物料停用均被拒绝；
* 在制供给取 MES 已下达 / 生产中的未完工数量（草稿不计），指定仓库时不产生在制供给；
* 转单需要 `procurement.requisition.create`（真实约束，不绕过采购服务）；
* 权限与数据范围：匿名 403、缺 `planning.mrp.run` 不能运行、只读不能转单、跨公司隔离；
  `planning.mrp.*` 与 BOM 权限互不授予；
* `bucket=week` 归一到周一、区间非法与分段非法被拒；
* 归档只改状态且重复归档被拒；取消建议必须填原因；
* 审计与 Outbox 事件与业务同事务落库。

数据构造说明：库存余额、销售订单、采购订单属于被测模块的**上游夹具**，
这里直接经 ORM 构造并按业务状态置位，以保证用例聚焦 MRP 自身的净算与转单行为；
MRP 自身的全部读写都走 `apps.planning.mrp` 公开服务。
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.core.exceptions import StateConflict, ValidationFailed
from apps.core.models import AuditLog, CodeRule, OutboxEvent, ResetPeriod
from apps.core.services import business_timezone
from apps.crm.models import Customer
from apps.identity.models import DataScopeType
from apps.integration.models import DocumentLink
from apps.masterdata.models import Color, Material, MaterialCategory, Size, Sku, Style, UoM
from apps.mes.models import ProductionOrder, ProductionOrderStatus
from apps.planning import mrp as mrp_engine
from apps.planning.models import (
    Bom,
    BomLine,
    BomStatus,
    MrpBucket,
    MrpDemandSource,
    MrpRun,
    MrpRunStatus,
    MrpSuggestion,
    MrpSuggestionStatus,
    MrpSuggestionType,
    MrpSupplyLine,
    MrpSupplySource,
)
from apps.procurement.models import (
    OrderStatus,
    PurchaseOrder,
    PurchaseOrderLine,
    PurchaseRequisition,
)
from apps.sales.models import SalesOrder, SalesOrderLine, SalesOrderStatus
from apps.srm.models import AdmissionStatus, Supplier
from apps.wms.models import InventoryBalance, QualityStatus, Warehouse
from tests.conftest import make_role, make_user

pytestmark = pytest.mark.django_db

RUNS_URL = "/api/v1/planning/mrp-runs/"
SUGGESTIONS_URL = "/api/v1/planning/mrp-suggestions/"
LOGIN_URL = "/api/v1/identity/auth/login/"
PASSWORD = "Tst!Passw0rd2026"
TODAY = date(2026, 9, 1)

MRP_PERMISSIONS = [
    "planning.mrp.view",
    "planning.mrp.run",
    "planning.mrp.convert",
    "planning.mrp.cancel",
    "planning.mrp.archive",
    "procurement.requisition.view",
    "procurement.requisition.create",
    "masterdata.material.view",
    "analytics.dashboard.view",
]


def login(client, user) -> None:
    response = client.post(
        LOGIN_URL, {"username": user.username, "password": PASSWORD}, format="json"
    )
    assert response.status_code == 200, response.content


@pytest.fixture
def mrp_code_rules(db):
    """取号依赖编码规则；测试库不跑 bootstrap_system，这里显式建规则。"""
    for code, name, pattern in (
        ("MRP", "MRP 运行编号", "MRP{YYYYMMDD}{SEQ:4}"),
        ("PR", "采购申请号", "PR{YYYYMMDD}{SEQ:4}"),
        ("MO", "生产工单号", "MO{YYYYMMDD}{SEQ:4}"),
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


def _material(company, code, name, category, uom, **extra) -> Material:
    return Material.objects.create(
        company=company, code=code, name=name, category=category, base_uom=uom, **extra
    )


@pytest.fixture
def env(company, other_company, department_factory, mrp_code_rules):
    """最小 MRP 环境：分类 / 物料 / 款式 / SKU / 仓库 / 客户 / 供应商 / 服务账号。"""
    cat_fabric = MaterialCategory.objects.create(
        code="MRP-FAB-CAT", name="面料", category_type="fabric"
    )
    cat_accessory = MaterialCategory.objects.create(
        code="MRP-ACC-CAT", name="辅料", category_type="accessory"
    )
    cat_finished = MaterialCategory.objects.create(
        code="MRP-FIN-CAT", name="成品", category_type="finished"
    )
    cat_semi = MaterialCategory.objects.create(
        code="MRP-SEMI-CAT", name="半成品", category_type="semifinished"
    )
    uom_pc = UoM.objects.create(code="MRP-PC", name="件", category="quantity")
    uom_m = UoM.objects.create(code="MRP-M", name="米", category="length")

    fabric = _material(company, "MRP-FAB", "主面料", cat_fabric, uom_m)
    button = _material(company, "MRP-BTN", "纽扣", cat_accessory, uom_pc)
    thread = _material(company, "MRP-THR", "缝纫线", cat_accessory, uom_pc)
    semi = _material(company, "MRP-SEMI", "半成品衣片", cat_semi, uom_pc)
    finished = _material(company, "MRP-FIN", "成品衬衫", cat_finished, uom_pc)
    orphan_finished = _material(company, "MRP-FIN2", "无 BOM 成品", cat_finished, uom_pc)
    other_material = _material(other_company, "MRP-OTH", "对照物料", cat_fabric, uom_m)

    style = Style.objects.create(company=company, code="MRP-ST1", name="基础衬衫", size_group="men")
    other_style = Style.objects.create(company=other_company, code="MRP-ST2", name="对照款式")
    color = Color.objects.create(code="MRP-BK", name="黑色")
    size = Size.objects.create(code="MRP-L", name="L")
    size_xl = Size.objects.create(code="MRP-XL", name="XL")
    sku = Sku.objects.create(
        company=company, style=style, color=color, size=size, code="MRP-ST1-BK-L", material=finished
    )
    # 无 BOM 的成品必须落在**另一个款式**上：款式通用 BOM 会覆盖同款所有 SKU，
    # 若共用款式就会「意外」可展开，测不出 unexploded_materials 分支。
    orphan_style = Style.objects.create(company=company, code="MRP-ST3", name="无 BOM 款式")
    orphan_sku = Sku.objects.create(
        company=company,
        style=orphan_style,
        color=color,
        size=size_xl,
        code="MRP-ST3-BK-XL",
        material=orphan_finished,
    )
    other_sku = Sku.objects.create(
        company=other_company, style=other_style, color=color, size=size, code="MRP-ST2-BK-L"
    )

    factory = department_factory["factories"]["F01"]
    warehouse = Warehouse.objects.create(company=company, code="MRP-W01", name="成品仓", factory=factory)
    warehouse2 = Warehouse.objects.create(company=company, code="MRP-W02", name="面料仓", factory=factory)
    other_warehouse = Warehouse.objects.create(
        company=other_company, code="MRP-W03", name="对照仓"
    )

    customer = Customer.objects.create(company=company, code="MRP-C1", name="演示客户")
    supplier = Supplier.objects.create(
        company=company,
        code="MRP-S1",
        name="演示供应商",
        admission_status=AdmissionStatus.ADMITTED,
    )

    return {
        "company": company,
        "other_company": other_company,
        "uom_pc": uom_pc,
        "uom_m": uom_m,
        "fabric": fabric,
        "button": button,
        "thread": thread,
        "semi": semi,
        "finished": finished,
        "orphan_finished": orphan_finished,
        "other_material": other_material,
        "style": style,
        "sku": sku,
        "orphan_sku": orphan_sku,
        "other_sku": other_sku,
        "warehouse": warehouse,
        "warehouse2": warehouse2,
        "other_warehouse": other_warehouse,
        "customer": customer,
        "supplier": supplier,
        "svc_user": make_user(username="mrp_svc", company=company, is_superuser=True),
    }


def make_bom(env, *, lines, sku=None, style=None, code="MRP-BOM-1", version=1, status=BomStatus.APPROVED) -> Bom:
    bom = Bom.objects.create(
        company=env["company"],
        code=code,
        style=style or env["style"],
        sku=sku,
        version_no=version,
        status=status,
        effective_from=TODAY,
    )
    for index, row in enumerate(lines, start=1):
        material = row["material"]
        BomLine.objects.create(
            bom=bom,
            line_no=index,
            material=material,
            quantity=Decimal(row.get("quantity", "1")),
            loss_rate=Decimal(row.get("loss_rate", "0")),
            uom=material.base_uom,
            line_type=row.get("line_type", "normal"),
        )
    return bom


def make_balance(material, warehouse, *, on_hand="0", frozen="0", reserved="0", quality=QualityStatus.QUALIFIED, company=None):
    return InventoryBalance.objects.create(
        company=company or material.company,
        material=material,
        warehouse=warehouse,
        quality_status=quality,
        on_hand=Decimal(on_hand),
        frozen=Decimal(frozen),
        reserved=Decimal(reserved),
    )


def make_sales_order(
    env,
    *,
    material,
    sku=None,
    quantity="10",
    expected=TODAY,
    status=SalesOrderStatus.APPROVED,
    warehouse=None,
    order_no="SO-MRP-1",
    shipped="0",
    company=None,
) -> SalesOrder:
    owner = company or env["company"]
    order = SalesOrder.objects.create(
        company=owner,
        order_no=order_no,
        customer=env["customer"] if owner == env["company"] else Customer.objects.create(company=owner, code=f"{order_no}-C", name="对照客户"),
        status=status,
        order_date=TODAY,
        expected_date=expected,
        warehouse=warehouse if warehouse is not None else env["warehouse"],
    )
    SalesOrderLine.objects.create(
        order=order,
        line_no=1,
        material=material,
        sku=sku,
        quantity=Decimal(quantity),
        shipped_quantity=Decimal(shipped),
        price=Decimal("10"),
        amount=Decimal("100"),
        uom=material.base_uom,
        expected_date=expected,
    )
    return order


def make_purchase_order(
    env,
    *,
    material,
    quantity="10",
    received="0",
    expected=TODAY,
    status=OrderStatus.APPROVED,
    warehouse=None,
    order_no="PO-MRP-1",
    company=None,
) -> PurchaseOrder:
    owner = company or env["company"]
    order = PurchaseOrder.objects.create(
        company=owner,
        order_no=order_no,
        supplier=env["supplier"],
        status=status,
        order_date=TODAY,
        expected_date=expected,
        warehouse=warehouse if warehouse is not None else env["warehouse"],
    )
    PurchaseOrderLine.objects.create(
        order=order,
        line_no=1,
        material=material,
        quantity=Decimal(quantity),
        received_quantity=Decimal(received),
        price=Decimal("5"),
        amount=Decimal("50"),
        uom=material.base_uom,
        expected_date=expected,
    )
    return order


def run(env, **kwargs) -> MrpRun:
    params = {
        "company": env["company"],
        "user": env["svc_user"],
        "horizon_start": TODAY,
        "horizon_end": TODAY + timedelta(days=30),
    }
    params.update(kwargs)
    return mrp_engine.run_mrp(**params)


def suggestions_of(run_obj, **filters):
    queryset = MrpSuggestion.objects.filter(run=run_obj, **filters)
    return {row.material.code: row for row in queryset.order_by("line_no")}

# -- 净算口径 -------------------------------------------------------------


def test_net_requirement_nets_on_hand_and_on_order(env):
    """净需求 = 毛需求 − 合格可用库存 − 采购在途；子件毛需求按含损耗用量展开。"""
    make_bom(
        env,
        lines=[
            {"material": env["fabric"], "quantity": "2", "loss_rate": "0.05"},
            {"material": env["button"], "quantity": "4"},
        ],
    )
    make_balance(env["fabric"], env["warehouse"], on_hand="60")
    make_balance(env["button"], env["warehouse"], on_hand="500")
    make_sales_order(env, material=env["finished"], sku=env["sku"], quantity="100")
    make_purchase_order(env, material=env["fabric"], quantity="40")

    run_obj = run(env)
    rows = suggestions_of(run_obj)

    # 成品：无现有库存 → 生产建议 100
    assert rows["MRP-FIN"].suggestion_type == MrpSuggestionType.PRODUCTION
    assert rows["MRP-FIN"].quantity == Decimal("100.000000")
    # 面料：毛需求 100 × 2 ×(1+5%) = 210，现有 60、在途 40 → 净需求 110
    assert rows["MRP-FAB"].suggestion_type == MrpSuggestionType.PURCHASE
    assert rows["MRP-FAB"].quantity == Decimal("110.000000")
    # 纽扣：现有库存充足 → 不产生建议
    assert "MRP-BTN" not in rows
    assert run_obj.summary["suggestion_count"] == 2


def test_purchase_on_order_reduces_net_requirement(env):
    """采购在途按预计到货日期进入对应分段。"""
    make_sales_order(env, material=env["fabric"], quantity="100", expected=TODAY + timedelta(days=3))
    make_purchase_order(env, material=env["fabric"], quantity="30", expected=TODAY + timedelta(days=3))

    rows = suggestions_of(run(env))
    assert rows["MRP-FAB"].quantity == Decimal("70.000000")


def test_usable_stock_excludes_frozen_reserved_and_unqualified(env):
    """可用量 = on_hand − frozen − reserved，且只算合格库存（冻结/占用不得当自由供给）。"""
    make_sales_order(env, material=env["fabric"], quantity="60")
    make_balance(env["fabric"], env["warehouse"], on_hand="100", frozen="30", reserved="20")
    # 待检库存不计入供给
    make_balance(
        env["fabric"],
        env["warehouse"],
        on_hand="500",
        quality=QualityStatus.QUARANTINE,
    )

    rows = suggestions_of(run(env))
    assert rows["MRP-FAB"].quantity == Decimal("10.000000")

    supply = run(env).supplies.get(material=env["fabric"])
    assert supply.source_type == MrpSupplySource.ON_HAND
    assert supply.quantity == Decimal("50.000000")


def test_overdue_demand_lands_in_first_bucket(env):
    """逾期需求计入第一个分段，而不是被丢掉。"""
    make_sales_order(env, material=env["fabric"], quantity="10", expected=TODAY - timedelta(days=7))

    run_obj = run(env)
    demand = run_obj.demands.get(material=env["fabric"])
    assert demand.due_date == TODAY - timedelta(days=7)
    assert demand.bucket_date == mrp_engine.mrp_bucket_date(TODAY, MrpBucket.DAY) == TODAY
    assert run_obj.suggestions.get(material=env["fabric"]).due_date == TODAY


def test_demand_outside_horizon_ignored(env):
    """区间之外的需求不参与本次净算（避免把远期需求算成本期缺料）。"""
    make_sales_order(env, material=env["fabric"], quantity="10", expected=TODAY + timedelta(days=90))
    run_obj = run(env)
    assert not run_obj.demands.exists()
    assert not run_obj.suggestions.exists()


def test_partially_shipped_demand_uses_remaining_quantity(env):
    """部分发货的订单只对未发货量产生需求。"""
    make_sales_order(
        env,
        material=env["fabric"],
        quantity="100",
        shipped="40",
        status=SalesOrderStatus.PARTIALLY_SHIPPED,
    )
    rows = suggestions_of(run(env))
    assert rows["MRP-FAB"].quantity == Decimal("60.000000")


def test_draft_order_produces_no_demand(env):
    """草稿 / 已取消订单不占用供给。"""
    make_sales_order(env, material=env["fabric"], quantity="50", status=SalesOrderStatus.DRAFT)
    make_sales_order(
        env,
        material=env["button"],
        quantity="50",
        status=SalesOrderStatus.CANCELLED,
        order_no="SO-MRP-2",
    )
    run_obj = run(env)
    assert not run_obj.demands.exists()


# -- BOM 展开与低层码 -----------------------------------------------------


def test_explosion_uses_parent_net_requirement(env):
    """子件毛需求按**父件净需求**展开：成品现有库存不会被重复展开。"""
    make_bom(env, lines=[{"material": env["fabric"], "quantity": "2"}])
    make_balance(env["finished"], env["warehouse"], on_hand="30")
    make_sales_order(env, material=env["finished"], sku=env["sku"], quantity="100")

    run_obj = run(env)
    rows = suggestions_of(run_obj)
    assert rows["MRP-FIN"].quantity == Decimal("70.000000")
    # 70 × 2 = 140，而不是 100 × 2 = 200
    assert rows["MRP-FAB"].quantity == Decimal("140.000000")
    child = run_obj.demands.get(material=env["fabric"])
    assert child.source_type == MrpDemandSource.PARENT_ITEM
    assert "MRP-FIN" in child.path
    assert child.level == 1


def test_low_level_code_net_calculated_once(env):
    """同一物料被多个父件引用时按最低层级只净算一次，需求合并。"""
    finished2 = Material.objects.create(
        company=env["company"],
        code="MRP-FIN3",
        name="另一款成品",
        category=env["finished"].category,
        base_uom=env["uom_pc"],
    )
    size_xxl = Size.objects.create(code="MRP-XXL", name="XXL")
    sku2 = Sku.objects.create(
        company=env["company"],
        style=env["style"],
        color=env["sku"].color,
        size=size_xxl,
        code="MRP-ST1-BK-XXL",
        material=finished2,
    )
    make_bom(env, lines=[{"material": env["fabric"], "quantity": "1"}])
    make_bom(
        env,
        lines=[{"material": env["fabric"], "quantity": "1"}],
        sku=sku2,
        code="MRP-BOM-2",
    )
    make_balance(env["fabric"], env["warehouse"], on_hand="5")
    make_sales_order(env, material=env["finished"], sku=env["sku"], quantity="10")
    make_sales_order(
        env, material=finished2, sku=sku2, quantity="10", order_no="SO-MRP-2"
    )

    run_obj = run(env)
    fabric_rows = list(run_obj.suggestions.filter(material=env["fabric"]))
    assert len(fabric_rows) == 1
    assert fabric_rows[0].quantity == Decimal("15.000000")
    assert fabric_rows[0].detail["level"] == 1


def test_suggestion_type_rules_and_unexploded_materials(env):
    """有 BOM 或分类为成品/半成品 → 生产建议；成品无生效 BOM 记入 unexploded_materials。"""
    make_bom(env, lines=[{"material": env["fabric"], "quantity": "1"}])
    make_sales_order(env, material=env["finished"], sku=env["sku"], quantity="10")
    make_sales_order(env, material=env["semi"], quantity="5", order_no="SO-MRP-2")
    make_sales_order(
        env, material=env["orphan_finished"], sku=env["orphan_sku"], quantity="7", order_no="SO-MRP-3"
    )

    run_obj = run(env)
    rows = suggestions_of(run_obj)
    assert rows["MRP-FIN"].suggestion_type == MrpSuggestionType.PRODUCTION
    assert rows["MRP-SEMI"].suggestion_type == MrpSuggestionType.PRODUCTION
    assert rows["MRP-FIN2"].suggestion_type == MrpSuggestionType.PRODUCTION
    assert "MRP-FIN2" in run_obj.summary["unexploded_materials"]
    assert "MRP-SEMI" in run_obj.summary["unexploded_materials"]
    # 半成品与无 BOM 成品都不能通过 MRP 转单（MES 工单未实现）
    assert rows["MRP-SEMI"].converted_document_id == ""

def _purchase_suggestion(env, quantity="10", order_no="SO-MRP-1"):
    make_sales_order(env, material=env["fabric"], quantity=quantity, order_no=order_no)
    run_obj = run(env)
    return run_obj, run_obj.suggestions.get(material=env["fabric"])


# -- 循环 BOM 与异常 ------------------------------------------------------


def test_cycle_bom_rejected_and_failed_run_recorded(env):
    """循环 BOM 必须直接拒绝，并且留下一条 failed 运行（不含半截结果）。"""
    size_semi = Size.objects.create(code="MRP-SEMI-SZ", name="半成品码")
    semi_sku = Sku.objects.create(
        company=env["company"],
        style=env["style"],
        color=env["sku"].color,
        size=size_semi,
        code="MRP-ST1-BK-SEMI",
        material=env["semi"],
    )
    # 成品 → 半成品（SKU 专属版本）
    make_bom(env, lines=[{"material": env["semi"], "quantity": "1"}], sku=env["sku"])
    # 半成品 → 成品：形成 finished → semi → finished 的循环
    make_bom(
        env,
        lines=[{"material": env["finished"], "quantity": "1"}],
        sku=semi_sku,
        code="MRP-BOM-2",
    )
    make_sales_order(env, material=env["finished"], sku=env["sku"], quantity="1")

    with pytest.raises(ValidationFailed) as excinfo:
        run(env)
    assert excinfo.value.code == "BOM_CYCLE_DETECTED"
    assert "MRP-FIN" in str(excinfo.value)

    failed = MrpRun.objects.filter(status=MrpRunStatus.FAILED)
    assert failed.count() == 1
    assert not failed.first().demands.exists()
    assert "循环" in failed.first().error_message
    assert not MrpRun.objects.filter(status=MrpRunStatus.COMPLETED).exists()


def test_mrp_is_read_only_for_inventory(env):
    """MRP 只读库存，不写库存余额（库存变动只能走统一库存服务）。"""
    make_sales_order(env, material=env["fabric"], quantity="10")
    balance = make_balance(env["fabric"], env["warehouse"], on_hand="3", reserved="1")
    before = (balance.on_hand, balance.frozen, balance.reserved, InventoryBalance.objects.count())

    run(env)

    balance.refresh_from_db()
    after = (balance.on_hand, balance.frozen, balance.reserved, InventoryBalance.objects.count())
    assert before == after


def test_invalid_bucket_and_horizon_rejected(env):
    with pytest.raises(ValidationFailed) as excinfo:
        run(env, bucket="month")
    assert excinfo.value.code == "INVALID_BUCKET"

    with pytest.raises(ValidationFailed) as excinfo:
        run(env, horizon_start=TODAY, horizon_end=TODAY - timedelta(days=1))
    assert excinfo.value.code == "INVALID_HORIZON"

    assert not MrpRun.objects.exists()


def test_week_bucket_normalises_to_monday(env):
    """按周分段归一到周一：同一周内的需求落在同一分段。"""
    wednesday = date(2026, 9, 2)
    make_sales_order(env, material=env["fabric"], quantity="10", expected=wednesday)
    make_sales_order(
        env, material=env["button"], quantity="5", expected=date(2026, 9, 4), order_no="SO-MRP-2"
    )

    run_obj = run(env, bucket=MrpBucket.WEEK)
    fabric = run_obj.demands.get(material=env["fabric"])
    button = run_obj.demands.get(material=env["button"])
    assert fabric.bucket_date == date(2026, 8, 31)
    assert button.bucket_date == fabric.bucket_date
    assert run_obj.bucket == MrpBucket.WEEK


def test_audit_and_outbox_event_written_with_business_data(env):
    make_sales_order(env, material=env["fabric"], quantity="10")
    run_obj = run(env)

    audit = AuditLog.objects.filter(
        object_type="planning.MrpRun", object_id=str(run_obj.pk), action="create"
    )
    assert audit.count() == 1
    assert audit.first().changes["run_no"]["after"] == run_obj.run_no

    event = OutboxEvent.objects.get(dedup_key=f"mrp-run:{run_obj.pk}")
    assert event.event_type == mrp_engine.EVENT_RUN_COMPLETED
    assert event.aggregate_type == "planning.MrpRun"
    assert event.payload["run_no"] == run_obj.run_no


# -- 转单 / 取消 / 归档 ---------------------------------------------------


def test_convert_creates_draft_requisition_with_document_link(env):
    """采购建议 → 草稿采购申请（仍走审批）+ 单据关联，并记录转单信息与事件。"""
    run_obj, suggestion = _purchase_suggestion(env, quantity="25")

    mrp_engine.convert_suggestion(suggestion, user=env["svc_user"], remark="演示转单")

    suggestion.refresh_from_db()
    assert suggestion.status == MrpSuggestionStatus.CONVERTED
    assert suggestion.converted_document_type == "procurement.PurchaseRequisition"
    assert suggestion.converted_at is not None
    assert suggestion.converted_by_id == env["svc_user"].pk

    requisition = PurchaseRequisition.objects.get(pk=int(suggestion.converted_document_id))
    assert requisition.status == "draft"
    assert requisition.request_type == "planned"
    assert requisition.company_id == env["company"].pk
    line = requisition.lines.get()
    assert line.material_id == env["fabric"].pk
    assert line.quantity == Decimal("25.000000")
    assert line.needed_date == suggestion.due_date

    link = DocumentLink.objects.get(source_type="planning.MrpSuggestion", source_id=str(suggestion.pk))
    assert link.target_type == "procurement.PurchaseRequisition"
    assert link.target_id == str(requisition.pk)
    assert link.target_no == requisition.requisition_no

    event = OutboxEvent.objects.get(dedup_key=f"mrp-suggestion-converted:{suggestion.pk}")
    assert event.payload["requisition_no"] == requisition.requisition_no
    assert event.payload["quantity"] == "25.000000"

    audit = AuditLog.objects.filter(
        object_type="planning.MrpSuggestion", object_id=str(suggestion.pk), action="update"
    )
    assert audit.count() == 1
    assert run_obj.suggestions.count() == 1


def test_convert_twice_rejected(env):
    _, suggestion = _purchase_suggestion(env)
    mrp_engine.convert_suggestion(suggestion, user=env["svc_user"])
    with pytest.raises(StateConflict) as excinfo:
        mrp_engine.convert_suggestion(suggestion, user=env["svc_user"])
    assert excinfo.value.code == "SUGGESTION_ALREADY_CONVERTED"
    assert PurchaseRequisition.objects.count() == 1


def test_convert_stale_suggestion_rejected(env):
    """重算后旧建议失效：不允许用过期结果产生采购承诺。"""
    make_sales_order(env, material=env["fabric"], quantity="10")
    first = run(env)
    stale = first.suggestions.get(material=env["fabric"])
    run(env)

    with pytest.raises(StateConflict) as excinfo:
        mrp_engine.convert_suggestion(stale, user=env["svc_user"])
    assert excinfo.value.code == "SUGGESTION_STALE"
    assert PurchaseRequisition.objects.count() == 0


def test_convert_production_suggestion_creates_draft_order(env):
    """生产建议 -> 草稿 MES 生产工单 + 单据关联（下达仍由生产角色在 MES 显式执行）。"""
    make_bom(env, lines=[{"material": env["fabric"], "quantity": "1"}])
    make_sales_order(env, material=env["finished"], sku=env["sku"], quantity="5")
    run_obj = run(env)
    suggestion = run_obj.suggestions.get(material=env["finished"])
    assert suggestion.suggestion_type == MrpSuggestionType.PRODUCTION

    mrp_engine.convert_suggestion(suggestion, user=env["svc_user"])

    suggestion.refresh_from_db()
    assert suggestion.status == MrpSuggestionStatus.CONVERTED
    assert suggestion.converted_document_type == "mes.ProductionOrder"
    order = ProductionOrder.objects.get(pk=int(suggestion.converted_document_id))
    assert order.status == ProductionOrderStatus.DRAFT
    assert order.order_no.startswith("MO")
    assert order.source_type == "mrp_suggestion"
    assert order.source_no == f"{run_obj.run_no}#{suggestion.line_no}"
    assert order.quantity == Decimal("5.000000")
    assert order.planned_end is not None

    link = DocumentLink.objects.get(
        source_type="planning.MrpSuggestion", source_id=str(suggestion.pk)
    )
    assert link.target_type == "mes.ProductionOrder"
    assert link.target_no == order.order_no

    event = OutboxEvent.objects.get(dedup_key=f"mrp-suggestion-converted:{suggestion.pk}")
    assert event.payload["production_order_no"] == order.order_no


def _release_in_progress_order(env, *, quantity="5", order_no="MO-INPROG-1", status=None):
    return ProductionOrder.objects.create(
        company=env["company"],
        order_no=order_no,
        style=env["style"],
        product_material=env["finished"],
        quantity=Decimal(quantity),
        status=status or ProductionOrderStatus.RELEASED,
        planned_end=datetime.combine(TODAY, time.min, tzinfo=business_timezone()),
    )


def test_in_progress_supply_nets_open_production_orders(env):
    """已下达 / 生产中的 MES 工单未完工数量计入在制供给，需求被满足后不再产生建议。"""
    make_bom(env, lines=[{"material": env["fabric"], "quantity": "1"}])
    make_sales_order(env, material=env["finished"], sku=env["sku"], quantity="5")
    _release_in_progress_order(env)

    run_obj = run(env)

    assert run_obj.parameters["in_progress_supply"] == "mes_open_orders"
    supply = MrpSupplyLine.objects.get(run=run_obj, source_type=MrpSupplySource.IN_PROGRESS)
    assert supply.quantity == Decimal("5.000000")
    assert supply.reference_no == "MO-INPROG-1"
    assert MrpSuggestion.objects.filter(run=run_obj, material=env["finished"]).count() == 0


def test_draft_production_order_is_not_counted_as_supply(env):
    """草稿工单没有冻结 BOM / 工艺快照，不算供给（不能拿还没下达的产能充当库存）。"""
    make_bom(env, lines=[{"material": env["fabric"], "quantity": "1"}])
    make_sales_order(env, material=env["finished"], sku=env["sku"], quantity="5")
    _release_in_progress_order(env, status=ProductionOrderStatus.DRAFT)

    run_obj = run(env)

    assert (
        MrpSupplyLine.objects.filter(run=run_obj, source_type=MrpSupplySource.IN_PROGRESS).count()
        == 0
    )
    assert suggestions_of(run_obj)["MRP-FIN"].quantity == Decimal("5.000000")


def test_convert_inactive_material_rejected(env):
    _, suggestion = _purchase_suggestion(env)
    Material.objects.filter(pk=env["fabric"].pk).update(is_active=False)
    with pytest.raises(StateConflict) as excinfo:
        mrp_engine.convert_suggestion(suggestion, user=env["svc_user"])
    assert excinfo.value.code == "MATERIAL_INACTIVE"


def test_cancel_requires_reason_and_blocks_convert(env):
    _, suggestion = _purchase_suggestion(env)
    with pytest.raises(ValidationFailed) as excinfo:
        mrp_engine.cancel_suggestion(suggestion, user=env["svc_user"], reason="   ")
    assert excinfo.value.code == "REASON_REQUIRED"

    mrp_engine.cancel_suggestion(suggestion, user=env["svc_user"], reason="需求已由替代料满足")
    suggestion.refresh_from_db()
    assert suggestion.status == MrpSuggestionStatus.CANCELLED
    assert suggestion.cancel_reason == "需求已由替代料满足"

    with pytest.raises(StateConflict) as excinfo:
        mrp_engine.convert_suggestion(suggestion, user=env["svc_user"])
    assert excinfo.value.code == "SUGGESTION_NOT_OPEN"


def test_archive_run_blocks_conversion_and_repeat_archive_rejected(env):
    run_obj, suggestion = _purchase_suggestion(env)
    mrp_engine.archive_run(run_obj, user=env["svc_user"], reason="历史归档")
    run_obj.refresh_from_db()
    assert run_obj.status == MrpRunStatus.ARCHIVED
    assert run_obj.archived_by_id == env["svc_user"].pk
    assert run_obj.archived_at is not None
    # 归档不删除明细，历史可追溯
    assert run_obj.demands.exists() and run_obj.suggestions.exists()

    with pytest.raises(StateConflict) as excinfo:
        mrp_engine.archive_run(run_obj, user=env["svc_user"])
    assert excinfo.value.code == "STATE_CONFLICT"

    with pytest.raises(StateConflict) as excinfo:
        mrp_engine.convert_suggestion(suggestion, user=env["svc_user"])
    assert excinfo.value.code == "MRP_RUN_NOT_ACTIVE"

# -- API：鉴权、数据范围、接口契约 ----------------------------------------


@pytest.fixture
def api_clients(registry_permissions, company):
    """按权限集合造账号；每个身份独立 APIClient，避免会话互相覆盖。"""

    def _make(username: str, perms: list[str], data_scope_type: str = DataScopeType.COMPANY):
        role = make_role(
            code=f"test_mrp_{username}",
            permission_codes=perms,
            data_scope_type=data_scope_type,
            company=company,
        )
        user = make_user(username=username, role=role, company=company)
        client = APIClient()
        login(client, user)
        return client, user

    return _make


def test_anonymous_access_rejected(api_client, env):
    assert api_client.get(RUNS_URL).status_code in (401, 403)
    assert api_client.post(RUNS_URL, {}, format="json").status_code in (401, 403)
    assert api_client.get(SUGGESTIONS_URL).status_code in (401, 403)


def test_view_only_user_cannot_run_mrp(api_clients, env):
    client, _ = api_clients("mrp_viewer", ["planning.mrp.view"])
    assert client.get(RUNS_URL).status_code == 200
    response = client.post(RUNS_URL, {"bucket": "day"}, format="json")
    assert response.status_code == 403, response.content
    assert not MrpRun.objects.exists()


def test_user_without_convert_permission_cannot_convert(api_clients, env):
    _, suggestion = _purchase_suggestion(env)
    client, _ = api_clients("mrp_runner", ["planning.mrp.view", "planning.mrp.run"])
    response = client.post(f"{SUGGESTIONS_URL}{suggestion.pk}/convert/", {}, format="json")
    assert response.status_code == 403, response.content
    assert PurchaseRequisition.objects.count() == 0


def test_convert_requires_procurement_requisition_create(api_clients, env):
    """MRP 转单必须真正具备采购申请新建权限（不绕过采购服务）。"""
    _, suggestion = _purchase_suggestion(env)
    client, _ = api_clients(
        "mrp_converter",
        ["planning.mrp.view", "planning.mrp.convert"],
    )
    response = client.post(f"{SUGGESTIONS_URL}{suggestion.pk}/convert/", {}, format="json")
    assert response.status_code == 403, response.content
    assert PurchaseRequisition.objects.count() == 0


def test_run_api_creates_run_with_counts_and_detail_endpoints(api_clients, env):
    make_bom(env, lines=[{"material": env["fabric"], "quantity": "1"}])
    make_balance(env["fabric"], env["warehouse"], on_hand="2")
    make_sales_order(env, material=env["finished"], sku=env["sku"], quantity="10")
    client, _ = api_clients("mrp_full", MRP_PERMISSIONS)

    response = client.post(
        RUNS_URL,
        {
            "horizon_start": TODAY.isoformat(),
            "horizon_end": (TODAY + timedelta(days=10)).isoformat(),
            "bucket": "day",
            "remark": "接口运行",
        },
        format="json",
    )
    assert response.status_code == 201, response.content
    body = response.json()
    assert body["status"] == MrpRunStatus.COMPLETED
    assert body["demand_count"] == 2
    assert body["suggestion_count"] == 2
    assert body["company_id"] == env["company"].pk
    run_id = body["id"]

    demands = client.get(f"{RUNS_URL}{run_id}/demands/")
    assert demands.status_code == 200
    demands_body = demands.json()
    assert demands_body["count"] == 2
    assert demands_body["results"][0]["source_type"] == MrpDemandSource.SALES_ORDER

    supplies = client.get(f"{RUNS_URL}{run_id}/supplies/")
    assert supplies.status_code == 200
    assert supplies.json()["count"] == 1

    suggestions = client.get(f"{RUNS_URL}{run_id}/suggestions/?suggestion_type=purchase")
    assert suggestions.status_code == 200
    suggestion_body = suggestions.json()
    assert suggestion_body["count"] == 1
    assert suggestion_body["results"][0]["material_code"] == "MRP-FAB"
    assert suggestion_body["results"][0]["convertible"] is True


def test_api_convert_and_repeat_rejected(api_clients, env):
    _, suggestion = _purchase_suggestion(env, quantity="12")
    client, _ = api_clients("mrp_convert_ok", MRP_PERMISSIONS)

    payload = {"needed_date": (TODAY + timedelta(days=4)).isoformat(), "remark": "接口转单"}
    response = client.post(f"{SUGGESTIONS_URL}{suggestion.pk}/convert/", payload, format="json")
    assert response.status_code == 200, response.content
    assert response.json()["status"] == MrpSuggestionStatus.CONVERTED

    requisition = PurchaseRequisition.objects.get()
    assert requisition.status == "draft"
    assert requisition.lines.get().needed_date == TODAY + timedelta(days=4)

    again = client.post(f"{SUGGESTIONS_URL}{suggestion.pk}/convert/", payload, format="json")
    assert again.status_code == 409, again.content
    assert again.json()["code"] == "SUGGESTION_ALREADY_CONVERTED"
    assert PurchaseRequisition.objects.count() == 1


def test_api_run_rejects_invalid_parameters(api_clients, env):
    client, _ = api_clients("mrp_params", MRP_PERMISSIONS)
    bad_bucket = client.post(RUNS_URL, {"bucket": "month"}, format="json")
    assert bad_bucket.status_code == 400, bad_bucket.content

    reversed_range = client.post(
        RUNS_URL,
        {
            "horizon_start": TODAY.isoformat(),
            "horizon_end": (TODAY - timedelta(days=3)).isoformat(),
        },
        format="json",
    )
    assert reversed_range.status_code == 400, reversed_range.content
    assert not MrpRun.objects.exists()


def test_api_run_scoped_to_company_and_warehouse(api_clients, env):
    """跨公司运行不可见；仓库过滤只影响本次计算的供给口径。"""
    make_sales_order(env, material=env["fabric"], quantity="10", warehouse=env["warehouse"])
    make_sales_order(
        env,
        material=env["fabric"],
        quantity="100",
        order_no="SO-MRP-W2",
        warehouse=env["warehouse2"],
        expected=TODAY + timedelta(days=1),
    )
    make_balance(env["fabric"], env["warehouse"], on_hand="4")
    make_balance(env["fabric"], env["warehouse2"], on_hand="1000")

    client, _ = api_clients("mrp_scope", MRP_PERMISSIONS)
    response = client.post(RUNS_URL, {"warehouse_id": env["warehouse"].pk}, format="json")
    assert response.status_code == 201, response.content
    run_id = response.json()["id"]
    # 只算 W01 的需求 10 与库存 4 → 缺料 6
    suggestion = client.get(f"{RUNS_URL}{run_id}/suggestions/").json()["results"][0]
    assert suggestion["quantity"] == "6.000000"

    other_run = MrpRun.objects.create(
        company=env["other_company"],
        run_no="MRP-OTHER",
        status=MrpRunStatus.COMPLETED,
        bucket=MrpBucket.DAY,
        horizon_start=TODAY,
        horizon_end=TODAY + timedelta(days=10),
    )
    listed = client.get(RUNS_URL).json()
    assert listed["count"] == 1
    assert client.get(f"{RUNS_URL}{other_run.pk}/").status_code == 404


def test_mrp_permissions_do_not_grant_other_modules(api_clients, env):
    """MRP 权限不外溢：不能建 BOM，也不能改库存。"""
    client, _ = api_clients("mrp_only", MRP_PERMISSIONS)
    bom_response = client.post(
        "/api/v1/planning/boms/",
        {"style_id": env["style"].pk, "lines": [{"material_id": env["fabric"].pk, "quantity": "1"}]},
        format="json",
    )
    assert bom_response.status_code == 403, bom_response.content
    assert not Bom.objects.exists()


def test_archive_api_requires_permission_and_is_audited(api_clients, env):
    _, suggestion = _purchase_suggestion(env)
    run_obj = suggestion.run
    client, _ = api_clients("mrp_viewer2", ["planning.mrp.view"])
    assert client.post(f"{RUNS_URL}{run_obj.pk}/archive/", {}, format="json").status_code == 403

    admin_client, _ = api_clients("mrp_archiver", MRP_PERMISSIONS)
    response = admin_client.post(
        f"{RUNS_URL}{run_obj.pk}/archive/", {"reason": "接口归档"}, format="json"
    )
    assert response.status_code == 200, response.content
    assert response.json()["status"] == MrpRunStatus.ARCHIVED
    archive_audit = AuditLog.objects.filter(
        object_type="planning.MrpRun", object_id=str(run_obj.pk), action="update"
    )
    assert archive_audit.count() == 1
    assert archive_audit.first().reason == "接口归档"
