"""Unit tests for AppSettings dependency injection wiring."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from infrastructure.configuration import AppSettings
from infrastructure.services import AppSettingsDep, get_app_settings


def test_app_settings_dep_override():
    """AppSettingsDep should support FastAPI dependency overrides."""
    app = FastAPI()

    @app.get("/app-config")
    def read_config(settings: AppSettingsDep) -> dict[str, str]:
        return {
            "prefix": settings.PREFIX,
            "log_level": settings.LOG_LEVEL,
            "git_sha": settings.GIT_SHA,
        }

    override = AppSettings(PREFIX="dev", LOG_LEVEL="DEBUG", GIT_SHA="abc123")
    app.dependency_overrides[get_app_settings] = lambda: override

    try:
        with TestClient(app) as client:
            response = client.get("/app-config")

        assert response.status_code == 200
        assert response.json() == {
            "prefix": "dev",
            "log_level": "DEBUG",
            "git_sha": "abc123",
        }
    finally:
        app.dependency_overrides.clear()
