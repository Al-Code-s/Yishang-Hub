"""能源管理业务服务。

约定（与全平台一致）：

* 状态流转只在本模块的服务层发生，视图只做鉴权与参数装配；
* 报警由「读数写入 / 运行记录结束 / 离线扫描」三条真实路径触发，
  不做「页面上点了报警才生成报警」的假流程；
* 同一仪表同一类型同一天只报一次警（去重窗口），避免刷屏；
* 所有金额用 Decimal 并按分/厘四舍五入，禁止 float。
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from django.db.models import Q, Sum

from apps.core.exceptions import StateConflict, ValidationFailed
from apps.core.services import business_now, business_today, generate_code
from apps.ems.models import (
    AlarmLevel,
    AlarmSource,
    AlarmStatus,
    AlarmType,
    EnergyAlarm,
    EnergyMeter,
    EnergyPrice,
    EnergyRunRecord,
    EnergyThreshold,
    MeterReading,
    MeterStatus,
    ReadingSource,
    RunStatus,
    TariffPeriod,
)

METER_CODE_RULE = "EM"
ALARM_CODE_RULE = "EAL"
RUN_RECORD_CODE_RULE = "ERN"

# 金额与单耗的展示精度：金额 4 位（与 money_field 一致），单耗 6 位
MONEY_QUANT = Decimal("0.0001")
QUANTITY_QUANT = Decimal("0.000001")


def next_meter_code() -> str:
    """计量设备编号（编码规则 EM）。"""
    return generate_code(METER_CODE_RULE)


def next_alarm_no() -> str:
    """能源报警编号（编码规则 EAL）。"""
    return generate_code(ALARM_CODE_RULE)


def next_run_record_no() -> str:
    """设备运行记录编号（编码规则 ERN）。"""
    return generate_code(RUN_RECORD_CODE_RULE)


# --------------------------------------------------------------------------
# 价格
# --------------------------------------------------------------------------


def resolve_price(
    company_id: int,
    medium: str,
    *,
    on_date: date | None = None,
    tariff_period: str = TariffPeriod.FLAT,
) -> EnergyPrice | None:
    """取某介质某时段在指定日期生效的单价（多条时取生效日期最新的一条）。"""
    target = on_date or business_today()
    return (
        EnergyPrice.objects.filter(
            company_id=company_id,
            medium=medium,
            tariff_period=tariff_period,
            is_active=True,
            effective_from__lte=target,
        )
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=target))
        .order_by("-effective_from", "-id")
        .first()
    )


def estimate_cost(
    company_id: int,
    medium: str,
    consumption: Decimal,
    *,
    on_date: date | None = None,
    tariff_period: str = TariffPeriod.FLAT,
) -> Decimal:
    """按当期单价把用量折算成费用；没有维护价格时返回 0（不猜价格）。"""
    price = resolve_price(company_id, medium, on_date=on_date, tariff_period=tariff_period)
    if price is None:
        return Decimal("0").quantize(MONEY_QUANT)
    return (Decimal(consumption) * price.unit_price).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


# --------------------------------------------------------------------------
# 报警
# --------------------------------------------------------------------------


def thresholds_for(meter: EnergyMeter) -> list[EnergyThreshold]:
    """匹配到该仪表的生效阈值：指定仪表的 + 该介质通用的。"""
    return list(
        EnergyThreshold.objects.filter(
            company_id=meter.company_id, medium=meter.medium, is_active=True
        ).filter(Q(meter__isnull=True) | Q(meter_id=meter.pk))
    )


def raise_alarm(
    *,
    company_id: int,
    alarm_type: str,
    message: str,
    occurred_at: datetime | None = None,
    level: str = AlarmLevel.WARNING,
    meter: EnergyMeter | None = None,
    source: str = AlarmSource.AUTO,
    triggered_value: Decimal | None = None,
    threshold_value: Decimal | None = None,
    dedupe_window: timedelta | None = None,
    source_ref: str = "",
) -> EnergyAlarm | None:
    """生成报警；同类型、同来源的报警在去重窗口内已存在时不再重复生成。

    ``source_ref`` 是报警的精确来源标识（例如数采测点 ``iot:GW-01:T1``）。
    没有它时只能按「公司 + 类型 + 仪表」去重，一个公司一天内所有设备的越限报警
    会被压成一条；有了它，每台设备的每个测点各自去重，不会互相顶掉。
    """
    moment = occurred_at or business_now()
    if dedupe_window is None:
        window_start = moment.replace(hour=0, minute=0, second=0, microsecond=0)
    else:
        window_start = moment - dedupe_window

    duplicates = EnergyAlarm.objects.filter(
        company_id=company_id,
        alarm_type=alarm_type,
        occurred_at__gte=window_start,
        meter_id=meter.pk if meter is not None else None,
        source_ref=source_ref,
    )
    if duplicates.exists():
        return None

    return EnergyAlarm.objects.create(
        company_id=company_id,
        alarm_no=next_alarm_no(),
        meter=meter,
        area_id=meter.area_id if meter is not None else None,
        alarm_type=alarm_type,
        level=level,
        status=AlarmStatus.PENDING,
        source=source,
        source_ref=source_ref[:128],
        occurred_at=moment,
        message=message[:255],
        triggered_value=triggered_value,
        threshold_value=threshold_value,
    )


def evaluate_thresholds(meter: EnergyMeter, reading: MeterReading) -> list[EnergyAlarm]:
    """按读数与当日用量评估阈值，命中即生成报警（含去重）。"""
    alarms: list[EnergyAlarm] = []
    day_start = reading.reading_at.replace(hour=0, minute=0, second=0, microsecond=0)
    for threshold in thresholds_for(meter):
        if threshold.upper_limit is not None and reading.reading > threshold.upper_limit:
            alarm = raise_alarm(
                company_id=meter.company_id,
                alarm_type=AlarmType.OVER_LIMIT,
                message=f"{meter.name} 读数 {reading.reading} 超过上限 {threshold.upper_limit}",
                occurred_at=reading.reading_at,
                level=threshold.alarm_level,
                meter=meter,
                triggered_value=reading.reading,
                threshold_value=threshold.upper_limit,
            )
            if alarm is not None:
                alarms.append(alarm)
        if threshold.lower_limit is not None and reading.reading < threshold.lower_limit:
            alarm = raise_alarm(
                company_id=meter.company_id,
                alarm_type=AlarmType.OVER_LIMIT,
                message=f"{meter.name} 读数 {reading.reading} 低于下限 {threshold.lower_limit}",
                occurred_at=reading.reading_at,
                level=threshold.alarm_level,
                meter=meter,
                triggered_value=reading.reading,
                threshold_value=threshold.lower_limit,
            )
            if alarm is not None:
                alarms.append(alarm)
        if threshold.daily_limit is not None:
            day_usage = (
                MeterReading.objects.filter(
                    meter=meter, reading_at__gte=day_start, reading_at__lte=reading.reading_at
                ).aggregate(total=Sum("consumption"))["total"]
                or Decimal("0")
            )
            if day_usage > threshold.daily_limit:
                alarm = raise_alarm(
                    company_id=meter.company_id,
                    alarm_type=AlarmType.ENERGY_CONSUMPTION,
                    message=(
                        f"{meter.name} 当日用量 {day_usage} 超过日用量上限 {threshold.daily_limit}"
                    ),
                    occurred_at=reading.reading_at,
                    level=threshold.alarm_level,
                    meter=meter,
                    triggered_value=day_usage,
                    threshold_value=threshold.daily_limit,
                )
                if alarm is not None:
                    alarms.append(alarm)
    return alarms


def handle_alarm(alarm: EnergyAlarm, *, note: str = "", handler=None) -> EnergyAlarm:
    """开始处理报警：待处理 → 处理中。"""
    if alarm.status != AlarmStatus.PENDING:
        raise StateConflict("只有待处理的报警可以开始处理。", code="ALARM_STATUS_INVALID")
    alarm.status = AlarmStatus.HANDLING
    alarm.handled_at = business_now()
    alarm.handle_note = note or alarm.handle_note
    if handler is not None:
        alarm.handler = handler
    alarm.save(update_fields=["status", "handled_at", "handle_note", "handler", "updated_at"])
    return alarm


def close_alarm(alarm: EnergyAlarm, *, note: str = "") -> EnergyAlarm:
    """关闭报警：待处理 / 处理中 → 已关闭，必须写明处理说明。"""
    if alarm.status == AlarmStatus.CLOSED:
        raise StateConflict("该报警已关闭，无需重复关闭。", code="ALARM_STATUS_INVALID")
    text = (note or alarm.handle_note or "").strip()
    if not text:
        raise ValidationFailed("关闭报警必须填写处理说明。", code="ALARM_NOTE_REQUIRED")
    alarm.status = AlarmStatus.CLOSED
    alarm.handle_note = text
    alarm.handled_at = alarm.handled_at or business_now()
    alarm.closed_at = business_now()
    alarm.save(
        update_fields=["status", "handle_note", "handled_at", "closed_at", "updated_at"]
    )
    return alarm


def scan_offline_meters(
    *, now: datetime | None = None, company_id: int | None = None
) -> list[EnergyAlarm]:
    """扫描超时未抄表的仪表并生成离线报警。

    由 ``manage.py ems_offline_check`` 定时调用（不依赖 Celery 才能跑），
    阈值取自 ``EnergyThreshold.offline_minutes``；没有配置离线阈值的仪表不检测，
    避免「全表报警」这种噪音。
    """
    moment = now or business_now()
    thresholds = EnergyThreshold.objects.filter(offline_minutes__gt=0, is_active=True)
    if company_id is not None:
        thresholds = thresholds.filter(company_id=company_id)

    created: list[EnergyAlarm] = []
    for threshold in thresholds:
        meters = EnergyMeter.objects.filter(
            company_id=threshold.company_id, medium=threshold.medium, is_monitored=True, is_active=True
        ).exclude(status=MeterStatus.STOPPED)
        if threshold.meter_id:
            meters = meters.filter(pk=threshold.meter_id)
        deadline = moment - timedelta(minutes=threshold.offline_minutes)
        for meter in meters:
            if meter.last_reading_at is not None and meter.last_reading_at >= deadline:
                continue
            if meter.last_reading_at is None and (meter.install_date or business_today()) > deadline.date():
                # 新装仪表还没到抄表时间，不算离线
                continue
            alarm = raise_alarm(
                company_id=meter.company_id,
                alarm_type=AlarmType.OFFLINE,
                message=(
                    f"{meter.name} 超过 {threshold.offline_minutes} 分钟未抄表"
                    f"（最近抄表：{meter.last_reading_at:%Y-%m-%d %H:%M}）"
                    if meter.last_reading_at
                    else f"{meter.name} 从未抄表，已超过 {threshold.offline_minutes} 分钟"
                ),
                occurred_at=moment,
                level=threshold.alarm_level,
                meter=meter,
            )
            if alarm is not None:
                if meter.status != MeterStatus.OFFLINE:
                    meter.status = MeterStatus.OFFLINE
                    meter.save(update_fields=["status", "updated_at"])
                created.append(alarm)
    return created


# --------------------------------------------------------------------------
# 抄表
# --------------------------------------------------------------------------


@transaction.atomic
def record_reading(
    *,
    meter: EnergyMeter,
    reading: Decimal,
    reading_at: datetime | None = None,
    source: str = ReadingSource.MANUAL,
    tariff_period: str = TariffPeriod.FLAT,
    recorder=None,
    note: str = "",
) -> MeterReading:
    """抄表：计算本次用量、推进仪表最近抄表时间、评估阈值。

    读数回退（小于上一次读数）会被拒绝：仪表只可能因更换/清零回退，
    那种情况需要走「换表」而不是把负数用量写进统计，避免月报被冲成负数。
    """
    value = Decimal(reading)
    if value < 0:
        raise ValidationFailed("表底读数不能为负数。", code="READING_NEGATIVE")
    moment = reading_at or business_now()

    previous = (
        MeterReading.objects.filter(meter=meter)
        .filter(reading_at__lte=moment)
        .order_by("-reading_at", "-id")
        .first()
    )
    if previous is not None and value < previous.reading:
        raise ValidationFailed(
            f"本次读数 {value} 小于上次读数 {previous.reading}，请确认后重新录入。",
            code="READING_ROLLBACK",
            details={"previous_reading": str(previous.reading)},
        )
    delta = value - previous.reading if previous is not None else Decimal("0")
    consumption = (delta * meter.multiplier).quantize(QUANTITY_QUANT)

    record = MeterReading.objects.create(
        company_id=meter.company_id,
        meter=meter,
        reading_at=moment,
        reading=value,
        consumption=consumption,
        tariff_period=tariff_period,
        source=source,
        recorder=recorder,
        note=note,
    )

    meter.last_reading_at = moment
    if meter.status != MeterStatus.STOPPED:
        meter.status = MeterStatus.ONLINE
    meter.save(update_fields=["last_reading_at", "status", "updated_at"])

    evaluate_thresholds(meter, record)
    return record


# --------------------------------------------------------------------------
# 设备运行记录
# --------------------------------------------------------------------------


def start_run_record(
    *,
    meter: EnergyMeter,
    started_at: datetime | None = None,
    equipment=None,
    operator=None,
    output_desc: str = "",
    remark: str = "",
) -> EnergyRunRecord:
    """开始一条设备运行记录（同一仪表不允许两条未结束的记录）。"""
    running = EnergyRunRecord.objects.filter(meter=meter, status=RunStatus.RUNNING).exists()
    if running:
        raise StateConflict("该仪表已有未结束的运行记录，请先结束再开始新记录。", code="RUN_ALREADY_OPEN")
    return EnergyRunRecord.objects.create(
        company_id=meter.company_id,
        record_no=next_run_record_no(),
        meter=meter,
        equipment=equipment if equipment is not None else meter.equipment,
        status=RunStatus.RUNNING,
        started_at=started_at or business_now(),
        operator=operator,
        output_desc=output_desc,
        remark=remark,
    )


@transaction.atomic
def finish_run_record(
    record: EnergyRunRecord,
    *,
    finished_at: datetime | None = None,
    output_qty: Decimal | None = None,
    output_desc: str | None = None,
    energy_consumption: Decimal | None = None,
) -> EnergyRunRecord:
    """结束运行记录：算运行时长、能耗与单耗，并按单耗阈值报警。"""
    if record.status != RunStatus.RUNNING:
        raise StateConflict("只有运行中的记录可以结束。", code="RUN_STATUS_INVALID")
    moment = finished_at or business_now()
    if moment < record.started_at:
        raise ValidationFailed("结束时间不能早于开始时间。", code="RUN_TIME_INVALID")

    if energy_consumption is None:
        total = MeterReading.objects.filter(
            meter_id=record.meter_id, reading_at__gte=record.started_at, reading_at__lte=moment
        ).aggregate(total=Sum("consumption"))["total"]
        energy_consumption = total or Decimal("0")
    energy = Decimal(energy_consumption)
    if energy < 0:
        raise ValidationFailed("能耗用量不能为负数。", code="RUN_CONSUMPTION_NEGATIVE")

    quantity = Decimal(output_qty if output_qty is not None else record.output_qty)
    if quantity < 0:
        raise ValidationFailed("产量不能为负数。", code="RUN_OUTPUT_NEGATIVE")

    record.finished_at = moment
    record.run_minutes = max(0, int((moment - record.started_at).total_seconds() // 60))
    record.energy_consumption = energy
    record.output_qty = quantity
    if output_desc is not None:
        record.output_desc = output_desc
    record.unit_consumption = (
        (energy / quantity).quantize(QUANTITY_QUANT) if quantity > 0 else Decimal("0")
    )
    record.status = RunStatus.FINISHED
    record.save(
        update_fields=[
            "finished_at", "run_minutes", "energy_consumption", "output_qty",
            "output_desc", "unit_consumption", "status", "updated_at",
        ]
    )

    meter = record.meter
    for threshold in thresholds_for(meter):
        limit = threshold.unit_consumption_limit
        if limit is None or quantity <= 0:
            continue
        if record.unit_consumption > limit:
            raise_alarm(
                company_id=record.company_id,
                alarm_type=AlarmType.UNIT_CONSUMPTION,
                message=(
                    f"{meter.name} 单耗 {record.unit_consumption} 超过上限 {limit}"
                    f"（记录 {record.record_no}）"
                ),
                occurred_at=moment,
                level=threshold.alarm_level,
                meter=meter,
                triggered_value=record.unit_consumption,
                threshold_value=limit,
            )
    return record


def cancel_run_record(record: EnergyRunRecord, *, reason: str = "") -> EnergyRunRecord:
    """取消运行记录（未结束的误录记录），必须写明原因。"""
    if record.status != RunStatus.RUNNING:
        raise StateConflict("只有运行中的记录可以取消。", code="RUN_STATUS_INVALID")
    text = (reason or "").strip()
    if not text:
        raise ValidationFailed("取消运行记录必须填写原因。", code="RUN_REASON_REQUIRED")
    record.status = RunStatus.CANCELLED
    record.remark = f"{record.remark}\n取消原因：{text}".strip()
    record.finished_at = record.finished_at or business_now()
    record.save(update_fields=["status", "remark", "finished_at", "updated_at"])
    return record


__all__ = [
    "ALARM_CODE_RULE",
    "METER_CODE_RULE",
    "RUN_RECORD_CODE_RULE",
    "close_alarm",
    "estimate_cost",
    "evaluate_thresholds",
    "finish_run_record",
    "handle_alarm",
    "next_alarm_no",
    "next_meter_code",
    "next_run_record_no",
    "raise_alarm",
    "record_reading",
    "resolve_price",
    "scan_offline_meters",
    "start_run_record",
    "thresholds_for",
]
