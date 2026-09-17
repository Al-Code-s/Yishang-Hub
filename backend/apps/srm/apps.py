from __future__ import annotations

from django.apps import AppConfig


class SrmConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.srm"
    label = "srm"
    verbose_name = "供应商管理"
