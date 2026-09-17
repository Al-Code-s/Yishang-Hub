"""请求级上下文：request_id、来源 IP、客户端、当前登录用户。

使用 contextvars 而非 thread local，保证 async/ASGI 语义正确。
"""

from __future__ import annotations

import contextvars
import logging
import re
import uuid
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from apps.identity.models import User

_REQUEST_ID: contextvars.ContextVar[str] = contextvars.ContextVar("yishang_request_id", default="-")
_CURRENT_USER: contextvars.ContextVar[Any] = contextvars.ContextVar("yishang_current_user", default=None)
_REQUEST_IP: contextvars.ContextVar[str] = contextvars.ContextVar("yishang_request_ip", default="")
_USER_AGENT: contextvars.ContextVar[str] = contextvars.ContextVar("yishang_user_agent", default="")

# 只接受安全字符，避免外部输入原样写入日志造成注入
_SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def normalise_request_id(raw: str | None) -> str:
    if raw and _SAFE_REQUEST_ID.match(raw):
        return raw
    return uuid.uuid4().hex


def set_request_id(value: str | None = None) -> str:
    request_id = normalise_request_id(value)
    _REQUEST_ID.set(request_id)
    return request_id


def get_request_id() -> str:
    return _REQUEST_ID.get()


def set_request_meta(ip: str = "", user_agent: str = "") -> None:
    _REQUEST_IP.set(ip or "")
    _USER_AGENT.set(user_agent or "")


def get_request_ip() -> str:
    return _REQUEST_IP.get()


def get_user_agent() -> str:
    return _USER_AGENT.get()


def set_current_user(user: User | None) -> None:
    _CURRENT_USER.set(user)


def get_current_user() -> User | None:
    """返回当前请求上下文中的登录用户；无请求上下文或未登录时返回 None。"""
    user = _CURRENT_USER.get()
    if user is None or not getattr(user, "is_authenticated", False):
        return None
    return user


class RequestIdFilter(logging.Filter):
    """把 request_id 注入每条日志记录。"""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id()
        return True
