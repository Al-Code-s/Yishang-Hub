from __future__ import annotations

from django.apps import AppConfig


class IotConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.iot"
    label = "iot"
    verbose_name = "设备数采与监控"
