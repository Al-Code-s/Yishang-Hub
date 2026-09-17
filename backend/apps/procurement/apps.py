from __future__ import annotations

from django.apps import AppConfig


class ProcurementConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.procurement"
    label = "procurement"
    verbose_name = "采购管理"

    def ready(self) -> None:
        # 显式登记审批结果回写：审批通过与业务状态迁移是两个动作，
        # 这里把两者在**同一事务**内串起来（不使用 signals）。
        from apps.procurement import services
        from apps.workflow.registry import register_biz_handler

        register_biz_handler(services.BIZ_TYPE_REQUISITION, services.on_requisition_approval_outcome)
        register_biz_handler(services.BIZ_TYPE_ORDER, services.on_order_approval_outcome)
