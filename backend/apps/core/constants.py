"""数值与业务常量。

统一数值精度，禁止用 Python float 累计金额与库存；
API 的 Decimal 一律以字符串输出（见 REST_FRAMEWORK.COERCE_DECIMAL_TO_STRING）。
"""

from __future__ import annotations

from typing import Any

from django.db import models

# 数量：按国际单位与服饰行业计量习惯保留 6 位小数
QUANTITY_MAX_DIGITS = 20
QUANTITY_DECIMAL_PLACES = 6

# 单价：保留 6 位小数，避免多次换算后失真
PRICE_MAX_DIGITS = 20
PRICE_DECIMAL_PLACES = 6

# 金额：保留 4 位小数，最终业务金额由后端计算与校验
MONEY_MAX_DIGITS = 20
MONEY_DECIMAL_PLACES = 4

# 比率 / 换算率
RATE_MAX_DIGITS = 18
RATE_DECIMAL_PLACES = 10

# 能源读数：按仪表精度单独定义
METER_READING_MAX_DIGITS = 20
METER_READING_DECIMAL_PLACES = 6


def quantity_field(*args: Any, **kwargs: Any) -> models.DecimalField:
    kwargs.setdefault("max_digits", QUANTITY_MAX_DIGITS)
    kwargs.setdefault("decimal_places", QUANTITY_DECIMAL_PLACES)
    return models.DecimalField(*args, **kwargs)


def price_field(*args: Any, **kwargs: Any) -> models.DecimalField:
    kwargs.setdefault("max_digits", PRICE_MAX_DIGITS)
    kwargs.setdefault("decimal_places", PRICE_DECIMAL_PLACES)
    return models.DecimalField(*args, **kwargs)


def money_field(*args: Any, **kwargs: Any) -> models.DecimalField:
    kwargs.setdefault("max_digits", MONEY_MAX_DIGITS)
    kwargs.setdefault("decimal_places", MONEY_DECIMAL_PLACES)
    return models.DecimalField(*args, **kwargs)


def rate_field(*args: Any, **kwargs: Any) -> models.DecimalField:
    kwargs.setdefault("max_digits", RATE_MAX_DIGITS)
    kwargs.setdefault("decimal_places", RATE_DECIMAL_PLACES)
    return models.DecimalField(*args, **kwargs)


def reading_field(*args: Any, **kwargs: Any) -> models.DecimalField:
    """能源仪表读数（表底值、用量、阈值）。精度见 METER_READING_*。"""
    kwargs.setdefault("max_digits", METER_READING_MAX_DIGITS)
    kwargs.setdefault("decimal_places", METER_READING_DECIMAL_PLACES)
    return models.DecimalField(*args, **kwargs)
