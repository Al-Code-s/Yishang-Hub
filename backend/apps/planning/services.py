"""计划模块业务服务：BOM 与工艺路线的版本、审核与快照。

规则（任务书 9.5、10.6、14.2 案例 13）：

1. 只有**草稿**版本可以改明细；提交后冻结。需要变更就**新建版本**，不覆盖历史版本。
2. 审核通过时，同一「款式 + SKU 范围」的旧已审核版本自动转 `obsolete`，
   保证任何时刻只有一个生效版本；旧版本的**内容不被修改**。
3. 提交与审批复用既有 `workflow`，审批终结通过 `workflow.registry` 显式回写状态
   （任务书 4.3 禁止用 signals 承载关键流程）。
4. `build_*_snapshot()` 输出纯数据（可直接 JSON 序列化），由 MES 工单下达时保存；
   已审核版本不可变，因此快照内容与版本一致（有测试固化）。
5. 并发：范围内版本号由 `select_for_update` 降低碰撞概率，**最终靠
   (company, scope_key, version_no) 唯一约束兜底**——空结果集上的
   `select_for_update` 不提供锁保护（任务书 5.6）。
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from decimal import Decimal
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.core.exceptions import StateConflict, ValidationFailed
from apps.core.logging import get_current_user
from apps.core.models import AuditAction
from apps.core.permissions import require_codes
from apps.core.services import (
    build_changes,
    generate_code,
    publish_event,
    record_audit,
)
from apps.planning.models import (
    DEFAULT_ROUTING_STEPS,
    Bom,
    BomLine,
    BomLineType,
    BomStatus,
    Routing,
    RoutingStatus,
    RoutingStep,
    engineering_scope_key,
)

BIZ_TYPE_BOM = "planning.bom"
BIZ_TYPE_ROUTING = "planning.routing"
BOM_CODE_RULE = "BOM"
ROUTING_CODE_RULE = "ROUTING"
ZERO = Decimal("0")


def _require_lines(rows: Iterable[dict[str, Any]], label: str) -> list[dict[str, Any]]:
    materialized = list(rows or [])
    if not materialized:
        raise ValidationFailed(f"{label}至少需要一行。", code="EMPTY_DOCUMENT")
    return materialized


def _positive(value: Any, message: str) -> Decimal:
    if value is None:
        raise ValidationFailed(message, code="VALIDATION_ERROR")
    decimal_value = Decimal(str(value))
    if decimal_value <= ZERO:
        raise ValidationFailed(message, code="VALIDATION_ERROR")
    return decimal_value

def _assert_style_usable(style) -> None:
    if not getattr(style, "is_active", True):
        raise ValidationFailed("款式已停用，不能新建工程数据。", code="STYLE_INACTIVE")


def _assert_sku_matches(style, sku) -> None:
    if sku is not None and sku.style_id != style.pk:
        raise ValidationFailed("所选 SKU 不属于该款式。", code="SKU_STYLE_MISMATCH")


def _assert_company_scope(*, company, style, sku=None) -> None:
    """公司一致性校验。

    接口层已按数据范围解析过公司，这里再做一次，覆盖服务被后台任务或其他模块
    直接调用的情况：跨公司的款式 / SKU 不允许组合成同一份工程数据。
    """
    company_id = getattr(company, "pk", company)
    if style.company_id != company_id:
        raise ValidationFailed("款式与公司不一致。", code="COMPANY_STYLE_MISMATCH")
    if sku is not None and sku.company_id != company_id:
        raise ValidationFailed("SKU 与公司不一致。", code="COMPANY_SKU_MISMATCH")


def _assert_effective_range(effective_from: date | None, effective_to: date | None) -> None:
    if effective_from and effective_to and effective_to < effective_from:
        raise ValidationFailed("失效日期不能早于生效日期。", code="INVALID_EFFECTIVE_RANGE")


def _next_version_no(model: Any, *, company: Any, style_id: int, sku_id: int | None) -> int:
    """同范围内的下一个版本号。

    说明：空结果集上的 ``select_for_update`` **不提供锁保护**（任务书 5.6），
    这里只是减少碰撞概率，真正的一致性由 (company, scope_key, version_no) 唯一约束兜底。
    """
    key = engineering_scope_key(style_id, sku_id)
    last = (
        model.objects.select_for_update()
        .filter(company=company, scope_key=key)
        .order_by("-version_no")
        .values_list("version_no", flat=True)
        .first()
    )
    return int(last or 0) + 1


def _replace_bom_lines(bom: Bom, rows: list[dict[str, Any]]) -> None:
    """整表替换 BOM 明细。只在草稿版本上调用。"""
    bom.lines.all().delete()
    seen_materials: set[int] = set()
    created: list[tuple[BomLine, dict[str, Any]]] = []
    for index, row in enumerate(rows, start=1):
        material = row["material"]
        line_type = row.get("line_type") or BomLineType.NORMAL
        if line_type == BomLineType.NORMAL:
            if material.pk in seen_materials:
                raise ValidationFailed(
                    f"物料 {material.code} 重复出现：同一 BOM 中同一物料只允许一条正常用料行。",
                    code="DUPLICATE_MATERIAL",
                )
            seen_materials.add(material.pk)
        loss_rate = Decimal(str(row.get("loss_rate") if row.get("loss_rate") is not None else ZERO))
        if loss_rate < ZERO or loss_rate >= 1:
            raise ValidationFailed(f"第 {index} 行损耗率必须在 [0, 1) 之间。", code="INVALID_LOSS_RATE")
        if material.company_id != bom.company_id:
            raise ValidationFailed(
                f"第 {index} 行物料与 BOM 所属公司不一致。", code="COMPANY_MATERIAL_MISMATCH"
            )
        line = BomLine(
            bom=bom,
            line_no=int(row.get("line_no") or index),
            material=material,
            quantity=_positive(row.get("quantity"), f"第 {index} 行标准用量必须大于 0。"),
            loss_rate=loss_rate,
            uom=row.get("uom") or material.base_uom,
            line_type=line_type,
            position=row.get("position") or "",
            is_key_material=bool(row.get("is_key_material")),
            remark=row.get("remark") or "",
        )
        line.save()
        created.append((line, row))
    by_line_no = {line.line_no: line for line, _ in created}
    if len(by_line_no) != len(created):
        raise ValidationFailed("BOM 明细行号重复。", code="DUPLICATE_LINE_NO")
    for line, row in created:
        target_no = row.get("substitute_for_line_no")
        if not target_no:
            continue
        if line.line_type != BomLineType.SUBSTITUTE:
            raise ValidationFailed(
                f"第 {line.line_no} 行：只有替代料行才能指定被替代用料。", code="INVALID_SUBSTITUTE"
            )
        target = by_line_no.get(int(target_no))
        if target is None or target.line_type == BomLineType.SUBSTITUTE:
            raise ValidationFailed(
                f"第 {line.line_no} 行：被替代行号 {target_no} 无效。", code="INVALID_SUBSTITUTE"
            )
        if target.material_id == line.material_id:
            raise ValidationFailed("替代料不能与被替代物料相同。", code="INVALID_SUBSTITUTE")
        line.substitute_for = target
        line.save()

@transaction.atomic
def create_bom(
    *,
    user: Any,
    company: Any,
    style: Any,
    lines: Iterable[dict[str, Any]],
    sku: Any = None,
    effective_from: date | None = None,
    effective_to: date | None = None,
    remark: str = "",
    code: str = "",
) -> Bom:
    """新建 BOM 草稿版本。版本号在同一「款式 + SKU 范围」内自增。"""
    require_codes(user, "planning.bom.create")
    _assert_company_scope(company=company, style=style, sku=sku)
    _assert_style_usable(style)
    _assert_sku_matches(style, sku)
    _assert_effective_range(effective_from, effective_to)
    rows = _require_lines(lines, "BOM")
    bom = Bom(
        company=company,
        code=code or generate_code(BOM_CODE_RULE),
        style=style,
        sku=sku,
        version_no=_next_version_no(
            Bom, company=company, style_id=style.pk, sku_id=sku.pk if sku else None
        ),
        status=BomStatus.DRAFT,
        effective_from=effective_from,
        effective_to=effective_to,
        remark=remark or "",
    )
    bom.save()
    _replace_bom_lines(bom, rows)
    record_audit(
        action=AuditAction.CREATE,
        instance=bom,
        changes={"code": bom.code, "version_no": bom.version_no, "line_count": len(rows)},
        object_repr=str(bom),
        company=company,
        actor=user,
    )
    publish_event(
        event_type="planning.bom.created",
        aggregate_type="planning.Bom",
        aggregate_id=bom.pk,
        payload={"bom_id": bom.pk, "bom_code": bom.code, "version_no": bom.version_no},
        dedup_key=f"bom:{bom.pk}:created",
    )
    return bom


@transaction.atomic
def update_bom(
    bom: Bom,
    *,
    user: Any,
    header: dict[str, Any] | None = None,
    lines: Iterable[dict[str, Any]] | None = None,
) -> Bom:
    """修改草稿 BOM。已提交/已审核的版本拒绝修改，必须派生新版本。"""
    require_codes(user, "planning.bom.update")
    locked = Bom.objects.select_for_update().get(pk=bom.pk)
    if not locked.is_editable:
        raise StateConflict(
            "只有草稿状态的 BOM 可以修改；已提交或已审核的版本请派生新版本。",
            code="BOM_LOCKED",
        )
    payload = dict(header or {})
    before = {
        "effective_from": locked.effective_from,
        "effective_to": locked.effective_to,
        "remark": locked.remark,
    }
    for field in ("effective_from", "effective_to", "remark"):
        if field in payload:
            setattr(locked, field, payload[field])
    _assert_effective_range(locked.effective_from, locked.effective_to)
    locked.save()
    if lines is not None:
        _replace_bom_lines(locked, _require_lines(lines, "BOM"))
    after = {
        "effective_from": locked.effective_from,
        "effective_to": locked.effective_to,
        "remark": locked.remark,
    }
    changes = build_changes(before, after)
    if lines is not None:
        changes["lines"] = {"line_count": locked.lines.count()}
    if changes:
        record_audit(
            action=AuditAction.UPDATE,
            instance=locked,
            changes=changes,
            object_repr=str(locked),
            company=locked.company,
            actor=user,
        )
    return locked

def _submit_for_approval(
    document: Any, *, user: Any, biz_type: str, title: str, summary: str, comment: str
):
    """创建并提交审批实例。复用 workflow，不新建审批体系。"""
    from apps.workflow import services as workflow_services

    instance = workflow_services.create_instance(
        user,
        title=title,
        biz_type=biz_type,
        biz_id=str(document.pk),
        biz_no=document.code,
        summary=summary,
        amount=None,
        company=document.company,
        department=None,
    )
    workflow_services.submit_instance(user, instance, comment=comment)
    return instance


def _activate_version(
    *,
    model: Any,
    document: Any,
    instance: Any,
    approved_status: str,
    obsolete_status: str,
    kind: str,
) -> None:
    """审核通过：本版本生效，同范围的旧已审核版本转作废。

    旧版本只改 ``status``，**内容一律不动**，因此已引用旧版本的工单不受影响。
    """
    approver = get_current_user()
    previous_versions = (
        model.objects.select_for_update()
        .filter(company=document.company, scope_key=document.scope_key, status=approved_status)
        .exclude(pk=document.pk)
    )
    for old in previous_versions:
        previous_status = old.status
        old.status = obsolete_status
        old.save()
        record_audit(
            action=AuditAction.UPDATE,
            instance=old,
            changes={"status": {"before": previous_status, "after": obsolete_status}},
            reason=f"{kind} v{document.version_no} 审核通过，旧版本自动作废",
            object_repr=str(old),
            company=old.company,
            actor=instance.applicant,
        )
    previous_status = document.status
    document.status = approved_status
    document.approved_at = timezone.now()
    if getattr(approver, "pk", None):
        document.approved_by = approver
    document.save()
    record_audit(
        action=AuditAction.APPROVE,
        instance=document,
        changes={"status": {"before": previous_status, "after": approved_status}},
        object_repr=str(document),
        approval_basis=f"workflow.ApprovalInstance#{instance.pk}",
        company=document.company,
        actor=instance.applicant,
    )
    publish_event(
        event_type=f"planning.{kind.lower()}.approved",
        aggregate_type=f"planning.{model.__name__}",
        aggregate_id=document.pk,
        payload={
            "id": document.pk,
            "code": document.code,
            "version_no": document.version_no,
            "scope_key": document.scope_key,
        },
        dedup_key=f"{kind.lower()}:{document.pk}:approved",
    )


def _record_outcome(document: Any, *, instance: Any, outcome: str, status_field_values: dict[str, str]) -> None:
    """驳回 / 撤回的统一回写与审计。"""
    from apps.workflow.registry import OUTCOME_REJECTED

    previous_status = document.status
    document.status = status_field_values["rejected" if outcome == OUTCOME_REJECTED else "withdrawn"]
    document.save()
    record_audit(
        action=AuditAction.REJECT if outcome == OUTCOME_REJECTED else AuditAction.WITHDRAW,
        instance=document,
        changes={"status": {"before": previous_status, "after": document.status}},
        object_repr=str(document),
        approval_basis=f"workflow.ApprovalInstance#{instance.pk}",
        company=document.company,
        actor=instance.applicant,
    )

@transaction.atomic
def submit_bom(bom: Bom, *, user: Any, comment: str = "") -> Bom:
    """提交 BOM 审批。提交后明细冻结。"""
    require_codes(user, "planning.bom.submit")
    locked = Bom.objects.select_for_update().get(pk=bom.pk)
    if locked.status != BomStatus.DRAFT:
        raise StateConflict("只有草稿状态的 BOM 可以提交。", code="STATE_CONFLICT")
    if not locked.lines.exists():
        raise ValidationFailed("BOM 没有明细，不能提交。", code="EMPTY_DOCUMENT")
    instance = _submit_for_approval(
        locked,
        user=user,
        biz_type=BIZ_TYPE_BOM,
        title=f"BOM 审核 {locked.code}",
        summary=f"{locked.style} / {locked.scope_label} / v{locked.version_no}",
        comment=comment,
    )
    locked.status = BomStatus.SUBMITTED
    locked.submitted_at = timezone.now()
    locked.approval_instance = instance
    locked.save()
    record_audit(
        action=AuditAction.SUBMIT,
        instance=locked,
        changes={"status": {"before": BomStatus.DRAFT, "after": BomStatus.SUBMITTED}},
        object_repr=str(locked),
        reason=comment,
        approval_basis=f"workflow.ApprovalInstance#{instance.pk}",
        company=locked.company,
        actor=user,
    )
    publish_event(
        event_type="planning.bom.submitted",
        aggregate_type="planning.Bom",
        aggregate_id=locked.pk,
        payload={"bom_id": locked.pk, "bom_code": locked.code},
        dedup_key=f"bom:{locked.pk}:submitted",
    )
    return locked


def on_bom_approval_outcome(instance: Any, outcome: str) -> None:
    """审批终结回写 BOM 状态（由 workflow.registry 在同一事务内调用）。"""
    from apps.workflow.registry import (
        OUTCOME_APPROVED,
        OUTCOME_REJECTED,
        OUTCOME_WITHDRAWN,
    )

    bom = Bom.objects.select_for_update().filter(pk=instance.biz_id).first()
    if bom is None or bom.status != BomStatus.SUBMITTED:
        return
    if outcome == OUTCOME_APPROVED:
        _activate_version(
            model=Bom,
            document=bom,
            instance=instance,
            approved_status=BomStatus.APPROVED,
            obsolete_status=BomStatus.OBSOLETE,
            kind="BOM",
        )
    elif outcome in (OUTCOME_REJECTED, OUTCOME_WITHDRAWN):
        _record_outcome(
            bom,
            instance=instance,
            outcome=outcome,
            status_field_values={"rejected": BomStatus.REJECTED, "withdrawn": BomStatus.DRAFT},
        )


@transaction.atomic
def obsolete_bom(bom: Bom, *, user: Any, reason: str) -> Bom:
    """作废 BOM 版本（需填原因）。作废只改状态与启用标记，不物理删除。"""
    require_codes(user, "planning.bom.obsolete")
    if not (reason or "").strip():
        raise ValidationFailed("作废必须填写原因。", code="REASON_REQUIRED")
    locked = Bom.objects.select_for_update().get(pk=bom.pk)
    if locked.status == BomStatus.OBSOLETE:
        raise StateConflict("该 BOM 版本已作废。", code="STATE_CONFLICT")
    if locked.status == BomStatus.SUBMITTED:
        raise StateConflict("审核中的 BOM 不能直接作废，请先撤回审批。", code="STATE_CONFLICT")
    previous_status = locked.status
    locked.status = BomStatus.OBSOLETE
    locked.is_active = False
    locked.save()
    record_audit(
        action=AuditAction.DEACTIVATE,
        instance=locked,
        changes={"status": {"before": previous_status, "after": BomStatus.OBSOLETE}},
        reason=reason,
        object_repr=str(locked),
        company=locked.company,
        actor=user,
    )
    return locked

@transaction.atomic
def create_bom_version(bom: Bom, *, user: Any, effective_from: date | None = None) -> Bom:
    """从既有版本派生新的草稿版本（复制明细）。

    这是**唯一允许的变更方式**：不覆盖已审核版本，历史内容与已下达工单不受影响。
    """
    require_codes(user, "planning.bom.create")
    source = Bom.objects.select_for_update().get(pk=bom.pk)
    if source.status == BomStatus.SUBMITTED:
        raise StateConflict("审核中的版本不能派生新版本，请先撤回审批。", code="STATE_CONFLICT")
    rows = [
        {
            "line_no": line.line_no,
            "material": line.material,
            "quantity": line.quantity,
            "loss_rate": line.loss_rate,
            "uom": line.uom,
            "line_type": line.line_type,
            "position": line.position,
            "is_key_material": line.is_key_material,
            "remark": line.remark,
            "substitute_for_line_no": (
                line.substitute_for.line_no if line.substitute_for_id else None
            ),
        }
        for line in source.lines.select_related("material", "uom", "substitute_for").order_by(
            "line_no"
        )
    ]
    new_bom = Bom(
        company=source.company,
        code=generate_code(BOM_CODE_RULE),
        style=source.style,
        sku=source.sku,
        version_no=_next_version_no(
            Bom, company=source.company, style_id=source.style_id, sku_id=source.sku_id
        ),
        status=BomStatus.DRAFT,
        effective_from=effective_from or source.effective_from,
        effective_to=None,
        remark=source.remark,
    )
    new_bom.save()
    _replace_bom_lines(new_bom, rows)
    record_audit(
        action=AuditAction.CREATE,
        instance=new_bom,
        changes={
            "code": new_bom.code,
            "version_no": new_bom.version_no,
            "derived_from": {"before": None, "after": source.code},
        },
        object_repr=str(new_bom),
        reason=f"从 {source.code} 派生新版本",
        company=new_bom.company,
        actor=user,
    )
    return new_bom


def build_bom_snapshot(bom: Bom) -> dict[str, Any]:
    """输出 BOM 快照（纯数据，可 JSON 序列化）。

    MES 工单下达时保存本快照；由于已审核版本内容不可变，
    后续派生新版本不会改变既有快照（任务书 9.5、14.2 案例 13）。
    """
    lines = [
        {
            "line_no": line.line_no,
            "material_id": line.material_id,
            "material_code": line.material.code,
            "quantity": str(line.quantity),
            "loss_rate": str(line.loss_rate),
            "gross_quantity": str(line.gross_quantity),
            "uom_id": line.uom_id,
            "line_type": line.line_type,
            "substitute_for_line_no": (
                line.substitute_for.line_no if line.substitute_for_id else None
            ),
            "position": line.position,
            "is_key_material": line.is_key_material,
        }
        for line in bom.lines.select_related("material", "substitute_for").order_by("line_no")
    ]
    return {
        "bom_id": bom.pk,
        "bom_code": bom.code,
        "status": bom.status,
        "version_no": bom.version_no,
        "style_id": bom.style_id,
        "sku_id": bom.sku_id,
        "scope_key": bom.scope_key,
        "effective_from": bom.effective_from.isoformat() if bom.effective_from else None,
        "effective_to": bom.effective_to.isoformat() if bom.effective_to else None,
        "line_count": len(lines),
        "lines": lines,
    }

def default_routing_step_rows() -> list[dict[str, Any]]:
    """任务书 9.5 默认工艺：裁剪 → 缝制 → 整烫 → 检验 → 包装。"""
    return [
        {
            "sequence": index,
            "name": name,
            "is_quality_gate": is_gate,
            "workcenter": "",
            "equipment_requirement": "",
            "standard_hours": ZERO,
            "is_outsourced": False,
            "remark": "",
        }
        for index, (name, is_gate) in enumerate(DEFAULT_ROUTING_STEPS, start=1)
    ]


def _replace_routing_steps(routing: Routing, rows: list[dict[str, Any]]) -> None:
    routing.steps.all().delete()
    seen_sequences: set[int] = set()
    for index, row in enumerate(rows, start=1):
        sequence = int(row.get("sequence") or index)
        if sequence in seen_sequences:
            raise ValidationFailed(f"工序顺序 {sequence} 重复。", code="DUPLICATE_SEQUENCE")
        seen_sequences.add(sequence)
        standard_hours = Decimal(
            str(row.get("standard_hours") if row.get("standard_hours") is not None else ZERO)
        )
        if standard_hours < ZERO:
            raise ValidationFailed("标准工时不能为负数。", code="INVALID_STANDARD_HOURS")
        RoutingStep(
            routing=routing,
            sequence=sequence,
            name=(row.get("name") or "").strip() or f"工序 {sequence}",
            workshop=row.get("workshop"),
            workcenter=row.get("workcenter") or "",
            equipment_requirement=row.get("equipment_requirement") or "",
            standard_hours=standard_hours,
            is_quality_gate=bool(row.get("is_quality_gate")),
            is_outsourced=bool(row.get("is_outsourced")),
            remark=row.get("remark") or "",
        ).save()


@transaction.atomic
def create_routing(
    *,
    user: Any,
    company: Any,
    style: Any,
    steps: Iterable[dict[str, Any]] | None = None,
    sku: Any = None,
    effective_from: date | None = None,
    effective_to: date | None = None,
    remark: str = "",
    code: str = "",
) -> Routing:
    """新建工艺路线草稿版本。未提供工序时套用默认工艺。"""
    require_codes(user, "planning.routing.create")
    _assert_company_scope(company=company, style=style, sku=sku)
    _assert_style_usable(style)
    _assert_sku_matches(style, sku)
    _assert_effective_range(effective_from, effective_to)
    # 只有「未提供工序」才套用默认工艺；显式传入空列表视为错误输入，直接拒绝
    rows = (
        default_routing_step_rows() if steps is None else _require_lines(steps, "工艺路线工序")
    )
    routing = Routing(
        company=company,
        code=code or generate_code(ROUTING_CODE_RULE),
        style=style,
        sku=sku,
        version_no=_next_version_no(
            Routing, company=company, style_id=style.pk, sku_id=sku.pk if sku else None
        ),
        status=RoutingStatus.DRAFT,
        effective_from=effective_from,
        effective_to=effective_to,
        remark=remark or "",
    )
    routing.save()
    _replace_routing_steps(routing, rows)
    record_audit(
        action=AuditAction.CREATE,
        instance=routing,
        changes={"code": routing.code, "version_no": routing.version_no, "step_count": len(rows)},
        object_repr=str(routing),
        company=company,
        actor=user,
    )
    publish_event(
        event_type="planning.routing.created",
        aggregate_type="planning.Routing",
        aggregate_id=routing.pk,
        payload={
            "routing_id": routing.pk,
            "routing_code": routing.code,
            "version_no": routing.version_no,
        },
        dedup_key=f"routing:{routing.pk}:created",
    )
    return routing


@transaction.atomic
def update_routing(
    routing: Routing,
    *,
    user: Any,
    header: dict[str, Any] | None = None,
    steps: Iterable[dict[str, Any]] | None = None,
) -> Routing:
    """修改草稿工艺路线。已提交/已审核的版本拒绝修改。"""
    require_codes(user, "planning.routing.update")
    locked = Routing.objects.select_for_update().get(pk=routing.pk)
    if not locked.is_editable:
        raise StateConflict(
            "只有草稿状态的工艺路线可以修改；已提交或已审核的版本请派生新版本。",
            code="ROUTING_LOCKED",
        )
    payload = dict(header or {})
    before = {
        "effective_from": locked.effective_from,
        "effective_to": locked.effective_to,
        "remark": locked.remark,
    }
    for field in ("effective_from", "effective_to", "remark"):
        if field in payload:
            setattr(locked, field, payload[field])
    _assert_effective_range(locked.effective_from, locked.effective_to)
    locked.save()
    if steps is not None:
        _replace_routing_steps(locked, _require_lines(steps, "工艺路线工序"))
    after = {
        "effective_from": locked.effective_from,
        "effective_to": locked.effective_to,
        "remark": locked.remark,
    }
    changes = build_changes(before, after)
    if steps is not None:
        changes["steps"] = {"step_count": locked.steps.count()}
    if changes:
        record_audit(
            action=AuditAction.UPDATE,
            instance=locked,
            changes=changes,
            object_repr=str(locked),
            company=locked.company,
            actor=user,
        )
    return locked

@transaction.atomic
def submit_routing(routing: Routing, *, user: Any, comment: str = "") -> Routing:
    """提交工艺路线审批。提交后工序冻结。"""
    require_codes(user, "planning.routing.submit")
    locked = Routing.objects.select_for_update().get(pk=routing.pk)
    if locked.status != RoutingStatus.DRAFT:
        raise StateConflict("只有草稿状态的工艺路线可以提交。", code="STATE_CONFLICT")
    if not locked.steps.exists():
        raise ValidationFailed("工艺路线没有工序，不能提交。", code="EMPTY_DOCUMENT")
    instance = _submit_for_approval(
        locked,
        user=user,
        biz_type=BIZ_TYPE_ROUTING,
        title=f"工艺路线审核 {locked.code}",
        summary=f"{locked.style} / {locked.scope_label} / v{locked.version_no}",
        comment=comment,
    )
    locked.status = RoutingStatus.SUBMITTED
    locked.submitted_at = timezone.now()
    locked.approval_instance = instance
    locked.save()
    record_audit(
        action=AuditAction.SUBMIT,
        instance=locked,
        changes={"status": {"before": RoutingStatus.DRAFT, "after": RoutingStatus.SUBMITTED}},
        object_repr=str(locked),
        reason=comment,
        approval_basis=f"workflow.ApprovalInstance#{instance.pk}",
        company=locked.company,
        actor=user,
    )
    publish_event(
        event_type="planning.routing.submitted",
        aggregate_type="planning.Routing",
        aggregate_id=locked.pk,
        payload={"routing_id": locked.pk, "routing_code": locked.code},
        dedup_key=f"routing:{locked.pk}:submitted",
    )
    return locked


def on_routing_approval_outcome(instance: Any, outcome: str) -> None:
    """审批终结回写工艺路线状态（由 workflow.registry 在同一事务内调用）。"""
    from apps.workflow.registry import (
        OUTCOME_APPROVED,
        OUTCOME_REJECTED,
        OUTCOME_WITHDRAWN,
    )

    routing = Routing.objects.select_for_update().filter(pk=instance.biz_id).first()
    if routing is None or routing.status != RoutingStatus.SUBMITTED:
        return
    if outcome == OUTCOME_APPROVED:
        _activate_version(
            model=Routing,
            document=routing,
            instance=instance,
            approved_status=RoutingStatus.APPROVED,
            obsolete_status=RoutingStatus.OBSOLETE,
            kind="Routing",
        )
    elif outcome in (OUTCOME_REJECTED, OUTCOME_WITHDRAWN):
        _record_outcome(
            routing,
            instance=instance,
            outcome=outcome,
            status_field_values={
                "rejected": RoutingStatus.REJECTED,
                "withdrawn": RoutingStatus.DRAFT,
            },
        )

@transaction.atomic
def create_routing_version(
    routing: Routing, *, user: Any, effective_from: date | None = None
) -> Routing:
    """从既有工艺路线派生新的草稿版本（复制工序）。"""
    require_codes(user, "planning.routing.create")
    source = Routing.objects.select_for_update().get(pk=routing.pk)
    if source.status == RoutingStatus.SUBMITTED:
        raise StateConflict("审核中的版本不能派生新版本，请先撤回审批。", code="STATE_CONFLICT")
    rows = [
        {
            "sequence": step.sequence,
            "name": step.name,
            "workshop": step.workshop,
            "workcenter": step.workcenter,
            "equipment_requirement": step.equipment_requirement,
            "standard_hours": step.standard_hours,
            "is_quality_gate": step.is_quality_gate,
            "is_outsourced": step.is_outsourced,
            "remark": step.remark,
        }
        for step in source.steps.select_related("workshop").order_by("sequence")
    ]
    new_routing = Routing(
        company=source.company,
        code=generate_code(ROUTING_CODE_RULE),
        style=source.style,
        sku=source.sku,
        version_no=_next_version_no(
            Routing, company=source.company, style_id=source.style_id, sku_id=source.sku_id
        ),
        status=RoutingStatus.DRAFT,
        effective_from=effective_from or source.effective_from,
        effective_to=None,
        remark=source.remark,
    )
    new_routing.save()
    _replace_routing_steps(new_routing, rows)
    record_audit(
        action=AuditAction.CREATE,
        instance=new_routing,
        changes={
            "code": new_routing.code,
            "version_no": new_routing.version_no,
            "derived_from": {"before": None, "after": source.code},
        },
        object_repr=str(new_routing),
        reason=f"从 {source.code} 派生新版本",
        company=new_routing.company,
        actor=user,
    )
    return new_routing


@transaction.atomic
def obsolete_routing(routing: Routing, *, user: Any, reason: str) -> Routing:
    """作废工艺路线版本（需填原因）。"""
    require_codes(user, "planning.routing.obsolete")
    if not (reason or "").strip():
        raise ValidationFailed("作废必须填写原因。", code="REASON_REQUIRED")
    locked = Routing.objects.select_for_update().get(pk=routing.pk)
    if locked.status == RoutingStatus.OBSOLETE:
        raise StateConflict("该工艺路线版本已作废。", code="STATE_CONFLICT")
    if locked.status == RoutingStatus.SUBMITTED:
        raise StateConflict("审核中的工艺路线不能直接作废，请先撤回审批。", code="STATE_CONFLICT")
    previous_status = locked.status
    locked.status = RoutingStatus.OBSOLETE
    locked.is_active = False
    locked.save()
    record_audit(
        action=AuditAction.DEACTIVATE,
        instance=locked,
        changes={"status": {"before": previous_status, "after": RoutingStatus.OBSOLETE}},
        reason=reason,
        object_repr=str(locked),
        company=locked.company,
        actor=user,
    )
    return locked

def build_routing_snapshot(routing: Routing) -> dict[str, Any]:
    """输出工艺路线快照（纯数据，可 JSON 序列化）。

    与 ``build_bom_snapshot`` 一样，供 MES 工单下达时保存；
    已审核版本不可变，快照内容与版本一致。
    """
    steps = [
        {
            "sequence": step.sequence,
            "name": step.name,
            "workshop_id": step.workshop_id,
            "workcenter": step.workcenter,
            "equipment_requirement": step.equipment_requirement,
            "standard_hours": str(step.standard_hours),
            "is_quality_gate": step.is_quality_gate,
            "is_outsourced": step.is_outsourced,
        }
        for step in routing.steps.order_by("sequence")
    ]
    return {
        "routing_id": routing.pk,
        "routing_code": routing.code,
        "status": routing.status,
        "version_no": routing.version_no,
        "style_id": routing.style_id,
        "sku_id": routing.sku_id,
        "scope_key": routing.scope_key,
        "effective_from": routing.effective_from.isoformat() if routing.effective_from else None,
        "effective_to": routing.effective_to.isoformat() if routing.effective_to else None,
        "step_count": len(steps),
        "steps": steps,
    }


def get_effective_bom(company: Any, style: Any, sku: Any = None) -> Bom | None:
    """取生效版本的 BOM（同一范围最多一条 approved）。供 MRP / MES 使用。"""
    style_id = getattr(style, "pk", style)
    sku_id = getattr(sku, "pk", sku) if sku is not None else None
    return (
        Bom.objects.filter(
            company=company,
            scope_key=engineering_scope_key(style_id, sku_id),
            status=BomStatus.APPROVED,
            is_active=True,
        )
        .order_by("-version_no")
        .first()
    )


def get_effective_bom_for(company: Any, style: Any, sku: Any = None) -> Bom | None:
    """按「SKU 差异版本优先、否则回落款式通用版本」取生效 BOM。

    与 ``get_effective_bom``（只认精确范围）的区别：本函数用于**需求侧**解析
    （MRP 展开、工单下达），允许「款式通用 BOM 服务所有 SKU」这一常见做法；
    若该 SKU 存在专属生效版本，则以专属版本为准。
    """
    style_id = getattr(style, "pk", style)
    sku_id = getattr(sku, "pk", sku) if sku is not None else None
    if sku_id is not None:
        specific = get_effective_bom(company, style_id, sku_id)
        if specific is not None:
            return specific
    return get_effective_bom(company, style_id, None)


def get_effective_routing(company: Any, style: Any, sku: Any = None) -> Routing | None:
    """取生效版本的工艺路线。SKU 差异版本优先，否则回落款式通用版本。"""
    style_id = getattr(style, "pk", style)
    sku_id = getattr(sku, "pk", sku) if sku is not None else None
    base = Routing.objects.filter(
        company=company, status=RoutingStatus.APPROVED, is_active=True
    )
    if sku_id is not None:
        specific = (
            base.filter(scope_key=engineering_scope_key(style_id, sku_id))
            .order_by("-version_no")
            .first()
        )
        if specific is not None:
            return specific
    return (
        base.filter(scope_key=engineering_scope_key(style_id, None))
        .order_by("-version_no")
        .first()
    )


__all__ = [
    "BIZ_TYPE_BOM",
    "BIZ_TYPE_ROUTING",
    "BOM_CODE_RULE",
    "ROUTING_CODE_RULE",
    "build_bom_snapshot",
    "build_routing_snapshot",
    "create_bom",
    "create_bom_version",
    "create_routing",
    "create_routing_version",
    "default_routing_step_rows",
    "get_effective_bom",
    "get_effective_bom_for",
    "get_effective_routing",
    "obsolete_bom",
    "obsolete_routing",
    "on_bom_approval_outcome",
    "on_routing_approval_outcome",
    "submit_bom",
    "submit_routing",
    "update_bom",
    "update_routing",
]
