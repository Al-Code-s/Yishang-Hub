"""数采设备离线检测。

判定依据只有一条：**最后一次上报时间**与设备自身配置的「离线判定（分钟）」。
平台不假装实时，也不去 ping 设备——真实网络探测属于现场实施范畴。

判定为离线的设备会置为「离线」状态，并按来源（``iot:设备编码``）写一条
能源报警台账的离线报警（同一来源一小时内只报一次，不刷屏）。

模拟设备（``is_simulated=True``）不参与判定：模拟器不跑的时候自然「离线」，
报出来只会污染报警台账。
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.iot import services


class Command(BaseCommand):
    help = "扫描超时未上报的数采设备，置为离线并生成离线报警（不含模拟设备）。"

    def add_arguments(self, parser) -> None:
        parser.add_argument("--company", type=int, default=None, help="只检查指定公司 ID")

    def handle(self, *args, **options) -> None:
        result = services.detect_offline_gateways(company_id=options.get("company"))
        self.stdout.write(
            f"检查时间：{result['checked_at']:%Y-%m-%d %H:%M:%S}；"
            f"判定离线：{result['offline']} 台；新增报警：{result['alarms']} 条。"
        )
        if not result["offline"]:
            self.stdout.write("全部纳入离线判定的设备均在阈值内上报。")
