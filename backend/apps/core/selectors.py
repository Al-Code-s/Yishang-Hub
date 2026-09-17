"""查询与数据范围过滤。

数据范围（data scope）是四层权限中的第四层，必须在后端强制生效：
列表查询、详情访问、关联对象校验、导出与异步任务都复用同一套规则。

合并规则（与 docs/permission-matrix.md 保持一致）：
1. 超级管理员不受限制；
2. 同一用户多个角色时，操作权限取并集；
3. 数据范围取“最宽”的一档；同档次内取各角色授权范围的并集；
4. 先施加公司边界，再施加更细的组织维度；
5. 自定义范围在各维度之间取并集；
6. 单一维度范围（工厂/部门/仓库）若模型上没有对应字段，则返回空集（就严不就宽）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import reduce
from operator import and_, or_
from typing import Any

from django.db.models import Q, QuerySet

from apps.core.exceptions import NotPermitted

EMPTY_SCOPE_TYPE = "none"

SINGLE_DIMENSION_SCOPES = {"factory", "department", "warehouse"}


@dataclass(frozen=True)
class DataScope:
    """解析后的数据范围描述。"""

    scope_type: str
    user_id: int | None = None
    company_ids: frozenset[int] = field(default_factory=frozenset)
    factory_ids: frozenset[int] = field(default_factory=frozenset)
    department_ids: frozenset[int] = field(default_factory=frozenset)
    warehouse_ids: frozenset[int] = field(default_factory=frozenset)

    @property
    def is_unrestricted(self) -> bool:
        from apps.identity.models import DataScopeType

        return self.scope_type == DataScopeType.ALL


def restricted_scope() -> DataScope:
    """无任何可见范围（未登录、无角色、授权维度缺失时使用）。"""
    return DataScope(scope_type=EMPTY_SCOPE_TYPE)


def _department_descendants(root_ids: set[int]) -> set[int]:
    """展开部门子树。层级不深，使用迭代查询即可。"""
    from apps.factory.models import Department

    result: set[int] = set(root_ids)
    frontier = set(root_ids)
    for _ in range(32):  # 防御性深度上限，避免脏数据造成死循环
        if not frontier:
            break
        children = set(
            Department.objects.filter(parent_id__in=frontier).values_list("id", flat=True)
        )
        new_ids = children - result
        result |= new_ids
        frontier = new_ids
    return result


def resolve_data_scope(user: Any) -> DataScope:
    """解析用户的最终数据范围。"""
    from apps.identity.models import DataScopeType, RoleScopeGrant, ScopeDimension

    if user is None or not getattr(user, "is_authenticated", False):
        return restricted_scope()
    if getattr(user, "is_superuser", False):
        return DataScope(scope_type=DataScopeType.ALL, user_id=user.pk)

    roles = list(user.active_roles())
    if not roles:
        return restricted_scope()

    rank = DataScopeType.rank_map()
    effective = max(roles, key=lambda role: rank.get(role.data_scope_type, 0))
    scope_type = effective.data_scope_type

    if scope_type == DataScopeType.ALL:
        return DataScope(scope_type=DataScopeType.ALL, user_id=user.pk)

    # 公司边界：收敛到用户归属公司 + 角色声明的公司
    company_ids: set[int] = set()
    if getattr(user, "company_id", None):
        company_ids.add(user.company_id)
    company_ids |= {role.company_id for role in roles if role.company_id}

    same_rank_roles = [role for role in roles if role.data_scope_type == scope_type]
    grants = RoleScopeGrant.objects.filter(role__in=same_rank_roles)

    def granted(dimension: str) -> set[int]:
        return {grant.object_id for grant in grants if grant.dimension == dimension}

    factory_ids: set[int] = set()
    department_ids: set[int] = set()
    warehouse_ids: set[int] = set()

    if scope_type == DataScopeType.COMPANY:
        pass
    elif scope_type == DataScopeType.CUSTOM:
        company_ids |= granted(ScopeDimension.COMPANY)
        factory_ids = granted(ScopeDimension.FACTORY)
        department_ids = _department_descendants(granted(ScopeDimension.DEPARTMENT))
        warehouse_ids = granted(ScopeDimension.WAREHOUSE)
        if not (factory_ids or department_ids or warehouse_ids):
            # 自定义范围却没有授权任何组织对象：按公司收敛，避免越权
            pass
    elif scope_type == DataScopeType.FACTORY:
        factory_ids = granted(ScopeDimension.FACTORY)
        if not factory_ids:
            return restricted_scope()
    elif scope_type == DataScopeType.DEPARTMENT:
        department_ids = granted(ScopeDimension.DEPARTMENT)
        if not department_ids:
            return restricted_scope()
        department_ids = _department_descendants(department_ids)
    elif scope_type == DataScopeType.WAREHOUSE:
        warehouse_ids = granted(ScopeDimension.WAREHOUSE)
        if not warehouse_ids:
            return restricted_scope()
    elif scope_type == DataScopeType.SELF:
        return DataScope(scope_type=DataScopeType.SELF, user_id=user.pk)

    return DataScope(
        scope_type=scope_type,
        user_id=user.pk,
        company_ids=frozenset(company_ids),
        factory_ids=frozenset(factory_ids),
        department_ids=frozenset(department_ids),
        warehouse_ids=frozenset(warehouse_ids),
    )


def apply_data_scope(
    queryset: QuerySet,
    scope: DataScope,
    *,
    company_field: str | None = "company_id",
    factory_field: str | None = None,
    department_field: str | None = None,
    warehouse_field: str | None = None,
    owner_field: str | None = "created_by_id",
) -> QuerySet:
    """把数据范围转换成查询条件。找不到可用维度时返回空集（fail closed）。"""
    from apps.identity.models import DataScopeType

    if scope.is_unrestricted:
        return queryset
    if scope.scope_type == EMPTY_SCOPE_TYPE:
        return queryset.none()

    if scope.scope_type == DataScopeType.SELF:
        if owner_field:
            return queryset.filter(**{owner_field: scope.user_id})
        return queryset.none()

    conditions: list[Q] = []
    if company_field and scope.company_ids:
        conditions.append(Q(**{f"{company_field}__in": sorted(scope.company_ids)}))

    if scope.scope_type == DataScopeType.COMPANY:
        pass
    elif scope.scope_type in {DataScopeType.FACTORY, DataScopeType.DEPARTMENT, DataScopeType.WAREHOUSE}:
        # 单一维度：必须能在模型上找到对应字段，否则就严不就宽
        field_by_scope = {
            DataScopeType.FACTORY: (factory_field, scope.factory_ids),
            DataScopeType.DEPARTMENT: (department_field, scope.department_ids),
            DataScopeType.WAREHOUSE: (warehouse_field, scope.warehouse_ids),
        }
        target_field, target_ids = field_by_scope[scope.scope_type]
        if not target_field or not target_ids:
            return queryset.none()
        conditions.append(Q(**{f"{target_field}__in": sorted(target_ids)}))
    elif scope.scope_type == DataScopeType.CUSTOM:
        dimension_conditions: list[Q] = []
        for candidate_field, candidate_ids in (
            (factory_field, scope.factory_ids),
            (department_field, scope.department_ids),
            (warehouse_field, scope.warehouse_ids),
        ):
            if candidate_field and candidate_ids:
                dimension_conditions.append(
                    Q(**{f"{candidate_field}__in": sorted(candidate_ids)})
                )
        if dimension_conditions:
            conditions.append(reduce(or_, dimension_conditions))

    if not conditions:
        return queryset.none()
    return queryset.filter(reduce(and_, conditions))


def scoped_queryset(queryset: QuerySet, user: Any, **field_map: str | None) -> QuerySet:
    """便捷入口：解析用户数据范围并过滤查询集。"""
    return apply_data_scope(queryset, resolve_data_scope(user), **field_map)


def assert_in_scope(obj: Any, user: Any, **field_map: str | None) -> None:
    """校验单个对象是否在用户数据范围内，用于关联对象选择校验。"""
    model = type(obj)
    accessible = scoped_queryset(model.objects.filter(pk=obj.pk), user, **field_map).exists()
    if not accessible:
        raise NotPermitted(
            "目标对象不在当前用户的数据范围内。",
            code="OUT_OF_DATA_SCOPE",
            details={"object_type": f"{model._meta.app_label}.{model._meta.object_name}"},
        )


def is_action_allowed(user: Any, code: str) -> bool:
    """供前端按钮级判断与后端二次校验复用的操作权限判断。"""
    return bool(getattr(user, "is_authenticated", False)) and user.has_permission_codes([code])


__all__ = [
    "DataScope",
    "apply_data_scope",
    "assert_in_scope",
    "is_action_allowed",
    "resolve_data_scope",
    "restricted_scope",
    "scoped_queryset",
]
