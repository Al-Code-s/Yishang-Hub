from __future__ import annotations

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.srm import views

router = DefaultRouter()
router.register("suppliers", views.SupplierViewSet, basename="srm-supplier")
router.register("supplier-contacts", views.SupplierContactViewSet, basename="srm-supplier-contact")
router.register(
    "supplier-qualifications",
    views.SupplierQualificationViewSet,
    basename="srm-supplier-qualification",
)
router.register(
    "supplier-evaluation-weights",
    views.SupplierEvaluationWeightViewSet,
    basename="srm-supplier-evaluation-weight",
)
router.register(
    "supplier-evaluations",
    views.SupplierEvaluationViewSet,
    basename="srm-supplier-evaluation",
)

urlpatterns = [path("", include(router.urls))]
