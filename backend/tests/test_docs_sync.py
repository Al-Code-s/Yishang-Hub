"""文档与代码同步校验（任务书 19.3 / 20.3）。

使用说明 ``docs/user-guide.md`` 里内嵌一条机器可校验的事实行：

    <!-- yishang-doc-sync: permissions=173 menus=56 models=86 migrations=19 builtin_roles=13 -->

本用例把该行与**代码里的权威来源**逐项比对。任何一项变化会让本用例失败，
从而强制「代码更新后使用文档同步变动」，避免文档静默过期。

注意：这里只校验**数量层面**；菜单名称、操作步骤、错误码解释等描述性内容
仍由人工按 `docs/user-guide.md` §11.3 的收尾清单维护。
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest
from django.apps import apps as django_apps

from apps.core.management.commands.bootstrap_system import BUILTIN_ROLES
from apps.identity.permissions_registry import MENUS, PERMISSIONS

REPO_ROOT = Path(__file__).resolve().parents[2]
GUIDE_PATH = REPO_ROOT / "docs" / "user-guide.md"
SYNC_LINE_RE = re.compile(r"<!--\s*yishang-doc-sync:\s*(?P<body>[^>]*?)\s*-->")


def _read_declared_facts() -> dict[str, int]:
    text = GUIDE_PATH.read_text(encoding="utf-8")
    match = SYNC_LINE_RE.search(text)
    assert match is not None, (
        f"{GUIDE_PATH} 缺少事实行：<!-- yishang-doc-sync: permissions=... menus=... "
        "models=... migrations=... builtin_roles=... -->。不要删除该行，按实际值更新即可。"
    )
    facts: dict[str, int] = {}
    for token in match.group("body").split():
        key, _, raw = token.partition("=")
        facts[key.strip()] = int(raw)
    return facts


def _actual_model_count() -> int:
    return len([m for m in django_apps.get_models() if m._meta.managed and not m._meta.auto_created])


def _actual_migration_count() -> int:
    apps_dir = REPO_ROOT / "backend" / "apps"
    return len([p for p in apps_dir.glob("*/migrations/[0-9]*_*.py") if p.is_file()])


def test_user_guide_declares_all_sync_facts():
    declared = _read_declared_facts()
    expected_keys = {"permissions", "menus", "models", "migrations", "builtin_roles"}
    assert set(declared) == expected_keys, (
        f"事实行的键应为 {sorted(expected_keys)}，实际为 {sorted(declared)}。"
    )
    for key, value in declared.items():
        assert value > 0, f"事实行 {key} 应大于 0，实际为 {value}。"


def test_published_guide_html_is_up_to_date():
    """对外发布的网页版使用说明必须与 Markdown 源保持一致。

    ``docs/user-guide.html``（直接发给客户）与 ``frontend/public/guide.html``
    （随前端发布，访问 ``/guide.html``）都由 ``scripts/build_user_guide.py`` 生成；
    改了 Markdown 却不重新生成时，本用例会失败。
    """
    script = REPO_ROOT / "scripts" / "build_user_guide.py"
    result = subprocess.run(
        [sys.executable, str(script), "--check"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == 0, (
        "网页版使用说明已过期（与 docs/user-guide.md 不一致）。请运行："
        " python scripts/build_user_guide.py\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )


@pytest.mark.parametrize(
    ("key", "actual"),
    [
        ("permissions", lambda: len(PERMISSIONS)),
        ("menus", lambda: len(MENUS)),
        ("models", _actual_model_count),
        ("migrations", _actual_migration_count),
        ("builtin_roles", lambda: len(BUILTIN_ROLES)),
    ],
)
def test_user_guide_sync_facts_match_code(key, actual):
    declared = _read_declared_facts()
    current = actual()
    assert declared[key] == current, (
        f"docs/user-guide.md 的事实行已过期：{key}={declared[key]}，代码实际为 {current}。\n"
        f"请更新 {GUIDE_PATH} 中的 <!-- yishang-doc-sync: ... --> 事实行，"
        "并同步文档正文（§二 能力边界、§四 角色权限点数、§五 菜单清单等）。"
    )
