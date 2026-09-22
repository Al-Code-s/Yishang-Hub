"""供应商评价的只读统计：按明细实时聚合，不落汇总表。

与 ``apps/qms/selectors.py``、``apps/crm/selectors.py`` 同一口径：评价会被补录、
会被重新录入，任何「评价汇总表」在一次补录之后就会与明细对不上。这里全部
**按评价单与评价明细实时聚合**，页面上的数永远能回到明细逐条核对。

两条不粉饰的规则：

* **平均分只统计「完整口径」的评价**：缺数据且选择「标注缺失」时，总分上限低于 100，
  把它们混进平均分会让平均值莫名偏低；这类评价的条数单独返回（``ungraded_total``）。
* **缺失维度单独计数**：``line_missing_total`` 数的是「没有数据」的维度行，
  与「打了 0 分」完全是两件事。

时间窗口按**评价单登记时间**（``created_at``）过滤，取业务时区的自然日边界。
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from django.db.models import Avg, Count, Q

from apps.core.selectors import scoped_queryset
from apps.core.services import parse_business_moment, serialise_value
from apps.srm.models import (
    EVALUATION_DIMENSIONS,
    EvaluationDimension,
    MissingDimensionPolicy,
    SupplierEvaluation,
    SupplierEvaluationLine,
    SupplierEvaluationStatus,
    SupplierGrade,
)

RATE_QUANT = Decimal("0.01")
DIMENSION_LABELS = dict(EvaluationDimension.choices)
POLICY_LABELS = dict(MissingDimensionPolicy.choices)


def _rate(numerator: int, denominator: int) -> str:
    """百分比，保留 2 位；分母为 0 时返回 0.00（不返回 None，便于前端直接显示）。"""
    if not denominator:
        return str(Decimal("0").quantize(RATE_QUANT))
    return str(
        (Decimal(numerator) / Decimal(denominator) * 100).quantize(
            RATE_QUANT, rounding=ROUND_HALF_UP
        )
    )


def _decimal_or_none(value: Any) -> str | None:
    if value is None:
        return None
    return str(Decimal(value).quantize(RATE_QUANT, rounding=ROUND_HALF_UP))


def evaluation_statistics(
    user: Any,
    *,
    since: Any = None,
    until: Any = None,
    company_id: int | None = None,
    supplier_id: int | None = None,
) -> dict[str, Any]:
    """供应商评价统计：单据量、等级分布、维度均值与缺数据情况。"""
    queryset = scoped_queryset(
        SupplierEvaluation.objects.all(), user, company_field="company_id"
    )
    since_at = parse_business_moment(since, field="since")
    until_at = parse_business_moment(until, field="until", end_of_day=True)
    if since_at is not None:
        queryset = queryset.filter(created_at__gte=since_at)
    if until_at is not None:
        queryset = queryset.filter(created_at__lt=until_at)
    if company_id is not None:
        queryset = queryset.filter(company_id=company_id)
    if supplier_id is not None:
        queryset = queryset.filter(supplier_id=supplier_id)

    totals = queryset.aggregate(
        total=Count("id"),
        draft_total=Count("id", filter=Q(status=SupplierEvaluationStatus.DRAFT)),
        effective_total=Count("id", filter=Q(status=SupplierEvaluationStatus.EFFECTIVE)),
        archived_total=Count("id", filter=Q(status=SupplierEvaluationStatus.ARCHIVED)),
        scored_total=Count("id", filter=Q(total_score__isnull=False)),
        # 「没有等级」= 缺数据且按标注缺失口径处理（或还没录入明细），不参与平均分
        ungraded_total=Count("id", filter=Q(grade="")),
        missing_policy_total=Count(
            "id", filter=Q(missing_dimension_policy=MissingDimensionPolicy.REDISTRIBUTE)
        ),
        supplier_total=Count("supplier_id", distinct=True),
    )
    # 完整口径的平均分：只在有等级（即口径完整、总分满 100）的评价上求平均
    avg_score = queryset.filter(~Q(grade="")).aggregate(value=Avg("total_score"))["value"]

    by_grade = dict(queryset.values_list("grade").annotate(total=Count("id")))
    by_status = dict(queryset.values_list("status").annotate(total=Count("id")))

    lines = SupplierEvaluationLine.objects.filter(evaluation__in=queryset)
    dimension_rows = {
        row["dimension"]: row
        for row in lines.values("dimension").annotate(
            scored_total=Count("id", filter=Q(is_missing=False)),
            missing_total=Count("id", filter=Q(is_missing=True)),
            avg_score=Avg("raw_score", filter=Q(is_missing=False)),
        )
    }
    line_aggregate = lines.aggregate(
        total=Count("id"), missing_total=Count("id", filter=Q(is_missing=True))
    )

    return {
        "since": serialise_value(since_at),
        "until": serialise_value(until_at),
        "total": totals["total"] or 0,
        "draft_total": totals["draft_total"] or 0,
        "effective_total": totals["effective_total"] or 0,
        "archived_total": totals["archived_total"] or 0,
        "scored_total": totals["scored_total"] or 0,
        "ungraded_total": totals["ungraded_total"] or 0,
        "supplier_total": totals["supplier_total"] or 0,
        "avg_total_score": _decimal_or_none(avg_score),
        "missing_policy_total": totals["missing_policy_total"] or 0,
        "line_total": line_aggregate["total"] or 0,
        "line_missing_total": line_aggregate["missing_total"] or 0,
        "missing_rate": _rate(
            line_aggregate["missing_total"] or 0, line_aggregate["total"] or 0
        ),
        "by_grade": [
            {
                "value": value,
                "label": label,
                "total": by_grade.get(value, 0),
            }
            for value, label in SupplierGrade.choices
        ],
        "by_status": [
            {
                "value": value,
                "label": label,
                "total": by_status.get(value, 0),
            }
            for value, label in SupplierEvaluationStatus.choices
        ],
        "by_policy": [
            {
                "value": value,
                "label": POLICY_LABELS[value],
                "total": queryset.filter(missing_dimension_policy=value).count(),
            }
            for value in MissingDimensionPolicy.values
        ],
        "by_dimension": [
            {
                "value": dimension,
                "label": DIMENSION_LABELS[dimension],
                "scored_total": dimension_rows.get(dimension, {}).get("scored_total", 0),
                "missing_total": dimension_rows.get(dimension, {}).get("missing_total", 0),
                "avg_score": _decimal_or_none(
                    dimension_rows.get(dimension, {}).get("avg_score")
                ),
            }
            for dimension in EVALUATION_DIMENSIONS
        ],
    }


__all__ = ["evaluation_statistics"]
