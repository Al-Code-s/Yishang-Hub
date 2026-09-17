from __future__ import annotations

from django.conf import settings
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from apps.core.exceptions import APIError


class StandardPagination(PageNumberPagination):
    """统一分页：限制最大页大小，返回固定结构。"""

    page_size_query_param = "page_size"
    max_page_size = None

    def get_page_size(self, request) -> int:
        page_size = super().get_page_size(request)
        limit = settings.YISHANG["PAGE_SIZE_MAX"]
        if page_size and page_size > limit:
            raise APIError(
                f"page_size 不能超过 {limit}",
                code="PAGE_SIZE_EXCEEDED",
                details={"max_page_size": limit},
            )
        return page_size

    def get_paginated_response(self, data) -> Response:
        return Response(
            {
                "count": self.page.paginator.count,
                "page": self.page.number,
                "page_size": self.get_page_size(self.request),
                "results": data,
            }
        )
