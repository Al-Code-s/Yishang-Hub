from __future__ import annotations

from django.urls import path

from apps.analytics import views

urlpatterns = [
    path("dashboard/", views.DashboardView.as_view(), name="analytics-dashboard"),
    path(
        "masterdata-freshness/",
        views.MasterdataFreshnessView.as_view(),
        name="analytics-masterdata-freshness",
    ),
]
