"""新疆意尚智造科技有限公司演示数据（2026 年起）。

用途：把部署后“页面都是空的”的问题解决掉——在**新疆意尚智造科技有限公司**
这一家公司下，把各模块在 2026-01-01 之后的业务记录造出来。

安全约束（与 `seed_demo` 一致）：

* 生产环境（``DJANGO_ENV=production``）直接拒绝执行；
* 不写入任何真实个人资料：姓名为合成姓名，电话统一 138-0000-xxxx；
* 所有对象 remark 均为“演示数据（新疆意尚智造）”，与真实业务数据明显区分；
* **幂等**：重复执行只补齐缺失的记录，不会重复建单、不会重复过账、不会重复生成读数；
* 业务状态只能由 **Service 层**推进；库存只能经统一库存服务过账。

时间口径：所有业务日期（请求/订单/报工/抄表/点巡检/安全环保等）均在
2026-01-01 至今天之间，避免出现“业务单据比公司还早”的假数据。
"""

from __future__ import annotations

import random
import secrets
import string
from datetime import date, datetime, time, timedelta
from datetime import timezone as dt_timezone
from decimal import Decimal

from django.conf import settings
from django.core.cache import cache
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.crm.models import Customer, CustomerContact
from apps.ems.models import (
    AlarmLevel,
    AlarmType,
    EnergyAlarm,
    EnergyArea,
    EnergyMeter,
    EnergyPrice,
    EnergyRunRecord,
    EnergyThreshold,
    MeterReading,
    MeterStatus,
    TariffPeriod,
)
from apps.ems.models import ReadingSource as EmsReadingSource
from apps.equipment.models import (
    AbnormalSource,
    AbnormalTask,
    AbnormalType,
    Equipment,
    EquipmentPart,
    EquipmentType,
    FaultLevel,
    FaultReport,
    FaultReportStatus,
    InspectionItem,
    InspectionRecord,
    InspectionResult,
    InspectionTask,
    InspectionTaskType,
    MaintenanceItem,
    MaintenancePlan,
    MaintenanceTask,
    SparePart,
    TaskStatus,
)
from apps.equipment.services import (
    next_abnormal_task_no,
    next_inspection_record_no,
    next_inspection_task_no,
)
from apps.factory.models import (
    Company,
    Department,
    Employee,
    Factory,
    ProductionLine,
    Shift,
    Station,
    Team,
    TeamMember,
    Workshop,
)
from apps.identity.models import DataScopeType, Menu, Permission, Role, User, UserRole
from apps.iot.models import (
    GatewayStatus,
    GatewayType,
    IoTConnection,
    IoTGateway,
    IoTMessage,
    IoTPoint,
    IoTProtocol,
    IoTReading,
)
from apps.masterdata.models import (
    Color,
    FabricProfile,
    Identifier,
    IdentifierType,
    Material,
    MaterialCategory,
    Size,
    Sku,
    Style,
    UoM,
    UoMConversion,
)
from apps.qms.models import QualityInspectionItem
from apps.srm.models import Supplier, SupplierContact, SupplierQualification
from apps.wms.models import Location, LocationType, Warehouse, Zone, ZoneType
from apps.workflow.models import ApprovalTemplate, ApprovalTemplateNode, ApproverType

DEMO_REMARK = "演示数据（新疆意尚智造）"
DATA_START = date(2026, 1, 1)

#: 固定随机种子：同一天重复执行不会拟出不同的数字（便于对账与复现）
RANDOM_SEED = 20260101
# 业务时间按北京时间（UTC+8）生成，落库统一 UTC，界面按 Asia/Shanghai 展示
BUSINESS_TZ = dt_timezone(timedelta(hours=8))
# 演示能源报警的标记：避免与数采越限自动产生的报警互相「顶掉」
ENERGY_ALARM_MARK = "demo:xj-energy-alarm"

COMPANY = {
    "code": "XJYS",
    "name": "新疆意尚智造科技有限公司",
    "short_name": "新疆意尚智造",
    "address": "新疆维吾尔自治区乌鲁木齐市高新技术产业开发区（新市区）北区工业园",
    "contact_person": "李疆",
    "contact_phone": "0991-8800000",
}

DEMO_ROLES = (
    (
        "demo_dept_manager",
        "部门主管（演示）",
        DataScopeType.DEPARTMENT,
        (
            "workflow.instance.view",
            "workflow.instance.approve",
            "analytics.dashboard.view",
            "core.attachment.upload",
            "core.attachment.download",
        ),
    ),
    (
        "demo_gm",
        "总经理（演示）",
        DataScopeType.COMPANY,
        (
            "workflow.instance.view",
            "workflow.instance.approve",
            "workflow.instance.withdraw",
            "analytics.dashboard.view",
            "core.attachment.upload",
            "core.attachment.download",
        ),
    ),
    (
        "demo_finance",
        "财务复核（演示）",
        DataScopeType.COMPANY,
        (
            "workflow.instance.view",
            "workflow.instance.approve",
            "analytics.dashboard.view",
            "core.attachment.upload",
            "core.attachment.download",
        ),
    ),
)

def _generate_password(length: int = 18) -> str:
    alphabet = string.ascii_letters + string.digits + "!@#%^&*-_=+"
    while True:
        candidate = "".join(secrets.choice(alphabet) for _ in range(length))
        if (
            any(c.islower() for c in candidate)
            and any(c.isupper() for c in candidate)
            and any(c.isdigit() for c in candidate)
            and any(c in "!@#%^&*-_=+" for c in candidate)
        ):
            return candidate

# code, name, parent_code, department_type, sort_order
DEPARTMENTS = (
    ("GM", "总经理办公室", None, "management", 10),
    ("PROD", "生产部", None, "production", 20),
    ("PLAN", "计划科", "PROD", "production", 21),
    ("TECH", "技术科", "PROD", "production", 22),
    ("PUR", "采购部", None, "procurement", 30),
    ("SALES", "销售部", None, "sales", 40),
    ("WH", "仓储部", None, "warehouse", 50),
    ("QC", "质量部", None, "quality", 60),
    ("EAM", "设备动力部", None, "equipment", 70),
    ("ENERGY", "能源管理科", "EAM", "equipment", 71),
    ("IT", "信息部", None, "management", 80),
    ("HR", "人力资源部", None, "management", 90),
    ("FIN", "财务部", None, "management", 100),
    ("EHS", "安全环保部", None, "management", 110),
)

# code, name, address
FACTORIES = (
    ("F01", "乌鲁木齐智能工厂", "新疆乌鲁木齐市高新区北区工业园金山路 66 号"),
    ("F02", "阿克苏成衣加工基地", "新疆阿克苏地区阿克苏纺织工业城纺织大道 18 号"),
)

# factory_code -> ((workshop_code, workshop_name, workshop_type, sort, (line_code, line_name, line_type, capacity)), ...)
WORKSHOPS = {
    "F01": (
        ("CUT", "智能裁剪车间", "cutting", 10, ("CL01", "一号智能裁剪线", "automated", "1500")),
        ("SEW", "缝制一车间", "sewing", 20, ("SL01", "一号缝制线", "hanging", "1200")),
        ("SEW2", "缝制二车间", "sewing", 30, ("SL02", "二号缝制线", "manual", "1000")),
        ("FIN", "整烫包装车间", "finishing", 40, ("FL01", "一号整烫包装线", "manual", "1800")),
        ("PWR", "动力车间", "other", 50, ("PL01", "动力供应线", "automated", "0")),
    ),
    "F02": (
        ("SEW", "缝制车间", "sewing", 10, ("SL01", "一号缝制线", "manual", "900")),
        ("FIN", "整烫包装车间", "finishing", 20, ("FL01", "一号整烫包装线", "manual", "1100")),
    ),
}

STATIONS = (
    ("CUT-01", "自动裁床", "裁剪", 10),
    ("CUT-02", "验片", "裁剪", 20),
    ("SEW-01", "平缝", "缝制", 10),
    ("SEW-02", "包缝", "缝制", 20),
    ("SEW-03", "锁眼钉扣", "缝制", 30),
    ("FIN-01", "整烫", "整烫", 10),
    ("FIN-02", "成衣检验", "检验", 20),
    ("FIN-03", "包装入库", "包装", 30),
)

SHIFTS = (
    ("DAY", "白班", "10:00", "19:00", False, 60),
    ("MID", "中班", "17:00", "01:00", True, 45),
    ("NIGHT", "夜班", "22:00", "08:00", True, 45),
)

# employee_no, name, gender, dept, factory, position, employment, hire_date
EMPLOYEES = (
    ("XJ2001", "李疆", "male", "GM", "F01", "总经理", "full_time", "2018-03-01"),
    ("XJ2002", "王凯", "male", "PROD", "F01", "生产经理", "full_time", "2019-06-12"),
    ("XJ2003", "阿依古丽·买买提", "female", "PLAN", "F01", "计划主管", "full_time", "2020-09-03"),
    ("XJ2004", "张丽", "female", "PUR", "F01", "采购主管", "full_time", "2020-04-16"),
    ("XJ2005", "刘洋", "male", "SALES", "F01", "销售主管", "full_time", "2021-02-25"),
    ("XJ2006", "周梅", "female", "WH", "F01", "仓储主管", "full_time", "2019-11-06"),
    ("XJ2007", "吴刚", "male", "QC", "F01", "质量工程师", "full_time", "2020-07-15"),
    ("XJ2008", "郑涛", "male", "EAM", "F01", "设备主管", "full_time", "2019-05-18"),
    ("XJ2009", "冯雪", "female", "PROD", "F01", "缝纫工", "full_time", "2022-03-22"),
    ("XJ2010", "许静", "female", "PROD", "F01", "裁剪工", "full_time", "2022-08-09"),
    ("XJ2011", "何俊", "male", "PROD", "F01", "整烫工", "full_time", "2021-10-12"),
    ("XJ2012", "马超", "male", "PROD", "F02", "缝纫工", "full_time", "2022-04-01"),
    ("XJ2013", "朱婷", "female", "QC", "F02", "质检员", "full_time", "2022-06-20"),
    ("XJ2014", "范伟", "male", "IT", "F01", "信息化专员", "full_time", "2021-01-11"),
    ("XJ2015", "钱进", "male", "PUR", "F01", "采购专员", "full_time", "2021-05-10"),
    ("XJ2016", "杜娜", "female", "EHS", "F01", "安全环保主管", "full_time", "2020-08-17"),
    ("XJ2017", "黄强", "male", "ENERGY", "F01", "能源管理员", "full_time", "2021-07-05"),
    ("XJ2018", "徐慧", "female", "FIN", "F01", "财务主管", "full_time", "2019-09-23"),
    ("XJ2019", "张伟", "male", "EAM", "F01", "维修工", "full_time", "2022-05-09"),
    ("XJ2020", "李娜", "female", "HR", "F01", "人事专员", "full_time", "2022-09-01"),
)

# code, name, category, decimal_places（平台级共享，已存在则复用）
UOMS = (
    ("KG", "公斤", "weight", 3),
    ("M", "米", "length", 2),
    ("YD", "码", "length", 2),
    ("PCS", "个", "quantity", 0),
    ("PC", "件", "quantity", 0),
    ("SET", "套", "quantity", 0),
    ("DZ", "打", "quantity", 0),
    ("ROLL", "卷", "quantity", 0),
    ("CTN", "箱", "quantity", 0),
    ("UNIT", "台", "quantity", 0),
    ("L", "升", "volume", 2),
    ("M3", "立方米", "volume", 3),
    ("KWH", "千瓦时", "quantity", 2),
    ("T", "吨", "weight", 3),
)

# 只登记与批次/卷无关的固定换算；米↔公斤随卷变化，不在此登记
UOM_CONVERSIONS = (
    ("DZ", "PCS", "12"),
    ("YD", "M", "0.9144"),
    ("T", "KG", "1000"),
)

# code, name, category_type, parent_code, sort_order
MATERIAL_CATEGORIES = (
    ("FB", "面料", "fabric", None, 10),
    ("FB-KNIT", "针织面料", "fabric", "FB", 11),
    ("FB-WOVEN", "梭织面料", "fabric", "FB", 12),
    ("AC", "辅料", "accessory", None, 20),
    ("AC-THREAD", "缝纫线", "accessory", "AC", 21),
    ("AC-BTN", "钮扣", "accessory", "AC", 22),
    ("AC-ZIP", "拉链", "accessory", "AC", 23),
    ("AC-TAPE", "织带与罗纹", "accessory", "AC", 24),
    ("AC-LABEL", "商标与标签", "accessory", "AC", 25),
    ("SF", "半成品", "semifinished", None, 30),
    ("FG", "成品", "finished", None, 40),
    ("PKG", "包装物", "packaging", None, 50),
    ("SP", "备品备件", "spare_part", None, 60),
    ("SP-SEW", "缝制设备配件", "spare_part", "SP", 61),
    ("SP-ELEC", "电气与仪表备件", "spare_part", "SP", 62),
    ("CS", "消耗品", "consumable", None, 70),
)

# code, name, category, spec, base_uom, batch, roll, safe_stock, purchase_price, reference_cost
MATERIALS = (
    ("XJ-FAB-001", "新疆长绒棉汗布", "FB-KNIT", "60S 长绒棉 180g/m2 幅宽185cm", "KG",
     True, True, "800", "52.600000", "53.500000"),
    ("XJ-FAB-002", "精梳棉双面布", "FB-KNIT", "40S 双面 260g/m2 幅宽185cm", "KG",
     True, True, "600", "46.800000", "47.500000"),
    ("XJ-FAB-003", "棉涤工装面料", "FB-WOVEN", "棉涤 65/35 240g/m2 幅宽150cm", "KG",
     True, True, "500", "32.000000", "32.800000"),
    ("XJ-ACC-001", "涤纶缝纫线", "AC-THREAD", "40S/2 5000m 卷装", "ROLL",
     True, False, "300", "8.900000", "9.200000"),
    ("XJ-ACC-002", "树脂钮扣", "AC-BTN", "18L 四孔 黑色", "PCS",
     True, False, "30000", "0.120000", "0.130000"),
    ("XJ-ACC-003", "尼龙拉链", "AC-ZIP", "3# 60cm 闭尾", "PCS",
     True, False, "12000", "1.380000", "1.430000"),
    ("XJ-ACC-004", "棉涤罗纹", "AC-TAPE", "2x1 罗纹 幅宽60cm", "KG",
     True, False, "200", "33.000000", "34.000000"),
    ("XJ-ACC-005", "主唛织标", "AC-LABEL", "30x60mm 缎面", "PCS",
     True, False, "40000", "0.180000", "0.200000"),
    ("XJ-PKG-001", "三层瓦楞纸箱", "PKG", "600x400x300mm", "CTN",
     False, False, "3000", "6.400000", "6.700000"),
    ("XJ-PKG-002", "吊牌", "PKG", "90x50mm 铜版纸", "PCS",
     True, False, "50000", "0.250000", "0.270000"),
    ("XJ-PKG-003", "PE 透明胶袋", "PKG", "350x450mm 0.03mm", "PCS",
     False, False, "60000", "0.090000", "0.100000"),
    ("XJ-SP-001", "缝纫机压脚", "SP-SEW", "DB 标准压脚", "PCS",
     False, False, "150", "18.000000", "19.000000"),
    ("XJ-SP-002", "伺服电机碳刷", "SP-ELEC", "6x12x16mm", "PCS",
     False, False, "300", "4.500000", "5.000000"),
    ("XJ-SP-003", "缝纫机针", "SP-SEW", "DBx1 14#", "PCS",
     True, False, "8000", "0.350000", "0.400000"),
    ("XJ-SP-004", "空压机空气滤芯", "SP", "卡特式 120mm", "PCS",
     False, False, "60", "86.000000", "90.000000"),
    ("XJ-SP-005", "深沟球轴承 6204", "SP", "6204-2RS", "PCS",
     False, False, "120", "12.500000", "13.000000"),
    ("XJ-CS-001", "缝纫机油", "CS", "32# 白油 5L/桶", "L",
     False, False, "300", "23.000000", "24.000000"),
)

FABRIC_PROFILES = (
    ("XJ-FAB-001", "100% 新疆长绒棉", "185.00", "180.000", "本白", True, "3.800"),
    ("XJ-FAB-002", "100% 棉", "185.00", "260.000", "麻灰", True, "4.200"),
    ("XJ-FAB-003", "棉涤 65/35", "150.00", "240.000", "藏青", True, "2.500"),
)

COLORS = (
    ("BK", "黑色", "#000000", 10),
    ("WH", "白色", "#FFFFFF", 20),
    ("OW", "米白", "#F5F1E6", 30),
    ("NV", "藏青", "#1B2A4A", 40),
    ("MB", "雾霾蓝", "#7C98B3", 50),
    ("LG", "浅灰", "#D9D9D9", 70),
    ("KH", "卡其", "#C3B091", 80),
)

SIZES = (
    ("S", "S 155/76A", "women", 10),
    ("M", "M 160/80A", "women", 20),
    ("L", "L 165/84A", "women", 30),
    ("XL", "XL 170/88A", "women", 40),
    ("2XL", "2XL 175/92A", "women", 50),
    ("170A", "170/88A", "men", 60),
    ("175A", "175/92A", "men", 70),
    ("180A", "180/96A", "men", 80),
)

# code, name, size_group, brand, season, year, series
STYLES = (
    ("XJYS-W-2601", "女士圆领长袖T恤", "women", "意尚智造", "春夏", "2026", "新疆长绒棉系列"),
    ("XJYS-W-2602", "女士连帽卫衣", "women", "意尚智造", "秋冬", "2026", "新疆长绒棉系列"),
    ("XJYS-M-2601", "男士工装夹克", "men", "意尚智造", "秋冬", "2026", "工装系列"),
    ("XJYS-M-2602", "男士饶领短袖T恤", "men", "意尚智造", "春夏", "2026", "工装系列"),
)

# (每个款式对应的颜色集、尺码集) —— 颜色与尺码均使用上面已存在的全局编码
STYLE_SKUS = {
    "XJYS-W-2601": (("WH", "OW", "MB", "NV"), ("S", "M", "L", "XL")),
    "XJYS-W-2602": (("LG", "NV", "KH"), ("M", "L", "XL", "2XL")),
    "XJYS-M-2601": (("NV", "KH", "BK"), ("170A", "175A", "180A")),
    "XJYS-M-2602": (("WH", "BK", "NV"), ("170A", "175A", "180A")),
}

WAREHOUSES = (
    ("XJ-WH-RAW-01", "原料仓", "raw", "F01", "WH", False),
    ("XJ-WH-ACC-01", "辅料仓", "consumable", "F01", "WH", False),
    ("XJ-WH-FG-01", "成品仓", "finished", "F01", "WH", False),
    ("XJ-WH-SP-01", "备件仓", "spare", "F01", "EAM", False),
    ("XJ-WH-F02-01", "阿克苏成品仓", "finished", "F02", "WH", False),
)

ZONES = (
    ("RECV", "待检区", "receiving", 10),
    ("STO", "储存区", "storage", 20),
    ("SHIP", "发货区", "shipping", 30),
)

ZONE_LOCATION_GRID = {
    "RECV": (2, 2, 1),
    "STO": (2, 3, 2),
    "SHIP": (1, 2, 1),
}

# 客户（合成联系人与 138-0000-xxxx 合成号码，不含真实个人资料）
CUSTOMERS = (
    {
        "code": "XJ-CUS-001",
        "name": "乌鲁木齐天山羊绒制品有限公司",
        "short_name": "天山羊绒",
        "category": "brand",
        "level": "A",
        "status": "active",
        "credit_limit": "800000",
        "payment_terms": "月结 30 天",
        "tax_no": "91650100MA0XJ0001X",
        "address": "新疆乌鲁木齐市经济技术开发区中亚北路",
        "primary_contact_name": "石建国",
        "primary_contact_phone": "13800002001",
        "salesman_no": "XJ2005",
        "contacts": (
            {"name": "石建国", "position": "采购经理", "phone": "13800002001", "is_primary": True},
            {"name": "李婧", "position": "对账会计", "phone": "13800002002"},
        ),
    },
    {
        "code": "XJ-CUS-002",
        "name": "新疆西域工装科技有限公司",
        "short_name": "西域工装",
        "category": "direct",
        "level": "A",
        "status": "active",
        "credit_limit": "1200000",
        "payment_terms": "月结 45 天",
        "tax_no": "91650100MA0XJ0002Y",
        "address": "新疆乌鲁木齐市米东区工业园",
        "primary_contact_name": "王强",
        "primary_contact_phone": "13800002003",
        "salesman_no": "XJ2005",
        "contacts": (
            {"name": "王强", "position": "供应链总监", "phone": "13800002003", "is_primary": True},
        ),
    },
    {
        "code": "XJ-CUS-003",
        "name": "兰州西北服饰贸易有限公司",
        "short_name": "西北贸易",
        "category": "distributor",
        "level": "B",
        "status": "active",
        "credit_limit": "400000",
        "payment_terms": "月结 30 天",
        "tax_no": "91620100MA0GS0003Z",
        "address": "甘肃省兰州市七里河区西津东路",
        "primary_contact_name": "周俊",
        "primary_contact_phone": "13800002004",
        "salesman_no": "XJ2005",
        "contacts": (
            {"name": "周俊", "position": "总经理", "phone": "13800002004", "is_primary": True},
        ),
    },
    {
        "code": "XJ-CUS-004",
        "name": "京东服饰自营旗舰店（新疆专区）",
        "short_name": "京东专区",
        "category": "online",
        "level": "B",
        "status": "active",
        "credit_limit": "200000",
        "payment_terms": "预付",
        "address": "北京市亦庄经济技术开发区科创十一街",
        "primary_contact_name": "陈曦",
        "primary_contact_phone": "13800002005",
        "salesman_no": "XJ2005",
        "contacts": (
            {"name": "陈曦", "position": "运营负责人", "phone": "13800002005", "is_primary": True},
        ),
    },
    {
        "code": "XJ-CUS-005",
        "name": "喀什国际商贸城批发商行",
        "short_name": "喀什批发",
        "category": "agent",
        "level": "C",
        "status": "potential",
        "credit_limit": "0",
        "payment_terms": "现款",
        "address": "新疆喀什地区喀什市国际大巴扎",
        "primary_contact_name": "阿卜都拉·热合曼",
        "primary_contact_phone": "13800002006",
        "salesman_no": "XJ2005",
        "contacts": (
            {"name": "阿卜都拉·热合曼", "position": "采购主管", "phone": "13800002006", "is_primary": True},
        ),
    },
)

SUPPLIERS = (
    {
        "code": "XJ-SUP-001",
        "name": "新疆巴州棉纺有限责任公司",
        "short_name": "巴州棉纺",
        "category": "fabric",
        "grade": "A",
        "admission_status": "admitted",
        "payment_terms": "月结 60 天",
        "tax_no": "91652800MA0BZ0001A",
        "address": "新疆巴音郭楞蒙古自治州库尔勒市纺织工业园",
        "primary_contact_name": "孙倩",
        "primary_contact_phone": "13800002101",
        "buyer_no": "XJ2004",
        "contacts": (
            {"name": "孙倩", "position": "销售经理", "phone": "13800002101", "is_primary": True},
        ),
        "qualifications": (
            {"qualification_type": "business_license", "certificate_no": "XJ-BL-0001",
             "issued_by": "新疆巴音郭楞市场监督管理局",
             "issued_date": "2020-05-18", "expiry_date": "2032-05-17"},
            {"qualification_type": "quality_system", "certificate_no": "XJ-ISO9001-0001",
             "issued_by": "新疆自治区认证中心",
             "issued_date": "2024-03-01", "expiry_date": "2027-02-28"},
            {"qualification_type": "test_report", "certificate_no": "XJ-TR-0001",
             "issued_by": "新疆纺织产品质量检验中心",
             "issued_date": "2025-11-20", "expiry_date": "2026-11-19"},
        ),
    },
    {
        "code": "XJ-SUP-002",
        "name": "乌鲁木齐华瑞辅料有限公司",
        "short_name": "华瑞辅料",
        "category": "accessory",
        "grade": "A",
        "admission_status": "admitted",
        "payment_terms": "月结 30 天",
        "tax_no": "91650100MA0HR0002B",
        "address": "新疆乌鲁木齐市头屯河区工业园",
        "primary_contact_name": "钱伟",
        "primary_contact_phone": "13800002102",
        "buyer_no": "XJ2004",
        "contacts": (
            {"name": "钱伟", "position": "业务经理", "phone": "13800002102", "is_primary": True},
        ),
        "qualifications": (
            {"qualification_type": "business_license", "certificate_no": "XJ-BL-0002",
             "issued_by": "乌鲁木齐市市场监督管理局",
             "issued_date": "2021-08-09", "expiry_date": "2031-08-08"},
        ),
    },
    {
        "code": "XJ-SUP-003",
        "name": "新疆丝路机电设备有限公司",
        "short_name": "丝路机电",
        "category": "equipment",
        "grade": "B",
        "admission_status": "admitted",
        "payment_terms": "货到付款",
        "tax_no": "91650100MA0SD0003C",
        "address": "新疆乌鲁木齐市高新区科创大道",
        "primary_contact_name": "杨海",
        "primary_contact_phone": "13800002103",
        "buyer_no": "XJ2004",
        "contacts": (
            {"name": "杨海", "position": "区域销售", "phone": "13800002103", "is_primary": True},
        ),
        "qualifications": (
            {"qualification_type": "business_license", "certificate_no": "XJ-BL-0003",
             "issued_by": "乌鲁木齐市市场监督管理局",
             "issued_date": "2019-04-02", "expiry_date": "2029-04-01"},
        ),
    },
    {
        "code": "XJ-SUP-004",
        "name": "呼和浩特包装制品有限公司",
        "short_name": "呼市包装",
        "category": "packaging",
        "grade": "B",
        "admission_status": "admitted",
        "payment_terms": "月结 30 天",
        "address": "内蒙古自治区呼和浩特市玉泉区",
        "primary_contact_name": "赵霞",
        "primary_contact_phone": "13800002104",
        "buyer_no": "XJ2004",
        "contacts": (
            {"name": "赵霞", "position": "业务员", "phone": "13800002104", "is_primary": True},
        ),
        "qualifications": (
            {"qualification_type": "business_license", "certificate_no": "XJ-BL-0004",
             "issued_by": "呼和浩特市市场监督管理局",
             "issued_date": "2020-01-15", "expiry_date": "2030-01-14"},
            {"qualification_type": "test_report", "certificate_no": "",
             "issued_by": "呼市质检院",
             "issued_date": "2026-01-15", "expiry_date": None},
        ),
    },
    {
        "code": "XJ-SUP-005",
        "name": "新疆天池能源服务有限公司",
        "short_name": "天池能源",
        "category": "service",
        "grade": "C",
        "admission_status": "pending",
        "payment_terms": "月结 60 天",
        "address": "新疆乌鲁木齐市经济技术开发区",
        "primary_contact_name": "黄建",
        "primary_contact_phone": "13800002105",
        "buyer_no": "XJ2004",
        "contacts": (
            {"name": "黄建", "position": "项目经理", "phone": "13800002105", "is_primary": True},
        ),
        "qualifications": (),
    },
)


# 新疆意尚智造自己的审批模板（与 seed_demo 的模板共用同一组演示角色）
XJ_APPROVAL_TEMPLATES = (
    {
        "code": "XJ-AP-GENERAL",
        "name": "通用审批",
        "biz_type": "general",
        "description": "单节点部门审批。",
        "nodes": ({"seq": 1, "name": "部门主管审批", "role": "demo_dept_manager", "amount_min": None},),
    },
    {
        "code": "XJ-AP-PRC-REQ",
        "name": "采购申请审批",
        "biz_type": "procurement.requisition",
        "description": "部门主管 → 金额≥1 万总经理 → 金额≥5 万财务复核。",
        "nodes": (
            {"seq": 1, "name": "部门主管审批", "role": "demo_dept_manager", "amount_min": None},
            {"seq": 2, "name": "总经理审批", "role": "demo_gm", "amount_min": "10000"},
            {"seq": 3, "name": "财务复核", "role": "demo_finance", "amount_min": "50000"},
        ),
    },
    {
        "code": "XJ-AP-PRC-ORDER",
        "name": "采购订单审批",
        "biz_type": "procurement.order",
        "description": "部门主管 → 金额≥10 万总经理审批。",
        "nodes": (
            {"seq": 1, "name": "部门主管审批", "role": "demo_dept_manager", "amount_min": None},
            {"seq": 2, "name": "总经理审批", "role": "demo_gm", "amount_min": "100000"},
        ),
    },
    {
        "code": "XJ-AP-SALES-ORDER",
        "name": "销售订单审批",
        "biz_type": "sales.order",
        "description": "部门主管审批；金额≥5 万追加总经理，≥20 万追加财务复核。",
        "nodes": (
            {"seq": 1, "name": "部门主管审批", "role": "demo_dept_manager", "amount_min": None},
            {"seq": 2, "name": "总经理审批", "role": "demo_gm", "amount_min": "50000"},
            {"seq": 3, "name": "财务复核", "role": "demo_finance", "amount_min": "200000"},
        ),
    },
    {
        "code": "XJ-AP-BOM",
        "name": "料件清单审批",
        "biz_type": "planning.bom",
        "description": "料件清单版本审核：部门主管审批。",
        "nodes": ({"seq": 1, "name": "部门主管审批", "role": "demo_dept_manager", "amount_min": None},),
    },
    {
        "code": "XJ-AP-ROUTING",
        "name": "工艺路线审批",
        "biz_type": "planning.routing",
        "description": "工艺路线版本审核：部门主管审批。",
        "nodes": ({"seq": 1, "name": "部门主管审批", "role": "demo_dept_manager", "amount_min": None},),
    },
)

# username, display_name, employee_no, role_codes
XJ_USERS = (
    ("xj_admin", "范伟", "XJ2014", ("super_admin",)),
    ("xj_mgr", "王凯", "XJ2002", ("demo_dept_manager",)),
    ("xj_gm", "李疆", "XJ2001", ("demo_gm",)),
    ("xj_finance", "徐慧", "XJ2018", ("demo_finance",)),
)


def _forget_permission_cache(user) -> None:
    """清掉指定用户的权限缓存条目。

    演示命令是在同一个事务里反复 bump_permission_version() 的：一旦事务回滚，
    版本号不会前进，而 identity:user_perms:<pk>:<version> 这个键会残留旧值，
    后续运行就会一直命中"没有权限"的陈旧结果（服务层 require_codes 误判）。
    """
    version = int(user.permission_version or 0)
    cache.delete_many(
        [
            f"identity:user_perms:{user.pk}:{item}"
            for item in range(max(version - 1, 0), version + 2)
        ]
    )


class Command(BaseCommand):
    help = "写入新疆意尚智造科技有限公司的演示数据（2026 年起，幂等，生产环境禁止）。"

    def add_arguments(self, parser) -> None:
        parser.add_argument("--yes", action="store_true", help="在非开发环境中确认执行。")
        parser.add_argument(
            "--skip-heavy",
            action="store_true",
            help="跳过读数 / 点巡检等数量较大的记录（用于快速建立骨架）。",
        )

    def handle(self, *args, **options) -> None:
        environment = settings.DJANGO_ENV
        if environment == "production":
            raise CommandError(
                "seed_demo_xjys 禁止在生产环境执行。请使用 bootstrap_system 初始化系统数据。"
            )
        if environment not in {"development", "test"} and not options["yes"]:
            raise CommandError(f"当前环境为 {environment}，如确认写入演示数据请追加 --yes。")

        random.seed(RANDOM_SEED)
        self.counts: dict[str, int] = {}
        self.created_passwords: list[tuple[str, str]] = []
        self.skip_heavy = bool(options["skip_heavy"])
        today = date.today()
        # 业务日期窗口：2026-01-01 至今天（不会超出当前日期）
        self.today = today
        self.horizon_days = max((today - DATA_START).days, 1)

        with transaction.atomic():
            self.company = self._company()
            self.departments = self._departments()
            self.factories = self._factories()
            self.workshops, self.lines = self._workshops()
            self._stations()
            self.shifts = self._shifts()
            self.employees = self._employees()
            self._teams()
            self.uoms = self._uoms()
            self.categories = self._material_categories()
            self.materials = self._materials()
            self._fabric_profiles()
            self.colors = self._colors()
            self.sizes = self._sizes()
            self.styles = self._styles()
            self._skus()
            self._warehouses()
            self.customers = self._customers()
            self.suppliers = self._suppliers()
            self._demo_roles()
            self.users = self._users()
            self.actor = self.users["xj_admin"]
            self._approval_templates()
            self.equipment_types = self._equipment_types()
            self.equipments = self._equipments()
            self.spare_parts = self._spare_parts()
            self._equipment_parts()
            self.maintenance_items = self._maintenance_items()
            self.inspection_items = self._inspection_items()
            self.abnormal_types = self._abnormal_types()
            self._equipment_flow()
            self._energy_master()
            self._energy_reading_flow()
            self._energy_run_flow()
            self._energy_alarm_flow()
            self._iot_master()
            self._iot_flow()
            self._inventory_flow()
            self._procurement_flow()
            self._planning_flow()
            self._sales_flow()
            self._mes_flow()
            self._mrp_flow()
            self._qms_flow()
            self._srm_flow()
            self._crm_flow()
            self._ehs_flow()
            self._logistics_flow()

        self._report()
        if self.created_passwords:
            lines = "\n".join(f"    {name}：{pwd}" for name, pwd in self.created_passwords)
            self.stdout.write(self.style.WARNING("以下演示账号为本次新建，口令仅显示一次（请勿用于生产）：\n" + lines))

    # -- 通用工具 ------------------------------------------------------
    def _count(self, label: str, created: bool = True) -> None:
        if created:
            self.counts[label] = self.counts.get(label, 0) + 1

    def _upsert(self, model, key: dict, defaults: dict):
        """公司范围内的业务主数据：按业务键复用已有记录。"""
        defaults = dict(defaults)
        if any(f.name == "remark" for f in model._meta.get_fields()):
            defaults["remark"] = DEMO_REMARK
        obj, created = model.objects.update_or_create(**key, defaults=defaults)
        self._count(model._meta.label, created)
        return obj

    def _ensure(self, model, key: dict, defaults: dict):
        """平台级共享参考数据：已存在就原样保留（不覆盖其他公司用过的字典）。"""
        obj, created = model.objects.get_or_create(**key, defaults=defaults)
        self._count(model._meta.label, created)
        return obj

    def _report(self) -> None:
        total = sum(self.counts.values())
        self.stdout.write(self.style.SUCCESS(f"新疆意尚智造演示数据：新建 {total} 条。"))
        for label in sorted(self.counts):
            self.stdout.write(f"  {label}: +{self.counts[label]}")
        self.stdout.write(
            f"公司：{self.company.name}（{self.company.code}）；"
            f"业务日期区间：{DATA_START} ~ {self.today}。"
        )

    def _demo_roles(self) -> None:
        """补齐审批节点需要的演示角色（``demo_dept_manager`` 等）。

        角色挂在公司下，因此这里**只在缺失时创建**：覆盖式 upsert 会把已存在的角色
        改到本公司，属于动别人的数据。
        """

        for code, name, scope, codes in DEMO_ROLES:
            if Role.objects.filter(code=code).exists():
                continue
            role = Role.objects.create(
                code=code,
                name=name,
                company=self.company,
                data_scope_type=scope,
                is_system=False,
                is_active=True,
                sort_order=200,
                remark=f"{DEMO_REMARK}：审批节点路由使用。",
            )
            permissions = list(Permission.objects.filter(code__in=codes))
            missing = set(codes) - {item.code for item in permissions}
            if missing:
                raise CommandError(
                    f"演示角色 {code} 引用了未注册的权限点：{sorted(missing)}；请先执行 bootstrap_system。"
                )
            role.permissions.set(permissions)
            selected = list(Menu.objects.filter(permission_code__in=codes, is_active=True))
            # 补齐上级目录，否则页面可见但导航目录缺失
            parent_codes = {item.parent.code for item in selected if item.parent_id}
            selected += list(Menu.objects.filter(code__in=parent_codes))
            role.menus.set(selected)
            self._count("identity.Role", True)

    def _users(self) -> dict[str, User]:
        """新疆意尚智造自己的演示账号（建立人与审批人）。

        口令优先 ``YISHANG_DEMO_PASSWORD``，否则随机生成并打印一次；
        已存在的账号只同步归属与角色，**不会重置口令**。
        """

        result: dict[str, User] = {}
        configured = settings.YISHANG.get("DEMO_PASSWORD") or ""
        for username, display_name, employee_no, role_codes in XJ_USERS:
            employee = self.employees.get(employee_no)
            department = employee.department if employee else None
            user = User.objects.filter(username=username).first()
            if user is None:
                password = configured or _generate_password()
                user = User(
                    username=username,
                    display_name=display_name,
                    company=self.company,
                    department=department,
                    remark=f"{DEMO_REMARK}：{display_name}",
                )
                user.set_password(password)
                user.must_change_password = False
                user.save()
                self.created_passwords.append((username, password))
                self._count("identity.User")
            else:
                user.display_name = display_name
                user.company = self.company
                user.department = department
                user.is_active = True
                user.must_change_password = False
                user.remark = f"{DEMO_REMARK}：{display_name}"
                user.save(
                    update_fields=[
                        "display_name", "company", "department", "is_active",
                        "must_change_password", "remark", "updated_at",
                    ]
                )
            if employee is not None and employee.user_id != user.pk:
                employee.user = user
                employee.save(update_fields=["user", "updated_at"])

            roles = list(Role.objects.filter(code__in=role_codes))
            missing = set(role_codes) - {item.code for item in roles}
            if missing:
                raise CommandError(f"演示账号 {username} 引用了不存在的角色：{sorted(missing)}")
            role_ids = [role.pk for role in roles]
            UserRole.objects.filter(user=user).exclude(role_id__in=role_ids).delete()
            existing = set(UserRole.objects.filter(user=user).values_list("role_id", flat=True))
            UserRole.objects.bulk_create(
                [UserRole(user=user, role=role) for role in roles if role.pk not in existing],
                ignore_conflicts=True,
            )
            user.bump_permission_version()
            _forget_permission_cache(user)
            result[username] = user
        return result

    def _approve_fully(self, instance_id, document) -> bool:
        """把审批实例推到「已通过」（按节点角色逐个审批）。

        与 seed_demo 一致：全程走 `apps.workflow.services`，不直接改审批表。
        """
        from apps.workflow import services as workflow_services
        from apps.workflow.models import ApprovalInstance, InstanceStatus, StepStatus

        actor = getattr(self, "users", {}).get("xj_mgr")
        if actor is None or instance_id is None:
            return False
        instance = ApprovalInstance.objects.filter(pk=instance_id).first()
        for _ in range(10):
            if instance is None or instance.status != InstanceStatus.PENDING:
                break
            step = instance.steps.filter(status=StepStatus.PENDING).order_by("seq").first()
            if step is None:
                break
            candidates = set(step.candidate_user_ids())
            username = {
                "demo_gm": "xj_gm",
                "demo_finance": "xj_finance",
            }.get(getattr(step.approver_role, "code", ""), "xj_mgr")
            approver = self.users.get(username)
            if approver is None or approver.pk not in candidates:
                approver = self.users.get("xj_mgr")
            if approver is None or approver.pk not in candidates:
                self.stdout.write(self.style.WARNING(f"没有可用的演示审批人，审批实例 {instance.instance_no} 停在当前节点。"))
                break
            workflow_services.approve_instance(approver, instance, comment="演示审批通过")
            instance.refresh_from_db()
        document.refresh_from_db()
        return instance is not None and instance.status == InstanceStatus.APPROVED

    # -- 演示数据工具（时间 / 取值） --------------------------------------
    def _aware(self, day: date, hour: int = 8, minute: int = 0) -> datetime:
        """按北京时间（UTC+8）生成业务时间，落库仍是 UTC。"""
        return datetime(day.year, day.month, day.day, hour, minute, tzinfo=BUSINESS_TZ)

    def _rand_date(self, *, start: date | None = None, end: date | None = None) -> date:
        start = start or DATA_START
        end = end or self.today
        if end <= start:
            return start
        return start + timedelta(days=random.randrange((end - start).days + 1))

    def _stamp(self, instance, **fields) -> None:
        """只用于把演示数据的时间字段对齐到 2026 年区间，不改变任何业务状态。"""
        if not fields:
            return
        type(instance).objects.filter(pk=instance.pk).update(**fields)
        for name, value in fields.items():
            setattr(instance, name, value)

    def _measured_value(self, item) -> Decimal | None:
        low, high = item.lower_limit, item.upper_limit
        if low is None and high is None:
            return None
        low = low if low is not None else Decimal("0")
        high = high if high is not None else low + Decimal("10")
        span = high - low
        if span <= 0:
            return low
        return (low + span * Decimal(str(round(random.uniform(0.15, 0.85), 4)))).quantize(
            Decimal("0.001")
        )

    # -- 设备管理 ----------------------------------------------------------
    def _equipment_types(self) -> dict[str, EquipmentType]:
        result: dict[str, EquipmentType] = {}
        for code, name, category, is_special, cycle in EQUIPMENT_TYPES:
            result[code] = self._ensure(
                EquipmentType,
                {"code": code},
                {
                    "name": name,
                    "category": category,
                    "is_special": is_special,
                    "maintenance_cycle_days": cycle,
                    "is_active": True,
                    "remark": DEMO_REMARK,
                },
            )
        return result

    def _equipments(self) -> dict[str, Equipment]:
        result: dict[str, Equipment] = {}
        for (
            code,
            name,
            type_code,
            status,
            factory_code,
            workshop_key,
            line_key,
            location,
            brand,
            model_no,
            serial_no,
            purchase,
            start,
            value,
            warranty,
            dept_code,
            owner_no,
        ) in EQUIPMENTS:
            equipment_type = self.equipment_types[type_code]
            result[code] = self._upsert(
                Equipment,
                {"company": self.company, "code": code},
                {
                    "name": name,
                    "equipment_type": equipment_type,
                    "status": status,
                    "factory": self.factories.get(factory_code),
                    "workshop": self.workshops.get(workshop_key),
                    "production_line": self.lines.get(line_key),
                    "location": location,
                    "brand": brand,
                    "model_no": model_no,
                    "serial_no": serial_no,
                    "supplier": self.suppliers.get("XJ-SUP-003"),
                    "purchase_date": date.fromisoformat(purchase),
                    "start_date": date.fromisoformat(start),
                    "original_value": Decimal(value),
                    "warranty_until": date.fromisoformat(warranty),
                    "is_special": bool(equipment_type.is_special),
                    "owner_department": self.departments.get(dept_code),
                    "owner_employee": self.employees.get(owner_no),
                    "is_active": True,
                },
            )
        return result

    def _spare_parts(self) -> dict[str, SparePart]:
        result: dict[str, SparePart] = {}
        for (
            code,
            name,
            part_type,
            spec,
            material_code,
            type_code,
            safety_stock,
            price,
            life_days,
            supplier_code,
        ) in SPARE_PARTS:
            result[code] = self._upsert(
                SparePart,
                {"company": self.company, "code": code},
                {
                    "name": name,
                    "part_type": part_type,
                    "spec": spec,
                    "material": self.materials.get(material_code) if material_code else None,
                    "equipment_type": self.equipment_types.get(type_code) if type_code else None,
                    "uom": self.uoms["PCS"],
                    "safety_stock": Decimal(safety_stock),
                    "reference_price": Decimal(price),
                    "life_days": life_days,
                    "supplier": self.suppliers.get(supplier_code),
                    "is_active": True,
                },
            )
        return result

    def _equipment_parts(self) -> None:
        for equipment_code, name, part_type, spec, quantity, uom_code, position, life_days in (
            EQUIPMENT_PARTS
        ):
            self._upsert(
                EquipmentPart,
                {"equipment": self.equipments[equipment_code], "name": name},
                {
                    "part_type": part_type,
                    "spec": spec,
                    "quantity": Decimal(quantity),
                    "uom": self.uoms[uom_code],
                    "position": position,
                    "life_days": life_days,
                    "is_active": True,
                },
            )

    def _maintenance_items(self) -> dict[str, MaintenanceItem]:
        result: dict[str, MaintenanceItem] = {}
        for code, name, category, type_code, cycle_days, standard in MAINTENANCE_ITEMS:
            result[code] = self._ensure(
                MaintenanceItem,
                {"code": code},
                {
                    "name": name,
                    "category": category,
                    "equipment_type": self.equipment_types.get(type_code) if type_code else None,
                    "cycle_days": cycle_days,
                    "standard": standard,
                    "is_active": True,
                    "remark": DEMO_REMARK,
                },
            )
        return result

    def _inspection_items(self) -> dict[str, InspectionItem]:
        result: dict[str, InspectionItem] = {}
        for code, name, method, standard, uom_code, lower, upper in INSPECTION_ITEMS:
            result[code] = self._ensure(
                InspectionItem,
                {"code": code},
                {
                    "name": name,
                    "method": method,
                    "standard": standard,
                    "uom": self.uoms.get(uom_code) if uom_code else None,
                    "lower_limit": Decimal(lower) if lower is not None else None,
                    "upper_limit": Decimal(upper) if upper is not None else None,
                    "is_active": True,
                    "remark": DEMO_REMARK,
                },
            )
        return result

    def _abnormal_types(self) -> dict[str, AbnormalType]:
        result: dict[str, AbnormalType] = {}
        for code, name, level in ABNORMAL_TYPES:
            result[code] = self._ensure(
                AbnormalType,
                {"code": code},
                {"name": name, "level": level, "is_active": True, "remark": DEMO_REMARK},
            )
        return result

    # -- 设备业务闭环 ------------------------------------------------------
    def _equipment_flow(self) -> None:
        self._maintenance_flow()
        self._repair_flow()
        self._inspection_flow()
        self._abnormal_flow()

    def _maintenance_flow(self) -> None:
        from apps.equipment import services as equipment_services

        if MaintenanceTask.objects.filter(company=self.company).exists():
            self.stdout.write("  设备保养：已存在演示任务，跳过。")
            return
        for key, name, equipment_code, cycle_days, item_codes, owner_no, dept_code in (
            MAINTENANCE_PLANS
        ):
            start = self._rand_date(end=DATA_START + timedelta(days=20))
            plan = self._upsert(
                MaintenancePlan,
                {"company": self.company, "plan_no": f"XJ-MP-{key.upper()}"},
                {
                    "name": name,
                    "equipment": self.equipments[equipment_code],
                    "cycle_days": cycle_days,
                    "start_date": start,
                    "next_date": start,
                    "responsible_employee": self.employees[owner_no],
                    "department": self.departments[dept_code],
                    "is_active": True,
                },
            )
            plan.items.set([self.maintenance_items[code] for code in item_codes])
            for _ in range(20):
                created = equipment_services.generate_maintenance_tasks(plan, until_date=self.today)
                if not created:
                    break
                for _task in created:
                    self._count("equipment.MaintenanceTask", True)

        closing = self.today - timedelta(days=2)
        pending = MaintenanceTask.objects.filter(
            company=self.company, status=TaskStatus.PENDING, plan_date__lte=closing
        ).order_by("plan_date")
        for task in pending:
            if random.random() < 0.15:
                continue
            day = task.plan_date
            equipment_services.start_equipment_task(task, timestamp=self._aware(day, 9, 30))
            record = equipment_services.complete_maintenance_task(
                task,
                executor=task.assignee,
                content=f"按《{task.plan.name}》要求逐项执行保养，填写保养卡并复检。",
                result=random.choice(
                    [
                        "保养完成，设备运行平稳，参数在标准范围。",
                        "更换易损件后复检合格，运行正常。",
                        "发现轻微渗油，现场处理后复检合格。",
                        "润滑与紧固到位，试机 30 分钟无异常。",
                    ]
                ),
                is_qualified=random.random() > 0.08,
                cost=Decimal(str(round(random.uniform(0, 480), 2))),
                maintain_date=day,
            )
            self._count("equipment.MaintenanceRecord", True)
            self._stamp(
                task,
                started_at=self._aware(day, 9, 30),
                finished_at=self._aware(day, 11, 10),
            )
            self._stamp(record, created_at=self._aware(day, 11, 15))

        future = MaintenanceTask.objects.filter(
            company=self.company, status=TaskStatus.PENDING, plan_date__gt=self.today
        ).order_by("plan_date")
        for task in future:
            self._stamp(
                task,
                started_at=None,
                finished_at=None,
                created_at=self._aware(task.plan_date - timedelta(days=7), 8, 30),
            )

    def _repair_flow(self) -> None:
        from apps.equipment import services as equipment_services

        if FaultReport.objects.filter(company=self.company).exists():
            self.stdout.write("  设备维修：已存在演示报修单，跳过。")
            return
        definitions = (
            ("XJ-EQ-SEW-04", "high", "四号平缝机主轴异响、转速不稳，怀疑轴承磨损。", "completed", "XJ2019"),
            ("XJ-EQ-CUT-02", "medium", "二号裁床刀头定位偏差超差，裁片尺寸不稳定。", "completed", "XJ2019"),
            ("XJ-EQ-BOILER-01", "critical", "锅炉点火失败并报故障，蒸汽压力无法建立。", "completed", "XJ2020"),
            ("XJ-EQ-AIR-01", "high", "空压机排气温度偏高，压差报警。", "completed", "XJ2020"),
            ("XJ-EQ-IRON-01", "medium", "整烫机汽缸密封处漏气，压力保持不住。", "in_progress", "XJ2019"),
            ("XJ-EQ-OVL-01", "low", "包缝机线迹跳针，需调整弯针与张力。", "assigned", "XJ2019"),
            ("XJ-EQ-AGV-01", "high", "AGV 行走驱动轮异响并停摆，无法自动搬运。", "reported", "XJ2020"),
            ("XJ-EQ-ELEC-01", "critical", "配电柜断路器温升异常，红外检测超温。", "reported", "XJ2020"),
        )
        for equipment_code, level, description, outcome, repairer_no in definitions:
            day = self._rand_date(end=self.today - timedelta(days=1))
            equipment = self.equipments[equipment_code]
            reporter = self.employees[random.choice(["XJ2009", "XJ2010", "XJ2011", "XJ2013"])]
            report = equipment_services.raise_fault_report(
                equipment=equipment,
                description=description,
                level=level,
                reporter=reporter,
                company=self.company,
                remark=DEMO_REMARK,
            )
            self._count("equipment.FaultReport", True)
            self._stamp(
                report,
                reported_at=self._aware(day, 10, 20),
                created_at=self._aware(day, 10, 20),
            )
            if outcome in {"reported", "cancelled"}:
                continue
            assigned_day = day + timedelta(days=1)
            task = equipment_services.create_repair_task_from_report(
                report,
                assignee=self.employees[repairer_no],
                symptom=description,
                assigned_date=assigned_day,
                remark=DEMO_REMARK,
            )
            self._count("equipment.RepairTask", True)
            self._stamp(task, created_at=self._aware(assigned_day, 8, 40))
            if outcome == "completed":
                equipment_services.start_equipment_task(
                    task, timestamp=self._aware(assigned_day, 9, 0)
                )
                repair_day = assigned_day + timedelta(days=random.randint(0, 2))
                record = equipment_services.complete_repair_task(
                    task,
                    repairer=self.employees[repairer_no],
                    fault_reason=random.choice(
                        [
                            "轴承磨损导致配合间隙过大。",
                            "长期运行后紧固件松动，定位漂移。",
                            "点火电极积碳，火焰检测信号弱。",
                            "滤芯堵塞导致进气不足、排气温度升高。",
                        ]
                    ),
                    solution=random.choice(
                        [
                            "更换轴承并调整同轴度，试机 2 小时正常。",
                            "重新校准定位并更换磨损件，首件检验合格。",
                            "清理电极并调整间隙，点火恢复正常。",
                            "更换滤芯与油分离芯，压差回到正常范围。",
                        ]
                    ),
                    parts_used=random.choice(["轴承 6204×2", "刀片 4 片", "点火电极×1", "空气滤芯×1"]),
                    cost=Decimal(str(round(random.uniform(120, 2600), 2))),
                    downtime_minutes=random.choice([60, 90, 120, 180, 240]),
                    result="维修完成，设备恢复运行并复检合格。",
                    repair_date=repair_day,
                )
                self._count("equipment.RepairRecord", True)
                self._stamp(record, created_at=self._aware(repair_day, 16, 30))
                self._stamp(
                    task,
                    started_at=self._aware(assigned_day, 9, 0),
                    finished_at=self._aware(repair_day, 16, 20),
                )
                report.refresh_from_db()
                if report.status != FaultReportStatus.CLOSED:
                    equipment_services.close_fault_report(report)
                    self._stamp(report, closed_at=self._aware(repair_day, 16, 30))
            elif outcome == "in_progress":
                equipment_services.start_equipment_task(
                    task, timestamp=self._aware(assigned_day, 9, 0)
                )
                self._stamp(task, started_at=self._aware(assigned_day, 9, 0))

    def _inspection_flow(self) -> None:
        from apps.equipment import services as equipment_services

        if InspectionTask.objects.filter(company=self.company).exists():
            self.stdout.write("  点巡检：已存在演示任务，跳过。")
            return
        definitions = (
            ("XJ-EQ-CUT-01", InspectionTaskType.POINT, "XJ2010", "completed"),
            ("XJ-EQ-CUT-02", InspectionTaskType.POINT, "XJ2010", "completed"),
            ("XJ-EQ-SEW-01", InspectionTaskType.PATROL, "XJ2009", "completed"),
            ("XJ-EQ-SEW-02", InspectionTaskType.POINT, "XJ2009", "completed"),
            ("XJ-EQ-SEW-05", InspectionTaskType.PATROL, "XJ2009", "completed"),
            ("XJ-EQ-OVL-01", InspectionTaskType.POINT, "XJ2011", "completed"),
            ("XJ-EQ-BTN-01", InspectionTaskType.POINT, "XJ2011", "completed"),
            ("XJ-EQ-IRON-01", InspectionTaskType.PATROL, "XJ2011", "completed"),
            ("XJ-EQ-AIR-01", InspectionTaskType.PATROL, "XJ2020", "completed"),
            ("XJ-EQ-AIR-02", InspectionTaskType.POINT, "XJ2020", "in_progress"),
            ("XJ-EQ-BOILER-01", InspectionTaskType.PATROL, "XJ2019", "completed"),
            ("XJ-EQ-PRES-01", InspectionTaskType.POINT, "XJ2019", "in_progress"),
            ("XJ-EQ-ELEC-01", InspectionTaskType.PATROL, "XJ2017", "completed"),
            ("XJ-EQ-PV-01", InspectionTaskType.PATROL, "XJ2017", "completed"),
            ("XJ-EQ-AGV-01", InspectionTaskType.POINT, "XJ2020", "pending"),
            ("XJ-EQ-AGV-02", InspectionTaskType.POINT, "XJ2020", "pending"),
            ("XJ-EQ-TEST-01", InspectionTaskType.POINT, "XJ2007", "pending"),
            ("XJ-EQ-SEW-06", InspectionTaskType.POINT, "XJ2009", "cancelled"),
        )
        item_pool = list(self.inspection_items.values())
        abnormal_count = 0
        fault_candidates: list[InspectionRecord] = []
        for equipment_code, task_type, inspector_no, outcome in definitions:
            day = self._rand_date(end=self.today)
            equipment = self.equipments[equipment_code]
            inspector = self.employees[inspector_no]
            task = InspectionTask.objects.create(
                company=self.company,
                task_no=next_inspection_task_no(),
                task_type=task_type,
                equipment=equipment,
                plan_date=day,
                assignee=inspector,
                remark=DEMO_REMARK,
            )
            self._count("equipment.InspectionTask", True)
            self._stamp(task, created_at=self._aware(day - timedelta(days=3), 8, 0))
            if outcome == "pending":
                continue
            if outcome == "cancelled":
                equipment_services.cancel_equipment_task(task, reason="设备停机检修，点巡检顺延。")
                continue
            task.items.set(random.sample(item_pool, k=random.randint(4, 6)))
            equipment_services.start_equipment_task(task, timestamp=self._aware(day, 9, 0))
            task_items = list(task.items.all())
            for index, item in enumerate(task_items):
                value = self._measured_value(item)
                abnormal = random.random() < 0.12
                record = InspectionRecord.objects.create(
                    company=self.company,
                    record_no=next_inspection_record_no(),
                    task=task,
                    equipment=equipment,
                    item=item,
                    inspected_at=self._aware(day, 9, 20 + index * 6),
                    inspector=inspector,
                    measured_value=value,
                    result=InspectionResult.ABNORMAL if abnormal else InspectionResult.NORMAL,
                    abnormal_desc=(
                        random.choice(
                            [
                                "实测值超出标准范围，需停机复核。",
                                "存在异响与温升，建议转报修处理。",
                                "压力保持不住，疑似泄漏。",
                                "安全护罩固定螺栓松动。",
                            ]
                        )
                        if abnormal
                        else ""
                    ),
                    remark=DEMO_REMARK,
                )
                self._count("equipment.InspectionRecord", True)
                if abnormal:
                    abnormal_count += 1
                    if abnormal_count % 2 == 1:
                        fault_candidates.append(record)
            if outcome == "completed":
                equipment_services.finish_equipment_task(
                    task, result=f"共检查 {len(task_items)} 项，正常 {len(task_items) - 1} 项。"
                )
                self._stamp(
                    task,
                    started_at=self._aware(day, 9, 0),
                    finished_at=self._aware(day, 10, 30),
                )
            else:
                self._stamp(task, started_at=self._aware(day, 9, 0))
        for record in fault_candidates[:4]:
            report = equipment_services.raise_fault_from_inspection(
                record,
                level=FaultLevel.MEDIUM if record.equipment_id else FaultLevel.HIGH,
                reporter=record.inspector,
            )
            self._count("equipment.FaultReport", True)
            self._stamp(
                report,
                reported_at=record.inspected_at,
                created_at=record.inspected_at,
            )

    def _abnormal_flow(self) -> None:
        from apps.equipment import services as equipment_services

        if AbnormalTask.objects.filter(company=self.company).exists():
            self.stdout.write("  设备异常：已存在演示任务，跳过。")
            return
        definitions = (
            ("XJ-EQ-SEW-04", "XJ-AT-002", AbnormalSource.INSPECTION, "high", "缝制一车间四号平缝机振动超标，实测 6.1mm/s，已停机待修。", "closed", "XJ2019"),
            ("XJ-EQ-CUT-02", "XJ-AT-001", AbnormalSource.DEVICE, "medium", "二号裁床主电机外壳温度 78℃，超过 70℃ 预警线。", "closed", "XJ2019"),
            ("XJ-EQ-AIR-01", "XJ-AT-004", AbnormalSource.DEVICE, "high", "空压站管路压力波动大，疑似气路泄漏。", "closed", "XJ2020"),
            ("XJ-EQ-ELEC-01", "XJ-AT-003", AbnormalSource.INSPECTION, "critical", "配电柜出线端温升异常，红外测温 92℃。", "closed", "XJ2017"),
            ("XJ-EQ-IRON-01", "XJ-AT-004", AbnormalSource.INSPECTION, "medium", "整烫机蒸汽管接头轻微泄漏，压力不稳。", "closed", "XJ2020"),
            ("XJ-EQ-SEW-06", "XJ-AT-006", AbnormalSource.MANUAL, "low", "六号平缝机运行时有周期性异响，未影响产能。", "handling", "XJ2019"),
            ("XJ-EQ-PV-01", "XJ-AT-001", AbnormalSource.DEVICE, "medium", "光伏汇流箱温升偏高，组件表面沙尘覆盖。", "assigned", "XJ2017"),
            ("XJ-EQ-AGV-02", "XJ-AT-003", AbnormalSource.MANUAL, "high", "AGV 充电桩通讯中断，无法自动回充。", "reported", "XJ2020"),
        )
        for equipment_code, type_code, source, _level, description, outcome, handler_no in (
            definitions
        ):
            day = self._rand_date(end=self.today)
            equipment = self.equipments[equipment_code]
            reporter = self.employees[random.choice(["XJ2009", "XJ2010", "XJ2011", "XJ2013"])]
            handler = self.employees[handler_no]
            task = AbnormalTask.objects.create(
                company=self.company,
                task_no=next_abnormal_task_no(),
                abnormal_type=self.abnormal_types[type_code],
                equipment=equipment,
                source=source,
                description=description,
                reported_by=reporter,
                reported_at=self._aware(day, 11, 0),
                remark=DEMO_REMARK,
            )
            self._count("equipment.AbnormalTask", True)
            self._stamp(task, created_at=self._aware(day, 11, 0))
            if outcome == "reported":
                continue
            deadline = day + timedelta(days=3)
            equipment_services.assign_abnormal_task(task, handler=handler, deadline=deadline)
            self._stamp(task, reported_at=self._aware(day, 11, 0))
            if outcome == "assigned":
                continue
            equipment_services.start_abnormal_handling(
                task, action="现场核查并制定临时处置措施，安排停机窗口。"
            )
            if outcome == "handling":
                continue
            handle_day = day + timedelta(days=random.randint(1, 3))
            record = equipment_services.close_abnormal_task(
                task,
                action=random.choice(
                    [
                        "停机更换磨损件并重新对中，复测振动值 2.1mm/s。",
                        "清理散热通道并加装轴流风机，温升降至 58℃。",
                        "更换老化气管接头，保压试验 30 分钟无泄漏。",
                        "紧固出线端螺栓并检测接触电阻，温升恢复正常。",
                    ]
                ),
                result="整改完成，复测合格，现场已恢复正常生产。",
                handle_date=handle_day,
                handler=handler,
            )
            self._count("equipment.AbnormalRecord", True)
            self._stamp(record, created_at=self._aware(handle_day, 16, 0))
            self._stamp(task, closed_at=self._aware(handle_day, 15, 30))

    # -- 能源管理（EMS） ---------------------------------------------------
    def _season_factor(self, day: date) -> float:
        """新疆气候：冬季采暖与夏季空调推高用能，春秋相对平稳。"""
        return {
            1: 1.26,
            2: 1.18,
            3: 1.04,
            4: 0.94,
            5: 0.90,
            6: 1.06,
            7: 1.21,
            8: 1.16,
            9: 0.96,
            10: 0.92,
            11: 1.09,
            12: 1.27,
        }[day.month]

    def _energy_master(self) -> None:
        if EnergyMeter.objects.filter(company=self.company).exists():
            self.stdout.write("  能源管理：已存在演示主数据，跳过。")
            self.energy_meters = {
                meter.code: meter
                for meter in EnergyMeter.objects.filter(company=self.company)
            }
            self.energy_areas = {
                area.code: area for area in EnergyArea.objects.filter(company=self.company)
            }
            self.meter_daily = dict.fromkeys(self.energy_meters, "0")
            return

        areas: dict[str, EnergyArea] = {}
        area_definitions = (
            ("XJ-AREA-F01", "乌鲁木齐智能工厂", None, "PROD", "XJ2002", "42000"),
            ("XJ-AREA-F01-CUT", "裁剪车间", "XJ-AREA-F01", "PROD", "XJ2010", "2600"),
            ("XJ-AREA-F01-SEW", "缝制一车间", "XJ-AREA-F01", "PROD", "XJ2009", "3200"),
            ("XJ-AREA-F01-SEW2", "缝制二车间", "XJ-AREA-F01", "PROD", "XJ2011", "3000"),
            ("XJ-AREA-F01-FIN", "整烫包装车间", "XJ-AREA-F01", "PROD", "XJ2011", "2800"),
            ("XJ-AREA-F01-PWR", "动力车间", "XJ-AREA-F01", "EAM", "XJ2019", "1800"),
            ("XJ-AREA-F02", "阿克苏成衣加工基地", None, "PROD", "XJ2012", "22000"),
            ("XJ-AREA-F02-SEW", "阿克苏缝制车间", "XJ-AREA-F02", "PROD", "XJ2012", "3600"),
            ("XJ-AREA-F02-FIN", "阿克苏整烫车间", "XJ-AREA-F02", "PROD", "XJ2013", "2400"),
            ("XJ-AREA-WH", "仓储区", None, "WH", "XJ2006", "9600"),
            ("XJ-AREA-ADM", "综合办公与生活区", None, "HR", "XJ2020", "5400"),
        )
        for code, name, parent_code, dept_code, manager_no, size in area_definitions:
            areas[code] = self._upsert(
                EnergyArea,
                {"company": self.company, "code": code},
                {
                    "name": name,
                    "parent": areas.get(parent_code) if parent_code else None,
                    "department": self.departments.get(dept_code),
                    "manager": self.employees.get(manager_no),
                    "area_size": Decimal(size),
                    "is_active": True,
                },
            )
        self.energy_areas = areas

        price_definitions = (
            ("electricity", TariffPeriod.SHARP, "大工业尖峰电价", "1.213000", "元/kWh"),
            ("electricity", TariffPeriod.PEAK, "大工业高峰电价", "0.941000", "元/kWh"),
            ("electricity", TariffPeriod.FLAT, "大工业平段电价", "0.612000", "元/kWh"),
            ("electricity", TariffPeriod.VALLEY, "大工业低谷电价", "0.312000", "元/kWh"),
            ("water", TariffPeriod.FLAT, "工业用水单价", "4.900000", "元/t"),
            ("gas", TariffPeriod.FLAT, "管道天然气单价", "2.720000", "元/m3"),
            ("liquid", TariffPeriod.FLAT, "外供蒸汽单价", "168.000000", "元/t"),
        )
        for medium, period, name, price, currency in price_definitions:
            self._upsert(
                EnergyPrice,
                {
                    "company": self.company,
                    "medium": medium,
                    "tariff_period": period,
                    "effective_from": DATA_START,
                },
                {
                    "name": name,
                    "unit_price": Decimal(price),
                    "currency_unit": currency,
                    "effective_to": None,
                    "is_active": True,
                },
            )

        meter_definitions = (
            ("XJ-EM-ELE-01", "厂区总电表", "electricity", "XJ-AREA-F01", None, "ENERGY",
             "DTSD341", "XJ26E001", "kWh", "1 号配电室进线柜", "1860"),
            ("XJ-EM-ELE-02", "裁剪车间电表", "electricity", "XJ-AREA-F01-CUT", "XJ-EQ-CUT-01",
             "PROD", "DTSD341", "XJ26E002", "kWh", "裁剪车间配电箱", "430"),
            ("XJ-EM-ELE-03", "缝制一车间电表", "electricity", "XJ-AREA-F01-SEW", None, "PROD",
             "DTSD341", "XJ26E003", "kWh", "缝制一车间配电箱", "565"),
            ("XJ-EM-ELE-04", "缝制二车间电表", "electricity", "XJ-AREA-F01-SEW2", None, "PROD",
             "DTSD341", "XJ26E004", "kWh", "缝制二车间配电箱", "486"),
            ("XJ-EM-ELE-05", "整烫包装车间电表", "electricity", "XJ-AREA-F01-FIN", None, "PROD",
             "DTSD341", "XJ26E005", "kWh", "整烫车间配电箱", "372"),
            ("XJ-EM-ELE-06", "空压站电表", "electricity", "XJ-AREA-F01-PWR", "XJ-EQ-AIR-01",
             "EAM", "DTSD341", "XJ26E006", "kWh", "空压站配电箱", "268"),
            ("XJ-EM-ELE-07", "光伏并网发电表", "electricity", "XJ-AREA-F01-PWR", "XJ-EQ-PV-01",
             "ENERGY", "DTSD341", "XJ26E007", "kWh", "光伏并网柜", "175"),
            ("XJ-EM-ELE-08", "阿克苏基地总电表", "electricity", "XJ-AREA-F02", None, "ENERGY",
             "DTSD341", "XJ26E008", "kWh", "基地配电室", "618"),
            ("XJ-EM-WAT-01", "厂区总水表", "water", "XJ-AREA-F01", None, "ENERGY",
             "LXLC-100", "XJ26W001", "t", "厂区给水井", "38"),
            ("XJ-EM-WAT-02", "办公生活区水表", "water", "XJ-AREA-ADM", None, "HR",
             "LXLC-80", "XJ26W002", "t", "生活区水表井", "11"),
            ("XJ-EM-GAS-01", "锅炉房天然气表", "gas", "XJ-AREA-F01-PWR", "XJ-EQ-BOILER-01",
             "EAM", "G65", "XJ26G001", "m3", "锅炉房燃气间", "402"),
            ("XJ-EM-GAS-02", "食堂天然气表", "gas", "XJ-AREA-ADM", None, "HR",
             "G25", "XJ26G002", "m3", "食堂燃气间", "24"),
            ("XJ-EM-LIQ-01", "蒸汽流量表", "liquid", "XJ-AREA-F01-PWR", "XJ-EQ-BOILER-01",
             "EAM", "LUGB-100", "XJ26L001", "t", "蒸汽主管", "21"),
            ("XJ-EM-LIQ-02", "整烫热水流量表", "liquid", "XJ-AREA-F01-FIN", "XJ-EQ-IRON-01",
             "PROD", "LUGB-80", "XJ26L002", "t", "整烫热水管", "8.5"),
        )
        meters: dict[str, EnergyMeter] = {}
        self.meter_daily: dict[str, str] = {}
        for (
            code, name, medium, area_code, equipment_code, dept_code,
            model_no, serial_no, unit, location, daily,
        ) in meter_definitions:
            meters[code] = self._upsert(
                EnergyMeter,
                {"company": self.company, "code": code},
                {
                    "name": name,
                    "medium": medium,
                    "area": areas.get(area_code),
                    "equipment": self.equipments.get(equipment_code) if equipment_code else None,
                    "department": self.departments.get(dept_code),
                    "meter_model": model_no,
                    "serial_no": serial_no,
                    "multiplier": Decimal("1"),
                    "unit": unit,
                    "status": MeterStatus.ONLINE,
                    "location": location,
                    "install_date": date(2025, 12, 20),
                    "is_monitored": True,
                    "is_active": True,
                },
            )
            self.meter_daily[code] = daily
        self.energy_meters = meters

        threshold_definitions = (
            ("电力抄表离线阈值", "electricity", None, 240, AlarmLevel.WARNING),
            ("用水抄表离线阈值", "water", None, 1440, AlarmLevel.WARNING),
            ("燃气抄表离线阈值", "gas", None, 720, AlarmLevel.WARNING),
            ("蒸汽抄表离线阈值", "liquid", None, 720, AlarmLevel.INFO),
        )
        for name, medium, meter_code, offline_minutes, level in threshold_definitions:
            self._upsert(
                EnergyThreshold,
                {"company": self.company, "name": name},
                {
                    "medium": medium,
                    "meter": meters.get(meter_code) if meter_code else None,
                    "offline_minutes": offline_minutes,
                    "alarm_level": level,
                    "is_active": True,
                },
            )
        self._upsert(
            EnergyThreshold,
            {"company": self.company, "name": "空压站电表单耗上限"},
            {
                "medium": "electricity",
                "meter": meters["XJ-EM-ELE-06"],
                "unit_consumption_limit": Decimal("2.6000"),
                "offline_minutes": 0,
                "alarm_level": AlarmLevel.CRITICAL,
                "is_active": True,
            },
        )

    def _energy_reading_flow(self) -> None:
        from apps.ems import services as ems_services

        if MeterReading.objects.filter(company=self.company).exists():
            self.stdout.write("  能源抄表：已存在演示读数，跳过。")
            return
        recorder = self.employees["XJ2017"]
        step = 5
        for code, meter in self.energy_meters.items():
            base = Decimal(self.meter_daily[code])
            total = Decimal(str(round(random.uniform(86000, 128000), 2)))
            day = DATA_START
            while day <= self.today:
                factor = Decimal(str(round(self._season_factor(day), 3)))
                noise = Decimal(str(round(random.uniform(0.85, 1.15), 3)))
                total = (total + base * factor * noise * step).quantize(Decimal("0.01"))
                ems_services.record_reading(
                    meter=meter,
                    reading=total,
                    reading_at=self._aware(day, 8, 30),
                    source=EmsReadingSource.AUTO,
                    tariff_period=TariffPeriod.FLAT,
                    recorder=recorder,
                    note=DEMO_REMARK,
                )
                self._count("ems.MeterReading", True)
                day = day + timedelta(days=step)

    def _energy_run_flow(self) -> None:
        from apps.ems import services as ems_services

        if EnergyRunRecord.objects.filter(company=self.company).exists():
            self.stdout.write("  设备运行记录：已存在演示记录，跳过。")
            return
        definitions = (
            ("XJ-EM-ELE-06", "XJ-EQ-AIR-01", "XJ2019", 5, "压缩空气产量", "m3", "2.10", "2.45"),
            ("XJ-EM-GAS-01", "XJ-EQ-BOILER-01", "XJ2019", 4, "蒸汽产量", "t", "9.80", "12.60"),
            ("XJ-EM-LIQ-01", "XJ-EQ-BOILER-01", "XJ2019", 4, "外供蒸汽量", "t", "8.40", "11.20"),
            ("XJ-EM-ELE-02", "XJ-EQ-CUT-01", "XJ2010", 5, "裁片产量", "件", "0.80", "1.35"),
            ("XJ-EM-ELE-07", "XJ-EQ-PV-01", "XJ2017", 4, "光伏发电量", "kWh", "0.00", "0.00"),
        )
        for meter_code, equipment_code, operator_no, count, output_desc, _unit, low, high in (
            definitions
        ):
            meter = self.energy_meters[meter_code]
            equipment = self.equipments[equipment_code]
            operator = self.employees[operator_no]
            for index in range(count):
                day = self._rand_date(end=self.today - timedelta(days=2))
                started = self._aware(day, 9, 0)
                finished = self._aware(day, 18, 0)
                record = ems_services.start_run_record(
                    meter=meter,
                    started_at=started,
                    equipment=equipment,
                    operator=operator,
                    output_desc=output_desc,
                    remark=DEMO_REMARK,
                )
                output_qty = Decimal(str(round(random.uniform(120, 3200), 2)))
                per_unit = Decimal(str(round(random.uniform(float(low), float(high)), 4)))
                if meter_code == "XJ-EM-ELE-06" and index == count - 1:
                    per_unit = Decimal("2.9000")
                ems_services.finish_run_record(
                    record,
                    finished_at=finished,
                    output_qty=output_qty,
                    energy_consumption=(per_unit * output_qty).quantize(Decimal("0.01")),
                )
                self._count("ems.EnergyRunRecord", True)

        running_day = self.today - timedelta(days=1)
        ems_services.start_run_record(
            meter=self.energy_meters["XJ-EM-ELE-03"],
            started_at=self._aware(running_day, 10, 0),
            equipment=self.equipments["XJ-EQ-SEW-01"],
            operator=self.employees["XJ2009"],
            output_desc="缝制一车间当班产量",
            remark=DEMO_REMARK,
        )
        self._count("ems.EnergyRunRecord", True)

    def _energy_alarm_flow(self) -> None:
        from apps.ems import services as ems_services

        if EnergyAlarm.objects.filter(
            company=self.company, source_ref=ENERGY_ALARM_MARK
        ).exists():
            self.stdout.write("  能源报警：已存在演示报警，跳过。")
            return
        meters = self.energy_meters
        alarm_definitions = (
            ("XJ-EM-ELE-03", AlarmType.OVER_LIMIT, AlarmLevel.WARNING, 62,
             "缝制一车间电表 读数 51230 超过上限 50000", "51230", "50000", "closed"),
            ("XJ-EM-ELE-06", AlarmType.OVER_LIMIT, AlarmLevel.WARNING, 74,
             "空压站电表 读数 26840 超过上限 26000", "26840", "26000", "closed"),
            ("XJ-EM-LIQ-01", AlarmType.OVER_LIMIT, AlarmLevel.INFO, 96,
             "蒸汽流量表 读数 1845 超过上限 1800", "1845", "1800", "pending"),
            ("XJ-EM-ELE-08", AlarmType.OFFLINE, AlarmLevel.CRITICAL, 120,
             "阿克苏基地总电表 超过 240 分钟未抄表", None, None, "closed"),
            ("XJ-EM-LIQ-02", AlarmType.OFFLINE, AlarmLevel.WARNING, 150,
             "整烫热水流量表 超过 720 分钟未抄表", None, None, "handling"),
            ("XJ-EM-GAS-01", AlarmType.ENERGY_CONSUMPTION, AlarmLevel.CRITICAL, 45,
             "锅炉房天然气表 当日用量 1180 超过日用量上限 1000", "1180", "1000", "closed"),
            ("XJ-EM-ELE-01", AlarmType.ENERGY_CONSUMPTION, AlarmLevel.WARNING, 52,
             "厂区总电表 当日用量 6420 超过日用量上限 6000", "6420", "6000", "handling"),
            ("XJ-EM-WAT-01", AlarmType.ENERGY_CONSUMPTION, AlarmLevel.INFO, 110,
             "厂区总水表 当日用量 126 超过日用量上限 110", "126", "110", "pending"),
            ("XJ-EM-ELE-02", AlarmType.UNIT_CONSUMPTION, AlarmLevel.WARNING, 88,
             "裁剪车间电表 单耗 1.62 超过上限 1.40（记录 XJ-ER-000021）", "1.62", "1.40", "closed"),
        )
        for meter_code, alarm_type, level, days_ago, message, triggered, threshold, status in (
            alarm_definitions
        ):
            occurred = self._aware(self.today - timedelta(days=days_ago), 14, 0)
            alarm = ems_services.raise_alarm(
                company_id=self.company.pk,
                alarm_type=alarm_type,
                message=message,
                occurred_at=occurred,
                level=level,
                meter=meters[meter_code],
                triggered_value=Decimal(triggered) if triggered else None,
                threshold_value=Decimal(threshold) if threshold else None,
                source_ref=ENERGY_ALARM_MARK,
            )
            if alarm is None:
                continue
            self._count("ems.EnergyAlarm", True)
            handler = self.employees["XJ2017"]
            if status == "closed":
                ems_services.handle_alarm(
                    alarm, note="已通知动力车间现场核查。", handler=handler
                )
                ems_services.close_alarm(
                    alarm,
                    note=random.choice(
                        [
                            "现场确认为空压机加卸载频繁，调整压力带后恢复正常。",
                            "更换老化密封件并保压试验，用能回到正常区间。",
                            "调整生产排班错峰用能，次日用量已回落。",
                        ]
                    ),
                )
                self._stamp(
                    alarm,
                    handled_at=occurred + timedelta(hours=1),
                    closed_at=occurred + timedelta(hours=3),
                )
            elif status == "handling":
                ems_services.handle_alarm(alarm, note="已派工现场核查，等待处理结果。", handler=handler)
                self._stamp(alarm, handled_at=occurred + timedelta(hours=1))

    # -- 设备数采（IoT） ---------------------------------------------------
    def _iot_master(self) -> None:
        from apps.iot import services as iot_services

        connection_definitions = (
            ("XJ-IOT-CONN-01", "车间设备 HTTP 上报通道", IoTProtocol.HTTP, "10.10.20.31", True),
            ("XJ-IOT-CONN-02", "能源表计 HTTP 上报通道", IoTProtocol.HTTP, "10.10.30.11", True),
            ("XJ-IOT-CONN-03", "PLC / MQTT 预留通道", IoTProtocol.MQTT, "mqtt://10.10.20.9:1883", False),
        )
        connections: dict[str, IoTConnection] = {}
        for code, name, protocol, endpoint, enabled in connection_definitions:
            connections[code] = self._upsert(
                IoTConnection,
                {"company": self.company, "code": code},
                {
                    "name": name,
                    "protocol": protocol,
                    "endpoint": endpoint,
                    "credential_ref": "env:XJ_IOT_TOKEN",
                    "timeout_seconds": 10,
                    "batch_limit": 200,
                    "rate_limit_per_minute": 120,
                    "is_enabled": enabled,
                    "is_simulated": protocol == IoTProtocol.HTTP,
                    "is_active": True,
                },
            )

        gateway_definitions = (
            ("XJ-GW-01", "裁剪车间采集网关", GatewayType.GATEWAY, "XJ-IOT-CONN-01",
             "XJ-EQ-CUT-01", "F01", "F01/CUT", "裁剪车间电气柜", GatewayStatus.ONLINE),
            ("XJ-GW-02", "缝制一车间边缘网关", GatewayType.GATEWAY, "XJ-IOT-CONN-01",
             "XJ-EQ-SEW-01", "F01", "F01/SEW", "缝制一车间线首", GatewayStatus.ONLINE),
            ("XJ-GW-03", "空压站采集网关", GatewayType.GATEWAY, "XJ-IOT-CONN-01",
             "XJ-EQ-AIR-01", "F01", "F01/PWR", "空压站控制柜", GatewayStatus.ONLINE),
            ("XJ-GW-04", "锅炉房采集网关", GatewayType.GATEWAY, "XJ-IOT-CONN-01",
             "XJ-EQ-BOILER-01", "F01", "F01/PWR", "锅炉房控制室", GatewayStatus.ONLINE),
            ("XJ-GW-05", "光伏汇流箱采集器", GatewayType.SENSOR, "XJ-IOT-CONN-01",
             "XJ-EQ-PV-01", "F01", "F01/PWR", "厂房光伏汇流箱", GatewayStatus.ONLINE),
            ("XJ-GW-06", "车间电能表采集器", GatewayType.ELECTRIC_METER, "XJ-IOT-CONN-02",
             None, "F01", "F01/PWR", "1 号配电室", GatewayStatus.ONLINE),
            ("XJ-GW-07", "厂区水表采集器", GatewayType.WATER_METER, "XJ-IOT-CONN-02",
             None, "F01", "F01/PWR", "厂区给水井", GatewayStatus.ONLINE),
            ("XJ-GW-08", "阿克苏基地备用网关", GatewayType.GATEWAY, "XJ-IOT-CONN-03",
             None, "F02", "F02/SEW", "基地配电室", GatewayStatus.OFFLINE),
        )
        gateways: dict[str, IoTGateway] = {}
        for (
            code,
            name,
            gateway_type,
            conn_code,
            equipment_code,
            factory_code,
            workshop_key,
            location,
            status,
        ) in gateway_definitions:
            existed = IoTGateway.objects.filter(company=self.company, code=code).exists()
            gateway = self._upsert(
                IoTGateway,
                {"company": self.company, "code": code},
                {
                    "name": name,
                    "gateway_type": gateway_type,
                    "connection": connections[conn_code],
                    "equipment": self.equipments.get(equipment_code) if equipment_code else None,
                    "factory": self.factories.get(factory_code),
                    "workshop": self.workshops.get(workshop_key),
                    "location": location,
                    "status": status,
                    "offline_minutes": 60,
                    "is_simulated": True,
                    "is_active": True,
                },
            )
            if not existed:
                iot_services.issue_device_token(gateway, rotated_at=self._aware(DATA_START, 9, 0))
            gateways[code] = gateway
        self.iot_gateways = gateways

        point_definitions = (
            ("XJ-GW-01", "CUT01-T1", "裁床主轴温度", "temperature", "℃", "0", "120", None, "75", True, False, None),
            ("XJ-GW-01", "CUT01-C1", "裁床主轴电流", "current", "A", "0", "20", None, "15", True, False, None),
            ("XJ-GW-01", "CUT01-V1", "裁床电机电压", "voltage", "V", "300", "450", "340", "430", True, False, None),
            ("XJ-GW-02", "SEW01-T1", "缝纫机机头温度", "temperature", "℃", "0", "100", None, "70", True, False, None),
            ("XJ-GW-02", "SEW01-C1", "缝纫机电机电流", "current", "A", "0", "8", None, "6", True, False, None),
            ("XJ-GW-03", "AIR01-P1", "空压机排气压力", "pressure", "MPa", "0.4", "1.0", "0.6", "0.85", True, False, None),
            ("XJ-GW-03", "AIR01-T1", "空压机排气温度", "temperature", "℃", "0", "130", None, "100", True, False, None),
            ("XJ-GW-03", "AIR01-E1", "空压站累计电量", "electricity", "kWh", None, None, None, None, False, True, "XJ-EM-ELE-06"),
            ("XJ-GW-04", "BOIL01-P1", "锅炉蒸汽压力", "pressure", "MPa", "0.2", "0.8", "0.4", "0.65", True, False, None),
            ("XJ-GW-04", "BOIL01-T1", "锅炉烟气温度", "temperature", "℃", "0", "260", None, "200", True, False, None),
            ("XJ-GW-04", "BOIL01-F1", "锅炉燃气流量", "flow", "m3/h", "0", "60", None, None, True, False, None),
            ("XJ-GW-05", "PV01-E1", "光伏发电功率", "electricity", "kW", "0", "320", None, None, True, False, None),
            ("XJ-GW-05", "PV01-T1", "光伏组件温度", "temperature", "℃", "-20", "90", None, "70", True, False, None),
            ("XJ-GW-06", "ELE06-R1", "空压站电表读数", "electricity", "kWh", None, None, None, None, False, True, "XJ-EM-ELE-06"),
            ("XJ-GW-06", "ELE03-R1", "缝制一车间电表读数", "electricity", "kWh", None, None, None, None, False, True, "XJ-EM-ELE-03"),
            ("XJ-GW-07", "WAT01-R1", "厂区总水表读数", "water", "t", None, None, None, None, False, True, "XJ-EM-WAT-01"),
        )
        points: dict[str, IoTPoint] = {}
        for (
            gateway_code, code, name, quantity, unit, low, high, lower, upper,
            alarm_enabled, cumulative, meter_code,
        ) in point_definitions:
            points[f"{gateway_code}:{code}"] = self._upsert(
                IoTPoint,
                {"company": self.company, "gateway": gateways[gateway_code], "code": code},
                {
                    "name": name,
                    "quantity": quantity,
                    "unit": unit,
                    "range_min": Decimal(low) if low is not None else None,
                    "range_max": Decimal(high) if high is not None else None,
                    "precision": 2,
                    "is_cumulative": cumulative,
                    "upper_limit": Decimal(upper) if upper is not None else None,
                    "lower_limit": Decimal(lower) if lower is not None else None,
                    "alarm_enabled": alarm_enabled,
                    "meter": self.energy_meters.get(meter_code) if meter_code else None,
                    "is_active": True,
                },
            )
        self.iot_points = points

    def _iot_flow(self) -> None:
        from apps.iot import services as iot_services

        if IoTMessage.objects.filter(company=self.company).exists():
            self.stdout.write("  设备数采：已存在演示报文，跳过。")
            return
        gateways = self.iot_gateways
        cumulative: dict[str, float] = {}
        report_plan = (
            ("XJ-GW-01", 11),
            ("XJ-GW-02", 10),
            ("XJ-GW-03", 11),
            ("XJ-GW-04", 10),
            ("XJ-GW-05", 9),
            ("XJ-GW-06", 8),
            ("XJ-GW-07", 8),
        )
        for gateway_code, count in report_plan:
            gateway = gateways[gateway_code]
            gateway_points = [
                point
                for key, point in self.iot_points.items()
                if key.startswith(gateway_code + ":")
            ]
            for index in range(count):
                day = DATA_START + timedelta(
                    days=int((self.today - DATA_START).days * (index + 1) / (count + 1))
                )
                moment = self._aware(day, 9 + (index % 6), (index * 7) % 60)
                payload = {
                    "message_id": f"XJ-MSG-{gateway_code}-{index + 1:03d}",
                    "device_time": moment.isoformat(),
                    "simulated": True,
                    "points": [
                        {
                            "code": point.code,
                            "value": str(self._iot_value(point, index, cumulative)),
                        }
                        for point in gateway_points
                    ],
                }
                iot_services.ingest_report(gateway, payload, source_ip="10.10.20.31")
                self._count("iot.IoTMessage", True)
                message = IoTMessage.objects.filter(
                    gateway=gateway, message_id=payload["message_id"][:64]
                ).first()
                if message is not None:
                    self._stamp(message, received_at=moment, created_at=moment)
                    IoTReading.objects.filter(message=message).update(
                        received_at=moment, created_at=moment
                    )

        gateway = gateways["XJ-GW-01"]
        first_point = next(
            point for key, point in self.iot_points.items() if key.startswith("XJ-GW-01:")
        )
        duplicate_payload = {
            "message_id": "XJ-MSG-XJ-GW-01-001",
            "device_time": self._aware(DATA_START + timedelta(days=10), 14, 0).isoformat(),
            "simulated": True,
            "points": [{"code": first_point.code, "value": "63.20"}],
        }
        iot_services.ingest_report(gateway, duplicate_payload, source_ip="10.10.20.31")
        self._count("iot.IoTMessage", True)
        failed_payload = {
            "message_id": "XJ-MSG-XJ-GW-01-900",
            "device_time": self._aware(self.today - timedelta(days=3), 15, 0).isoformat(),
            "simulated": True,
            "points": [{"code": "CUT01-X9", "value": "1.00"}],
        }
        iot_services.ingest_report(gateway, failed_payload, source_ip="10.10.20.31")
        self._count("iot.IoTMessage", True)
        for message in IoTMessage.objects.filter(company=self.company, is_simulated=True):
            if message.received_at.date() == self.today:
                base = self._aware(self.today - timedelta(days=2), 16, 0)
                self._stamp(message, received_at=base, created_at=base)
                IoTReading.objects.filter(message=message).update(received_at=base, created_at=base)

        offline = gateways["XJ-GW-08"]
        self._stamp(
            offline,
            status=GatewayStatus.OFFLINE,
            last_seen_at=self._aware(self.today - timedelta(days=26), 11, 0),
        )
        self._stamp(
            gateways["XJ-GW-02"],
            last_seen_at=self._aware(self.today - timedelta(days=1), 18, 30),
        )

    def _iot_value(self, point, index: int, cumulative: dict[str, float]) -> float:
        precision = int(point.precision or 2)
        if point.is_cumulative:
            base = cumulative.get(point.code)
            if base is None:
                base = float(random.uniform(12000, 48000))
            base = base + random.uniform(180, 640)
            cumulative[point.code] = base
            return round(base, precision)
        low = float(point.range_min or 0)
        high = float(point.range_max or 100)
        mid = (low + high) / 2 if high > low else high
        value = mid * random.uniform(0.82, 1.12)
        if point.upper_limit is not None and random.random() < 0.12:
            value = float(point.upper_limit) * random.uniform(1.02, 1.10)
        if point.lower_limit is not None and random.random() < 0.08:
            value = float(point.lower_limit) * random.uniform(0.88, 0.98)
        return round(value, precision)

    # -- 库存 / 采购 / 销售 -------------------------------------------------
    def _warehouse(self, code: str) -> Warehouse:
        return Warehouse.objects.get(company=self.company, code=code)

    def _location(self, warehouse_code: str, zone_code: str, location_code: str) -> Location:
        """储位编码在不同库区可能重复，必须连同仓库与库区一起定位。"""
        return Location.objects.get(
            zone__warehouse__code=warehouse_code,
            zone__warehouse__company=self.company,
            zone__code=zone_code,
            code=location_code,
        )

    def _stock_document(
        self,
        marker: str,
        document_type: str,
        warehouse_code: str,
        lines: list[dict],
        *,
        reason: str = "",
    ):
        """经统一库存服务建单并过账；已存在同 biz_no 单据时直接跳过（幂等）。"""
        from apps.wms.models import InventoryDocument
        from apps.wms.services import stock

        if InventoryDocument.objects.filter(company=self.company, biz_no=marker).exists():
            return None
        document = stock.create_document(
            document_type=document_type,
            company=self.company,
            warehouse=self._warehouse(warehouse_code),
            lines=lines,
            user=self.actor,
            biz_type="seed_demo_xjys",
            biz_no=marker,
            remark=f"{DEMO_REMARK}：{reason}" if reason else DEMO_REMARK,
        )
        posted = stock.post_document(
            document,
            user=self.actor,
            idempotency_key=f"xj-seed-{marker}",
            reason=reason or DEMO_REMARK,
        )
        self._count("wms.InventoryDocument", True)
        return posted

    def _inventory_flow(self) -> None:
        """期初与出入库：面料 / 辅料 / 包装物 / 备件 / 成品。"""
        from apps.wms.models import DocumentType, InventoryDocument, QualityStatus
        from apps.wms.services import stock

        self.material_locations = {
            "XJ-FAB-001": ("XJ-WH-RAW-01", "STO", "A01-01-01"),
            "XJ-FAB-002": ("XJ-WH-RAW-01", "STO", "A01-01-02"),
            "XJ-FAB-003": ("XJ-WH-RAW-01", "STO", "A01-02-01"),
            "XJ-ACC-001": ("XJ-WH-RAW-01", "STO", "A01-02-02"),
            "XJ-ACC-002": ("XJ-WH-RAW-01", "STO", "A01-03-01"),
            "XJ-ACC-003": ("XJ-WH-RAW-01", "STO", "A01-03-02"),
            "XJ-ACC-004": ("XJ-WH-RAW-01", "STO", "A02-01-01"),
            "XJ-ACC-005": ("XJ-WH-RAW-01", "STO", "A02-01-02"),
            "XJ-PKG-001": ("XJ-WH-ACC-01", "STO", "A01-01-01"),
            "XJ-PKG-002": ("XJ-WH-ACC-01", "STO", "A01-01-02"),
            "XJ-PKG-003": ("XJ-WH-ACC-01", "STO", "A01-02-01"),
            "XJ-SP-001": ("XJ-WH-SP-01", "STO", "A01-01-01"),
            "XJ-SP-002": ("XJ-WH-SP-01", "STO", "A01-01-02"),
            "XJ-SP-003": ("XJ-WH-SP-01", "STO", "A01-02-01"),
            "XJ-SP-004": ("XJ-WH-SP-01", "STO", "A01-02-02"),
            "XJ-SP-005": ("XJ-WH-SP-01", "STO", "A01-03-01"),
            "XJ-CS-001": ("XJ-WH-SP-01", "STO", "A01-03-02"),
        }
        if InventoryDocument.objects.filter(company=self.company).exists():
            self.stdout.write("  库存：已存在演示单据，跳过。")
            return

        def location_of(material_code: str):
            warehouse_code, zone_code, location_code = self.material_locations[material_code]
            return self._location(warehouse_code, zone_code, location_code)

        opening = (
            ("XJ-FAB-001", "20000", ""),
            ("XJ-FAB-002", "12000", ""),
            ("XJ-FAB-003", "8000", ""),
            ("XJ-ACC-001", "1500", ""),
            ("XJ-ACC-002", "80000", ""),
            ("XJ-ACC-003", "30000", ""),
            ("XJ-ACC-004", "3000", ""),
            ("XJ-ACC-005", "200000", ""),
        )
        self._stock_document(
            "XJ-OP-RAW-01",
            DocumentType.RECEIPT,
            "XJ-WH-RAW-01",
            [
                {
                    "material_id": self.materials[code].id,
                    "location_id": location_of(code).id,
                    "batch_no": batch,
                    "quality_status": QualityStatus.QUALIFIED,
                    "quantity": Decimal(quantity),
                }
                for code, quantity, batch in opening
            ],
            reason="原料与辅料期初结存（2026-01-01 盘点）",
        )
        self._stock_document(
            "XJ-OP-ACC-01",
            DocumentType.RECEIPT,
            "XJ-WH-ACC-01",
            [
                {
                    "material_id": self.materials[code].id,
                    "location_id": location_of(code).id,
                    "quality_status": QualityStatus.QUALIFIED,
                    "quantity": Decimal(quantity),
                }
                for code, quantity in (
                    ("XJ-PKG-001", "6000"),
                    ("XJ-PKG-002", "120000"),
                    ("XJ-PKG-003", "150000"),
                )
            ],
            reason="包装物期初结存（2026-01-01 盘点）",
        )
        self._stock_document(
            "XJ-OP-SP-01",
            DocumentType.RECEIPT,
            "XJ-WH-SP-01",
            [
                {
                    "material_id": self.materials[code].id,
                    "location_id": location_of(code).id,
                    "quality_status": QualityStatus.QUALIFIED,
                    "quantity": Decimal(quantity),
                }
                for code, quantity in (
                    ("XJ-SP-001", "260"),
                    ("XJ-SP-002", "500"),
                    ("XJ-SP-003", "12000"),
                    ("XJ-SP-004", "90"),
                    ("XJ-SP-005", "180"),
                    ("XJ-CS-001", "420"),
                )
            ],
            reason="备品备件期初结存（2026-01-01 盘点）",
        )

        # 面料到货入待检区 → 来料检验放行（质量状态转换链路）
        quarantine_location = self._location("XJ-WH-RAW-01", "RECV", "A01-01-01")
        receipt = self._stock_document(
            "XJ-GR-FAB-2601",
            DocumentType.RECEIPT,
            "XJ-WH-RAW-01",
            [
                {
                    "material_id": self.materials["XJ-FAB-001"].id,
                    "location_id": quarantine_location.id,
                    "batch_no": "XJ-FAB-B2601",
                    "roll_no": "ROLL-2601",
                    "quality_status": QualityStatus.QUARANTINE,
                    "quantity": Decimal("5600"),
                },
                {
                    "material_id": self.materials["XJ-FAB-002"].id,
                    "location_id": quarantine_location.id,
                    "batch_no": "XJ-FAB-B2602",
                    "roll_no": "ROLL-2611",
                    "quality_status": QualityStatus.QUARANTINE,
                    "quantity": Decimal("3200"),
                },
            ],
            reason="巴州棉纺到货入待检区",
        )
        if receipt is not None:
            for material_code, batch_no, roll_no, quantity in (
                ("XJ-FAB-001", "XJ-FAB-B2601", "ROLL-2601", "5600"),
                ("XJ-FAB-002", "XJ-FAB-B2602", "ROLL-2611", "3200"),
            ):
                stock.release_quality(
                    user=self.actor,
                    company=self.company.id,
                    warehouse=receipt.warehouse,
                    material=self.materials[material_code],
                    location=quarantine_location,
                    quantity=Decimal(quantity),
                    batch_no=batch_no,
                    roll_no=roll_no,
                    from_status=QualityStatus.QUARANTINE,
                    to_status=QualityStatus.QUALIFIED,
                    biz_type="seed_demo_xjys",
                    biz_no=f"XJ-QL-{batch_no}",
                    reason="来料检验合格（外观、幅宽、克重、色差符合标准）",
                    idempotency_key=f"xj-seed-quality-{batch_no}",
                )
            self._count("wms.InventoryDocument", True)

        # 备件入库后移库到发货区，并做一次盘点差异（盘亏）
        from_location = self._location("XJ-WH-SP-01", "STO", "A01-03-02")
        self._stock_document(
            "XJ-MV-SP-01",
            DocumentType.MOVE,
            "XJ-WH-SP-01",
            [
                {
                    "material_id": self.materials["XJ-CS-001"].id,
                    "location_id": from_location.id,
                    "target_location_id": self._location("XJ-WH-SP-01", "SHIP", "A01-01-01").id,
                    "quality_status": QualityStatus.QUALIFIED,
                    "quantity": Decimal("60"),
                }
            ],
            reason="缝纫机油转到发货区备领",
        )
        self._stock_document(
            "XJ-AD-SP-01",
            DocumentType.ADJUSTMENT,
            "XJ-WH-SP-01",
            [
                {
                    "material_id": self.materials["XJ-SP-003"].id,
                    "location_id": self._location("XJ-WH-SP-01", "STO", "A01-02-01").id,
                    "quality_status": QualityStatus.QUALIFIED,
                    "direction": "out",
                    "quantity": Decimal("18"),
                    "remark": "2026-06 半年度盘点差异（缝纫机针盘亏）",
                }
            ],
            reason="半年度盘点差异审批通过",
        )

    def _procurement_flow(self) -> None:
        """采购闭环：申请 → 审批 → 订单 → 到货 → 过账 → 来料检验放行。"""
        from apps.procurement import services as prc
        from apps.procurement.models import (
            GoodsReceipt,
            OrderStatus,
            PurchaseOrder,
            PurchaseRequisition,
            ReceiptStatus,
            RequisitionStatus,
        )

        if PurchaseRequisition.objects.filter(company=self.company).exists():
            self.stdout.write("  采购：已存在演示单据，跳过。")
            return
        quarantine_location = self._location("XJ-WH-RAW-01", "RECV", "A01-02-01")

        definitions = (
            {
                "requisition_no": "XJ-PR-0001",
                "request_type": "planned",
                "purpose": "春夏款长绒棉汗布与拉链备料（计划采购）",
                "lines": (("XJ-FAB-001", "4200"), ("XJ-ACC-003", "12000")),
                "supplier_code": "XJ-SUP-001",
                "warehouse_code": "XJ-WH-RAW-01",
                "order_no": "XJ-PO-0001",
                "receipt_no": "XJ-RC-0001",
                "receipt_lines": (
                    ("XJ-FAB-001", "4200", "XJ-FAB-B2603"),
                    ("XJ-ACC-003", "12000", "XJ-ACC-Z2603"),
                ),
                "inspect": True,
            },
            {
                "requisition_no": "XJ-PR-0002",
                "request_type": "urgent",
                "purpose": "空压机滤芯紧急采购（空压站压差报警）",
                "lines": (("XJ-SP-004", "40"),),
                "supplier_code": "XJ-SUP-003",
                "warehouse_code": "XJ-WH-SP-01",
                "order_no": "XJ-PO-0002",
                "receipt_no": "XJ-RC-0002",
                "receipt_lines": (("XJ-SP-004", "40", ""),),
                "inspect": True,
            },
            {
                "requisition_no": "XJ-PR-0003",
                "request_type": "normal",
                "purpose": "阿克苏基地包装物补充（待审批）",
                "lines": (("XJ-PKG-001", "2000"),),
                "supplier_code": "XJ-SUP-004",
                "warehouse_code": "XJ-WH-ACC-01",
                "order_no": None,
                "receipt_no": None,
                "receipt_lines": (),
                "inspect": False,
            },
        )
        for index, item in enumerate(definitions):
            requisition = PurchaseRequisition.objects.filter(
                company=self.company, requisition_no=item["requisition_no"]
            ).first()
            if requisition is None:
                requisition = prc.create_requisition(
                    user=self.actor,
                    company=self.company,
                    lines=[
                        {"material_id": self.materials[code].id, "quantity": Decimal(quantity)}
                        for code, quantity in item["lines"]
                    ],
                    request_type=item["request_type"],
                    needed_date=self._rand_date(end=DATA_START + timedelta(days=40)),
                    department=self.departments["PUR"],
                    factory=self.factories["F01"],
                    purpose=item["purpose"],
                    remark=DEMO_REMARK,
                    requisition_no=item["requisition_no"],
                )
                self._count("procurement.PurchaseRequisition", True)
                self._stamp(
                    requisition,
                    created_at=self._aware(DATA_START + timedelta(days=index * 45), 9, 30),
                )
            if requisition.status == RequisitionStatus.DRAFT and index < 2:
                requisition = prc.submit_requisition(
                    requisition, user=self.actor, comment="演示提交"
                )
            if requisition.status == RequisitionStatus.SUBMITTED:
                self._approve_fully(requisition.approval_instance_id, requisition)
            if item["order_no"] is None or requisition.status != RequisitionStatus.APPROVED:
                continue

            order = PurchaseOrder.objects.filter(
                company=self.company, order_no=item["order_no"]
            ).first()
            if order is None:
                order = prc.create_order_from_requisition(
                    requisition,
                    user=self.actor,
                    supplier=self.suppliers[item["supplier_code"]],
                    warehouse=self._warehouse(item["warehouse_code"]),
                    expected_date=self._rand_date(
                        start=DATA_START + timedelta(days=10), end=self.today
                    ),
                    tax_rate=Decimal("13"),
                    payment_terms="月结 60 天",
                    remark=f"{DEMO_REMARK}：由采购申请 {item['requisition_no']} 转单",
                    order_no=item["order_no"],
                )
                self._count("procurement.PurchaseOrder", True)
            if order.status == OrderStatus.DRAFT:
                order = prc.submit_order(order, user=self.actor, comment="演示提交")
            if order.status == OrderStatus.SUBMITTED:
                self._approve_fully(order.approval_instance_id, order)

            receipt = GoodsReceipt.objects.filter(
                company=self.company, receipt_no=item["receipt_no"]
            ).first()
            if receipt is None and order.status in OrderStatus.open_for_receipt():
                order_lines = {
                    line.material.code: line
                    for line in order.lines.select_related("material").order_by("line_no")
                }
                rows = []
                for material_code, quantity, batch_no in item["receipt_lines"]:
                    row = {
                        "order_line": order_lines[material_code],
                        "quantity": Decimal(quantity),
                        "batch_no": batch_no,
                    }
                    if item["warehouse_code"] == "XJ-WH-RAW-01":
                        row["location"] = quarantine_location
                    elif material_code in self.material_locations:
                        row["location"] = self._location(
                            *self.material_locations[material_code]
                        )
                    rows.append(row)
                receipt = prc.create_receipt(
                    user=self.actor,
                    order=order,
                    warehouse=self._warehouse(item["warehouse_code"]),
                    lines=rows,
                    supplier_delivery_no=f"DN-{item['receipt_no']}",
                    remark=DEMO_REMARK,
                    receipt_no=item["receipt_no"],
                )
                self._count("procurement.GoodsReceipt", True)
            if receipt is not None and receipt.status == ReceiptStatus.DRAFT:
                receipt = prc.post_receipt(
                    receipt, user=self.actor, idempotency_key=f"xj-seed-{item['receipt_no']}-post"
                )
            if receipt is not None and receipt.status == ReceiptStatus.POSTED and item["inspect"]:
                prc.inspect_receipt(
                    receipt,
                    user=self.actor,
                    result="qualified",
                    remark="来料检验：外观、规格与数量符合标准，判定合格放行",
                    idempotency_key=f"xj-seed-{item['receipt_no']}-inspect",
                )

    def _sales_flow(self) -> None:
        """销售闭环：订单 → 审批 → 占用 → 发货 → 退货 → 检验判定。"""
        from apps.sales import services as sal
        from apps.sales.models import (
            ReturnDisposition,
            ReturnStatus,
            SalesOrder,
            SalesOrderStatus,
            SalesReturn,
            SalesShipment,
            ShipmentStatus,
        )
        from apps.wms.models import DocumentType, InventoryDocument, QualityStatus

        warehouse = self._warehouse("XJ-WH-FG-01")
        finished_location = self._location("XJ-WH-FG-01", "STO", "A01-01-01")

        if not InventoryDocument.objects.filter(
            company=self.company, biz_no="XJ-FG-OPEN-01"
        ).exists():
            self._stock_document(
                "XJ-FG-OPEN-01",
                DocumentType.RECEIPT,
                "XJ-WH-FG-01",
                [
                    {
                        "material_id": self.sku_map[sku_code].material_id,
                        "location_id": finished_location.id,
                        "batch_no": "XJ-FG-2603-01",
                        "quality_status": QualityStatus.QUALIFIED,
                        "quantity": Decimal(quantity),
                    }
                    for sku_code, quantity in (
                        ("XJYS-W-2601-WH-M", "360"),
                        ("XJYS-W-2601-WH-L", "320"),
                        ("XJYS-M-2601-NV-175A", "280"),
                        ("XJYS-M-2601-NV-180A", "240"),
                        ("XJYS-W-2602-LG-L", "220"),
                        ("XJYS-M-2602-BK-175A", "260"),
                    )
                ],
                reason="2026-03 首批成品入库（电商与经销渠道备货）",
            )

        if SalesOrder.objects.filter(company=self.company).exists():
            self.stdout.write("  销售：已存在演示单据，跳过。")
            return

        definitions = (
            {
                "order_no": "XJ-SO-0001",
                "customer_code": "XJ-CUS-004",
                "sku_code": "XJYS-W-2601-WH-M",
                "quantity": "180",
                "price": "129.000000",
                "outcome": "shipped",
                "priority": "urgent",
                "carrier": "顺丰速运",
                "tracking_no": "SF-XJ-2601001",
            },
            {
                "order_no": "XJ-SO-0002",
                "customer_code": "XJ-CUS-002",
                "sku_code": "XJYS-M-2601-NV-175A",
                "quantity": "120",
                "price": "268.000000",
                "outcome": "shipped",
                "priority": "normal",
                "carrier": "德邦物流",
                "tracking_no": "DB-XJ-2601002",
            },
            {
                "order_no": "XJ-SO-0003",
                "customer_code": "XJ-CUS-003",
                "sku_code": "XJYS-W-2602-LG-L",
                "quantity": "90",
                "price": "199.000000",
                "outcome": "submitted",
                "priority": "normal",
                "carrier": "",
                "tracking_no": "",
            },
            {
                "order_no": "XJ-SO-0004",
                "customer_code": "XJ-CUS-001",
                "sku_code": "XJYS-M-2602-BK-175A",
                "quantity": "150",
                "price": "159.000000",
                "outcome": "draft",
                "priority": "normal",
                "carrier": "",
                "tracking_no": "",
            },
        )
        for index, item in enumerate(definitions):
            sku = self.sku_map[item["sku_code"]]
            customer = self.customers[item["customer_code"]]
            order = SalesOrder.objects.filter(
                company=self.company, order_no=item["order_no"]
            ).first()
            order_day = DATA_START + timedelta(days=20 + index * 32)
            if order is None:
                order = sal.create_order(
                    user=self.actor,
                    company=self.company,
                    customer=customer,
                    lines=[
                        {
                            "material_id": sku.material_id,
                            "sku_id": sku.pk,
                            "quantity": Decimal(item["quantity"]),
                            "price": Decimal(item["price"]),
                        }
                    ],
                    order_date=order_day,
                    expected_date=order_day + timedelta(days=18),
                    priority=item["priority"],
                    warehouse=warehouse,
                    tax_rate=Decimal("13"),
                    payment_terms="月结 30 天",
                    delivery_address=customer.address,
                    remark=f"{DEMO_REMARK}：订单到交付链路",
                    order_no=item["order_no"],
                )
                self._count("sales.SalesOrder", True)
                self._stamp(order, created_at=self._aware(order_day, 9, 20))
            if item["outcome"] == "draft":
                continue
            if order.status == SalesOrderStatus.DRAFT:
                order = sal.submit_order(order, user=self.actor, comment="演示提交")
            if order.status == SalesOrderStatus.SUBMITTED:
                self._approve_fully(order.approval_instance_id, order)
            if item["outcome"] == "submitted":
                continue
            if order.status in SalesOrderStatus.open_for_shipment():
                sal.reserve_order_stock(order, user=self.actor, reason="订单备货占用成品库存")

            shipment = SalesShipment.objects.filter(
                company=self.company, sales_order=order, shipment_no=f"XJ-SH-{index + 1:04d}"
            ).first()
            if shipment is None and order.status in SalesOrderStatus.open_for_shipment():
                order_line = order.lines.order_by("line_no").first()
                shipment = sal.create_shipment(
                    user=self.actor,
                    order=order,
                    warehouse=warehouse,
                    lines=[{"order_line": order_line, "quantity": Decimal(item["quantity"])}],
                    receiver_name=customer.primary_contact_name,
                    receiver_phone=customer.primary_contact_phone,
                    delivery_address=customer.address,
                    carrier=item["carrier"],
                    tracking_no=item["tracking_no"],
                    shipment_no=f"XJ-SH-{index + 1:04d}",
                    remark=f"{DEMO_REMARK}：整单发货",
                )
                self._count("sales.SalesShipment", True)
            if shipment is not None and shipment.status == ShipmentStatus.DRAFT:
                shipment = sal.post_shipment(
                    shipment, user=self.actor, idempotency_key=f"xj-seed-ship-{index + 1:04d}"
                )
            if shipment is None or shipment.status != ShipmentStatus.POSTED:
                continue
            if item["order_no"] != "XJ-SO-0001":
                continue

            return_doc = SalesReturn.objects.filter(
                company=self.company, return_no="XJ-SR-0001"
            ).first()
            if return_doc is None:
                order_line = order.lines.order_by("line_no").first()
                return_doc = sal.create_return(
                    user=self.actor,
                    order=order,
                    warehouse=warehouse,
                    lines=[{"order_line": order_line, "quantity": Decimal("12")}],
                    shipment=shipment,
                    reason="客户反馈 12 件袖长偏差超差，要求换货",
                    return_no="XJ-SR-0001",
                    remark=f"{DEMO_REMARK}：退货先入待检，再判定质量状态",
                )
                self._count("sales.SalesReturn", True)
            if return_doc.status == ReturnStatus.DRAFT:
                return_doc = sal.post_return(
                    return_doc, user=self.actor, idempotency_key="xj-seed-sales-return-0001"
                )
            if return_doc.status == ReturnStatus.POSTED:
                sal.inspect_return(
                    return_doc,
                    user=self.actor,
                    result=ReturnDisposition.QUALIFIED,
                    remark="复检：外观与尺寸符合标准，转合格库存（人工判定）",
                    idempotency_key="xj-seed-sales-return-inspect-0001",
                )

    # -- 工程数据（BOM / 工艺路线）与 MRP ---------------------------------
    def _planning_flow(self) -> None:
        from apps.planning import services as pl
        from apps.planning.models import Bom, BomStatus, Routing, RoutingStatus

        bom_definitions = {
            "XJYS-W-2601": (
                ("XJ-FAB-001", "0.280000", "0.060000", "大身"),
                ("XJ-ACC-001", "0.004000", "0.050000", "缝制"),
                ("XJ-ACC-002", "2", "0.020000", "门襟"),
                ("XJ-ACC-005", "1", "0.010000", "领口"),
            ),
            "XJYS-W-2602": (
                ("XJ-FAB-002", "0.480000", "0.060000", "大身"),
                ("XJ-ACC-001", "0.006000", "0.050000", "缝制"),
                ("XJ-ACC-002", "2", "0.020000", "袋口"),
                ("XJ-ACC-004", "0.090000", "0.080000", "袖口与下摆"),
                ("XJ-ACC-005", "1", "0.010000", "领口"),
            ),
            "XJYS-M-2601": (
                ("XJ-FAB-003", "1.150000", "0.070000", "大身与袖子"),
                ("XJ-ACC-001", "0.012000", "0.050000", "缝制"),
                ("XJ-ACC-002", "4", "0.020000", "门襟与袖口"),
                ("XJ-ACC-003", "1", "0.010000", "前襟"),
                ("XJ-ACC-005", "2", "0.010000", "领口与侧缝"),
            ),
            "XJYS-M-2602": (
                ("XJ-FAB-001", "0.220000", "0.060000", "大身"),
                ("XJ-ACC-001", "0.003500", "0.050000", "缝制"),
                ("XJ-ACC-005", "1", "0.010000", "领口"),
            ),
        }
        routing_steps = (
            {
                "sequence": 1,
                "name": "裁剪",
                "workshop": self.workshops["F01/CUT"],
                "workcenter": "一号智能裁剪线",
                "equipment_requirement": "智能裁床",
                "standard_hours": Decimal("0.080000"),
            },
            {
                "sequence": 2,
                "name": "缝制",
                "workshop": self.workshops["F01/SEW"],
                "workcenter": "一号缝制线",
                "equipment_requirement": "电脑平缝机 / 包缝机",
                "standard_hours": Decimal("0.360000"),
            },
            {
                "sequence": 3,
                "name": "整烫",
                "workshop": self.workshops["F01/FIN"],
                "workcenter": "一号整烫包装线",
                "equipment_requirement": "蒸汽整烫机",
                "standard_hours": Decimal("0.060000"),
            },
            {
                "sequence": 4,
                "name": "成衣检验",
                "workshop": self.workshops["F01/FIN"],
                "workcenter": "成衣检验工位",
                "standard_hours": Decimal("0.050000"),
                "is_quality_gate": True,
            },
            {
                "sequence": 5,
                "name": "包装入库",
                "workshop": self.workshops["F01/FIN"],
                "workcenter": "包装工位",
                "standard_hours": Decimal("0.040000"),
            },
        )
        effective = DATA_START
        for style_code, lines in bom_definitions.items():
            style = self.styles[style_code]
            bom = (
                Bom.objects.filter(company=self.company, style=style, sku__isnull=True)
                .order_by("-version_no")
                .first()
            )
            if bom is None:
                bom = pl.create_bom(
                    user=self.actor,
                    company=self.company,
                    style=style,
                    lines=[
                        {
                            "material": self.materials[material_code],
                            "quantity": Decimal(quantity),
                            "loss_rate": Decimal(loss),
                            "position": position,
                        }
                        for material_code, quantity, loss, position in lines
                    ],
                    effective_from=effective,
                    remark=DEMO_REMARK,
                )
                self._count("planning.Bom", True)
            if bom.status == BomStatus.DRAFT:
                bom = pl.submit_bom(bom, user=self.actor, comment="演示提交")
            if bom.status == BomStatus.SUBMITTED:
                self._approve_fully(bom.approval_instance_id, bom)

            routing = (
                Routing.objects.filter(company=self.company, style=style, sku__isnull=True)
                .order_by("-version_no")
                .first()
            )
            if routing is None:
                routing = pl.create_routing(
                    user=self.actor,
                    company=self.company,
                    style=style,
                    steps=routing_steps,
                    effective_from=effective,
                    remark=DEMO_REMARK,
                )
                self._count("planning.Routing", True)
            if routing.status == RoutingStatus.DRAFT:
                routing = pl.submit_routing(routing, user=self.actor, comment="演示提交")
            if routing.status == RoutingStatus.SUBMITTED:
                self._approve_fully(routing.approval_instance_id, routing)

    def _mrp_flow(self) -> None:
        """MRP 运算：按销售订单与现有库存净算，生成采购 / 生产建议并转单。"""
        from apps.planning import mrp as mrp_services
        from apps.planning.models import MrpRun, MrpSuggestion

        if MrpRun.objects.filter(company=self.company).exists():
            self.stdout.write("  MRP：已存在演示运算，跳过。")
            return
        run = mrp_services.run_mrp(
            company=self.company,
            user=self.actor,
            horizon_start=self.today,
            horizon_end=self.today + timedelta(days=30),
            bucket="week",
            remark=f"{DEMO_REMARK}：滚动 4 周净需求运算",
        )
        self._count("planning.MrpRun", True)
        self._stamp(run, created_at=self._aware(self.today - timedelta(days=6), 20, 0))

        suggestions = list(
            MrpSuggestion.objects.filter(run=run).order_by("due_date", "id")
        )
        purchase = [row for row in suggestions if row.suggestion_type == "purchase"][:3]
        production = [row for row in suggestions if row.suggestion_type == "production"][:1]
        for suggestion in purchase + production:
            if suggestion.status != "open":
                continue
            mrp_services.convert_suggestion(
                suggestion,
                user=self.actor,
                remark=f"{DEMO_REMARK}：由 MRP 建议转单",
            )
            self._count("planning.MrpSuggestion.converted", True)

    # -- MES 生产 ----------------------------------------------------------
    def _mes_flow(self) -> None:
        from apps.mes import services as mes_services
        from apps.mes.models import (
            ProductionOrder,
            ProductionOrderStatus,
            ProductionStepStatus,
        )

        if ProductionOrder.objects.filter(company=self.company).exists():
            self.stdout.write("  MES 生产：已存在演示工单，跳过。")
            return
        definitions = (
            {
                "order_no": "XJ-MO-0001",
                "style_code": "XJYS-W-2601",
                "sku_code": "XJYS-W-2601-WH-M",
                "quantity": "400",
                "outcome": "closed",
                "scrap": "6",
                "line": "F01/SEW/SL01",
                "equipment_code": "XJ-EQ-SEW-01",
                "operator_no": "XJ2009",
                "source_type": "sales_order",
                "source_no": "XJ-SO-0001",
            },
            {
                "order_no": "XJ-MO-0002",
                "style_code": "XJYS-M-2601",
                "sku_code": "XJYS-M-2601-NV-175A",
                "quantity": "300",
                "outcome": "completed",
                "scrap": "4",
                "line": "F01/SEW/SL01",
                "equipment_code": "XJ-EQ-SEW-02",
                "operator_no": "XJ2009",
                "source_type": "mrp_suggestion",
                "source_no": "MRP-2026-04",
            },
            {
                "order_no": "XJ-MO-0003",
                "style_code": "XJYS-W-2602",
                "sku_code": "XJYS-W-2602-LG-L",
                "quantity": "260",
                "outcome": "in_progress",
                "scrap": "0",
                "line": "F01/SEW2/SL02",
                "equipment_code": "XJ-EQ-SEW-05",
                "operator_no": "XJ2011",
                "source_type": "sales_order",
                "source_no": "XJ-SO-0003",
            },
            {
                "order_no": "XJ-MO-0004",
                "style_code": "XJYS-M-2602",
                "sku_code": "XJYS-M-2602-BK-175A",
                "quantity": "200",
                "outcome": "draft",
                "scrap": "0",
                "line": "F02/SEW/SL01",
                "equipment_code": None,
                "operator_no": "XJ2012",
                "source_type": "manual",
                "source_no": "",
            },
            {
                "order_no": "XJ-MO-0005",
                "style_code": "XJYS-W-2601",
                "sku_code": "XJYS-W-2601-WH-L",
                "quantity": "120",
                "outcome": "released",
                "scrap": "0",
                "line": "F01/SEW/SL01",
                "equipment_code": None,
                "operator_no": "XJ2009",
                "source_type": "manual",
                "source_no": "",
            },
            {
                "order_no": "XJ-MO-0006",
                "style_code": "XJYS-M-2601",
                "sku_code": "XJYS-M-2601-NV-180A",
                "quantity": "100",
                "outcome": "cancelled",
                "scrap": "0",
                "line": "F01/SEW/SL01",
                "equipment_code": None,
                "operator_no": "XJ2009",
                "source_type": "manual",
                "source_no": "",
            },
        )
        for index, item in enumerate(definitions):
            style = self.styles[item["style_code"]]
            sku = self.sku_map[item["sku_code"]]
            workshop_key = "/".join(item["line"].split("/")[:2])
            start_day = DATA_START + timedelta(days=12 + index * 26)
            order = ProductionOrder.objects.filter(
                company=self.company, order_no=item["order_no"]
            ).first()
            if order is None:
                order = mes_services.create_order(
                    self.actor,
                    company=self.company,
                    style=style,
                    sku=sku,
                    quantity=Decimal(item["quantity"]),
                    product_material=sku.material,
                    factory=self.factories[workshop_key.split("/")[0]],
                    workshop=self.workshops[workshop_key],
                    production_line=self.lines[item["line"]],
                    material_warehouse=self._warehouse("XJ-WH-RAW-01"),
                    receipt_warehouse=self._warehouse("XJ-WH-FG-01"),
                    planned_start=self._aware(start_day, 8, 0),
                    planned_end=self._aware(start_day + timedelta(days=6), 18, 0),
                    owner=self.employees["XJ2002"],
                    source_type=item["source_type"],
                    source_no=item["source_no"],
                    remark=f"{DEMO_REMARK}：{style.name}",
                    order_no=item["order_no"],
                )
                self._count("mes.ProductionOrder", True)
                self._stamp(order, created_at=self._aware(start_day - timedelta(days=4), 9, 0))
            if item["outcome"] == "draft":
                continue
            if item["outcome"] == "cancelled":
                if order.status == ProductionOrderStatus.DRAFT:
                    mes_services.release_order(order, user=self.actor)
                mes_services.cancel_order(
                    order, user=self.actor, reason="客户订单变更，本批暂缓投产"
                )
                continue
            if order.status == ProductionOrderStatus.DRAFT:
                order = mes_services.release_order(order, user=self.actor)
                self._stamp(
                    order,
                    released_at=self._aware(start_day, 8, 30),
                    created_at=self._aware(start_day - timedelta(days=4), 9, 0),
                )
            if item["outcome"] in {"released", "cancelled"}:
                continue

            # 领料：把 BOM 用料行指到该物料常备储位后整单领料
            for line in order.materials.select_related("material").all():
                target = self.material_locations.get(line.material.code)
                if target is not None and line.location_id is None:
                    line.location = self._location(*target)
                    line.save(update_fields=["location", "updated_at"])
            if order.issue_document_id is None:
                mes_services.issue_materials(
                    order, user=self.actor, idempotency_key=f"xj-seed-issue-{order.order_no}"
                )
                self._count("mes.ProductionOrder.issued", True)

            quantity = order.quantity
            if item["outcome"] == "in_progress":
                first_step = order.steps.order_by("sequence").first()
                if first_step is not None and first_step.status == ProductionStepStatus.PENDING:
                    mes_services.report_production(
                        order,
                        user=self.actor,
                        step=first_step,
                        quantity=quantity,
                        qualified_quantity=quantity,
                        operator=self.employees["XJ2010"],
                        equipment=self.equipments["XJ-EQ-CUT-01"],
                        work_hours=Decimal("26.5"),
                        started_at=self._aware(start_day, 8, 30),
                        finished_at=self._aware(start_day + timedelta(days=1), 17, 30),
                        remark="裁剪完成，转入缝制",
                    )
                    self._count("mes.ProductionReport", True)
                continue

            scrap = Decimal(item["scrap"])
            for step in order.steps.order_by("sequence"):
                if step.status == ProductionStepStatus.COMPLETED:
                    continue
                qualified = quantity - scrap
                report, order = mes_services.report_production(
                    order,
                    user=self.actor,
                    step=step,
                    quantity=quantity,
                    qualified_quantity=qualified,
                    scrap_quantity=scrap,
                    operator=self.employees[item["operator_no"]],
                    equipment=(
                        self.equipments[item["equipment_code"]]
                        if item["equipment_code"]
                        else None
                    ),
                    work_hours=step.standard_hours * quantity,
                    started_at=self._aware(start_day + timedelta(days=step.sequence - 1), 8, 30),
                    finished_at=self._aware(start_day + timedelta(days=step.sequence), 17, 30),
                    remark=f"{step.name}工序报工",
                )
                self._count("mes.ProductionReport", True)
                scrap = Decimal("0")
                # report_production 内部重新取了 step 行，质检点检验单挂在那一份对象上，
                # 必须回读才能看到 inspection_order。
                step.refresh_from_db(fields=["inspection_order"])
                if step.is_quality_gate and step.inspection_order_id:
                    self._pass_inspection(
                        step.inspection_order,
                        day=start_day + timedelta(days=step.sequence),
                    )
            order.refresh_from_db()
            if order.status == ProductionOrderStatus.IN_PROGRESS:
                order = mes_services.complete_order(
                    order, user=self.actor, remark="全部工序完工，质检点合格"
                )
            if item["outcome"] == "in_progress":
                continue
            if order.receipt_document_id is None:
                mes_services.receipt_finished_goods(
                    order,
                    user=self.actor,
                    location=self._location("XJ-WH-FG-01", "STO", "A01-02-01"),
                    batch_no=f"XJ-FG-{item['order_no'].split('-')[-1]}-01",
                    idempotency_key=f"xj-seed-fg-{order.order_no}",
                )
                self._count("mes.ProductionOrder.receipted", True)
            order.refresh_from_db()
            if item["outcome"] == "closed" and order.status == ProductionOrderStatus.COMPLETED:
                mes_services.close_order(order, user=self.actor, remark="批次结束，工单关闭")
                self._stamp(order, closed_at=self._aware(start_day + timedelta(days=9), 17, 0))

    # -- 质量管理（QMS） ---------------------------------------------------
    def _quality_items(self) -> dict[str, QualityInspectionItem]:
        result: dict[str, QualityInspectionItem] = {}
        definitions = (
            ("XJ-QI-001", "面料克重", "physical", "quantitative", "g/m2", "170", "190", "GB/T 4669"),
            ("XJ-QI-002", "面料幅宽", "size", "quantitative", "cm", "180", "190", "GB/T 4669"),
            ("XJ-QI-003", "色差等级", "appearance", "qualitative", "", None, None, "GB/T 250 灰卡≥4 级"),
            ("XJ-QI-004", "甲醛含量", "physical", "quantitative", "mg/kg", "0", "75", "GB 18401 B 类"),
            ("XJ-QI-005", "缝制针距密度", "physical", "quantitative", "针/3cm", "10", "14", "FZ/T 80002"),
            ("XJ-QI-006", "缝口强力", "physical", "quantitative", "N", "80", "320", "GB/T 3923.1"),
            ("XJ-QI-007", "衣长尺寸偏差", "size", "quantitative", "cm", "-1.5", "1.5", "GB/T 2660"),
            ("XJ-QI-008", "外观检查", "appearance", "qualitative", "", None, None, "无破损、无污渍、无线头"),
            ("XJ-QI-009", "包装与标签核对", "package", "qualitative", "", None, None, "吊牌、洗唛、条码齐全"),
            ("XJ-QI-010", "拉链往复试验", "function", "quantitative", "次", "800", "5000", "QB/T 2171"),
        )
        for code, name, category, value_type, unit, lower, upper, standard in definitions:
            result[code] = self._upsert(
                QualityInspectionItem,
                {"company": self.company, "code": code},
                {
                    "name": name,
                    "category": category,
                    "value_type": value_type,
                    "unit": unit,
                    "method": "抽样检验",
                    "standard_text": standard,
                    "lower_limit": Decimal(lower) if lower is not None else None,
                    "upper_limit": Decimal(upper) if upper is not None else None,
                    "is_active": True,
                },
            )
        return result

    def _inspection_rows(self, order, *, fail_count: int = 0) -> list[dict]:
        """按检验类型挑项目并造实测值；fail_count 指定超差项数。"""
        mapping = {
            "iqc": ("XJ-QI-001", "XJ-QI-002", "XJ-QI-003", "XJ-QI-004"),
            "first_article": ("XJ-QI-005", "XJ-QI-007", "XJ-QI-008"),
            "ipqc": ("XJ-QI-005", "XJ-QI-006", "XJ-QI-008"),
            "fqc": ("XJ-QI-006", "XJ-QI-007", "XJ-QI-008"),
            "oqc": ("XJ-QI-007", "XJ-QI-009", "XJ-QI-010"),
            "other": ("XJ-QI-008", "XJ-QI-009"),
        }
        codes = mapping.get(order.inspection_type, mapping["ipqc"])
        rows = []
        for index, code in enumerate(codes):
            item = self.quality_items[code]
            fail = index < fail_count
            if item.value_type == "quantitative":
                rows.append(
                    {
                        "item": item,
                        "measured_value": self._limit_value(item, fail=fail),
                        "remark": "超差，需返工" if fail else "",
                    }
                )
            else:
                rows.append(
                    {
                        "item": item,
                        "is_qualified": not fail,
                        "text_value": "不合格：存在明显色差" if fail else "符合标准",
                    }
                )
        return rows

    def _limit_value(self, item, *, fail: bool) -> Decimal:
        low = item.lower_limit if item.lower_limit is not None else Decimal("0")
        high = item.upper_limit if item.upper_limit is not None else low + Decimal("10")
        span = high - low
        if span <= 0:
            return low
        if fail:
            value = high + span * Decimal(str(round(random.uniform(0.05, 0.25), 4)))
        else:
            value = low + span * Decimal(str(round(random.uniform(0.2, 0.8), 4)))
        return value.quantize(Decimal("0.01"))

    def _pass_inspection(self, order, *, day: date | None = None, fail_count: int = 0) -> None:
        """录入结果 → 提交 → 判定（MES 质检点与 QMS 演示共用同一条路径）。"""
        from apps.qms import services as qms_services

        if getattr(self, "quality_items", None) is None:
            self.quality_items = self._quality_items()
        from apps.qms.models import QualityInspectionStatus, QualityJudgement

        order.refresh_from_db()
        if order.status != QualityInspectionStatus.DRAFT:
            return
        moment = self._aware(day or self.today, 15, 0)
        qms_services.record_results(order, self._inspection_rows(order, fail_count=fail_count))
        qms_services.submit_order(order)
        qms_services.judge_order(
            order,
            judgement=QualityJudgement.PASSED if not fail_count else QualityJudgement.FAILED,
            judge_remark="全项符合标准，判定合格" if not fail_count else "存在超差项，判定不合格并开质量报警",
            inspector=self.employees["XJ2007"],
            inspected_at=moment,
        )
        self._count("qms.QualityInspectionOrder", True)
        self._stamp(order, inspected_at=moment, created_at=moment - timedelta(hours=3))

    def _qms_flow(self) -> None:
        from apps.qms import services as qms_services
        from apps.qms.models import (
            QualityAlert,
            QualityAlertStatus,
            QualityInspectionOrder,
            QualityIssue,
            QualityIssueStatus,
        )

        self.quality_items = getattr(self, "quality_items", None) or self._quality_items()
        if QualityInspectionOrder.objects.filter(
            company=self.company, order_no__startswith="XJ-QC-"
        ).exists():
            self.stdout.write("  质量管理：已存在演示检验单，跳过。")
            return
        definitions = (
            ("iqc", "来料检验", "XJ-FAB-001", "XJ-FAB-B2601", "巴州棉纺", "3000", 0, "closed"),
            ("iqc", "来料检验", "XJ-ACC-003", "XJ-ACC-Z2603", "华瑞辅料", "12000", 0, "closed"),
            ("first_article", "首件检验", None, "XJ-MO-0001-FA", "", "5", 0, "closed"),
            ("ipqc", "过程检验", None, "XJ-MO-0001", "", "60", 0, "closed"),
            ("fqc", "成品检验", None, "XJ-MO-0001", "", "120", 0, "closed"),
            ("oqc", "出货检验", None, "XJ-SO-0001", "", "60", 0, "closed"),
            ("ipqc", "过程检验", None, "XJ-MO-0002", "", "80", 2, "judged"),
            ("fqc", "成品检验", None, "XJ-MO-0002", "", "150", 1, "judged"),
        )
        for index, (
            inspection_type,
            label,
            material_code,
            batch_no,
            _supplier_name,
            quantity,
            fail_count,
            outcome,
        ) in enumerate(definitions):
            day = DATA_START + timedelta(days=6 + index * 27)
            order = qms_services.create_order(
                self.actor,
                company=self.company,
                inspection_type=inspection_type,
                source_no=batch_no or f"XJ-QC-{index + 1:04d}",
                material=self.materials.get(material_code) if material_code else None,
                product_desc=f"{label}（演示数据）",
                batch_no=batch_no,
                workshop=self.workshops["F01/FIN"] if inspection_type in {"fqc", "oqc"} else None,
                quantity=Decimal(quantity),
                sample_quantity=Decimal(min(int(quantity), 20)),
                unit="PC",
                inspector=self.employees["XJ2007"],
                inspected_at=self._aware(day, 15, 0),
                remark=DEMO_REMARK,
                order_no=f"XJ-QC-{index + 1:04d}",
            )
            self._stamp(order, created_at=self._aware(day, 9, 10))
            self._pass_inspection(order, day=day, fail_count=fail_count)
            if outcome == "closed":
                for alert in order.alerts.all():
                    qms_services.handle_alert(alert, handler=self.employees["XJ2007"])
                    qms_services.close_alert(alert, remark="已整改并复检合格，报警闭环。")
                qms_services.close_order(order)
                self._stamp(order, judged_at=self._aware(day, 15, 30))
            else:
                self._stamp(order, judged_at=self._aware(day, 15, 30))

        alerts = list(
            QualityAlert.objects.filter(company=self.company, status=QualityAlertStatus.OPEN).order_by(
                "id"
            )
        )
        for index, alert in enumerate(alerts):
            if index == 0:
                issue = qms_services.create_issue_from_alert(
                    alert,
                    title="缝制针距密度超差（下摆明线）",
                    category="craft",
                    cause="缝纫机针距调节机构松动，操作工未按首件确认换线后参数。",
                    corrective_action="重新校准针距并全批返工返修，返工后逐件复检。",
                    preventive_action="换线换款必须做首件确认，机修每周点检针距机构。",
                )
                self._count("qms.QualityIssue", True)
                qms_services.publish_issue(issue)
                self._stamp(issue, created_at=self._aware(self.today - timedelta(days=40), 10, 0))
                qms_services.handle_alert(alert, handler=self.employees["XJ2007"])
                qms_services.close_alert(alert, remark="已返工返修并复检合格，纳入质量问题知识库。")
            elif index == 1:
                qms_services.handle_alert(alert, handler=self.employees["XJ2007"])
        archived = (
            QualityIssue.objects.filter(
                company=self.company, status=QualityIssueStatus.PUBLISHED
            )
            .exclude(issue_no=getattr(issue, "issue_no", ""))
            .first()
        )
        if archived is not None:
            qms_services.archive_issue(archived)

    # -- 供应商评价（SRM） -------------------------------------------------
    def _srm_flow(self) -> None:
        from apps.srm import services as srm_services
        from apps.srm.models import (
            EvaluationDimension,
            SupplierEvaluation,
            SupplierEvaluationWeight,
        )

        if SupplierEvaluation.objects.filter(company=self.company).exists():
            self.stdout.write("  供应商评价：已存在演示评价，跳过。")
            return
        config = SupplierEvaluationWeight.objects.filter(
            company=self.company, is_active=True
        ).first()
        if config is None:
            config = srm_services.create_weight_config(
                self.actor,
                company=self.company,
                weights={
                    EvaluationDimension.QUALITY: "30",
                    EvaluationDimension.TECHNOLOGY: "15",
                    EvaluationDimension.RESPONSE: "15",
                    EvaluationDimension.DELIVERY: "25",
                    EvaluationDimension.COST: "15",
                },
                remark=f"{DEMO_REMARK}：质量导向权重",
                activate=True,
            )
            self._count("srm.SupplierEvaluationWeight", True)

        score_board = {
            "XJ-SUP-001": ("92", "85", "88", "90", "82"),
            "XJ-SUP-002": ("88", "80", "86", "84", "86"),
            "XJ-SUP-003": ("85", "88", "90", "78", "75"),
            "XJ-SUP-004": ("78", "72", "80", "82", "88"),
            "XJ-SUP-005": (None, "70", "75", None, "72"),
        }
        dimensions = tuple(EvaluationDimension.values)
        for index, (supplier_code, scores) in enumerate(score_board.items()):
            supplier = self.suppliers[supplier_code]
            period_end = self.today - timedelta(days=15 + index * 12)
            evaluation = srm_services.create_evaluation(
                self.actor,
                company=self.company,
                supplier=supplier,
                weight_config=config,
                missing_dimension_policy="mark_missing",
                period_start=period_end - timedelta(days=90),
                period_end=period_end,
                evaluated_by=self.employees["XJ2004"],
                evaluated_at=self._aware(period_end, 16, 0),
                remark=f"{DEMO_REMARK}：季度供应商量化评价",
            )
            self._count("srm.SupplierEvaluation", True)
            rows = [
                {
                    "dimension": dimension,
                    "raw_score": score,
                    "raw_observation": {
                        "批次合格率": f"{score}%" if score else "未统计",
                        "统计期间": f"{period_end - timedelta(days=90)} ~ {period_end}",
                    },
                    "remark": "" if score else "本期无交付记录，按缺失维度处理",
                }
                for dimension, score in zip(dimensions, scores, strict=False)
            ]
            srm_services.set_evaluation_lines(self.actor, evaluation, rows)
            if index < 3:
                srm_services.publish_evaluation(self.actor, evaluation)
                self._stamp(evaluation, created_at=self._aware(period_end, 16, 30))
            if index == 3:
                srm_services.publish_evaluation(self.actor, evaluation)
                srm_services.archive_evaluation(self.actor, evaluation)

    # -- 客户管理（CRM 投诉与评价） ----------------------------------------
    def _crm_flow(self) -> None:
        from apps.crm import services as crm_services
        from apps.crm.models import (
            ComplaintStatus,
            CustomerComplaint,
            ProductReview,
            ProductReviewStatus,
        )

        if not CustomerComplaint.objects.filter(company=self.company).exists():
            definitions = (
                ("XJ-CP-0001", "XJ-CUS-004", "quality", "important", "online",
                 "长绒棉T恤袖口线头多且领口偏大",
                 "客户收到 180 件订单后反馈：约 20 件袖口线头未修剪，5 件领口比样衣偏大 1cm。",
                 "closed", 24),
                ("XJ-CP-0002", "XJ-CUS-001", "delivery", "general", "phone",
                 "工装夹克交期延后 3 天",
                 "客户反映原定 3 月 18 日到货的工装夹克实际 3 月 21 日到达，影响其门店上架计划。",
                 "closed", 62),
                ("XJ-CP-0003", "XJ-CUS-003", "packaging", "general", "email",
                 "外箱受潮导致纸箱变形",
                 "公路运输途中遇雨，外箱部分受潮变形，客户要求后续加防潮包装。",
                 "resolved", 40),
                ("XJ-CP-0004", "XJ-CUS-005", "price", "general", "salesman",
                 "促销批次结算单价与报价不一致",
                 "客户对 5 月促销批次的结算单价提出异议，认为与季度报价单不符。",
                 "handling", 12),
                ("XJ-CP-0005", "XJ-CUS-002", "service", "severe", "visit",
                 "售后换货响应慢",
                 "客户反馈换货申请提交后 5 个工作日仍未收到处理结果，影响其二批订单信心。",
                 "pending", 4),
            )
            for (
                complaint_no, customer_code, complaint_type, level, source,
                title, content, status, days_ago,
            ) in definitions:
                day = self.today - timedelta(days=days_ago)
                complaint = CustomerComplaint.objects.create(
                    company=self.company,
                    complaint_no=complaint_no,
                    customer=self.customers[customer_code],
                    complaint_type=complaint_type,
                    level=level,
                    status=ComplaintStatus.PENDING,
                    source=source,
                    title=title,
                    content=content,
                    complained_at=self._aware(day, 10, 30),
                    reporter=self.customers[customer_code].primary_contact_name,
                    reporter_phone=self.customers[customer_code].primary_contact_phone,
                    receiver=self.employees["XJ2005"],
                    remark=DEMO_REMARK,
                )
                self._count("crm.CustomerComplaint", True)
                self._stamp(complaint, created_at=self._aware(day, 10, 30))
                if status == "pending":
                    continue
                crm_services.accept_complaint(
                    complaint,
                    receiver=self.employees["XJ2005"],
                    handler=self.employees["XJ2007"],
                    measure="已受理并通知质量与仓储复核，24 小时内给出处理方案。",
                )
                self._stamp(complaint, accepted_at=self._aware(day + timedelta(days=1), 9, 0))
                if status == "handling":
                    continue
                resolved_day = day + timedelta(days=2)
                crm_services.resolve_complaint(
                    complaint,
                    measure=random.choice(
                        [
                            "返工修剪线头并复检合格，对偏大领口按尺寸重新配码补发。",
                            "调整排产与物流商，后续订单预留 2 天缓冲期并每周同步进度。",
                            "更换防潮包装并加托盘缠膜，运输合同增加防雨条款。",
                        ]
                    ),
                    handler=self.employees["XJ2007"],
                    satisfaction=random.choice([4, 5]),
                )
                self._stamp(complaint, resolved_at=self._aware(resolved_day, 15, 0))
                if status == "resolved":
                    continue
                crm_services.close_complaint(
                    complaint, note="客户确认处理结果，投诉闭环并归档。"
                )
                self._stamp(complaint, closed_at=self._aware(resolved_day + timedelta(days=1), 11, 0))

        if not ProductReview.objects.filter(company=self.company).exists():
            review_definitions = (
                ("XJ-CUS-004", "XJYS-W-2601-WH-M", 5, "closed",
                 "面料很舒服，新疆长绒棉确实亲肤，做工也不错。", 18),
                ("XJ-CUS-004", "XJYS-W-2601-WH-L", 4, "closed",
                 "版型偏大一点，建议按平时尺码买小一码。", 16),
                ("XJ-CUS-002", "XJYS-M-2601-NV-175A", 5, "replied",
                 "工装夹克耐磨，口袋设计实用，车间穿着很合适。", 33),
                ("XJ-CUS-003", "XJYS-W-2602-LG-L", 3, "replied",
                 "卫衣手感好，但帽绳偏短，希望改进。", 27),
                ("XJ-CUS-005", "XJYS-M-2601-KH-180A", 4, "pending",
                 "整体满意，交货稍慢，希望旺季提前排产。", 6),
                ("XJ-CUS-001", "XJYS-M-2602-BK-175A", 2, "pending",
                 "两件成衣下摆线迹不齐，已联系售后换货。", 3),
            )
            for index, (
                customer_code, sku_code, score, status, content, days_ago,
            ) in enumerate(review_definitions):
                day = self.today - timedelta(days=days_ago)
                sku = self.sku_map[sku_code]
                review = ProductReview.objects.create(
                    company=self.company,
                    review_no=f"XJ-RV-{index + 1:04d}",
                    customer=self.customers[customer_code],
                    sku=sku,
                    product_desc=f"{sku.style.name} {sku.color.name} {sku.size.name}",
                    score=score,
                    status=ProductReviewStatus.PENDING,
                    reviewer_name=self.customers[customer_code].primary_contact_name,
                    reviewed_at=day,
                    content=content,
                    remark=DEMO_REMARK,
                )
                self._count("crm.ProductReview", True)
                self._stamp(review, created_at=self._aware(day, 20, 0))
                if status == "pending":
                    continue
                crm_services.reply_product_review(
                    review,
                    reply=random.choice(
                        [
                            "感谢反馈！已同步生产与质检部门持续改进缝制工艺。",
                            "感谢支持！尺码建议已更新到商品页，欢迎继续监督。",
                            "非常抱歉给您带来不便，售后已与您联系安排换货。",
                        ]
                    ),
                    replier=self.employees["XJ2005"],
                )
                self._stamp(review, replied_at=self._aware(day + timedelta(days=1), 10, 0))
                if status == "replied":
                    continue
                crm_services.close_product_review(
                    review, note="已与客户确认处理结果，评价闭环归档。"
                )
                self._stamp(review, closed_at=self._aware(day + timedelta(days=2), 9, 30))

    # -- 安全环保（EHS） ---------------------------------------------------
    def _ehs_flow(self) -> None:
        from apps.ehs import services as ehs_services
        from apps.ehs.models import (
            AccidentRecord,
            AccidentStatus,
            ComplianceCheck,
            ComplianceResult,
            ComplianceStatus,
            EmergencyPlan,
            EnvironmentMonitor,
            FireDrill,
            FireFacility,
            FireFacilityStatus,
            HazardRecord,
            HazardStatus,
            PermitStatus,
            RegulationStatus,
            SafetyCheck,
            SafetyRegulation,
            SafetyTraining,
            SpecialEquipmentInspection,
            TrainingStatus,
            WasteRecord,
            WasteStatus,
            WorkPermit,
        )

        if SafetyRegulation.objects.filter(company=self.company).exists():
            self.stdout.write("  安全环保：已存在演示记录，跳过。")
            return
        ehs = self.employees["XJ2016"]
        qc = self.employees["XJ2007"]

        def log(domain: str, business_type: str, action: str, label: str, detail: str, day: date):
            ehs_services.log_operation(
                company_id=self.company.pk,
                domain=domain,
                business_type=business_type,
                action=action,
                business_label=label,
                operator=ehs,
                detail=detail,
                payload={"来源": "seed_demo_xjys"},
            )

        # 制度与培训
        for index, (name, category, org, issue_day) in enumerate(
            (
                ("安全生产责任制管理办法", "system", "公司安全生产委员会", 5),
                ("设备安全操作规程（缝制与裁剪）", "operation", "设备动力部", 12),
                ("动火作业安全管理制度", "operation", "安全环保部", 26),
                ("生产安全事故应急预案管理办法", "emergency", "公司安全生产委员会", 48),
                ("危险废物规范化管理细则", "other", "安全环保部", 66),
            )
        ):
            day = DATA_START + timedelta(days=issue_day)
            regulation = SafetyRegulation.objects.create(
                company=self.company,
                code=f"XJ-SR-{index + 1:03d}",
                name=name,
                category=category,
                version_no=f"A/{2026}",
                issue_org=org,
                issue_date=day,
                effective_date=day + timedelta(days=5),
                status=RegulationStatus.EFFECTIVE,
                owner_department=self.departments["EHS"],
                owner_employee=ehs,
                remark=DEMO_REMARK,
            )
            self._count("ehs.SafetyRegulation", True)
            self._stamp(regulation, created_at=self._aware(day, 10, 0))

        for _index, (topic, training_type, day_offset, participants, hours) in enumerate(
            (
                ("新员工三级安全教育（入厂）", "induction", 15, 12, "8.0"),
                ("缝制设备安全操作与应急处置", "special", 62, 26, "4.0"),
                ("动火作业与消防器材实操", "special", 96, 18, "4.0"),
                ("安全生产月专题复训", "refresher", 158, 36, "3.0"),
                ("危险废物规范处置培训", "special", 205, 14, "2.5"),
                ("下半年消防疏散演练前培训", "drill", 248, 40, "2.0"),
            )
        ):
            day = DATA_START + timedelta(days=day_offset)
            training = SafetyTraining.objects.create(
                company=self.company,
                training_no=ehs_services.next_training_no(),
                topic=topic,
                training_type=training_type,
                trainer="新疆应急管理学院 讲师 / 内部注册安全工程师",
                department=self.departments["EHS"],
                planned_date=day - timedelta(days=3),
                actual_date=day,
                duration_hours=Decimal(hours),
                participant_count=participants,
                passed_count=participants - 1,
                status=TrainingStatus.FINISHED,
                remark=DEMO_REMARK,
            )
            self._count("ehs.SafetyTraining", True)
            self._stamp(training, created_at=self._aware(day, 9, 0))

        # 隐患排查与整改闭环
        hazard_definitions = (
            ("裁剪车间配电箱门未关且周边堆放布卷", "high", 22, "closed"),
            ("缝制一车间通道被半成品周转箱占用", "medium", 55, "closed"),
            ("空压站压力表超期未校验", "high", 88, "closed"),
            ("成品仓消防栓前堆放纸箱", "medium", 120, "verifying"),
            ("锅炉房燃气报警器探头积灰未清洁", "medium", 175, "rectifying"),
            ("阿克苏车间地面油污未及时清理", "low", 210, "reported"),
        )
        for _index, (title, level, offset, outcome) in enumerate(hazard_definitions):
            day = DATA_START + timedelta(days=offset)
            hazard = HazardRecord.objects.create(
                company=self.company,
                hazard_no=ehs_services.next_hazard_no(),
                title=title,
                description=f"安全检查发现：{title}，需按「五定」要求整改。",
                level=level,
                source="inspection",
                location=random.choice(["裁剪车间", "缝制一车间", "空压站", "成品仓", "锅炉房"]),
                department=self.departments["EHS"],
                reported_by=ehs,
                found_date=day,
                due_date=day + timedelta(days=7),
                status=HazardStatus.REPORTED,
                remark=DEMO_REMARK,
            )
            self._count("ehs.HazardRecord", True)
            self._stamp(hazard, created_at=self._aware(day, 14, 0))
            if outcome == "reported":
                continue
            ehs_services.start_hazard_rectify(
                hazard,
                measure="现场立即整改：清理通道、断电挂牌、安排校验与清洁。",
                operator=ehs,
                rectified_by=ehs,
            )
            if outcome == "rectifying":
                continue
            ehs_services.submit_hazard_verify(
                hazard,
                operator=ehs,
                rectified_date=day + timedelta(days=2),
            )
            if outcome == "verifying":
                continue
            ehs_services.verify_hazard(
                hazard,
                result="现场复查合格，隐患已消除。",
                passed=True,
                operator=ehs,
                verified_by=qc,
            )
            self._stamp(hazard, verified_date=day + timedelta(days=3))

        # 应急预案与演练
        plan = EmergencyPlan.objects.create(
            company=self.company,
            code=ehs_services.next_plan_code(),
            name="生产安全事故综合应急预案",
            plan_type="production",
            response_level="company",
            issue_date=DATA_START + timedelta(days=30),
            review_date=DATA_START + timedelta(days=395),
            drill_cycle_days=180,
            next_drill_date=self.today + timedelta(days=45),
            status=RegulationStatus.EFFECTIVE,
            owner_employee=ehs,
            remark=DEMO_REMARK,
        )
        self._count("ehs.EmergencyPlan", True)
        fire_plan = EmergencyPlan.objects.create(
            company=self.company,
            code=ehs_services.next_plan_code(),
            name="火灾事故专项应急预案",
            plan_type="fire",
            response_level="workshop",
            issue_date=DATA_START + timedelta(days=32),
            review_date=DATA_START + timedelta(days=397),
            drill_cycle_days=180,
            next_drill_date=self.today + timedelta(days=60),
            status=RegulationStatus.EFFECTIVE,
            owner_employee=ehs,
            remark=DEMO_REMARK,
        )
        self._count("ehs.EmergencyPlan", True)

        for _index, (topic, drill_type, offset, participants) in enumerate(
            (
                ("灭火器实操演练（春季）", "extinguisher", 70, 32),
                ("车间火灾疏散演练（安全生产月）", "evacuation", 165, 86),
                ("危险化学品泄漏联合处置演练", "joint", 235, 24),
            )
        ):
            day = DATA_START + timedelta(days=offset)
            drill = FireDrill.objects.create(
                company=self.company,
                drill_no=ehs_services.next_drill_no(),
                topic=topic,
                drill_type=drill_type,
                planned_date=day - timedelta(days=5),
                actual_date=day,
                organizer="安全环保部",
                participant_count=participants,
                duration_minutes=random.choice([45, 60, 90]),
                assessment="演练组织有序，人员到位及时，处置流程符合预案要求。",
                issues="个别员工对灭火器提把握持方式不熟练，已现场纠正。",
                plan=fire_plan if drill_type != "joint" else plan,
                remark=DEMO_REMARK,
            )
            self._count("ehs.FireDrill", True)
            self._stamp(drill, created_at=self._aware(day, 15, 30))

        # 事故处理
        accident_definitions = (
            ("缝纫工手指被机针刺伤（轻伤）", "injury", "minor", 84, "closed"),
            ("空压机皮带断裂导致短时停机", "equipment", "general", 140, "rectified"),
            ("成品仓搬运工腰部扭伤", "injury", "minor", 20, "investigating"),
        )
        for _index, (title, category, level, offset, outcome) in enumerate(accident_definitions):
            day = DATA_START + timedelta(days=offset)
            accident = AccidentRecord.objects.create(
                company=self.company,
                accident_no=ehs_services.next_accident_no(),
                title=title,
                category=category,
                level=level,
                occurred_at=self._aware(day, 11, 20),
                location=random.choice(["缝制一车间", "空压站", "成品仓"]),
                department=self.departments["PROD"],
                injured_count=1 if category == "injury" else 0,
                lost_days=random.choice([0, 1, 2]),
                loss_amount=Decimal(str(round(random.uniform(500, 12000), 2))),
                description=f"{title}。现场已第一时间处置，未造成次生事故。",
                reporter=ehs,
                reported_at=self._aware(day, 11, 50),
                status=AccidentStatus.REPORTED,
                remark=DEMO_REMARK,
            )
            self._count("ehs.AccidentRecord", True)
            self._stamp(accident, created_at=self._aware(day, 12, 0))
            if outcome == "reported":
                continue
            ehs_services.start_accident_investigation(
                accident, investigator=qc, operator=ehs
            )
            if outcome == "investigating":
                continue
            ehs_services.rectify_accident(
                accident,
                measures="加装针距防护罩并开展专项安全教育，作业前检查防护装置。",
                causes="设备防护罩未完全闭合，员工未按规程佩戴防护手套。",
                operator=ehs,
            )
            if outcome == "rectified":
                continue
            ehs_services.close_accident(
                accident,
                result="整改措施落实到位，同类风险已消除，事故结案。",
                operator=ehs,
                closed_date=day + timedelta(days=12),
            )

        # 环保：排污监测 / 固废危废 / 环保合规
        monitor_definitions = (
            ("waste_water", "污水处理站总排口", "COD", "150", "118", "mg/L", 18),
            ("waste_water", "污水处理站总排口", "氨氮", "25", "14.6", "mg/L", 76),
            ("waste_gas", "锅炉房烟囱", "颗粒物", "20", "12.4", "mg/m3", 44),
            ("waste_gas", "锅炉房烟囱", "氮氧化物", "150", "132", "mg/m3", 132),
            ("noise", "厂界东侧", "昼间噪声", "65", "58.2", "dB(A)", 200),
            ("waste_water", "污水处理站总排口", "PH", "9", "7.4", "", 92),
        )
        for _index, (medium, point, pollutant, limit, measured, unit, offset) in enumerate(
            monitor_definitions
        ):
            day = DATA_START + timedelta(days=offset)
            limit_value = Decimal(limit)
            measured_value = Decimal(measured)
            monitor = EnvironmentMonitor.objects.create(
                company=self.company,
                monitor_no=ehs_services.next_monitor_no(),
                medium=medium,
                point_name=point,
                pollutant=pollutant,
                limit_value=limit_value,
                measured_value=measured_value,
                unit=unit,
                is_compliant=measured_value <= limit_value,
                monitored_at=self._aware(day, 10, 0),
                permit_no="91650100MA0XJYS001P",
                monitor_org="新疆环境监测总站（委托检测）",
                remark=DEMO_REMARK,
            )
            self._count("ehs.EnvironmentMonitor", True)
            self._stamp(monitor, created_at=self._aware(day, 10, 30))
            ehs_services.apply_monitor_compliance(monitor)

        waste_definitions = (
            ("废布料边角料", "general", "", "12.6", "吨", "stored", 30),
            ("废纸箱与包装物", "general", "", "4.8", "吨", "transferred", 88),
            ("废机油", "hazardous", "HW08 900-249-08", "0.62", "吨", "disposed", 120),
            ("沾染油污的棉纱与手套", "hazardous", "HW49 900-041-49", "0.18", "吨", "disposed", 196),
            ("废灯管", "hazardous", "HW29 900-023-29", "0.04", "吨", "stored", 214),
        )
        for index, (name, waste_type, code, quantity, unit, status, offset) in enumerate(
            waste_definitions
        ):
            day = DATA_START + timedelta(days=offset)
            waste = WasteRecord.objects.create(
                company=self.company,
                waste_no=ehs_services.next_waste_no(),
                waste_name=name,
                waste_type=waste_type,
                waste_code=code,
                quantity=Decimal(quantity),
                unit=unit,
                produced_date=day,
                storage_location="危废暂存间（防渗、防雨、防流失）"
                if waste_type == "hazardous"
                else "固废暂存区",
                disposal_method="委托有资质单位转移处置"
                if waste_type == "hazardous"
                else "回收再利用",
                disposal_org="新疆天蓝环保科技有限公司"
                if waste_type == "hazardous"
                else "乌鲁木齐再生资源回收公司",
                transfer_no=f"XJ-WT-{index + 1:04d}" if status != "stored" else "",
                disposed_date=day + timedelta(days=8) if status == "disposed" else None,
                status=WasteStatus(status),
                remark=DEMO_REMARK,
            )
            self._count("ehs.WasteRecord", True)
            self._stamp(waste, created_at=self._aware(day, 11, 0))

        compliance_definitions = (
            ("第一季度环保自查（排污许可执行报告）", "self", "compliant", 60, "closed"),
            ("生态环境局执法检查", "government", "partial", 130, "rectified"),
            ("ISO14001 第三方监督审核", "third_party", "compliant", 190, "closed"),
            ("排污许可证年度执行报告核查", "permit", "partial", 240, "pending"),
        )
        for _index, (title, check_type, result, offset, status) in enumerate(compliance_definitions):
            day = DATA_START + timedelta(days=offset)
            check = ComplianceCheck.objects.create(
                company=self.company,
                check_no=ehs_services.next_compliance_no(),
                title=title,
                check_type=check_type,
                check_date=day,
                organization="新疆生态环境监测总站"
                if check_type == "government"
                else "公司安全环保部",
                checker=ehs,
                result=ComplianceResult(result),
                issues="危废暂存间标识牌信息不完整；排污台账部分时段记录缺失。"
                if result != "compliant"
                else "",
                rectify_due_date=day + timedelta(days=30) if result != "compliant" else None,
                # 「已关闭」的检查先落到「已整改」，再由服务层关闭，
                # 这样状态推进（与操作日志）都走同一条业务路径。
                status=ComplianceStatus.RECTIFIED
                if status == "closed"
                else ComplianceStatus(status),
                rectified_date=day + timedelta(days=20) if status in {"rectified", "closed"} else None,
                owner_employee=ehs,
                remark=DEMO_REMARK,
            )
            self._count("ehs.ComplianceCheck", True)
            self._stamp(check, created_at=self._aware(day, 9, 30))
            if status == "closed":
                ehs_services.close_compliance_check(
                    check, operator=ehs, rectified_date=day + timedelta(days=20)
                )

        # 消防与设备设施安全
        fire_locations = (
            ("裁剪车间", "extinguisher", "4kg 干粉灭火器", 6),
            ("缝制一车间", "extinguisher", "4kg 干粉灭火器", 8),
            ("缝制二车间", "extinguisher", "4kg 干粉灭火器", 6),
            ("整烫包装车间", "extinguisher", "4kg 干粉灭火器", 4),
            ("成品仓", "hydrant", "室内消火栓", 3),
            ("原料仓", "hydrant", "室内消火栓", 2),
            ("配电室", "alarm", "感烟火灾探测报警器", 4),
            ("锅炉房", "alarm", "可燃气体报警器", 2),
            ("缝制一车间", "exit", "安全出口指示与应急照明", 4),
        )
        for _index, (location, facility_type, name, quantity) in enumerate(fire_locations):
            last_check = self._rand_date(end=self.today - timedelta(days=10))
            facility = FireFacility.objects.create(
                company=self.company,
                code=ehs_services.next_fire_facility_code(),
                name=name,
                facility_type=facility_type,
                location=location,
                quantity=quantity,
                unit="具" if facility_type in {"extinguisher", "hydrant"} else "个",
                last_check_date=last_check,
                next_check_date=last_check + timedelta(days=180),
                status=FireFacilityStatus.NORMAL,
                department=self.departments["EHS"],
                owner_employee=ehs,
                remark=DEMO_REMARK,
            )
            self._count("ehs.FireFacility", True)
            self._stamp(facility, created_at=self._aware(last_check, 10, 0))

        permit_definitions = (
            ("hot_work", "成品仓屋面防水补漏动火作业（焊接）", "high", 52, "accepted"),
            ("maintenance", "空压机主机检修（停机挂牌上锁）", "medium", 108, "finished"),
            ("explosion_proof", "锅炉房燃气管道法兰紧固（防爆工具）", "high", 168, "working"),
            ("confined_space", "污水处理站调节池清淤作业", "high", 21, "approved"),
            ("hot_work", "厂区管廊支架焊接加固", "medium", 6, "applied"),
        )
        for _index, (permit_type, content, risk, offset, outcome) in enumerate(permit_definitions):
            day = DATA_START + timedelta(days=offset)
            permit = WorkPermit.objects.create(
                company=self.company,
                permit_no=ehs_services.next_permit_no(),
                permit_type=permit_type,
                status=PermitStatus.APPLIED,
                work_content=content,
                work_location=random.choice(["成品仓", "空压站", "锅炉房", "污水处理站", "厂区管廊"]),
                risk_level=risk,
                protective_measures="作业前气体检测、配备灭火器与监护人、动火票与动火人资格审查、作业后 30 分钟复查。",
                applicant=self.employees["XJ2019"],
                department=self.departments["EAM"],
                start_at=self._aware(day, 8, 30),
                end_at=self._aware(day, 18, 0),
                remark=DEMO_REMARK,
            )
            self._count("ehs.WorkPermit", True)
            self._stamp(permit, created_at=self._aware(day - timedelta(days=2), 9, 0))
            if outcome == "applied":
                continue
            ehs_services.approve_permit(
                permit,
                approver=ehs,
                guardian=self.employees["XJ2016"],
                note="作业条件与防护措施已确认，同意作业。",
            )
            self._stamp(permit, approved_at=self._aware(day - timedelta(days=1), 16, 0))
            if outcome == "approved":
                continue
            ehs_services.start_permit_work(permit, operator=ehs)
            if outcome == "working":
                continue
            ehs_services.finish_permit_work(
                permit, result="作业完成，工完料尽场地清，动火后复查无残火。", operator=ehs
            )
            if outcome == "finished":
                continue
            ehs_services.accept_permit(
                permit,
                result="现场验收合格，恢复生产条件。",
                accepted_by=ehs,
                operator=ehs,
            )

        safety_check_definitions = (
            ("intrinsic", "缝制车间本质安全检查", "F01/SEW", "XJ-EQ-SEW-01", 40, "rectified"),
            ("explosion_proof", "锅炉房防爆电气专项检查", "F01/PWR", "XJ-EQ-BOILER-01", 96, "closed"),
            ("fire_proof", "配电室防火防爆与消防设施检查", "F01/PWR", "XJ-EQ-ELEC-01", 152, "closed"),
            ("intrinsic", "空压站设备本质安全检查", "F01/PWR", "XJ-EQ-AIR-01", 218, "normal"),
        )
        for _index, (
            check_type, title, _workshop_key, equipment_code, offset, outcome,
        ) in enumerate(safety_check_definitions):
            day = DATA_START + timedelta(days=offset)
            check = SafetyCheck.objects.create(
                company=self.company,
                check_no=ehs_services.next_safety_check_no(),
                check_type=check_type,
                title=title,
                check_date=day,
                checker=ehs,
                department=self.departments["EHS"],
                equipment=self.equipments[equipment_code],
                check_content="安全防护装置、急停与联锁、接地与漏电保护、防爆等级、消防器材配备。",
                problem_count=0 if outcome == "normal" else random.randint(1, 4),
                conclusion="防护装置齐全有效，符合安全要求。"
                if outcome == "normal"
                else "存在防护罩缺失、接地电阻偏高等问题，需限期整改。",
                status="normal" if outcome == "normal" else "rectified",
                rectify_requirement="" if outcome == "normal" else "补齐防护罩并复测接地电阻，7 日内完成。",
                rectified_date=day + timedelta(days=5) if outcome != "normal" else None,
                remark=DEMO_REMARK,
            )
            self._count("ehs.SafetyCheck", True)
            self._stamp(check, created_at=self._aware(day, 10, 0))

        for index, (equipment_code, org, offset, result) in enumerate(
            (
                ("XJ-EQ-BOILER-01", "新疆维吾尔自治区特种设备检验研究院", 58, "qualified"),
                ("XJ-EQ-PRES-01", "新疆维吾尔自治区特种设备检验研究院", 142, "qualified"),
                ("XJ-EQ-AIR-01", "乌鲁木齐市特种设备检验所", 205, "conditional"),
            )
        ):
            day = DATA_START + timedelta(days=offset)
            inspection = SpecialEquipmentInspection.objects.create(
                company=self.company,
                certificate_no=f"XJ-TS-2026-{index + 1:04d}",
                equipment=self.equipments[equipment_code],
                equipment_name=self.equipments[equipment_code].name,
                inspection_org=org,
                inspection_date=day,
                next_inspection_date=day + timedelta(days=365),
                result=result,
                inspector="王建军 / 李红",
                issue_date=day + timedelta(days=10),
                remark=DEMO_REMARK,
            )
            self._count("ehs.SpecialEquipmentInspection", True)
            self._stamp(inspection, created_at=self._aware(day, 11, 0))

        log("safety", "regulation", "create", "安全生产责任制管理办法", "发布 2026 版制度并组织宣贯。", DATA_START + timedelta(days=5))
        log("environment", "monitor", "create", "污水处理站总排口", "录入 1 月委托检测数据，COD 与氨氮达标。", DATA_START + timedelta(days=18))
        log("fire", "permit", "start", "成品仓动火作业", "动火作业开工，监护人到岗。", DATA_START + timedelta(days=52))

    # -- 厂内物流 ----------------------------------------------------------
    def _logistics_flow(self) -> None:
        from apps.logistics import services as logistics_services
        from apps.logistics.models import (
            AutomationDevice,
            AutomationDeviceStatus,
            LogisticsTask,
            LogisticsTaskStatus,
        )

        if AutomationDevice.objects.filter(company=self.company).exists():
            self.stdout.write("  厂内物流：已存在演示设备，跳过。")
            return
        device_definitions = (
            ("XJ-LG-AGV-01", "一号激光导航 AGV", "agv", "F01/SEW", "缝制一车间线边库", "500", "1.20", 86),
            ("XJ-LG-AGV-02", "二号激光导航 AGV", "agv", "F01/CUT", "裁剪车间线边库", "500", "1.20", 62),
            ("XJ-LG-SHUTTLE-01", "成品仓四向穿梭车", "shuttle", "F01/FIN", "成品仓货架区", "800", "1.80", 94),
            ("XJ-LG-STACKER-01", "巷道堆垛机", "stacker", "F01/FIN", "成品仓 1 号巷道", "1000", "1.50", 78),
            ("XJ-LG-ROBOT-01", "码垛机器人", "robot", "F01/FIN", "包装下线工位", "300", "0.95", 71),
        )
        devices: dict[str, AutomationDevice] = {}
        for code, name, device_type, workshop_key, location, load, speed, battery in (
            device_definitions
        ):
            day = self._rand_date(end=DATA_START + timedelta(days=60))
            device = AutomationDevice.objects.create(
                company=self.company,
                code=code,
                name=name,
                device_type=device_type,
                status=AutomationDeviceStatus.IDLE,
                workshop=self.workshops[workshop_key],
                location=location,
                max_load=Decimal(load),
                speed=Decimal(speed),
                battery_level=battery,
                commissioned_date=day,
                last_maintenance_date=day + timedelta(days=45),
                next_maintenance_date=day + timedelta(days=135),
                remark=DEMO_REMARK,
            )
            self._count("logistics.AutomationDevice", True)
            self._stamp(device, created_at=self._aware(day, 9, 0))
            devices[code] = device

        warehouses = {
            "RAW": self._warehouse("XJ-WH-RAW-01"),
            "FG": self._warehouse("XJ-WH-FG-01"),
            "SP": self._warehouse("XJ-WH-SP-01"),
        }
        task_definitions = (
            ("XJ-LT-0001", "move", "RAW", "XJ-LG-AGV-01", "XJ-FAB-001", "180", "finished", 30, "XJ2010"),
            ("XJ-LT-0002", "transfer", "FG", "XJ-LG-SHUTTLE-01", "XJ-FAB-002", "60", "finished", 66, "XJ2006"),
            ("XJ-LT-0003", "picking", "FG", "XJ-LG-STACKER-01", "XJ-SP-001", "24", "finished", 92, "XJ2006"),
            ("XJ-LT-0004", "inbound", "FG", "XJ-LG-ROBOT-01", "XJ-SP-003", "120", "executing", 12, "XJ2006"),
            ("XJ-LT-0005", "outbound", "SP", "XJ-LG-AGV-02", "XJ-SP-004", "40", "dispatched", 3, "XJ2008"),
            ("XJ-LT-0006", "move", "RAW", "XJ-LG-AGV-02", "XJ-CS-001", "15", "pending", 1, "XJ2008"),
            ("XJ-LT-0007", "counting", "FG", "XJ-LG-SHUTTLE-01", "XJ-SP-002", "1", "cancelled", 48, "XJ2006"),
        )
        for index, (
            task_no, task_type, warehouse_key, device_code, material_code, quantity,
            outcome, days_ago, assignee_no,
        ) in enumerate(task_definitions):
            day = self.today - timedelta(days=days_ago)
            warehouse = warehouses[warehouse_key]
            task = LogisticsTask.objects.create(
                company=self.company,
                task_no=task_no,
                task_type=task_type,
                device=devices[device_code],
                priority="normal" if index % 3 else "high",
                status=LogisticsTaskStatus.PENDING,
                warehouse=warehouse,
                material=self.materials[material_code],
                quantity=Decimal(quantity),
                container_no=f"PLT-260{index + 1:02d}",
                requested_by=self.employees[assignee_no],
                planned_at=self._aware(day, 9, 0),
                remark=DEMO_REMARK,
            )
            self._count("logistics.LogisticsTask", True)
            self._stamp(task, created_at=self._aware(day - timedelta(days=1), 16, 0))
            logistics_services.log_operation(
                company_id=self.company.pk,
                action="create",
                task=task,
                operator=self.employees[assignee_no],
                detail=f"新建物流任务 {task_no}",
            )
            if outcome == "pending":
                continue
            logistics_services.dispatch_task(
                task,
                assignee=self.employees[assignee_no],
                device=devices[device_code],
                planned_at=self._aware(day, 9, 30),
            )
            if outcome == "cancelled":
                logistics_services.cancel_task(
                    task, reason="盘点计划调整，任务取消。", operator=self.employees[assignee_no]
                )
                continue
            if outcome == "dispatched":
                continue
            logistics_services.start_task(task, operator=self.employees[assignee_no])
            if outcome == "executing":
                logistics_services.set_device_status(
                    devices[device_code],
                    AutomationDeviceStatus.RUNNING,
                    operator=self.employees[assignee_no],
                    detail="执行搬运任务中",
                    battery_level=devices[device_code].battery_level,
                )
                continue
            logistics_services.finish_task(
                task,
                result=random.choice(
                    [
                        "按计划完成搬运，货物状态与数量核对一致。",
                        "完成移库，目标储位已扫码确认。",
                        "拣货完成，短装 0 件，交接单已签字。",
                    ]
                ),
                quantity=Decimal(quantity),
                operator=self.employees[assignee_no],
            )
            logistics_services.set_device_status(
                devices[device_code],
                AutomationDeviceStatus.IDLE,
                operator=self.employees[assignee_no],
                detail="任务完成返回待命位",
                battery_level=max(20, devices[device_code].battery_level - 12),
            )

    # -- 组织 --------------------------------------------------------------
    def _company(self) -> Company:
        return self._upsert(
            Company,
            {"code": COMPANY["code"]},
            {
                "name": COMPANY["name"],
                "short_name": COMPANY["short_name"],
                "address": COMPANY["address"],
                "contact_person": COMPANY["contact_person"],
                "contact_phone": COMPANY["contact_phone"],
                "is_active": True,
            },
        )

    def _departments(self) -> dict[str, Department]:
        result: dict[str, Department] = {}
        for code, name, parent_code, dept_type, sort_order in DEPARTMENTS:
            result[code] = self._upsert(
                Department,
                {"company": self.company, "code": code},
                {
                    "name": name,
                    "parent": result.get(parent_code) if parent_code else None,
                    "department_type": dept_type,
                    "sort_order": sort_order,
                    "is_active": True,
                },
            )
        return result

    def _factories(self) -> dict[str, Factory]:
        result: dict[str, Factory] = {}
        for code, name, address in FACTORIES:
            result[code] = self._upsert(
                Factory,
                {"company": self.company, "code": code},
                {"name": name, "address": address, "is_active": True},
            )
        return result

    def _workshops(self):
        workshops: dict[str, Workshop] = {}
        lines: dict[str, ProductionLine] = {}
        for factory_code, items in WORKSHOPS.items():
            factory = self.factories[factory_code]
            for code, name, wtype, sort_order, line_def in items:
                workshop_key = f"{factory_code}/{code}"
                workshops[workshop_key] = self._upsert(
                    Workshop,
                    {"factory": factory, "code": code},
                    {
                        "name": name,
                        "workshop_type": wtype,
                        "sort_order": sort_order,
                        "is_active": True,
                    },
                )
                line_code, line_name, line_type, capacity = line_def
                lines[f"{workshop_key}/{line_code}"] = self._upsert(
                    ProductionLine,
                    {"workshop": workshops[workshop_key], "code": line_code},
                    {
                        "name": line_name,
                        "line_type": line_type,
                        "daily_capacity": Decimal(capacity),
                        "is_active": True,
                    },
                )
        return workshops, lines

    def _stations(self) -> None:
        for line in self.lines.values():
            for code, name, process_name, sort_order in STATIONS:
                self._upsert(
                    Station,
                    {"line": line, "code": code},
                    {
                        "name": name,
                        "process_name": process_name,
                        "sort_order": sort_order,
                        "is_active": True,
                    },
                )

    def _shifts(self) -> dict[str, Shift]:
        result: dict[str, Shift] = {}
        for code, name, start, end, cross_day, break_minutes in SHIFTS:
            result[code] = self._upsert(
                Shift,
                {"company": self.company, "code": code},
                {
                    "name": name,
                    "start_time": time(int(start[:2]), int(start[3:])),
                    "end_time": time(int(end[:2]), int(end[3:])),
                    "cross_day": cross_day,
                    "break_minutes": break_minutes,
                    "is_active": True,
                },
            )
        return result

    def _employees(self) -> dict[str, Employee]:
        result: dict[str, Employee] = {}
        for no, name, gender, dept_code, factory_code, position, employment, hire in EMPLOYEES:
            result[no] = self._upsert(
                Employee,
                {"company": self.company, "employee_no": no},
                {
                    "name": name,
                    "gender": gender,
                    "department": self.departments[dept_code],
                    "factory": self.factories[factory_code],
                    "position": position,
                    "employment_type": employment,
                    "hire_date": date.fromisoformat(hire),
                    "status": "active",
                    "is_active": True,
                },
            )
        return result

    def _teams(self) -> None:
        definitions = (
            ("XJ-T-CUT-DAY", "裁剪白班班组", "F01/CUT", "DAY", "XJ2010", ("XJ2010", "XJ2009")),
            ("XJ-T-SEW1-DAY", "缝制一线白班班组", "F01/SEW", "DAY", "XJ2009", ("XJ2009", "XJ2011")),
            ("XJ-T-SEW2-DAY", "缝制二线白班班组", "F01/SEW2", "DAY", "XJ2002", ("XJ2011",)),
            ("XJ-T-FIN-DAY", "整烫包装白班班组", "F01/FIN", "DAY", "XJ2011", ("XJ2011", "XJ2013")),
            ("XJ-T-F02-DAY", "阿克苏车间白班班组", "F02/SEW", "DAY", "XJ2012", ("XJ2012", "XJ2013")),
        )
        for code, name, workshop_key, shift_code, leader_no, member_nos in definitions:
            team = self._upsert(
                Team,
                {"code": code},
                {
                    "workshop": self.workshops[workshop_key],
                    "shift": self.shifts[shift_code],
                    "name": name,
                    "leader": self.employees[leader_no],
                    "is_active": True,
                },
            )
            for no in member_nos:
                self._upsert(
                    TeamMember,
                    {"team": team, "employee": self.employees[no]},
                    {
                        "role_in_team": "组员" if no != leader_no else "班组长",
                        "start_date": DATA_START,
                        "is_active": True,
                    },
                )

    # -- 主数据 ----------------------------------------------------------
    def _uoms(self) -> dict[str, UoM]:
        result: dict[str, UoM] = {}
        for code, name, category, places in UOMS:
            result[code] = self._ensure(
                UoM,
                {"code": code},
                {
                    "name": name,
                    "category": category,
                    "decimal_places": places,
                    "is_active": True,
                    "remark": DEMO_REMARK,
                },
            )
        for from_code, to_code, factor in UOM_CONVERSIONS:
            self._ensure(
                UoMConversion,
                {"from_uom": result[from_code], "to_uom": result[to_code]},
                {"factor": Decimal(factor), "is_fixed": True, "is_active": True},
            )
        return result

    def _material_categories(self) -> dict[str, MaterialCategory]:
        result: dict[str, MaterialCategory] = {}
        for code, name, category_type, parent_code, sort_order in MATERIAL_CATEGORIES:
            result[code] = self._ensure(
                MaterialCategory,
                {"code": code},
                {
                    "name": name,
                    "category_type": category_type,
                    "parent": result.get(parent_code) if parent_code else None,
                    "sort_order": sort_order,
                    "is_active": True,
                    "remark": DEMO_REMARK,
                },
            )
        return result

    def _materials(self) -> dict[str, Material]:
        result: dict[str, Material] = {}
        for (
            code, name, category, spec, base_uom, batch, roll,
            safe_stock, purchase_price, reference_cost,
        ) in MATERIALS:
            result[code] = self._upsert(
                Material,
                {"company": self.company, "code": code},
                {
                    "name": name,
                    "category": self.categories[category],
                    "spec": spec,
                    "base_uom": self.uoms[base_uom],
                    "purchase_uom": self.uoms[base_uom],
                    "purchase_factor": Decimal("1"),
                    "sales_uom": self.uoms[base_uom],
                    "sales_factor": Decimal("1"),
                    "is_batch_managed": batch,
                    "is_roll_managed": roll,
                    "is_serial_managed": False,
                    "safe_stock": Decimal(safe_stock),
                    "purchase_price": Decimal(purchase_price),
                    "reference_cost": Decimal(reference_cost),
                    "brand": COMPANY["short_name"],
                    "season": "四季",
                    "year": "2026",
                    "series": "常规",
                    "is_active": True,
                },
            )
        return result

    def _fabric_profiles(self) -> None:
        for code, composition, width, gram, color_no, dye_lot, shrinkage in FABRIC_PROFILES:
            self._upsert(
                FabricProfile,
                {"material": self.materials[code]},
                {
                    "composition": composition,
                    "width_cm": Decimal(width),
                    "gram_weight": Decimal(gram),
                    "default_color_no": color_no,
                    "dye_lot_required": dye_lot,
                    "shrinkage_rate": Decimal(shrinkage),
                },
            )

    def _colors(self) -> dict[str, Color]:
        result: dict[str, Color] = {}
        for code, name, hex_code, sort_order in COLORS:
            result[code] = self._ensure(
                Color,
                {"code": code},
                {
                    "name": name,
                    "hex_code": hex_code,
                    "sort_order": sort_order,
                    "is_active": True,
                    "remark": DEMO_REMARK,
                },
            )
        return result

    def _sizes(self) -> dict[str, Size]:
        result: dict[str, Size] = {}
        for code, name, group, sort_order in SIZES:
            result[code] = self._ensure(
                Size,
                {"code": code},
                {
                    "name": name,
                    "size_group": group,
                    "sort_order": sort_order,
                    "is_active": True,
                    "remark": DEMO_REMARK,
                },
            )
        return result

    def _styles(self) -> dict[str, Style]:
        result: dict[str, Style] = {}
        for code, name, size_group, brand, season, year, series in STYLES:
            result[code] = self._upsert(
                Style,
                {"company": self.company, "code": code},
                {
                    "name": name,
                    "category": self.categories["FG"],
                    "size_group": size_group,
                    "brand": brand,
                    "season": season,
                    "year": year,
                    "series": series,
                    "description": f"{name}（{series}）",
                    "is_active": True,
                },
            )
        return result

    def _skus(self) -> None:
        """按「款式 + 颜色 + 尺码」生成 SKU 与并一对一的成品物料。"""
        counter = 260000
        self.sku_map = {}
        for style_code, (color_codes, size_codes) in STYLE_SKUS.items():
            style = self.styles[style_code]
            for color_code in color_codes:
                color = self.colors[color_code]
                for size_code in size_codes:
                    size = self.sizes[size_code]
                    counter += 1
                    sku_code = f"{style.code}-{color.code}-{size.code}"
                    material = self._upsert(
                        Material,
                        {"company": self.company, "code": f"FG-{sku_code}"},
                        {
                            "name": f"{style.name} {color.name} {size.name}",
                            "category": self.categories["FG"],
                            "spec": f"{style.name} / {color.name} / {size.name}",
                            "base_uom": self.uoms["PC"],
                            "purchase_uom": self.uoms["PC"],
                            "purchase_factor": Decimal("1"),
                            "sales_uom": self.uoms["PC"],
                            "sales_factor": Decimal("1"),
                            "is_batch_managed": True,
                            "is_roll_managed": False,
                            "is_serial_managed": False,
                            "safe_stock": Decimal("0"),
                            "purchase_price": Decimal("0"),
                            "reference_cost": Decimal("0"),
                            "brand": style.brand,
                            "season": style.season,
                            "year": style.year,
                            "series": style.series,
                            "is_active": True,
                        },
                    )
                    barcode = f"69{counter:011d}"
                    sku = self._upsert(
                        Sku,
                        {"company": self.company, "style": style, "color": color, "size": size},
                        {
                            "code": sku_code,
                            "material": material,
                            "barcode": barcode,
                            "is_active": True,
                        },
                    )
                    self.sku_map[sku_code] = sku
                    self._upsert(
                        Identifier,
                        {"identifier_type": IdentifierType.SKU_BARCODE, "value": barcode},
                        {
                            "sku": sku,
                            "material": material,
                            "extra": {"来源": "seed_demo_xjys"},
                            "is_active": True,
                        },
                    )

    # -- 仓库 / 库区 / 储位 ----------------------------------------------
    def _warehouses(self) -> None:
        for code, name, wtype, factory_code, dept_code, allow_negative in WAREHOUSES:
            factory = self.factories[factory_code]
            warehouse = self._upsert(
                Warehouse,
                {"company": self.company, "code": code},
                {
                    "name": name,
                    "warehouse_type": wtype,
                    "factory": factory,
                    "department": self.departments[dept_code],
                    "address": factory.address,
                    "manager_name": "周梅",
                    "allow_negative_stock": allow_negative,
                    "is_active": True,
                },
            )
            for zone_code, zone_name, zone_type, sort_order in ZONES:
                zone = self._upsert(
                    Zone,
                    {"warehouse": warehouse, "code": zone_code},
                    {
                        "name": zone_name,
                        "zone_type": zone_type,
                        "allow_mixed_batch": zone_type != ZoneType.STORAGE,
                        "sort_order": sort_order,
                        "is_active": True,
                    },
                )
                rows, columns, levels = ZONE_LOCATION_GRID[zone_code]
                for row in range(1, rows + 1):
                    for column in range(1, columns + 1):
                        for level in range(1, levels + 1):
                            self._upsert(
                                Location,
                                {"zone": zone, "code": f"A{row:02d}-{column:02d}-{level:02d}"},
                                {
                                    "name": f"{zone_name}{row}排{column}列{level}层",
                                    "location_type": (
                                        LocationType.SHELF
                                        if zone_type == ZoneType.STORAGE
                                        else LocationType.FLOOR
                                    ),
                                    "row_no": f"A{row:02d}",
                                    "column_no": f"{column:02d}",
                                    "level_no": f"{level:02d}",
                                    "capacity": Decimal("1000"),
                                    "is_locked": False,
                                    "is_active": True,
                                },
                            )

    # -- 客户与供应商 ------------------------------------------------------
    def _customers(self) -> dict[str, Customer]:
        result: dict[str, Customer] = {}
        for item in CUSTOMERS:
            customer = self._upsert(
                Customer,
                {"company": self.company, "code": item["code"]},
                {
                    "name": item["name"],
                    "short_name": item.get("short_name", ""),
                    "category": item.get("category", "direct"),
                    "level": item.get("level", "C"),
                    "status": item.get("status", "active"),
                    "credit_limit": Decimal(item.get("credit_limit", "0")),
                    "payment_terms": item.get("payment_terms", ""),
                    "tax_no": item.get("tax_no", ""),
                    "address": item.get("address", ""),
                    "primary_contact_name": item.get("primary_contact_name", ""),
                    "primary_contact_phone": item.get("primary_contact_phone", ""),
                    "salesman": self.employees.get(item.get("salesman_no", "")),
                    "is_active": True,
                },
            )
            for contact in item.get("contacts", ()):
                self._upsert(
                    CustomerContact,
                    {"customer": customer, "name": contact["name"]},
                    {
                        "position": contact.get("position", ""),
                        "phone": contact.get("phone", ""),
                        "email": contact.get("email", ""),
                        "is_primary": bool(contact.get("is_primary")),
                        "is_active": True,
                    },
                )
            result[item["code"]] = customer
        return result

    def _suppliers(self) -> dict[str, Supplier]:
        result: dict[str, Supplier] = {}
        for item in SUPPLIERS:
            supplier = self._upsert(
                Supplier,
                {"company": self.company, "code": item["code"]},
                {
                    "name": item["name"],
                    "short_name": item.get("short_name", ""),
                    "category": item.get("category", "other"),
                    "grade": item.get("grade", "C"),
                    "admission_status": item.get("admission_status", "pending"),
                    "payment_terms": item.get("payment_terms", ""),
                    "tax_no": item.get("tax_no", ""),
                    "address": item.get("address", ""),
                    "primary_contact_name": item.get("primary_contact_name", ""),
                    "primary_contact_phone": item.get("primary_contact_phone", ""),
                    "buyer": self.employees.get(item.get("buyer_no", "")),
                    "is_active": True,
                },
            )
            for contact in item.get("contacts", ()):
                self._upsert(
                    SupplierContact,
                    {"supplier": supplier, "name": contact["name"]},
                    {
                        "position": contact.get("position", ""),
                        "phone": contact.get("phone", ""),
                        "email": contact.get("email", ""),
                        "is_primary": bool(contact.get("is_primary")),
                        "is_active": True,
                    },
                )
            for qualification in item.get("qualifications", ()):
                key = {
                    "supplier": supplier,
                    "qualification_type": qualification["qualification_type"],
                    "certificate_no": qualification.get("certificate_no", ""),
                }
                self._upsert(
                    SupplierQualification,
                    key,
                    {
                        "issued_by": qualification.get("issued_by", ""),
                        "issued_date": (
                            date.fromisoformat(qualification["issued_date"])
                            if qualification.get("issued_date")
                            else None
                        ),
                        "expiry_date": (
                            date.fromisoformat(qualification["expiry_date"])
                            if qualification.get("expiry_date")
                            else None
                        ),
                        "is_active": True,
                    },
                )
            result[item["code"]] = supplier
        return result

    def _approval_templates(self) -> None:
        for definition in XJ_APPROVAL_TEMPLATES:
            template = self._upsert(
                ApprovalTemplate,
                {"code": definition["code"]},
                {
                    "name": definition["name"],
                    "biz_type": definition["biz_type"],
                    "company": self.company,
                    "allow_self_approval": False,
                    "description": definition["description"],
                    "is_active": True,
                },
            )
            for node in definition["nodes"]:
                role = Role.objects.filter(code=node["role"]).first()
                if role is None:
                    raise CommandError(
                        f"审批模板 {definition['code']} 引用了不存在的角色 {node['role']}；请先执行 seed_demo。"
                    )
                self._upsert(
                    ApprovalTemplateNode,
                    {"template": template, "seq": node["seq"]},
                    {
                        "name": node["name"],
                        "approver_type": ApproverType.ROLE,
                        "approver_role": role,
                        "approver_user": None,
                        "amount_min": Decimal(node["amount_min"]) if node["amount_min"] else None,
                        "amount_max": None,
                        "department_ids": [],
                        "is_active": True,
                    },
                )

# ---------------------------------------------------------------------------
# 设备管理（设备台账 / 保养 / 维修 / 点巡检 / 异常）
# ---------------------------------------------------------------------------

# code, name, category, is_special, maintenance_cycle_days
EQUIPMENT_TYPES = (
    ("XJ-EQ-SEW", "缝制设备", "production", False, 30),
    ("XJ-EQ-CUT", "裁剪设备", "production", False, 30),
    ("XJ-EQ-IRON", "整烫设备", "production", False, 30),
    ("XJ-EQ-AIR", "空压与气源设备", "utility", True, 30),
    ("XJ-EQ-BOILER", "锅炉（特种）", "utility", True, 15),
    ("XJ-EQ-PRESSURE", "压力容器（特种）", "utility", True, 30),
    ("XJ-EQ-ELEC", "电气与配电设备", "utility", False, 90),
    ("XJ-EQ-PV", "光伏发电设备", "utility", False, 180),
    ("XJ-EQ-TEST", "检测设备", "inspection", False, 90),
    ("XJ-EQ-AGV", "物流设备", "logistics", False, 60),
)

# code, name, type_code, status, factory, workshop_key, line_key, location, brand, model, serial,
# purchase_date, start_date, original_value, warranty_until, dept, owner_employee_no
EQUIPMENTS = (
    ("XJ-EQ-CUT-01", "一号智能裁床", "XJ-EQ-CUT", "in_use", "F01", "F01/CUT", "F01/CUT/CL01",
     "裁剪车间 A1 区", "拓卡奔马", "TK-2007", "CN26-0001",
     "2025-12-05", "2026-01-01", "486000", "2028-12-04", "PROD", "XJ2010"),
    ("XJ-EQ-CUT-02", "二号智能裁床", "XJ-EQ-CUT", "in_use", "F01", "F01/CUT", "F01/CUT/CL01",
     "裁剪车间 A2 区", "拓卡奔马", "TK-2007", "CN26-0002",
     "2025-12-05", "2026-01-01", "486000", "2028-12-04", "PROD", "XJ2010"),
    ("XJ-EQ-SEW-01", "电脑平缝机 01", "XJ-EQ-SEW", "in_use", "F01", "F01/SEW", "F01/SEW/SL01",
     "缝制一车间 1 工位", "兄弟", "S-7200C", "CN26-0101",
     "2025-12-10", "2026-01-01", "12800", "2027-12-09", "PROD", "XJ2009"),
    ("XJ-EQ-SEW-02", "电脑平缝机 02", "XJ-EQ-SEW", "in_use", "F01", "F01/SEW", "F01/SEW/SL01",
     "缝制一车间 2 工位", "兄弟", "S-7200C", "CN26-0102",
     "2025-12-10", "2026-01-01", "12800", "2027-12-09", "PROD", "XJ2009"),
    ("XJ-EQ-SEW-03", "电脑平缝机 03", "XJ-EQ-SEW", "in_use", "F01", "F01/SEW", "F01/SEW/SL01",
     "缝制一车间 3 工位", "兄弟", "S-7200C", "CN26-0103",
     "2025-12-10", "2026-01-01", "12800", "2027-12-09", "PROD", "XJ2009"),
    ("XJ-EQ-SEW-04", "电脑平缝机 04", "XJ-EQ-SEW", "repairing", "F01", "F01/SEW", "F01/SEW/SL01",
     "缝制一车间 4 工位", "兄弟", "S-7200C", "CN26-0104",
     "2025-12-10", "2026-01-01", "12800", "2027-12-09", "PROD", "XJ2009"),
    ("XJ-EQ-SEW-05", "电脑平缝机 05", "XJ-EQ-SEW", "in_use", "F01", "F01/SEW2", "F01/SEW2/SL02",
     "缝制二车间 1 工位", "兄弟", "S-7200C", "CN26-0105",
     "2025-12-10", "2026-01-01", "12800", "2027-12-09", "PROD", "XJ2011"),
    ("XJ-EQ-SEW-06", "电脑平缝机 06", "XJ-EQ-SEW", "in_use", "F01", "F01/SEW2", "F01/SEW2/SL02",
     "缝制二车间 2 工位", "兄弟", "S-7200C", "CN26-0106",
     "2025-12-10", "2026-01-01", "12800", "2027-12-09", "PROD", "XJ2011"),
    ("XJ-EQ-OVL-01", "包缝机 01", "XJ-EQ-SEW", "in_use", "F01", "F01/SEW", "F01/SEW/SL01",
     "缝制一车间 包缝工位", "兄弟", "MO-6714S", "CN26-0201",
     "2025-12-10", "2026-01-01", "18600", "2027-12-09", "PROD", "XJ2009"),
    ("XJ-EQ-OVL-02", "包缝机 02", "XJ-EQ-SEW", "idle", "F01", "F01/SEW2", "F01/SEW2/SL02",
     "缝制二车间 备用", "兄弟", "MO-6714S", "CN26-0202",
     "2025-12-10", "2026-01-01", "18600", "2027-12-09", "PROD", "XJ2011"),
    ("XJ-EQ-BTN-01", "锁眼钉扣机", "XJ-EQ-SEW", "in_use", "F01", "F01/SEW", "F01/SEW/SL01",
     "缝制一车间 专机工位", "兄弟", "LBH-1790", "CN26-0301",
     "2025-12-12", "2026-01-01", "56000", "2027-12-11", "PROD", "XJ2009"),
    ("XJ-EQ-IRON-01", "一号蒸汽整烫机", "XJ-EQ-IRON", "in_use", "F01", "F01/FIN", "F01/FIN/FL01",
     "整烫包装车间 整烫区", "三美", "SM-2026", "CN26-0401",
     "2025-12-15", "2026-01-01", "36800", "2027-12-14", "PROD", "XJ2011"),
    ("XJ-EQ-IRON-02", "二号蒸汽整烫机", "XJ-EQ-IRON", "in_use", "F01", "F01/FIN", "F01/FIN/FL01",
     "整烫包装车间 整烫区", "三美", "SM-2026", "CN26-0402",
     "2025-12-15", "2026-01-01", "36800", "2027-12-14", "PROD", "XJ2011"),
    ("XJ-EQ-AIR-01", "螺杆空压机 01", "XJ-EQ-AIR", "in_use", "F01", "F01/PWR", "F01/PWR/PL01",
     "动力车间 空压站", "阿特拉斯", "GA-37", "CN26-0501",
     "2025-12-18", "2026-01-01", "268000", "2028-12-17", "EAM", "XJ2019"),
    ("XJ-EQ-AIR-02", "螺杆空压机 02（备用）", "XJ-EQ-AIR", "idle", "F01", "F01/PWR", "F01/PWR/PL01",
     "动力车间 空压站", "阿特拉斯", "GA-37", "CN26-0502",
     "2025-12-18", "2026-01-01", "268000", "2028-12-17", "EAM", "XJ2019"),
    ("XJ-EQ-PRES-01", "储气罐（压力容器）", "XJ-EQ-PRESSURE", "in_use", "F01", "F01/PWR", "F01/PWR/PL01",
     "动力车间 空压站", "新疆丝路机电", "C-3.0/0.8", "XJPR-2026-01",
     "2025-12-18", "2026-01-01", "46000", "2031-12-17", "EAM", "XJ2019"),
    ("XJ-EQ-BOILER-01", "燃气蒸汽锅炉", "XJ-EQ-BOILER", "in_use", "F01", "F01/PWR", "F01/PWR/PL01",
     "动力车间 锅炉房", "新疆丝路机电", "WNS2-1.25", "XJBL-2026-01",
     "2025-12-20", "2026-01-05", "680000", "2028-12-19", "EAM", "XJ2019"),
    ("XJ-EQ-ELEC-01", "箱式变压器", "XJ-EQ-ELEC", "in_use", "F01", "F01/PWR", "F01/PWR/PL01",
     "动力车间 变配电室", "特变电气", "S13-M-1250", "XJTR-2026-01",
     "2025-12-20", "2026-01-05", "420000", "2028-12-19", "EAM", "XJ2017"),
    ("XJ-EQ-PV-01", "分布式光伏并网柜", "XJ-EQ-PV", "in_use", "F01", "F01/PWR", "F01/PWR/PL01",
     "厂区屋面光伏区", "华为", "SUN2000-100KTL", "XJPV-2026-01",
     "2025-12-28", "2026-01-10", "1026000", "2031-12-27", "ENERGY", "XJ2017"),
    ("XJ-EQ-TEST-01", "织物强力试验机", "XJ-EQ-TEST", "in_use", "F01", "F01/FIN", "F01/FIN/FL01",
     "质量室", "莱州市万测", "HD-B609B", "XJTS-2026-01",
     "2025-12-22", "2026-01-06", "76000", "2028-12-21", "QC", "XJ2007"),
    ("XJ-EQ-AGV-01", "AGV 搬运机器人 01", "XJ-EQ-AGV", "in_use", "F01", "F01/FIN", "F01/FIN/FL01",
     "成品仓自动化区", "海康机器人", "Q7-1500", "XJAGV-2026-01",
     "2026-01-15", "2026-02-01", "230000", "2029-01-14", "WH", "XJ2006"),
    ("XJ-EQ-AGV-02", "AGV 搬运机器人 02", "XJ-EQ-AGV", "repairing", "F01", "F01/FIN", "F01/FIN/FL01",
     "成品仓自动化区", "海康机器人", "Q7-1500", "XJAGV-2026-02",
     "2026-01-15", "2026-02-01", "230000", "2029-01-14", "WH", "XJ2006"),
)

# code, name, part_type, spec, material_code or None, equipment_type_code or None, safety_stock,
# reference_price, life_days, supplier_code
SPARE_PARTS = (
    ("XJ-SP-001", "缝纫机压脚", "wear", "DB 标准压脚", "XJ-SP-001", "XJ-EQ-SEW",
     "150", "18.000000", 180, "XJ-SUP-003"),
    ("XJ-SP-002", "伺服电机碳刷", "electric", "6x12x16mm", "XJ-SP-002", "XJ-EQ-SEW",
     "300", "4.500000", 365, "XJ-SUP-003"),
    ("XJ-SP-003", "缝纫机针", "wear", "DBx1 14#", "XJ-SP-003", "XJ-EQ-SEW",
     "8000", "0.350000", 30, "XJ-SUP-003"),
    ("XJ-SP-004", "空压机空气滤芯", "consumable", "卡特式 120mm", "XJ-SP-004", "XJ-EQ-AIR",
     "60", "86.000000", 180, "XJ-SUP-003"),
    ("XJ-SP-005", "深沟球轴承 6204", "mechanical", "6204-2RS", "XJ-SP-005", None,
     "120", "12.500000", 730, "XJ-SUP-003"),
    ("XJ-SP-006", "锅炉燃烧器喷嘴", "wear", "燃气型 G1/2", None, "XJ-EQ-BOILER",
     "20", "320.000000", 365, "XJ-SUP-005"),
    ("XJ-SP-007", "整烫机密封圈", "wear", "耐高温硅胶 260mm", None, "XJ-EQ-IRON",
     "80", "24.000000", 180, "XJ-SUP-003"),
    ("XJ-SP-008", "裁床刀片", "wear", "四面刀 8mm", None, "XJ-EQ-CUT",
     "40", "180.000000", 120, "XJ-SUP-003"),
)

# equipment_code, name, part_type, spec, quantity, uom_code, position, life_days
EQUIPMENT_PARTS = (
    ("XJ-EQ-CUT-01", "四面刀片", "wear", "8mm", "4", "PCS", "刀头", 120),
    ("XJ-EQ-CUT-01", "导向轴承", "mechanical", "LM20UU", "8", "PCS", "导轨", 730),
    ("XJ-EQ-CUT-02", "四面刀片", "wear", "8mm", "4", "PCS", "刀头", 120),
    ("XJ-EQ-SEW-01", "压脚", "wear", "DB 标准", "1", "PCS", "机头", 180),
    ("XJ-EQ-SEW-01", "伺服电机", "electric", "550W", "1", "SET", "机体", 3650),
    ("XJ-EQ-SEW-02", "压脚", "wear", "DB 标准", "1", "PCS", "机头", 180),
    ("XJ-EQ-SEW-04", "旋梭", "mechanical", "H-7", "1", "PCS", "机头", 365),
    ("XJ-EQ-OVL-01", "弯针", "wear", "MO 6714S", "2", "PCS", "机头", 120),
    ("XJ-EQ-BTN-01", "打扣冲头", "wear", "φ18mm", "2", "PCS", "冲头", 240),
    ("XJ-EQ-IRON-01", "密封圈", "wear", "260mm", "2", "PCS", "汽缸", 180),
    ("XJ-EQ-IRON-02", "密封圈", "wear", "260mm", "2", "PCS", "汽缸", 180),
    ("XJ-EQ-AIR-01", "空气滤芯", "consumable", "120mm", "2", "PCS", "进气口", 180),
    ("XJ-EQ-AIR-01", "伺服碳刷", "electric", "6x12x16", "4", "PCS", "电机", 365),
    ("XJ-EQ-BOILER-01", "燃烧器喷嘴", "wear", "G1/2", "1", "PCS", "燃烧器", 365),
    ("XJ-EQ-PRES-01", "安全阀", "standard", "A28H-16C", "1", "PCS", "罐顶", 730),
    ("XJ-EQ-AGV-01", "行走驱动轮", "wear", "φ150mm", "2", "PCS", "底盘", 365),
    ("XJ-EQ-AGV-02", "行走驱动轮", "wear", "φ150mm", "2", "PCS", "底盘", 365),
    ("XJ-EQ-TEST-01", "传感器模组", "electric", "5000N", "1", "PCS", "传感器", 730),
)

# code, name, category, equipment_type_code or None, cycle_days, standard
MAINTENANCE_ITEMS = (
    ("XJ-MI-001", "清洁与润滑", "daily", None, 30,
     "清理工作面油污，按说明书补充专用润滑油，油位在量窗中位区间。"),
    ("XJ-MI-002", "电气系统检查", "level1", None, 30,
     "检查电源线、插头、接地与空开上下游器件，无烧焦、无松动。"),
    ("XJ-MI-003", "安全装置检查", "daily", None, 15,
     "护罩、急停、光电保护齐全有效，动作可靠。"),
    ("XJ-MI-004", "精度校准", "precision", "XJ-EQ-CUT", 90,
     "按校准规程校验定位精度，偏差≤±0.2mm。"),
    ("XJ-MI-005", "传动皮带检查与张紧", "level1", "XJ-EQ-SEW", 60,
     "皮带无裂纹，按压下量 10~15mm 为张紧合适。"),
    ("XJ-MI-006", "空气滤芯更换", "level2", "XJ-EQ-AIR", 180,
     "更换空气滤芯与油气分离芯，记录压差。"),
    ("XJ-MI-007", "压力表校验", "level2", "XJ-EQ-BOILER", 180,
     "压力表送法定校验机构校验，校验证书留档。"),
    ("XJ-MI-008", "燃烧器与烟道清扫", "level2", "XJ-EQ-BOILER", 90,
     "清扫燃烧器喷嘴与烟管，检查烟气含氧量。"),
    ("XJ-MI-009", "光伏组件清洁", "daily", "XJ-EQ-PV", 30,
     "清洁组件表面积沙，检查汇流箱温升与组件热斑。"),
    ("XJ-MI-010", "尺寸精度校验", "precision", "XJ-EQ-TEST", 180,
     "用标准测力计校验，示值误差≤±1%。"),
)

# storage_key, name, equipment_code, cycle_days, items, responsible_employee_no, dept
MAINTENANCE_PLANS = (
    ("cut01", "一号裁床季度保养", "XJ-EQ-CUT-01", 30, ("XJ-MI-001", "XJ-MI-003", "XJ-MI-004"), "XJ2010", "PROD"),
    ("sew01", "一号缝纫机月保", "XJ-EQ-SEW-01", 30, ("XJ-MI-001", "XJ-MI-002", "XJ-MI-005"), "XJ2009", "PROD"),
    ("sew04", "四号缝纫机月保", "XJ-EQ-SEW-04", 30, ("XJ-MI-001", "XJ-MI-005"), "XJ2009", "PROD"),
    ("iron01", "一号整烫机月保", "XJ-EQ-IRON-01", 30, ("XJ-MI-001", "XJ-MI-003"), "XJ2011", "PROD"),
    ("air01", "空压站季度保养", "XJ-EQ-AIR-01", 90, ("XJ-MI-001", "XJ-MI-006"), "XJ2019", "EAM"),
    ("boiler01", "锅炉月检保养", "XJ-EQ-BOILER-01", 30, ("XJ-MI-003", "XJ-MI-007", "XJ-MI-008"), "XJ2019", "EAM"),
    ("pv01", "光伏组件月度清洁", "XJ-EQ-PV-01", 30, ("XJ-MI-009",), "XJ2017", "ENERGY"),
    ("test01", "强力试验机半年校验", "XJ-EQ-TEST-01", 180, ("XJ-MI-010",), "XJ2007", "QC"),
)

# code, name, method, standard, uom_code or None, lower, upper
INSPECTION_ITEMS = (
    ("XJ-II-001", "设备运行温度", "measure", "轴承与电机外壳温度不高于 70℃", "PCS", "0", "70"),
    ("XJ-II-002", "设备运行振动", "measure", "振动速度有效值不高于 4.5mm/s", "PCS", "0", "4.5"),
    ("XJ-II-003", "润滑油油位", "visual", "油位在量窗上下限之间", None, None, None),
    ("XJ-II-004", "空压系统压力", "measure", "工作压力 0.6~0.8MPa", "PCS", "0.6", "0.8"),
    ("XJ-II-005", "主电机运行电流", "measure", "不超过额定电流 110%", "PCS", "0", "15"),
    ("XJ-II-006", "异响与异常振动", "audio", "无金属摩擦声、无周期性异响", None, None, None),
    ("XJ-II-007", "泄漏检查", "visual", "气路、油路、水路无渗漏", None, None, None),
    ("XJ-II-008", "安全护罩与急停", "visual", "护罩齐全，急停按钮动作可靠", None, None, None),
    ("XJ-II-009", "蒸汽压力", "measure", "工作压力 0.4~0.6MPa", "PCS", "0.4", "0.6"),
    ("XJ-II-010", "锅炉烟气含氧量", "measure", "含氧量不高于 6%", "PCS", "0", "6"),
)

# code, name, level
ABNORMAL_TYPES = (
    ("XJ-AT-001", "温升异常", "medium"),
    ("XJ-AT-002", "振动异常", "medium"),
    ("XJ-AT-003", "电气异常", "high"),
    ("XJ-AT-004", "泄漏与气压异常", "high"),
    ("XJ-AT-005", "安全防护缺失", "critical"),
    ("XJ-AT-006", "异响与异常振动", "low"),
)
