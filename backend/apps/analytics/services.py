"""工作台指标。

所有指标都从业务数据实时计算，不使用写死的演示数字。
每张卡片都声明数据来源、统计口径与权限编码，缺失权限的卡片不返回。
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from django.db.models import QuerySet
from django.utils import timezone

from apps.core.selectors import is_action_allowed, scoped_queryset


def _card(
    *,
    key: str,
    label: str,
    value: int | None,
    source: str,
    time_field: str,
    scope: str,
    permission: str,
) -> dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "value": value,
        "definition": {
            "source": source,
            "time_field": time_field,
            "scope": scope,
            "excludes_cancelled": True,
            "updated_at": timezone.now().isoformat(),
            "permission": permission,
        },
    }


def _scoped_count(user, queryset: QuerySet, **fields: str | None) -> int:
    return scoped_queryset(queryset, user, **fields).count()


def dashboard(user: Any) -> dict[str, Any]:
    from apps.factory.models import Department, Employee, Factory, ProductionLine, Workshop
    from apps.identity.models import User
    from apps.masterdata.models import Material, Sku, Style
    from apps.wms.models import Location, Warehouse
    from apps.workflow.selectors import my_instances_queryset, todo_queryset

    cards: list[dict[str, Any]] = []

    if is_action_allowed(user, "masterdata.material.view"):
        cards.append(
            _card(
                key="materials",
                label="物料档案",
                value=_scoped_count(user, Material.objects.filter(is_active=True), company_field="company_id"),
                source="masterdata.Material",
                time_field="created_at",
                scope="当前用户数据范围内的启用物料",
                permission="masterdata.material.view",
            )
        )
    if is_action_allowed(user, "masterdata.sku.view"):
        cards.append(
            _card(
                key="skus",
                label="SKU",
                value=_scoped_count(user, Sku.objects.filter(is_active=True), company_field="company_id"),
                source="masterdata.Sku",
                time_field="created_at",
                scope="当前用户数据范围内的启用 SKU",
                permission="masterdata.sku.view",
            )
        )
    if is_action_allowed(user, "masterdata.style.view"):
        cards.append(
            _card(
                key="styles",
                label="款式",
                value=_scoped_count(user, Style.objects.filter(is_active=True), company_field="company_id"),
                source="masterdata.Style",
                time_field="created_at",
                scope="当前用户数据范围内的启用款式",
                permission="masterdata.style.view",
            )
        )
    if is_action_allowed(user, "wms.warehouse.view"):
        cards.append(
            _card(
                key="warehouses",
                label="仓库",
                value=_scoped_count(
                    user,
                    Warehouse.objects.filter(is_active=True),
                    company_field="company_id",
                    factory_field="factory_id",
                    warehouse_field="id",
                ),
                source="wms.Warehouse",
                time_field="created_at",
                scope="当前用户数据范围内的启用仓库",
                permission="wms.warehouse.view",
            )
        )
    if is_action_allowed(user, "wms.location.view"):
        cards.append(
            _card(
                key="locations",
                label="储位",
                value=_scoped_count(
                    user,
                    Location.objects.filter(is_active=True),
                    company_field="zone__warehouse__company_id",
                    factory_field="zone__warehouse__factory_id",
                    warehouse_field="zone__warehouse_id",
                ),
                source="wms.Location",
                time_field="created_at",
                scope="当前用户数据范围内的启用储位",
                permission="wms.location.view",
            )
        )
    if is_action_allowed(user, "factory.employee.view"):
        cards.append(
            _card(
                key="employees",
                label="在职员工",
                value=_scoped_count(
                    user,
                    Employee.objects.filter(is_active=True, status="active"),
                    company_field="company_id",
                    department_field="department_id",
                    factory_field="factory_id",
                    owner_field="user_id",
                ),
                source="factory.Employee",
                time_field="created_at",
                scope="状态为在职且启用的员工",
                permission="factory.employee.view",
            )
        )
    if is_action_allowed(user, "identity.user.view"):
        cards.append(
            _card(
                key="users",
                label="启用账号",
                value=_scoped_count(
                    user,
                    User.objects.filter(is_active=True),
                    company_field="company_id",
                    department_field="department_id",
                    owner_field="id",
                ),
                source="identity.User",
                time_field="date_joined",
                scope="启用状态的可登录账号",
                permission="identity.user.view",
            )
        )

    # 组织结构规模
    if is_action_allowed(user, "factory.department.view"):
        cards.append(
            _card(
                key="departments",
                label="部门",
                value=_scoped_count(
                    user, Department.objects.filter(is_active=True),
                    company_field="company_id", department_field="id",
                ),
                source="factory.Department",
                time_field="created_at",
                scope="启用部门",
                permission="factory.department.view",
            )
        )
    if is_action_allowed(user, "factory.factory.view"):
        cards.append(
            _card(
                key="factories",
                label="工厂",
                value=_scoped_count(
                    user, Factory.objects.filter(is_active=True),
                    company_field="company_id", factory_field="id",
                ),
                source="factory.Factory",
                time_field="created_at",
                scope="启用工厂",
                permission="factory.factory.view",
            )
        )
    if is_action_allowed(user, "factory.workshop.view"):
        cards.append(
            _card(
                key="workshops",
                label="车间",
                value=_scoped_count(
                    user, Workshop.objects.filter(is_active=True),
                    company_field="factory__company_id", factory_field="factory_id",
                ),
                source="factory.Workshop",
                time_field="created_at",
                scope="启用车间",
                permission="factory.workshop.view",
            )
        )
    if is_action_allowed(user, "factory.line.view"):
        cards.append(
            _card(
                key="lines",
                label="线体",
                value=_scoped_count(
                    user, ProductionLine.objects.filter(is_active=True),
                    company_field="workshop__factory__company_id",
                    factory_field="workshop__factory_id",
                ),
                source="factory.ProductionLine",
                time_field="created_at",
                scope="启用线体",
                permission="factory.line.view",
            )
        )

    todo_count = todo_queryset(user).count() if is_action_allowed(user, "workflow.instance.view") else None
    my_pending = (
        my_instances_queryset(user).filter(status="pending").count()
        if is_action_allowed(user, "workflow.instance.view")
        else None
    )

    recent_activity = _recent_activity(user)
    return {
        "generated_at": timezone.now().isoformat(),
        "business_timezone": timezone.get_current_timezone_name(),
        "cards": cards,
        "approval": {"todo": todo_count, "my_submitted_pending": my_pending},
        "recent_activity": recent_activity,
    }


def _recent_activity(user: Any, limit: int = 10) -> list[dict[str, Any]]:
    """最近业务动态：来自审计日志，按数据范围过滤。"""
    from apps.core.models import AuditLog

    if not is_action_allowed(user, "core.audit.view"):
        # 无审计查看权限时退化为“本人最近操作”，不泄露他人行为
        queryset = AuditLog.objects.filter(actor=user)
    else:
        queryset = scoped_queryset(
            AuditLog.objects.all(), user, company_field="company_id", owner_field="actor_id"
        )
    rows = queryset.order_by("-id")[:limit]
    return [
        {
            "id": row.id,
            "action": row.action,
            "object_type": row.object_type,
            "object_repr": row.object_repr,
            "actor_name": row.actor_name,
            "created_at": row.created_at.isoformat(),
        }
        for row in rows
    ]


def masterdata_freshness(user: Any, days: int = 7) -> dict[str, Any]:
    """近 N 天主数据新增量，用于判断数据维护活跃度。"""
    from apps.masterdata.models import Material, Sku, Style

    since = timezone.now() - timedelta(days=days)
    result: dict[str, Any] = {"since": since.isoformat(), "days": days}
    for key, queryset, fields in (
        ("materials", Material.objects.filter(created_at__gte=since), {"company_field": "company_id"}),
        ("styles", Style.objects.filter(created_at__gte=since), {"company_field": "company_id"}),
        ("skus", Sku.objects.filter(created_at__gte=since), {"company_field": "company_id"}),
    ):
        result[key] = scoped_queryset(queryset, user, **fields).count()  # type: ignore[arg-type]
    return result
