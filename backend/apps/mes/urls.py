from __future__ import annotations

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.mes import views

router = DefaultRouter()
router.register("orders", views.ProductionOrderViewSet, basename="mes-order")
router.register("reports", views.ProductionReportViewSet, basename="mes-report")

urlpatterns = [path("", include(router.urls))]
