from __future__ import annotations

from django.apps import AppConfig


class IntegrationConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.integration"
    label = "integration"
    verbose_name = "内部协同"

    def ready(self) -> None:
        # 注册 Outbox 事件处理器（导入即注册）
        from apps.integration import handlers  # noqa: F401
