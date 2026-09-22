from __future__ import annotations

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.logistics import views

router = DefaultRouter()
router.register("automation-devices", views.AutomationDeviceViewSet, basename="automation-device")
router.register("tasks", views.LogisticsTaskViewSet, basename="logistics-task")
router.register(
    "operation-logs", views.LogisticsOperationLogViewSet, basename="logistics-operation-log"
)

urlpatterns = [path("", include(router.urls))]
