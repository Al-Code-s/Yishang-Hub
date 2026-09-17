from __future__ import annotations

from typing import TYPE_CHECKING

from django.conf import settings

from apps.core.logging import set_current_user, set_request_id, set_request_meta

if TYPE_CHECKING:
    from django.http import HttpRequest, HttpResponse


def _client_ip(request: HttpRequest) -> str:
    """取客户端 IP。

    仅当部署在受信反向代理之后时才信任 X-Forwarded-For，由
    DJANGO_USE_X_FORWARDED_FOR 控制，避免被伪造。
    """
    if getattr(settings, "USE_X_FORWARDED_FOR", False):
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "") or ""


class RequestIdMiddleware:
    """为每个请求分配追踪标识，并回写到响应头。"""

    header_name = "X-Request-Id"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        request_id = set_request_id(request.headers.get(self.header_name))
        set_request_meta(_client_ip(request), request.headers.get("User-Agent", ""))
        request.request_id = request_id  # type: ignore[attr-defined]
        response = self.get_response(request)
        response[self.header_name] = request_id
        return response


class CurrentUserMiddleware:
    """把当前用户放入上下文，供审计字段自动填充使用。

    仅用于填充 created_by / updated_by 等审计信息，不作为权限判定依据；
    权限判定一律以 request.user 为准。
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        user = getattr(request, "user", None)
        set_current_user(user if user is not None and user.is_authenticated else None)
        try:
            return self.get_response(request)
        finally:
            set_current_user(None)


class ContentSecurityPolicyMiddleware:
    """写入 CSP 响应头；策略为空时跳过（本地开发为便于 Vite HMR 会留空）。"""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        response = self.get_response(request)
        policy = settings.YISHANG.get("CSP_POLICY", "")
        if policy and not response.has_header("Content-Security-Policy"):
            response["Content-Security-Policy"] = policy
        return response
