"""兼容入口：演示数据统一由 ``seed_demo_xjys`` 生成。

背景：本平台只服务「新疆意尚智造科技有限公司」一家公司。早期 ``seed_demo``
会额外创建第二家演示公司（``YS``）的数据，两套组织架构
（部门 / 工厂 / 车间 / 班次 / 员工）同名不同值、互相覆盖，与「只保留一家公司」
的口径冲突，因此不再保留独立实现。

命令名 ``seed_demo`` 作为兼容入口继续可用，行为等价于 ``seed_demo_xjys``。
演示角色定义与口令生成函数已随实现迁入 ``seed_demo_xjys``。
"""

from __future__ import annotations

from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "演示数据（兼容入口）：等价于 seed_demo_xjys，幂等，生产环境禁止执行。"

    def add_arguments(self, parser) -> None:
        parser.add_argument("--yes", action="store_true", help="在非开发环境中确认执行。")

    def handle(self, *args, **options) -> None:
        self.stdout.write("seed_demo 已合并到 seed_demo_xjys，转由 seed_demo_xjys 执行。")
        call_command(
            "seed_demo_xjys",
            yes=bool(options.get("yes")),
            verbosity=options.get("verbosity", 1),
        )
