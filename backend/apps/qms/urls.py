from __future__ import annotations

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.qms import views

router = DefaultRouter()
router.register("inspection-items", views.QualityInspectionItemViewSet, basename="qms-item")
router.register("inspections", views.QualityInspectionOrderViewSet, basename="qms-inspection")
router.register("alerts", views.QualityAlertViewSet, basename="qms-alert")
router.register("issues", views.QualityIssueViewSet, basename="qms-issue")

urlpatterns = [path("", include(router.urls))]
