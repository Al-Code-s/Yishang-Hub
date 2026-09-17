"""本地开发配置。不得用于生产部署。"""

from __future__ import annotations

from .base import *  # noqa: F403

DJANGO_ENV = "development"
DEBUG = True

ALLOWED_HOSTS = env_list(  # noqa: F405
    "DJANGO_ALLOWED_HOSTS", ("localhost", "127.0.0.1", "[::1]")
)

# Vite 开发服务器
DEV_FRONTEND_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
CORS_ALLOWED_ORIGINS = DEV_FRONTEND_ORIGINS
CSRF_TRUSTED_ORIGINS = DEV_FRONTEND_ORIGINS

INTERNAL_IPS = ["127.0.0.1"]

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# 开发环境放开 CSP，避免阻塞 Vite HMR；中间件在策略为空时跳过写入
YISHANG["CSP_POLICY"] = ""  # noqa: F405
