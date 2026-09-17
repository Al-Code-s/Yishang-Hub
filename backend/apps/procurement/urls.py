"""采购模块路由。前缀：/api/v1/procurement/"""

from __future__ import annotations

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.procurement import views

router = DefaultRouter()
router.register("requisitions", views.RequisitionViewSet, basename="procurement-requisition")
router.register("orders", views.PurchaseOrderViewSet, basename="procurement-order")
router.register("receipts", views.GoodsReceiptViewSet, basename="procurement-receipt")

urlpatterns = [path("", include(router.urls))]
