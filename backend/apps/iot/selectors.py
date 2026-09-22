"""设备数采只读查询：按「测点 × 时间桶」实时聚合采集读数。

为什么统计不落汇总表：设备会补发、会重传，同一时刻的读数也可能被重新判定质量。
任何「小时 / 日汇总表」在一次补发之后就会与明细对不上（与 ``apps/ems/selectors.py``
同一口径）——这里全部**按明细实时聚合**，靠 ``(company, point, device_time)`` 索引
把成本压在「测点 × 时间桶」的量级上，页面上的数字永远能回到「采集读数」逐条核对。

分桶按**业务时区**（``YISHANG['BUSINESS_TIME_ZONE']``，默认 Asia/Shanghai）截断：
若按 UTC 截断，北京时间 08:00 之前的读数会被算进前一天（见 ``docs/data-model.md`` 第一节）。

分桶的实现方式是把时间先加上业务时区偏移再截断，**不用** ``TruncDay(..., tzinfo=...)``：
后者会生成 ``CONVERT_TZ(col, 'UTC', 'Asia/Shanghai')``，而 MySQL 的命名时区表常常
没有导入（本项目实测返回 NULL），整张统计表会莫名空掉。偏移量按「当前时刻」取，
对 Asia/Shanghai 这类不实行夏令时的时区恒等于 +08:00；若换用有夏令时的时区，
历史桶的边界会随当前偏移整体平移，届时需改用带时区表的实现。

只读聚合**不写任何表**，也不产生报警：报警只在采集入库时由
``apps/iot/services.py`` 按测点上下限判定。
"""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from django.db.models import (
    Count,
    DateTimeField,
    ExpressionWrapper,
    F,
    Max,
    Min,
    Q,
    QuerySet,
    Sum,
)
from django.db.models.functions import TruncDay, TruncHour

from apps.core.exceptions import ValidationFailed
from apps.core.selectors import scoped_queryset
from apps.core.services import (
    business_now,
    business_timezone,
    parse_business_moment,
    serialise_value,
)
from apps.iot.models import IoTReading

#: 时间桶粒度 → ORM 截断函数
GRANULARITIES: dict[str, Any] = {"hour": TruncHour, "day": TruncDay}
DEFAULT_GRANULARITY = "day"

#: 粒度 → 未指定区间时的默认窗口 / 允许的最大窗口（避免「按小时查三年」把接口拖死）
DEFAULT_WINDOW: dict[str, timedelta] = {
    "hour": timedelta(hours=48),
    "day": timedelta(days=30),
}
MAX_WINDOW: dict[str, timedelta] = {
    "hour": timedelta(days=31),
    "day": timedelta(days=1096),
}

#: 明细行（测点 × 桶）返回上限：超出时按桶倒序截断，并在响应里标记 truncated
ROW_LIMIT = 500
MAX_ROW_LIMIT = 2000
#: 趋势（按桶汇总）返回的最大桶数
MAX_BUCKETS = 200
#: 平均值的小数位，与 ``reading_field`` 的 decimal_places 保持一致
VALUE_QUANT = Decimal("0.000001")


def _average(value_sum: Any, sample_count: int) -> Decimal:
    if not sample_count:
        return Decimal("0").quantize(VALUE_QUANT)
    return (Decimal(value_sum or 0) / Decimal(sample_count)).quantize(
        VALUE_QUANT, rounding=ROUND_HALF_UP
    )


def _business_offset(moment: datetime) -> timedelta:
    """业务时区相对 UTC 的偏移（Asia/Shanghai 恒为 +08:00）。"""
    return moment.astimezone(business_timezone()).utcoffset() or timedelta(0)


def _bucket_field(offset: timedelta) -> Any:
    """把 UTC 存储时间平移到业务时区的「墙上时间」，再交给截断函数分桶。"""
    if not offset:
        return F("device_time")
    return ExpressionWrapper(F("device_time") + offset, output_field=DateTimeField())


def _bucket_instant(bucket: datetime | None, offset: timedelta) -> datetime | None:
    """把「按业务时区截断出来的墙上时间」还原成真正的 UTC 时刻。

    例：Asia/Shanghai 的 2026-09-21 00:00 是 UTC 的 2026-09-20T16:00Z；
    还原之后前端按业务时区渲染，看到的仍是 09-21 这一天的起点。
    """
    if bucket is None:
        return None
    return bucket - offset


def _is_over_limit(row: dict[str, Any]) -> bool:
    upper = row["point__upper_limit"]
    lower = row["point__lower_limit"]
    if upper is not None and row["value_max"] is not None and row["value_max"] > upper:
        return True
    return bool(lower is not None and row["value_min"] is not None and row["value_min"] < lower)


def reading_statistics(
    user: Any,
    *,
    granularity: str = DEFAULT_GRANULARITY,
    since: Any = None,
    until: Any = None,
    company_id: int | None = None,
    gateway_id: int | None = None,
    point_id: int | None = None,
    is_simulated: bool | None = None,
    limit: int = ROW_LIMIT,
) -> dict[str, Any]:
    """按时间桶聚合采集读数（只读，不落汇总表）。

    返回三块内容：``rows``（测点 × 桶的明细聚合）、``buckets``（桶级趋势，
    供前端画曲线）、``totals``（整体口径）。超限只做**标记**（``is_over_limit``），
    不在这里生成报警——报警的判定与去重只发生在采集入库路径上，避免同一份数据两处报警。
    """
    granularity = (granularity or DEFAULT_GRANULARITY).strip()
    if granularity not in GRANULARITIES:
        raise ValidationFailed(
            f"不支持的时间粒度：{granularity}。",
            code="GRANULARITY_NOT_SUPPORTED",
            details={"supported": sorted(GRANULARITIES)},
        )

    moment = business_now()
    until_at = parse_business_moment(until, field="until", end_of_day=True) or moment
    since_at = (
        parse_business_moment(since, field="since") or until_at - DEFAULT_WINDOW[granularity]
    )
    if since_at >= until_at:
        raise ValidationFailed(
            "开始时间必须早于结束时间。",
            code="INVALID_TIME_RANGE",
            details={"since": since_at.isoformat(), "until": until_at.isoformat()},
        )
    window = until_at - since_at
    if window > MAX_WINDOW[granularity]:
        raise ValidationFailed(
            f"按{'小时' if granularity == 'hour' else '天'}统计的时间跨度最多 "
            f"{MAX_WINDOW[granularity].days} 天，当前 {window.days} 天。",
            code="TIME_RANGE_TOO_WIDE",
            details={
                "granularity": granularity,
                "max_days": MAX_WINDOW[granularity].days,
                "window_days": window.days,
            },
        )

    queryset: QuerySet[IoTReading] = scoped_queryset(
        IoTReading.objects.all(), user, company_field="company_id"
    ).filter(device_time__gte=since_at, device_time__lt=until_at)
    if company_id is not None:
        queryset = queryset.filter(company_id=company_id)
    if gateway_id is not None:
        queryset = queryset.filter(gateway_id=gateway_id)
    if point_id is not None:
        queryset = queryset.filter(point_id=point_id)
    if is_simulated is not None:
        queryset = queryset.filter(is_simulated=is_simulated)

    trunc = GRANULARITIES[granularity]
    offset = _business_offset(moment)
    bucket_field = _bucket_field(offset)
    row_limit = max(1, min(int(limit or ROW_LIMIT), MAX_ROW_LIMIT))

    detail = (
        queryset.annotate(bucket=trunc(bucket_field))
        .values(
            "bucket",
            "point_id",
            "point__code",
            "point__name",
            "point__quantity",
            "point__unit",
            "point__lower_limit",
            "point__upper_limit",
            "gateway__code",
        )
        .annotate(
            sample_count=Count("id"),
            simulated_count=Count("id", filter=Q(is_simulated=True)),
            value_sum=Sum("value"),
            value_min=Min("value"),
            value_max=Max("value"),
        )
        .order_by("-bucket", "point__code", "point_id")
    )

    rows = []
    for row in detail[: row_limit + 1]:
        bucket = _bucket_instant(row["bucket"], offset)
        rows.append(
            {
                "bucket": serialise_value(bucket),
                "granularity": granularity,
                "point_id": row["point_id"],
                "point_code": row["point__code"],
                "point_name": row["point__name"],
                "quantity": row["point__quantity"],
                "unit": row["point__unit"] or "",
                "gateway_code": row["gateway__code"],
                "lower_limit": serialise_value(row["point__lower_limit"]),
                "upper_limit": serialise_value(row["point__upper_limit"]),
                "sample_count": row["sample_count"],
                "simulated_count": row["simulated_count"],
                "value_sum": serialise_value(row["value_sum"]),
                "value_min": serialise_value(row["value_min"]),
                "value_max": serialise_value(row["value_max"]),
                "value_avg": str(_average(row["value_sum"], row["sample_count"])),
                "is_over_limit": _is_over_limit(row),
                "is_simulated": row["simulated_count"] >= row["sample_count"],
            }
        )
    truncated = len(rows) > row_limit
    rows = rows[:row_limit]

    bucket_rows = [
        {
            "bucket": serialise_value(_bucket_instant(row["bucket"], offset)),
            "sample_count": row["sample_count"],
            "simulated_count": row["simulated_count"],
            "value_sum": serialise_value(row["value_sum"]),
        }
        for row in (
            queryset.annotate(bucket=trunc(bucket_field))
            .values("bucket")
            .annotate(
                sample_count=Count("id"),
                simulated_count=Count("id", filter=Q(is_simulated=True)),
                value_sum=Sum("value"),
            )
            .order_by("-bucket")[:MAX_BUCKETS]
        )
    ]

    totals = queryset.aggregate(
        sample_count=Count("id"),
        simulated_count=Count("id", filter=Q(is_simulated=True)),
        point_count=Count("point_id", distinct=True),
        gateway_count=Count("gateway_id", distinct=True),
        value_sum=Sum("value"),
    )
    totals = {key: serialise_value(value) for key, value in totals.items()}

    return {
        "granularity": granularity,
        "since": serialise_value(since_at),
        "until": serialise_value(until_at),
        "row_limit": row_limit,
        "truncated": truncated,
        "rows": rows,
        "buckets": bucket_rows,
        "totals": totals,
    }


__all__ = [
    "DEFAULT_GRANULARITY",
    "GRANULARITIES",
    "MAX_WINDOW",
    "ROW_LIMIT",
    "reading_statistics",
]
