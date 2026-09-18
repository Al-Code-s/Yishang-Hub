from __future__ import annotations

from django.apps import AppConfig


class SalesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.sales"
    label = "sales"
    verbose_name = "销售管理"

    def ready(self) -> None:
        # 显式登记审批结果回写：审批通过与业务状态迁移是两个动作，
        # 这里把两者在**同一事务**内串起来（不使用 signals）。
        from apps.sales import services
        from apps.workflow.registry import register_biz_handler

        register_biz_handler(services.BIZ_TYPE_ORDER, services.on_order_approval_outcome)
