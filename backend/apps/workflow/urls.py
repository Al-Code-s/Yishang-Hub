from __future__ import annotations

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.workflow import views

router = DefaultRouter()
router.register("templates", views.ApprovalTemplateViewSet, basename="workflow-template")
router.register("instances", views.ApprovalInstanceViewSet, basename="workflow-instance")

urlpatterns = [path("", include(router.urls))]
