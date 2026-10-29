"""Integration tests for server.lifespan module."""

import sys
from unittest.mock import MagicMock, patch

import pytest

from server import lifespan as lifespan_module
from server.lifespan import (
    _get_logger_from_app,
    _initialize_directory_provider,
    _is_test_environment,
    _register_legacy_handlers,
    _stop_scheduled_tasks,
)


@pytest.mark.integration
def test_lifespan_is_test_environment_detects_pytest():
    """Test that _is_test_environment detects pytest environment."""
    # Arrange

    # Act
    is_test = _is_test_environment()

    # Assert
    assert is_test is True


@pytest.mark.integration
def test_lifespan_is_test_environment_detects_non_pytest():
    """Test that _is_test_environment returns False when pytest not loaded."""
    # Arrange
    original_modules = sys.modules.copy()

    # Temporarily remove pytest from sys.modules
    if "pytest" in sys.modules:
        del sys.modules["pytest"]

    try:
        # Act
        result = lifespan_module._is_test_environment()

        # Assert
        assert result is False
    finally:
        # Restore sys.modules
        sys.modules.update(original_modules)


@pytest.mark.integration
def test_lifespan_get_logger_returns_logger():
    """The lifespan logger is a structlog logger from the pipeline the configuration phase configured."""
    logger = _get_logger_from_app()

    assert logger is not None


@pytest.mark.integration
def test_lifespan_does_not_configure_logging():
    """Logging is configured once, by the app factory's configuration phase; lifespan only reads the logger."""
    assert not hasattr(lifespan_module, "configure_logging")


@pytest.mark.integration
def test_lifespan_register_legacy_handlers_calls_register(mock_bot):
    """Test that _register_legacy_handlers calls register on all modules."""
    # Arrange
    mock_logger = MagicMock()

    with (
        patch("server.lifespan.role") as mock_role,
        patch("server.lifespan.atip") as mock_atip,
        patch("server.lifespan.aws") as mock_aws,
        patch("server.lifespan.secret") as mock_secret,
        patch("server.lifespan.webhook_helper") as mock_webhook,
        patch("server.lifespan.incident") as mock_incident,
        patch("server.lifespan.incident_helper") as mock_incident_helper,
    ):
        # Act
        _register_legacy_handlers(mock_bot, mock_logger)

        # Assert
        mock_role.register.assert_called_once_with(mock_bot)
        mock_atip.register.assert_called_once_with(mock_bot)
        mock_aws.register.assert_called_once_with(mock_bot)
        mock_secret.register.assert_called_once_with(mock_bot)
        mock_webhook.register.assert_called_once_with(mock_bot)
        mock_incident.register.assert_called_once_with(mock_bot)
        mock_incident_helper.register.assert_called_once_with(mock_bot)


@pytest.mark.integration
def test_lifespan_stop_scheduled_tasks_with_none_event():
    """Test that _stop_scheduled_tasks handles None event gracefully."""
    # Arrange

    # Act
    _stop_scheduled_tasks(None)

    # Assert - Should not raise


@pytest.mark.integration
def test_lifespan_stop_scheduled_tasks_sets_event():
    """Test that _stop_scheduled_tasks sets the stop event."""
    # Arrange
    mock_event = MagicMock()

    # Act
    _stop_scheduled_tasks(mock_event)

    # Assert
    mock_event.set.assert_called_once()


@pytest.mark.integration
def test_initialize_directory_provider_stores_provider_on_app_state(monkeypatch):
    """Directory provider is warmed and stored on app.state during startup."""
    # Arrange
    app = MagicMock()
    app.state = MagicMock()
    mock_logger = MagicMock()
    mock_settings = MagicMock()
    mock_settings.require_startup_warmup = True
    mock_provider = MagicMock()
    mock_provider.warmup.return_value = MagicMock(is_success=True, message="ok")

    monkeypatch.setattr("server.lifespan.get_directory_provider", lambda: mock_provider)

    # Act
    _initialize_directory_provider(app, mock_settings, mock_logger)

    # Assert
    assert app.state.directory_provider is mock_provider
    mock_provider.warmup.assert_called_once_with()


@pytest.mark.integration
def test_initialize_directory_provider_raises_when_required_warmup_fails(monkeypatch):
    """Startup fails fast when warmup fails and warmup is required."""
    # Arrange
    app = MagicMock()
    app.state = MagicMock()
    mock_logger = MagicMock()
    mock_settings = MagicMock()
    mock_settings.require_startup_warmup = True
    mock_provider = MagicMock()
    mock_provider.warmup.return_value = MagicMock(
        is_success=False,
        message="credentials_invalid",
    )

    monkeypatch.setattr("server.lifespan.get_directory_provider", lambda: mock_provider)

    # Act / Assert
    with pytest.raises(RuntimeError, match="directory_warmup_failed"):
        _initialize_directory_provider(app, mock_settings, mock_logger)


@pytest.mark.integration
def test_initialize_directory_provider_allows_failed_optional_warmup(monkeypatch):
    """Startup skips remote warmup when fail-fast warmup is not required."""
    # Arrange
    app = MagicMock()
    app.state = MagicMock()
    mock_logger = MagicMock()
    mock_settings = MagicMock()
    mock_settings.require_startup_warmup = False
    mock_provider = MagicMock()

    monkeypatch.setattr("server.lifespan.get_directory_provider", lambda: mock_provider)

    # Act
    _initialize_directory_provider(app, mock_settings, mock_logger)

    # Assert
    assert app.state.directory_provider is mock_provider
    mock_provider.warmup.assert_not_called()
