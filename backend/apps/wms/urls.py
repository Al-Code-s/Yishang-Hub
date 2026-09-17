from __future__ import annotations

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.wms import views

router = DefaultRouter()
router.register("warehouses", views.WarehouseViewSet, basename="wms-warehouse")
router.register("zones", views.ZoneViewSet, basename="wms-zone")
router.register("locations", views.LocationViewSet, basename="wms-location")
router.register("inventory-balances", views.InventoryBalanceViewSet, basename="wms-inventory-balance")
router.register(
    "inventory-transactions", views.InventoryTransactionViewSet, basename="wms-inventory-transaction"
)
router.register(
    "inventory-documents", views.InventoryDocumentViewSet, basename="wms-inventory-document"
)

urlpatterns = [path("", include(router.urls))]
