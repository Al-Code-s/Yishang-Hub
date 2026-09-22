"""能源管理只读查询：监控视图、统计汇总、报表数据。

为什么统计不落汇总表：抄表数据会被补录、会被纠错，任何「日/月汇总表」在出现
补录后都必须重算，否则报表与明细对不上。这里全部**按明细实时聚合**，
在按 (公司, 介质, 仪表, 时间) 建索引的前提下，性能足够，且永远与明细一致。
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from django.db.models import Count, Q, QuerySet, Sum
from django.db.models.functions import TruncDate, TruncMonth, TruncYear

from apps.core.exceptions import ValidationFailed
from apps.core.selectors import scoped_queryset
from apps.core.services import business_now, business_today
from apps.ems.models import (
    AlarmStatus,
    AlarmType,
    EnergyAlarm,
    EnergyMedium,
    EnergyMeter,
    MeterReading,
    MeterStatus,
    TariffPeriod,
)
from apps.ems.services import estimate_cost, resolve_price

#: 维度 → (主键字段, 编码字段, 名称字段)
ENTITY_DIMENSIONS: dict[str, tuple[str, str, str]] = {
    "meter": ("meter_id", "meter__code", "meter__name"),
    "area": ("meter__area_id", "meter__area__code", "meter__area__name"),
    "department": (
        "meter__department_id",
        "meter__department__code",
        "meter__department__name",
    ),
    "equipment": ("meter__equipment_id", "meter__equipment__code", "meter__equipment__name"),
}

#: 时间维度 → ORM 截断表达式工厂
PERIOD_DIMENSIONS: dict[str, Any] = {
    "day": TruncDate,
    "month": TruncMonth,
    "year": TruncYear,
}

MEDIUM_LABELS = dict(EnergyMedium.choices)
TARIFF_LABELS = dict(TariffPeriod.choices)


def _parse_date(value: Any) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def reading_queryset(
    user: Any,
    *,
    start: Any = None,
    end: Any = None,
    medium: str | None = None,
    area_id: int | None = None,
    department_id: int | None = None,
    meter_id: int | None = None,
    equipment_id: int | None = None,
    tariff_period: str | None = None,
) -> QuerySet[MeterReading]:
    """按数据范围 + 条件过滤抄表明细。"""
    queryset = scoped_queryset(
        MeterReading.objects.select_related("meter", "meter__area", "meter__department"),
        user,
        company_field="company_id",
    )
    start_at = _parse_date(start)
    end_at = _parse_date(end)
    if start_at is not None:
        queryset = queryset.filter(reading_at__date__gte=start_at)
    if end_at is not None:
        queryset = queryset.filter(reading_at__date__lte=end_at)
    if medium:
        queryset = queryset.filter(meter__medium=medium)
    if area_id:
        queryset = queryset.filter(meter__area_id=area_id)
    if department_id:
        queryset = queryset.filter(meter__department_id=department_id)
    if meter_id:
        queryset = queryset.filter(meter_id=meter_id)
    if equipment_id:
        queryset = queryset.filter(meter__equipment_id=equipment_id)
    if tariff_period:
        queryset = queryset.filter(tariff_period=tariff_period)
    return queryset


def consumption_rows(
    user: Any,
    *,
    dimension: str = "meter",
    start: Any = None,
    end: Any = None,
    medium: str | None = None,
    area_id: int | None = None,
    department_id: int | None = None,
    meter_id: int | None = None,
    equipment_id: int | None = None,
    tariff_period: str | None = None,
) -> list[dict[str, Any]]:
    """按维度聚合用能量并按当期单价折算费用。

    费用按 (介质, 时段) 分组分别取价后再汇总；某介质未维护价格时费用计 0，
    并在 ``priced=False`` 上标记出来，由界面提示「未维护单价」，
    而不是拿默认价糊弄出一份看起来完整的成本表。
    """
    if dimension in PERIOD_DIMENSIONS:
        return _period_rows(
            user,
            dimension=dimension,
            start=start,
            end=end,
            medium=medium,
            area_id=area_id,
            department_id=department_id,
            meter_id=meter_id,
            equipment_id=equipment_id,
            tariff_period=tariff_period,
        )
    if dimension not in ENTITY_DIMENSIONS:
        raise ValidationFailed(
            f"不支持的统计维度：{dimension}。",
            code="DIMENSION_NOT_SUPPORTED",
            details={"supported": sorted(ENTITY_DIMENSIONS) + sorted(PERIOD_DIMENSIONS)},
        )

    key_field, code_field, label_field = ENTITY_DIMENSIONS[dimension]
    queryset = reading_queryset(
        user,
        start=start,
        end=end,
        medium=medium,
        area_id=area_id,
        department_id=department_id,
        meter_id=meter_id,
        equipment_id=equipment_id,
        tariff_period=tariff_period,
    )
    rows = (
        queryset.values(
            key_field,
            code_field,
            label_field,
            "meter__medium",
            "meter__unit",
            "tariff_period",
            "company_id",
        )
        .annotate(consumption=Sum("consumption"))
        .order_by()
    )

    on_date = _parse_date(start) or business_today()
    merged: dict[Any, dict[str, Any]] = {}
    for row in rows:
        key = row[key_field]
        bucket = merged.setdefault(
            key,
            {
                "key": key if key is not None else 0,
                "code": row[code_field] or "-",
                "label": row[label_field] or "未指定",
                "unit": row["meter__unit"] or "",
                "medium": row["meter__medium"],
                "medium_label": MEDIUM_LABELS.get(row["meter__medium"], row["meter__medium"]),
                "consumption": Decimal("0"),
                "cost": Decimal("0"),
                "priced": True,
                "periods": [],
            },
        )
        usage = row["consumption"] or Decimal("0")
        bucket["consumption"] += usage
        if resolve_price(row["company_id"], row["meter__medium"], on_date=on_date,
                         tariff_period=row["tariff_period"]) is None:
            bucket["priced"] = False
        bucket["cost"] += estimate_cost(
            row["company_id"],
            row["meter__medium"],
            usage,
            on_date=on_date,
            tariff_period=row["tariff_period"],
        )
        bucket["periods"].append(
            {
                "period": row["tariff_period"],
                "period_label": TARIFF_LABELS.get(row["tariff_period"], row["tariff_period"]),
                "consumption": str(usage),
            }
        )

    result = []
    for bucket in merged.values():
        bucket["consumption"] = str(bucket["consumption"])
        bucket["cost"] = str(bucket["cost"])
        result.append(bucket)
    result.sort(key=lambda item: Decimal(item["consumption"]), reverse=True)
    return result


def _period_rows(user: Any, *, dimension: str, **filters: Any) -> list[dict[str, Any]]:
    trunc = PERIOD_DIMENSIONS[dimension]
    queryset = reading_queryset(user, **filters)
    rows = (
        queryset.annotate(bucket=trunc("reading_at"))
        .values("bucket", "meter__medium", "meter__unit", "tariff_period", "company_id")
        .annotate(consumption=Sum("consumption"))
        .order_by("bucket")
    )
    merged: dict[Any, dict[str, Any]] = {}
    for row in rows:
        key = row["bucket"]
        label = key.strftime("%Y-%m-%d") if dimension == "day" else (
            key.strftime("%Y-%m") if dimension == "month" else key.strftime("%Y")
        )
        bucket = merged.setdefault(
            key,
            {
                "key": label,
                "code": label,
                "label": label,
                "unit": "",
                "medium": row["meter__medium"],
                "medium_label": MEDIUM_LABELS.get(row["meter__medium"], row["meter__medium"]),
                "consumption": Decimal("0"),
                "cost": Decimal("0"),
                "priced": True,
                "periods": [],
            },
        )
        usage = row["consumption"] or Decimal("0")
        bucket["consumption"] += usage
        on_date = key.date() if isinstance(key, datetime) else key
        if resolve_price(row["company_id"], row["meter__medium"], on_date=on_date,
                         tariff_period=row["tariff_period"]) is None:
            bucket["priced"] = False
        bucket["cost"] += estimate_cost(
            row["company_id"],
            row["meter__medium"],
            usage,
            on_date=on_date,
            tariff_period=row["tariff_period"],
        )
        bucket["periods"].append(
            {
                "period": row["tariff_period"],
                "period_label": TARIFF_LABELS.get(row["tariff_period"], row["tariff_period"]),
                "consumption": str(usage),
            }
        )
    result = []
    for key in sorted(merged):
        bucket = merged[key]
        bucket["consumption"] = str(bucket["consumption"])
        bucket["cost"] = str(bucket["cost"])
        result.append(bucket)
    return result


def peak_valley_rows(
    user: Any,
    *,
    medium: str,
    start: Any = None,
    end: Any = None,
    dimension: str = "medium",
) -> list[dict[str, Any]]:
    """尖峰平谷分时段用量：按「时段」或「时段 + 日期」展开。"""
    queryset = reading_queryset(user, start=start, end=end, medium=medium)
    if dimension == "day":
        rows = (
            queryset.annotate(bucket=TruncDate("reading_at"))
            .values("bucket", "tariff_period", "company_id")
            .annotate(consumption=Sum("consumption"))
            .order_by("bucket")
        )
        result = []
        for row in rows:
            usage = row["consumption"] or Decimal("0")
            on_date = row["bucket"]
            result.append(
                {
                    "key": row["bucket"].strftime("%Y-%m-%d"),
                    "code": row["bucket"].strftime("%Y-%m-%d"),
                    "label": row["bucket"].strftime("%Y-%m-%d"),
                    "period": row["tariff_period"],
                    "period_label": TARIFF_LABELS.get(row["tariff_period"], row["tariff_period"]),
                    "consumption": str(usage),
                    "cost": str(
                        estimate_cost(
                            row["company_id"],
                            medium,
                            usage,
                            on_date=on_date,
                            tariff_period=row["tariff_period"],
                        )
                    ),
                }
            )
        return result

    rows = (
        queryset.values("tariff_period", "company_id", "meter__unit")
        .annotate(consumption=Sum("consumption"))
        .order_by()
    )
    result = []
    for row in rows:
        usage = row["consumption"] or Decimal("0")
        result.append(
            {
                "key": row["tariff_period"],
                "code": row["tariff_period"],
                "label": TARIFF_LABELS.get(row["tariff_period"], row["tariff_period"]),
                "period": row["tariff_period"],
                "period_label": TARIFF_LABELS.get(row["tariff_period"], row["tariff_period"]),
                "unit": row["meter__unit"] or "",
                "consumption": str(usage),
                "cost": str(
                    estimate_cost(
                        row["company_id"], medium, usage, tariff_period=row["tariff_period"]
                    )
                ),
            }
        )
    order = {period: index for index, period in enumerate(TariffPeriod.values)}
    result.sort(key=lambda item: order.get(item["period"], 99))
    return result


def meter_monitor_queryset(
    user: Any,
    *,
    medium: str | None = None,
    area_id: int | None = None,
    status: str | None = None,
    search: str | None = None,
    company_id: int | None = None,
    monitored_only: bool = False,
) -> QuerySet[EnergyMeter]:
    """设备监控列表：仪表 + 最近抄表 + 本期用量。"""
    queryset = scoped_queryset(
        EnergyMeter.objects.select_related("area", "department", "equipment", "company"),
        user,
        company_field="company_id",
    )
    if medium:
        queryset = queryset.filter(medium=medium)
    if area_id:
        queryset = queryset.filter(area_id=area_id)
    if status:
        queryset = queryset.filter(status=status)
    if company_id:
        queryset = queryset.filter(company_id=company_id)
    if monitored_only:
        queryset = queryset.filter(is_monitored=True)
    if search:
        queryset = queryset.filter(
            Q(code__icontains=search) | Q(name__icontains=search) | Q(location__icontains=search)
        )

    month_start = business_today().replace(day=1)
    return queryset.annotate(
        month_consumption=Sum(
            "readings__consumption",
            filter=Q(readings__reading_at__date__gte=month_start),
        ),
        open_alarm_count=Count(
            "alarms",
            filter=Q(alarms__status__in=[AlarmStatus.PENDING, AlarmStatus.HANDLING]),
            distinct=True,
        ),
    ).order_by("code")


def last_readings(meter_ids: list[int]) -> dict[int, MeterReading]:
    """批量取每台仪表最近一次抄表，避免界面逐行查库。"""
    if not meter_ids:
        return {}
    rows = (
        MeterReading.objects.filter(meter_id__in=meter_ids)
        .order_by("meter_id", "-reading_at", "-id")
        .values("meter_id", "reading", "reading_at", "consumption")
    )
    result: dict[int, MeterReading] = {}
    for row in rows:
        if row["meter_id"] in result:
            continue
        record = MeterReading(
            meter_id=row["meter_id"],
            reading=row["reading"],
            reading_at=row["reading_at"],
            consumption=row["consumption"],
        )
        result[row["meter_id"]] = record
    return result


def home_summary(user: Any, *, company_id: int | None = None) -> dict[str, Any]:
    """能源首页：今日/本月用量与费用、仪表状态、未处理报警、用量排行与趋势。"""
    today = business_today()
    month_start = today.replace(day=1)
    moment = business_now()

    def _totals(start: date, end: date) -> dict[str, Any]:
        by_medium: dict[str, dict[str, str]] = defaultdict(
            lambda: {"consumption": "0", "cost": "0"}
        )
        rows = (
            reading_queryset(user, start=start, end=end)
            .values("meter__medium", "tariff_period", "company_id")
            .annotate(consumption=Sum("consumption"))
            .order_by()
        )
        total_consumption = Decimal("0")
        total_cost = Decimal("0")
        for row in rows:
            usage = row["consumption"] or Decimal("0")
            cost = estimate_cost(
                row["company_id"],
                row["meter__medium"],
                usage,
                on_date=end,
                tariff_period=row["tariff_period"],
            )
            bucket = by_medium[row["meter__medium"]]
            bucket["consumption"] = str(Decimal(bucket["consumption"]) + usage)
            bucket["cost"] = str(Decimal(bucket["cost"]) + cost)
            total_consumption += usage
            total_cost += cost
        for medium, label in EnergyMedium.choices:
            by_medium.setdefault(medium, {"consumption": "0", "cost": "0"})
            by_medium[medium]["label"] = label
        return {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "total_consumption": str(total_consumption),
            "total_cost": str(total_cost),
            "by_medium": by_medium,
        }

    # 单独统计仪表状态：把聚合注解与 values() 混在一起会让分组口径变得难以解释
    status_queryset = scoped_queryset(
        EnergyMeter.objects.filter(is_monitored=True, is_active=True),
        user,
        company_field="company_id",
    )
    if company_id:
        status_queryset = status_queryset.filter(company_id=company_id)
    status_rows = status_queryset.values("status").annotate(total=Count("id"))
    status_counts = {row["status"]: row["total"] for row in status_rows}

    alarms = scoped_queryset(EnergyAlarm.objects.all(), user, company_field="company_id")
    if company_id:
        alarms = alarms.filter(company_id=company_id)
    open_alarms = alarms.exclude(status=AlarmStatus.CLOSED).count()
    pending_alarms = alarms.filter(status=AlarmStatus.PENDING).count()
    today_alarms = alarms.filter(occurred_at__date=today).count()

    trend_start = today - timedelta(days=13)
    trend_rows = (
        reading_queryset(user, start=trend_start, end=today)
        .annotate(bucket=TruncDate("reading_at"))
        .values("bucket")
        .annotate(consumption=Sum("consumption"))
        .order_by("bucket")
    )
    trend = {row["bucket"].strftime("%Y-%m-%d"): str(row["consumption"] or 0) for row in trend_rows}
    trend_series = [
        {
            "date": (trend_start + timedelta(days=offset)).isoformat(),
            "consumption": trend.get((trend_start + timedelta(days=offset)).isoformat(), "0"),
        }
        for offset in range(14)
    ]

    ranking = consumption_rows(user, dimension="meter", start=month_start, end=today)[:5]

    return {
        "generated_at": moment.isoformat(),
        "today": _totals(today, today),
        "month": _totals(month_start, today),
        "meters": {
            "total": sum(status_counts.values()),
            "online": status_counts.get(MeterStatus.ONLINE, 0),
            "offline": status_counts.get(MeterStatus.OFFLINE, 0),
            "stopped": status_counts.get(MeterStatus.STOPPED, 0),
            "monitored": status_counts.get(MeterStatus.ONLINE, 0) + status_counts.get(MeterStatus.OFFLINE, 0),
        },
        "alarms": {
            "open": open_alarms,
            "pending": pending_alarms,
            "today": today_alarms,
            "by_type": {
                row["alarm_type"]: row["total"]
                for row in alarms.exclude(status=AlarmStatus.CLOSED)
                .values("alarm_type")
                .annotate(total=Count("id"))
            },
        },
        "trend": trend_series,
        "ranking": ranking,
    }


def alarm_type_options() -> list[dict[str, str]]:
    return [{"value": value, "label": label} for value, label in AlarmType.choices]


__all__ = [
    "ENTITY_DIMENSIONS",
    "MEDIUM_LABELS",
    "PERIOD_DIMENSIONS",
    "TARIFF_LABELS",
    "alarm_type_options",
    "consumption_rows",
    "home_summary",
    "last_readings",
    "meter_monitor_queryset",
    "peak_valley_rows",
    "reading_queryset",
]
