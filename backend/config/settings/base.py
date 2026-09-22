"""意尚智造集成平台 Django 基础配置。

本文件只放各环境共享的配置；差异部分由 dev.py / test.py / prod.py 覆盖。
所有敏感项通过环境变量注入，仓库内不保存任何生产凭据。
"""

from __future__ import annotations

import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

# backend/ 目录；REPO_ROOT 为仓库根目录
BASE_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = BASE_DIR.parent

# 本地开发使用 backend/.env（已被 .gitignore 忽略）；生产由编排注入环境变量
load_dotenv(BASE_DIR / ".env")


def env_str(key: str, default: str = "") -> str:
    value = os.environ.get(key)
    return default if value is None or value.strip() == "" else value.strip()


def env_bool(key: str, default: bool = False) -> bool:
    raw = os.environ.get(key)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def env_int(key: str, default: int) -> int:
    raw = os.environ.get(key)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ImproperlyConfigured(f"环境变量 {key} 必须是整数，当前值不合法。") from exc


def env_list(key: str, default: tuple[str, ...] = ()) -> list[str]:
    raw = os.environ.get(key)
    if raw is None or raw.strip() == "":
        return list(default)
    return [item.strip() for item in raw.split(",") if item.strip()]


# --------------------------------------------------------------------------
# 基础安全
# --------------------------------------------------------------------------
DJANGO_ENV = env_str("DJANGO_ENV", "development")
DEBUG = env_bool("DJANGO_DEBUG", False)

SECRET_KEY = env_str("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    if DJANGO_ENV in {"development", "test"}:
        # 仅供本地开发/测试；生产环境缺失 SECRET_KEY 时直接拒绝启动
        SECRET_KEY = "dev-only-insecure-secret-key-change-me"
    else:
        raise ImproperlyConfigured(
            "生产环境必须通过 DJANGO_SECRET_KEY 环境变量提供密钥。"
        )

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", ("localhost", "127.0.0.1"))
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")

# --------------------------------------------------------------------------
# 应用
# --------------------------------------------------------------------------
DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "django_filters",
    "corsheaders",
    "drf_spectacular",
    "django_celery_beat",
]

LOCAL_APPS = [
    "apps.core",
    "apps.identity",
    "apps.factory",
    "apps.masterdata",
    "apps.crm",
    "apps.sales",
    "apps.srm",
    "apps.procurement",
    "apps.planning",
    "apps.mes",
    "apps.qms",
    "apps.equipment",
    "apps.ems",
    "apps.iot",
    "apps.ehs",
    "apps.logistics",
    "apps.wms",
    "apps.workflow",
    "apps.integration",
    "apps.analytics",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "apps.core.middleware.RequestIdMiddleware",
    "apps.core.middleware.ContentSecurityPolicyMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.core.middleware.CurrentUserMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# --------------------------------------------------------------------------
# 数据库（MySQL 8 / InnoDB / utf8mb4 / 严格模式）
# --------------------------------------------------------------------------
DB_DRIVER = env_str("DB_DRIVER", "mysqlclient").lower()
if DB_DRIVER == "pymysql":
    # Windows 本地开发无 C 工具链时的等价 MySQLdb 实现；生产镜像使用 mysqlclient
    import pymysql

    pymysql.install_as_MySQLdb()
elif DB_DRIVER != "mysqlclient":  # pragma: no cover
    raise ImproperlyConfigured(
        f"不支持的 DB_DRIVER={DB_DRIVER!r}，可选值为 mysqlclient 或 pymysql。"
    )

DB_NAME = env_str("DB_NAME", "yishang_platform")
DB_USER = env_str("DB_USER", "yishang_app")
DB_PASSWORD = env_str("DB_PASSWORD")
DB_HOST = env_str("DB_HOST", "127.0.0.1")
DB_PORT = env_str("DB_PORT", "3306")

STRICT_SQL_MODE = (
    "STRICT_TRANS_TABLES,NO_ZERO_DATE,NO_ZERO_IN_DATE,"
    "ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION"
)

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": DB_NAME,
        "USER": DB_USER,
        "PASSWORD": DB_PASSWORD,
        "HOST": DB_HOST,
        "PORT": DB_PORT,
        "CONN_MAX_AGE": env_int("DB_CONN_MAX_AGE", 60),
        "CONN_HEALTH_CHECKS": True,
        "OPTIONS": {
            "charset": "utf8mb4",
            # 显式固定严格模式，避免依赖实例默认值
            "init_command": f"SET sql_mode='{STRICT_SQL_MODE}'",
        },
        "TEST": {
            "NAME": env_str("DB_TEST_NAME", "test_yishang_platform"),
            "CHARSET": "utf8mb4",
            "COLLATION": "utf8mb4_0900_ai_ci",
        },
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --------------------------------------------------------------------------
# 认证
# --------------------------------------------------------------------------
AUTH_USER_MODEL = "identity.User"

AUTHENTICATION_BACKENDS = [
    "apps.identity.backends.UsernameOrPhoneBackend",
]

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
    "django.contrib.auth.hashers.ScryptPasswordHasher",
]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 10},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# --------------------------------------------------------------------------
# 会话 / CSRF / CORS
# --------------------------------------------------------------------------
SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_COOKIE_NAME = "yishang_sessionid"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = env_int("SESSION_COOKIE_AGE", 60 * 60 * 12)
SESSION_SAVE_EVERY_REQUEST = True

CSRF_COOKIE_NAME = "yishang_csrftoken"
# 前端需要读取该 Cookie 并回填 X-CSRFToken，因此不能设为 HttpOnly
CSRF_COOKIE_HTTPONLY = False
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_FAILURE_VIEW = "apps.core.views.csrf_failure"

CORS_ALLOW_CREDENTIALS = True
CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS")

# 仅当部署在受信反向代理之后才信任 X-Forwarded-For；默认关闭，避免伪造来源 IP
USE_X_FORWARDED_FOR = env_bool("DJANGO_USE_X_FORWARDED_FOR", False)

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

# --------------------------------------------------------------------------
# DRF / OpenAPI
# --------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "apps.core.pagination.StandardPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.OrderingFilter",
        "rest_framework.filters.SearchFilter",
    ],
    "EXCEPTION_HANDLER": "apps.core.exceptions.yishang_exception_handler",
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    # Decimal 一律以字符串输出，前端使用十进制计算
    "COERCE_DECIMAL_TO_STRING": True,
    "DATETIME_FORMAT": "iso-8601",
    "UNAUTHENTICATED_USER": "django.contrib.auth.models.AnonymousUser",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "意尚智造集成平台 API",
    "DESCRIPTION": (
        "服饰企业统一集成平台。采购、销售、生产、仓储等业务直接在本平台实现，"
        "不是对接外部 ERP/MES/WMS 的接口平台。"
    ),
    "VERSION": "0.1.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "SCHEMA_PATH_PREFIX": "/api/v1",
    "COMPONENT_SPLIT_REQUEST": True,
}

# --------------------------------------------------------------------------
# 缓存 / Celery
# --------------------------------------------------------------------------
REDIS_URL = env_str("REDIS_URL", "redis://127.0.0.1:6379/0")

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_URL,
        "KEY_PREFIX": "yishang",
    }
}

CELERY_BROKER_URL = env_str("CELERY_BROKER_URL", REDIS_URL)
CELERY_RESULT_BACKEND = env_str("CELERY_RESULT_BACKEND", "django-db")
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TIMEZONE = "UTC"
CELERY_ENABLE_UTC = True
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = env_int("CELERY_TASK_TIME_LIMIT", 60 * 30)
CELERY_TASK_SOFT_TIME_LIMIT = env_int("CELERY_TASK_SOFT_TIME_LIMIT", 60 * 25)
CELERY_TASK_ACKS_LATE = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"

# --------------------------------------------------------------------------
# 国际化与时区
# --------------------------------------------------------------------------
LANGUAGE_CODE = "zh-hans"
# 存储与传输统一 UTC；业务界面按 Asia/Shanghai 展示
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# --------------------------------------------------------------------------
# 静态文件 / 媒体
# --------------------------------------------------------------------------
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
if env_str("OBJECT_STORAGE_BUCKET"):
    # S3 兼容对象存储需要 django-storages[s3]；缺失时直接拒绝启动而不是静默退化为本地磁盘
    import importlib.util

    if importlib.util.find_spec("storages") is None:  # pragma: no cover
        raise ImproperlyConfigured(
            "配置了 OBJECT_STORAGE_BUCKET 但未安装 django-storages，"
            "请执行 uv sync --extra s3 或在镜像中安装依赖。"
        )
    STORAGES["default"] = {"BACKEND": "storages.backends.s3.S3Storage"}
    # 附件属于企业私有资料，对象存储默认不公开
    AWS_STORAGE_BUCKET_NAME = env_str("OBJECT_STORAGE_BUCKET")
    AWS_S3_ENDPOINT_URL = env_str("OBJECT_STORAGE_ENDPOINT")
    AWS_ACCESS_KEY_ID = env_str("OBJECT_STORAGE_ACCESS_KEY")
    AWS_SECRET_ACCESS_KEY = env_str("OBJECT_STORAGE_SECRET_KEY")
    AWS_S3_REGION_NAME = env_str("OBJECT_STORAGE_REGION", "us-east-1")
    AWS_QUERYSTRING_AUTH = True
    AWS_DEFAULT_ACL = None
    AWS_S3_FILE_OVERWRITE = False

DATA_UPLOAD_MAX_MEMORY_SIZE = env_int("DATA_UPLOAD_MAX_MEMORY_SIZE", 20 * 1024 * 1024)
FILE_UPLOAD_MAX_MEMORY_SIZE = env_int("FILE_UPLOAD_MAX_MEMORY_SIZE", 5 * 1024 * 1024)
DATA_UPLOAD_MAX_NUMBER_FIELDS = 5000

# --------------------------------------------------------------------------
# 日志（带 request_id）
# --------------------------------------------------------------------------
LOG_LEVEL = env_str("LOG_LEVEL", "INFO")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "%(asctime)s %(levelname)s [%(name)s] request_id=%(request_id)s %(message)s",
        },
    },
    "filters": {
        "request_id": {"()": "apps.core.logging.RequestIdFilter"},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "standard",
            "filters": ["request_id"],
        },
    },
    "root": {"handlers": ["console"], "level": LOG_LEVEL},
    "loggers": {
        "django.request": {"handlers": ["console"], "level": "WARNING", "propagate": False},
        "django.security": {"handlers": ["console"], "level": "WARNING", "propagate": False},
        "yishang.audit": {"handlers": ["console"], "level": "INFO", "propagate": False},
    },
}

# --------------------------------------------------------------------------
# 平台业务参数（集中管理，避免散落魔法值）
# --------------------------------------------------------------------------
YISHANG_API_PREFIX = env_str("YISHANG_API_PREFIX", "api/v1")
YISHANG_BUSINESS_TIME_ZONE = env_str("YISHANG_BUSINESS_TIME_ZONE", "Asia/Shanghai")

YISHANG = {
    "API_PREFIX": YISHANG_API_PREFIX,
    "BUSINESS_TIME_ZONE": YISHANG_BUSINESS_TIME_ZONE,
    # 分页上限，超过直接拒绝，避免一次拉取全表
    "PAGE_SIZE_MAX": env_int("YISHANG_PAGE_SIZE_MAX", 200),
    # 连续登录失败锁定策略
    "LOGIN_FAILURE_LIMIT": env_int("YISHANG_LOGIN_FAILURE_LIMIT", 5),
    "LOGIN_FAILURE_WINDOW_MINUTES": env_int("YISHANG_LOGIN_FAILURE_WINDOW_MINUTES", 15),
    "LOGIN_LOCK_MINUTES": env_int("YISHANG_LOGIN_LOCK_MINUTES", 15),
    # 幂等键保留时长
    "IDEMPOTENCY_TTL_HOURS": env_int("YISHANG_IDEMPOTENCY_TTL_HOURS", 24),
    # 库存默认禁止负库存（阶段 2 由库存服务强制）
    "ALLOW_NEGATIVE_STOCK": env_bool("YISHANG_ALLOW_NEGATIVE_STOCK", False),
    # 上传附件限制
    "ATTACHMENT_MAX_BYTES": env_int("YISHANG_ATTACHMENT_MAX_BYTES", 20 * 1024 * 1024),
    "ATTACHMENT_ALLOWED_EXTENSIONS": env_list(
        "YISHANG_ATTACHMENT_ALLOWED_EXTENSIONS",
        (
            "pdf", "png", "jpg", "jpeg", "webp", "gif",
            "doc", "docx", "xls", "xlsx", "csv", "txt", "zip",
        ),
    ),
    "CSP_POLICY": env_str("YISHANG_CSP_POLICY", "default-src 'self'"),
    # bootstrap_system 使用的管理员账号来源；密码只从环境变量读取，绝不写死在代码里
    "BOOTSTRAP_ADMIN_USERNAME": env_str("YISHANG_ADMIN_USERNAME", "admin"),
    "BOOTSTRAP_ADMIN_PASSWORD": env_str("YISHANG_ADMIN_PASSWORD", ""),
    # seed_demo 使用的演示账号口令来源；留空时由命令随机生成并打印一次
    "DEMO_PASSWORD": env_str("YISHANG_DEMO_PASSWORD", ""),
}
