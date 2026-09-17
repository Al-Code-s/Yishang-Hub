from __future__ import annotations

from django.apps import AppConfig


class MasterDataConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.masterdata"
    label = "masterdata"
    verbose_name = "统一主数据"
