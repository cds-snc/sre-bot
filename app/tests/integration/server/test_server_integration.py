"""Integration tests for server module."""

import pytest

from server import server


@pytest.fixture
def integration_server_app():
    """Create a server app for integration testing."""
    return server.create_app()


@pytest.mark.integration
def test_server_app_initializes_with_handlers(integration_server_app):
    """Test that server app initializes with all required handlers."""
    # Assert
    assert integration_server_app is not None
    assert len(integration_server_app.user_middleware) > 0
    assert len(integration_server_app.routes) > 0


@pytest.mark.integration
def test_server_has_cors_middleware_configured(integration_server_app):
    """CORS middleware should be configured with explicit non-wildcard lists and no credentials mode."""
    # Assert
    cors_middleware = next(
        (m for m in integration_server_app.user_middleware if m.cls.__name__ == "CORSMiddleware"),
        None,
    )

    assert cors_middleware is not None
    assert cors_middleware.kwargs["allow_credentials"] is False
    assert "*" not in cors_middleware.kwargs["allow_origins"]
    assert "*" not in cors_middleware.kwargs["allow_methods"]
    assert "*" not in cors_middleware.kwargs["allow_headers"]


@pytest.mark.integration
def test_server_exports_app_factory_and_builds_nothing_at_import():
    """The server module exposes create_app and no module-level app."""
    assert callable(server.create_app)
    assert not hasattr(server, "handler")


@pytest.mark.integration
def test_server_includes_api_router(integration_server_app):
    """Test that server includes the API router."""
    # Arrange & Act
    routes = integration_server_app.routes

    # Assert
    assert len(routes) > 0
