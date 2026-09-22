"""客户管理只读统计：投诉与产品评价。

口径与 ``apps/ems/selectors.py``、``apps/iot/selectors.py`` 一致：**统计一律由明细实时
聚合**，不落任何汇总表。投诉被改派、被重新评分，评价被回复之后，统计立刻跟着变，
页面上看到的数与列表页逐条对得上——不会出现「有页面没有真数据」。

两条不粉饰的规则：

* **没有回访就没有满意度**：``satisfaction=0`` 表示客户尚未评价，不计入平均分，
  同时把「未评价」的条数单独返回，避免用 0 分拉低平均值；
* **好评率按已评分数据算**：评价的评分是必填项（1~5 分），因此好评率分母就是评价总数。
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from django.db.models import Count, Q, QuerySet, Sum

from apps.core.selectors import scoped_queryset
from apps.core.services import parse_business_moment, serialise_value
from apps.crm.models import (
    ComplaintLevel,
    ComplaintSource,
    ComplaintStatus,
    ComplaintType,
    CustomerComplaint,
    ProductReview,
    ProductReviewStatus,
)

#: 满意度平均分保留 2 位
SCORE_QUANT = Decimal("0.01")
#: 评分分档（1~5 分各一档）
REVIEW_SCORES = (1, 2, 3, 4, 5)
#: 好评线：4 分及以上算好评
GOOD_SCORE = 4


def _average(total: Any, count: int, *, quant: Decimal = SCORE_QUANT) -> str | None:
    """按「有值的样本」求平均；没有样本时返回 None（而不是 0）。"""
    if not count:
        return None
    return str((Decimal(total or 0) / Decimal(count)).quantize(quant, rounding=ROUND_HALF_UP))


def _distribution(
    queryset: QuerySet, field: str, labels: dict[str, str], *, include_zero: bool = False
) -> list[dict[str, Any]]:
    """把某个枚举字段的分布按「数量倒序」返回，标签取模型里的中文名。"""
    counts = dict(queryset.values_list(field).annotate(total=Count("id")))
    rows = [
        {"value": value, "label": labels.get(value, value), "total": counts.get(value, 0)}
        for value in labels
        if include_zero or counts.get(value)
    ]
    rows.sort(key=lambda row: (-row["total"], list(labels).index(row["value"])))
    return rows


def complaint_statistics(
    user: Any,
    *,
    since: Any = None,
    until: Any = None,
    company_id: int | None = None,
    customer_id: int | None = None,
) -> dict[str, Any]:
    """投诉统计：总量、未关闭、状态/类型/级别分布、满意度平均分。"""
    queryset = scoped_queryset(
        CustomerComplaint.objects.all(), user, company_field="company_id"
    )
    since_at = parse_business_moment(since, field="since")
    until_at = parse_business_moment(until, field="until", end_of_day=True)
    if since_at is not None:
        queryset = queryset.filter(complained_at__gte=since_at)
    if until_at is not None:
        queryset = queryset.filter(complained_at__lt=until_at)
    if company_id is not None:
        queryset = queryset.filter(company_id=company_id)
    if customer_id is not None:
        queryset = queryset.filter(customer_id=customer_id)

    totals = queryset.aggregate(
        total=Count("id"),
        open_total=Count("id", filter=~Q(status=ComplaintStatus.CLOSED)),
        closed_total=Count("id", filter=Q(status=ComplaintStatus.CLOSED)),
        rated_total=Count("id", filter=Q(satisfaction__gt=0)),
        satisfaction_sum=Sum("satisfaction", filter=Q(satisfaction__gt=0)),
    )
    rated_total = totals["rated_total"] or 0
    return {
        "since": serialise_value(since_at),
        "until": serialise_value(until_at),
        "total": totals["total"] or 0,
        "open_total": totals["open_total"] or 0,
        "closed_total": totals["closed_total"] or 0,
        "unrated_total": (totals["total"] or 0) - rated_total,
        "avg_satisfaction": _average(totals["satisfaction_sum"], rated_total),
        "by_status": _distribution(queryset, "status", dict(ComplaintStatus.choices)),
        "by_type": _distribution(queryset, "complaint_type", dict(ComplaintType.choices)),
        "by_level": _distribution(queryset, "level", dict(ComplaintLevel.choices)),
        "by_source": _distribution(queryset, "source", dict(ComplaintSource.choices)),
    }


def product_review_statistics(
    user: Any,
    *,
    since: Any = None,
    until: Any = None,
    company_id: int | None = None,
    customer_id: int | None = None,
) -> dict[str, Any]:
    """产品评价统计：总量、待回复、平均评分、评分分布与好评率。"""
    queryset = scoped_queryset(ProductReview.objects.all(), user, company_field="company_id")
    since_at = parse_business_moment(since, field="since")
    until_at = parse_business_moment(until, field="until", end_of_day=True)
    # 评价日期是 DateField：按日期比较，避免把时区偏移算进「哪一天」
    if since_at is not None:
        queryset = queryset.filter(reviewed_at__gte=since_at.date())
    if until_at is not None:
        queryset = queryset.filter(reviewed_at__lte=until_at.date())
    if company_id is not None:
        queryset = queryset.filter(company_id=company_id)
    if customer_id is not None:
        queryset = queryset.filter(customer_id=customer_id)

    totals = queryset.aggregate(
        total=Count("id"),
        pending_total=Count("id", filter=Q(status=ProductReviewStatus.PENDING)),
        closed_total=Count("id", filter=Q(status=ProductReviewStatus.CLOSED)),
        score_sum=Sum("score"),
        good_total=Count("id", filter=Q(score__gte=GOOD_SCORE)),
    )
    total = totals["total"] or 0
    good_total = totals["good_total"] or 0
    score_counts = dict(queryset.values_list("score").annotate(total=Count("id")))
    return {
        "since": serialise_value(since_at),
        "until": serialise_value(until_at),
        "total": total,
        "pending_total": totals["pending_total"] or 0,
        "closed_total": totals["closed_total"] or 0,
        "avg_score": _average(totals["score_sum"], total),
        "good_total": good_total,
        "good_rate": str(
            (Decimal(good_total) / Decimal(total) * 100).quantize(
                SCORE_QUANT, rounding=ROUND_HALF_UP
            )
            if total
            else Decimal("0").quantize(SCORE_QUANT)
        ),
        "by_status": _distribution(queryset, "status", dict(ProductReviewStatus.choices)),
        "by_score": [
            {
                "value": score,
                "label": f"{score} 分",
                "total": score_counts.get(score, 0),
            }
            for score in REVIEW_SCORES
        ],
    }


__all__ = ["complaint_statistics", "product_review_statistics"]
