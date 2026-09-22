"""生产执行（MES）统计：按明细实时聚合，不落汇总表。

与 `apps/ems/selectors.py`、`apps/qms/selectors.py` 同一口径：工单会被补报工、
会被重判质检，任何「日 / 月产量汇总表」在一次补录之后就会与明细对不上。
这里全部**按工单、工序与报工明细实时聚合**，页面上的数字永远能回到明细核对。

统计口径（刻意如此）：

* 时间窗口按**工单创建时间**（`created_at`）过滤，取业务时区的自然日边界；
* `output_quantity`（产出）与 `qualified_quantity`（合格）都是**末道工序口径**
  （同一件产品经过多道工序，按全部工序求和会重复计数）；
* `process_scrap_rate`（工序报废率）按**工序口径**计算：全部工序报废数 / 全部工序报工数，
  与产出、合格数不是同一分母，因此单独命名、不合并成「一个合格率」；
* 「未判定质检点」统计质检点工序中检验单尚未判定为合格 / 让步的数量——它是
  **不能完工**的直接原因，页面必须能一眼看到。
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from django.db.models import Count, Q, Sum

from apps.core.selectors import scoped_queryset
from apps.core.services import parse_business_moment, serialise_value
from apps.mes.models import (
    ProductionOrder,
    ProductionOrderStatus,
    ProductionOrderStep,
    ProductionReport,
)
from apps.qms.models import QualityJudgement

RATE_QUANT = Decimal("0.01")


def _rate(numerator: Any, denominator: Any) -> str:
    """百分比，保留 2 位；分母为 0 时返回 0.00（不返回 None，便于前端直接显示）。"""
    top = Decimal(numerator or 0)
    bottom = Decimal(denominator or 0)
    if not bottom:
        return str(Decimal("0").quantize(RATE_QUANT))
    return str((top / bottom * 100).quantize(RATE_QUANT, rounding=ROUND_HALF_UP))


def production_statistics(
    user: Any,
    *,
    since: Any = None,
    until: Any = None,
    company_id: int | None = None,
    workshop_id: int | None = None,
) -> dict[str, Any]:
    """生产执行看板：工单量、产出与合格、工序报废与未判定质检点。"""
    orders = scoped_queryset(
        ProductionOrder.objects.all(),
        user,
        company_field="company_id",
        factory_field="factory_id",
    )
    since_at = parse_business_moment(since, field="since")
    until_at = parse_business_moment(until, field="until", end_of_day=True)
    if since_at is not None:
        orders = orders.filter(created_at__gte=since_at)
    if until_at is not None:
        orders = orders.filter(created_at__lt=until_at)
    if company_id is not None:
        orders = orders.filter(company_id=company_id)
    if workshop_id is not None:
        orders = orders.filter(workshop_id=workshop_id)

    totals = orders.aggregate(
        total=Count("id"),
        draft_total=Count("id", filter=Q(status=ProductionOrderStatus.DRAFT)),
        released_total=Count("id", filter=Q(status=ProductionOrderStatus.RELEASED)),
        in_progress_total=Count("id", filter=Q(status=ProductionOrderStatus.IN_PROGRESS)),
        completed_total=Count("id", filter=Q(status=ProductionOrderStatus.COMPLETED)),
        closed_total=Count("id", filter=Q(status=ProductionOrderStatus.CLOSED)),
        cancelled_total=Count("id", filter=Q(status=ProductionOrderStatus.CANCELLED)),
        planned_quantity=Sum("quantity"),
        output_quantity=Sum("completed_quantity"),
        qualified_quantity=Sum("qualified_quantity"),
        scrap_quantity=Sum("scrap_quantity"),
    )
    order_ids = list(orders.values_list("id", flat=True))
    steps = ProductionOrderStep.objects.filter(order_id__in=order_ids)
    step_totals = steps.aggregate(
        reported=Sum("reported_quantity"), scrap=Sum("scrap_quantity")
    )
    pending_gate_total = (
        steps.filter(is_quality_gate=True)
        .filter(
            Q(inspection_order__isnull=True)
            | Q(inspection_order__judgement=QualityJudgement.PENDING)
        )
        .count()
    )
    scrap_by_step = (
        steps.values("name")
        .annotate(scrap=Sum("scrap_quantity"), reported=Sum("reported_quantity"))
        .filter(scrap__gt=0)
        .order_by("-scrap", "name")[:10]
    )
    reports = ProductionReport.objects.filter(order_id__in=order_ids)
    report_totals = reports.aggregate(
        total=Count("id"),
        quantity=Sum("quantity"),
        qualified=Sum("qualified_quantity"),
        scrap=Sum("scrap_quantity"),
        hours=Sum("work_hours"),
    )

    return {
        "since": serialise_value(since_at),
        "until": serialise_value(until_at),
        "total": totals["total"] or 0,
        "draft_total": totals["draft_total"] or 0,
        "released_total": totals["released_total"] or 0,
        "in_progress_total": totals["in_progress_total"] or 0,
        "completed_total": totals["completed_total"] or 0,
        "closed_total": totals["closed_total"] or 0,
        "cancelled_total": totals["cancelled_total"] or 0,
        "planned_quantity": str(Decimal(totals["planned_quantity"] or 0)),
        "output_quantity": str(Decimal(totals["output_quantity"] or 0)),
        "qualified_quantity": str(Decimal(totals["qualified_quantity"] or 0)),
        "scrap_quantity": str(Decimal(totals["scrap_quantity"] or 0)),
        "final_yield_rate": _rate(totals["qualified_quantity"], totals["output_quantity"]),
        "process_reported_quantity": str(Decimal(step_totals["reported"] or 0)),
        "process_scrap_quantity": str(Decimal(step_totals["scrap"] or 0)),
        "process_scrap_rate": _rate(step_totals["scrap"], step_totals["reported"]),
        "pending_gate_total": pending_gate_total,
        "report_total": report_totals["total"] or 0,
        "report_quantity": str(Decimal(report_totals["quantity"] or 0)),
        "report_qualified_quantity": str(Decimal(report_totals["qualified"] or 0)),
        "report_scrap_quantity": str(Decimal(report_totals["scrap"] or 0)),
        "report_work_hours": str(Decimal(report_totals["hours"] or 0)),
        "by_status": [
            {"value": value, "label": label, "total": totals.get(f"{value}_total", 0) or 0}
            for value, label in ProductionOrderStatus.choices
        ],
        "scrap_by_step": [
            {
                "step_name": row["name"],
                "scrap_quantity": str(Decimal(row["scrap"] or 0)),
                "reported_quantity": str(Decimal(row["reported"] or 0)),
                "scrap_rate": _rate(row["scrap"], row["reported"]),
            }
            for row in scrap_by_step
        ],
    }


__all__ = ["production_statistics"]
