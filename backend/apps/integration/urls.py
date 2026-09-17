from __future__ import annotations

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.integration import views

router = DefaultRouter()
router.register("outbox-events", views.OutboxEventViewSet, basename="integration-outbox")
router.register("document-links", views.DocumentLinkViewSet, basename="integration-document-link")

urlpatterns = [path("", include(router.urls))]
