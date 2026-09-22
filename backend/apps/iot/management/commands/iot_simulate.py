"""模拟采集器（开发 / 演示用，任务书 11.3 第 1 条）。

**这是一个模拟器，不是设备接入。** 它生成的数据会：

* 在报文与读数上带 ``is_simulated=True``，界面按「模拟」标签显示；
* 走**与真实上报完全相同**的服务层路径（``ingest_report``）：同样受批次上限、限流、
  判重与越限判定约束，不会绕过业务规则去「造」一份好看的数据；
* 命令行输出顶部明确标注「模拟数据（非真实设备采集）」。

``--seed-demo`` 可按任务书 11.1 的数量（5 台传感器 + 2 台智能水表 + 2 台智能电表）
建一套**演示设备**，全部标记为模拟设备；不传该参数时不会创建任何设备。
"""

from __future__ import annotations

import random
import time
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError

from apps.core.services import business_now
from apps.factory.models import Company
from apps.iot import services
from apps.iot.models import (
    GatewayType,
    IoTConnection,
    IoTGateway,
    IoTPoint,
    IoTProtocol,
    PointQuantity,
)

SIMULATION_BANNER = "*** 模拟数据（非真实设备采集）***"


class Command(BaseCommand):
    help = (
        "模拟采集器：按测点生成模拟读数并走真实采集入库流程（数据全程标注为「模拟」）。"
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument("--gateway", help="数采设备编码；--seed-demo 时可省略")
        parser.add_argument("--company", type=int, help="公司 ID（--seed-demo 时使用）")
        parser.add_argument("--seed-demo", action="store_true", help="先创建一套标记为模拟的演示设备")
        parser.add_argument("--points", default="", help="测点编码，逗号分隔；默认该设备下全部启用测点")
        parser.add_argument("--rounds", type=int, default=1, help="发送轮数，默认 1")
        parser.add_argument("--interval", type=float, default=0.0, help="轮次间隔秒数，默认 0")
        parser.add_argument("--out-of-range", action="store_true", help="故意生成越限值以验证越限报警")
        parser.add_argument("--dry-run", action="store_true", help="只打印将要发送的报文，不入库")

    def handle(self, *args, **options) -> None:
        self.stdout.write(self.style.WARNING(SIMULATION_BANNER))
        if options["seed_demo"]:
            gateway = self._seed_demo(options.get("company"))
        else:
            code = options.get("gateway")
            if not code:
                raise CommandError("请用 --gateway 指定数采设备编码，或使用 --seed-demo 创建演示设备。")
            gateway = IoTGateway.objects.filter(code=code).first()
            if gateway is None:
                raise CommandError(f"找不到数采设备 {code}。")

        points = self._resolve_points(gateway, options.get("points") or "")
        if not points:
            raise CommandError(f"设备 {gateway.code} 下没有启用的测点，请先在「采集测点」中登记。")

        rounds = max(1, int(options["rounds"]))
        interval = max(0.0, float(options["interval"]))
        for index in range(rounds):
            payload = self._build_payload(points, out_of_range=bool(options["out_of_range"]), index=index)
            if options["dry_run"]:
                self.stdout.write(f"[{index + 1}/{rounds}] 待发送报文：{payload}")
            else:
                result = services.ingest_report(gateway, payload)
                self.stdout.write(
                    f"[{index + 1}/{rounds}] {payload['message_id']} → 状态 {result['status']}，"
                    f"入库读数 {result['accepted']} 条，跳过 {result['skipped']} 条，"
                    f"新增报警 {result['alarms']} 条"
                )
                if result.get("problems"):
                    self.stdout.write(self.style.WARNING("  说明：" + "；".join(result["problems"])))
            if interval and index < rounds - 1:
                time.sleep(interval)

        self.stdout.write(
            self.style.WARNING(
                f"{SIMULATION_BANNER} 以上读数由内置模拟器生成，不代表任何真实设备状态。"
            )
        )

    # -- 内部实现 ----------------------------------------------------------

    def _seed_demo(self, company_id: int | None) -> IoTGateway:
        company = Company.objects.filter(pk=company_id).first() if company_id else Company.objects.first()
        if company is None:
            raise CommandError("找不到公司，请先创建公司或用 --company 指定。")

        connection, _ = IoTConnection.objects.get_or_create(
            company=company,
            code="SIM-HTTP-DEMO",
            defaults={
                "name": "模拟 HTTP 连接（演示用）",
                "protocol": IoTProtocol.SIMULATOR,
                "endpoint": "内置模拟器（无外部地址）",
                "credential_ref": "模拟器无需令牌",
                "is_simulated": True,
                "remark": "由 manage.py iot_simulate --seed-demo 创建，仅用于演示与联调。",
            },
        )
        plan = (
            (GatewayType.SENSOR, 5, "传感器"),
            (GatewayType.WATER_METER, 2, "智能水表"),
            (GatewayType.ELECTRIC_METER, 2, "智能电表"),
        )
        first: IoTGateway | None = None
        for gateway_type, count, label in plan:
            for index in range(1, count + 1):
                code = f"SIM-{gateway_type.upper()[:3]}-{index:02d}"
                gateway, _ = IoTGateway.objects.get_or_create(
                    company=company,
                    code=code,
                    defaults={
                        "name": f"模拟{label}{index}",
                        "gateway_type": gateway_type,
                        "connection": connection,
                        "location": "演示环境",
                        "is_simulated": True,
                        "offline_minutes": 0,
                        "remark": "任务书 11.1 的演示占位设备；真实设备信息待现场确认。",
                    },
                )
                self._ensure_demo_points(gateway)
                first = first or gateway
        self.stdout.write(
            self.style.WARNING("已创建 / 复用一套标记为「模拟」的演示设备（5 传感器 + 2 水表 + 2 电表）。")
        )
        assert first is not None
        return first

    def _ensure_demo_points(self, gateway: IoTGateway) -> None:
        """按设备类型建演示测点。

        量程与报警上下限一律留空：平台不知道真实设备的量程，就不该替它编一个。
        """
        if gateway.gateway_type == GatewayType.SENSOR:
            specs = [
                ("TEMP", PointQuantity.TEMPERATURE, "温度", "℃", False),
                ("VOLT", PointQuantity.VOLTAGE, "电压", "V", False),
                ("CURR", PointQuantity.CURRENT, "电流", "A", False),
                ("VIB", PointQuantity.VIBRATION, "振动", "mm/s", False),
            ]
        elif gateway.gateway_type == GatewayType.WATER_METER:
            specs = [("WATER-TOTAL", PointQuantity.WATER, "累计水量", "m³", True)]
        else:
            specs = [("ELEC-TOTAL", PointQuantity.ELECTRICITY, "累计电量", "kWh", True)]

        for code, quantity, name, unit, is_cumulative in specs:
            IoTPoint.objects.get_or_create(
                company=gateway.company,
                gateway=gateway,
                code=code,
                defaults={
                    "name": name,
                    "quantity": quantity,
                    "unit": unit,
                    "precision": 3,
                    "is_cumulative": is_cumulative,
                    "alarm_enabled": not is_cumulative,
                    "remark": "模拟演示测点（量程与上限未按真实设备设置）",
                },
            )

    def _resolve_points(self, gateway: IoTGateway, raw: str) -> list[IoTPoint]:
        queryset = IoTPoint.objects.filter(gateway=gateway, is_active=True).order_by("code")
        codes = [item.strip() for item in raw.split(",") if item.strip()]
        if codes:
            queryset = queryset.filter(code__in=codes)
        return list(queryset)

    def _build_payload(self, points: list[IoTPoint], *, out_of_range: bool, index: int) -> dict:
        moment = business_now()
        return {
            "message_id": f"SIM-{moment:%Y%m%d%H%M%S}-{index + 1}",
            "device_time": moment.isoformat(),
            "simulated": True,
            "points": [
                {"code": point.code, "value": self._value_for(point, out_of_range)}
                for point in points
            ],
        }

    def _value_for(self, point: IoTPoint, out_of_range: bool) -> str:
        if out_of_range and point.upper_limit is not None:
            return str(point.upper_limit * Decimal("1.1"))
        if out_of_range:
            return "999"
        if point.is_cumulative:
            latest = point.readings.order_by("-device_time").first()
            base = latest.value if latest is not None else Decimal("1000")
            return str(base + Decimal(random.randint(1, 20)))
        low = point.range_min if point.range_min is not None else Decimal("0")
        high = point.range_max if point.range_max is not None else Decimal("100")
        span = high - low
        return str((low + span * Decimal(str(round(random.random(), 4)))).quantize(Decimal("0.001")))
