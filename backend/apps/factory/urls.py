from __future__ import annotations

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.factory import views

router = DefaultRouter()
router.register("companies", views.CompanyViewSet, basename="factory-company")
router.register("departments", views.DepartmentViewSet, basename="factory-department")
router.register("factories", views.FactoryViewSet, basename="factory-factory")
router.register("workshops", views.WorkshopViewSet, basename="factory-workshop")
router.register("lines", views.ProductionLineViewSet, basename="factory-line")
router.register("stations", views.StationViewSet, basename="factory-station")
router.register("employees", views.EmployeeViewSet, basename="factory-employee")
router.register("shifts", views.ShiftViewSet, basename="factory-shift")
router.register("teams", views.TeamViewSet, basename="factory-team")

urlpatterns = [path("", include(router.urls))]
