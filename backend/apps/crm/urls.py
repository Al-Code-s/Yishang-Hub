from __future__ import annotations

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.crm import views

router = DefaultRouter()
router.register("customers", views.CustomerViewSet, basename="crm-customer")
router.register("customer-contacts", views.CustomerContactViewSet, basename="crm-customer-contact")
router.register("complaints", views.CustomerComplaintViewSet, basename="crm-complaint")
router.register("product-reviews", views.ProductReviewViewSet, basename="crm-product-review")

urlpatterns = [path("", include(router.urls))]
