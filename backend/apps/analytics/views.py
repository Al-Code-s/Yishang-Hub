from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.analytics import services
from apps.core.permissions import HasRequiredPermissions


class DashboardView(APIView):
    """工作台首页数据。指标按权限裁剪，不返回用户无权查看的内容。"""

    permission_classes = [HasRequiredPermissions]
    required_permissions = {"GET": "analytics.dashboard.view"}

    @extend_schema(responses={200: dict})
    def get(self, request, *args, **kwargs) -> Response:
        return Response(services.dashboard(request.user))


class MasterdataFreshnessView(APIView):
    permission_classes = [HasRequiredPermissions]
    required_permissions = {"GET": "analytics.dashboard.view"}

    def get(self, request, *args, **kwargs) -> Response:
        days = int(request.query_params.get("days", 7))
        return Response(services.masterdata_freshness(request.user, days=days))
