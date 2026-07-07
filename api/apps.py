"""Django app config for API endpoints."""

from __future__ import annotations

from django.apps import AppConfig


class ApiConfig(AppConfig):
    """Registers the ERP AI Agent API app with Django."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "api"
