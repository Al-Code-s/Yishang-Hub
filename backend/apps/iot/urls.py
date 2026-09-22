from __future__ import annotations

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.iot import views

router = DefaultRouter()
# 接入配置：连接、数采设备、测点
router.register("connections", views.IoTConnectionViewSet, basename="iot-connection")
router.register("gateways", views.IoTGatewayViewSet, basename="iot-gateway")
router.register("points", views.IoTPointViewSet, basename="iot-point")
# 采集数据：标准化读数、采集日志（均只读）
router.register("readings", views.IoTReadingViewSet, basename="iot-reading")
router.register("messages", views.IoTMessageViewSet, basename="iot-message")

urlpatterns = [
    # 设备侧 HTTP 采集入口（设备令牌认证，不使用员工会话）
    path("ingest/", views.DeviceIngestView.as_view(), name="iot-ingest"),
    # 人员侧只读聚合视图（设备监控）
    path("monitor/", views.DeviceMonitorView.as_view(), name="iot-monitor"),
    # 人员侧只读聚合视图（采集统计：按测点 × 时间桶实时聚合读数）
    path("statistics/", views.IoTStatisticsView.as_view(), name="iot-statistics"),
    path("", include(router.urls)),
]
