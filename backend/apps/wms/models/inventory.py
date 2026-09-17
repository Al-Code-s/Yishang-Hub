"""库存核心模型：库存余额、库存流水、库存单据。

设计契约见 `docs/inventory-rules.md`（阶段 2 的强制契约）。要点：

1. **规范化维度键**：维度中的 `batch_no` / `roll_no` 可空，而 MySQL 唯一索引不把两个 NULL
   视为相等，直接建多列联合唯一索引会产生重复余额行。因此余额表使用
   `dimension_key NOT NULL UNIQUE`（单列唯一），空值被显式编码为占位符。
2. **流水只追加**：`InventoryTransaction` 不是 `BaseModel`，没有 `version` / `updated_at`，
   并在 `save()` / `delete()` 中拒绝修改与删除，把「流水不可篡改」变成模型级保证，
   而不只是接口约定。
3. **四类数量口径**：`on_hand` / `frozen` / `reserved` / `available`（property）。
   冻结与占用是**互斥数量桶**，由数据库检查约束保证 `frozen + reserved <= on_hand`。

本文件只描述结构与不变量；加锁、幂等、并发创建等流程实现在
`apps/wms/services/stock.py`，**任何模块不得绕过库存服务直接改余额表**。
"""

from __future__ import annotations

import hashlib
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import F, Q

from apps.core.models import BaseModel, CompanyScopedModel

# 数量统一精度：与任务书 5.3 一致（20 位、6 位小数）
QUANTITY_MAX_DIGITS = 20
QUANTITY_DECIMAL_PLACES = 6
DIMENSION_KEY_LENGTH = 64
EMPTY_DIMENSION_TOKEN = "-"


class ImmutableLedgerError(Exception):
    """试图修改或删除库存流水。库存流水为只追加记录。"""


class QualityStatus(models.TextChoices):
    """库存质量状态。待检与不合格库存**不能直接领用或销售**。"""

    QUARANTINE = "quarantine", "待检"
    QUALIFIED = "qualified", "合格"
    REJECTED = "rejected", "不合格"


class TransactionType(models.TextChoices):
    RECEIPT = "receipt", "入库"
    ISSUE = "issue", "出库"
    MOVE_OUT = "move_out", "移库转出"
    MOVE_IN = "move_in", "移库转入"
    ADJUST_UP = "adjust_up", "盘盈调整"
    ADJUST_DOWN = "adjust_down", "盘亏调整"
    QUALITY_OUT = "quality_out", "质量转换转出"
    QUALITY_IN = "quality_in", "质量转换转入"


class Direction(models.TextChoices):
    """库存调整方向。仅调整单使用，其余单据类型由单据类型本身决定方向。"""

    IN = "in", "增加"
    OUT = "out", "减少"


class DocumentType(models.TextChoices):
    RECEIPT = "receipt", "收货入库"
    ISSUE = "issue", "出库"
    MOVE = "move", "移库"
    ADJUSTMENT = "adjustment", "库存调整"
    QUALITY = "quality", "质量状态转换"


class DocumentStatus(models.TextChoices):
    DRAFT = "draft", "草稿"
    POSTED = "posted", "已过账"
    REVERSED = "reversed", "已冲销"
    CANCELLED = "cancelled", "已取消"


def normalize_token(value: str | None) -> str:
    """维度 token 规范化：空值与空白统一编码为占位符，其余去除首尾空白。

    大小写语义：编码类标识（批次号、卷号）按任务书 5.1 明确为**不区分大小写**，
    因此统一 `casefold()`，不依赖数据库排序规则。
    """
    if value is None:
        return EMPTY_DIMENSION_TOKEN
    text = str(value).strip()
    if not text:
        return EMPTY_DIMENSION_TOKEN
    return text.casefold()


def build_dimension_key(
    *,
    company_id: int,
    material_id: int,
    warehouse_id: int,
    location_id: int | None,
    batch_no: str | None,
    roll_no: str | None,
    quality_status: str,
) -> str:
    """生成库存维度键。

    格式：`company|material|warehouse|location|batch|roll|quality` 的 sha256 前 32 位十六进制。
    这是余额表**唯一真正生效**的唯一约束；可读维度列仅用于查询与展示。
    """
    raw = "|".join(
        (
            str(company_id),
            str(material_id),
            str(warehouse_id),
            normalize_token(location_id),
            normalize_token(batch_no),
            normalize_token(roll_no),
            normalize_token(quality_status),
        )
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]
class InventoryBalance(CompanyScopedModel):
    """库存余额。维度：公司 + 物料 + 仓库 + 储位 + 批次 + 卷号 + 质量状态。

    一个维度**只有一行**，由 `dimension_key` 单列唯一约束保证。
    `available` 是计算属性，不落库，避免出现四类数量互相不一致的中间态。
    """

    material = models.ForeignKey(
        "masterdata.Material",
        verbose_name="物料",
        on_delete=models.PROTECT,
        related_name="inventory_balances",
        db_index=True,
    )
    warehouse = models.ForeignKey(
        "wms.Warehouse",
        verbose_name="仓库",
        on_delete=models.PROTECT,
        related_name="inventory_balances",
        db_index=True,
    )
    location = models.ForeignKey(
        "wms.Location",
        verbose_name="储位",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="inventory_balances",
    )
    batch_no = models.CharField("批次号", max_length=64, blank=True, default="", db_index=True)
    roll_no = models.CharField("卷号", max_length=64, blank=True, default="", db_index=True)
    quality_status = models.CharField(
        "质量状态",
        max_length=16,
        choices=QualityStatus.choices,
        default=QualityStatus.QUARANTINE,
        db_index=True,
    )
    # 唯一真正生效的唯一约束（单列），由 build_dimension_key() 生成
    dimension_key = models.CharField(
        "维度键", max_length=DIMENSION_KEY_LENGTH, unique=True, editable=False
    )
    on_hand = models.DecimalField(
        "实存量", max_digits=QUANTITY_MAX_DIGITS, decimal_places=QUANTITY_DECIMAL_PLACES,
        default=Decimal("0"),
    )
    frozen = models.DecimalField(
        "冻结量", max_digits=QUANTITY_MAX_DIGITS, decimal_places=QUANTITY_DECIMAL_PLACES,
        default=Decimal("0"),
    )
    reserved = models.DecimalField(
        "占用量", max_digits=QUANTITY_MAX_DIGITS, decimal_places=QUANTITY_DECIMAL_PLACES,
        default=Decimal("0"),
    )

    class Meta:
        verbose_name = "库存余额"
        verbose_name_plural = "库存余额"
        ordering = ["company_id", "material_id", "warehouse_id", "id"]
        indexes = [
            models.Index(
                fields=["material", "warehouse", "quality_status"],
                name="idx_balance_material_wh_qs",
            ),
            models.Index(fields=["warehouse", "location"], name="idx_balance_wh_location"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(on_hand__gte=0) & Q(frozen__gte=0) & Q(reserved__gte=0),
                name="ck_inventory_balance_non_negative",
            ),
            models.CheckConstraint(
                # frozen + reserved <= on_hand（用等价形式表达，避免依赖未定义的 __add 查找）
                condition=Q(frozen__lte=F("on_hand") - F("reserved")),
                name="ck_inventory_balance_buckets_within_on_hand",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.material_id}@{self.warehouse_id}:{self.on_hand}"

    def save(self, *args, **kwargs):
        if not self.dimension_key:
            self.dimension_key = self.build_dimension_key()
        super().save(*args, **kwargs)

    def build_dimension_key(self) -> str:
        return build_dimension_key(
            company_id=self.company_id,
            material_id=self.material_id,
            warehouse_id=self.warehouse_id,
            location_id=self.location_id,
            batch_no=self.batch_no,
            roll_no=self.roll_no,
            quality_status=self.quality_status,
        )

    @property
    def available(self) -> Decimal:
        """可用量 = 实存量 - 冻结量 - 占用量（任务书 10.8 数量定义）。"""
        return (self.on_hand or Decimal("0")) - (self.frozen or Decimal("0")) - (
            self.reserved or Decimal("0")
        )
class InventoryTransaction(models.Model):
    """库存流水（只追加）。

    刻意**不继承 `BaseModel`**：没有 `version` / `updated_at`，并在 `save()` / `delete()`
    中拒绝更新与删除。任务书 5.5 要求「审计和库存流水不能通过普通业务接口修改」，
    仅靠不提供接口是不够的，这里把它变成模型级不变量。

    每条流水记录数量增减与过账前后的余额快照，使
    `on_hand = 可用 + 冻结 + 占用` 在任意时点都能核对。
    """

    id = models.BigAutoField(primary_key=True)
    company = models.ForeignKey(
        "factory.Company", verbose_name="所属公司", on_delete=models.PROTECT,
        related_name="inventory_transactions", db_index=True,
    )
    document = models.ForeignKey(
        "wms.InventoryDocument", verbose_name="库存单据", null=True, blank=True,
        on_delete=models.PROTECT, related_name="transactions",
    )
    document_line = models.ForeignKey(
        "wms.InventoryDocumentLine", verbose_name="单据行", null=True, blank=True,
        on_delete=models.PROTECT, related_name="transactions",
    )
    transaction_type = models.CharField(
        "流水类型", max_length=16, choices=TransactionType.choices, db_index=True
    )
    material = models.ForeignKey(
        "masterdata.Material", verbose_name="物料", on_delete=models.PROTECT,
        related_name="inventory_transactions", db_index=True,
    )
    warehouse = models.ForeignKey(
        "wms.Warehouse", verbose_name="仓库", on_delete=models.PROTECT,
        related_name="inventory_transactions", db_index=True,
    )
    location = models.ForeignKey(
        "wms.Location", verbose_name="储位", null=True, blank=True,
        on_delete=models.PROTECT, related_name="inventory_transactions",
    )
    batch_no = models.CharField("批次号", max_length=64, blank=True, default="")
    roll_no = models.CharField("卷号", max_length=64, blank=True, default="")
    quality_status = models.CharField(
        "质量状态", max_length=16, choices=QualityStatus.choices, db_index=True
    )
    dimension_key = models.CharField(
        "维度键", max_length=DIMENSION_KEY_LENGTH, db_index=True, editable=False
    )
    # 有符号数量：入库为正、出库为负
    quantity = models.DecimalField(
        "数量", max_digits=QUANTITY_MAX_DIGITS, decimal_places=QUANTITY_DECIMAL_PLACES
    )
    on_hand_before = models.DecimalField(
        "过账前实存量", max_digits=QUANTITY_MAX_DIGITS,
        decimal_places=QUANTITY_DECIMAL_PLACES, default=Decimal("0"),
    )
    on_hand_after = models.DecimalField(
        "过账后实存量", max_digits=QUANTITY_MAX_DIGITS,
        decimal_places=QUANTITY_DECIMAL_PLACES, default=Decimal("0"),
    )
    frozen_after = models.DecimalField(
        "过账后冻结量", max_digits=QUANTITY_MAX_DIGITS,
        decimal_places=QUANTITY_DECIMAL_PLACES, default=Decimal("0"),
    )
    reserved_after = models.DecimalField(
        "过账后占用量", max_digits=QUANTITY_MAX_DIGITS,
        decimal_places=QUANTITY_DECIMAL_PLACES, default=Decimal("0"),
    )
    reason = models.CharField("原因", max_length=255, blank=True, default="")
    # 同一业务事件处理唯一约束（任务书 5.4）：重复过账不会产生第二条流水
    dedup_key = models.CharField(
        "去重键", max_length=191, null=True, blank=True, unique=True, editable=False
    )
    operator = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="操作人", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="+",
    )
    created_at = models.DateTimeField("发生时间", auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "库存流水"
        verbose_name_plural = "库存流水"
        ordering = ["-id"]
        indexes = [
            models.Index(fields=["material", "warehouse", "-id"], name="idx_txn_material_wh_id"),
            models.Index(fields=["document", "id"], name="idx_txn_document_id"),
        ]

    def __str__(self) -> str:
        return f"{self.transaction_type}:{self.quantity}"

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ImmutableLedgerError("库存流水为只追加记录，不允许修改。")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ImmutableLedgerError("库存流水为只追加记录，不允许删除。")
class InventoryDocument(CompanyScopedModel):
    """库存单据头（收货、出库、移库、调整、质量转换）。

    只有 `draft` 状态可以修改；`posted` 之后只能整体冲销。
    单据编号按编码规则取号，保存在本公司内唯一。
    """

    document_no = models.CharField("单据编号", max_length=32, blank=True, default="")
    document_type = models.CharField(
        "单据类型", max_length=16, choices=DocumentType.choices, db_index=True
    )
    status = models.CharField(
        "状态", max_length=16, choices=DocumentStatus.choices,
        default=DocumentStatus.DRAFT, db_index=True,
    )
    warehouse = models.ForeignKey(
        "wms.Warehouse", verbose_name="仓库", on_delete=models.PROTECT,
        related_name="inventory_documents",
    )
    biz_type = models.CharField("来源单据类型", max_length=32, blank=True, default="")
    biz_id = models.CharField("来源单据主键", max_length=64, blank=True, default="")
    biz_no = models.CharField("来源单据编号", max_length=64, blank=True, default="")
    idempotency_key = models.CharField(
        "过账幂等键", max_length=128, null=True, blank=True, unique=True, editable=False
    )
    posted_at = models.DateTimeField("过账时间", null=True, blank=True)
    posted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="过账人", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="+",
    )
    reversed_at = models.DateTimeField("冲销时间", null=True, blank=True)
    reversed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="冲销人", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="+",
    )
    reverse_reason = models.TextField("冲销原因", blank=True, default="")
    remark = models.TextField("备注", blank=True, default="")

    class Meta:
        verbose_name = "库存单据"
        verbose_name_plural = "库存单据"
        ordering = ["-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "document_no"], name="uq_inventory_document_company_no"
            ),
        ]

    def __str__(self) -> str:
        return self.document_no or f"#{self.pk}"

    @property
    def is_editable(self) -> bool:
        return self.status == DocumentStatus.DRAFT

    def postable_lines(self):
        return self.lines.all()


class InventoryDocumentLine(BaseModel):
    """库存单据行。

    不同单据类型使用的字段：
    * 收货/出库/调整：`location` + `quality_status` + `quantity`；
    * 移库：`location`（转出储位）→ `target_location`（转入储位）；
    * 质量转换：`quality_status`（转出）→ `target_quality_status`（转入）。
    """

    document = models.ForeignKey(
        InventoryDocument, verbose_name="单据", on_delete=models.CASCADE, related_name="lines"
    )
    line_no = models.PositiveIntegerField("行号", default=1)
    material = models.ForeignKey(
        "masterdata.Material", verbose_name="物料", on_delete=models.PROTECT, related_name="+"
    )
    location = models.ForeignKey(
        "wms.Location", verbose_name="储位", null=True, blank=True,
        on_delete=models.PROTECT, related_name="+",
    )
    target_location = models.ForeignKey(
        "wms.Location", verbose_name="目标储位", null=True, blank=True,
        on_delete=models.PROTECT, related_name="+",
    )
    batch_no = models.CharField("批次号", max_length=64, blank=True, default="")
    roll_no = models.CharField("卷号", max_length=64, blank=True, default="")
    quality_status = models.CharField(
        "质量状态", max_length=16, choices=QualityStatus.choices,
        default=QualityStatus.QUARANTINE,
    )
    target_quality_status = models.CharField(
        "目标质量状态", max_length=16, choices=QualityStatus.choices,
        blank=True, default="",
    )
    direction = models.CharField(
        "调整方向", max_length=8, choices=Direction.choices, default=Direction.IN,
        help_text="仅库存调整单使用：增加=盘盈、减少=盘亏。",
    )
    quantity = models.DecimalField(
        "数量", max_digits=QUANTITY_MAX_DIGITS, decimal_places=QUANTITY_DECIMAL_PLACES
    )
    remark = models.CharField("备注", max_length=255, blank=True, default="")

    class Meta:
        verbose_name = "库存单据行"
        verbose_name_plural = "库存单据行"
        ordering = ["document_id", "line_no", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["document", "line_no"], name="uq_inventory_line_document_no"
            ),
            models.CheckConstraint(
                condition=Q(quantity__gt=0), name="ck_inventory_line_quantity_positive"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.document_id}-{self.line_no}"
