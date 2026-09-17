"""仓储主数据：仓库、库区、储位。

阶段 1 仅实现仓库结构主数据；库存余额、库存流水、过账服务、批次/卷号维度属于阶段 2，
其维度唯一约束与并发创建方案见 docs/data-model.md 与 docs/inventory-rules.md。
"""

from __future__ import annotations

from django.db import models

from apps.core.models import BaseModel, CompanyScopedModel


class WarehouseType(models.TextChoices):
    RAW = "raw", "原料仓"
    WIP = "wip", "半成品仓"
    FINISHED = "finished", "成品仓"
    SPARE = "spare", "备件仓"
    CONSUMABLE = "consumable", "耗材仓"
    QUARANTINE = "quarantine", "待检仓"


class Warehouse(CompanyScopedModel):
    factory = models.ForeignKey(
        "factory.Factory",
        verbose_name="所属工厂",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="warehouses",
    )
    department = models.ForeignKey(
        "factory.Department",
        verbose_name="管理部门",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="warehouses",
    )
    code = models.CharField("仓库编码", max_length=32)
    name = models.CharField("仓库名称", max_length=64)
    warehouse_type = models.CharField(
        "仓库类型", max_length=16, choices=WarehouseType.choices, default=WarehouseType.RAW
    )
    address = models.CharField("地址", max_length=255, blank=True, default="")
    manager_name = models.CharField("负责人", max_length=64, blank=True, default="")
    allow_negative_stock = models.BooleanField(
        "允许负库存",
        default=False,
        help_text="默认禁止负库存；即使开启也必须由库存服务显式判定并留痕。",
    )
    is_active = models.BooleanField("启用", default=True, db_index=True)
    remark = models.TextField("备注", blank=True, default="")

    class Meta:
        verbose_name = "仓库"
        verbose_name_plural = "仓库"
        ordering = ["company_id", "code"]
        constraints = [
            models.UniqueConstraint(fields=["company", "code"], name="uq_warehouse_company_code"),
        ]

    def __str__(self) -> str:
        return f"{self.name}({self.code})"


class ZoneType(models.TextChoices):
    RECEIVING = "receiving", "收货区"
    STORAGE = "storage", "存储区"
    PICKING = "picking", "拣货区"
    SHIPPING = "shipping", "发货区"
    QUARANTINE = "quarantine", "待检区"
    RETURN = "return", "退货区"


class Zone(BaseModel):
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="zones")
    code = models.CharField("库区编码", max_length=32)
    name = models.CharField("库区名称", max_length=64)
    zone_type = models.CharField(
        "库区类型", max_length=16, choices=ZoneType.choices, default=ZoneType.STORAGE
    )
    allow_mixed_batch = models.BooleanField("允许混批次", default=False)
    sort_order = models.IntegerField("排序", default=0)
    is_active = models.BooleanField("启用", default=True, db_index=True)
    remark = models.TextField("备注", blank=True, default="")

    class Meta:
        verbose_name = "库区"
        verbose_name_plural = "库区"
        ordering = ["warehouse_id", "sort_order", "id"]
        constraints = [
            models.UniqueConstraint(fields=["warehouse", "code"], name="uq_zone_warehouse_code"),
        ]

    def __str__(self) -> str:
        return f"{self.name}({self.code})"


class LocationType(models.TextChoices):
    SHELF = "shelf", "货架储位"
    FLOOR = "floor", "地面储位"
    RACK = "rack", "托盘位"
    STAGING = "staging", "暂存位"


class Location(BaseModel):
    """储位。code 在同一库区内唯一。"""

    zone = models.ForeignKey(Zone, on_delete=models.PROTECT, related_name="locations")
    code = models.CharField("储位编码", max_length=32)
    name = models.CharField("储位名称", max_length=64, blank=True, default="")
    location_type = models.CharField(
        "储位类型", max_length=16, choices=LocationType.choices, default=LocationType.SHELF
    )
    row_no = models.CharField("排", max_length=16, blank=True, default="")
    column_no = models.CharField("列", max_length=16, blank=True, default="")
    level_no = models.CharField("层", max_length=16, blank=True, default="")
    capacity = models.DecimalField(
        "容量", max_digits=20, decimal_places=6, null=True, blank=True
    )
    is_locked = models.BooleanField(
        "冻结", default=False, help_text="冻结储位不允许新的上架与移入操作。"
    )
    is_active = models.BooleanField("启用", default=True, db_index=True)
    remark = models.TextField("备注", blank=True, default="")

    class Meta:
        verbose_name = "储位"
        verbose_name_plural = "储位"
        ordering = ["zone_id", "code"]
        constraints = [
            models.UniqueConstraint(fields=["zone", "code"], name="uq_location_zone_code"),
        ]
        indexes = [models.Index(fields=["zone", "is_active"], name="idx_location_zone_active")]

    def __str__(self) -> str:
        return f"{self.zone.code}/{self.code}"
