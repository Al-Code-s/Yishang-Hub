"""供应商模块的领域规则：主联系人唯一性 + 五维量化评价。

评价的计算口径（`docs/assumptions.md` A-10~A-12，**刻意如此，不要放宽**）：

* **总分只能由本模块计算**：明细写入时按权重快照重算 ``total_score``，
  接口传入的 ``total_score`` 一律忽略——不允许人工填一个好看的分数。
* **权重配置只增不改**：调整权重派生新版本，旧版本原样保留；
  评价单保存 ``weight_snapshot``，历史评分不因后来改权重而变。
* **缺数据不记零分**：五个维度必须各给一行，没有数据的维度把 ``raw_score`` 留空，
  由服务层标记 ``is_missing``：
    - ``mark_missing``：有效权重为 0，总分是**不完整口径**的加权和（上限低于 100），
      因此**不给等级**——避免用缺项总分贴标签；
    - ``redistribute``：把缺数据维度的权重按比例摊给有数据的维度（有效权重合计仍为 100），
      总分是完整的百分制，可以给等级。
  两种策略都会在评价单上留下 ``missing_dimensions`` 与 ``effective_weight_total``。
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from django.db import transaction

from apps.core.exceptions import StateConflict, ValidationFailed
from apps.core.models import AuditAction
from apps.core.permissions import require_codes
from apps.core.services import (
    business_now,
    ensure_single_primary,
    generate_code,
    record_audit,
)
from apps.srm.models import (
    DIMENSION_WEIGHT_FIELD,
    EVALUATION_DIMENSIONS,
    EvaluationDimension,
    MissingDimensionPolicy,
    SupplierContact,
    SupplierEvaluation,
    SupplierEvaluationLine,
    SupplierEvaluationStatus,
    SupplierEvaluationWeight,
    SupplierGrade,
)

EVALUATION_CODE_RULE = "SEV"
HUNDRED = Decimal("100")
CENT = Decimal("0.01")
ZERO = Decimal("0")

#: 等级阈值（含端点），按从高到低匹配；低于最后一档即为 D 级
GRADE_THRESHOLDS: tuple[tuple[Decimal, str], ...] = (
    (Decimal("90"), SupplierGrade.A),
    (Decimal("75"), SupplierGrade.B),
    (Decimal("60"), SupplierGrade.C),
)


def ensure_single_primary_contact(contact: SupplierContact) -> None:
    """保证同一供应商下只有一个主要联系人。"""
    ensure_single_primary(
        SupplierContact,
        instance=contact,
        scope_field="supplier_id",
        scope_id=contact.supplier_id,
    )


# ---------------------------------------------------------------------------
# 权重配置
# ---------------------------------------------------------------------------


def next_evaluation_no() -> str:
    """评价单号（编码规则 SEV）。"""
    return generate_code(EVALUATION_CODE_RULE)


def normalize_weights(weights: dict[str, Any]) -> dict[str, Decimal]:
    """把各维度权重规整成 Decimal，并校验取值与合计。

    合计必须是 **100**；不接受 99.99 或 100.01——「差不多 100」会让总分失去可解释性。
    """
    normalized: dict[str, Decimal] = {}
    for dimension in EVALUATION_DIMENSIONS:
        raw = weights.get(dimension, 0)
        if raw in (None, ""):
            raw = 0
        try:
            value = Decimal(str(raw))
        except Exception as exc:  # noqa: BLE001 - 统一转成业务校验错误
            raise ValidationFailed(
                f"权重必须是数字：{dimension}={raw}", code="INVALID_WEIGHT"
            ) from exc
        if value < 0 or value > HUNDRED:
            raise ValidationFailed(
                f"权重必须在 0~100 之间：{dimension}={value}", code="INVALID_WEIGHT"
            )
        normalized[dimension] = value.quantize(CENT, rounding=ROUND_HALF_UP)
    total = sum(normalized.values())
    if total != HUNDRED:
        raise ValidationFailed(
            f"五类权重之和必须为 100%，当前为 {total}%。", code="WEIGHT_TOTAL_INVALID"
        )
    return normalized


def snapshot_weights(config: SupplierEvaluationWeight) -> dict[str, str]:
    """权重快照（JSON 可序列化；Decimal 一律以字符串保存）。"""
    return {dimension: str(getattr(config, field)) for dimension, field in DIMENSION_WEIGHT_FIELD.items()}


def active_weight_config(company: Any) -> SupplierEvaluationWeight | None:
    company_id = getattr(company, "pk", company)
    return (
        SupplierEvaluationWeight.objects.filter(company_id=company_id, is_active=True)
        .order_by("-version_no", "-id")
        .first()
    )


def require_active_weight_config(company: Any) -> SupplierEvaluationWeight:
    config = active_weight_config(company)
    if config is None:
        raise ValidationFailed(
            "该公司还没有启用的评价权重配置，请先维护五类权重（合计 100%）。",
            code="EVALUATION_WEIGHT_REQUIRED",
        )
    return config


def create_weight_config(
    user: Any,
    *,
    company: Any,
    weights: dict[str, Any],
    remark: str = "",
    activate: bool = True,
) -> SupplierEvaluationWeight:
    """新建一版权重配置（需要 `srm.evaluation_weight.create`）。"""
    require_codes(user, "srm.evaluation_weight.create")
    return _store_weight_config(
        user, company=company, weights=weights, remark=remark, activate=activate
    )


@transaction.atomic
def _store_weight_config(
    user: Any,
    *,
    company: Any,
    weights: dict[str, Any],
    remark: str = "",
    activate: bool = True,
) -> SupplierEvaluationWeight:
    """落库一版权重配置：版本号在公司内自增，启用时把同公司其它版本置为停用。

    权限校验由调用方负责（新建与派生新版本的权限点不同）。
    """
    company_id = getattr(company, "pk", company)
    normalized = normalize_weights(weights)
    last_version = (
        SupplierEvaluationWeight.objects.filter(company_id=company_id)
        .order_by("-version_no")
        .values_list("version_no", flat=True)
        .first()
    )
    config = SupplierEvaluationWeight(
        company_id=company_id,
        version_no=int(last_version or 0) + 1,
        is_active=bool(activate),
        remark=remark or "",
    )
    for dimension, field in DIMENSION_WEIGHT_FIELD.items():
        setattr(config, field, normalized[dimension])
    config.save()
    if config.is_active:
        ensure_single_primary(
            SupplierEvaluationWeight,
            instance=config,
            scope_field="company_id",
            scope_id=company_id,
            flag_field="is_active",
        )
    record_audit(
        action=AuditAction.CREATE,
        instance=config,
        changes={
            "version_no": config.version_no,
            "weights": snapshot_weights(config),
            "is_active": config.is_active,
        },
        reason=remark or "",
        object_repr=str(config),
        company=config.company,
        actor=user,
    )
    return config


@transaction.atomic
def derive_weight_config(
    user: Any,
    config: SupplierEvaluationWeight,
    *,
    weights: dict[str, Any] | None = None,
    remark: str | None = None,
    activate: bool = True,
) -> SupplierEvaluationWeight:
    """派生新版本：**不修改**传入的旧配置，改动体现在新版本上。

    这样历史评价引用的 `weight_config` 与其权重快照始终可解释（A-10 的留痕要求）。
    """
    require_codes(user, "srm.evaluation_weight.update")
    locked = SupplierEvaluationWeight.objects.select_for_update().get(pk=config.pk)
    merged = locked.weights()
    for dimension, value in (weights or {}).items():
        if dimension not in DIMENSION_WEIGHT_FIELD:
            raise ValidationFailed(f"未知的评价维度：{dimension}", code="INVALID_DIMENSION")
        merged[dimension] = value
    return _store_weight_config(
        user,
        company=locked.company_id,
        weights=merged,
        remark=locked.remark if remark is None else remark,
        activate=activate,
    )


# ---------------------------------------------------------------------------
# 评价单
# ---------------------------------------------------------------------------


def _assert_supplier_usable(supplier: Any) -> None:
    if not supplier.is_active:
        raise StateConflict("供应商已停用，不能对其发起评价。", code="SUPPLIER_INACTIVE")


def _prepare_lines(evaluation: SupplierEvaluation, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """校验明细并补齐权重（来自评分时的权重快照）。

    五个维度必须**各给一行**：没有数据的维度把 ``raw_score`` 留空，
    由服务层标记缺失——「没填」与「数据为零」在这里被强制区分开。
    """
    provided: dict[str, dict[str, Any]] = {}
    for row in rows:
        dimension = str(row.get("dimension") or "").strip()
        if dimension not in DIMENSION_WEIGHT_FIELD:
            raise ValidationFailed(f"未知的评价维度：{dimension}", code="INVALID_DIMENSION")
        if dimension in provided:
            raise ValidationFailed(f"维度重复：{dimension}", code="DUPLICATED_DIMENSION")
        provided[dimension] = row
    missing_rows = [d for d in EVALUATION_DIMENSIONS if d not in provided]
    if missing_rows:
        raise ValidationFailed(
            "五个维度必须各给一行（没有数据的维度请把原始得分留空）："
            + "、".join(dict(EvaluationDimension.choices)[d] for d in missing_rows),
            code="DIMENSION_ROWS_INCOMPLETE",
        )

    snapshot = {k: Decimal(str(v)) for k, v in (evaluation.weight_snapshot or {}).items()}
    prepared: list[dict[str, Any]] = []
    for dimension in EVALUATION_DIMENSIONS:
        row = provided[dimension]
        raw_score = row.get("raw_score")
        if raw_score in (None, ""):
            score: Decimal | None = None
        else:
            try:
                score = Decimal(str(raw_score))
            except Exception as exc:  # noqa: BLE001
                raise ValidationFailed(
                    f"原始得分必须是数字：{dimension}={raw_score}", code="INVALID_SCORE"
                ) from exc
            if score < 0 or score > HUNDRED:
                raise ValidationFailed(
                    f"原始得分必须在 0~100 之间：{dimension}={score}", code="INVALID_SCORE"
                )
            score = score.quantize(CENT, rounding=ROUND_HALF_UP)
        observation = row.get("raw_observation")
        if observation in (None, ""):
            observation = {}
        if not isinstance(observation, dict):
            raise ValidationFailed(
                f"原始观测值必须是对象：{dimension}", code="INVALID_OBSERVATION"
            )
        if dimension not in snapshot:
            raise ValidationFailed(
                f"权重快照缺少维度 {dimension}，请重新维护权重配置。",
                code="WEIGHT_SNAPSHOT_INCOMPLETE",
            )
        prepared.append(
            {
                "dimension": dimension,
                "raw_score": score,
                "raw_observation": observation,
                "weight": snapshot[dimension],
                "remark": str(row.get("remark") or ""),
            }
        )
    return prepared


def _redistributed_weights(lines: list[SupplierEvaluationLine]) -> None:
    """把缺数据维度的权重按比例摊给有数据的维度，合计精确等于 100%。

    逐个 ``quantize`` 后把余量补在**权重最大**的那个有效维度上，
    避免四舍五入导致合计 99.99 / 100.01（不允许「差不多 100」）。
    """
    available = [line for line in lines if not line.is_missing]
    pool = sum(line.weight for line in available)
    if not available or pool <= ZERO:
        for line in lines:
            line.effective_weight = ZERO
        return
    target = max(available, key=lambda line: (line.weight, line.dimension))
    assigned = ZERO
    for line in available:
        if line is target:
            continue
        line.effective_weight = (line.weight / pool * HUNDRED).quantize(
            CENT, rounding=ROUND_HALF_UP
        )
        assigned += line.effective_weight
    target.effective_weight = HUNDRED - assigned


def recalculate(evaluation: SupplierEvaluation) -> SupplierEvaluation:
    """按明细与权重快照重算总分、有效权重合计、缺失维度与等级。"""
    lines = list(evaluation.lines.all().order_by("dimension"))
    policy = evaluation.missing_dimension_policy
    if not lines:
        evaluation.total_score = None
        evaluation.effective_weight_total = ZERO
        evaluation.grade = ""
        evaluation.missing_dimensions = []
        evaluation.save(
            update_fields=[
                "total_score",
                "effective_weight_total",
                "grade",
                "missing_dimensions",
                "updated_at",
            ]
        )
        return evaluation

    for line in lines:
        if line.is_missing:
            line.effective_weight = ZERO
            line.weighted_score = None
        else:
            line.effective_weight = line.weight
    if policy == MissingDimensionPolicy.REDISTRIBUTE and any(line.is_missing for line in lines):
        _redistributed_weights(lines)
    for line in lines:
        if line.is_missing:
            line.weighted_score = None
        else:
            line.weighted_score = (
                line.raw_score * line.effective_weight / HUNDRED
            ).quantize(CENT, rounding=ROUND_HALF_UP)
    SupplierEvaluationLine.objects.bulk_update(
        lines, ["effective_weight", "weighted_score", "is_missing"]
    )

    missing = [line.dimension for line in lines if line.is_missing]
    total_score = sum((line.weighted_score or ZERO for line in lines), ZERO).quantize(
        CENT, rounding=ROUND_HALF_UP
    )
    effective_total = sum((line.effective_weight for line in lines), ZERO).quantize(
        CENT, rounding=ROUND_HALF_UP
    )
    evaluation.total_score = total_score
    evaluation.effective_weight_total = effective_total
    evaluation.missing_dimensions = missing
    # 缺数据且不重分配权重时总分口径不完整（上限低于 100），因此不给等级
    complete = not missing or policy == MissingDimensionPolicy.REDISTRIBUTE
    evaluation.grade = grade_for(total_score) if complete else ""
    evaluation.save(
        update_fields=[
            "total_score",
            "effective_weight_total",
            "grade",
            "missing_dimensions",
            "updated_at",
        ]
    )
    return evaluation


def grade_for(score: Decimal) -> str:
    """按阈值给出等级；缺数据的不完整口径不要调用本函数。"""
    for threshold, grade in GRADE_THRESHOLDS:
        if score >= threshold:
            return grade
    return SupplierGrade.D


@transaction.atomic
def create_evaluation(
    user: Any,
    *,
    company: Any,
    supplier: Any,
    weight_config: Any = None,
    missing_dimension_policy: str = MissingDimensionPolicy.MARK_MISSING,
    period_start: Any = None,
    period_end: Any = None,
    evaluated_by: Any = None,
    evaluated_at: Any = None,
    remark: str = "",
    evaluation_no: str = "",
) -> SupplierEvaluation:
    """新建评价单（草稿）。权重来自指定配置，未指定时取该公司当前启用的版本。

    建单时就冻结 ``weight_snapshot``：之后即使派生了新版权重，这张单子仍按
    评分当时的权重解释（A-10）。
    """
    require_codes(user, "srm.evaluation.create")
    company_id = getattr(company, "pk", company)
    if getattr(supplier, "company_id", None) != company_id:
        raise ValidationFailed("供应商与公司不一致。", code="COMPANY_SUPPLIER_MISMATCH")
    _assert_supplier_usable(supplier)
    if period_start and period_end and period_end < period_start:
        raise ValidationFailed(
            "评价期间止不得早于评价期间起。", code="INVALID_PERIOD_RANGE"
        )
    if weight_config is None:
        config = require_active_weight_config(company_id)
    else:
        config = weight_config
        if config.company_id != company_id:
            raise ValidationFailed("权重配置与公司不一致。", code="COMPANY_WEIGHT_MISMATCH")
    evaluation = SupplierEvaluation.objects.create(
        company_id=company_id,
        evaluation_no=str(evaluation_no or "").strip() or next_evaluation_no(),
        supplier=supplier,
        weight_config=config,
        weight_snapshot=snapshot_weights(config),
        missing_dimension_policy=missing_dimension_policy or MissingDimensionPolicy.MARK_MISSING,
        period_start=period_start,
        period_end=period_end,
        evaluated_by=evaluated_by,
        evaluated_at=evaluated_at,
        status=SupplierEvaluationStatus.DRAFT,
        remark=remark or "",
    )
    record_audit(
        action=AuditAction.CREATE,
        instance=evaluation,
        changes={
            "evaluation_no": evaluation.evaluation_no,
            "supplier_id": evaluation.supplier_id,
            "weight_config": config.version_no,
            "missing_dimension_policy": evaluation.missing_dimension_policy,
        },
        reason=evaluation.remark,
        object_repr=evaluation.evaluation_no,
        company=evaluation.company,
        actor=user,
    )
    return evaluation


@transaction.atomic
def set_evaluation_lines(
    user: Any, evaluation: SupplierEvaluation, rows: list[dict[str, Any]]
) -> SupplierEvaluation:
    """整表替换评价明细（仅草稿），并立即重算总分。"""
    require_codes(user, "srm.evaluation.update")
    locked = SupplierEvaluation.objects.select_for_update().get(pk=evaluation.pk)
    if not locked.is_editable:
        raise StateConflict(
            "只有草稿状态的评价单可以录入评分；已生效的评价请归档后重新发起。",
            code="EVALUATION_LOCKED",
        )
    prepared = _prepare_lines(locked, list(rows))
    locked.lines.all().delete()
    # 逐条 create（只有 5 行）：不依赖驱动回填自增主键，随后重算才能落到正确的行上
    for row in prepared:
        SupplierEvaluationLine.objects.create(
            evaluation=locked,
            dimension=row["dimension"],
            raw_score=row["raw_score"],
            raw_observation=row["raw_observation"],
            weight=row["weight"],
            effective_weight=ZERO,
            is_missing=row["raw_score"] is None,
            remark=row["remark"],
        )
    recalculate(locked)
    record_audit(
        action=AuditAction.UPDATE,
        instance=locked,
        changes={
            "lines": [row["dimension"] for row in prepared],
            "total_score": locked.total_score,
            "missing_dimensions": locked.missing_dimensions,
        },
        object_repr=locked.evaluation_no,
        company=locked.company,
        actor=user,
    )
    return locked


@transaction.atomic
def publish_evaluation(user: Any, evaluation: SupplierEvaluation) -> SupplierEvaluation:
    """评价单生效：草稿 → 已生效。没有明细（或还没来得及重算）不允许生效。"""
    require_codes(user, "srm.evaluation.publish")
    locked = SupplierEvaluation.objects.select_for_update().get(pk=evaluation.pk)
    if locked.status != SupplierEvaluationStatus.DRAFT:
        raise StateConflict("只有草稿状态的评价单可以生效。", code="EVALUATION_STATUS_INVALID")
    if not locked.lines.exists():
        raise StateConflict("评价单还没有录入任何维度，不能生效。", code="EVALUATION_LINES_REQUIRED")
    if locked.total_score is None:
        raise StateConflict("评价单总分尚未计算，不能生效。", code="EVALUATION_SCORE_MISSING")
    locked.status = SupplierEvaluationStatus.EFFECTIVE
    if locked.evaluated_at is None:
        locked.evaluated_at = business_now()
    locked.save(update_fields=["status", "evaluated_at", "updated_at"])
    record_audit(
        action=AuditAction.UPDATE,
        instance=locked,
        changes={"status": locked.status, "total_score": locked.total_score, "grade": locked.grade},
        object_repr=locked.evaluation_no,
        company=locked.company,
        actor=user,
    )
    return locked


@transaction.atomic
def archive_evaluation(user: Any, evaluation: SupplierEvaluation) -> SupplierEvaluation:
    """归档评价单；已归档的不能重复归档。"""
    require_codes(user, "srm.evaluation.archive")
    locked = SupplierEvaluation.objects.select_for_update().get(pk=evaluation.pk)
    if locked.status == SupplierEvaluationStatus.ARCHIVED:
        raise StateConflict("该评价单已经归档。", code="EVALUATION_STATUS_INVALID")
    locked.status = SupplierEvaluationStatus.ARCHIVED
    locked.save(update_fields=["status", "updated_at"])
    record_audit(
        action=AuditAction.UPDATE,
        instance=locked,
        changes={"status": locked.status},
        object_repr=locked.evaluation_no,
        company=locked.company,
        actor=user,
    )
    return locked


__all__ = [
    "EVALUATION_CODE_RULE",
    "GRADE_THRESHOLDS",
    "active_weight_config",
    "archive_evaluation",
    "create_evaluation",
    "create_weight_config",
    "derive_weight_config",
    "ensure_single_primary_contact",
    "grade_for",
    "next_evaluation_no",
    "normalize_weights",
    "publish_evaluation",
    "recalculate",
    "require_active_weight_config",
    "set_evaluation_lines",
    "snapshot_weights",
]
