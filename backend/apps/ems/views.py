"""能源管理接口。

分层约定（与全平台一致）：

* View 只做鉴权 + 参数装配 + 调用服务，状态流转全部在 ``services`` 里；
* 统计/报表/首页/监控是**只读聚合**，读的是抄表明细，不读任何汇总缓存；
* 导出 Excel 走 openpyxl 真实生成 xlsx，导出行为写入审计日志。
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from io import BytesIO
from typing import Any

from django.http import HttpResponse
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.exceptions import StateConflict
from apps.core.models import AuditAction
from apps.core.pagination import StandardPagination
from apps.core.permissions import HasRequiredPermissions
from apps.core.selectors import assert_in_scope
from apps.core.services import record_audit
from apps.core.viewsets import ActiveFilterMixin, ReadOnlyScopedViewSet, ScopedModelViewSet
from apps.ems import selectors, services
from apps.ems.models import (
    AlarmStatus,
    EnergyAlarm,
    EnergyArea,
    EnergyMeter,
    EnergyPrice,
    EnergyRunRecord,
    EnergyThreshold,
    MeterReading,
)
from apps.ems.serializers import (
    AlarmCloseSerializer,
    AlarmHandleSerializer,
    EnergyAlarmSerializer,
    EnergyAreaSerializer,
    EnergyMeterSerializer,
    EnergyPriceSerializer,
    EnergyRunRecordSerializer,
    EnergyThresholdSerializer,
    MeterReadingSerializer,
    ReadingRecordSerializer,
    RunCancelSerializer,
    RunFinishSerializer,
    RunStartSerializer,
)


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _str_or_none(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _decimal(value: Any) -> Decimal:
    """把 API 里的字符串数值转回 Decimal 做汇总（不经过 float）。"""
    return Decimal(str(value or "0"))


def _sum_decimal(values: Any) -> str:
    return str(sum((_decimal(value) for value in values), Decimal("0")))


class EnergyAreaViewSet(ActiveFilterMixin, ScopedModelViewSet):
    queryset = EnergyArea.objects.select_related("company", "parent", "department", "manager").all()
    serializer_class = EnergyAreaSerializer
    scope_fields = {"company_field": "company_id"}
    audit_fields = (
        "code", "name", "parent_id", "department_id", "manager_id", "area_size", "is_active"
    )
    search_fields = ["code", "name"]
    filterset_fields = ["company_id", "parent_id", "department_id", "manager_id"]
    ordering_fields = ["id", "code", "name", "updated_at"]
    uniqueness_error_map = {"uq_energy_area_company_code": "同一公司下区域编码已存在。"}
    required_permissions = {
        "list": "ems.area.view",
        "retrieve": "ems.area.view",
        "create": "ems.area.create",
        "partial_update": "ems.area.update",
        "set_active": "ems.area.update",
    }


class EnergyMeterViewSet(ActiveFilterMixin, ScopedModelViewSet):
    queryset = EnergyMeter.objects.select_related(
        "company", "area", "department", "equipment"
    ).all()
    serializer_class = EnergyMeterSerializer
    scope_fields = {"company_field": "company_id"}
    audit_fields = (
        "code", "name", "medium", "area_id", "equipment_id", "department_id", "multiplier",
        "unit", "status", "location", "is_monitored", "is_active",
    )
    search_fields = ["code", "name", "location", "serial_no"]
    filterset_fields = ["company_id", "medium", "area_id", "department_id", "equipment_id", "status"]
    ordering_fields = ["id", "code", "name", "last_reading_at", "updated_at"]
    uniqueness_error_map = {"uq_energy_meter_company_code": "同一公司下仪表编码已存在。"}
    required_permissions = {
        "list": "ems.meter.view",
        "retrieve": "ems.meter.view",
        "create": "ems.meter.create",
        "partial_update": "ems.meter.update",
        "set_active": "ems.meter.update",
    }

    def perform_create(self, serializer) -> None:
        """仪表编码留空时按编码规则（EM）自动取号。"""
        code = str(serializer.validated_data.get("code") or "").strip()
        serializer.validated_data["code"] = code or services.next_meter_code()
        super().perform_create(serializer)


class EnergyPriceViewSet(ActiveFilterMixin, ScopedModelViewSet):
    queryset = EnergyPrice.objects.select_related("company").all()
    serializer_class = EnergyPriceSerializer
    scope_fields = {"company_field": "company_id"}
    audit_fields = (
        "medium", "tariff_period", "name", "unit_price", "effective_from", "effective_to",
        "is_active",
    )
    search_fields = ["name"]
    filterset_fields = ["company_id", "medium", "tariff_period", "is_active"]
    ordering_fields = ["id", "medium", "tariff_period", "effective_from"]
    uniqueness_error_map = {
        "uq_energy_price_company_medium_period_from": "同介质同时段同生效日期已维护价格。"
    }
    required_permissions = {
        "list": "ems.price.view",
        "retrieve": "ems.price.view",
        "create": "ems.price.create",
        "partial_update": "ems.price.update",
        "set_active": "ems.price.update",
    }


class EnergyThresholdViewSet(ActiveFilterMixin, ScopedModelViewSet):
    queryset = EnergyThreshold.objects.select_related("company", "meter").all()
    serializer_class = EnergyThresholdSerializer
    scope_fields = {"company_field": "company_id"}
    audit_fields = (
        "name", "medium", "meter_id", "upper_limit", "lower_limit", "daily_limit",
        "unit_consumption_limit", "offline_minutes", "alarm_level", "is_active",
    )
    search_fields = ["name"]
    filterset_fields = ["company_id", "medium", "meter_id", "alarm_level"]
    ordering_fields = ["id", "medium", "name"]
    uniqueness_error_map = {"uq_energy_threshold_company_name": "同一公司下阈值名称已存在。"}
    required_permissions = {
        "list": "ems.threshold.view",
        "retrieve": "ems.threshold.view",
        "create": "ems.threshold.create",
        "partial_update": "ems.threshold.update",
        "set_active": "ems.threshold.update",
    }


class MeterReadingViewSet(ReadOnlyScopedViewSet):
    """抄表读数：只读列表 + 「抄表」动作。

    读数一经录入即为事实，不提供 PATCH：录错了应重新抄表纠偏或作废换表，
    而不是悄悄改历史数字把报表做平。
    """

    queryset = MeterReading.objects.select_related("company", "meter", "recorder").all()
    serializer_class = MeterReadingSerializer
    scope_fields = {"company_field": "company_id"}
    search_fields = ["note", "meter__code", "meter__name"]
    filterset_fields = ["company_id", "meter_id", "tariff_period", "source", "meter__medium"]
    ordering_fields = ["id", "reading_at", "consumption"]
    required_permissions = {
        "list": "ems.reading.view",
        "retrieve": "ems.reading.view",
        "record": "ems.reading.create",
    }

    @extend_schema(request=ReadingRecordSerializer, responses={201: MeterReadingSerializer})
    @action(detail=False, methods=["post"], url_path="record")
    def record(self, request, *args, **kwargs) -> Response:
        """抄表：用量由服务层按上次读数计算，越权仪表被数据范围拦截。"""
        payload = ReadingRecordSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        meter = data["meter_id"]
        assert_in_scope(meter, request.user, company_field="company_id")
        record = services.record_reading(
            meter=meter,
            reading=data["reading"],
            reading_at=data.get("reading_at"),
            source=data.get("source") or "manual",
            tariff_period=data.get("tariff_period") or "flat",
            recorder=data.get("recorder_id"),
            note=data.get("note") or "",
        )
        record_audit(
            action=AuditAction.CREATE,
            instance=record,
            changes={
                "meter": meter.code,
                "reading": str(record.reading),
                "consumption": str(record.consumption),
            },
            object_repr=f"{meter.code} 读数 {record.reading}",
        )
        return Response(self.get_serializer(record).data, status=status.HTTP_201_CREATED)


class EnergyRunRecordViewSet(ReadOnlyScopedViewSet):
    """设备运行记录：只读 + 「开始 / 结束 / 取消」，状态由服务层推进。"""

    queryset = EnergyRunRecord.objects.select_related(
        "company", "meter", "equipment", "operator"
    ).all()
    serializer_class = EnergyRunRecordSerializer
    scope_fields = {"company_field": "company_id"}
    search_fields = ["record_no", "meter__code", "meter__name", "output_desc"]
    filterset_fields = ["company_id", "meter_id", "equipment_id", "status"]
    ordering_fields = ["id", "started_at", "run_minutes", "unit_consumption"]
    required_permissions = {
        "list": "ems.run_record.view",
        "retrieve": "ems.run_record.view",
        "start": "ems.run_record.create",
        "finish": "ems.run_record.execute",
        "cancel": "ems.run_record.execute",
    }

    @extend_schema(request=RunStartSerializer, responses={201: EnergyRunRecordSerializer})
    @action(detail=False, methods=["post"], url_path="start")
    def start(self, request, *args, **kwargs) -> Response:
        payload = RunStartSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        meter = data["meter_id"]
        assert_in_scope(meter, request.user, company_field="company_id")
        record = services.start_run_record(
            meter=meter,
            started_at=data.get("started_at"),
            equipment=data.get("equipment_id"),
            operator=data.get("operator_id"),
            output_desc=data.get("output_desc") or "",
            remark=data.get("remark") or "",
        )
        record_audit(
            action=AuditAction.CREATE,
            instance=record,
            changes={"meter": meter.code, "status": record.status},
            object_repr=record.record_no,
        )
        return Response(self.get_serializer(record).data, status=status.HTTP_201_CREATED)

    @extend_schema(request=RunFinishSerializer, responses={200: EnergyRunRecordSerializer})
    @action(detail=True, methods=["post"], url_path="finish")
    def finish(self, request, *args, **kwargs) -> Response:
        record = self.get_object()
        payload = RunFinishSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        before = {
            "status": record.status,
            "energy_consumption": str(record.energy_consumption),
            "unit_consumption": str(record.unit_consumption),
        }
        updated = services.finish_run_record(
            record,
            finished_at=data.get("finished_at"),
            output_qty=data.get("output_qty"),
            output_desc=data.get("output_desc"),
            energy_consumption=data.get("energy_consumption"),
        )
        record_audit(
            action=AuditAction.UPDATE,
            instance=updated,
            changes={
                **before,
                "status": updated.status,
                "energy_consumption": str(updated.energy_consumption),
                "unit_consumption": str(updated.unit_consumption),
            },
            object_repr=updated.record_no,
        )
        return Response(self.get_serializer(updated).data)

    @extend_schema(request=RunCancelSerializer, responses={200: EnergyRunRecordSerializer})
    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request, *args, **kwargs) -> Response:
        record = self.get_object()
        payload = RunCancelSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        updated = services.cancel_run_record(record, reason=payload.validated_data["reason"])
        record_audit(
            action=AuditAction.UPDATE,
            instance=updated,
            changes={"status": updated.status},
            reason=payload.validated_data["reason"],
            object_repr=updated.record_no,
        )
        return Response(self.get_serializer(updated).data)


class EnergyAlarmViewSet(ActiveFilterMixin, ScopedModelViewSet):
    """报警管理：人工上报走 create（source=manual / 编号自动），处理走动作接口。"""

    queryset = EnergyAlarm.objects.select_related(
        "company", "meter", "area", "handler"
    ).all()
    serializer_class = EnergyAlarmSerializer
    scope_fields = {"company_field": "company_id"}
    audit_fields = (
        "alarm_no", "meter_id", "alarm_type", "level", "status", "occurred_at", "message",
    )
    search_fields = ["alarm_no", "message", "meter__code", "meter__name"]
    filterset_fields = ["company_id", "meter_id", "area_id", "alarm_type", "level", "status"]
    ordering_fields = ["id", "alarm_no", "occurred_at", "level"]
    uniqueness_error_map = {"uq_energy_alarm_company_no": "报警编号已存在。"}
    required_permissions = {
        "list": "ems.alarm.view",
        "retrieve": "ems.alarm.view",
        "create": "ems.alarm.create",
        "partial_update": "ems.alarm.update",
        "handle": "ems.alarm.handle",
        "close": "ems.alarm.handle",
        "scan_offline": "ems.alarm.handle",
    }

    def perform_create(self, serializer) -> None:
        """人工上报报警：编号自动、来源人工、初始状态待处理、公司按仪表推导。"""
        data = serializer.validated_data
        meter = data.get("meter")
        if data.get("company") is None and meter is not None:
            data["company"] = meter.company
        if data.get("company") is None:
            raise StateConflict("人工上报报警必须指定公司或计量设备。", code="COMPANY_REQUIRED")
        data["alarm_no"] = str(data.get("alarm_no") or "").strip() or services.next_alarm_no()
        serializer.validated_data["source"] = "manual"
        serializer.validated_data["status"] = AlarmStatus.PENDING
        super().perform_create(serializer)

    @extend_schema(request=AlarmHandleSerializer, responses={200: EnergyAlarmSerializer})
    @action(detail=True, methods=["post"], url_path="handle")
    def handle(self, request, *args, **kwargs) -> Response:
        alarm = self.get_object()
        payload = AlarmHandleSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        updated = services.handle_alarm(
            alarm,
            note=payload.validated_data.get("note") or "",
            handler=payload.validated_data.get("handler_id"),
        )
        record_audit(
            action=AuditAction.UPDATE,
            instance=updated,
            changes={"status": updated.status},
            object_repr=updated.alarm_no,
        )
        return Response(self.get_serializer(updated).data)

    @extend_schema(request=AlarmCloseSerializer, responses={200: EnergyAlarmSerializer})
    @action(detail=True, methods=["post"], url_path="close")
    def close(self, request, *args, **kwargs) -> Response:
        alarm = self.get_object()
        payload = AlarmCloseSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        updated = services.close_alarm(alarm, note=payload.validated_data["note"])
        record_audit(
            action=AuditAction.UPDATE,
            instance=updated,
            changes={"status": updated.status},
            reason=payload.validated_data["note"],
            object_repr=updated.alarm_no,
        )
        return Response(self.get_serializer(updated).data)

    @extend_schema(responses={200: dict})
    @action(detail=False, methods=["post"], url_path="scan-offline")
    def scan_offline(self, request, *args, **kwargs) -> Response:
        """立即执行一次离线扫描（与 ``manage.py ems_offline_check`` 同一服务）。"""
        created = services.scan_offline_meters(company_id=_int_or_none(request.data.get("company_id")))
        return Response(
            {
                "created": len(created),
                "alarms": [
                    {"id": alarm.pk, "alarm_no": alarm.alarm_no, "message": alarm.message}
                    for alarm in created
                ],
            }
        )


class EnergyMonitorView(APIView):
    """设备监控：仪表状态 + 最近抄表 + 本月用量 + 未处理报警数。"""

    permission_classes = [HasRequiredPermissions]
    required_permissions = {"GET": "ems.monitor.view"}

    @extend_schema(responses={200: dict})
    def get(self, request, *args, **kwargs) -> Response:
        queryset = selectors.meter_monitor_queryset(
            request.user,
            medium=_str_or_none(request.query_params.get("medium")),
            area_id=_int_or_none(request.query_params.get("area_id")),
            status=_str_or_none(request.query_params.get("status")),
            search=_str_or_none(request.query_params.get("search")),
            company_id=_int_or_none(request.query_params.get("company_id")),
        )
        meter_ids = list(queryset.values_list("id", flat=True))
        last = selectors.last_readings(meter_ids)
        rows = []
        for meter in queryset:
            reading = last.get(meter.pk)
            rows.append(
                {
                    "id": meter.pk,
                    "code": meter.code,
                    "name": meter.name,
                    "medium": meter.medium,
                    "medium_display": meter.get_medium_display(),
                    "unit": meter.unit,
                    "status": meter.status,
                    "status_display": meter.get_status_display(),
                    "area_name": meter.area.name if meter.area_id else "",
                    "department_name": meter.department.name if meter.department_id else "",
                    "equipment_name": meter.equipment.name if meter.equipment_id else "",
                    "location": meter.location,
                    "last_reading": str(reading.reading) if reading else None,
                    "last_reading_at": reading.reading_at.isoformat() if reading else None,
                    "last_consumption": str(reading.consumption) if reading else None,
                    "month_consumption": str(meter.month_consumption or 0),
                    "open_alarm_count": meter.open_alarm_count or 0,
                    "is_monitored": meter.is_monitored,
                }
            )
        paginator = StandardPagination()
        page = paginator.paginate_queryset(rows, request, view=self)
        return paginator.get_paginated_response(page)


class EnergyHomeView(APIView):
    """能源首页：今日/本月用量与费用、仪表状态、报警与趋势。"""

    permission_classes = [HasRequiredPermissions]
    required_permissions = {"GET": "ems.home.view"}

    @extend_schema(responses={200: dict})
    def get(self, request, *args, **kwargs) -> Response:
        return Response(
            selectors.home_summary(
                request.user, company_id=_int_or_none(request.query_params.get("company_id"))
            )
        )


class EnergyStatisticsView(APIView):
    """能耗统计：按介质、区域、部门、设备、仪表或时间维度聚合。

    「用水 / 用电 / 用气 / 用液统计」页面是把本接口的 ``medium`` 参数固定为对应介质，
    不存在四份重复的聚合逻辑。
    """

    permission_classes = [HasRequiredPermissions]
    required_permissions = {"GET": "ems.statistics.view"}

    @extend_schema(responses={200: dict})
    def get(self, request, *args, **kwargs) -> Response:
        params = request.query_params
        dimension = (_str_or_none(params.get("dimension")) or "meter")
        rows = selectors.consumption_rows(
            request.user,
            dimension=dimension,
            start=_str_or_none(params.get("start")),
            end=_str_or_none(params.get("end")),
            medium=_str_or_none(params.get("medium")),
            area_id=_int_or_none(params.get("area_id")),
            department_id=_int_or_none(params.get("department_id")),
            meter_id=_int_or_none(params.get("meter_id")),
            equipment_id=_int_or_none(params.get("equipment_id")),
            tariff_period=_str_or_none(params.get("tariff_period")),
        )
        return Response(
            {
                "dimension": dimension,
                "start": _str_or_none(params.get("start")),
                "end": _str_or_none(params.get("end")),
                "rows": rows,
                "totals": {
                    "row_count": len(rows),
                    "unpriced": sum(1 for row in rows if not row["priced"]),
                    "consumption": _sum_decimal(row["consumption"] for row in rows),
                    "cost": _sum_decimal(row["cost"] for row in rows),
                },
            }
        )


def _xlsx_response(rows: list[dict[str, Any]], *, title: str) -> HttpResponse:
    """把统计行导出为真正的 xlsx（openpyxl），而不是改后缀的 CSV。"""
    from openpyxl import Workbook
    from openpyxl.styles import Font

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = title[:31] or "能耗报表"
    headers = ["维度", "编码", "名称", "介质", "用量", "单位", "费用", "单价状态"]
    sheet.append(headers)
    for cell in sheet[1]:
        cell.font = Font(bold=True)
    for row in rows:
        sheet.append(
            [
                row.get("label", ""),
                row.get("code", ""),
                row.get("label", ""),
                row.get("medium_label", ""),
                float(_decimal(row.get("consumption"))),
                row.get("unit", ""),
                float(_decimal(row.get("cost"))),
                "已维护单价" if row.get("priced") else "未维护单价",
            ]
        )
    for column, width in zip("ABCDEFGH", (18, 20, 24, 10, 16, 10, 16, 14), strict=False):
        sheet.column_dimensions[column].width = width

    buffer = BytesIO()
    workbook.save(buffer)
    response = HttpResponse(
        buffer.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    filename = f"energy-report-{date.today():%Y%m%d}.xlsx"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


class EnergyReportView(APIView):
    """能耗报表：日 / 月 / 年用能统计，支持尖峰平谷分时段，支持导出 Excel。"""

    permission_classes = [HasRequiredPermissions]
    required_permissions = {"GET": "ems.report.view"}

    @extend_schema(responses={200: dict})
    def get(self, request, *args, **kwargs) -> Response | HttpResponse:
        params = request.query_params
        period = _str_or_none(params.get("period")) or "day"
        if period not in selectors.PERIOD_DIMENSIONS:
            raise StateConflict(
                "报表周期只支持 day / month / year。", code="REPORT_PERIOD_INVALID"
            )
        medium = _str_or_none(params.get("medium"))
        start = _str_or_none(params.get("start"))
        end = _str_or_none(params.get("end"))
        rows = selectors.consumption_rows(
            request.user,
            dimension=period,
            medium=medium,
            start=start,
            end=end,
            area_id=_int_or_none(params.get("area_id")),
            department_id=_int_or_none(params.get("department_id")),
            meter_id=_int_or_none(params.get("meter_id")),
        )
        peak_valley: list[dict[str, Any]] = []
        if medium:
            peak_valley = selectors.peak_valley_rows(
                request.user,
                medium=medium,
                start=start,
                end=end,
                dimension=_str_or_none(params.get("peak_valley_dimension")) or "period",
            )
        if (_str_or_none(params.get("export")) or "").lower() in {"xlsx", "excel", "1", "true"}:
            record_audit(
                action=AuditAction.EXPORT,
                object_type="ems.EnergyReport",
                object_repr=f"能耗报表 {period} {start or ''}~{end or ''}".strip(),
                changes={"period": period, "medium": medium or "all", "rows": len(rows)},
            )
            return _xlsx_response(rows, title="能耗报表")
        return Response(
            {
                "period": period,
                "medium": medium,
                "medium_label": selectors.MEDIUM_LABELS.get(medium or "", "全部介质"),
                "start": start,
                "end": end,
                "rows": rows,
                "peak_valley": peak_valley,
                "totals": {
                    "consumption": _sum_decimal(row["consumption"] for row in rows),
                    "cost": _sum_decimal(row["cost"] for row in rows),
                    "unpriced": sum(1 for row in rows if not row["priced"]),
                },
            }
        )


__all__ = [
    "EnergyAlarmViewSet",
    "EnergyAreaViewSet",
    "EnergyHomeView",
    "EnergyMeterViewSet",
    "EnergyMonitorView",
    "EnergyPriceViewSet",
    "EnergyReportView",
    "EnergyRunRecordViewSet",
    "EnergyStatisticsView",
    "EnergyThresholdViewSet",
    "MeterReadingViewSet",
]
