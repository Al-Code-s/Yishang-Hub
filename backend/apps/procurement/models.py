"""采购模块：采购申请、采购订单、到货收货、来料检验放行。

设计边界（任务书 10.5）：

* **实物到货、库存记账与质量放行是三个不同动作**。本模块把三者拆开：
  `GoodsReceipt` 记录实物到货 → `post` 调用统一库存服务记账（进入**待检**库存）
  → `inspect` 调用统一库存服务做质量放行（待检 → 合格 / 不合格）。
  这样既不会重复增加库存，也不会出现「收货即可销售」的越权设计。
* 本模块**不直接写库存表**，所有库存变动经由 `apps.wms.services.stock`。
* 采购订单审批复用 `workflow`，审批结果通过 `workflow.registry` 显式回写单据状态。
* 收货数量**不得超过订单未收数量**（默认不允许超收），超收直接拒绝而不是静默接受。
"""

from __future__ import annotations

from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.core.constants import money_field, price_field, quantity_field, rate_field
from apps.core.models import BaseModel, CompanyScopedModel


class RequisitionType(models.TextChoices):
    NORMAL = "normal", "常规申请"
    PLANNED = "planned", "计划申请"
    URGENT = "urgent", "紧急申请"


class RequisitionStatus(models.TextChoices):
    DRAFT = "draft", "草稿"
    SUBMITTED = "submitted", "审批中"
    APPROVED = "approved", "已批准"
    REJECTED = "rejected", "已驳回"
    CLOSED = "closed", "已关闭"
    CANCELLED = "cancelled", "已取消"


class OrderStatus(models.TextChoices):
    DRAFT = "draft", "草稿"
    SUBMITTED = "submitted", "审批中"
    APPROVED = "approved", "已批准"
    PARTIALLY_RECEIVED = "partially_received", "部分到货"
    RECEIVED = "received", "已到货"
    CLOSED = "closed", "已关闭"
    REJECTED = "rejected", "已驳回"
    CANCELLED = "cancelled", "已取消"

    @classmethod
    def open_for_receipt(cls) -> tuple[str, ...]:
        """允许继续收货的状态。"""
        return (cls.APPROVED, cls.PARTIALLY_RECEIVED)


class ReceiptStatus(models.TextChoices):
    DRAFT = "draft", "草稿"
    POSTED = "posted", "已收货待检"
    INSPECTED = "inspected", "已检验"
    CANCELLED = "cancelled", "已取消"


class InspectionResult(models.TextChoices):
    NONE = "none", "未检验"
    QUALIFIED = "qualified", "合格放行"
    REJECTED = "rejected", "判为不合格"


class PurchaseRequisition(CompanyScopedModel):
    """采购申请。提交后进入审批，批准与否由 `workflow` 回写。"""

    requisition_no = models.CharField("申请单号", max_length=32)
    request_type = models.CharField(
        "申请类型",
        max_length=16,
        choices=RequisitionType.choices,
        default=RequisitionType.NORMAL,
        db_index=True,
    )
    status = models.CharField(
        "状态",
        max_length=16,
        choices=RequisitionStatus.choices,
        default=RequisitionStatus.DRAFT,
        db_index=True,
    )
    applicant = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="申请人",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="purchase_requisitions",
    )
    department = models.ForeignKey(
        "factory.Department",
        verbose_name="申请部门",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    factory = models.ForeignKey(
        "factory.Factory",
        verbose_name="需求工厂",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    needed_date = models.DateField("需求日期", null=True, blank=True, db_index=True)
    purpose = models.CharField("用途说明", max_length=255, blank=True, default="")
    approval_instance_id = models.PositiveBigIntegerField("审批实例", null=True, blank=True)
    approved_at = models.DateTimeField("批准时间", null=True, blank=True)
    remark = models.TextField("备注", blank=True, default="")

    class Meta:
        verbose_name = "采购申请"
        verbose_name_plural = "采购申请"
        ordering = ["-id"]
        constraints = [
            models.UniqueConstraint(fields=["company", "requisition_no"], name="uq_requisition_company_no"),
        ]
        indexes = [models.Index(fields=["company", "status"], name="idx_requisition_status")]

    def __str__(self) -> str:
        return self.requisition_no


class PurchaseRequisitionLine(BaseModel):
    """采购申请明细。"""

    requisition = models.ForeignKey(PurchaseRequisition, on_delete=models.CASCADE, related_name="lines")
    line_no = models.PositiveIntegerField("行号")
    material = models.ForeignKey(
        "masterdata.Material",
        verbose_name="物料",
        on_delete=models.PROTECT,
        related_name="+",
        db_index=True,
    )
    quantity = quantity_field("申请数量")
    uom = models.ForeignKey(
        "masterdata.UoM",
        verbose_name="单位",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    needed_date = models.DateField("需求日期", null=True, blank=True)
    suggested_supplier = models.ForeignKey(
        "srm.Supplier",
        verbose_name="建议供应商",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    ordered_quantity = quantity_field("已转订单数量", default=0)
    remark = models.CharField("备注", max_length=255, blank=True, default="")

    class Meta:
        verbose_name = "采购申请明细"
        verbose_name_plural = "采购申请明细"
        ordering = ["requisition_id", "line_no"]
        constraints = [
            models.UniqueConstraint(fields=["requisition", "line_no"], name="uq_requisition_line_no"),
            models.CheckConstraint(condition=Q(quantity__gt=0), name="ck_requisition_line_quantity_positive"),
        ]

    def __str__(self) -> str:
        return f"{self.requisition_id}-{self.line_no}"


class PurchaseOrder(CompanyScopedModel):
    """采购订单。

    金额口径：行 `amount` = 数量 × 未税单价；单头 `total_amount` = Σ 行金额（未税）；
    `tax_amount` = Σ round(行金额 × 税率, 4)；`amount_with_tax` = 两者之和。
    舍入使用 `ROUND_HALF_UP`，统一在服务层 `recalculate_order_amounts()` 完成，
    **不由前端计算或提交**（任务书 5.3）。
    """

    order_no = models.CharField("订单号", max_length=32)
    supplier = models.ForeignKey(
        "srm.Supplier",
        verbose_name="供应商",
        on_delete=models.PROTECT,
        related_name="purchase_orders",
        db_index=True,
    )
    status = models.CharField(
        "状态",
        max_length=32,
        choices=OrderStatus.choices,
        default=OrderStatus.DRAFT,
        db_index=True,
    )
    source_requisition = models.ForeignKey(
        PurchaseRequisition,
        verbose_name="来源申请",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="purchase_orders",
    )
    buyer = models.ForeignKey(
        "factory.Employee",
        verbose_name="采购员",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    order_date = models.DateField("下单日期", null=True, blank=True, db_index=True)
    expected_date = models.DateField("期望到货日期", null=True, blank=True)
    warehouse = models.ForeignKey(
        "wms.Warehouse",
        verbose_name="收货仓库",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
        help_text="收货单的默认收货仓库；收货行可单独覆盖。",
    )
    currency = models.CharField("币种", max_length=8, default="CNY")
    tax_rate = rate_field("税率(%)", default=0)
    payment_terms = models.CharField("结算方式", max_length=64, blank=True, default="")
    total_amount = money_field("未税金额", default=0)
    tax_amount = money_field("税额", default=0)
    amount_with_tax = money_field("价税合计", default=0)
    supplier_exception = models.BooleanField(
        "供应商例外授权", default=False, help_text="对未准入/已停用供应商下单时置位，需专用权限并留痕。"
    )
    supplier_exception_reason = models.TextField("例外原因", blank=True, default="")
    approval_instance_id = models.PositiveBigIntegerField("审批实例", null=True, blank=True)
    approved_at = models.DateTimeField("批准时间", null=True, blank=True)
    closed_at = models.DateTimeField("关闭时间", null=True, blank=True)
    remark = models.TextField("备注", blank=True, default="")

    class Meta:
        verbose_name = "采购订单"
        verbose_name_plural = "采购订单"
        ordering = ["-id"]
        constraints = [
            models.UniqueConstraint(fields=["company", "order_no"], name="uq_order_company_no"),
            models.CheckConstraint(
                condition=Q(tax_rate__gte=0) & Q(tax_rate__lte=100),
                name="ck_order_tax_rate_range",
            ),
        ]
        indexes = [
            models.Index(fields=["company", "status"], name="idx_order_status"),
            models.Index(fields=["supplier"], name="idx_order_supplier"),
        ]

    def __str__(self) -> str:
        return self.order_no


class PurchaseOrderLine(BaseModel):
    """采购订单明细。`received_quantity` 由收货过账累计，**不得由前端直接写入**。"""

    order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name="lines")
    line_no = models.PositiveIntegerField("行号")
    material = models.ForeignKey(
        "masterdata.Material",
        verbose_name="物料",
        on_delete=models.PROTECT,
        related_name="+",
        db_index=True,
    )
    quantity = quantity_field("订单数量")
    received_quantity = quantity_field("已收货数量", default=0)
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
    expected_date = models.DateField("期望到货日期", null=True, blank=True)
    warehouse = models.ForeignKey(
        "wms.Warehouse",
        verbose_name="收货仓库",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    source_line = models.ForeignKey(
        PurchaseRequisitionLine,
        verbose_name="来源申请行",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="order_lines",
    )
    remark = models.CharField("备注", max_length=255, blank=True, default="")

    class Meta:
        verbose_name = "采购订单明细"
        verbose_name_plural = "采购订单明细"
        ordering = ["order_id", "line_no"]
        constraints = [
            models.UniqueConstraint(fields=["order", "line_no"], name="uq_order_line_no"),
            models.CheckConstraint(condition=Q(quantity__gt=0), name="ck_order_line_quantity_positive"),
            models.CheckConstraint(
                condition=Q(received_quantity__gte=0), name="ck_order_line_received_non_negative"
            ),
            models.CheckConstraint(
                condition=Q(received_quantity__lte=models.F("quantity")),
                name="ck_order_line_received_within_quantity",
            ),
        ]

    @property
    def remaining_quantity(self):
        return self.quantity - self.received_quantity

    def __str__(self) -> str:
        return f"{self.order_id}-{self.line_no}"


class GoodsReceipt(CompanyScopedModel):
    """到货收货单。

    状态机：`draft → posted（已收货待检）→ inspected（已检验）`，草稿可 `cancelled`。

    * `post` 调用统一库存服务把实物到货**记账为待检库存**；
    * `inspect` 调用统一库存服务做**质量放行**（待检 → 合格或不合格）。

    两者是**不同动作**：只有 `inspect` 放行后的库存才能被领用或销售
    （WMS 侧对 `issue` 强制要求合格状态）。
    """

    receipt_no = models.CharField("收货单号", max_length=32)
    purchase_order = models.ForeignKey(
        PurchaseOrder,
        verbose_name="采购订单",
        on_delete=models.PROTECT,
        related_name="receipts",
        db_index=True,
    )
    supplier = models.ForeignKey(
        "srm.Supplier",
        verbose_name="供应商",
        on_delete=models.PROTECT,
        related_name="+",
        db_index=True,
    )
    status = models.CharField(
        "状态",
        max_length=16,
        choices=ReceiptStatus.choices,
        default=ReceiptStatus.DRAFT,
        db_index=True,
    )
    warehouse = models.ForeignKey(
        "wms.Warehouse",
        verbose_name="收货仓库",
        on_delete=models.PROTECT,
        related_name="+",
    )
    received_at = models.DateTimeField("收货时间", null=True, blank=True)
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="收货人",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    supplier_delivery_no = models.CharField("供应商送货单号", max_length=64, blank=True, default="")
    inspection_result = models.CharField(
        "检验结论",
        max_length=16,
        choices=InspectionResult.choices,
        default=InspectionResult.NONE,
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
    # 库存单据引用：用于幂等与追溯（哪个收货单生成了哪张库存单）
    receipt_document_id = models.PositiveBigIntegerField("入库库存单据", null=True, blank=True)
    quality_document_id = models.PositiveBigIntegerField("质量转换单据", null=True, blank=True)
    remark = models.TextField("备注", blank=True, default="")

    class Meta:
        verbose_name = "采购收货单"
        verbose_name_plural = "采购收货单"
        ordering = ["-id"]
        constraints = [
            models.UniqueConstraint(fields=["company", "receipt_no"], name="uq_receipt_company_no"),
        ]
        indexes = [
            models.Index(fields=["purchase_order", "status"], name="idx_receipt_order_status"),
        ]

    def __str__(self) -> str:
        return self.receipt_no


class GoodsReceiptLine(BaseModel):
    """收货明细。数量不得超过对应订单行的未收数量。"""

    receipt = models.ForeignKey(GoodsReceipt, on_delete=models.CASCADE, related_name="lines")
    line_no = models.PositiveIntegerField("行号")
    order_line = models.ForeignKey(
        PurchaseOrderLine,
        verbose_name="订单行",
        on_delete=models.PROTECT,
        related_name="receipt_lines",
    )
    material = models.ForeignKey(
        "masterdata.Material",
        verbose_name="物料",
        on_delete=models.PROTECT,
        related_name="+",
        db_index=True,
    )
    quantity = quantity_field("收货数量")
    location = models.ForeignKey(
        "wms.Location",
        verbose_name="收货储位",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
        help_text="为空表示仅记入仓库不指定储位（库存维度使用空储位）。",
    )
    batch_no = models.CharField("批次号", max_length=64, blank=True, default="")
    roll_no = models.CharField("卷号", max_length=64, blank=True, default="")
    remark = models.CharField("备注", max_length=255, blank=True, default="")

    class Meta:
        verbose_name = "采购收货明细"
        verbose_name_plural = "采购收货明细"
        ordering = ["receipt_id", "line_no"]
        constraints = [
            models.UniqueConstraint(fields=["receipt", "line_no"], name="uq_receipt_line_no"),
            models.CheckConstraint(condition=Q(quantity__gt=0), name="ck_receipt_line_quantity_positive"),
        ]

    def __str__(self) -> str:
        return f"{self.receipt_id}-{self.line_no}"
