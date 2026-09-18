from __future__ import annotations

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.sales import views

router = DefaultRouter()
router.register("orders", views.SalesOrderViewSet, basename="sales-order")
router.register("shipments", views.SalesShipmentViewSet, basename="sales-shipment")
router.register("returns", views.SalesReturnViewSet, basename="sales-return")

urlpatterns = [path("", include(router.urls))]
