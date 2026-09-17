"""统一库存服务用例（任务书 10.8、5.6、14.2 第 5~11 条）。

覆盖：
* 余额 / 流水 / 维度键（含「无批次无卷号」的规范化）；
* 单据过账、冲销、质量放行与幂等；
* 流水只追加（模型级不可篡改）；
* **并发**：同维度并发创建只有一行、并发出库不产生负库存、死锁重试不重复落账；
* 接口层的登录、操作权限与仓库数据范围。

并发用例使用 `django_db(transaction=True)` + 真实线程与**独立数据库连接**，
不依赖测试框架的外层事务掩盖问题（任务书 14.2 明确要求）。
"""

from __future__ import annotations

import threading
from decimal import Decimal
from functools import partial

import pytest
from django.core.management import call_command
from django.db import OperationalError, connections

from apps.core.exceptions import (
    InsufficientStock,
    StateConflict,
    ValidationFailed,
)
from apps.core.models import OutboxEvent
from apps.identity.models import DataScopeType, ScopeDimension
from apps.masterdata.models import Material, MaterialCategory, UoM
from apps.wms.models import (
    DocumentStatus,
    DocumentType,
    ImmutableLedgerError,
    InventoryBalance,
    InventoryDocument,
    InventoryTransaction,
    Location,
    QualityStatus,
    TransactionType,
    Warehouse,
    Zone,
)
from apps.wms.services import stock
from tests.conftest import make_role, make_user

pytestmark = pytest.mark.django_db

DOCUMENTS_URL = "/api/v1/wms/inventory-documents/"
BALANCES_URL = "/api/v1/wms/inventory-balances/"
TRANSACTIONS_URL = "/api/v1/wms/inventory-transactions/"

INVENTORY_PERMISSIONS = [
    "wms.inventory.view",
    "wms.document.view",
    "wms.document.create",
    "wms.document.update",
    "wms.document.post",
    "wms.document.reverse",
    "wms.quality.release",
    "wms.warehouse.view",
]


@pytest.fixture
def inventory_code_rules(db):
    """库存单据取号依赖编码规则；测试库不会跑 bootstrap_system，这里显式建规则。"""
    from apps.core.models import CodeRule, ResetPeriod

    rules = (
        ("GR", "采购收货单号", "GR{YYYYMMDD}{SEQ:4}"),
        ("ST", "盘点单号", "ST{YYYYMMDD}{SEQ:4}"),
        ("TR", "移库单号", "TR{YYYYMMDD}{SEQ:4}"),
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
def stock_env(company, department_factory, inventory_code_rules):
    """最小库存环境：1 个物料 + 2 个仓库（各 1 个储位）。"""
    category = MaterialCategory.objects.create(
        code="INV-CAT", name="测试物料分类", category_type="fabric"
    )
    uom = UoM.objects.create(code="INV-M", name="米", category="length")
    material = Material.objects.create(
        company=company, code="INV-M1", name="测试面料", category=category, base_uom=uom
    )
    warehouses: dict[str, Warehouse] = {}
    locations: dict[str, Location] = {}
    for key, code, factory_code in (("a", "INV-WHA", "F01"), ("b", "INV-WHB", "F02")):
        warehouse = Warehouse.objects.create(
            company=company,
            code=code,
            name=f"测试仓库{code}",
            warehouse_type="raw",
            factory=department_factory["factories"][factory_code],
        )
        zone = Zone.objects.create(warehouse=warehouse, code="Z1", name="存储区")
        location = Location.objects.create(zone=zone, code="L1", name="储位1")
        locations[key] = location
        if key == "a":
            # 同一仓库内的第二个储位：移库在同一仓库内进行，跨仓库属于调拨
            locations["a2"] = Location.objects.create(zone=zone, code="L2", name="储位2")
        warehouses[key] = warehouse
    return {
        "company": company,
        "material": material,
        "warehouse_a": warehouses["a"],
        "warehouse_b": warehouses["b"],
        "location_a": locations["a"],
        "location_a2": locations["a2"],
        "location_b": locations["b"],
    }


@pytest.fixture
def stock_user(company):
    """服务层用例使用超级管理员，专注库存规则本身。"""
    return make_user(username="inv_service", company=company, is_superuser=True)


def _line(env, quantity, *, location=None, batch_no="", roll_no="", quality=QualityStatus.QUALIFIED,
          target_location=None, target_quality="", direction="in"):
    return {
        "material_id": env["material"].id,
        "location_id": (location or env["location_a"]).id,
        "target_location_id": target_location.id if target_location is not None else None,
        "batch_no": batch_no,
        "roll_no": roll_no,
        "quality_status": quality,
        "target_quality_status": target_quality,
        "direction": direction,
        "quantity": quantity,
    }


def _create(env, document_type, lines, *, user, warehouse=None, **extra):
    return stock.create_document(
        document_type=document_type,
        company=env["company"].id,
        warehouse=warehouse or env["warehouse_a"],
        lines=lines,
        user=user,
        **extra,
    )


def _receipt(env, quantity, *, user, warehouse=None, **kwargs):
    return _create(
        env, DocumentType.RECEIPT, [_line(env, quantity, **kwargs)], user=user, warehouse=warehouse
    )


def _issue(env, quantity, *, user, **kwargs):
    return _create(env, DocumentType.ISSUE, [_line(env, quantity, **kwargs)], user=user)


def _posted_receipt(env, quantity, *, user, **kwargs):
    return stock.post_document(_receipt(env, quantity, user=user, **kwargs), user=user)


def _balance(env, location=None, **filters):
    return InventoryBalance.objects.get(
        material=env["material"], location=location or env["location_a"], **filters
    )
def _run_concurrently(targets):
    """在独立线程与独立连接上同时启动若干操作，收集结果与异常。"""
    results: list = []
    errors: list = []
    guard = threading.Lock()
    barrier = threading.Barrier(len(targets))

    def runner(func):
        def run():
            try:
                barrier.wait(timeout=15)
                value = func()
                with guard:
                    results.append(value)
            except Exception as exc:  # noqa: BLE001 - 并发用例需要收集全部异常类型
                with guard:
                    errors.append(exc)
            finally:
                connections.close_all()

        return run

    threads = [threading.Thread(target=runner(target), daemon=True) for target in targets]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=90)
    return results, errors


# ---------------------------------------------------------------------------
# 余额、流水与维度
# ---------------------------------------------------------------------------


def test_receipt_creates_balance_and_ledger(stock_env, stock_user):
    posted = _posted_receipt(stock_env, Decimal("12.5"), user=stock_user)

    assert posted.status == DocumentStatus.POSTED
    assert posted.document_no.startswith("GR")
    assert posted.posted_at is not None

    balance = _balance(stock_env)
    assert balance.on_hand == Decimal("12.500000")
    assert balance.available == Decimal("12.500000")
    assert balance.quality_status == QualityStatus.QUALIFIED
    assert balance.dimension_key == balance.build_dimension_key()
    assert len(balance.dimension_key) == 32

    txn = InventoryTransaction.objects.get(document=posted)
    assert txn.transaction_type == TransactionType.RECEIPT
    assert txn.quantity == Decimal("12.500000")
    assert txn.on_hand_before == Decimal("0.000000")
    assert txn.on_hand_after == Decimal("12.500000")
    assert txn.dimension_key == balance.dimension_key
    assert txn.operator_id == stock_user.pk
    assert txn.dedup_key == f"{posted.pk}:{txn.document_line_id}:1:in"


def test_issue_reduces_balance(stock_env, stock_user):
    _posted_receipt(stock_env, Decimal("10"), user=stock_user)
    posted = stock.post_document(_issue(stock_env, Decimal("4"), user=stock_user), user=stock_user)

    balance = _balance(stock_env)
    assert balance.on_hand == Decimal("6.000000")
    assert balance.available == Decimal("6.000000")
    txn = InventoryTransaction.objects.get(document=posted)
    assert txn.quantity == Decimal("-4.000000")
    assert txn.transaction_type == TransactionType.ISSUE


def test_empty_batch_and_roll_share_one_dimension(stock_env, stock_user):
    """MySQL 唯一索引不把两个 NULL 视为相等：无批次/无卷号必须落到同一个维度键。"""
    _posted_receipt(stock_env, Decimal("3"), user=stock_user, batch_no="", roll_no="")
    stock.post_document(_receipt(stock_env, Decimal("2"), user=stock_user), user=stock_user)

    assert InventoryBalance.objects.filter(material=stock_env["material"]).count() == 1
    assert _balance(stock_env).on_hand == Decimal("5.000000")


def test_batch_no_is_case_insensitive(stock_env, stock_user):
    _posted_receipt(stock_env, Decimal("1"), user=stock_user, batch_no="Lot-A")
    _posted_receipt(stock_env, Decimal("1"), user=stock_user, batch_no="LOT-a")

    assert InventoryBalance.objects.filter(material=stock_env["material"]).count() == 1
    assert _balance(stock_env).on_hand == Decimal("2.000000")


def test_multiple_batches_are_separate_dimensions(stock_env, stock_user):
    _posted_receipt(stock_env, Decimal("1"), user=stock_user, batch_no="B1")
    _posted_receipt(stock_env, Decimal("1"), user=stock_user, batch_no="B2")

    assert InventoryBalance.objects.filter(material=stock_env["material"]).count() == 2
    assert InventoryBalance.objects.get(batch_no="B1").on_hand == Decimal("1.000000")


def test_insufficient_stock_is_rejected_without_side_effect(stock_env, stock_user):
    _posted_receipt(stock_env, Decimal("3"), user=stock_user)
    document = _issue(stock_env, Decimal("5"), user=stock_user)

    with pytest.raises(InsufficientStock) as excinfo:
        stock.post_document(document, user=stock_user)

    assert excinfo.value.code == "INSUFFICIENT_STOCK"
    assert excinfo.value.details["required"] == "5.000000"
    assert excinfo.value.details["available"] == "3.000000"
    document.refresh_from_db()
    assert document.status == DocumentStatus.DRAFT
    assert InventoryTransaction.objects.filter(document=document).count() == 0
    assert _balance(stock_env).on_hand == Decimal("3.000000")


def test_ledger_is_append_only(stock_env, stock_user):
    posted = _posted_receipt(stock_env, Decimal("2"), user=stock_user)
    txn = InventoryTransaction.objects.get(document=posted)

    txn.reason = "试图篡改"
    with pytest.raises(ImmutableLedgerError):
        txn.save()
    with pytest.raises(ImmutableLedgerError):
        txn.delete()
    assert InventoryTransaction.objects.filter(pk=txn.pk).count() == 1
# ---------------------------------------------------------------------------
# 质量状态与质量放行
# ---------------------------------------------------------------------------


def test_quarantine_stock_cannot_be_issued(stock_env, stock_user):
    _posted_receipt(stock_env, Decimal("5"), user=stock_user, quality=QualityStatus.QUARANTINE)
    document = _issue(stock_env, Decimal("1"), user=stock_user, quality=QualityStatus.QUARANTINE)

    with pytest.raises(StateConflict) as excinfo:
        stock.post_document(document, user=stock_user)

    assert excinfo.value.code == "QUALITY_NOT_RELEASED"
    document.refresh_from_db()
    assert document.status == DocumentStatus.DRAFT
    document.refresh_from_db()
    assert _balance(stock_env, quality_status=QualityStatus.QUARANTINE).on_hand == Decimal("5.000000")


def test_rejected_stock_cannot_be_issued(stock_env, stock_user):
    _posted_receipt(stock_env, Decimal("5"), user=stock_user, quality=QualityStatus.REJECTED)
    document = _issue(stock_env, Decimal("1"), user=stock_user, quality=QualityStatus.REJECTED)

    with pytest.raises(StateConflict) as excinfo:
        stock.post_document(document, user=stock_user)
    assert excinfo.value.code == "QUALITY_NOT_RELEASED"


def test_release_quality_moves_stock_between_statuses(stock_env, stock_user):
    _posted_receipt(stock_env, Decimal("5"), user=stock_user, quality=QualityStatus.QUARANTINE)

    release = stock.release_quality(
        user=stock_user,
        company=stock_env["company"].id,
        warehouse=stock_env["warehouse_a"],
        material=stock_env["material"],
        quantity=Decimal("5"),
        location=stock_env["location_a"],
        from_status=QualityStatus.QUARANTINE,
        to_status=QualityStatus.QUALIFIED,
        reason="来料检验合格",
    )

    assert release.document_type == DocumentType.QUALITY
    assert release.status == DocumentStatus.POSTED
    assert release.document_no.startswith("ST")
    assert _balance(stock_env, quality_status=QualityStatus.QUARANTINE).on_hand == Decimal("0.000000")
    assert _balance(stock_env, quality_status=QualityStatus.QUALIFIED).on_hand == Decimal("5.000000")

    # 放行后可正常出库
    stock.post_document(_issue(stock_env, Decimal("2"), user=stock_user), user=stock_user)
    assert _balance(stock_env, quality_status=QualityStatus.QUALIFIED).on_hand == Decimal("3.000000")


# ---------------------------------------------------------------------------
# 移库与冲销
# ---------------------------------------------------------------------------


def test_move_conserves_quantity(stock_env, stock_user):
    _posted_receipt(stock_env, Decimal("10"), user=stock_user)
    document = _create(
        stock_env,
        DocumentType.MOVE,
        [_line(stock_env, Decimal("4"), target_location=stock_env["location_a2"])],
        user=stock_user,
    )
    posted = stock.post_document(document, user=stock_user)

    assert _balance(stock_env, location=stock_env["location_a"]).on_hand == Decimal("6.000000")
    assert _balance(stock_env, location=stock_env["location_a2"]).on_hand == Decimal("4.000000")
    total = sum(
        InventoryBalance.objects.filter(material=stock_env["material"]).values_list(
            "on_hand", flat=True
        ),
        Decimal("0"),
    )
    assert total == Decimal("10.000000")

    types = list(
        InventoryTransaction.objects.filter(document=posted)
        .order_by("id")
        .values_list("transaction_type", flat=True)
    )
    assert types == [TransactionType.MOVE_OUT, TransactionType.MOVE_IN]


def test_move_to_other_warehouse_is_rejected(stock_env, stock_user):
    _posted_receipt(stock_env, Decimal("5"), user=stock_user)
    document = _create(
        stock_env,
        DocumentType.MOVE,
        [_line(stock_env, Decimal("1"), target_location=stock_env["location_b"])],
        user=stock_user,
    )
    with pytest.raises(ValidationFailed) as excinfo:
        stock.post_document(document, user=stock_user)
    assert excinfo.value.code == "LOCATION_WAREHOUSE_MISMATCH"


def test_reversal_blocked_when_stock_consumed(stock_env, stock_user):
    receipt = _posted_receipt(stock_env, Decimal("10"), user=stock_user)
    stock.post_document(_issue(stock_env, Decimal("8"), user=stock_user), user=stock_user)

    with pytest.raises(StateConflict) as excinfo:
        stock.reverse_document(receipt, user=stock_user, reason="录错数量")

    assert excinfo.value.code == "REVERSAL_BLOCKED"
    assert excinfo.value.details["available"] == "2.000000"
    receipt.refresh_from_db()
    assert receipt.status == DocumentStatus.POSTED
    assert _balance(stock_env).on_hand == Decimal("2.000000")


def test_reversal_succeeds_after_stock_returned(stock_env, stock_user):
    receipt = _posted_receipt(stock_env, Decimal("10"), user=stock_user)
    issue = stock.post_document(_issue(stock_env, Decimal("8"), user=stock_user), user=stock_user)
    stock.reverse_document(issue, user=stock_user, reason="客户取消，货退回")

    reversed_receipt = stock.reverse_document(receipt, user=stock_user, reason="录错数量")
    assert reversed_receipt.status == DocumentStatus.REVERSED
    assert reversed_receipt.reverse_reason == "录错数量"
    assert _balance(stock_env).on_hand == Decimal("0.000000")
    assert InventoryTransaction.objects.filter(document=receipt).count() == 2


def test_reversal_requires_reason(stock_env, stock_user):
    receipt = _posted_receipt(stock_env, Decimal("1"), user=stock_user)
    with pytest.raises(ValidationFailed) as excinfo:
        stock.reverse_document(receipt, user=stock_user, reason="   ")
    assert excinfo.value.code == "REVERSE_REASON_REQUIRED"


def test_double_reversal_is_rejected(stock_env, stock_user):
    receipt = _posted_receipt(stock_env, Decimal("1"), user=stock_user)
    stock.reverse_document(receipt, user=stock_user, reason="第一次")
    with pytest.raises(StateConflict) as excinfo:
        stock.reverse_document(receipt, user=stock_user, reason="第二次")
    assert excinfo.value.code == "ALREADY_REVERSED"
# ---------------------------------------------------------------------------
# 幂等与重试
# ---------------------------------------------------------------------------


def test_same_idempotency_key_posts_once(stock_env, stock_user):
    document = _receipt(stock_env, Decimal("4"), user=stock_user)

    first = stock.post_document(document, user=stock_user, idempotency_key="KEY-INV-1")
    replay = stock.post_document(document, user=stock_user, idempotency_key="KEY-INV-1")

    assert first.pk == replay.pk
    assert replay.status == DocumentStatus.POSTED
    assert InventoryTransaction.objects.filter(document=document).count() == 1
    assert _balance(stock_env).on_hand == Decimal("4.000000")


def test_same_idempotency_key_on_other_document_is_rejected(stock_env, stock_user):
    first = _receipt(stock_env, Decimal("4"), user=stock_user)
    second = _receipt(stock_env, Decimal("4"), user=stock_user)
    stock.post_document(first, user=stock_user, idempotency_key="KEY-INV-2")

    with pytest.raises(StateConflict) as excinfo:
        stock.post_document(second, user=stock_user, idempotency_key="KEY-INV-2")

    assert excinfo.value.code == "IDEMPOTENCY_KEY_CONFLICT"
    second.refresh_from_db()
    assert second.status == DocumentStatus.DRAFT


def test_deadlock_retry_does_not_duplicate_ledger(stock_env, stock_user, monkeypatch):
    """注入一次死锁错误：必须重跑整个事务，且余额与流水只落一次。"""
    calls = {"count": 0}
    real_publish = stock.publish_event

    def flaky_publish(*args, **kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            raise OperationalError(1213, "Deadlock found when trying to get lock")
        return real_publish(*args, **kwargs)

    monkeypatch.setattr(stock, "publish_event", flaky_publish)

    document = _receipt(stock_env, Decimal("6"), user=stock_user)
    posted = stock.post_document(document, user=stock_user)

    assert calls["count"] == 2
    assert posted.status == DocumentStatus.POSTED
    assert InventoryTransaction.objects.filter(document=posted).count() == 1
    assert _balance(stock_env).on_hand == Decimal("6.000000")
    assert OutboxEvent.objects.filter(event_type="wms.document.posted").count() == 1


def test_non_retryable_error_is_not_retried(stock_env, stock_user, monkeypatch):
    calls = {"count": 0}

    def broken_publish(*args, **kwargs):
        calls["count"] += 1
        raise OperationalError(1045, "Access denied for user")

    monkeypatch.setattr(stock, "publish_event", broken_publish)

    document = _receipt(stock_env, Decimal("6"), user=stock_user)
    with pytest.raises(OperationalError):
        stock.post_document(document, user=stock_user)
    assert calls["count"] == 1
    # 整个事务已回滚：不留下余额行、流水，也不留下已过账状态
    assert InventoryBalance.objects.count() == 0
    assert InventoryTransaction.objects.count() == 0
    document.refresh_from_db()
    assert document.status == DocumentStatus.DRAFT


# ---------------------------------------------------------------------------
# 单据编号与草稿规则
# ---------------------------------------------------------------------------


def test_document_numbers_are_unique_and_allocated_on_create(stock_env, stock_user):
    first = _receipt(stock_env, Decimal("1"), user=stock_user)
    second = _receipt(stock_env, Decimal("1"), user=stock_user)

    assert first.document_no and second.document_no
    assert first.document_no != second.document_no
    assert InventoryDocument.objects.filter(
        company=stock_env["company"], document_no=first.document_no
    ).count() == 1


def test_posted_document_cannot_be_edited(stock_env, stock_user):
    posted = _posted_receipt(stock_env, Decimal("1"), user=stock_user)

    with pytest.raises(StateConflict) as excinfo:
        stock.update_draft_document(posted, user=stock_user, remark="改备注")

    assert excinfo.value.code == "STATE_CONFLICT"
    posted.refresh_from_db()
    assert posted.remark == ""


def test_draft_document_lines_can_be_replaced(stock_env, stock_user):
    document = _receipt(stock_env, Decimal("1"), user=stock_user)
    updated = stock.update_draft_document(
        document,
        user=stock_user,
        remark="调整数量",
        lines=[_line(stock_env, Decimal("7"))],
    )

    assert updated.remark == "调整数量"
    assert updated.lines.count() == 1
    posted = stock.post_document(updated, user=stock_user)
    assert InventoryTransaction.objects.filter(document=posted).count() == 1
    assert _balance(stock_env).on_hand == Decimal("7.000000")


def test_empty_document_is_rejected(stock_env, stock_user):
    with pytest.raises(ValidationFailed) as excinfo:
        _create(stock_env, DocumentType.RECEIPT, [], user=stock_user)
    assert excinfo.value.code == "EMPTY_DOCUMENT"


def test_zero_quantity_line_is_rejected(stock_env, stock_user):
    with pytest.raises(ValidationFailed) as excinfo:
        _receipt(stock_env, Decimal("0"), user=stock_user)
    assert excinfo.value.code == "INVALID_LINE_QUANTITY"
# ---------------------------------------------------------------------------
# 并发（真实连接 + 真实事务）
# ---------------------------------------------------------------------------


@pytest.fixture
def committed_data_cleanup():
    """`transaction=True` 用例会真实提交数据，结束后主动清库。

    不依赖测试框架的隐式 flush：出现异常中断的会话时，残留数据会让后续用例
    在「编码已存在」这类唯一约束上失败，排查成本很高。
    """
    yield
    call_command(
        "flush",
        verbosity=0,
        interactive=False,
        allow_cascade=True,
        inhibit_post_migrate=True,
    )


@pytest.mark.django_db(transaction=True)
def test_concurrent_balance_creation_yields_single_row(stock_env, stock_user, committed_data_cleanup):
    """必测 7：新库存余额行并发创建不重复。"""
    documents = [
        _receipt(stock_env, Decimal("1"), user=stock_user, batch_no="RACE")
        for _ in range(3)
    ]
    results, errors = _run_concurrently(
        [partial(stock.post_document, document, user=stock_user) for document in documents]
    )

    assert errors == [], errors
    assert len(results) == 3
    assert InventoryBalance.objects.filter(material=stock_env["material"]).count() == 1
    balance = _balance(stock_env)
    assert balance.on_hand == Decimal("3.000000")
    assert InventoryTransaction.objects.filter(material=stock_env["material"]).count() == 3


@pytest.mark.django_db(transaction=True)
def test_concurrent_issue_never_produces_negative_stock(
    stock_env, stock_user, committed_data_cleanup
):
    """必测 6：并发出库不产生负库存。"""
    _posted_receipt(stock_env, Decimal("8"), user=stock_user)
    documents = [_issue(stock_env, Decimal("3"), user=stock_user) for _ in range(4)]

    results, errors = _run_concurrently(
        [partial(stock.post_document, document, user=stock_user) for document in documents]
    )

    assert all(isinstance(error, InsufficientStock) for error in errors), errors
    assert len(results) == 2
    balance = _balance(stock_env)
    issued = Decimal("3") * len(results)
    assert balance.on_hand == Decimal("8.000000") - issued
    assert balance.on_hand >= Decimal("0")
    assert InventoryTransaction.objects.filter(transaction_type=TransactionType.ISSUE).count() == len(
        results
    )
    posted_count = InventoryDocument.objects.filter(
        pk__in=[document.pk for document in documents], status=DocumentStatus.POSTED
    ).count()
    assert posted_count == len(results)


@pytest.mark.django_db(transaction=True)
def test_concurrent_transfer_keeps_total(stock_env, stock_user, committed_data_cleanup):
    """必测 11：并发移库数量守恒。"""
    _posted_receipt(stock_env, Decimal("30"), user=stock_user)
    documents = [
        _create(
            stock_env,
            DocumentType.MOVE,
            [_line(stock_env, Decimal("5"), target_location=stock_env["location_a2"])],
            user=stock_user,
        )
        for _ in range(3)
    ]
    _, errors = _run_concurrently(
        [partial(stock.post_document, document, user=stock_user) for document in documents]
    )

    assert errors == [], errors
    total = sum(
        InventoryBalance.objects.filter(material=stock_env["material"]).values_list(
            "on_hand", flat=True
        ),
        Decimal("0"),
    )
    assert total == Decimal("30.000000")
    assert _balance(stock_env, location=stock_env["location_a"]).on_hand == Decimal("15.000000")
    assert _balance(stock_env, location=stock_env["location_a2"]).on_hand == Decimal("15.000000")
# ---------------------------------------------------------------------------
# 接口层：登录、操作权限、数据范围、幂等头
# ---------------------------------------------------------------------------


@pytest.fixture
def inventory_api_user(registry_permissions, stock_env):
    role = make_role(
        code="inv_api_role",
        permission_codes=INVENTORY_PERMISSIONS,
        data_scope_type=DataScopeType.WAREHOUSE,
        company=stock_env["company"],
        grants=[(ScopeDimension.WAREHOUSE, stock_env["warehouse_a"].pk)],
    )
    return make_user(username="inv_api", role=role, company=stock_env["company"])


def _create_payload(env, quantity="5.000000", *, warehouse=None, quality=QualityStatus.QUALIFIED,
                    document_type=DocumentType.RECEIPT, location=None):
    return {
        "document_type": document_type,
        "warehouse_id": (warehouse or env["warehouse_a"]).pk,
        "lines": [
            {
                "material_id": env["material"].id,
                "location_id": (location or env["location_a"]).pk,
                "batch_no": "",
                "roll_no": "",
                "quality_status": quality,
                "direction": "in",
                "quantity": quantity,
            }
        ],
    }


def test_inventory_endpoints_require_login(api_client):
    assert api_client.get(BALANCES_URL).status_code in {401, 403}
    assert api_client.get(TRANSACTIONS_URL).status_code in {401, 403}
    assert api_client.get(DOCUMENTS_URL).status_code in {401, 403}


def test_inventory_endpoints_require_permission(api_client, registry_permissions, company):
    role = make_role(code="inv_only_material", permission_codes=["masterdata.material.view"])
    user = make_user(username="inv_no_perm", role=role, company=company)
    api_client.force_authenticate(user=user)

    response = api_client.get(BALANCES_URL)
    assert response.status_code == 403
    assert response.json()["code"] == "PERMISSION_DENIED"


def test_document_lifecycle_over_api(api_client, stock_env, inventory_api_user):
    api_client.force_authenticate(user=inventory_api_user)

    created = api_client.post(
        DOCUMENTS_URL, _create_payload(stock_env), format="json"
    )
    assert created.status_code == 201, created.content
    document_id = created.json()["id"]
    assert created.json()["status"] == DocumentStatus.DRAFT
    assert created.json()["document_no"].startswith("GR")

    posted = api_client.post(f"{DOCUMENTS_URL}{document_id}/post/", {}, format="json")
    assert posted.status_code == 200, posted.content
    assert posted.json()["status"] == DocumentStatus.POSTED

    balances = api_client.get(BALANCES_URL)
    assert balances.status_code == 200
    assert balances.json()["count"] == 1
    row = balances.json()["results"][0]
    assert row["on_hand"] == "5.000000"
    assert row["available"] == "5.000000"
    assert row["material_id"] == stock_env["material"].id

    ledger = api_client.get(TRANSACTIONS_URL)
    assert ledger.json()["count"] == 1
    assert ledger.json()["results"][0]["document_id"] == document_id
    assert ledger.json()["results"][0]["quantity"] == "5.000000"

    reversed_response = api_client.post(
        f"{DOCUMENTS_URL}{document_id}/reverse/", {"reason": "接口联调冲销"}, format="json"
    )
    assert reversed_response.status_code == 200, reversed_response.content
    assert reversed_response.json()["status"] == DocumentStatus.REVERSED
    assert api_client.get(BALANCES_URL).json()["results"][0]["on_hand"] == "0.000000"


def test_api_idempotency_key_deducts_once(api_client, stock_env, inventory_api_user):
    api_client.force_authenticate(user=inventory_api_user)
    document_id = api_client.post(DOCUMENTS_URL, _create_payload(stock_env), format="json").json()["id"]
    url = f"{DOCUMENTS_URL}{document_id}/post/"

    first = api_client.post(url, {}, format="json", HTTP_IDEMPOTENCY_KEY="API-KEY-1")
    second = api_client.post(url, {}, format="json", HTTP_IDEMPOTENCY_KEY="API-KEY-1")

    assert first.status_code == 200
    assert second.status_code == 200
    assert second["Idempotency-Replayed"] == "true"
    assert InventoryTransaction.objects.filter(document_id=document_id).count() == 1
    assert api_client.get(BALANCES_URL).json()["results"][0]["on_hand"] == "5.000000"


def test_api_enforces_warehouse_scope(api_client, stock_env, inventory_api_user):
    """接口传入的 warehouse_id 不能绕过数据范围，列表也必须按范围收敛。"""
    superuser = make_user(username="inv_seed", company=stock_env["company"], is_superuser=True)
    stock.post_document(
        _receipt(
            stock_env,
            Decimal("7"),
            user=superuser,
            warehouse=stock_env["warehouse_b"],
            location=stock_env["location_b"],
        ),
        user=superuser,
    )
    api_client.force_authenticate(user=inventory_api_user)

    denied = api_client.post(
        DOCUMENTS_URL,
        _create_payload(stock_env, warehouse=stock_env["warehouse_b"]),
        format="json",
    )
    assert denied.status_code == 403
    assert denied.json()["code"] == "OUT_OF_DATA_SCOPE"

    allowed = api_client.post(
        DOCUMENTS_URL, _create_payload(stock_env, quantity="3.000000"), format="json"
    )
    assert allowed.status_code == 201, allowed.content
    document_id = allowed.json()["id"]
    assert api_client.post(f"{DOCUMENTS_URL}{document_id}/post/", {}, format="json").status_code == 200

    balances = api_client.get(BALANCES_URL).json()
    assert balances["count"] == 1
    assert balances["results"][0]["warehouse_id"] == stock_env["warehouse_a"].pk
    assert balances["results"][0]["on_hand"] == "3.000000"

    ledger = api_client.get(TRANSACTIONS_URL).json()
    assert ledger["count"] == 1
    assert ledger["results"][0]["warehouse_id"] == stock_env["warehouse_a"].pk


def test_inventory_read_apis_reject_writes(api_client, stock_env, inventory_api_user):
    api_client.force_authenticate(user=inventory_api_user)
    assert api_client.post(TRANSACTIONS_URL, {}, format="json").status_code == 405
    assert api_client.patch(f"{TRANSACTIONS_URL}1/", {}, format="json").status_code == 405
    assert api_client.delete(f"{TRANSACTIONS_URL}1/").status_code == 405
    assert api_client.post(BALANCES_URL, {}, format="json").status_code == 405


def test_api_release_quality(api_client, stock_env, inventory_api_user):
    api_client.force_authenticate(user=inventory_api_user)
    created = api_client.post(
        DOCUMENTS_URL,
        _create_payload(stock_env, quality=QualityStatus.QUARANTINE),
        format="json",
    )
    document_id = created.json()["id"]
    api_client.post(f"{DOCUMENTS_URL}{document_id}/post/", {}, format="json")

    response = api_client.post(
        f"{DOCUMENTS_URL}release-quality/",
        {
            "company_id": stock_env["company"].id,
            "warehouse_id": stock_env["warehouse_a"].pk,
            "material_id": stock_env["material"].id,
            "location_id": stock_env["location_a"].pk,
            "quantity": "5.000000",
            "reason": "来料检验合格",
        },
        format="json",
    )
    assert response.status_code == 201, response.content
    assert response.json()["document_type"] == DocumentType.QUALITY
    assert response.json()["status"] == DocumentStatus.POSTED

    quarantined = InventoryBalance.objects.get(
        material=stock_env["material"], quality_status=QualityStatus.QUARANTINE
    )
    qualified = InventoryBalance.objects.get(
        material=stock_env["material"], quality_status=QualityStatus.QUALIFIED
    )
    assert quarantined.on_hand == Decimal("0.000000")
    assert qualified.on_hand == Decimal("5.000000")

def test_meta_exposes_inventory_enums(api_client, registry_permissions, company):
    user = make_user(username="inv_meta", company=company, is_superuser=True)
    api_client.force_authenticate(user=user)
    response = api_client.get("/api/v1/meta/")
    assert response.status_code == 200, response.content
    body = response.json()
    for key in (
        "quality_statuses",
        "inventory_document_types",
        "inventory_document_statuses",
        "inventory_transaction_types",
        "inventory_directions",
    ):
        assert body.get(key), f"meta 缺少枚举 {key}"
    assert {item["value"] for item in body["quality_statuses"]} == {
        "quarantine",
        "qualified",
        "rejected",
    }
    assert {item["value"] for item in body["inventory_document_types"]} >= {
        "receipt",
        "issue",
        "move",
        "adjustment",
        "quality",
    }
