"""自动化测试配置。

按要求关键数据库用例运行在 MySQL 上（不使用 SQLite），以便校验
唯一约束、CHECK 约束、锁与事务语义。
"""

from __future__ import annotations

from .base import *  # noqa: F403

DJANGO_ENV = "test"
DEBUG = False

ALLOWED_HOSTS = ["*"]

# 测试使用本地内存缓存，避免依赖 Redis 可用性
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "yishang-test",
    }
}

# 加速测试：仅测试环境使用快速哈希，生产仍为 Argon2
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# Celery 在测试中同步执行，避免依赖 broker
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

YISHANG["CSP_POLICY"] = ""  # noqa: F405

# 明确锁定 MySQL 测试库，防止误落到 SQLite
DATABASES["default"]["ENGINE"] = "django.db.backends.mysql"  # noqa: F405
