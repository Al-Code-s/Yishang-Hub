"""通用视图基类：数据范围过滤 + 审计 + 乐观锁 + 唯一约束友好提示。

各业务模块的 CRUD 视图复用本基类，避免把权限与审计逻辑复制到每个模块。
"""

from __future__ import annotations

from typing import Any

from django.db import IntegrityError, transaction
from rest_framework import serializers as drf_serializers
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.exceptions import StateConflict
from apps.core.models import AuditAction
from apps.core.permissions import HasRequiredPermissions
from apps.core.selectors import assert_in_scope, scoped_queryset
from apps.core.services import (
    assert_version,
    build_changes,
    record_audit,
    snapshot_fields,
)


class ScopedModelViewSet(viewsets.ModelViewSet):
    """按数据范围过滤 + 自动审计的 ModelViewSet。

    子类需要声明：
    * ``scope_fields``：模型上的数据范围字段映射；
    * ``audit_fields``：需要写入审计摘要的字段；
    * ``required_permissions``：各 action 对应的权限编码。
    """

    permission_classes = [HasRequiredPermissions]
    http_method_names = ["get", "post", "patch", "head", "options"]
    # 置为 None 表示该实体是全局共享主数据，不做数据范围收敛
    scope_fields: dict[str, str | None] | None = {"company_field": "company_id"}
    audit_fields: tuple[str, ...] = ()
    uniqueness_error_map: dict[str, str] = {}

    def get_queryset(self):
        base = super().get_queryset()
        if self.scope_fields is None:
            return base
        return scoped_queryset(base, self.request.user, **self.scope_fields)

    # -- 写操作 ----------------------------------------------------------
    def assert_object_in_scope(self, obj) -> None:
        """校验写入后的对象仍落在当前用户的数据范围内。

        外键字段（如 company_id）可写并不等于可以越权：前端传入的组织标识必须
        经过这里的数据范围校验，否则任何人都能借写入接口越过范围限制。
        """
        if self.scope_fields is None:  # 全局共享主数据，不做范围收敛
            return
        assert_in_scope(obj, self.request.user, **self.scope_fields)

    def perform_create(self, serializer) -> None:
        obj = serializer.save()
        self.assert_object_in_scope(obj)
        record_audit(
            action=AuditAction.CREATE,
            instance=obj,
            changes=snapshot_fields(obj, self.audit_fields),
            object_repr=str(obj),
        )

    def perform_update(self, serializer) -> None:
        before = snapshot_fields(serializer.instance, self.audit_fields)
        obj = serializer.save()
        self.assert_object_in_scope(obj)
        after = snapshot_fields(obj, self.audit_fields)
        changes = build_changes(before, after)
        if changes:
            record_audit(
                action=AuditAction.UPDATE, instance=obj, changes=changes, object_repr=str(obj)
            )

    def create(self, request, *args, **kwargs) -> Response:
        try:
            with transaction.atomic():
                return super().create(request, *args, **kwargs)
        except IntegrityError as exc:
            raise self._integrity_conflict(exc) from exc

    def partial_update(self, request, *args, **kwargs) -> Response:
        instance = self.get_object()
        assert_version(instance, request.data.get("expected_version"))
        try:
            with transaction.atomic():
                return super().partial_update(request, *args, **kwargs)
        except IntegrityError as exc:
            raise self._integrity_conflict(exc) from exc

    def _integrity_conflict(self, exc: IntegrityError) -> StateConflict:
        text = str(exc)
        for marker, message in self.uniqueness_error_map.items():
            if marker in text:
                return StateConflict(message, code="DUPLICATED")
        return StateConflict(
            "数据与已有记录冲突（违反唯一约束）。", code="DUPLICATED", details={"hint": text[:200]}
        )

    # -- 通用动作 --------------------------------------------------------
    @action(detail=True, methods=["post"], url_path="set-active")
    def set_active(self, request, *args, **kwargs) -> Response:
        instance = self.get_object()
        is_active = drf_serializers.BooleanField().run_validation(request.data.get("is_active"))
        reason = str(request.data.get("reason", "") or "")
        before = {"is_active": instance.is_active}
        instance.is_active = is_active
        instance.save(update_fields=["is_active", "updated_at"])
        record_audit(
            action=AuditAction.ACTIVATE if is_active else AuditAction.DEACTIVATE,
            instance=instance,
            changes=build_changes(before, {"is_active": is_active}),
            reason=reason,
            object_repr=str(instance),
        )
        return Response(self.get_serializer(instance).data)


class ActiveFilterMixin:
    """支持 ?is_active=true/false 过滤。"""

    def filter_queryset(self, queryset):
        queryset = super().filter_queryset(queryset)  # type: ignore[misc]
        raw = self.request.query_params.get("is_active")  # type: ignore[attr-defined]
        if raw is None or raw == "":
            return queryset
        if raw.lower() in {"1", "true", "yes"}:
            return queryset.filter(is_active=True)
        if raw.lower() in {"0", "false", "no"}:
            return queryset.filter(is_active=False)
        raise StateConflict("is_active 参数取值不合法。", code="INVALID_FILTER")


class ReadOnlyScopedViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [HasRequiredPermissions]
    scope_fields: dict[str, str | None] | None = {"company_field": "company_id"}

    def get_queryset(self):
        base = super().get_queryset()
        if self.scope_fields is None:
            return base
        return scoped_queryset(base, self.request.user, **self.scope_fields)


def as_choice_list(choices: Any) -> list[dict[str, str]]:
    """把 Django choices 转成前端下拉可用的列表。"""
    return [{"value": value, "label": label} for value, label in choices]
