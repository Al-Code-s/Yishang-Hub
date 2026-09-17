"""Django 项目配置包。

在此导入 Celery 应用，使 @shared_task 能绑定到同一个 app 实例。
"""

from __future__ import annotations

from .celery import app as celery_app

__all__ = ("celery_app",)
