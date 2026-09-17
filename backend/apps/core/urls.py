from __future__ import annotations

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.core import views

router = DefaultRouter()
router.register("dictionaries", views.DictionaryViewSet, basename="core-dictionary")
router.register("dictionary-items", views.DictionaryItemViewSet, basename="core-dictionary-item")
router.register("code-rules", views.CodeRuleViewSet, basename="core-code-rule")
router.register("audit-logs", views.AuditLogViewSet, basename="core-audit-log")
router.register("attachments", views.AttachmentViewSet, basename="core-attachment")

urlpatterns = [
    path("meta/", views.MetaView.as_view(), name="core-meta"),
    path("", include(router.urls)),
]
