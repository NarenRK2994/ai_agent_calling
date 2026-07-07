"""URL routes for the ERP AI Agent Django API."""

from __future__ import annotations

from django.urls import path

from api import views


urlpatterns = [
    path("health", views.health, name="health"),
    path("runs", views.create_run, name="create_run"),
    path("runs/<str:run_id>", views.get_run, name="get_run"),
    path("runs/<str:run_id>/events", views.stream_run_events, name="stream_run_events"),
]
