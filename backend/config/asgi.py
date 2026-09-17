"""ASGI 入口。

第一版不引入实时推送，仅保留标准入口；若后续需要 WebSocket，再单独评审
ASGI 部署方案（channel layer、连接数、Redis 语义）。
"""

from __future__ import annotations

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.prod")

application = get_asgi_application()
