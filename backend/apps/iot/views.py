"""设备数采接口。

两组接口，凭证完全分开：

* **人员接口**（会话 + 权限码）：连接配置、数采设备、测点的维护，读数与采集日志的查询，
  以及 ``rotate-token`` 生成设备令牌；
* **设备接口** ``POST /api/v1/iot/ingest/``：只认 ``X-Device-Token`` 头里的设备令牌，
  显式关闭会话认证——硬件上报不应该、也不允许借用员工登录态。

采集结果与失败原因都可在「采集日志」里看到；越限与离线报警写在能源管理的报警台账，
由 ``apps/ems/services.py::raise_alarm`` 统一生成。
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from django.db.models import Count, OuterRef, Subquery
from drf_spectacular.utils import extend_schema
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.models import AuditAction
from apps.core.permissions import HasRequiredPermissions
from apps.core.services import build_changes, business_now, record_audit, serialise_value
from apps.core.viewsets import ActiveFilterMixin, ReadOnlyScopedViewSet, ScopedModelViewSet
from apps.ems.models import AlarmStatus, EnergyAlarm
from apps.iot import selectors, services
from apps.iot.models import (
    GatewayStatus,
    IoTConnection,
    IoTGateway,
    IoTMessage,
    IoTPoint,
    IoTReading,
    MessageStatus,
)
from apps.iot.serializers import (
    IngestReportSerializer,
    IoTConnectionSerializer,
    IoTGatewaySerializer,
    IoTMessageSerializer,
    IoTPointSerializer,
    IoTReadingSerializer,
    TokenRotateSerializer,
)


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _bool_or_none(value: Any) -> bool | None:
    if value in (None, ""):
        return None
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


class IotScopedViewSet(ActiveFilterMixin, ScopedModelViewSet):
    """设备数采通用视图基类：按所属公司收敛数据范围。"""

    scope_fields = {"company_field": "company_id"}


class IoTConnectionViewSet(IotScopedViewSet):
    queryset = IoTConnection.objects.select_related("company").all()
    serializer_class = IoTConnectionSerializer
    audit_fields = (
        "code", "name", "protocol", "endpoint", "timeout_seconds", "batch_limit",
        "rate_limit_per_minute", "is_enabled", "is_simulated",
    )
    search_fields = ["code", "name", "endpoint"]
    filterset_fields = ["company_id", "protocol", "is_enabled", "is_simulated"]
    ordering_fields = ["id", "code", "name"]
    uniqueness_error_map = {"uq_iot_connection_company_code": "同一公司下连接编码已存在。"}
    required_permissions = {
        "list": "iot.connection.view",
        "retrieve": "iot.connection.view",
        "create": "iot.connection.create",
        "partial_update": "iot.connection.update",
        "set_active": "iot.connection.update",
    }

    def perform_create(self, serializer) -> None:
        data = serializer.validated_data
        data["code"] = str(data.get("code") or "").strip() or services.next_connection_code()
        super().perform_create(serializer)


class IoTGatewayViewSet(IotScopedViewSet):
    queryset = IoTGateway.objects.select_related(
        "company", "connection", "equipment", "factory", "workshop", "production_line"
    ).all()
    serializer_class = IoTGatewaySerializer
    audit_fields = (
        "code", "name", "gateway_type", "connection_id", "equipment_id", "location",
        "offline_minutes", "status", "is_simulated",
    )
    search_fields = ["code", "name", "location"]
    filterset_fields = ["company_id", "gateway_type", "connection_id", "status", "is_simulated"]
    ordering_fields = ["id", "code", "name", "last_seen_at"]
    uniqueness_error_map = {"uq_iot_gateway_company_code": "同一公司下设备编码已存在。"}
    required_permissions = {
        "list": "iot.gateway.view",
        "retrieve": "iot.gateway.view",
        "create": "iot.gateway.create",
        "partial_update": "iot.gateway.update",
        "set_active": "iot.gateway.update",
        "rotate_token": "iot.gateway.rotate_token",
    }

    def perform_create(self, serializer) -> None:
        data = serializer.validated_data
        data["code"] = str(data.get("code") or "").strip() or services.next_gateway_code()
        super().perform_create(serializer)

    @extend_schema(request=TokenRotateSerializer, responses={200: dict})
    @action(detail=True, methods=["post"], url_path="rotate-token")
    def rotate_token(self, request, *args, **kwargs) -> Response:
        """生成 / 轮换设备令牌：明文只返回一次，旧令牌立即失效。"""
        gateway = self.get_object()
        payload = TokenRotateSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        before = {"token_prefix": gateway.token_prefix}
        raw_token = services.issue_device_token(gateway)
        record_audit(
            action=AuditAction.UPDATE,
            instance=gateway,
            changes=build_changes(
                before,
                {
                    "token_prefix": gateway.token_prefix,
                    "token_rotated_at": serialise_value(gateway.token_rotated_at),
                },
            ),
            reason=payload.validated_data.get("reason", "") or "轮换设备令牌",
            object_repr=str(gateway),
        )
        return Response(
            {
                "gateway_id": gateway.pk,
                "gateway_code": gateway.code,
                "token_prefix": gateway.token_prefix,
                "token": raw_token,
                "token_rotated_at": gateway.token_rotated_at,
                "note": "明文令牌只在此处返回一次，请立即写入设备侧；平台只保存摘要。",
            }
        )


class IoTPointViewSet(IotScopedViewSet):
    queryset = IoTPoint.objects.select_related("company", "gateway", "meter").all()
    serializer_class = IoTPointSerializer
    audit_fields = (
        "code", "name", "gateway_id", "quantity", "unit", "precision", "is_cumulative",
        "upper_limit", "lower_limit", "alarm_enabled",
    )
    search_fields = ["code", "name"]
    filterset_fields = ["gateway_id", "quantity", "is_cumulative", "is_active"]
    ordering_fields = ["id", "code", "name"]
    uniqueness_error_map = {"uq_iot_point_gateway_code": "同一设备下测点编码已存在。"}
    required_permissions = {
        "list": "iot.point.view",
        "retrieve": "iot.point.view",
        "create": "iot.point.create",
        "partial_update": "iot.point.update",
        "set_active": "iot.point.update",
    }

    def perform_create(self, serializer) -> None:
        data = serializer.validated_data
        gateway = data["gateway"]
        # 公司归属由设备推导：即使客户端伪造 company_id 也不会生效；
        # 若设备本身不在当前用户的数据范围内，assert_object_in_scope 会拒绝并回滚。
        data["company"] = gateway.company
        data["code"] = str(data.get("code") or "").strip() or services.next_point_code()
        super().perform_create(serializer)


class IoTMessageViewSet(ReadOnlyScopedViewSet):
    """采集日志（只读）：包含重复报文与失败报文。"""

    queryset = IoTMessage.objects.select_related("company", "gateway").all()
    serializer_class = IoTMessageSerializer
    search_fields = ["message_id", "error_message", "gateway__code", "gateway__name"]
    filterset_fields = ["company_id", "gateway_id", "status", "is_simulated"]
    ordering_fields = ["id", "received_at", "status"]
    required_permissions = {
        "list": "iot.message.view",
        "retrieve": "iot.message.view",
    }


class IoTReadingViewSet(ReadOnlyScopedViewSet):
    """标准化读数（只读）。"""

    queryset = IoTReading.objects.select_related("company", "gateway", "point").all()
    serializer_class = IoTReadingSerializer
    search_fields = ["point__code", "point__name", "gateway__code"]
    filterset_fields = ["company_id", "gateway_id", "point_id", "quality", "source", "is_simulated"]
    ordering_fields = ["id", "device_time", "received_at", "value"]
    required_permissions = {
        "list": "iot.reading.view",
        "retrieve": "iot.reading.view",
    }


class IoTStatisticsView(APIView):
    """采集统计（只读聚合）：按「测点 × 时间桶」实时汇总采集读数。

    读的是采集明细，**不读也不写任何汇总表**——设备补发、重传之后统计立刻跟着变，
    页面上的数字永远能回到「采集读数」逐条核对（与能源统计同一口径）。
    分桶按业务时区截断，``granularity`` 支持 ``hour`` / ``day``，默认近 30 天按天。
    """

    permission_classes = [HasRequiredPermissions]
    required_permissions = ["iot.reading.view"]

    @extend_schema(responses={200: dict})
    def get(self, request, *args, **kwargs) -> Response:
        params = request.query_params
        limit = _int_or_none(params.get("limit"))
        return Response(
            selectors.reading_statistics(
                request.user,
                granularity=params.get("granularity") or selectors.DEFAULT_GRANULARITY,
                since=params.get("since"),
                until=params.get("until"),
                company_id=_int_or_none(params.get("company_id")),
                gateway_id=_int_or_none(params.get("gateway_id")),
                point_id=_int_or_none(params.get("point_id")),
                is_simulated=_bool_or_none(params.get("is_simulated")),
                limit=limit if limit is not None else selectors.ROW_LIMIT,
            )
        )


class DeviceIngestView(APIView):
    """HTTP 采集入口（设备侧调用）。

    * 只认 ``X-Device-Token``（或 ``Authorization: Device <token>``）；
    * 显式关闭会话认证：**不复用员工登录会话**（任务书 11.3）；
    * 限流、批次上限、判重与失败留痕都在 ``apps/iot/services.py::ingest_report`` 里完成。
    """

    authentication_classes: list = []
    permission_classes: list = []

    def _device_token(self, request) -> str:
        header_token = request.headers.get("X-Device-Token", "")
        if header_token:
            return header_token
        authorization = request.headers.get("Authorization", "")
        if authorization.lower().startswith("device "):
            return authorization[len("device ") :]
        return ""

    @extend_schema(request=IngestReportSerializer, responses={200: dict})
    def post(self, request, *args, **kwargs) -> Response:
        gateway = services.authenticate_device(self._device_token(request))
        payload = IngestReportSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        # 原样存上报报文（JSON 原始值），而不是把 DRF 反序列化后的 datetime 塞进 JSONField
        result = services.ingest_report(
            gateway,
            request.data if isinstance(request.data, dict) else {},
            source_ip=request.META.get("REMOTE_ADDR"),
        )
        return Response(
            {
                "gateway_code": gateway.code,
                "gateway_name": gateway.name,
                **result,
            }
        )


class DeviceMonitorView(APIView):
    """设备监控：按设备展示在线状态与最新读数（只读聚合视图）。"""

    permission_classes = [HasRequiredPermissions]
    required_permissions = ["iot.monitor.view"]

    @extend_schema(responses={200: dict})
    def get(self, request, *args, **kwargs) -> Response:
        from apps.core.selectors import scoped_queryset

        moment = business_now()
        gateways = (
            scoped_queryset(
                IoTGateway.objects.select_related("company", "connection"), request.user, company_field="company_id"
            )
            .filter(is_active=True)
            .order_by("code")
        )
        gateway_ids = list(gateways.values_list("id", flat=True))
        readings = IoTReading.objects.filter(gateway_id__in=gateway_ids)
        messages = IoTMessage.objects.filter(gateway_id__in=gateway_ids)
        since = moment - timedelta(hours=24)

        summary = {
            "gateway_total": len(gateway_ids),
            "online": gateways.filter(status=GatewayStatus.ONLINE).count(),
            "offline": gateways.filter(status=GatewayStatus.OFFLINE).count(),
            "unknown": gateways.filter(status=GatewayStatus.UNKNOWN).count(),
            "simulated": gateways.filter(is_simulated=True).count(),
            "readings_24h": readings.filter(received_at__gte=since).count(),
            "failed_messages_24h": messages.filter(
                received_at__gte=since, status=MessageStatus.FAILED
            ).count(),
            "duplicated_messages_24h": messages.filter(
                received_at__gte=since, status=MessageStatus.DUPLICATED
            ).count(),
            "open_alarms": EnergyAlarm.objects.filter(
                company_id__in=gateways.values_list("company_id", flat=True),
                status__in=[AlarmStatus.PENDING, AlarmStatus.HANDLING],
            ).count(),
        }

        # 每个测点取最新一条读数：用「每测点取最新 id」的子查询一次性取回，
        # 避免按测点逐条查询把接口拖成 N+1（原来按设备逐台查询，测点多了会明显变慢）。
        latest_ids = IoTReading.objects.filter(point_id=OuterRef("pk")).order_by(
            "-device_time", "-id"
        )
        latest_id_by_point = {
            point["pk"]: point["latest_id"]
            for point in IoTPoint.objects.filter(
                gateway_id__in=gateway_ids, is_active=True
            )
            .annotate(latest_id=Subquery(latest_ids.values("id")[:1]))
            .values("pk", "latest_id")
        }
        latest_readings = {
            reading.point_id: reading
            for reading in IoTReading.objects.filter(
                id__in=[pk for pk in latest_id_by_point.values() if pk is not None]
            )
        }
        points_by_gateway = {}
        for point in IoTPoint.objects.filter(gateway_id__in=gateway_ids, is_active=True).order_by(
            "gateway_id", "code"
        ):
            points_by_gateway.setdefault(point.gateway_id, []).append(point)

        rows = []
        for gateway in gateways:
            latest_points = []
            for point in points_by_gateway.get(gateway.pk, []):
                latest = latest_readings.get(point.pk)
                latest_points.append(
                    {
                        "point_id": point.pk,
                        "code": point.code,
                        "name": point.name,
                        "quantity": point.quantity,
                        "unit": point.unit,
                        "lower_limit": serialise_value(point.lower_limit),
                        "upper_limit": serialise_value(point.upper_limit),
                        "latest_value": serialise_value(latest.value) if latest else None,
                        "latest_device_time": serialise_value(latest.device_time) if latest else None,
                        "is_simulated": bool(latest.is_simulated) if latest else gateway.is_simulated,
                        "is_over_limit": bool(
                            latest
                            and (
                                (point.upper_limit is not None and latest.value > point.upper_limit)
                                or (point.lower_limit is not None and latest.value < point.lower_limit)
                            )
                        ),
                    }
                )
            rows.append(
                {
                    "id": gateway.pk,
                    "code": gateway.code,
                    "name": gateway.name,
                    "gateway_type": gateway.gateway_type,
                    "status": gateway.status,
                    "location": gateway.location,
                    "connection_name": str(gateway.connection) if gateway.connection_id else "",
                    "is_simulated": gateway.is_simulated,
                    "offline_minutes": gateway.offline_minutes,
                    "last_seen_at": serialise_value(gateway.last_seen_at),
                    "points": latest_points,
                }
            )

        recent = [
            {
                "id": reading.pk,
                "gateway_code": reading.gateway.code,
                "point_code": reading.point.code,
                "point_name": reading.point.name,
                "value": serialise_value(reading.value),
                "unit": reading.unit,
                "device_time": serialise_value(reading.device_time),
                "is_simulated": reading.is_simulated,
            }
            for reading in readings.select_related("gateway", "point").order_by(
                "-device_time", "-id"
            )[:20]
        ]
        message_stats = list(
            messages.values("status").annotate(total=Count("id")).order_by("status")
        )
        return Response(
            {
                "generated_at": moment,
                "summary": summary,
                "message_stats": message_stats,
                "gateways": rows,
                "recent_readings": recent,
            }
        )


__all__ = [
    "DeviceIngestView",
    "DeviceMonitorView",
    "IoTConnectionViewSet",
    "IoTGatewayViewSet",
    "IoTMessageViewSet",
    "IoTPointViewSet",
    "IoTReadingViewSet",
    "IoTStatisticsView",
]
