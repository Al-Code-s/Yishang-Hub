"""统一业务异常与 DRF 异常处理器。

对外错误结构（与 docs/api-conventions.md 保持一致）：

    {
      "code": "INSUFFICIENT_STOCK",
      "message": "可用库存不足",
      "details": {"required": "12.000000", "available": "8.000000"},
      "request_id": "..."
    }
"""

from __future__ import annotations

from typing import Any

from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.http import Http404
from rest_framework import exceptions as drf_exceptions
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

from apps.core.logging import get_request_id


class APIError(Exception):
    """业务异常基类。服务层抛出，由统一处理器转换为标准错误结构。"""

    status_code: int = status.HTTP_400_BAD_REQUEST
    code: str = "BAD_REQUEST"
    default_message: str = "请求无法处理"

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str | None = None,
        status_code: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.message = message or self.default_message
        if code is not None:
            self.code = code
        if status_code is not None:
            self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)


class ValidationFailed(APIError):
    status_code = status.HTTP_400_BAD_REQUEST
    code = "VALIDATION_FAILED"
    default_message = "参数校验未通过"


class ObjectNotFound(APIError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "NOT_FOUND"
    default_message = "对象不存在"


class NotPermitted(APIError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "FORBIDDEN"
    default_message = "没有执行该操作的权限"


class StateConflict(APIError):
    status_code = status.HTTP_409_CONFLICT
    code = "STATE_CONFLICT"
    default_message = "当前状态不允许该操作"


class OptimisticLockConflict(APIError):
    status_code = status.HTTP_409_CONFLICT
    code = "VERSION_CONFLICT"
    default_message = "数据已被他人修改，请刷新后重试"


class IdempotencyConflict(APIError):
    status_code = status.HTTP_409_CONFLICT
    code = "IDEMPOTENCY_KEY_CONFLICT"
    default_message = "幂等标识对应的请求内容不一致"


class InsufficientStock(APIError):
    status_code = status.HTTP_409_CONFLICT
    code = "INSUFFICIENT_STOCK"
    default_message = "可用库存不足"


def _envelope(
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
    status_code: int = status.HTTP_400_BAD_REQUEST,
) -> Response:
    return Response(
        {
            "code": code,
            "message": message,
            "details": details or {},
            "request_id": get_request_id(),
        },
        status=status_code,
    )


def yishang_exception_handler(exc: Exception, context: dict[str, Any]) -> Response | None:
    """DRF EXCEPTION_HANDLER 入口。"""
    if isinstance(exc, APIError):
        return _envelope(exc.code, exc.message, exc.details, exc.status_code)

    if isinstance(exc, Http404):
        return _envelope("NOT_FOUND", "对象不存在", status_code=status.HTTP_404_NOT_FOUND)

    if isinstance(exc, DjangoPermissionDenied):
        return _envelope("FORBIDDEN", "没有执行该操作的权限", status_code=status.HTTP_403_FORBIDDEN)

    if isinstance(exc, drf_exceptions.ValidationError):
        # 字段级错误保留在 details 中，便于前端逐字段提示
        details = exc.detail if isinstance(exc.detail, dict) else {"non_field_errors": exc.detail}
        return _envelope(
            "VALIDATION_FAILED",
            "参数校验未通过",
            _stringify_errors(details),
            status.HTTP_400_BAD_REQUEST,
        )

    if isinstance(exc, drf_exceptions.APIException):
        detail = exc.detail
        message = detail if isinstance(detail, str) else "请求无法处理"
        details = {} if isinstance(detail, str) else {"detail": _stringify_errors(detail)}
        return _envelope(
            getattr(exc, "default_code", "ERROR").upper(),
            message,
            details,
            exc.status_code,
        )

    # 未预期异常交给 Django 记录并返回 500，不在此吞掉堆栈
    return drf_exception_handler(exc, context)


def _stringify_errors(value: Any) -> Any:
    """把 DRF 的 ErrorDetail 递归转为普通字符串。"""
    if isinstance(value, dict):
        return {str(k): _stringify_errors(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_stringify_errors(item) for item in value]
    return str(value)
