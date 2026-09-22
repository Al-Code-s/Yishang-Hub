"""质量信息动态监测：按明细实时聚合，不落汇总表。

与 ``apps/ems/selectors.py``、``apps/iot/selectors.py`` 同一口径：检验单会被补录、
会被重新判定，任何「日 / 月质量汇总表」在一次补录之后就会与明细对不上。
这里全部**按检验单与检验结果实时聚合**，页面上的合格率永远能回到检验单逐条核对。

统计口径（刻意如此）：

* 时间窗口按**检验单登记时间**（``created_at``）过滤，取业务时区的自然日边界；
* **合格率只统计已判定且不是「待判定」的单据**，分母不含草稿与已提交未判定的单据——
  否则「还没检验」会被算成不合格，合格率凭空变低；
* 「让步接收」单独计数，不并入合格，也不并入不合格（它是有记录的例外）。
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from django.db.models import Count, Q

from apps.core.selectors import scoped_queryset
from apps.core.services import parse_business_moment, serialise_value
from apps.qms.models import (
    InspectionCategory,
    QualityAlert,
    QualityAlertLevel,
    QualityAlertStatus,
    QualityInspectionOrder,
    QualityInspectionStatus,
    QualityJudgement,
)

RATE_QUANT = Decimal("0.01")


def _rate(numerator: int, denominator: int) -> str:
    """百分比，保留 2 位；分母为 0 时返回 0.00（不返回 None，便于前端直接显示）。"""
    if not denominator:
        return str(Decimal("0").quantize(RATE_QUANT))
    return str(
        (Decimal(numerator) / Decimal(denominator) * 100).quantize(
            RATE_QUANT, rounding=ROUND_HALF_UP
        )
    )


def inspection_statistics(
    user: Any,
    *,
    since: Any = None,
    until: Any = None,
    company_id: int | None = None,
    inspection_type: str | None = None,
) -> dict[str, Any]:
    """质量信息动态监测：单据量、合格率、分布与未关闭报警。"""
    queryset = scoped_queryset(
        QualityInspectionOrder.objects.all(), user, company_field="company_id"
    )
    since_at = parse_business_moment(since, field="since")
    until_at = parse_business_moment(until, field="until", end_of_day=True)
    if since_at is not None:
        queryset = queryset.filter(created_at__gte=since_at)
    if until_at is not None:
        queryset = queryset.filter(created_at__lt=until_at)
    if company_id is not None:
        queryset = queryset.filter(company_id=company_id)
    if inspection_type:
        queryset = queryset.filter(inspection_type=inspection_type)

    totals = queryset.aggregate(
        total=Count("id"),
        draft_total=Count("id", filter=Q(status=QualityInspectionStatus.DRAFT)),
        submitted_total=Count("id", filter=Q(status=QualityInspectionStatus.SUBMITTED)),
        judged_total=Count("id", filter=~Q(judgement=QualityJudgement.PENDING)),
        passed_total=Count("id", filter=Q(judgement=QualityJudgement.PASSED)),
        failed_total=Count("id", filter=Q(judgement=QualityJudgement.FAILED)),
        concession_total=Count("id", filter=Q(judgement=QualityJudgement.CONCESSION)),
        pending_judgement_total=Count(
            "id",
            filter=Q(
                status=QualityInspectionStatus.JUDGED,
                judgement=QualityJudgement.PENDING,
            ),
        ),
    )
    judged_total = totals["judged_total"] or 0
    passed_total = totals["passed_total"] or 0
    failed_total = totals["failed_total"] or 0
    concession_total = totals["concession_total"] or 0
    qualified_total = passed_total + concession_total

    by_type = dict(queryset.values_list("inspection_type").annotate(total=Count("id")))
    by_judgement = dict(queryset.values_list("judgement").annotate(total=Count("id")))

    # 不合格项目 TOP：哪一类检验项目最容易出问题，直接指向改善方向
    failed_items = (
        queryset.filter(results__is_qualified=False)
        .values("results__item__code", "results__item__name", "results__item__category")
        .annotate(total=Count("results__id"))
        .order_by("-total", "results__item__code")[:10]
    )

    alerts = scoped_queryset(QualityAlert.objects.all(), user, company_field="company_id")
    if company_id is not None:
        alerts = alerts.filter(company_id=company_id)
    alert_totals = alerts.aggregate(
        total=Count("id"),
        open_total=Count(
            "id", filter=Q(status__in=[QualityAlertStatus.OPEN, QualityAlertStatus.HANDLING])
        ),
        closed_total=Count("id", filter=Q(status=QualityAlertStatus.CLOSED)),
    )
    alerts_by_level = dict(alerts.values_list("level").annotate(total=Count("id")))

    return {
        "since": serialise_value(since_at),
        "until": serialise_value(until_at),
        "total": totals["total"] or 0,
        "draft_total": totals["draft_total"] or 0,
        "submitted_total": totals["submitted_total"] or 0,
        "judged_total": judged_total,
        "passed_total": passed_total,
        "failed_total": failed_total,
        "concession_total": concession_total,
        "pending_judgement_total": totals["pending_judgement_total"] or 0,
        "pass_rate": _rate(qualified_total, judged_total),
        "fail_rate": _rate(failed_total, judged_total),
        "by_type": [
            {"value": value, "label": label, "total": by_type.get(value, 0)}
            for value, label in QualityInspectionOrder._meta.get_field(
                "inspection_type"
            ).choices
        ],
        "by_judgement": [
            {"value": value, "label": label, "total": by_judgement.get(value, 0)}
            for value, label in QualityJudgement.choices
        ],
        "failed_items": [
            {
                "item_code": row["results__item__code"],
                "item_name": row["results__item__name"],
                "category": row["results__item__category"],
                "category_label": dict(InspectionCategory.choices).get(
                    row["results__item__category"], row["results__item__category"]
                ),
                "total": row["total"],
            }
            for row in failed_items
        ],
        "alert_total": alert_totals["total"] or 0,
        "alert_open_total": alert_totals["open_total"] or 0,
        "alert_closed_total": alert_totals["closed_total"] or 0,
        "alerts_by_level": [
            {"value": value, "label": label, "total": alerts_by_level.get(value, 0)}
            for value, label in QualityAlertLevel.choices
        ],
    }


__all__ = ["inspection_statistics"]
