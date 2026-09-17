"""Celery 应用配置。

后端镜像可分别以 web / worker / beat 角色启动，均复用本模块。
"""

from __future__ import annotations

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

app = Celery("yishang")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()


@app.task(bind=True, name="config.debug_ping")
def debug_ping(self) -> str:
    """连通性自检任务，不产生任何业务副作用。"""
    return "pong"
