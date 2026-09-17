"""生产配置。

所有敏感项必须由环境变量注入；缺失关键项时直接拒绝启动，避免以不安全姿态运行。
"""

from __future__ import annotations

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403

DJANGO_ENV = "production"
DEBUG = False

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS")  # noqa: F405
if not ALLOWED_HOSTS:
    raise ImproperlyConfigured("生产环境必须配置 DJANGO_ALLOWED_HOSTS。")

CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")  # noqa: F405
if not CSRF_TRUSTED_ORIGINS:
    raise ImproperlyConfigured("生产环境必须配置 DJANGO_CSRF_TRUSTED_ORIGINS。")

if DB_PASSWORD == "":  # noqa: F405
    raise ImproperlyConfigured("生产环境必须配置数据库密码 DB_PASSWORD。")

# HTTPS 与 Cookie 安全
SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", True)  # noqa: F405
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = env_int("DJANGO_SECURE_HSTS_SECONDS", 60 * 60 * 24 * 30)  # noqa: F405
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = False

# 生产不写回本地 .env，全部使用编排注入
CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS")  # noqa: F405

EMAIL_BACKEND = env_str(  # noqa: F405
    "DJANGO_EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend"
)
EMAIL_HOST = env_str("DJANGO_EMAIL_HOST")  # noqa: F405
EMAIL_PORT = env_int("DJANGO_EMAIL_PORT", 25)  # noqa: F405
EMAIL_HOST_USER = env_str("DJANGO_EMAIL_HOST_USER")  # noqa: F405
EMAIL_HOST_PASSWORD = env_str("DJANGO_EMAIL_HOST_PASSWORD")  # noqa: F405
EMAIL_USE_TLS = env_bool("DJANGO_EMAIL_USE_TLS", False)  # noqa: F405
DEFAULT_FROM_EMAIL = env_str("DJANGO_DEFAULT_FROM_EMAIL", "no-reply@example.invalid")  # noqa: F405
