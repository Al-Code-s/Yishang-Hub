from __future__ import annotations

from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core"
    label = "core"
    verbose_name = "公共基础"

    def ready(self) -> None:
        # Django 不会自动发现应用目录下的 checks.py，必须显式导入，
        # 否则 yishang.E001（视图声明了未注册权限编码）永远不会触发。
        from apps.core import checks  # noqa: F401
