"""统一库存服务。

任务书 10.8 与 `docs/inventory-rules.md` 规定：**所有库存变更必须经由本模块**，
采购、销售、生产、备件等模块只调用这里，不得直接写余额表或流水表。

实现要点（对应任务书 5.6 的事务与并发要求）：

1. 先检查操作权限（`require_codes`）；
2. 按**固定顺序**（维度键升序）对涉及的余额行加锁，降低死锁风险；
3. 尚不存在的余额行不能认为 `select_for_update()` 已提供锁保护——
   采用「唯一约束 + 捕获 `IntegrityError` 后重新加锁」的并发安全创建；
4. 在锁内**重新校验**单据状态与可用数量；
5. 同一事务内更新**单据 + 余额 + 流水**，并写审计与 Outbox；
6. 幂等键与业务结果**同事务提交**，重复过账只产生一次库存变化；
7. 死锁/锁等待超时**有限重试**，重试必须重跑完整事务且保持幂等。
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from django.db import IntegrityError, OperationalError, transaction
from django.utils import timezone

from apps.core.exceptions import (
    InsufficientStock,
    ObjectNotFound,
    StateConflict,
    ValidationFailed,
)
from apps.core.models import AuditAction
from apps.core.permissions import require_codes
from apps.core.services import generate_code, publish_event, record_audit
from apps.masterdata.models import Material
from apps.wms.models import (
    Direction,
    DocumentStatus,
    DocumentType,
    InventoryBalance,
    InventoryDocument,
    InventoryDocumentLine,
    InventoryTransaction,
    Location,
    QualityStatus,
    TransactionType,
    Warehouse,
    build_dimension_key,
)

logger = logging.getLogger("yishang.inventory")

ZERO = Decimal("0")
MAX_LOCK_RETRIES = 3
# MySQL 死锁与锁等待超时的错误码
RETRYABLE_MYSQL_ERRORS = {1213, 1205}

# 各单据类型对应的流水类型（转出/转入）
OUTBOUND_TYPES = {DocumentType.ISSUE, DocumentType.MOVE, DocumentType.QUALITY}
# 只有「领用/销售出库」要求库存必须是合格状态；移库与质量转换不改变可用性判定
TYPES_REQUIRING_QUALIFIED = {DocumentType.ISSUE}

CODE_RULE_BY_DOCUMENT_TYPE = {
    DocumentType.RECEIPT: "GR",
    DocumentType.ISSUE: "ST",
    DocumentType.MOVE: "TR",
    DocumentType.ADJUSTMENT: "ST",
    DocumentType.QUALITY: "ST",
}


@dataclass(frozen=True)
class Dimension:
    """库存维度（可读形式）。同时承载余额行与流水行的字段来源。"""

    company_id: int
    material_id: int
    warehouse_id: int
    location_id: int | None
    batch_no: str | None
    roll_no: str | None
    quality_status: str

    @property
    def key(self) -> str:
        return build_dimension_key(
            company_id=self.company_id,
            material_id=self.material_id,
            warehouse_id=self.warehouse_id,
            location_id=self.location_id,
            batch_no=self.batch_no,
            roll_no=self.roll_no,
            quality_status=self.quality_status,
        )

    def as_balance_fields(self) -> dict[str, Any]:
        return {
            "company_id": self.company_id,
            "material_id": self.material_id,
            "warehouse_id": self.warehouse_id,
            "location_id": self.location_id,
            "batch_no": self.batch_no,
            "roll_no": self.roll_no,
            "quality_status": self.quality_status,
            "dimension_key": self.key,
        }

    def describe(self) -> dict[str, Any]:
        return {
            "material_id": self.material_id,
            "warehouse_id": self.warehouse_id,
            "location_id": self.location_id,
            "batch_no": self.batch_no,
            "roll_no": self.roll_no,
            "quality_status": self.quality_status,
        }

@dataclass(frozen=True)
class Movement:
    """单据行展开后的**单条**库存移动：一个维度上的一次数量变化。

    移库、质量转换等一行会产生两条 Movement（转出 + 转入），因此
    「单据行 → 库存动作」不能一一对应，必须显式展开后再统一加锁与落账。
    """

    dimension: Dimension
    delta: Decimal
    transaction_type: str
    line: InventoryDocumentLine
    role: str
    dedup_key: str
    reason: str = ""


# 冲销时使用的反向流水类型
REVERSAL_TYPE = {
    TransactionType.RECEIPT: TransactionType.ISSUE,
    TransactionType.ISSUE: TransactionType.RECEIPT,
    TransactionType.MOVE_OUT: TransactionType.MOVE_IN,
    TransactionType.MOVE_IN: TransactionType.MOVE_OUT,
    TransactionType.ADJUST_UP: TransactionType.ADJUST_DOWN,
    TransactionType.ADJUST_DOWN: TransactionType.ADJUST_UP,
    TransactionType.QUALITY_OUT: TransactionType.QUALITY_IN,
    TransactionType.QUALITY_IN: TransactionType.QUALITY_OUT,
}


def _mysql_error_code(exc: BaseException) -> int | None:
    """取出 MySQL 驱动错误码（PyMySQL 与 mysqlclient 都把错误码放在 args[0]）。"""
    args = getattr(exc, "args", ())
    if args and isinstance(args[0], int):
        return args[0]
    cause = exc.__cause__ or exc.__context__
    if cause is not None:
        cause_args = getattr(cause, "args", ())
        if cause_args and isinstance(cause_args[0], int):
            return cause_args[0]
    return None


def _is_retryable(exc: OperationalError) -> bool:
    return _mysql_error_code(exc) in RETRYABLE_MYSQL_ERRORS


def allocate_document_no(document_type: str, *, on_date: date | None = None) -> str:
    """按单据类型取单据编号（编码规则见 apps/identity/... bootstrap_system.CODE_RULES）。"""
    rule_code = CODE_RULE_BY_DOCUMENT_TYPE.get(document_type)
    if rule_code is None:
        raise ValidationFailed(f"未知的库存单据类型：{document_type}", code="UNKNOWN_DOCUMENT_TYPE")
    return generate_code(rule_code, on_date=on_date)


def _plan_movements(
    document: InventoryDocument,
    lines: list[InventoryDocumentLine],
    *,
    suffix: str = "",
) -> list[Movement]:
    """把单据行展开为库存动作。这是「单据 → 库存」的唯一翻译层。"""
    movements: list[Movement] = []
    company_id = document.company_id
    warehouse_id = document.warehouse_id

    def build(line: InventoryDocumentLine, location_id: int | None, quality_status: str) -> Dimension:
        return Dimension(
            company_id=company_id,
            material_id=line.material_id,
            warehouse_id=warehouse_id,
            location_id=location_id,
            batch_no=line.batch_no,
            roll_no=line.roll_no,
            quality_status=quality_status,
        )

    for line in lines:
        dedup_prefix = f"{document.pk}:{line.pk}:{line.line_no}"
        quantity = line.quantity or ZERO
        if quantity <= ZERO:
            raise ValidationFailed(
                f"第 {line.line_no} 行数量必须大于 0。", code="INVALID_LINE_QUANTITY"
            )
        if document.document_type == DocumentType.RECEIPT:
            movements.append(
                Movement(
                    build(line, line.location_id, line.quality_status),
                    quantity,
                    TransactionType.RECEIPT,
                    line,
                    "in",
                    f"{dedup_prefix}:in{suffix}",
                )
            )
        elif document.document_type == DocumentType.ISSUE:
            movements.append(
                Movement(
                    build(line, line.location_id, line.quality_status),
                    -quantity,
                    TransactionType.ISSUE,
                    line,
                    "out",
                    f"{dedup_prefix}:out{suffix}",
                )
            )
        elif document.document_type == DocumentType.MOVE:
            if line.target_location_id is None:
                raise ValidationFailed(
                    f"第 {line.line_no} 行移库必须指定目标储位。", code="TARGET_LOCATION_REQUIRED"
                )
            if line.target_location_id == line.location_id:
                raise ValidationFailed(
                    f"第 {line.line_no} 行转出储位与转入储位不能相同。",
                    code="SAME_LOCATION_MOVE",
                )
            movements.append(
                Movement(
                    build(line, line.location_id, line.quality_status),
                    -quantity,
                    TransactionType.MOVE_OUT,
                    line,
                    "out",
                    f"{dedup_prefix}:out{suffix}",
                )
            )
            movements.append(
                Movement(
                    build(line, line.target_location_id, line.quality_status),
                    quantity,
                    TransactionType.MOVE_IN,
                    line,
                    "in",
                    f"{dedup_prefix}:in{suffix}",
                )
            )
        elif document.document_type == DocumentType.ADJUSTMENT:
            if line.direction == Direction.OUT:
                movements.append(
                    Movement(
                        build(line, line.location_id, line.quality_status),
                        -quantity,
                        TransactionType.ADJUST_DOWN,
                        line,
                        "out",
                        f"{dedup_prefix}:out{suffix}",
                        reason=line.remark,
                    )
                )
            else:
                movements.append(
                    Movement(
                        build(line, line.location_id, line.quality_status),
                        quantity,
                        TransactionType.ADJUST_UP,
                        line,
                        "in",
                        f"{dedup_prefix}:in{suffix}",
                        reason=line.remark,
                    )
                )
        elif document.document_type == DocumentType.QUALITY:
            target_quality = line.target_quality_status
            if not target_quality:
                raise ValidationFailed(
                    f"第 {line.line_no} 行质量转换必须指定目标质量状态。",
                    code="TARGET_QUALITY_REQUIRED",
                )
            if target_quality == line.quality_status:
                raise ValidationFailed(
                    f"第 {line.line_no} 行目标质量状态与当前状态相同。",
                    code="SAME_QUALITY_STATUS",
                )
            movements.append(
                Movement(
                    build(line, line.location_id, line.quality_status),
                    -quantity,
                    TransactionType.QUALITY_OUT,
                    line,
                    "out",
                    f"{dedup_prefix}:quality-out{suffix}",
                    reason=line.remark,
                )
            )
            movements.append(
                Movement(
                    build(line, line.target_location_id or line.location_id, target_quality),
                    quantity,
                    TransactionType.QUALITY_IN,
                    line,
                    "in",
                    f"{dedup_prefix}:quality-in{suffix}",
                    reason=line.remark,
                )
            )
        else:
            raise ValidationFailed(
                f"不支持的库存单据类型：{document.document_type}", code="UNKNOWN_DOCUMENT_TYPE"
            )
    return movements

def _assert_locations_in_warehouse(document: InventoryDocument, lines: list[InventoryDocumentLine]) -> None:
    """储位必须属于单据头上的仓库，否则跨仓库改库存可以绕过仓库范围权限。"""
    location_ids: set[int] = set()
    for line in lines:
        for value in (line.location_id, line.target_location_id):
            if value:
                location_ids.add(value)
    if not location_ids:
        return
    rows = Location.objects.filter(pk__in=location_ids).values_list("id", "zone__warehouse_id")
    warehouse_by_location = {row[0]: row[1] for row in rows}
    for location_id in sorted(location_ids):
        if location_id not in warehouse_by_location:
            raise ObjectNotFound("储位不存在。", details={"location_id": location_id})
        if warehouse_by_location[location_id] != document.warehouse_id:
            raise ValidationFailed(
                "储位与单据仓库不一致；跨仓库移库属于调拨业务，首版请使用调拨单流程。",
                code="LOCATION_WAREHOUSE_MISMATCH",
                details={"location_id": location_id, "warehouse_id": document.warehouse_id},
            )


def _assert_quality_allowed(
    document: InventoryDocument, lines: list[InventoryDocumentLine]
) -> None:
    """出库（领用/销售发货）只能动用合格库存；待检与不合格库存必须先走质量放行。"""
    if document.document_type not in TYPES_REQUIRING_QUALIFIED:
        return
    for line in lines:
        if line.quality_status != QualityStatus.QUALIFIED:
            raise StateConflict(
                f"第 {line.line_no} 行为非合格库存（{line.quality_status}），不能出库；请先完成质量放行或转不合格品仓。",
                code="QUALITY_NOT_RELEASED",
                details={"line_no": line.line_no, "quality_status": line.quality_status},
            )


def _lock_balances(movements: list[Movement]) -> dict[str, InventoryBalance]:
    """按维度键升序加锁。固定顺序可显著降低并发死锁概率（任务书 5.6）。"""
    dimensions: dict[str, Dimension] = {}
    for movement in movements:
        dimensions.setdefault(movement.dimension.key, movement.dimension)

    balances: dict[str, InventoryBalance] = {}
    for key in sorted(dimensions):
        dimension = dimensions[key]
        balance = InventoryBalance.objects.select_for_update().filter(dimension_key=key).first()
        if balance is None:
            # 余额行不存在时 select_for_update() 不提供保护：先并发安全创建，再重新加锁。
            try:
                with transaction.atomic():
                    InventoryBalance.objects.create(**dimension.as_balance_fields())
                    logger.info("库存余额行创建 dimension_key=%s", key)
            except IntegrityError:
                pass  # 其他事务抢先创建，下面重新取锁即可
            balance = InventoryBalance.objects.select_for_update().filter(dimension_key=key).first()
            if balance is None:
                raise StateConflict(
                    "库存余额行并发创建失败，请重试。", code="BALANCE_CREATE_RACE"
                )
        balances[key] = balance
    return balances


def _assert_available(movements: list[Movement], balances: dict[str, InventoryBalance]) -> None:
    """在锁内重新校验可用量（锁外校验不作为依据）。"""
    for movement in movements:
        if movement.delta >= ZERO:
            continue
        balance = balances[movement.dimension.key]
        available = balance.available
        required = -movement.delta
        if available < required:
            warehouse_allows_negative = getattr(balance.warehouse, "allow_negative_stock", False)
            raise InsufficientStock(
                "可用库存不足，不能出库。",
                details={
                    **movement.dimension.describe(),
                    "required": str(required),
                    "available": str(available),
                    "warehouse_allows_negative": bool(warehouse_allows_negative),
                    "hint": "数据库非负约束始终生效；即使仓库开启允许负库存，也需先补做入库或库存调整单。",
                },
            )


def _write_movements(
    document: InventoryDocument,
    movements: list[Movement],
    balances: dict[str, InventoryBalance],
    *,
    user: Any,
    reason: str = "",
) -> None:
    """同一事务内更新【余额 + 流水】。流水只追加，重复执行由 dedup_key 唯一约束兜底。"""
    operator = user if getattr(user, "pk", None) else None
    for movement in movements:
        balance = balances[movement.dimension.key]
        before = balance.on_hand or ZERO
        after = before + movement.delta
        balance.on_hand = after
        balance.save()
        InventoryTransaction.objects.create(
            company_id=balance.company_id,
            document=document,
            document_line=movement.line,
            transaction_type=movement.transaction_type,
            material_id=movement.dimension.material_id,
            warehouse_id=movement.dimension.warehouse_id,
            location_id=movement.dimension.location_id,
            batch_no=movement.dimension.batch_no,
            roll_no=movement.dimension.roll_no,
            quality_status=movement.dimension.quality_status,
            dimension_key=movement.dimension.key,
            quantity=movement.delta,
            on_hand_before=before,
            on_hand_after=after,
            frozen_after=balance.frozen or ZERO,
            reserved_after=balance.reserved or ZERO,
            reason=(movement.reason or reason or "")[:255],
            dedup_key=movement.dedup_key,
            operator=operator,
        )
def _record_document_audit(
    document: InventoryDocument,
    *,
    user: Any,
    action: str,
    changes: dict[str, Any],
    reason: str = "",
) -> None:
    record_audit(
        action=action,
        instance=document,
        changes=changes,
        reason=reason,
        object_repr=document.document_no or f"#{document.pk}",
        company=document.company,
        actor=user,
    )


def post_document(
    document: InventoryDocument,
    *,
    user: Any,
    idempotency_key: str | None = None,
    reason: str = "",
) -> InventoryDocument:
    """库存单据过账：唯一的库存变动入口。

    幂等语义（任务书 7.2）：
    * 单据已过账且 `idempotency_key` 与库中一致 → 直接返回原单据，不重复扣减；
    * 同一幂等键被**其他**单据占用 → 拒绝，避免「同键不同内容」被静默接受。
    """
    if getattr(document, "pk", None) is None:
        raise ValidationFailed("单据必须先保存后才能过账。", code="DOCUMENT_NOT_SAVED")
    document_id = int(document.pk)

    for attempt in range(1, MAX_LOCK_RETRIES + 1):
        try:
            with transaction.atomic():
                return _post_locked(
                    document_id=document_id,
                    user=user,
                    idempotency_key=idempotency_key,
                    reason=reason,
                    attempt=attempt,
                )
        except OperationalError as exc:
            if not _is_retryable(exc) or attempt >= MAX_LOCK_RETRIES:
                raise
            logger.warning(
                "库存过账遇到可重试的数据库并发错误（第 %s/%s 次，错误码 %s），将重跑完整事务。",
                attempt,
                MAX_LOCK_RETRIES,
                _mysql_error_code(exc),
            )
    raise StateConflict("库存过账重试次数已用尽。", code="LOCK_RETRY_EXHAUSTED")


def _post_locked(
    *,
    document_id: int,
    user: Any,
    idempotency_key: str | None,
    reason: str,
    attempt: int,
) -> InventoryDocument:
    require_codes(user, "wms.document.post")
    document = (
        InventoryDocument.objects.select_for_update()
        .select_related("company", "warehouse")
        .filter(pk=document_id)
        .first()
    )
    if document is None:
        raise ObjectNotFound("库存单据不存在。", details={"document_id": document_id})

    # 锁内重新校验状态，不能沿用调用方传入的对象快照
    if document.status == DocumentStatus.POSTED:
        if idempotency_key and document.idempotency_key == idempotency_key:
            logger.info("库存过账幂等重放 document=%s", document.document_no)
            return document
        raise StateConflict(
            "单据已过账，不能重复过账。",
            details={"document_no": document.document_no, "status": document.status},
        )
    if document.status != DocumentStatus.DRAFT:
        raise StateConflict(
            "只有草稿状态的单据可以过账。",
            details={"document_no": document.document_no, "status": document.status},
        )
    if idempotency_key:
        conflict_no = (
            InventoryDocument.objects.filter(idempotency_key=idempotency_key)
            .exclude(pk=document.pk)
            .values_list("document_no", flat=True)
            .first()
        )
        if conflict_no is not None:
            raise StateConflict(
                "该过账幂等键已被其他单据使用。",
                code="IDEMPOTENCY_KEY_CONFLICT",
                details={"idempotency_key": idempotency_key, "document_no": conflict_no},
            )

    lines = list(
        document.lines.select_related("material", "location", "target_location").order_by(
            "line_no", "id"
        )
    )
    if not lines:
        raise ValidationFailed(
            "单据没有明细行，不能过账。", details={"document_no": document.document_no}
        )
    _assert_locations_in_warehouse(document, lines)
    _assert_quality_allowed(document, lines)

    movements = _plan_movements(document, lines)
    balances = _lock_balances(movements)
    _assert_available(movements, balances)
    _write_movements(document, movements, balances, user=user, reason=reason)

    before_status = document.status
    if not document.document_no:
        document.document_no = allocate_document_no(document.document_type)
    document.status = DocumentStatus.POSTED
    document.posted_at = timezone.now()
    document.posted_by = user if getattr(user, "pk", None) else None
    if idempotency_key:
        document.idempotency_key = idempotency_key
    document.save()

    _record_document_audit(
        document,
        user=user,
        action=AuditAction.POST,
        changes={
            "status": {"before": before_status, "after": document.status},
            "document_no": {"before": "", "after": document.document_no},
            "line_count": {"before": 0, "after": len(lines)},
        },
        reason=reason,
    )
    publish_event(
        event_type="wms.document.posted",
        aggregate_type="wms.InventoryDocument",
        aggregate_id=document.pk,
        payload={
            "document_no": document.document_no,
            "document_type": document.document_type,
            "warehouse_id": document.warehouse_id,
            "line_count": len(lines),
            "biz_type": document.biz_type,
            "biz_id": document.biz_id,
        },
        dedup_key=f"wms.document.posted:{document.pk}",
    )
    logger.info(
        "库存过账完成 document=%s type=%s lines=%s attempts=%s",
        document.document_no,
        document.document_type,
        len(lines),
        attempt,
    )
    return document
def reverse_document(
    document: InventoryDocument,
    *,
    user: Any,
    reason: str,
) -> InventoryDocument:
    """冲销已过账单据：写反向补偿流水，并校验下游是否已消耗。

    `docs/inventory-rules.md` 四.7：若原单据增加的库存已被下游消耗（可用量小于原数量），
    **拒绝**冲销并引导走退货/更正流程，不做「强行反冲」。
    """
    if getattr(document, "pk", None) is None:
        raise ValidationFailed("单据不存在，无法冲销。", code="DOCUMENT_NOT_SAVED")
    if not str(reason or "").strip():
        raise ValidationFailed("冲销必须填写原因。", code="REVERSE_REASON_REQUIRED")
    document_id = int(document.pk)

    for attempt in range(1, MAX_LOCK_RETRIES + 1):
        try:
            with transaction.atomic():
                return _reverse_locked(document_id=document_id, user=user, reason=reason)
        except OperationalError as exc:
            if not _is_retryable(exc) or attempt >= MAX_LOCK_RETRIES:
                raise
            logger.warning(
                "库存冲销遇到可重试的数据库并发错误（第 %s/%s 次，错误码 %s），将重跑完整事务。",
                attempt,
                MAX_LOCK_RETRIES,
                _mysql_error_code(exc),
            )
    raise StateConflict("库存冲销重试次数已用尽。", code="LOCK_RETRY_EXHAUSTED")


def _reverse_locked(*, document_id: int, user: Any, reason: str) -> InventoryDocument:
    require_codes(user, "wms.document.reverse")
    document = (
        InventoryDocument.objects.select_for_update()
        .select_related("company", "warehouse")
        .filter(pk=document_id)
        .first()
    )
    if document is None:
        raise ObjectNotFound("库存单据不存在。", details={"document_id": document_id})
    if document.status == DocumentStatus.REVERSED:
        raise StateConflict(
            "单据已冲销，不能重复冲销。",
            code="ALREADY_REVERSED",
            details={"document_no": document.document_no},
        )
    if document.status != DocumentStatus.POSTED:
        raise StateConflict(
            "只有已过账的单据可以冲销。",
            details={"document_no": document.document_no, "status": document.status},
        )

    lines = list(
        document.lines.select_related("material", "location", "target_location").order_by(
            "line_no", "id"
        )
    )
    if not lines:
        raise ValidationFailed("单据没有明细行，无法冲销。", details={"document_no": document.document_no})

    movements = [
        Movement(
            dimension=movement.dimension,
            delta=-movement.delta,
            transaction_type=REVERSAL_TYPE[movement.transaction_type],
            line=movement.line,
            role=movement.role,
            dedup_key=f"{movement.dedup_key}:reversal",
            reason=reason,
        )
        for movement in _plan_movements(document, lines)
    ]
    balances = _lock_balances(movements)
    _assert_reversible(movements, balances)
    _write_movements(document, movements, balances, user=user, reason=reason)

    document.status = DocumentStatus.REVERSED
    document.reversed_at = timezone.now()
    document.reversed_by = user if getattr(user, "pk", None) else None
    document.reverse_reason = reason
    document.save()

    _record_document_audit(
        document,
        user=user,
        action=AuditAction.REVERSE,
        changes={
            "status": {"before": DocumentStatus.POSTED, "after": document.status},
            "reverse_reason": {"before": "", "after": reason},
        },
        reason=reason,
    )
    publish_event(
        event_type="wms.document.reversed",
        aggregate_type="wms.InventoryDocument",
        aggregate_id=document.pk,
        payload={
            "document_no": document.document_no,
            "document_type": document.document_type,
            "warehouse_id": document.warehouse_id,
            "reason": reason,
        },
        dedup_key=f"wms.document.reversed:{document.pk}",
    )
    logger.info("库存冲销完成 document=%s", document.document_no)
    return document


def _assert_reversible(movements: list[Movement], balances: dict[str, InventoryBalance]) -> None:
    """冲销前检查「原单据增加的库存是否还在」。"""
    for movement in movements:
        if movement.delta >= ZERO:
            continue
        balance = balances[movement.dimension.key]
        available = balance.available
        required = -movement.delta
        if available < required:
            raise StateConflict(
                "原单据增加的库存已被下游消耗，不能直接冲销。",
                code="REVERSAL_BLOCKED",
                details={
                    **movement.dimension.describe(),
                    "required": str(required),
                    "available": str(available),
                    "hint": "请走退货单、库存调整单或更正单据，不要强行反冲。",
                },
            )
def release_quality(
    *,
    user: Any,
    company: Any,
    warehouse: Warehouse,
    material: Material,
    quantity: Decimal,
    location: Location | None = None,
    batch_no: str | None = None,
    roll_no: str | None = None,
    from_status: str = QualityStatus.QUARANTINE,
    to_status: str = QualityStatus.QUALIFIED,
    biz_type: str = "",
    biz_id: str = "",
    biz_no: str = "",
    reason: str = "",
    idempotency_key: str | None = None,
) -> InventoryDocument:
    """质量放行 / 转状态：创建质量转换单并立即过账。

    采购到货检验、生产完工检验等都通过这里改变库存质量状态，
    **不是**直接改余额表的 `quality_status` 字段（那会丢失流水与审计）。
    """
    require_codes(user, "wms.quality.release")
    if quantity is None or Decimal(quantity) <= ZERO:
        raise ValidationFailed("质量放行数量必须大于 0。", code="INVALID_LINE_QUANTITY")
    if from_status == to_status:
        raise ValidationFailed("转出与转入的质量状态不能相同。", code="SAME_QUALITY_STATUS")

    company_kwargs = {"company_id": company} if isinstance(company, int) else {"company": company}
    document = InventoryDocument(
        document_no=allocate_document_no(DocumentType.QUALITY),
        document_type=DocumentType.QUALITY,
        warehouse=warehouse,
        biz_type=biz_type,
        biz_id=str(biz_id) if biz_id else "",
        biz_no=biz_no,
        remark=reason,
        **company_kwargs,
    )
    document.save()
    InventoryDocumentLine.objects.create(
        document=document,
        line_no=1,
        material=material,
        location=location,
        batch_no=str(batch_no or "").strip(),
        roll_no=str(roll_no or "").strip(),
        quality_status=from_status,
        target_quality_status=to_status,
        quantity=quantity,
        remark=reason[:255],
    )
    return post_document(
        document, user=user, idempotency_key=idempotency_key, reason=reason
    )


__all__ = [
    "Dimension",
    "Movement",
    "allocate_document_no",
    "create_document",
    "post_document",
    "release_quality",
    "reverse_document",
    "update_draft_document",
]
def _fk_id(value: Any) -> int | None:
    if value is None:
        return None
    return getattr(value, "pk", value)


def _line_kwargs(row: Mapping[str, Any]) -> dict[str, Any]:
    """把序列化器校验后的行数据规整为模型字段。同时接受 ``x`` 与 ``x_id`` 两种写法。"""

    def pick(name: str) -> Any:
        if name in row:
            return row[name]
        return row.get(f"{name}_id")

    return {
        "material_id": _fk_id(pick("material")),
        "location_id": _fk_id(pick("location")),
        "target_location_id": _fk_id(pick("target_location")),
        "batch_no": str(row.get("batch_no") or "").strip(),
        "roll_no": str(row.get("roll_no") or "").strip(),
        "quality_status": row.get("quality_status") or QualityStatus.QUARANTINE,
        "target_quality_status": str(row.get("target_quality_status") or "").strip(),
        "direction": row.get("direction") or Direction.IN,
        "quantity": row.get("quantity"),
        "remark": str(row.get("remark") or "")[:255],
    }


def _create_lines(document: InventoryDocument, lines: Sequence[Mapping[str, Any]]) -> None:
    for index, row in enumerate(lines, start=1):
        kwargs = _line_kwargs(row)
        if kwargs["material_id"] is None:
            raise ValidationFailed(f"第 {index} 行缺少物料。", code="LINE_MATERIAL_REQUIRED")
        quantity = kwargs["quantity"]
        if quantity is None or Decimal(quantity) <= ZERO:
            raise ValidationFailed(
                f"第 {index} 行数量必须大于 0。", code="INVALID_LINE_QUANTITY"
            )
        InventoryDocumentLine.objects.create(document=document, line_no=index, **kwargs)


def create_document(
    *,
    document_type: str,
    company: Any,
    warehouse: Any,
    lines: Sequence[Mapping[str, Any]],
    user: Any,
    document_no: str = "",
    biz_type: str = "",
    biz_id: Any = "",
    biz_no: str = "",
    remark: str = "",
) -> InventoryDocument:
    """创建库存单据（草稿）。

    单据编号在**创建时**取号：`(company, document_no)` 上有唯一约束，若草稿统一留空，
    同一公司下第二张草稿就会撞唯一键。取号走 `generate_code`，行级锁保证不重号。
    """
    require_codes(user, "wms.document.create")
    if not lines:
        raise ValidationFailed("单据必须至少包含一行明细。", code="EMPTY_DOCUMENT")
    with transaction.atomic():
        document = InventoryDocument(
            document_no=str(document_no or "").strip() or allocate_document_no(document_type),
            document_type=document_type,
            warehouse=warehouse,
            company_id=_fk_id(company),
            biz_type=biz_type[:32],
            biz_id=str(biz_id or "")[:64],
            biz_no=str(biz_no or "")[:64],
            remark=remark,
        )
        document.save()
        _create_lines(document, lines)
        record_audit(
            action=AuditAction.CREATE,
            instance=document,
            changes={
                "document_no": {"before": "", "after": document.document_no},
                "document_type": {"before": "", "after": document.document_type},
                "line_count": {"before": 0, "after": len(lines)},
            },
            reason=remark,
            object_repr=document.document_no,
            company=document.company,
            actor=user,
        )
    return document


def update_draft_document(
    document: InventoryDocument,
    *,
    user: Any,
    lines: Sequence[Mapping[str, Any]] | None = None,
    **header: Any,
) -> InventoryDocument:
    """修改草稿单据。已过账单据只能冲销，不能改（任务书 5.5）。"""
    require_codes(user, "wms.document.update")
    with transaction.atomic():
        locked = InventoryDocument.objects.select_for_update().filter(pk=document.pk).first()
        if locked is None:
            raise ObjectNotFound("库存单据不存在。", details={"document_id": document.pk})
        if locked.status != DocumentStatus.DRAFT:
            raise StateConflict(
                "只有草稿状态的单据可以修改；已过账单据请使用冲销。",
                details={"document_no": locked.document_no, "status": locked.status},
            )
        changed: dict[str, Any] = {}
        for field, value in header.items():
            if value is None:
                continue
            current = getattr(locked, field)
            if current != value:
                changed[field] = {"before": current, "after": value}
                setattr(locked, field, value)
        if changed:
            locked.save()
        if lines is not None:
            if not lines:
                raise ValidationFailed("单据必须至少包含一行明细。", code="EMPTY_DOCUMENT")
            locked.lines.all().delete()
            _create_lines(locked, lines)
            changed["line_count"] = {"before": 0, "after": len(lines)}
        if changed:
            record_audit(
                action=AuditAction.UPDATE,
                instance=locked,
                changes=changed,
                object_repr=locked.document_no or f"#{locked.pk}",
                company=locked.company,
                actor=user,
            )
    return locked
