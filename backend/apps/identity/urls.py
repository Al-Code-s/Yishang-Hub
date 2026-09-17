from __future__ import annotations

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.identity import views

router = DefaultRouter()
router.register("users", views.UserViewSet, basename="identity-user")
router.register("roles", views.RoleViewSet, basename="identity-role")
router.register("permissions", views.PermissionViewSet, basename="identity-permission")
router.register("menus", views.MenuViewSet, basename="identity-menu")
router.register("login-attempts", views.LoginAttemptViewSet, basename="identity-login-attempt")
router.register("notifications", views.NotificationViewSet, basename="identity-notification")

auth_patterns = [
    path("auth/csrf/", views.CsrfBootstrapView.as_view(), name="identity-csrf"),
    path("auth/login/", views.LoginView.as_view(), name="identity-login"),
    path("auth/logout/", views.LogoutView.as_view(), name="identity-logout"),
    path("auth/session/", views.SessionView.as_view(), name="identity-session"),
    path("auth/change-password/", views.ChangePasswordView.as_view(), name="identity-change-password"),
    path("profile/", views.ProfileView.as_view(), name="identity-profile"),
]

urlpatterns = auth_patterns + [path("", include(router.urls))]
