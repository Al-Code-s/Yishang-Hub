"""计量设备离线巡检：按阈值生成「设备离线」报警。

用法（可挂到 Windows 计划任务或 cron；不强制依赖 Celery）：::

    python manage.py ems_offline_check
    python manage.py ems_offline_check --company 1

判定依据是 ``EnergyThreshold.offline_minutes``，没有配置离线阈值的仪表不检测，
避免把「本来就不需要抄表」的仪表全部报成离线。
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.ems.services import scan_offline_meters


class Command(BaseCommand):
    help = "扫描超时未抄表的计量设备并生成离线报警（同类型报警当天只生成一次）。"

    def add_arguments(self, parser) -> None:
        parser.add_argument("--company", type=int, default=None, help="只检测指定公司")

    def handle(self, *args, **options) -> None:
        created = scan_offline_meters(company_id=options.get("company"))
        if not created:
            self.stdout.write("没有新的离线报警。")
            return
        for alarm in created:
            self.stdout.write(f"[{alarm.alarm_no}] {alarm.message}")
        self.stdout.write(self.style.SUCCESS(f"生成离线报警 {len(created)} 条。"))
