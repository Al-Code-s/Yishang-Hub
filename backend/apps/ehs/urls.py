from __future__ import annotations

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.ehs import views

router = DefaultRouter()
# 安全管理
router.register("regulations", views.SafetyRegulationViewSet, basename="safety-regulation")
router.register("trainings", views.SafetyTrainingViewSet, basename="safety-training")
router.register("hazards", views.HazardRecordViewSet, basename="hazard-record")
router.register("emergency-plans", views.EmergencyPlanViewSet, basename="emergency-plan")
router.register("accidents", views.AccidentRecordViewSet, basename="accident-record")
# 环保管理
router.register("env-monitors", views.EnvironmentMonitorViewSet, basename="env-monitor")
router.register("wastes", views.WasteRecordViewSet, basename="waste-record")
router.register("compliance-checks", views.ComplianceCheckViewSet, basename="compliance-check")
# 消防管理
router.register("fire-facilities", views.FireFacilityViewSet, basename="fire-facility")
router.register("fire-drills", views.FireDrillViewSet, basename="fire-drill")
router.register("work-permits", views.WorkPermitViewSet, basename="work-permit")
# 设备设施安全
router.register("safety-checks", views.SafetyCheckViewSet, basename="safety-check")
router.register(
    "special-equipment-inspections",
    views.SpecialEquipmentInspectionViewSet,
    basename="special-equipment-inspection",
)
# 操作日志
router.register("operation-logs", views.EhsOperationLogViewSet, basename="ehs-operation-log")

urlpatterns = [path("", include(router.urls))]
