"""销售模块模型：销售订单 → 库存占用 → 发货出库 → 销售退货。

设计边界（任务书 10.3、12.1）：

* **库存变动只经** `apps.wms.services.stock`：本模块不写任何库存表，
  占用走 `stock.reserve_stock`，发货走 `stock.create_document` + `post_document`，
  退货收货与质量放行复用统一库存服务的收货与质量转换能力。
* **金额一律由后端计算**：行 `amount` = 数量 × 未税单价；单头 `total_amount` =
  Σ 行金额（未税）；`tax_amount` = Σ round(行金额 × 税率, 4)；`amount_with_tax` 为两者之和。
  前端提交的金额字段一律忽略。
* **已发货部分不得删除或改数量**：`shipped_quantity` 只由发货过账累计，
  `returned_quantity` 只由退货过账累计，两者对接口只读（任务书 10.3）。
* 销售订单审批复用 `workflow`，审批结果通过 `workflow.registry` 显式回写状态，
  不使用 signals（任务书 4.3）。
"""

from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import F, Q

from apps.core.constants import money_field, price_field, quantity_field, rate_field
from apps.core.models import BaseModel, CompanyScopedModel


class SalesOrderStatus(models.TextChoices):
    DRAFT = "draft", "草稿"
    SUBMITTED = "submitted", "审批中"
    APPROVED = "approved", "已批准"
    PARTIALLY_SHIPPED = "partially_shipped", "部分发货"
    SHIPPED = "shipped", "已发货"
    CLOSED = "closed", "已关闭"
    REJECTED = "rejected", "已驳回"
    CANCELLED = "cancelled", "已取消"

    @classmethod
    def open_for_shipment(cls) -> tuple[str, ...]:
        """允许继续发货与继续占用库存的状态。"""
        return (cls.APPROVED, cls.PARTIALLY_SHIPPED)

    @classmethod
    def cancellable(cls) -> tuple[str, ...]:
        """允许取消的状态：只要**没有发货事实**就可以取消。"""
        return (cls.DRAFT, cls.SUBMITTED, cls.APPROVED)


class OrderPriority(models.TextChoices):
    NORMAL = "normal", "普通"
    URGENT = "urgent", "加急"


class ShipmentStatus(models.TextChoices):
    DRAFT = "draft", "草稿"
    POSTED = "posted", "已出库"
    CANCELLED = "cancelled", "已取消"


class ReturnStatus(models.TextChoices):
    DRAFT = "draft", "草稿"
    POSTED = "posted", "已收货待检"
    INSPECTED = "inspected", "已检验"
    CANCELLED = "cancelled", "已取消"


class ReturnDisposition(models.TextChoices):
    """退货检验结论。退回的货物先验收，再决定质量状态（任务书 10.3）。"""

    NONE = "none", "未检验"
    QUALIFIED = "qualified", "合格回库"
    REJECTED = "rejected", "判为不合格"


class SalesOrder(CompanyScopedModel):
    """销售订单。提交后进入审批，批准后才允许占用库存与发货。"""

    order_no = models.CharField("订单号", max_length=32)
    customer = models.ForeignKey(
        "crm.Customer",
        verbose_name="客户",
        on_delete=models.PROTECT,
        related_name="sales_orders",
        db_index=True,
    )
    status = models.CharField(
        "状态",
        max_length=20,
        choices=SalesOrderStatus.choices,
        default=SalesOrderStatus.DRAFT,
        db_index=True,
    )
    salesman = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="业务员",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    order_date = models.DateField("下单日期", null=True, blank=True, db_index=True)
    expected_date = models.DateField("要求交期", null=True, blank=True, db_index=True)
    priority = models.CharField(
        "优先级",
        max_length=16,
        choices=OrderPriority.choices,
        default=OrderPriority.NORMAL,
        db_index=True,
    )
    warehouse = models.ForeignKey(
        "wms.Warehouse",
        verbose_name="发货仓库",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
        help_text="库存占用与发货的默认仓库；为空时必须在发货单上指定。",
    )
    currency = models.CharField("币种", max_length=8, default="CNY")
    tax_rate = rate_field("税率(%)", default=0)
    payment_terms = models.CharField("结算方式", max_length=64, blank=True, default="")
    delivery_address = models.CharField("收货地址", max_length=255, blank=True, default="")
    total_amount = money_field("未税金额", default=0)
    tax_amount = money_field("税额", default=0)
    amount_with_tax = money_field("价税合计", default=0)
    approval_instance_id = models.PositiveBigIntegerField("审批实例", null=True, blank=True)
    approved_at = models.DateTimeField("批准时间", null=True, blank=True)
    closed_at = models.DateTimeField("关闭时间", null=True, blank=True)
    remark = models.TextField("备注", blank=True, default="")

    class Meta:
        verbose_name = "销售订单"
        verbose_name_plural = "销售订单"
        ordering = ["-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "order_no"], name="uq_sales_order_company_no"
            ),
            models.CheckConstraint(
                condition=Q(tax_rate__gte=0) & Q(tax_rate__lte=100),
                name="ck_sales_order_tax_rate_range",
            ),
        ]
        indexes = [models.Index(fields=["company", "status"], name="idx_sales_order_status")]

    def __str__(self) -> str:
        return self.order_no


class SalesOrderLine(BaseModel):
    """销售订单明细。

    `shipped_quantity` / `returned_quantity` 由发货与退货过账累计，
    **对接口只读**，避免前端直接改数量绕过累计逻辑（任务书 10.3）。
    """

    order = models.ForeignKey(SalesOrder, on_delete=models.CASCADE, related_name="lines")
    line_no = models.PositiveIntegerField("行号")
    material = models.ForeignKey(
        "masterdata.Material",
        verbose_name="物料",
        on_delete=models.PROTECT,
        related_name="+",
        db_index=True,
    )
    sku = models.ForeignKey(
        "masterdata.Sku",
        verbose_name="SKU",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
        help_text="颜色 + 尺码对应的成品 SKU；与物料一对一，填写后按 SKU 追溯。",
    )
    quantity = quantity_field("订单数量")
    shipped_quantity = quantity_field("已发货数量", default=0)
    returned_quantity = quantity_field("已退货数量", default=0)
    price = price_field("未税单价", default=0)
    amount = money_field("未税金额", default=0)
    uom = models.ForeignKey(
        "masterdata.UoM",
        verbose_name="单位",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    expected_date = models.DateField("行交期", null=True, blank=True)
    remark = models.CharField("备注", max_length=255, blank=True, default="")

    class Meta:
        verbose_name = "销售订单明细"
        verbose_name_plural = "销售订单明细"
        ordering = ["order_id", "line_no", "id"]
        constraints = [
            models.UniqueConstraint(fields=["order", "line_no"], name="uq_sales_order_line_no"),
            models.CheckConstraint(
                condition=Q(quantity__gt=0), name="ck_sales_order_line_quantity_positive"
            ),
            models.CheckConstraint(
                condition=Q(shipped_quantity__gte=0) & Q(returned_quantity__gte=0),
                name="ck_sales_order_line_progress_non_negative",
            ),
            models.CheckConstraint(
                condition=Q(shipped_quantity__lte=F("quantity")),
                name="ck_sales_order_line_shipped_within_quantity",
            ),
            models.CheckConstraint(
                condition=Q(returned_quantity__lte=F("shipped_quantity")),
                name="ck_sales_order_line_returned_within_shipped",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.order_id}-{self.line_no}"

    @property
    def remaining_quantity(self) -> Decimal:
        """未发货数量。已发货部分不得修改或删除，剩余量只能通过新的发货单消耗。"""
        return (self.quantity or Decimal("0")) - (self.shipped_quantity or Decimal("0"))

    @property
    def returnable_quantity(self) -> Decimal:
        """可退货数量 = 已发货 - 已退货。"""
        return (self.shipped_quantity or Decimal("0")) - (self.returned_quantity or Decimal("0"))


class SalesShipment(CompanyScopedModel):
    """销售发货单。

    状态机：`draft → posted`（出库过账，扣减库存），草稿可 `cancelled`。
    过账前必须已完成**库存占用**，且占用数量覆盖本次发货数量。
    """

    shipment_no = models.CharField("发货单号", max_length=32)
    sales_order = models.ForeignKey(
        SalesOrder,
        verbose_name="销售订单",
        on_delete=models.PROTECT,
        related_name="shipments",
        db_index=True,
    )
    customer = models.ForeignKey(
        "crm.Customer",
        verbose_name="客户",
        on_delete=models.PROTECT,
        related_name="+",
        db_index=True,
    )
    status = models.CharField(
        "状态",
        max_length=16,
        choices=ShipmentStatus.choices,
        default=ShipmentStatus.DRAFT,
        db_index=True,
    )
    warehouse = models.ForeignKey(
        "wms.Warehouse",
        verbose_name="发货仓库",
        on_delete=models.PROTECT,
        related_name="+",
    )
    shipped_at = models.DateTimeField("发货时间", null=True, blank=True)
    shipped_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="发货人",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    receiver_name = models.CharField("收货人", max_length=64, blank=True, default="")
    receiver_phone = models.CharField("收货电话", max_length=32, blank=True, default="")
    delivery_address = models.CharField("收货地址", max_length=255, blank=True, default="")
    carrier = models.CharField("承运商", max_length=64, blank=True, default="")
    tracking_no = models.CharField("运单号", max_length=64, blank=True, default="")
    # 库存单据引用：用于幂等与追溯（哪张发货单生成了哪张库存单据）
    issue_document_id = models.PositiveBigIntegerField("出库库存单据", null=True, blank=True)
    remark = models.TextField("备注", blank=True, default="")

    class Meta:
        verbose_name = "销售发货单"
        verbose_name_plural = "销售发货单"
        ordering = ["-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "shipment_no"], name="uq_shipment_company_no"
            ),
        ]
        indexes = [
            models.Index(fields=["sales_order", "status"], name="idx_shipment_order_status"),
        ]

    def __str__(self) -> str:
        return self.shipment_no


class SalesShipmentLine(BaseModel):
    """发货明细。数量不得超过订单行未发货数量。"""

    shipment = models.ForeignKey(SalesShipment, on_delete=models.CASCADE, related_name="lines")
    line_no = models.PositiveIntegerField("行号")
    order_line = models.ForeignKey(
        SalesOrderLine,
        verbose_name="订单行",
        on_delete=models.PROTECT,
        related_name="shipment_lines",
    )
    material = models.ForeignKey(
        "masterdata.Material",
        verbose_name="物料",
        on_delete=models.PROTECT,
        related_name="+",
        db_index=True,
    )
    quantity = quantity_field("发货数量")
    location = models.ForeignKey(
        "wms.Location",
        verbose_name="发货储位",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
        help_text="为空表示不指定储位（库存维度使用空储位）；占用时必须与占用储位一致。",
    )
    batch_no = models.CharField("批次号", max_length=64, blank=True, default="")
    roll_no = models.CharField("卷号", max_length=64, blank=True, default="")
    remark = models.CharField("备注", max_length=255, blank=True, default="")

    class Meta:
        verbose_name = "销售发货明细"
        verbose_name_plural = "销售发货明细"
        ordering = ["shipment_id", "line_no"]
        constraints = [
            models.UniqueConstraint(fields=["shipment", "line_no"], name="uq_shipment_line_no"),
            models.CheckConstraint(
                condition=Q(quantity__gt=0), name="ck_shipment_line_quantity_positive"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.shipment_id}-{self.line_no}"


class SalesReturn(CompanyScopedModel):
    """销售退货单。

    状态机：`draft → posted（收货待检）→ inspected（检验判定）`。

    * `post` 把退回货物**记入待检库存**，调用统一库存服务的收货能力；
    * `inspect` 调用统一库存服务的**质量放行**：合格回库（可再次销售）或判为不合格。

    「验收」与「质量状态判定」是两个动作，与采购收货保持一致的口径。
    """

    return_no = models.CharField("退货单号", max_length=32)
    sales_order = models.ForeignKey(
        SalesOrder,
        verbose_name="销售订单",
        on_delete=models.PROTECT,
        related_name="returns",
        db_index=True,
    )
    shipment = models.ForeignKey(
        SalesShipment,
        verbose_name="原发货单",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="returns",
        help_text="分批发货时用于追溯具体发货批次；为空表示按订单行退货。",
    )
    customer = models.ForeignKey(
        "crm.Customer",
        verbose_name="客户",
        on_delete=models.PROTECT,
        related_name="+",
        db_index=True,
    )
    status = models.CharField(
        "状态",
        max_length=16,
        choices=ReturnStatus.choices,
        default=ReturnStatus.DRAFT,
        db_index=True,
    )
    warehouse = models.ForeignKey(
        "wms.Warehouse",
        verbose_name="退货收货仓库",
        on_delete=models.PROTECT,
        related_name="+",
    )
    reason = models.CharField("退货原因", max_length=255, blank=True, default="")
    received_at = models.DateTimeField("收货时间", null=True, blank=True)
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="收货人",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    inspection_result = models.CharField(
        "检验结论",
        max_length=16,
        choices=ReturnDisposition.choices,
        default=ReturnDisposition.NONE,
        db_index=True,
    )
    inspected_at = models.DateTimeField("检验时间", null=True, blank=True)
    inspected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="检验人",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    inspection_remark = models.TextField("检验说明", blank=True, default="")
    receipt_document_id = models.PositiveBigIntegerField("入库库存单据", null=True, blank=True)
    quality_document_id = models.PositiveBigIntegerField("质量转换单据", null=True, blank=True)
    remark = models.TextField("备注", blank=True, default="")

    class Meta:
        verbose_name = "销售退货单"
        verbose_name_plural = "销售退货单"
        ordering = ["-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "return_no"], name="uq_sales_return_company_no"
            ),
        ]
        indexes = [models.Index(fields=["sales_order", "status"], name="idx_return_order_status")]

    def __str__(self) -> str:
        return self.return_no


class SalesReturnLine(BaseModel):
    """退货明细。数量不得超过订单行「已发货 - 已退货」数量。"""

    return_doc = models.ForeignKey(SalesReturn, on_delete=models.CASCADE, related_name="lines")
    line_no = models.PositiveIntegerField("行号")
    order_line = models.ForeignKey(
        SalesOrderLine,
        verbose_name="订单行",
        on_delete=models.PROTECT,
        related_name="return_lines",
    )
    material = models.ForeignKey(
        "masterdata.Material",
        verbose_name="物料",
        on_delete=models.PROTECT,
        related_name="+",
        db_index=True,
    )
    quantity = quantity_field("退货数量")
    location = models.ForeignKey(
        "wms.Location",
        verbose_name="收货储位",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    batch_no = models.CharField("批次号", max_length=64, blank=True, default="")
    roll_no = models.CharField("卷号", max_length=64, blank=True, default="")
    remark = models.CharField("备注", max_length=255, blank=True, default="")

    class Meta:
        verbose_name = "销售退货明细"
        verbose_name_plural = "销售退货明细"
        ordering = ["return_doc_id", "line_no"]
        constraints = [
            models.UniqueConstraint(fields=["return_doc", "line_no"], name="uq_return_line_no"),
            models.CheckConstraint(
                condition=Q(quantity__gt=0), name="ck_return_line_quantity_positive"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.return_doc_id}-{self.line_no}"
