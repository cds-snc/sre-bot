"""Integration tests for server.lifespan module."""

import sys
import threading
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI

from server import lifespan as lifespan_module
from server.lifespan import (
    _activate_providers,
    _get_logger,
    _is_test_environment,
    _list_configs,
    _register_legacy_handlers,
    _start_scheduled_tasks,
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
def test_lifespan_get_logger_returns_logger(mock_settings):
    """Test that _get_logger returns a configured logger."""
    # Arrange

    # Act
    logger = _get_logger(mock_settings)

    # Assert
    assert logger is not None


@pytest.mark.integration
def test_lifespan_list_configs_logs_settings(mock_settings):
    """Test that _list_configs logs configuration settings."""
    # Arrange
    mock_logger = MagicMock()

    # Act
    _list_configs(mock_settings, mock_logger)

    # Assert
    mock_logger.info.assert_called()
    # First call should log "configuration_initialized"
    assert mock_logger.info.call_count >= 1


@pytest.mark.integration
@patch("server.lifespan.configure_logging")
def test_lifespan_get_logger_configures_logging(mock_configure_logging, mock_settings):
    """Test that _get_logger calls configure_logging with settings."""
    # Arrange
    mock_logger = MagicMock()
    mock_configure_logging.return_value = mock_logger

    # Act
    logger = _get_logger(mock_settings)

    # Assert
    mock_configure_logging.assert_called_once_with(settings=mock_settings)
    assert logger == mock_logger


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
        patch("server.lifespan.sre") as mock_sre,
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
        mock_sre.register.assert_called_once_with(mock_bot)
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
def test_lifespan_start_scheduled_tasks_skips_when_prefix_not_empty(
    mock_settings, mock_bot, monkeypatch
):
    """Test that _start_scheduled_tasks skips when PREFIX is not empty."""
    # Arrange
    mock_logger = MagicMock()
    mock_settings.PREFIX = "dev"
    init_mock = MagicMock()
    run_mock = MagicMock()
    monkeypatch.setattr("server.lifespan.scheduled_tasks.init", init_mock)
    monkeypatch.setattr("server.lifespan.scheduled_tasks.run_continuously", run_mock)

    # Act
    stop_event = _start_scheduled_tasks(mock_bot, mock_settings, mock_logger)

    # Assert
    assert stop_event is None
    init_mock.assert_not_called()
    run_mock.assert_not_called()
    mock_logger.info.assert_called_with(
        "scheduled_tasks_skipped",
        reason="prefix_not_empty",
    )


@pytest.mark.integration
def test_lifespan_start_scheduled_tasks_runs_when_prefix_empty(
    mock_settings, mock_bot, monkeypatch
):
    """Test that _start_scheduled_tasks starts when PREFIX is empty."""
    # Arrange
    mock_logger = MagicMock()
    mock_settings.PREFIX = ""
    init_mock = MagicMock()
    stop_event = threading.Event()
    run_mock = MagicMock(return_value=stop_event)
    monkeypatch.setattr("server.lifespan.scheduled_tasks.init", init_mock)
    monkeypatch.setattr("server.lifespan.scheduled_tasks.run_continuously", run_mock)

    # Act
    result = _start_scheduled_tasks(mock_bot, mock_settings, mock_logger)

    # Assert
    assert result is stop_event
    init_mock.assert_called_once_with(mock_bot)
    run_mock.assert_called_once()
    mock_logger.info.assert_called_with("scheduled_tasks_started")


@pytest.mark.integration
def test_lifespan_activate_providers_sets_app_state(mock_settings, monkeypatch):
    """Test that _activate_providers sets provider state on app."""
    # Arrange
    app = FastAPI()
    mock_logger = MagicMock()
    register_mock = MagicMock()
    discover_mock = MagicMock()
    log_mock = MagicMock()
    load_mock = MagicMock(return_value="primary")
    active_mock = MagicMock(return_value={"primary": "provider"})
    primary_mock = MagicMock(return_value="primary")

    monkeypatch.setattr(
        "server.lifespan.register_infrastructure_handlers", register_mock
    )
    monkeypatch.setattr("server.lifespan.discover_and_register_handlers", discover_mock)
    monkeypatch.setattr("server.lifespan.log_registered_handlers", log_mock)
    monkeypatch.setattr("server.lifespan.load_providers", load_mock)
    monkeypatch.setattr("server.lifespan.get_active_providers", active_mock)
    monkeypatch.setattr("server.lifespan.get_primary_provider_name", primary_mock)

    # Act
    _activate_providers(app, mock_settings, mock_logger)

    # Assert
    assert app.state.providers == {"primary": "provider"}
    assert app.state.primary_provider_name == "primary"
    register_mock.assert_called_once()
    discover_mock.assert_called_once_with(base_path="modules", package_root="modules")
    log_mock.assert_called_once()
