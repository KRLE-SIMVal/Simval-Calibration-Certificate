"""ASGI entrypoint for the SIMVal calibration certificate application."""

from __future__ import annotations

from app.backend.api.app import create_app_from_settings
from app.backend.api.settings import ApiSettings


app = create_app_from_settings(ApiSettings.from_environment())
