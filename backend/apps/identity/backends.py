"""登录认证后端：支持登录账号或手机号。"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.db.models import Q

User = get_user_model()


class UsernameOrPhoneBackend(ModelBackend):
    """按登录账号或手机号认证。

    锁定策略与失败计数由 identity.services 统一处理，此处只做凭据校验，
    避免把安全策略散落到多个层。
    """

    def authenticate(self, request, username=None, password=None, **kwargs):  # type: ignore[override]
        if username is None or password is None:
            return None
        identifier = str(username).strip()
        if not identifier:
            return None
        user = User.objects.filter(Q(username=identifier) | Q(phone=identifier)).first()
        if user is None:
            # 用户不存在时也执行一次哈希计算，避免通过响应时间枚举账号
            User().set_password(password)
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
