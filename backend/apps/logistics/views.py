"""生产物流接口：设备台账 + 任务状态机 + 只读操作日志。"""

from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.models import AuditAction
from apps.core.services import record_audit
from apps.core.viewsets import ActiveFilterMixin, ReadOnlyScopedViewSet, ScopedModelViewSet
from apps.logistics import services
from apps.logistics.models import AutomationDevice, LogisticsOperationLog, LogisticsTask
from apps.logistics.serializers import (
    AutomationDeviceSerializer,
    DeviceStatusSerializer,
    LogisticsOperationLogSerializer,
    LogisticsTaskSerializer,
    TaskCancelSerializer,
    TaskDispatchSerializer,
    TaskFinishSerializer,
    TaskStartSerializer,
)


class AutomationDeviceViewSet(ActiveFilterMixin, ScopedModelViewSet):
    queryset = AutomationDevice.objects.select_related("company", "workshop").all()
    serializer_class = AutomationDeviceSerializer
    scope_fields = {"company_field": "company_id"}
    audit_fields = (
        "code", "name", "device_type", "workshop_id", "location", "max_load", "speed",
        "battery_level", "is_active",
    )
    search_fields = ["code", "name", "location"]
    filterset_fields = ["company_id", "device_type", "status", "workshop_id"]
    ordering_fields = ["id", "code", "name", "battery_level", "next_maintenance_date"]
    uniqueness_error_map = {"uq_automation_device_company_code": "同一公司下设备编号已存在。"}
    required_permissions = {
        "list": "logistics.device.view",
        "retrieve": "logistics.device.view",
        "create": "logistics.device.create",
        "partial_update": "logistics.device.update",
        "set_active": "logistics.device.update",
        "set_status": "logistics.device.update",
    }

    def perform_create(self, serializer) -> None:
        """设备编号留空时按编码规则（AD）自动取号。"""
        code = str(serializer.validated_data.get("code") or "").strip()
        serializer.validated_data["code"] = code or services.next_device_code()
        super().perform_create(serializer)

    @extend_schema(request=DeviceStatusSerializer, responses={200: AutomationDeviceSerializer})
    @action(detail=True, methods=["post"], url_path="set-status")
    def set_status(self, request, *args, **kwargs) -> Response:
        """变更设备状态（故障 / 充电 / 保养 / 空闲），并写操作日志。"""
        device = self.get_object()
        payload = DeviceStatusSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        updated = services.set_device_status(
            device,
            data["status"],
            operator=data.get("operator_id"),
            detail=data.get("detail") or "",
            battery_level=data.get("battery_level"),
        )
        record_audit(
            action=AuditAction.UPDATE,
            instance=updated,
            changes={"status": updated.status, "battery_level": updated.battery_level},
            object_repr=str(updated),
        )
        return Response(self.get_serializer(updated).data)


class LogisticsTaskViewSet(ActiveFilterMixin, ScopedModelViewSet):
    queryset = LogisticsTask.objects.select_related(
        "company", "device", "warehouse", "from_location", "to_location", "material",
        "requested_by", "assignee",
    ).all()
    serializer_class = LogisticsTaskSerializer
    scope_fields = {"company_field": "company_id"}
    audit_fields = (
        "task_no", "task_type", "device_id", "priority", "warehouse_id", "from_location_id",
        "to_location_id", "material_id", "quantity", "container_no", "assignee_id",
    )
    search_fields = ["task_no", "container_no", "device__code", "device__name"]
    filterset_fields = ["company_id", "task_type", "status", "priority", "device_id", "warehouse_id"]
    ordering_fields = ["id", "task_no", "priority", "planned_at", "created_at"]
    uniqueness_error_map = {"uq_logistics_task_company_no": "同一公司下任务编号已存在。"}
    required_permissions = {
        "list": "logistics.task.view",
        "retrieve": "logistics.task.view",
        "create": "logistics.task.create",
        "partial_update": "logistics.task.update",
        "set_active": "logistics.task.update",
        "dispatch_task": "logistics.task.update",
        "start": "logistics.task.execute",
        "finish": "logistics.task.execute",
        "cancel": "logistics.task.update",
    }

    def perform_create(self, serializer) -> None:
        """任务编号留空时按编码规则（LT）自动取号，并写一条创建日志。"""
        data = serializer.validated_data
        data["task_no"] = str(data.get("task_no") or "").strip() or services.next_task_no()
        super().perform_create(serializer)
        task = serializer.instance
        services.log_operation(
            company_id=task.company_id,
            action="create",
            device=task.device,
            task=task,
            operator=task.requested_by,
            detail=f"创建任务 {task.task_no}",
        )

    @extend_schema(request=TaskDispatchSerializer, responses={200: LogisticsTaskSerializer})
    @action(detail=True, methods=["post"], url_path="dispatch")
    def dispatch_task(self, request, *args, **kwargs) -> Response:
        """下发任务：待下发 -> 已下发（可同时指定执行设备与计划时间）。

        方法名刻意不叫 `dispatch`：那会覆盖 `APIView.dispatch`，
        导致整个视图集都无法响应请求。对外 URL 仍是 `.../dispatch/`。
        """
        task = self.get_object()
        payload = TaskDispatchSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        updated = services.dispatch_task(
            task,
            assignee=data.get("assignee_id"),
            device=data.get("device_id"),
            planned_at=data.get("planned_at"),
        )
        record_audit(
            action=AuditAction.UPDATE, instance=updated,
            changes={"status": updated.status}, object_repr=updated.task_no,
        )
        return Response(self.get_serializer(updated).data)

    @extend_schema(request=TaskStartSerializer, responses={200: LogisticsTaskSerializer})
    @action(detail=True, methods=["post"], url_path="start")
    def start(self, request, *args, **kwargs) -> Response:
        task = self.get_object()
        payload = TaskStartSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        updated = services.start_task(task, operator=payload.validated_data.get("operator_id"))
        record_audit(
            action=AuditAction.UPDATE, instance=updated,
            changes={"status": updated.status}, object_repr=updated.task_no,
        )
        return Response(self.get_serializer(updated).data)

    @extend_schema(request=TaskFinishSerializer, responses={200: LogisticsTaskSerializer})
    @action(detail=True, methods=["post"], url_path="finish")
    def finish(self, request, *args, **kwargs) -> Response:
        task = self.get_object()
        payload = TaskFinishSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        updated = services.finish_task(
            task,
            result=data.get("result") or "",
            quantity=data.get("quantity"),
            to_location=data.get("to_location_id"),
            operator=data.get("operator_id"),
        )
        record_audit(
            action=AuditAction.UPDATE, instance=updated,
            changes={"status": updated.status, "quantity": str(updated.quantity)},
            object_repr=updated.task_no,
        )
        return Response(self.get_serializer(updated).data)

    @extend_schema(request=TaskCancelSerializer, responses={200: LogisticsTaskSerializer})
    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request, *args, **kwargs) -> Response:
        task = self.get_object()
        payload = TaskCancelSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        updated = services.cancel_task(task, reason=data["reason"], operator=data.get("operator_id"))
        record_audit(
            action=AuditAction.UPDATE, instance=updated,
            changes={"status": updated.status}, reason=data["reason"], object_repr=updated.task_no,
        )
        return Response(self.get_serializer(updated).data, status=status.HTTP_200_OK)


class LogisticsOperationLogViewSet(ReadOnlyScopedViewSet):
    """操作日志：只读。日志由服务层写入，接口不提供新增/修改/删除。"""

    queryset = LogisticsOperationLog.objects.select_related(
        "company", "device", "task", "operator"
    ).all()
    serializer_class = LogisticsOperationLogSerializer
    scope_fields = {"company_field": "company_id"}
    search_fields = ["detail", "device__code", "task__task_no"]
    filterset_fields = ["company_id", "device_id", "task_id", "action", "operator_id"]
    ordering_fields = ["id", "occurred_at"]
    required_permissions = {
        "list": "logistics.log.view",
        "retrieve": "logistics.log.view",
    }
