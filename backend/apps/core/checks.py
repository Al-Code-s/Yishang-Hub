"""平台自定义系统检查。

Django 会自动导入各已安装应用的 checks 模块。
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from django.core.checks import Error, register
from django.urls import URLPattern, URLResolver, get_resolver

from apps.identity.permissions_registry import MODULE_LABELS, PERMISSION_CODES


def _iter_callbacks(patterns: list[Any]) -> Iterator[Any]:
    for pattern in patterns:
        if isinstance(pattern, URLResolver):
            yield from _iter_callbacks(list(pattern.url_patterns))
        elif isinstance(pattern, URLPattern):
            yield pattern.callback


def _declared_codes(view_cls: Any) -> set[str]:
    declared = getattr(view_cls, "required_permissions", None)
    if not declared:
        return set()
    values = declared.values() if isinstance(declared, dict) else [declared]
    codes: set[str] = set()
    for value in values:
        if isinstance(value, str):
            codes.add(value)
        else:
            codes.update(value)
    return codes


@register("yishang")
def check_permission_codes(app_configs: Any, **kwargs: Any) -> list[Error]:
    """视图声明的权限编码必须存在于注册表，避免拼写错误导致权限静默失效。"""
    errors: list[Error] = []
    reported: set[tuple[str, str]] = set()
    for callback in _iter_callbacks(list(get_resolver().url_patterns)):
        view_cls = getattr(callback, "cls", None) or getattr(callback, "view_class", None)
        if view_cls is None:
            continue
        for code in _declared_codes(view_cls):
            marker = (view_cls.__name__, code)
            if code in PERMISSION_CODES or marker in reported:
                continue
            reported.add(marker)
            errors.append(
                Error(
                    f"视图 {view_cls.__name__} 声明了未注册的权限编码：{code}",
                    hint="请在 apps/identity/permissions_registry.py 中登记该编码。",
                    obj=view_cls,
                    id="yishang.E001",
                )
            )
    return errors


@register("yishang")
def check_permission_module_labels(app_configs: Any, **kwargs: Any) -> list[Error]:
    """每个权限模块都要有中文名，否则角色配置界面只显示英文模块名。"""
    modules = sorted({code.split(".")[0] for code in PERMISSION_CODES})
    missing = [module for module in modules if module not in MODULE_LABELS]
    if not missing:
        return []
    return [
        Error(
            f"权限模块缺少中文名：{', '.join(missing)}",
            hint=(
                "请在 apps/identity/permissions_registry.py 的 MODULE_LABELS 中登记中文名，"
                "界面一级分组会显示为「模块编码（中文名）」。"
            ),
            id="yishang.E002",
        )
    ]
