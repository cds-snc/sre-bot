"""Integration tests for server.lifespan module."""

import sys
import threading
from unittest.mock import MagicMock, patch

import pytest

from server import lifespan as lifespan_module
from server.lifespan import (
    _get_logger_from_app,
    _initialize_directory_provider,
    _is_test_environment,
    _list_configs_from_sections,
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
    logger = _get_logger_from_app(mock_settings)

    # Assert
    assert logger is not None


@pytest.mark.integration
def test_lifespan_list_configs_logs_settings(mock_settings):
    """Test that _list_configs logs configuration settings."""
    # Arrange
    mock_logger = MagicMock()
    mock_server_settings = MagicMock()
    mock_server_settings.model_dump.return_value = {"PORT": 8080}
    mock_directory_settings = MagicMock()
    mock_directory_settings.model_dump.return_value = {"require_startup_warmup": True}
    mock_sre_ops_settings = MagicMock()
    mock_sre_ops_settings.model_dump.return_value = {"SRE_OPS_CHANNEL_ID": ""}

    # Act
    _list_configs_from_sections(
        mock_settings,
        mock_server_settings,
        mock_directory_settings,
        mock_sre_ops_settings,
        mock_logger,
    )

    # Assert
    mock_logger.info.assert_called()
    first_call = mock_logger.info.call_args_list[0]
    assert first_call.args[0] == "configuration_initialized"

    base_settings = first_call.kwargs["base_settings"]
    assert all("PREFIX" not in entry for entry in base_settings)


@pytest.mark.integration
@patch("server.lifespan.configure_logging")
def test_lifespan_get_logger_configures_logging(mock_configure_logging, mock_settings):
    """Test that _get_logger calls configure_logging with settings."""
    # Arrange
    mock_logger = MagicMock()
    mock_configure_logging.return_value = mock_logger

    # Act
    logger = _get_logger_from_app(mock_settings)

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
def test_lifespan_start_scheduled_tasks_runs_when_environment_is_prod(
    mock_settings, mock_bot, monkeypatch
):
    """Test that _start_scheduled_tasks starts when ENVIRONMENT is production."""
    # Arrange
    mock_logger = MagicMock()
    mock_settings.ENVIRONMENT = "production"
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
def test_lifespan_start_scheduled_tasks_skips_when_environment_is_not_production(
    mock_settings, mock_bot, monkeypatch
):
    """Test that _start_scheduled_tasks skips when ENVIRONMENT is non-production."""
    # Arrange
    mock_logger = MagicMock()
    mock_settings.ENVIRONMENT = "local"
    init_mock = MagicMock()
    run_mock = MagicMock()
    monkeypatch.setattr("server.lifespan.scheduled_tasks.init", init_mock)
    monkeypatch.setattr("server.lifespan.scheduled_tasks.run_continuously", run_mock)

    # Act
    result = _start_scheduled_tasks(mock_bot, mock_settings, mock_logger)

    # Assert
    assert result is None
    init_mock.assert_not_called()
    run_mock.assert_not_called()
    mock_logger.info.assert_called_with(
        "scheduled_tasks_skipped",
        reason="environment_is_not_production",
    )


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
