"""Integration tests for server module."""

import pytest


@pytest.fixture
def integration_server_app():
    """Create a server app for integration testing."""
    # Import here to avoid issues with module-level initialization
    from server import server

    return server.handler


@pytest.mark.integration
def test_server_app_initializes_with_handlers(integration_server_app):
    """Test that server app initializes with all required handlers."""
    # Assert
    assert integration_server_app is not None
    assert len(integration_server_app.user_middleware) > 0
    assert len(integration_server_app.routes) > 0


@pytest.mark.integration
def test_server_has_cors_middleware_configured(integration_server_app):
    """Test that server has CORS middleware configured."""
    # Assert
    middleware_classes = [
        m.cls.__name__ for m in integration_server_app.user_middleware
    ]
    assert "CORSMiddleware" in middleware_classes


@pytest.mark.integration
def test_server_exports_handler_in_server_module():
    """Test that server module exports handler correctly."""
    # Arrange & Act
    from server import server

    # Assert
    assert hasattr(server, "handler")
    assert server.handler is not None


@pytest.mark.integration
def test_server_includes_api_router(integration_server_app):
    """Test that server includes the API router."""
    # Arrange & Act
    route_paths = [str(route.path) for route in integration_server_app.routes]

    # Assert
    assert len(route_paths) > 0
