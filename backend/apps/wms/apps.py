from __future__ import annotations

from django.apps import AppConfig


class WmsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.wms"
    label = "wms"
    verbose_name = "仓储管理"
