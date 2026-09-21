"""用户 / 角色 / 菜单查询。"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from apps.identity.models import Menu, Permission, Role
from apps.identity.permissions_registry import module_label


def build_menu_tree(menus: Iterable[Menu]) -> list[dict[str, Any]]:
    """把扁平菜单列表组装为树。

    若某菜单的上级未在集合中（例如父目录未授权），则提升为顶层节点，
    避免子菜单凭空消失。
    """
    menu_list = list(menus)
    nodes: dict[int, dict[str, Any]] = {}
    for menu in menu_list:
        nodes[menu.id] = {
            "id": menu.id,
            "code": menu.code,
            "name": menu.name,
            "parent_id": menu.parent_id,
            "path": menu.path,
            "component": menu.component,
            "icon": menu.icon,
            "menu_type": menu.menu_type,
            "sort_order": menu.sort_order,
            "visible": menu.visible,
            "permission_code": menu.permission_code,
            "children": [],
        }
    roots: list[dict[str, Any]] = []
    for menu in menu_list:
        node = nodes[menu.id]
        parent = nodes.get(menu.parent_id) if menu.parent_id else None
        if parent is None:
            roots.append(node)
        else:
            parent["children"].append(node)
    return roots


VISIBLE_MENU_TYPES = ("directory", "page")


def _with_ancestor_directories(menu_ids: set[int]) -> set[int]:
    """补齐上级目录，避免子菜单被提升为顶层、导航分组错乱。"""
    result = set(menu_ids)
    frontier = set(
        Menu.objects.filter(id__in=menu_ids)
        .exclude(parent_id__isnull=True)
        .values_list("parent_id", flat=True)
    )
    for _ in range(16):  # 层级有限，防御性上限
        frontier -= result
        if not frontier:
            break
        result |= frontier
        frontier = set(
            Menu.objects.filter(id__in=frontier)
            .exclude(parent_id__isnull=True)
            .values_list("parent_id", flat=True)
        )
    return result


def my_menu_queryset(user: Any):
    """当前用户可见的菜单（含可见页面的上级目录）。"""
    if getattr(user, "is_superuser", False):
        return Menu.objects.filter(is_active=True, menu_type__in=VISIBLE_MENU_TYPES)
    role_ids = list(user.roles.filter(is_active=True).values_list("id", flat=True))
    if not role_ids:
        return Menu.objects.none()
    granted = set(
        Menu.objects.filter(
            is_active=True, roles__id__in=role_ids, menu_type__in=VISIBLE_MENU_TYPES
        ).values_list("id", flat=True)
    )
    if not granted:
        return Menu.objects.none()
    return Menu.objects.filter(id__in=_with_ancestor_directories(granted), is_active=True)


def permission_groups() -> list[dict[str, Any]]:
    """按模块分组的权限点，供角色配置界面使用。"""
    groups: dict[str, dict[str, Any]] = {}
    for permission in Permission.objects.all().order_by("module", "resource", "action"):
        group = groups.setdefault(
            permission.module,
            {
                "module": permission.module,
                # 一级分组的中文名，界面显示为「模块编码（中文名）」
                "module_name": module_label(permission.module),
                "permissions": [],
            },
        )
        group["permissions"].append(
            {
                "code": permission.code,
                "name": permission.name,
                "resource": permission.resource,
                "action": permission.action,
                "permission_type": permission.permission_type,
            }
        )
    return list(groups.values())


def roles_for_user(user: Any):
    return Role.objects.filter(user_links__user=user).distinct()
