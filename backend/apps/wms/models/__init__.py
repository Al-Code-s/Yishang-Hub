"""仓储模块模型。

* `master`：仓库、库区、储位（阶段 1）
* `inventory`：库存余额、库存流水、库存单据（阶段 2）

拆分为包结构是为了让库存核心有独立文件承载；对外导入路径保持
`from apps.wms.models import X` 不变。
"""

from __future__ import annotations

from apps.wms.models.inventory import (
    DIMENSION_KEY_LENGTH,
    EMPTY_DIMENSION_TOKEN,
    QUANTITY_DECIMAL_PLACES,
    QUANTITY_MAX_DIGITS,
    Direction,
    DocumentStatus,
    DocumentType,
    ImmutableLedgerError,
    InventoryBalance,
    InventoryDocument,
    InventoryDocumentLine,
    InventoryTransaction,
    QualityStatus,
    ReservationStatus,
    StockReservation,
    TransactionType,
    build_dimension_key,
    normalize_token,
)
from apps.wms.models.master import Location, LocationType, Warehouse, WarehouseType, Zone, ZoneType

__all__ = [
    "DIMENSION_KEY_LENGTH",
    "EMPTY_DIMENSION_TOKEN",
    "QUANTITY_DECIMAL_PLACES",
    "QUANTITY_MAX_DIGITS",
    "Direction",
    "DocumentStatus",
    "DocumentType",
    "ImmutableLedgerError",
    "InventoryBalance",
    "InventoryDocument",
    "InventoryDocumentLine",
    "InventoryTransaction",
    "Location",
    "LocationType",
    "QualityStatus",
    "ReservationStatus",
    "StockReservation",
    "TransactionType",
    "Warehouse",
    "WarehouseType",
    "Zone",
    "ZoneType",
    "build_dimension_key",
    "normalize_token",
]
