"""统一主数据：计量单位、物料分类、物料、面料属性、款式、颜色、尺码、SKU、标识。

服饰模型：款式/SPU → 颜色 + 尺码 → SKU。
成品 SKU 与库存物料建立唯一对应关系，避免两套库存编码。
"""

from __future__ import annotations

from django.core.validators import MinValueValidator
from django.db import models

from apps.core.constants import price_field, quantity_field, rate_field
from apps.core.models import BaseModel, CompanyScopedModel

# 长度与重量之间不得无条件换算：面料按卷记录实际计量值与该卷换算依据


class UoM(BaseModel):
    """计量单位。"""

    code = models.CharField("单位编码", max_length=16, unique=True)
    name = models.CharField("单位名称", max_length=32)
    category = models.CharField(
        "单位类别",
        max_length=16,
        choices=(
            ("quantity", "数量"),
            ("length", "长度"),
            ("weight", "重量"),
            ("area", "面积"),
            ("time", "时间"),
            ("volume", "体积"),
            ("other", "其他"),
        ),
        default="quantity",
    )
    decimal_places = models.PositiveSmallIntegerField("显示精度", default=2)
    is_active = models.BooleanField("启用", default=True, db_index=True)
    remark = models.TextField("备注", blank=True, default="")

    class Meta:
        verbose_name = "计量单位"
        verbose_name_plural = "计量单位"
        ordering = ["category", "code"]

    def __str__(self) -> str:
        return f"{self.name}({self.code})"


class UoMConversion(BaseModel):
    """固定换算关系。

    仅登记与批次/卷无关的固定换算；“米→公斤”这类随卷变化的换算不在此处，
    而是在收卷/收货时记录实际值与依据。
    """

    from_uom = models.ForeignKey(UoM, on_delete=models.PROTECT, related_name="conversions_from")
    to_uom = models.ForeignKey(UoM, on_delete=models.PROTECT, related_name="conversions_to")
    factor = rate_field("换算率", validators=[MinValueValidator(0)])
    is_fixed = models.BooleanField("固定换算", default=True)
    is_active = models.BooleanField("启用", default=True)
    remark = models.TextField("备注", blank=True, default="")

    class Meta:
        verbose_name = "单位换算"
        verbose_name_plural = "单位换算"
        ordering = ["from_uom_id", "to_uom_id"]
        constraints = [
            models.UniqueConstraint(fields=["from_uom", "to_uom"], name="uq_uom_conversion_pair"),
            models.CheckConstraint(
                condition=~models.Q(from_uom=models.F("to_uom")),
                name="ck_uom_conversion_distinct",
            ),
            models.CheckConstraint(
                condition=models.Q(factor__gt=0),
                name="ck_uom_conversion_factor_positive",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.from_uom_id}->{self.to_uom_id} x{self.factor}"


class MaterialCategory(BaseModel):
    """统一物料分类：面料 / 辅料 / 半成品 / 成品 / 包装物 / 备品备件 / 消耗品。"""

    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="children"
    )
    code = models.CharField("分类编码", max_length=32, unique=True)
    name = models.CharField("分类名称", max_length=64)
    category_type = models.CharField(
        "分类类型",
        max_length=16,
        choices=(
            ("fabric", "面料"),
            ("accessory", "辅料"),
            ("semifinished", "半成品"),
            ("finished", "成品"),
            ("packaging", "包装物"),
            ("spare_part", "备品备件"),
            ("consumable", "消耗品"),
        ),
        default="fabric",
        db_index=True,
    )
    sort_order = models.IntegerField("排序", default=0)
    is_active = models.BooleanField("启用", default=True, db_index=True)
    remark = models.TextField("备注", blank=True, default="")

    class Meta:
        verbose_name = "物料分类"
        verbose_name_plural = "物料分类"
        ordering = ["sort_order", "code"]

    def __str__(self) -> str:
        return f"{self.name}({self.code})"


class Material(CompanyScopedModel):
    """物料主数据。数量一律用 Decimal，单位换算同时保存交易单位与基本单位。"""

    code = models.CharField("物料编码", max_length=64)
    name = models.CharField("物料名称", max_length=128)
    category = models.ForeignKey(
        MaterialCategory, verbose_name="物料分类", on_delete=models.PROTECT, related_name="materials"
    )
    spec = models.CharField("规格", max_length=128, blank=True, default="")

    base_uom = models.ForeignKey(
        UoM, verbose_name="基本单位", on_delete=models.PROTECT, related_name="materials_base"
    )
    purchase_uom = models.ForeignKey(
        UoM,
        verbose_name="采购单位",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="materials_purchase",
    )
    purchase_factor = rate_field("采购换算率", null=True, blank=True)
    sales_uom = models.ForeignKey(
        UoM,
        verbose_name="销售单位",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="materials_sales",
    )
    sales_factor = rate_field("销售换算率", null=True, blank=True)

    is_batch_managed = models.BooleanField("批次管理", default=False)
    is_roll_managed = models.BooleanField("卷号管理", default=False)
    is_serial_managed = models.BooleanField("序列号管理", default=False)

    safe_stock = quantity_field("安全库存", default=0)
    purchase_price = price_field("采购价", null=True, blank=True)
    reference_cost = price_field("参考成本", null=True, blank=True)

    brand = models.CharField("品牌", max_length=64, blank=True, default="")
    season = models.CharField("季节", max_length=32, blank=True, default="")
    year = models.CharField("年份", max_length=8, blank=True, default="")
    series = models.CharField("系列", max_length=64, blank=True, default="")
    image = models.CharField("图片地址", max_length=255, blank=True, default="")

    is_active = models.BooleanField("启用", default=True, db_index=True)
    remark = models.TextField("备注", blank=True, default="")

    class Meta:
        verbose_name = "物料"
        verbose_name_plural = "物料"
        ordering = ["company_id", "code"]
        constraints = [
            models.UniqueConstraint(fields=["company", "code"], name="uq_material_company_code"),
            models.CheckConstraint(
                condition=models.Q(safe_stock__gte=0), name="ck_material_safe_stock_non_negative"
            ),
        ]
        indexes = [
            models.Index(fields=["company", "category"], name="idx_material_company_category"),
            models.Index(fields=["name"], name="idx_material_name"),
        ]

    def __str__(self) -> str:
        return f"{self.name}({self.code})"


class FabricProfile(BaseModel):
    """面料特殊属性。米与公斤不做无条件统一换算。"""

    material = models.OneToOneField(
        Material, on_delete=models.CASCADE, related_name="fabric_profile"
    )
    composition = models.CharField("成分", max_length=128, blank=True, default="")
    width_cm = quantity_field("幅宽(cm)", null=True, blank=True)
    gram_weight = quantity_field("克重(g/m²)", null=True, blank=True)
    default_color_no = models.CharField("默认色号", max_length=32, blank=True, default="")
    dye_lot_required = models.BooleanField("需要缸号", default=True)
    shrinkage_rate = rate_field("缩水率(%)", null=True, blank=True)

    class Meta:
        verbose_name = "面料属性"
        verbose_name_plural = "面料属性"

    def __str__(self) -> str:
        return f"面料属性-{self.material_id}"


class Color(BaseModel):
    code = models.CharField("颜色编码", max_length=32, unique=True)
    name = models.CharField("颜色名称", max_length=64)
    hex_code = models.CharField("色值", max_length=16, blank=True, default="")
    sort_order = models.IntegerField("排序", default=0)
    is_active = models.BooleanField("启用", default=True, db_index=True)
    remark = models.TextField("备注", blank=True, default="")

    class Meta:
        verbose_name = "颜色"
        verbose_name_plural = "颜色"
        ordering = ["sort_order", "code"]

    def __str__(self) -> str:
        return f"{self.name}({self.code})"


class Size(BaseModel):
    code = models.CharField("尺码编码", max_length=32, unique=True)
    name = models.CharField("尺码名称", max_length=32)
    size_group = models.CharField("尺码组", max_length=32, default="adult", db_index=True)
    sort_order = models.IntegerField("排序", default=0)
    is_active = models.BooleanField("启用", default=True, db_index=True)
    remark = models.TextField("备注", blank=True, default="")

    class Meta:
        verbose_name = "尺码"
        verbose_name_plural = "尺码"
        ordering = ["size_group", "sort_order", "code"]

    def __str__(self) -> str:
        return f"{self.name}({self.code})"


class Style(CompanyScopedModel):
    """款式 / SPU。"""

    code = models.CharField("款式编码", max_length=64)
    name = models.CharField("款式名称", max_length=128)
    category = models.ForeignKey(
        MaterialCategory,
        verbose_name="款式分类",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="styles",
    )
    size_group = models.CharField("尺码组", max_length=32, default="adult")
    brand = models.CharField("品牌", max_length=64, blank=True, default="")
    season = models.CharField("季节", max_length=32, blank=True, default="")
    year = models.CharField("年份", max_length=8, blank=True, default="")
    series = models.CharField("系列", max_length=64, blank=True, default="")
    description = models.TextField("款式说明", blank=True, default="")
    image = models.CharField("图片地址", max_length=255, blank=True, default="")
    is_active = models.BooleanField("启用", default=True, db_index=True)
    remark = models.TextField("备注", blank=True, default="")

    class Meta:
        verbose_name = "款式"
        verbose_name_plural = "款式"
        ordering = ["company_id", "code"]
        constraints = [
            models.UniqueConstraint(fields=["company", "code"], name="uq_style_company_code"),
        ]

    def __str__(self) -> str:
        return f"{self.name}({self.code})"


class Sku(CompanyScopedModel):
    """SKU = 款式 + 颜色 + 尺码。成品 SKU 与库存物料唯一对应。"""

    style = models.ForeignKey(Style, on_delete=models.PROTECT, related_name="skus")
    color = models.ForeignKey(Color, on_delete=models.PROTECT, related_name="skus")
    size = models.ForeignKey(Size, on_delete=models.PROTECT, related_name="skus")
    code = models.CharField("SKU 编码", max_length=96)
    material = models.OneToOneField(
        Material,
        verbose_name="对应库存物料",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="sku",
        help_text="成品 SKU 必须唯一对应一个库存物料，避免出现两套库存编码。",
    )
    barcode = models.CharField("SKU 条码", max_length=64, null=True, blank=True, unique=True)
    is_active = models.BooleanField("启用", default=True, db_index=True)
    remark = models.TextField("备注", blank=True, default="")

    class Meta:
        verbose_name = "SKU"
        verbose_name_plural = "SKU"
        ordering = ["company_id", "code"]
        constraints = [
            models.UniqueConstraint(fields=["company", "code"], name="uq_sku_company_code"),
            models.UniqueConstraint(
                fields=["style", "color", "size"], name="uq_sku_style_color_size"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.style_id}-{self.color_id}-{self.size_id}"


class IdentifierType(models.TextChoices):
    SKU_BARCODE = "sku_barcode", "SKU 条码"
    BATCH = "batch", "批次码"
    ROLL = "roll", "卷号"
    CARTON = "carton", "箱码"
    RFID_EPC = "rfid_epc", "RFID EPC"
    CARRIER = "carrier", "载具码"


class Identifier(BaseModel):
    """统一标识表。

    各类标识识别不同对象，禁止合并到同一个字段：
    SKU 条码识别物料种类，批次码识别批次，卷号识别面料卷，
    箱码识别包装箱，RFID EPC 识别标签，载具码识别吊挂或物流载具。
    """

    identifier_type = models.CharField(
        "标识类型", max_length=16, choices=IdentifierType.choices, db_index=True
    )
    value = models.CharField("标识值", max_length=128)
    sku = models.ForeignKey(
        Sku, verbose_name="关联 SKU", null=True, blank=True, on_delete=models.PROTECT,
        related_name="identifiers",
    )
    material = models.ForeignKey(
        Material, verbose_name="关联物料", null=True, blank=True, on_delete=models.PROTECT,
        related_name="identifiers",
    )
    batch_no = models.CharField("批次号", max_length=64, blank=True, default="")
    extra = models.JSONField("扩展属性", default=dict, blank=True)
    is_active = models.BooleanField("启用", default=True, db_index=True)
    remark = models.TextField("备注", blank=True, default="")

    class Meta:
        verbose_name = "标识"
        verbose_name_plural = "标识"
        ordering = ["identifier_type", "value"]
        constraints = [
            # 同一标识值在同一类型下唯一；不同标识类型之间允许同值但语义不同
            models.UniqueConstraint(
                fields=["identifier_type", "value"], name="uq_identifier_type_value"
            ),
        ]
        indexes = [models.Index(fields=["value"], name="idx_identifier_value")]

    def __str__(self) -> str:
        return f"{self.identifier_type}:{self.value}"
