"""计划模块应用配置。

审批结果回写业务单据采用**显式注册**（任务书 4.3 禁止用 signals 承载关键流程）：
这里把 BOM / 工艺路线的审批终结处理函数注册到 `workflow.registry`。
"""

from django.apps import AppConfig


class PlanningConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.planning"
    verbose_name = "计划管理"

    def ready(self) -> None:
        from apps.planning import services
        from apps.workflow.registry import register_biz_handler

        register_biz_handler(services.BIZ_TYPE_BOM, services.on_bom_approval_outcome)
        register_biz_handler(services.BIZ_TYPE_ROUTING, services.on_routing_approval_outcome)
