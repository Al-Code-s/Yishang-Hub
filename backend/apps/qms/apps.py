from __future__ import annotations

from django.apps import AppConfig


class QmsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.qms"
    label = "qms"
    verbose_name = "质量管理"
