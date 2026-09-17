#!/usr/bin/env python
"""意尚智造集成平台 Django 管理入口。"""

from __future__ import annotations

import os
import sys


def main() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:  # pragma: no cover
        raise ImportError("无法导入 Django。请确认已激活虚拟环境并执行 uv sync。") from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()