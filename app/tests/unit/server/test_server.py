"""Unit tests for server.server module."""

import importlib

import pytest

from infrastructure.configuration.app import AppSettings
from server import server


@pytest.mark.unit
def test_handler_is_fastapi_app():
    """Test that handler is a properly initialized FastAPI app."""
    # Assert
    assert server.handler is not None
    assert hasattr(server.handler, "routes")
    assert hasattr(server.handler, "user_middleware")
    assert hasattr(server.handler, "dependency_overrides")


@pytest.mark.unit
def test_server_app_exported_correctly():
    """Test that server_app is properly exported from main."""
    # Assert
    assert server.handler is not None


@pytest.mark.unit
def test_cors_middleware_configured():
    """CORS middleware should use explicit non-wildcard lists from settings."""
    # Arrange
    app = server.handler

    # Assert
    cors_middleware = next(
        (m for m in app.user_middleware if m.cls.__name__ == "CORSMiddleware"),
        None,
    )
    assert cors_middleware is not None
    assert cors_middleware.kwargs["allow_credentials"] is True
    assert cors_middleware.kwargs["allow_origins"] == server.app_settings.CORS_ALLOWED_ORIGINS
    assert cors_middleware.kwargs["allow_methods"] == server.app_settings.CORS_ALLOWED_METHODS
    assert cors_middleware.kwargs["allow_headers"] == server.app_settings.CORS_ALLOWED_HEADERS
    assert "*" not in cors_middleware.kwargs["allow_origins"]
    assert "*" not in cors_middleware.kwargs["allow_methods"]
    assert "*" not in cors_middleware.kwargs["allow_headers"]


@pytest.mark.unit
def test_cors_middleware_uses_configured_origin_list_after_reload(monkeypatch):
    """Reloaded server module should preserve the exact configured origin allow-list."""
    configured_origins = ["https://frontend.example"]
    monkeypatch.setattr(
        "infrastructure.configuration.app.get_app_settings",
        lambda: AppSettings(
            ENVIRONMENT="production",
            CORS_ALLOWED_ORIGINS=configured_origins,
            CORS_ALLOWED_METHODS=["GET", "POST"],
            CORS_ALLOWED_HEADERS=["Authorization", "Content-Type"],
        ),
    )

    reloaded = importlib.reload(server)
    cors_middleware = next(
        (m for m in reloaded.handler.user_middleware if m.cls.__name__ == "CORSMiddleware"),
        None,
    )

    assert cors_middleware is not None
    assert cors_middleware.kwargs["allow_origins"] == configured_origins


@pytest.mark.unit
def test_api_router_included():
    """Test that API router is included in the handler."""
    # Arrange
    app = server.handler

    # Assert - Check that at least some routes exist from api_router
    route_paths = [str(route.path) for route in app.routes]
    assert len(route_paths) > 0


@pytest.mark.unit
def test_configuration_error_exception_exists():
    """Test that ConfigurationError exception is defined."""
    # Assert
    assert hasattr(server, "ConfigurationError")
    assert issubclass(server.ConfigurationError, Exception)


@pytest.mark.unit
def test_sns_message_validator_initialized():
    """Test that SNS message validator is initialized."""
    # Assert
    assert server.sns_message_validator is not None
