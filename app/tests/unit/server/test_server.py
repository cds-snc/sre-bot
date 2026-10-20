"""Unit tests for server.server module."""

import importlib

import pytest
from fastapi.testclient import TestClient

from infrastructure.security.settings import SecuritySettings
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
    """CORS middleware should use the security slice's explicit non-wildcard lists and no credentials mode."""
    # Arrange
    app = server.handler

    # Assert
    cors_middleware = next(
        (m for m in app.user_middleware if m.cls.__name__ == "CORSMiddleware"),
        None,
    )
    assert cors_middleware is not None
    assert cors_middleware.kwargs["allow_credentials"] is False
    assert cors_middleware.kwargs["allow_origins"] == server.security_settings.CORS_ALLOWED_ORIGINS
    assert cors_middleware.kwargs["allow_methods"] == server.security_settings.CORS_ALLOWED_METHODS
    assert cors_middleware.kwargs["allow_headers"] == server.security_settings.CORS_ALLOWED_HEADERS
    assert "*" not in cors_middleware.kwargs["allow_origins"]
    assert "*" not in cors_middleware.kwargs["allow_methods"]
    assert "*" not in cors_middleware.kwargs["allow_headers"]


@pytest.mark.unit
def test_cors_middleware_uses_configured_origin_list_after_reload(monkeypatch):
    """Reloaded server module should preserve the exact configured origin allow-list."""
    configured_origins = ["https://frontend.example"]
    monkeypatch.setattr(
        "infrastructure.security.settings.get_security_settings",
        lambda: SecuritySettings(
            _env_file=None,
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
def test_cors_preflight_from_allowed_origin_grants_no_credentials(monkeypatch):
    """A preflight from an allowed origin is answered without Access-Control-Allow-Credentials.

    The server module is reloaded with a security slice allowing one origin; the
    preflight is answered by the CORS middleware, so the lifespan never runs.
    """
    origin = "https://frontend.example"
    monkeypatch.setattr(
        "infrastructure.security.settings.get_security_settings",
        lambda: SecuritySettings(_env_file=None, CORS_ALLOWED_ORIGINS=[origin]),
    )
    reloaded = importlib.reload(server)

    response = TestClient(reloaded.handler).options(
        "/version",
        headers={"Origin": origin, "Access-Control-Request-Method": "GET"},
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin
    assert "access-control-allow-credentials" not in response.headers
    assert "PUT" not in response.headers["access-control-allow-methods"]


@pytest.mark.unit
def test_max_body_size_middleware_configured():
    """Webhook ingress should be protected by a body-size cap middleware."""
    # Arrange
    app = server.handler

    # Assert
    max_body_middleware = next(
        (m for m in app.user_middleware if m.cls.__name__ == "MaxBodySizeMiddleware"),
        None,
    )
    assert max_body_middleware is not None
    assert max_body_middleware.kwargs["max_bytes"] == server.app_settings.WEBHOOK_MAX_BODY_BYTES


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
