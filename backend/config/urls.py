"""根 URL 配置。

统一前缀 /api/v1/；健康检查放在根路径，便于容器探针直接使用。
"""

from __future__ import annotations

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from apps.core.views import health_live, health_ready

API_PREFIX = settings.YISHANG["API_PREFIX"]

urlpatterns = [
    path("admin/", admin.site.urls),
    path("healthz", health_live, name="health-live"),
    path("readyz", health_ready, name="health-ready"),
    path(f"{API_PREFIX}/", include("apps.core.urls")),
    path(f"{API_PREFIX}/identity/", include("apps.identity.urls")),
    path(f"{API_PREFIX}/factory/", include("apps.factory.urls")),
    path(f"{API_PREFIX}/masterdata/", include("apps.masterdata.urls")),
    path(f"{API_PREFIX}/crm/", include("apps.crm.urls")),
    path(f"{API_PREFIX}/sales/", include("apps.sales.urls")),
    path(f"{API_PREFIX}/srm/", include("apps.srm.urls")),
    path(f"{API_PREFIX}/procurement/", include("apps.procurement.urls")),
    path(f"{API_PREFIX}/planning/", include("apps.planning.urls")),
    path(f"{API_PREFIX}/wms/", include("apps.wms.urls")),
    path(f"{API_PREFIX}/workflow/", include("apps.workflow.urls")),
    path(f"{API_PREFIX}/integration/", include("apps.integration.urls")),
    path(f"{API_PREFIX}/analytics/", include("apps.analytics.urls")),
    path(f"{API_PREFIX}/schema/", SpectacularAPIView.as_view(), name="openapi-schema"),
    path(
        f"{API_PREFIX}/docs/",
        SpectacularSwaggerView.as_view(url_name="openapi-schema"),
        name="openapi-docs",
    ),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
