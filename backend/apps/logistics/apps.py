from __future__ import annotations

from django.apps import AppConfig


class LogisticsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.logistics"
    label = "logistics"
    verbose_name = "生产物流管理"
