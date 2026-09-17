from __future__ import annotations

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.masterdata import views

router = DefaultRouter()
router.register("uoms", views.UoMViewSet, basename="masterdata-uom")
router.register("uom-conversions", views.UoMConversionViewSet, basename="masterdata-uom-conversion")
router.register("material-categories", views.MaterialCategoryViewSet, basename="masterdata-material-category")
router.register("materials", views.MaterialViewSet, basename="masterdata-material")
router.register("colors", views.ColorViewSet, basename="masterdata-color")
router.register("sizes", views.SizeViewSet, basename="masterdata-size")
router.register("styles", views.StyleViewSet, basename="masterdata-style")
router.register("skus", views.SkuViewSet, basename="masterdata-sku")
router.register("identifiers", views.IdentifierViewSet, basename="masterdata-identifier")

urlpatterns = [path("", include(router.urls))]
