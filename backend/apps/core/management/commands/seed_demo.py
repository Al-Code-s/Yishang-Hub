"""开发演示数据初始化。

安全约束：
* 生产环境（DJANGO_ENV=production）直接拒绝执行；
* 演示账号口令不写死在代码里：优先 YISHANG_DEMO_PASSWORD，其次随机生成并打印一次；
* 所有对象均带 remark="演示数据"，与真实业务数据明显区分；
* 幂等：重复执行只同步固定的演示字段，不产生重复记录，也不会重置已有账号口令。

范围：仅已落地的实体——阶段 0/1 的组织、工厂、员工、物料、款式、颜色、尺码、SKU、
仓库库区储位、审批模板、演示账号、阶段 2 第一步的客户与供应商主数据，以及
阶段 2 的库存演示单据（收货、质量放行、生产领料、移库、盘点差异）。

库存余额与流水**不直接写入**：全部通过统一库存服务
（`apps/wms/services/stock.py`）过账生成，演示数据与真实业务走同一条路径。
采购订单、销售订单、工单等单据属阶段 2 后续增量，在对应业务服务落地前不在此伪造。
"""

from __future__ import annotations

import secrets
import string
from datetime import date, time, timedelta
from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.crm.models import Customer, CustomerContact
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
from apps.srm.models import Supplier, SupplierContact, SupplierQualification
from apps.wms.models import Location, LocationType, Warehouse, Zone, ZoneType
from apps.workflow.models import ApprovalTemplate, ApprovalTemplateNode, ApproverType

DEMO_REMARK = "演示数据"

COMPANY = {"code": "YS", "name": "意尚智造服饰有限公司", "short_name": "意尚智造服饰"}

UOMS = (
    ("PCS", "个", "quantity", 0),
    ("PC", "件", "quantity", 0),
    ("SET", "套", "quantity", 0),
    ("DZ", "打", "quantity", 0),
    ("M", "米", "length", 2),
    ("YD", "码", "length", 2),
    ("KG", "公斤", "weight", 3),
    ("T", "吨", "weight", 3),
    ("M2", "平方米", "area", 2),
    ("ROLL", "卷", "quantity", 0),
    ("CTN", "箱", "quantity", 0),
    ("UNIT", "台", "quantity", 0),
    ("L", "升", "volume", 2),
    ("KWH", "千瓦时", "quantity", 2),
)

# 只登记与批次/卷无关的固定换算；米↔公斤随卷变化，不在此登记
UOM_CONVERSIONS = (
    ("DZ", "PCS", "12"),
    ("YD", "M", "0.9144"),
    ("T", "KG", "1000"),
)

DEPARTMENTS = (
    ("GM", "总经理办公室", None, "management", 10),
    ("PROD", "生产部", None, "production", 20),
    ("PLAN", "计划科", "PROD", "production", 21),
    ("TECH", "技术科", "PROD", "production", 22),
    ("PUR", "采购部", None, "procurement", 30),
    ("SALES", "销售部", None, "sales", 40),
    ("WH", "仓储部", None, "warehouse", 50),
    ("QC", "质量部", None, "quality", 60),
    ("EAM", "设备部", None, "equipment", 70),
    ("IT", "信息部", None, "management", 80),
    ("HR", "人力资源部", None, "management", 90),
    ("FIN", "财务部", None, "management", 100),
    ("EHS", "安全环保部", None, "management", 110),
)

FACTORIES = (
    ("F01", "意尚智造一号工厂", "浙江省杭州市余杭区仁和街道"),
    ("F02", "意尚智造二号工厂", "浙江省湖州市吴兴区织里镇"),
)

WORKSHOPS = {
    "F01": (
        ("CUT", "裁剪车间", "cutting", 10, ("CL01", "一号裁剪线", "manual", "800")),
        ("SEW", "缝制车间", "sewing", 20, ("SL01", "一号缝制线", "manual", "1200")),
        ("SEW2", "缝制二车间", "sewing", 30, ("SL02", "二号缝制线", "manual", "1000")),
        ("FIN", "整烫包装车间", "finishing", 40, ("FL01", "一号整烫线", "manual", "1500")),
    ),
    "F02": (
        ("SEW", "缝制车间", "sewing", 10, ("SL01", "一号缝制线", "manual", "900")),
        ("FIN", "整烫包装车间", "finishing", 20, ("FL01", "一号整烫线", "manual", "1100")),
    ),
}

STATIONS = (
    ("CUT-01", "裁剪", "裁剪", 10),
    ("CUT-02", "验片", "裁剪", 20),
    ("SEW-01", "缝制", "缝制", 10),
    ("SEW-02", "锁眼钉扣", "缝制", 20),
    ("SEW-03", "专机", "缝制", 30),
    ("FIN-01", "整烫", "整烫", 10),
    ("FIN-02", "检验", "检验", 20),
    ("FIN-03", "包装", "包装", 30),
)

SHIFTS = (
    ("DAY", "白班", "08:00", "17:00", False, 60),
    ("MID", "中班", "16:00", "00:00", False, 45),
    ("NIGHT", "夜班", "22:00", "06:00", True, 45),
)

EMPLOYEES = (
    ("E1001", "陈立", "male", "GM", "F01", "总经理", "full_time", "2016-03-01"),
    ("E1002", "王慧", "female", "PROD", "F01", "生产经理", "full_time", "2017-06-12"),
    ("E1003", "李文强", "male", "PLAN", "F01", "计划主管", "full_time", "2018-09-03"),
    ("E1004", "赵敏", "female", "PUR", "F01", "采购主管", "full_time", "2018-04-16"),
    ("E1005", "孙磊", "male", "SALES", "F01", "销售主管", "full_time", "2019-02-25"),
    ("E1006", "周丽", "female", "WH", "F01", "仓储主管", "full_time", "2017-11-06"),
    ("E1007", "吴刚", "male", "QC", "F01", "质量工程师", "full_time", "2019-07-15"),
    ("E1008", "郑涛", "male", "EAM", "F01", "设备维修工", "full_time", "2020-05-18"),
    ("E1009", "冯雪", "female", "PROD", "F01", "缝纫工", "full_time", "2021-03-22"),
    ("E1010", "许静", "female", "PROD", "F01", "裁剪工", "full_time", "2021-08-09"),
    ("E1011", "何俊", "male", "PROD", "F01", "整烫工", "full_time", "2020-10-12"),
    ("E1012", "马超", "male", "PROD", "F02", "缝纫工", "full_time", "2022-04-01"),
    ("E1013", "朱婷", "female", "QC", "F02", "质检员", "full_time", "2022-06-20"),
    ("E1014", "范伟", "male", "IT", "F01", "信息化专员", "full_time", "2021-01-11"),
    ("E1015", "钱进", "male", "PUR", "F01", "采购专员", "full_time", "2021-05-10"),
)
MATERIAL_CATEGORIES = (
    ("FB", "面料", "fabric", None, 10),
    ("FB-KNIT", "针织面料", "fabric", "FB", 11),
    ("FB-WOVEN", "梭织面料", "fabric", "FB", 12),
    ("AC", "辅料", "accessory", None, 20),
    ("AC-THREAD", "缝纫线", "accessory", "AC", 21),
    ("AC-BTN", "纽扣", "accessory", "AC", 22),
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
    ("FAB-001", "精梳棉汗布", "FB-KNIT", "32S 180g/m2 幅宽185cm", "KG",
     True, True, "500", "42.500000", "43.000000"),
    ("FAB-002", "涤纶四面弹", "FB-WOVEN", "75D 210g/m2 幅宽150cm", "KG",
     True, True, "300", "28.000000", "28.500000"),
    ("FAB-003", "棉涤卫衣布", "FB-KNIT", "32S+150D 320g/m2 幅宽180cm", "KG",
     True, True, "400", "36.800000", "37.500000"),
    ("ACC-001", "涤纶缝纫线", "AC-THREAD", "40S/2 5000m 卷装", "ROLL",
     True, False, "200", "8.600000", "9.000000"),
    ("ACC-002", "树脂纽扣", "AC-BTN", "18L 四孔 黑色", "PCS",
     True, False, "20000", "0.120000", "0.130000"),
    ("ACC-003", "尼龙拉链", "AC-ZIP", "3# 60cm 闭尾", "PCS",
     True, False, "8000", "1.350000", "1.400000"),
    ("ACC-004", "棉涤罗纹", "AC-TAPE", "2x1 罗纹 幅宽60cm", "KG",
     True, False, "150", "32.000000", "33.000000"),
    ("ACC-005", "主唛织标", "AC-LABEL", "30x60mm 缎面", "PCS",
     True, False, "30000", "0.180000", "0.200000"),
    ("PKG-001", "三层瓦楞纸箱", "PKG", "600x400x300mm", "CTN",
     False, False, "2000", "6.200000", "6.500000"),
    ("PKG-002", "吊牌", "PKG", "90x50mm 铜版纸", "PCS",
     True, False, "40000", "0.250000", "0.270000"),
    ("PKG-003", "PE 透明胶袋", "PKG", "350x450mm 0.03mm", "PCS",
     False, False, "50000", "0.090000", "0.100000"),
    ("SP-001", "缝纫机压脚", "SP-SEW", "DB 标准压脚", "PCS",
     False, False, "100", "18.000000", "19.000000"),
    ("SP-002", "伺服电机碳刷", "SP-ELEC", "6x12x16mm", "PCS",
     False, False, "200", "4.500000", "5.000000"),
    ("SP-003", "缝纫机针", "SP-SEW", "DBx1 14#", "PCS",
     True, False, "5000", "0.350000", "0.400000"),
    ("CS-001", "缝纫机油", "CS", "32# 白油 5L/桶", "L",
     False, False, "200", "22.000000", "23.000000"),
)

FABRIC_PROFILES = (
    ("FAB-001", "100% 棉", "185.00", "180.000", "本白", True, "3.500"),
    ("FAB-002", "100% 涤纶", "150.00", "210.000", "藏青", True, "2.000"),
    ("FAB-003", "棉涤 65/35", "180.00", "320.000", "麻灰", True, "4.000"),
)

COLORS = (
    ("BK", "黑色", "#000000", 10),
    ("WH", "白色", "#FFFFFF", 20),
    ("OW", "米白", "#F5F1E6", 30),
    ("NV", "藏青", "#1B2A4A", 40),
    ("MB", "雾霾蓝", "#7C98B3", 50),
    ("WR", "酒红", "#7B2D42", 60),
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

STYLES = (
    ("YS-W-2401", "女士圆领短袖T恤", "women", "意尚智造", "夏", "2024", "轻氧系列"),
    ("YS-W-2402", "女士连帽卫衣", "women", "意尚智造", "秋", "2024", "轻氧系列"),
    ("YS-W-2403", "女士修身长裤", "women", "意尚智造", "四季", "2024", "都市系列"),
    ("YS-M-2401", "男士翻领 POLO 衫", "men", "意尚智造", "夏", "2024", "商务系列"),
    ("YS-M-2402", "男士休闲夹克", "men", "意尚智造", "秋", "2024", "商务系列"),
    ("YS-U-2403", "中性款运动外套", "unisex", "意尚智造", "春", "2024", "运动系列"),
)

STYLE_MATRIX = {
    "YS-W-2401": (("BK", "WH", "OW"), ("S", "M", "L", "XL")),
    "YS-W-2402": (("BK", "NV", "MB"), ("M", "L", "XL")),
    "YS-W-2403": (("BK", "KH"), ("S", "M", "L", "XL")),
    "YS-M-2401": (("WH", "NV"), ("170A", "175A", "180A")),
    "YS-M-2402": (("BK", "WR", "LG"), ("170A", "175A", "180A")),
    "YS-U-2403": (("BK", "LG"), ("M", "L", "XL")),
}

WAREHOUSES = (
    ("WH-RAW-01", "原料仓", "raw", "F01", "WH", False),
    ("WH-FG-01", "成品仓", "finished", "F01", "WH", False),
    ("WH-SP-01", "备件仓", "spare", "F01", "EAM", False),
    ("WH-QC-01", "待检仓", "quarantine", "F01", "QC", False),
    ("WH-RAW-02", "原料仓", "raw", "F02", "WH", False),
    ("WH-FG-02", "成品仓", "finished", "F02", "WH", False),
)

ZONES = (
    ("RCV", "收货区", "receiving", 10),
    ("STO", "存储区", "storage", 20),
    ("PCK", "拣货区", "picking", 30),
    ("SHP", "发货区", "shipping", 40),
)

# 库区 → (排数, 列数, 层数)，用于批量生成储位
ZONE_LOCATION_GRID = {"STO": (3, 4, 2), "PCK": (2, 4, 1), "RCV": (1, 3, 1), "SHP": (1, 3, 1)}
# 客户与供应商演示数据（阶段 2 第一步的主数据）。
# 电话一律使用 138-0000-xxxx 形式的合成号码，不含真实个人资料。
CUSTOMERS = (
    {
        "code": "CUS-001",
        "name": "杭州锦尚服饰有限公司",
        "short_name": "锦尚服饰",
        "category": "brand",
        "level": "A",
        "status": "active",
        "credit_limit": "500000",
        "payment_terms": "月结 30 天",
        "tax_no": "91330100MA0000001X",
        "address": "浙江省杭州市江干区九堡街道",
        "primary_contact_name": "刘敏",
        "primary_contact_phone": "13800000001",
        "salesman_no": "E1005",
        "contacts": (
            {"name": "刘敏", "position": "采购经理", "phone": "13800000001", "is_primary": True},
            {"name": "赵霞", "position": "对账会计", "phone": "13800000002"},
        ),
    },
    {
        "code": "CUS-002",
        "name": "苏州云锦服饰贸易有限公司",
        "short_name": "云锦贸易",
        "category": "distributor",
        "level": "B",
        "status": "active",
        "credit_limit": "200000",
        "payment_terms": "月结 45 天",
        "tax_no": "91320500MA0000002Y",
        "address": "江苏省苏州市吴中区",
        "primary_contact_name": "周俊",
        "primary_contact_phone": "13800000003",
        "salesman_no": "E1005",
        "contacts": (
            {"name": "周俊", "position": "总经理", "phone": "13800000003", "is_primary": True},
        ),
    },
    {
        "code": "CUS-003",
        "name": "广州衣尚电子商务有限公司",
        "short_name": "衣尚电商",
        "category": "online",
        "level": "C",
        "status": "potential",
        "credit_limit": "0",
        "payment_terms": "预付",
        "address": "广东省广州市白云区",
        "primary_contact_name": "陈曦",
        "primary_contact_phone": "13800000004",
        "salesman_no": "E1005",
        "contacts": (
            {"name": "陈曦", "position": "运营负责人", "phone": "13800000004", "is_primary": True},
        ),
    },
)

SUPPLIERS = (
    {
        "code": "SUP-001",
        "name": "绍兴柯桥恒源纺织有限公司",
        "short_name": "恒源纺织",
        "category": "fabric",
        "grade": "A",
        "admission_status": "admitted",
        "payment_terms": "月结 60 天",
        "tax_no": "91330600MA0000003Z",
        "address": "浙江省绍兴市柯桥区中国轻纺城",
        "primary_contact_name": "孙倩",
        "primary_contact_phone": "13800000011",
        "buyer_no": "E1004",
        "contacts": (
            {"name": "孙倩", "position": "销售经理", "phone": "13800000011", "is_primary": True},
        ),
        "qualifications": (
            {
                "qualification_type": "business_license",
                "certificate_no": "BL-DEMO-001",
                "issued_by": "绍兴市市场监督管理局",
                "issued_date": "2020-05-18",
                "expiry_date": "2030-05-17",
            },
            {
                "qualification_type": "quality_system",
                "certificate_no": "ISO9001-DEMO-001",
                "issued_by": "演示认证机构",
                "issued_date": "2023-03-01",
                "expiry_date": "2026-02-28",
            },
        ),
    },
    {
        "code": "SUP-002",
        "name": "宁波北仑辅料供应有限公司",
        "short_name": "北仑辅料",
        "category": "accessory",
        "grade": "B",
        "admission_status": "admitted",
        "payment_terms": "月结 30 天",
        "address": "浙江省宁波市北仑区",
        "primary_contact_name": "钱伟",
        "primary_contact_phone": "13800000012",
        "buyer_no": "E1004",
        "contacts": (
            {"name": "钱伟", "position": "业务员", "phone": "13800000012", "is_primary": True},
        ),
        "qualifications": (
            {
                "qualification_type": "business_license",
                "certificate_no": "BL-DEMO-002",
                "issued_by": "宁波市市场监督管理局",
                "issued_date": "2021-08-09",
                "expiry_date": "2031-08-08",
            },
            {
                # 故意留空证书编号：演示「未登记编号时 dedup_key 为 NULL、允许同类型多条」
                "qualification_type": "test_report",
                "certificate_no": "",
                "issued_by": "演示第三方检测机构",
                "issued_date": "2026-01-15",
                "expiry_date": None,
            },
        ),
    },
    {
        "code": "SUP-003",
        "name": "湖州织里机械备件有限公司",
        "short_name": "织里备件",
        "category": "spare_part",
        "grade": "C",
        "admission_status": "pending",
        "payment_terms": "现结",
        "address": "浙江省湖州市吴兴区织里镇",
        "primary_contact_name": "郑涛",
        "primary_contact_phone": "13800000013",
        "buyer_no": "E1004",
        "contacts": (
            {"name": "郑涛", "position": "售后工程师", "phone": "13800000013", "is_primary": True},
        ),
        "qualifications": (),
    },
)

DEMO_USERS = (
    ("md_admin", "主数据管理员", "E1014", ("masterdata_admin",)),
    ("fac_admin", "工厂管理员", "E1002", ("factory_admin",)),
    ("wh_admin", "仓储主管", "E1006", ("warehouse_admin",)),
    ("dept_mgr", "生产计划主管", "E1003", ("approver", "demo_dept_manager")),
    ("gm", "总经理", "E1001", ("approver", "demo_gm")),
    ("finance", "财务复核", "E1004", ("approver", "demo_finance")),
    ("qc01", "质量工程师", "E1007", ("viewer",)),
    ("sales01", "销售主管", "E1005", ("viewer",)),
    ("prc_admin", "采购专员", "E1015", ("procurement_admin",)),
    ("qc_inspect", "来料检验员", "E1013", ("quality_inspector",)),
)

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

APPROVAL_TEMPLATES = (
    {
        "code": "AP-GENERAL",
        "name": "通用审批",
        "biz_type": "general",
        "description": "单节点部门审批，用于验证顺序审批与审批轨迹。",
        "nodes": (
            {"seq": 1, "name": "部门主管审批", "role": "demo_dept_manager", "amount_min": None},
        ),
    },
    {
        "code": "AP-EXPENSE",
        "name": "费用报销审批",
        "biz_type": "expense",
        "description": "部门主管审批后，金额达到 5000 元进入财务复核。",
        "nodes": (
            {"seq": 1, "name": "部门主管审批", "role": "demo_dept_manager", "amount_min": None},
            {"seq": 2, "name": "财务复核", "role": "demo_finance", "amount_min": "5000"},
        ),
    },
    {
        "code": "AP-PURCHASE",
        "name": "采购申请审批（通用）",
        "biz_type": "purchase_request",
        "description": "部门主管 → 金额≥1 万总经理 → 金额≥5 万财务复核。",
        "nodes": (
            {"seq": 1, "name": "部门主管审批", "role": "demo_dept_manager", "amount_min": None},
            {"seq": 2, "name": "总经理审批", "role": "demo_gm", "amount_min": "10000"},
            {"seq": 3, "name": "财务复核", "role": "demo_finance", "amount_min": "50000"},
        ),
    },
    {
        # biz_type 必须与 apps.sales.services.BIZ_TYPE_ORDER 完全一致，
        # 否则销售订单提交时找不到模板（服务层直接拒绝而不是静默跳过审批）
        "code": "AP-SALES-ORDER",
        "name": "销售订单审批",
        "biz_type": "sales.order",
        "description": "部门主管审批；金额≥5 万追加总经理审批，金额≥20 万追加财务复核。",
        "nodes": (
            {"seq": 1, "name": "部门主管审批", "role": "demo_dept_manager", "amount_min": None},
            {"seq": 2, "name": "总经理审批", "role": "demo_gm", "amount_min": "50000"},
            {"seq": 3, "name": "财务复核", "role": "demo_finance", "amount_min": "200000"},
        ),
    },
    {
        # biz_type 必须与 apps.procurement.services.BIZ_TYPE_REQUISITION 完全一致，
        # 否则采购申请提交时找不到模板（服务层会直接拒绝而不是静默跳过审批）
        "code": "AP-PRC-REQ",
        "name": "采购申请审批",
        "biz_type": "procurement.requisition",
        "description": "采购申请：部门主管审批（演示单节点）。",
        "nodes": (
            {"seq": 1, "name": "部门主管审批", "role": "demo_dept_manager", "amount_min": None},
        ),
    },
    {
        # 对应 apps.procurement.services.BIZ_TYPE_ORDER
        "code": "AP-PRC-ORDER",
        "name": "采购订单审批",
        "biz_type": "procurement.order",
        "description": "采购订单：部门主管审批（演示单节点）。",
        "nodes": (
            {"seq": 1, "name": "部门主管审批", "role": "demo_dept_manager", "amount_min": None},
        ),
    },
    {
        # biz_type 必须与 apps.planning.services.BIZ_TYPE_BOM 完全一致，
        # 否则 BOM 提交时找不到模板（服务层直接拒绝而不是静默跳过审批）
        "code": "AP-BOM",
        "name": "BOM 变更审批",
        "biz_type": "planning.bom",
        "description": "BOM 版本审核：部门主管审批（演示单节点）。",
        "nodes": (
            {"seq": 1, "name": "部门主管审批", "role": "demo_dept_manager", "amount_min": None},
        ),
    },
    {
        # 对应 apps.planning.services.BIZ_TYPE_ROUTING
        "code": "AP-ROUTING",
        "name": "工艺路线审批",
        "biz_type": "planning.routing",
        "description": "工艺路线版本审核：部门主管审批（演示单节点）。",
        "nodes": (
            {"seq": 1, "name": "部门主管审批", "role": "demo_dept_manager", "amount_min": None},
        ),
    },
)


class Command(BaseCommand):
    help = "写入阶段 0/1 的开发演示数据（幂等，生产环境禁止执行）。"

    def add_arguments(self, parser) -> None:
        parser.add_argument("--yes", action="store_true", help="在非开发环境中确认执行。")
        parser.add_argument("--skip-users", action="store_true", help="不创建演示账号。")

    def handle(self, *args, **options) -> None:
        environment = settings.DJANGO_ENV
        if environment == "production":
            raise CommandError("seed_demo 禁止在生产环境执行。请使用 bootstrap_system 初始化系统数据。")
        if environment not in {"development", "test"} and not options["yes"]:
            raise CommandError(f"当前环境为 {environment}，如确认写入演示数据请追加 --yes。")

        self.counts: dict[str, int] = {}
        self.created_passwords: list[tuple[str, str]] = []

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
            self._customers()
            self._suppliers()
            self.demo_roles = self._demo_roles()
            if not options["skip_users"]:
                self._users()
            self._approval_templates()
            self._inventory()
            self._procurement()
            self._sales()
            self._engineering()
            self._mrp()

        self._report()
        if self.created_passwords:
            lines = "\n".join(f"    {name}：{pwd}" for name, pwd in self.created_passwords)
            self.stdout.write(
                self.style.WARNING("以下演示账号为本次新建，口令仅显示一次（请勿用于生产）：\n" + lines)
            )

    # -- 通用工具 --------------------------------------------------------
    def _upsert(self, model, key: dict, defaults: dict):
        obj, created = model.objects.update_or_create(**key, defaults=defaults)
        label = model._meta.label
        self.counts[label] = self.counts.get(label, 0) + (1 if created else 0)
        return obj
    # -- 组织 ------------------------------------------------------------
    def _company(self):
        return self._upsert(
            Company,
            {"code": COMPANY["code"]},
            {
                "name": COMPANY["name"],
                "short_name": COMPANY["short_name"],
                "address": "浙江省杭州市余杭区仁和街道",
                "contact_person": "陈立",
                "contact_phone": "0571-88880000",
                "is_active": True,
                "remark": DEMO_REMARK,
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
                    "remark": DEMO_REMARK,
                },
            )
        return result

    def _factories(self) -> dict[str, Factory]:
        result: dict[str, Factory] = {}
        for code, name, address in FACTORIES:
            result[code] = self._upsert(
                Factory,
                {"company": self.company, "code": code},
                {"name": name, "address": address, "is_active": True, "remark": DEMO_REMARK},
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
                        "remark": DEMO_REMARK,
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
                        "remark": DEMO_REMARK,
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
                        "remark": DEMO_REMARK,
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
                    "remark": DEMO_REMARK,
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
                    "remark": DEMO_REMARK,
                },
            )
        return result

    def _teams(self) -> None:
        definitions = (
            ("F01/SEW/SL01", "T-01", "一号缝制线甲班", "DAY", ("E1009",)),
            ("F01/SEW/SL01", "T-02", "一号缝制线乙班", "NIGHT", ("E1009",)),
            ("F01/CUT/CL01", "T-03", "裁剪线白班", "DAY", ("E1010",)),
            ("F01/FIN/FL01", "T-04", "整烫包装白班", "MID", ("E1011",)),
            ("F01/SEW2/SL02", "T-05", "二号缝制线白班", "DAY", ("E1009",)),
            ("F02/SEW/SL01", "T-06", "二厂缝制白班", "DAY", ("E1012",)),
            ("F02/FIN/FL01", "T-07", "二厂整烫包装白班", "DAY", ("E1013",)),
        )
        for line_key, code, name, shift_code, members in definitions:
            workshop = self.lines[line_key].workshop
            team = self._upsert(
                Team,
                {"workshop": workshop, "code": code},
                {
                    "name": name,
                    "shift": self.shifts[shift_code],
                    "leader": self.employees["E1002"],
                    "is_active": True,
                    "remark": DEMO_REMARK,
                },
            )
            for member_no in members:
                self._upsert(
                    TeamMember,
                    {"team": team, "employee": self.employees[member_no]},
                    {"role_in_team": "member", "start_date": date(2024, 1, 1), "is_active": True},
                )
    # -- 主数据 ----------------------------------------------------------
    def _uoms(self) -> dict[str, UoM]:
        result: dict[str, UoM] = {}
        for code, name, category, places in UOMS:
            result[code] = self._upsert(
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
            self._upsert(
                UoMConversion,
                {"from_uom": result[from_code], "to_uom": result[to_code]},
                {"factor": Decimal(factor), "is_fixed": True, "is_active": True},
            )
        return result

    def _material_categories(self) -> dict[str, MaterialCategory]:
        result: dict[str, MaterialCategory] = {}
        for code, name, category_type, parent_code, sort_order in MATERIAL_CATEGORIES:
            result[code] = self._upsert(
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
                    "brand": "意尚智造",
                    "season": "四季",
                    "year": "2024",
                    "series": "常规",
                    "is_active": True,
                    "remark": DEMO_REMARK,
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
            result[code] = self._upsert(
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
            result[code] = self._upsert(
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
                    "description": f"{name}（{series}）演示款式档案。",
                    "is_active": True,
                    "remark": DEMO_REMARK,
                },
            )
        return result

    def _skus(self) -> None:
        counter = 0
        for style_code, (color_codes, size_codes) in STYLE_MATRIX.items():
            style = self.styles[style_code]
            for color_code in color_codes:
                for size_code in size_codes:
                    counter += 1
                    color = self.colors[color_code]
                    size = self.sizes[size_code]
                    sku_code = f"{style_code}-{color_code}-{size_code}"
                    material = self._upsert(
                        Material,
                        {"company": self.company, "code": sku_code},
                        {
                            "name": f"{style.name} {color.name} {size.name}",
                            "category": self.categories["FG"],
                            "spec": f"{color.name}/{size.name}",
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
                            "remark": DEMO_REMARK,
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
                            "remark": DEMO_REMARK,
                        },
                    )
                    self._upsert(
                        Identifier,
                        {"identifier_type": IdentifierType.SKU_BARCODE, "value": barcode},
                        {
                            "sku": sku,
                            "material": material,
                            "extra": {"来源": "seed_demo"},
                            "is_active": True,
                            "remark": DEMO_REMARK,
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
                    "manager_name": "周丽",
                    "allow_negative_stock": allow_negative,
                    "is_active": True,
                    "remark": DEMO_REMARK,
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
                        "remark": DEMO_REMARK,
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
                                    "remark": DEMO_REMARK,
                                },
                            )

    # -- 演示角色与账号 --------------------------------------------------
    def _customers(self) -> None:
        """客户档案与联系人（阶段 2 第一步）。"""
        for item in CUSTOMERS:
            customer = self._upsert(
                Customer,
                {"company": self.company, "code": item["code"]},
                {
                    "name": item["name"],
                    "short_name": item["short_name"],
                    "category": item["category"],
                    "level": item["level"],
                    "status": item["status"],
                    "credit_limit": Decimal(item["credit_limit"]),
                    "payment_terms": item["payment_terms"],
                    "tax_no": item.get("tax_no", ""),
                    "address": item.get("address", ""),
                    "primary_contact_name": item.get("primary_contact_name", ""),
                    "primary_contact_phone": item.get("primary_contact_phone", ""),
                    "salesman": self.employees.get(item.get("salesman_no")),
                    "is_active": True,
                    "remark": DEMO_REMARK,
                },
            )
            for contact in item["contacts"]:
                self._upsert(
                    CustomerContact,
                    {"customer": customer, "name": contact["name"]},
                    {
                        "position": contact.get("position", ""),
                        "phone": contact.get("phone", ""),
                        "email": contact.get("email", ""),
                        "is_primary": bool(contact.get("is_primary", False)),
                        "is_active": True,
                        "remark": DEMO_REMARK,
                    },
                )

    def _suppliers(self) -> None:
        """供应商档案、联系人与资质（阶段 2 第一步）。"""
        for item in SUPPLIERS:
            supplier = self._upsert(
                Supplier,
                {"company": self.company, "code": item["code"]},
                {
                    "name": item["name"],
                    "short_name": item["short_name"],
                    "category": item["category"],
                    "grade": item["grade"],
                    "admission_status": item["admission_status"],
                    "payment_terms": item["payment_terms"],
                    "tax_no": item.get("tax_no", ""),
                    "address": item.get("address", ""),
                    "primary_contact_name": item.get("primary_contact_name", ""),
                    "primary_contact_phone": item.get("primary_contact_phone", ""),
                    "buyer": self.employees.get(item.get("buyer_no")),
                    "is_active": True,
                    "remark": DEMO_REMARK,
                },
            )
            for contact in item["contacts"]:
                self._upsert(
                    SupplierContact,
                    {"supplier": supplier, "name": contact["name"]},
                    {
                        "position": contact.get("position", ""),
                        "phone": contact.get("phone", ""),
                        "email": contact.get("email", ""),
                        "is_primary": bool(contact.get("is_primary", False)),
                        "is_active": True,
                        "remark": DEMO_REMARK,
                    },
                )
            for qualification in item["qualifications"]:
                self._upsert(
                    SupplierQualification,
                    {
                        "supplier": supplier,
                        "qualification_type": qualification["qualification_type"],
                        "certificate_no": qualification["certificate_no"],
                    },
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
                        "remark": DEMO_REMARK,
                    },
                )

    def _demo_roles(self) -> dict[str, Role]:
        result: dict[str, Role] = {}
        for code, name, scope, codes in DEMO_ROLES:
            role = self._upsert(
                Role,
                {"code": code},
                {
                    "name": name,
                    "company": self.company,
                    "data_scope_type": scope,
                    "is_system": False,
                    "is_active": True,
                    "sort_order": 200,
                    "remark": f"{DEMO_REMARK}：审批节点路由使用。",
                },
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
            result[code] = role
        return result

    def _users(self) -> None:
        configured = settings.YISHANG.get("DEMO_PASSWORD") or ""
        for username, display_name, employee_no, role_codes in DEMO_USERS:
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
                # 演示账号可能被多人共用，但仅用于本地开发，不强制改密；
                # 生产管理员账号由 bootstrap_system 创建并强制首次改密。
                user.must_change_password = False
                user.save()
                self.created_passwords.append((username, password))
                self.counts["identity.User"] = self.counts.get("identity.User", 0) + 1
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

    # -- 审批模板 --------------------------------------------------------
    def _approval_templates(self) -> None:
        for definition in APPROVAL_TEMPLATES:
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
                self._upsert(
                    ApprovalTemplateNode,
                    {"template": template, "seq": node["seq"]},
                    {
                        "name": node["name"],
                        "approver_type": ApproverType.ROLE,
                        "approver_role": self.demo_roles[node["role"]],
                        "approver_user": None,
                        "amount_min": Decimal(node["amount_min"]) if node["amount_min"] else None,
                        "amount_max": None,
                        "department_ids": [],
                        "is_active": True,
                    },
                )

    # -- 计划演示数据（BOM / 工艺路线） -----------------------------------
    def _engineering(self) -> None:
        """工程数据演示：BOM 与工艺路线 → 提交 → 审批通过（任务书 9.5）。

        与采购 / 销售演示数据同样的约束：全部通过 `apps.planning.services` 完成，
        演示数据不直接写单据表，也不修改已审核版本——需要变更时只能派生新版本。

        幂等：按「款式 + 款式通用范围」是否已有版本判断，已存在则只按当前状态
        继续推进到「已审核」，不会重复建单或产生重复版本。
        """
        from apps.planning import services as pl
        from apps.planning.models import Bom, BomStatus, Routing, RoutingStatus
        from apps.workflow import services as workflow_services
        from apps.workflow.models import ApprovalInstance, InstanceStatus

        actor = User.objects.filter(is_superuser=True).order_by("id").first()
        if actor is None:
            self.stdout.write(
                self.style.WARNING("未找到超级管理员账号，跳过 BOM / 工艺路线演示数据。")
            )
            return

        approver = User.objects.filter(username="dept_mgr", is_active=True).first()
        if approver is None:
            self.stdout.write(
                self.style.WARNING(
                    "未找到演示审批账号 dept_mgr，BOM / 工艺路线将停留在「审批中」。"
                )
            )

        def approve(instance_id: int | None, document) -> bool:
            if instance_id is None or approver is None:
                return False
            instance = ApprovalInstance.objects.filter(pk=instance_id).first()
            if instance is None or instance.status != InstanceStatus.PENDING:
                return False
            workflow_services.approve_instance(approver, instance, comment="演示审批通过")
            document.refresh_from_db()
            return True

        style = self.styles["YS-W-2401"]

        # 1) BOM：面料 + 缝纫线 + 主唛织标 + 吊牌 + 胶袋（含损耗率）
        bom = (
            Bom.objects.filter(company=self.company, style=style, sku__isnull=True)
            .order_by("-version_no")
            .first()
        )
        if bom is None:
            bom = pl.create_bom(
                user=actor,
                company=self.company,
                style=style,
                lines=[
                    {
                        "material": self.materials["FAB-001"],
                        "quantity": Decimal("0.280000"),
                        "loss_rate": Decimal("0.060000"),
                        "position": "大身",
                    },
                    {
                        "material": self.materials["ACC-001"],
                        "quantity": Decimal("0.004000"),
                        "loss_rate": Decimal("0.050000"),
                        "position": "缝制",
                    },
                    {
                        "material": self.materials["ACC-005"],
                        "quantity": Decimal("1"),
                        "loss_rate": Decimal("0.020000"),
                        "is_key_material": True,
                        "position": "领口",
                    },
                    {
                        "material": self.materials["PKG-002"],
                        "quantity": Decimal("1"),
                        "loss_rate": Decimal("0.010000"),
                    },
                    {
                        "material": self.materials["PKG-003"],
                        "quantity": Decimal("1"),
                        "loss_rate": Decimal("0.010000"),
                    },
                ],
                effective_from=date.today(),
                remark=DEMO_REMARK,
            )
            self._count("planning.Bom")
        if bom.status == BomStatus.DRAFT:
            bom = pl.submit_bom(bom, user=actor, comment="演示提交")
        if bom.status == BomStatus.SUBMITTED:
            approve(bom.approval_instance_id, bom)

        # 2) 工艺路线：裁剪 → 缝制 → 整烫 → 检验（质检点）→ 包装
        routing = (
            Routing.objects.filter(company=self.company, style=style, sku__isnull=True)
            .order_by("-version_no")
            .first()
        )
        if routing is None:
            routing = pl.create_routing(
                user=actor,
                company=self.company,
                style=style,
                steps=[
                    {
                        "sequence": 1,
                        "name": "裁剪",
                        "workshop": self.workshops["F01/CUT"],
                        "workcenter": "一号裁剪线",
                        "standard_hours": Decimal("0.080000"),
                    },
                    {
                        "sequence": 2,
                        "name": "缝制",
                        "workshop": self.workshops["F01/SEW"],
                        "workcenter": "一号缝制线",
                        "standard_hours": Decimal("0.350000"),
                    },
                    {
                        "sequence": 3,
                        "name": "整烫",
                        "workshop": self.workshops["F01/FIN"],
                        "workcenter": "一号整烫线",
                        "standard_hours": Decimal("0.060000"),
                    },
                    {
                        "sequence": 4,
                        "name": "检验",
                        "workshop": self.workshops["F01/FIN"],
                        "workcenter": "检验工位",
                        "standard_hours": Decimal("0.050000"),
                        "is_quality_gate": True,
                    },
                    {
                        "sequence": 5,
                        "name": "包装",
                        "workshop": self.workshops["F01/FIN"],
                        "workcenter": "包装工位",
                        "standard_hours": Decimal("0.040000"),
                    },
                ],
                effective_from=date.today(),
                remark=DEMO_REMARK,
            )
            self._count("planning.Routing")
        if routing.status == RoutingStatus.DRAFT:
            routing = pl.submit_routing(routing, user=actor, comment="演示提交")
        if routing.status == RoutingStatus.SUBMITTED:
            approve(routing.approval_instance_id, routing)

    # -- 审批推进（演示用） ----------------------------------------------
    def _approve_fully(self, instance_id: int | None, document) -> bool:
        """把审批实例推进到「已通过」。

        演示模板带金额路由（销售订单 ≥5 万追加总经理、≥20 万追加财务复核），
        只批一个节点会让单据停在「审批中」；这里按**节点上的审批角色**找演示账号逐个审批。
        与其它演示数据一致：全程走 `apps.workflow.services`，不直接改审批表。
        """
        from apps.workflow import services as workflow_services
        from apps.workflow.models import ApprovalInstance, InstanceStatus, StepStatus

        role_users = {
            "demo_dept_manager": "dept_mgr",
            "demo_gm": "gm",
            "demo_finance": "finance",
        }
        instance = ApprovalInstance.objects.filter(pk=instance_id).first()
        for _ in range(10):
            if instance is None or instance.status != InstanceStatus.PENDING:
                break
            step = instance.steps.filter(status=StepStatus.PENDING).order_by("seq").first()
            if step is None:
                break
            username = role_users.get(getattr(step.approver_role, "code", ""), "dept_mgr")
            approver = User.objects.filter(username=username, is_active=True).first()
            if approver is None:
                self.stdout.write(
                    self.style.WARNING(f"缺少演示审批账号 {username}，审批实例将停留在当前节点。")
                )
                break
            workflow_services.approve_instance(approver, instance, comment="演示审批通过")
            instance.refresh_from_db()
        document.refresh_from_db()
        return instance is not None and instance.status == InstanceStatus.APPROVED

    # -- MRP 演示数据 ----------------------------------------------------
    def _mrp(self) -> None:
        """MRP 演示数据：跑一次运算 + 把 1 条**采购建议**转成草稿采购申请（任务书 10.6）。

        约束与其他增量一致：只调用 `apps.planning.mrp` 的公开服务，
        不直接写 MRP 表、不伪造 MES 工单（生产建议本轮明确拒绝转单）。

        幂等：演示需求单按固定单号复用；该公司已有 `completed` 运行则不再重复运算，
        因此重复执行新建 0 条（需求单与运行都不会重复产生）。
        """
        from apps.planning import mrp as mrp_engine
        from apps.planning.models import MrpRun, MrpRunStatus, MrpSuggestion, MrpSuggestionStatus

        # 与库存 / 采购 / 销售 / BOM 演示数据一致：没有超级管理员说明业务单据尚未造出来，
        # MRP 无可算需求，直接跳过（测试库不跑 bootstrap_system 时即属此情况）。
        planner = User.objects.filter(is_superuser=True, is_active=True).order_by("id").first()
        if planner is None:
            self.stdout.write(
                self.style.WARNING("未找到超级管理员账号，跳过 MRP 演示数据（请先执行 bootstrap_system）。")
            )
            return

        # 需求来源：一张保持「已批准、未发货」的销售订单。
        # 选一个有生效 BOM 的成品 SKU，这样 MRP 才能演示「成品生产建议 → 展开子件 → 采购建议」。
        from apps.planning.models import Bom, BomStatus
        from apps.sales import services as sales_services
        from apps.sales.models import SalesOrder, SalesOrderStatus

        bom = (
            Bom.objects.filter(company=self.company, status=BomStatus.APPROVED, sku__isnull=True)
            .order_by("-version_no")
            .first()
        )
        plan_sku = (
            Sku.objects.filter(company=self.company, style=bom.style).order_by("code").first()
            if bom is not None
            else None
        )
        if plan_sku is None:
            self.stdout.write(
                self.style.WARNING("没有「已审核 BOM + SKU」可用于演示需求，跳过 MRP 演示数据。")
            )
            return

        order = SalesOrder.objects.filter(
            company=self.company, order_no="SO-MRP-0001"
        ).first()
        if order is None:
            order = sales_services.create_order(
                user=planner,
                company=self.company,
                customer=Customer.objects.get(company=self.company, code="CUS-001"),
                lines=[
                    {
                        "material_id": plan_sku.material_id,
                        "sku_id": plan_sku.pk,
                        "quantity": Decimal("300"),
                        "price": Decimal("399"),
                    }
                ],
                order_date=date.today(),
                expected_date=date.today() + timedelta(days=14),
                warehouse=Warehouse.objects.get(company=self.company, code="WH-FG-01"),
                tax_rate=Decimal("13"),
                remark=f"{DEMO_REMARK}：MRP 运算需求（保持未发货）",
                order_no="SO-MRP-0001",
            )
            self._count("sales.SalesOrder")
        if order.status == SalesOrderStatus.DRAFT:
            order = sales_services.submit_order(order, user=planner, comment="演示提交")
        if order.status == SalesOrderStatus.SUBMITTED:
            self._approve_fully(order.approval_instance_id, order)
        if order.status not in SalesOrderStatus.open_for_shipment():
            self.stdout.write(
                self.style.WARNING(
                    f"MRP 演示需求单 {order.order_no} 当前状态为「{order.get_status_display()}」，"
                    "本次运算可能没有需求。"
                )
            )

        if MrpRun.objects.filter(
            company=self.company, status=MrpRunStatus.COMPLETED
        ).exists():
            self.stdout.write("MRP 演示数据：已存在完成运行，跳过运算（幂等）。")
            return

        today = date.today()
        run = mrp_engine.run_mrp(
            company=self.company,
            user=planner,
            horizon_start=today,
            horizon_end=today + timedelta(days=mrp_engine.DEFAULT_HORIZON_DAYS),
            bucket="day",
            remark=DEMO_REMARK,
        )
        self._count("planning.MrpRun")

        suggestion = (
            MrpSuggestion.objects.filter(
                run=run, suggestion_type="purchase", status=MrpSuggestionStatus.OPEN
            )
            .order_by("line_no")
            .first()
        )
        if suggestion is None:
            self.stdout.write("MRP 演示数据：本次运算没有采购建议，跳过转单演示。")
            return
        # convert_suggestion 会在锁内重新取一次建议（select_for_update），因此必须使用
        # 返回值：传入的 suggestion 实例是转单前的快照，读了会拿到空的 converted_document_no。
        converted = mrp_engine.convert_suggestion(
            suggestion, user=planner, remark=f"{DEMO_REMARK}：采购建议转草稿采购申请"
        )
        self._count("procurement.PurchaseRequisition")
        self.stdout.write(
            f"MRP 演示数据：运行 {run.run_no}，已把第 {converted.line_no} 条采购建议"
            f"转为草稿采购申请 {converted.converted_document_no}（仍走采购审批）。"
        )

    # -- 采购演示数据 ----------------------------------------------------
    def _procurement(self) -> None:
        """采购闭环演示数据：申请 → 审批 → 订单 → 到货 → 待检 → 检验放行。

        与库存演示数据同样的约束：全部通过 `apps.procurement.services` 与统一库存
        服务完成，演示数据也不允许绕过服务层直接写单据或库存余额。

        幂等：按固定单号判断单据是否存在，已存在的单据按当前状态继续推进到目标
        状态，因此重复执行既不会重复建单，也不会重复入库。
        """
        from apps.procurement import services as prc
        from apps.procurement.models import (
            GoodsReceipt,
            OrderStatus,
            PurchaseOrder,
            PurchaseRequisition,
            ReceiptStatus,
            RequisitionStatus,
        )
        from apps.workflow import services as workflow_services
        from apps.workflow.models import ApprovalInstance, InstanceStatus

        actor = User.objects.filter(is_superuser=True).order_by("id").first()
        if actor is None:
            self.stdout.write(
                self.style.WARNING(
                    "未找到超级管理员账号，跳过采购演示数据（请先执行 bootstrap_system）。"
                )
            )
            return

        approver = User.objects.filter(username="dept_mgr", is_active=True).first()
        if approver is None:
            self.stdout.write(
                self.style.WARNING("未找到演示审批账号 dept_mgr，采购单据将停留在「审批中」。")
            )

        def approve(instance_id: int | None, document) -> bool:
            if instance_id is None or approver is None:
                return False
            instance = ApprovalInstance.objects.filter(pk=instance_id).first()
            if instance is None or instance.status != InstanceStatus.PENDING:
                return False
            workflow_services.approve_instance(approver, instance, comment="演示审批通过")
            document.refresh_from_db()
            return True

        fabric = Material.objects.get(company=self.company, code="FAB-001")
        button = Material.objects.get(company=self.company, code="ACC-002")
        supplier = Supplier.objects.get(company=self.company, code="SUP-001")
        warehouse = Warehouse.objects.get(company=self.company, code="WH-RAW-01")
        # 储位编码在不同库区可能重复，必须连同库区一起定位，避免取到多条
        location = Location.objects.get(
            zone__warehouse=warehouse, zone__code="STO", code="A01-01-01"
        )

        # 1) 采购申请 → 提交 → 审批通过
        requisition = PurchaseRequisition.objects.filter(
            company=self.company, requisition_no="PR-DEMO-0001"
        ).first()
        if requisition is None:
            requisition = prc.create_requisition(
                user=actor,
                company=self.company,
                lines=[
                    {"material_id": fabric.id, "quantity": Decimal("1200")},
                    {"material_id": button.id, "quantity": Decimal("3000")},
                ],
                request_type="planned",
                needed_date=date.today(),
                department=self.departments.get("PUR"),
                factory=self.factories.get("F01"),
                purpose="秋季新款面料与纽扣备料（演示）",
                remark=DEMO_REMARK,
                requisition_no="PR-DEMO-0001",
            )
            self._count("procurement.PurchaseRequisition")
        if requisition.status == RequisitionStatus.DRAFT:
            requisition = prc.submit_requisition(requisition, user=actor, comment="演示提交")
        if requisition.status == RequisitionStatus.SUBMITTED:
            approve(requisition.approval_instance_id, requisition)

        # 2) 按申请转采购订单 → 提交 → 审批通过
        order = PurchaseOrder.objects.filter(
            company=self.company, order_no="PO-DEMO-0001"
        ).first()
        if order is None and requisition.status == RequisitionStatus.APPROVED:
            order = prc.create_order_from_requisition(
                requisition,
                user=actor,
                supplier=supplier,
                warehouse=warehouse,
                expected_date=date.today(),
                tax_rate=Decimal("13"),
                payment_terms="月结 60 天",
                remark=f"{DEMO_REMARK}：由采购申请 PR-DEMO-0001 转单",
                order_no="PO-DEMO-0001",
            )
            self._count("procurement.PurchaseOrder")
        if order is not None and order.status == OrderStatus.DRAFT:
            order = prc.submit_order(order, user=actor, comment="演示提交")
        if order is not None and order.status == OrderStatus.SUBMITTED:
            approve(order.approval_instance_id, order)

        # 3) 到货收货 → 过账（待检库存）→ 来料检验放行
        receipt = GoodsReceipt.objects.filter(
            company=self.company, receipt_no="RC-DEMO-0001"
        ).first()
        if receipt is None and order is not None and order.status in OrderStatus.open_for_receipt():
            order_lines = {
                line.material.code: line
                for line in order.lines.select_related("material").order_by("line_no")
            }
            receipt = prc.create_receipt(
                user=actor,
                order=order,
                warehouse=warehouse,
                lines=[
                    {
                        "order_line": order_lines["FAB-001"],
                        "quantity": Decimal("800"),
                        "location": location,
                        "batch_no": "PO-DEMO-FAB-01",
                    },
                    {
                        "order_line": order_lines["ACC-002"],
                        "quantity": Decimal("3000"),
                        "batch_no": "PO-DEMO-BTN-01",
                    },
                ],
                supplier_delivery_no="DN-DEMO-0001",
                remark=DEMO_REMARK,
                receipt_no="RC-DEMO-0001",
            )
            self._count("procurement.GoodsReceipt")
        if receipt is not None and receipt.status == ReceiptStatus.DRAFT:
            receipt = prc.post_receipt(
                receipt, user=actor, idempotency_key="seed-demo-receipt-post-rc-demo-0001"
            )
        if receipt is not None and receipt.status == ReceiptStatus.POSTED:
            prc.inspect_receipt(
                receipt,
                user=actor,
                result="qualified",
                remark="演示：外观、幅宽、克重与色差符合标准，判定合格放行",
                idempotency_key="seed-demo-receipt-inspect-rc-demo-0001",
            )

    # -- 销售演示数据 ----------------------------------------------------
    def _sales(self) -> None:
        """销售闭环演示数据：销售订单 → 审批 → 库存占用 → 发货出库 → 退货待检 → 检验判定。

        与其它演示数据同样的约束：全部通过 `apps.sales.services` 与统一库存服务完成，
        不直接写单据、不直接改库存余额。幂等：固定单号 + 状态推进，重复执行既不会
        重复建单，也不会重复扣减库存。
        """
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
        from apps.workflow import services as workflow_services
        from apps.workflow.models import ApprovalInstance, InstanceStatus

        actor = User.objects.filter(is_superuser=True).order_by("id").first()
        if actor is None:
            self.stdout.write(
                self.style.WARNING(
                    "未找到超级管理员账号，跳过销售演示数据（请先执行 bootstrap_system）。"
                )
            )
            return

        approver = User.objects.filter(username="dept_mgr", is_active=True).first()
        if approver is None:
            self.stdout.write(
                self.style.WARNING("未找到演示审批账号 dept_mgr，销售订单将停留在「审批中」。")
            )

        def approve(instance_id: int | None, document) -> bool:
            if instance_id is None or approver is None:
                return False
            instance = ApprovalInstance.objects.filter(pk=instance_id).first()
            if instance is None or instance.status != InstanceStatus.PENDING:
                return False
            workflow_services.approve_instance(approver, instance, comment="演示审批通过")
            document.refresh_from_db()
            return True

        customer = Customer.objects.get(company=self.company, code="CUS-001")
        warehouse = Warehouse.objects.get(company=self.company, code="WH-FG-01")
        finished = (
            Material.objects.filter(company=self.company, category__code="FG")
            .order_by("code")
            .first()
        )
        if finished is None:
            self.stdout.write(self.style.WARNING("未找到成品 SKU 物料，跳过销售演示数据。"))
            return
        sku = Sku.objects.filter(material=finished).first()

        # 1) 销售订单（成品 SKU，颜色 / 尺码通过 SKU 关联）
        order = SalesOrder.objects.filter(
            company=self.company, order_no="SO-DEMO-0001"
        ).first()
        if order is None:
            order = sal.create_order(
                user=actor,
                company=self.company,
                customer=customer,
                lines=[
                    {
                        "material_id": finished.id,
                        "sku_id": getattr(sku, "id", None),
                        "quantity": Decimal("60"),
                        "price": Decimal("399"),
                    }
                ],
                order_date=date.today(),
                expected_date=date.today(),
                priority="normal",
                warehouse=warehouse,
                tax_rate=Decimal("13"),
                payment_terms="月结 30 天",
                delivery_address=customer.address,
                remark=f"{DEMO_REMARK}：订单到交付链路（订单 → 占用 → 发货 → 退货 → 检验）",
                order_no="SO-DEMO-0001",
            )
            self._count("sales.SalesOrder")
        if order.status == SalesOrderStatus.DRAFT:
            order = sal.submit_order(order, user=actor, comment="演示提交")
        if order.status == SalesOrderStatus.SUBMITTED:
            approve(order.approval_instance_id, order)

        # 2) 库存占用：只改可用量，不改实存量（幂等）
        if order.status in SalesOrderStatus.open_for_shipment():
            sal.reserve_order_stock(order, user=actor, reason="演示：订单备货占用")

        # 3) 发货出库：必须由本订单占用覆盖
        shipment = SalesShipment.objects.filter(
            company=self.company, sales_order=order, shipment_no="SH-DEMO-0001"
        ).first()
        if shipment is None and order.status in SalesOrderStatus.open_for_shipment():
            order_line = order.lines.order_by("line_no").first()
            shipment = sal.create_shipment(
                user=actor,
                order=order,
                warehouse=warehouse,
                lines=[{"order_line": order_line, "quantity": Decimal("60")}],
                receiver_name=customer.primary_contact_name,
                receiver_phone=customer.primary_contact_phone,
                delivery_address=customer.address,
                carrier="顺丰速运",
                tracking_no="SF-DEMO-0001",
                shipment_no="SH-DEMO-0001",
                remark=f"{DEMO_REMARK}：整单发货",
            )
            self._count("sales.SalesShipment")
        if shipment is not None and shipment.status == ShipmentStatus.DRAFT:
            shipment = sal.post_shipment(
                shipment, user=actor, idempotency_key="seed-demo-sales-ship-0001"
            )

        # 4) 客户退货 → 收货过账进「待检」→ 人工检验判定（合格回库）
        if shipment is None or shipment.status != ShipmentStatus.POSTED:
            return
        return_doc = SalesReturn.objects.filter(
            company=self.company, return_no="SR-DEMO-0001"
        ).first()
        if return_doc is None:
            order_line = order.lines.order_by("line_no").first()
            return_doc = sal.create_return(
                user=actor,
                order=order,
                warehouse=warehouse,
                lines=[{"order_line": order_line, "quantity": Decimal("6")}],
                shipment=shipment,
                reason="客户反馈 2 件尺码偏小、4 件存在色差",
                return_no="SR-DEMO-0001",
                remark=f"{DEMO_REMARK}：退货先验收再判定质量状态",
            )
            self._count("sales.SalesReturn")
        if return_doc.status == ReturnStatus.DRAFT:
            return_doc = sal.post_return(
                return_doc, user=actor, idempotency_key="seed-demo-sales-return-0001"
            )
        if return_doc.status == ReturnStatus.POSTED:
            sal.inspect_return(
                return_doc,
                user=actor,
                result=ReturnDisposition.QUALIFIED,
                remark="复检：外观与尺寸符合标准，转合格库存（演示为人工判定，非自动检测）",
                idempotency_key="seed-demo-sales-return-inspect-0001",
            )

    def _count(self, label: str, amount: int = 1) -> None:
        self.counts[label] = self.counts.get(label, 0) + amount

    # -- 输出 ------------------------------------------------------------
    def _report(self) -> None:
        self.stdout.write(self.style.SUCCESS("演示数据写入完成（本次新建数量）："))
        for label in sorted(self.counts):
            if self.counts[label]:
                self.stdout.write(f"  {label}: {self.counts[label]}")
        self.stdout.write(
            f"  合计新建 {sum(self.counts.values())} 条；其余演示对象已存在并已同步固定字段。"
        )


    # -- 库存演示数据 ----------------------------------------------------
    def _inventory(self) -> None:
        """库存演示数据。

        全部通过**统一库存服务**（`apps/wms/services/stock.py`）过账，演示数据也不允许
        绕过服务直接写余额表：否则演示出来的余额与流水口径可能与真实业务不一致。
        幂等：按 `biz_no` 标记判断是否已存在，重复执行不会重复入库。
        """
        from apps.wms.models import DocumentType, InventoryDocument, QualityStatus
        from apps.wms.services import stock

        actor = User.objects.filter(is_superuser=True).order_by("id").first()
        if actor is None:
            self.stdout.write(
                self.style.WARNING("未找到超级管理员账号，跳过库存演示数据（请先执行 bootstrap_system）。")
            )
            return

        def document(marker: str, document_type: str, warehouse_code: str, lines: list[dict],
                     *, reason: str = "") -> InventoryDocument | None:
            if InventoryDocument.objects.filter(biz_no=marker).exists():
                return None
            warehouse = Warehouse.objects.get(company=self.company, code=warehouse_code)
            created = stock.create_document(
                document_type=document_type,
                company=self.company,
                warehouse=warehouse,
                lines=lines,
                user=actor,
                biz_type="seed_demo",
                biz_no=marker,
                remark=f"{DEMO_REMARK}：{reason}" if reason else DEMO_REMARK,
            )
            posted = stock.post_document(created, user=actor, reason=reason)
            self.counts["wms.InventoryDocument"] = self.counts.get("wms.InventoryDocument", 0) + 1
            return posted

        def location(warehouse_code: str, zone_code: str, code: str):
            warehouse = Warehouse.objects.get(company=self.company, code=warehouse_code)
            return Location.objects.get(
                zone__warehouse=warehouse, zone__code=zone_code, code=code
            )

        fabric = Material.objects.get(company=self.company, code="FAB-001")
        button = Material.objects.get(company=self.company, code="ACC-002")
        finished = Material.objects.filter(company=self.company, category__code="FG").first()
        if finished is None:
            self.stdout.write(self.style.WARNING("未找到成品 SKU 物料，跳过成品入库演示数据。"))
            return

        # 1) 面料到货入待检仓，随后质量放行转为合格库存
        receipt = document(
            "DEMO-GR-FAB-001",
            DocumentType.RECEIPT,
            "WH-RAW-01",
            [
                {
                    "material_id": fabric.id,
                    "location_id": location("WH-RAW-01", "STO", "A01-01-01").id,
                    "batch_no": "FAB-2508-01",
                    "roll_no": "ROLL-0001",
                    "quality_status": QualityStatus.QUARANTINE,
                    "quantity": Decimal("600"),
                }
            ],
            reason="面料到货入待检区",
        )
        if receipt is not None:
            stock.release_quality(
                user=actor,
                company=self.company.id,
                warehouse=receipt.warehouse,
                material=fabric,
                quantity=Decimal("600"),
                location=location("WH-RAW-01", "STO", "A01-01-01"),
                batch_no="FAB-2508-01",
                roll_no="ROLL-0001",
                from_status=QualityStatus.QUARANTINE,
                to_status=QualityStatus.QUALIFIED,
                biz_type="seed_demo",
                biz_no="DEMO-QL-FAB-001",
                reason="来料检验合格，允许投产",
            )
            self.counts["wms.InventoryDocument"] = self.counts.get("wms.InventoryDocument", 0) + 1

        # 2) 辅料入库（合格）
        document(
            "DEMO-GR-ACC-002",
            DocumentType.RECEIPT,
            "WH-RAW-01",
            [
                {
                    "material_id": button.id,
                    "location_id": location("WH-RAW-01", "STO", "A01-01-02").id,
                    "batch_no": "ACC-B-2508",
                    "quality_status": QualityStatus.QUALIFIED,
                    "quantity": Decimal("5000"),
                }
            ],
            reason="辅料到货检验合格入库",
        )

        # 3) 成品入库
        document(
            "DEMO-GR-FG-001",
            DocumentType.RECEIPT,
            "WH-FG-01",
            [
                {
                    "material_id": finished.id,
                    "location_id": location("WH-FG-01", "STO", "A01-01-01").id,
                    "batch_no": "FG-2509-01",
                    "quality_status": QualityStatus.QUALIFIED,
                    "quantity": Decimal("240"),
                }
            ],
            reason="完工检验合格入库",
        )

        # 4) 生产领料（只能领用合格库存）
        document(
            "DEMO-IS-FAB-001",
            DocumentType.ISSUE,
            "WH-RAW-01",
            [
                {
                    "material_id": fabric.id,
                    "location_id": location("WH-RAW-01", "STO", "A01-01-01").id,
                    "batch_no": "FAB-2508-01",
                    "roll_no": "ROLL-0001",
                    "quality_status": QualityStatus.QUALIFIED,
                    "quantity": Decimal("120"),
                }
            ],
            reason="生产工单领料",
        )

        # 5) 库内移库
        document(
            "DEMO-TR-ACC-002",
            DocumentType.MOVE,
            "WH-RAW-01",
            [
                {
                    "material_id": button.id,
                    "location_id": location("WH-RAW-01", "STO", "A01-01-02").id,
                    "target_location_id": location("WH-RAW-01", "PCK", "A01-01-01").id,
                    "batch_no": "ACC-B-2508",
                    "quality_status": QualityStatus.QUALIFIED,
                    "quantity": Decimal("200"),
                }
            ],
            reason="拣货区补货",
        )

        # 6) 盘点差异（盘亏）
        document(
            "DEMO-AD-ACC-002",
            DocumentType.ADJUSTMENT,
            "WH-RAW-01",
            [
                {
                    "material_id": button.id,
                    "location_id": location("WH-RAW-01", "STO", "A01-01-02").id,
                    "batch_no": "ACC-B-2508",
                    "quality_status": QualityStatus.QUALIFIED,
                    "direction": "out",
                    "quantity": Decimal("2"),
                    "remark": "月度盘点差异（盘亏）",
                }
            ],
            reason="月度盘点差异审批通过",
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
