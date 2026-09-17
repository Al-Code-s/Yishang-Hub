"""登录、会话、CSRF 与口令相关用例（对应任务书 14.2 第 1 条与 6.1/6.5）。"""

from __future__ import annotations

import pytest
from django.contrib.sessions.models import Session
from django.utils import timezone

from apps.core.models import AuditAction, AuditLog
from apps.identity.models import LoginAttempt
from tests.conftest import make_user

pytestmark = pytest.mark.django_db

LOGIN_URL = "/api/v1/identity/auth/login/"
SESSION_URL = "/api/v1/identity/auth/session/"
LOGOUT_URL = "/api/v1/identity/auth/logout/"
CSRF_URL = "/api/v1/identity/auth/csrf/"
CHANGE_PASSWORD_URL = "/api/v1/identity/auth/change-password/"


def test_csrf_bootstrap_sets_cookie(api_client):
    response = api_client.get(CSRF_URL)
    assert response.status_code == 200
    assert "yishang_csrftoken" in response.cookies


def test_unauthenticated_session_is_rejected(api_client):
    response = api_client.get(SESSION_URL)
    assert response.status_code in (401, 403)


def test_login_success_returns_permissions_and_menus(api_client, registry_permissions, registry_menus, company):
    make_user(username="login_ok", company=company, is_superuser=True)
    response = api_client.post(LOGIN_URL, {"username": "login_ok", "password": "Tst!Passw0rd2026"}, format="json")
    assert response.status_code == 200, response.content
    body = response.json()
    assert body["user"]["username"] == "login_ok"
    assert "*" in body["permissions"]  # 超级管理员
    assert any(menu["code"] == "system" for menu in body["menus"])


def test_login_accepts_phone(api_client, company):
    make_user(username="phone_user", company=company, phone="13900000001")
    response = api_client.post(
        LOGIN_URL, {"username": "13900000001", "password": "Tst!Passw0rd2026"}, format="json"
    )
    assert response.status_code == 200, response.content


def test_login_failure_records_attempt_and_locks_account(api_client, company, settings):
    user = make_user(username="lock_me", company=company)
    limit = settings.YISHANG["LOGIN_FAILURE_LIMIT"]

    for _ in range(limit):
        response = api_client.post(LOGIN_URL, {"username": "lock_me", "password": "WrongPass!2026"}, format="json")
        assert response.status_code == 401
        assert response.json()["code"] == "INVALID_CREDENTIALS"

    user.refresh_from_db()
    assert user.failed_login_count >= limit
    assert user.locked_until is not None and user.locked_until > timezone.now()

    blocked = api_client.post(LOGIN_URL, {"username": "lock_me", "password": "Tst!Passw0rd2026"}, format="json")
    assert blocked.status_code == 423
    assert blocked.json()["code"] == "ACCOUNT_LOCKED"

    assert LoginAttempt.objects.filter(username="lock_me", successful=False).count() >= limit
    assert AuditLog.objects.filter(action=AuditAction.LOGIN_FAILED).exists()


def test_disabled_account_cannot_login(api_client, company):
    make_user(username="disabled_user", company=company, is_active=False)
    response = api_client.post(
        LOGIN_URL, {"username": "disabled_user", "password": "Tst!Passw0rd2026"}, format="json"
    )
    assert response.status_code == 403
    assert response.json()["code"] == "ACCOUNT_DISABLED"


def test_logout_invalidates_server_session(api_client, company):
    make_user(username="logout_user", company=company, is_superuser=True)
    api_client.post(LOGIN_URL, {"username": "logout_user", "password": "Tst!Passw0rd2026"}, format="json")
    session_key = api_client.cookies["yishang_sessionid"].value
    assert Session.objects.filter(session_key=session_key).exists()

    assert api_client.post(LOGOUT_URL).status_code == 200
    assert api_client.get(SESSION_URL).status_code in (401, 403)
    assert AuditLog.objects.filter(action=AuditAction.LOGOUT).exists()


def test_change_password_invalidates_other_sessions(api_client, company):
    from rest_framework.test import APIClient

    user = make_user(username="pwd_user", company=company, is_superuser=True)

    other = APIClient()
    other.post(LOGIN_URL, {"username": "pwd_user", "password": "Tst!Passw0rd2026"}, format="json")
    assert other.get(SESSION_URL).status_code == 200

    api_client.post(LOGIN_URL, {"username": "pwd_user", "password": "Tst!Passw0rd2026"}, format="json")
    changed = api_client.post(
        CHANGE_PASSWORD_URL,
        {"old_password": "Tst!Passw0rd2026", "new_password": "New!Passw0rd#2026"},
        format="json",
    )
    assert changed.status_code == 200, changed.content

    # 密码变更后鉴权哈希改变，旧会话立即失效
    assert other.get(SESSION_URL).status_code in (401, 403)
    # 当前会话被重新绑定，仍然可用
    assert api_client.get(SESSION_URL).status_code == 200

    user.refresh_from_db()
    assert user.check_password("New!Passw0rd#2026")


def test_change_password_rejects_wrong_old_password(api_client, company):
    make_user(username="pwd_user2", company=company, is_superuser=True)
    api_client.post(LOGIN_URL, {"username": "pwd_user2", "password": "Tst!Passw0rd2026"}, format="json")
    response = api_client.post(
        CHANGE_PASSWORD_URL,
        {"old_password": "NotMyPassword!1", "new_password": "New!Passw0rd#2026"},
        format="json",
    )
    assert response.status_code == 400
    assert response.json()["code"] == "OLD_PASSWORD_INCORRECT"


def test_change_password_enforces_policy(api_client, company):
    make_user(username="pwd_user3", company=company, is_superuser=True)
    api_client.post(LOGIN_URL, {"username": "pwd_user3", "password": "Tst!Passw0rd2026"}, format="json")
    response = api_client.post(
        CHANGE_PASSWORD_URL,
        {"old_password": "Tst!Passw0rd2026", "new_password": "123456"},
        format="json",
    )
    assert response.status_code == 400
    assert response.json()["code"] == "PASSWORD_POLICY_VIOLATION"


def test_session_reports_must_change_password_flag(api_client, registry_permissions, company):
    make_user(username="must_change", company=company, must_change_password=True)
    response = api_client.post(LOGIN_URL, {"username": "must_change", "password": "Tst!Passw0rd2026"}, format="json")
    assert response.status_code == 200
    assert response.json()["user"]["must_change_password"] is True


def test_write_requests_require_csrf_token(client, company):
    """未携带 CSRF 令牌的写操作必须被拒绝（DRF 视图之外的 Django 校验同样生效）。"""
    from django.test import Client

    plain = Client(enforce_csrf_checks=True)
    user = make_user(username="csrf_user", company=company, is_superuser=True)  # noqa: F841
    plain.force_login(user)
    response = plain.post(
        "/api/v1/masterdata/uoms/", data={"code": "CSRF1", "name": "x"}, content_type="application/json"
    )
    assert response.status_code == 403
