from __future__ import annotations

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.ems import views

router = DefaultRouter()
# 基础管理：区域、仪表、价格、阈值
router.register("areas", views.EnergyAreaViewSet, basename="ems-area")
router.register("meters", views.EnergyMeterViewSet, basename="ems-meter")
router.register("prices", views.EnergyPriceViewSet, basename="ems-price")
router.register("thresholds", views.EnergyThresholdViewSet, basename="ems-threshold")
# 运行数据：抄表读数、设备运行记录、报警
router.register("readings", views.MeterReadingViewSet, basename="ems-reading")
router.register("run-records", views.EnergyRunRecordViewSet, basename="ems-run-record")
router.register("alarms", views.EnergyAlarmViewSet, basename="ems-alarm")

urlpatterns = [
    # 只读聚合视图（首页 / 设备监控 / 能耗统计 / 能耗报表）
    path("home/", views.EnergyHomeView.as_view(), name="ems-home"),
    path("monitor/", views.EnergyMonitorView.as_view(), name="ems-monitor"),
    path("statistics/", views.EnergyStatisticsView.as_view(), name="ems-statistics"),
    path("report/", views.EnergyReportView.as_view(), name="ems-report"),
    path("", include(router.urls)),
]
