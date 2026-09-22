from __future__ import annotations

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.equipment import views

router = DefaultRouter()
# 设备基础信息
router.register("equipment-types", views.EquipmentTypeViewSet, basename="equipment-type")
router.register("equipments", views.EquipmentViewSet, basename="equipment")
router.register("equipment-parts", views.EquipmentPartViewSet, basename="equipment-part")
router.register("spare-parts", views.SparePartViewSet, basename="spare-part")
# 设备保养
router.register("maintenance-items", views.MaintenanceItemViewSet, basename="maintenance-item")
router.register("maintenance-plans", views.MaintenancePlanViewSet, basename="maintenance-plan")
router.register("maintenance-tasks", views.MaintenanceTaskViewSet, basename="maintenance-task")
router.register(
    "maintenance-records", views.MaintenanceRecordViewSet, basename="maintenance-record"
)
# 设备维修
router.register("fault-reports", views.FaultReportViewSet, basename="fault-report")
router.register("repair-tasks", views.RepairTaskViewSet, basename="repair-task")
router.register("repair-records", views.RepairRecordViewSet, basename="repair-record")
# 点巡检
router.register("inspection-items", views.InspectionItemViewSet, basename="inspection-item")
router.register("inspection-tasks", views.InspectionTaskViewSet, basename="inspection-task")
router.register("inspection-records", views.InspectionRecordViewSet, basename="inspection-record")
# 设备异常上报
router.register("abnormal-types", views.AbnormalTypeViewSet, basename="abnormal-type")
router.register("abnormal-tasks", views.AbnormalTaskViewSet, basename="abnormal-task")
router.register("abnormal-records", views.AbnormalRecordViewSet, basename="abnormal-record")

urlpatterns = [
    # 备件现存量（库存台账）：只读汇总，数据来自仓储模块的统一库存余额
    path(
        "spare-part-stock/",
        views.SparePartStockView.as_view(),
        name="spare-part-stock",
    ),
    path("", include(router.urls)),
]
