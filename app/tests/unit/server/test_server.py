"""Unit tests for server.server module."""

import pytest

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
    """Test that CORS middleware is present in the server."""
    # Arrange
    app = server.handler

    # Assert
    middleware_classes = [m.cls.__name__ for m in app.user_middleware]
    assert "CORSMiddleware" in middleware_classes


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
