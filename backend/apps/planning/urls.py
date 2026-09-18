"""计划模块路由。前缀：/api/v1/planning/"""

from __future__ import annotations

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.planning import views

router = DefaultRouter()
router.register("boms", views.BomViewSet, basename="planning-bom")
router.register("routings", views.RoutingViewSet, basename="planning-routing")
router.register("mrp-runs", views.MrpRunViewSet, basename="planning-mrp-run")
router.register("mrp-suggestions", views.MrpSuggestionViewSet, basename="planning-mrp-suggestion")

urlpatterns = [path("", include(router.urls))]
