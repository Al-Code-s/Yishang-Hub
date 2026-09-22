from __future__ import annotations

from django.apps import AppConfig


class EquipmentConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.equipment"
    label = "equipment"
    verbose_name = "设备管理"

