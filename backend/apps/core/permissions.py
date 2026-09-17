"""DRF 权限基类：操作权限（permission code）+ 数据范围。"""

from __future__ import annotations

from typing import Any

from rest_framework.permissions import BasePermission

from apps.core.exceptions import NotPermitted
from apps.core.selectors import resolve_data_scope

HTTP_METHOD_ANY = "*"


def required_codes_for(view: Any, request: Any) -> list[str]:
    """从视图上解析本次请求所需的权限编码。

    支持三种声明方式（优先级由高到低）：
    1. {"action_name": ["code", ...]} —— DRF ViewSet 自定义 action
    2. {"GET": ["code"], "POST": [...]} 或 {"*": [...]}
    3. ["code", ...] —— 所有方法一致
    """
    declared = getattr(view, "required_permissions", None)
    if not declared:
        return []
    if isinstance(declared, dict):
        action = getattr(view, "action", None)
        if action and action in declared:
            value = declared[action]
        elif request.method in declared:
            value = declared[request.method]
        elif HTTP_METHOD_ANY in declared:
            value = declared[HTTP_METHOD_ANY]
        else:
            return []
    else:
        value = declared
    if isinstance(value, str):
        return [value]
    return list(value)


class HasRequiredPermissions(BasePermission):
    """校验视图声明的操作权限编码。

    未声明 required_permissions 的视图仅要求登录（默认 IsAuthenticated）。
    """

    message = "没有执行该操作的权限。"

    def has_permission(self, request, view) -> bool:  # type: ignore[override]
        user = request.user
        if user is None or not user.is_authenticated:
            return False
        if getattr(user, "is_superuser", False):
            return True
        codes = required_codes_for(view, request)
        if not codes:
            return True
        return user.has_permission_codes(codes)


def require_codes(user: Any, *codes: str) -> None:
    """在服务/视图中做二次校验，缺失任一编码即拒绝。"""
    if getattr(user, "is_superuser", False):
        return
    if not user.has_permission_codes(list(codes)):
        raise NotPermitted(
            "没有执行该操作的权限。",
            code="PERMISSION_DENIED",
            details={"required": list(codes)},
        )


__all__ = [
    "HasRequiredPermissions",
    "require_codes",
    "required_codes_for",
    "resolve_data_scope",
]
