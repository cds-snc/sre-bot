"""Integration tests for server.lifespan module."""

from unittest.mock import MagicMock, patch
import sys

import pytest


@pytest.mark.integration
def test_lifespan_is_test_environment_detects_pytest():
    """Test that _is_test_environment detects pytest environment."""
    # Arrange
    from server.lifespan import _is_test_environment

    # Act
    is_test = _is_test_environment()

    # Assert
    assert is_test is True


@pytest.mark.integration
def test_lifespan_is_test_environment_detects_non_pytest():
    """Test that _is_test_environment returns False when pytest not loaded."""
    # Arrange
    from server import lifespan as lifespan_module

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
    from server.lifespan import _get_logger

    # Act
    logger = _get_logger(mock_settings)

    # Assert
    assert logger is not None


@pytest.mark.integration
def test_lifespan_list_configs_logs_settings(mock_settings):
    """Test that _list_configs logs configuration settings."""
    # Arrange
    from server.lifespan import _list_configs
    from unittest.mock import MagicMock

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
    from server.lifespan import _get_logger

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
    from server.lifespan import _register_legacy_handlers
    from unittest.mock import MagicMock, patch

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
@patch("server.lifespan.SocketModeHandler")
def test_lifespan_start_socket_mode_creates_handler(mock_handler_class, mock_bot):
    """Test that _start_socket_mode creates and starts SocketModeHandler."""
    # Arrange
    from server.lifespan import _start_socket_mode
    from unittest.mock import MagicMock

    mock_handler = MagicMock()
    mock_handler_class.return_value = mock_handler
    mock_logger = MagicMock()
    app_token = "xapp-test-token"

    # Act
    handler, thread = _start_socket_mode(mock_bot, app_token, mock_logger)

    # Assert
    assert handler == mock_handler
    assert thread is not None
    assert thread.daemon is True
    assert thread.name == "slack-socket-mode"
    mock_logger.info.assert_called_with("socket_mode_started")


@pytest.mark.integration
def test_lifespan_stop_scheduled_tasks_with_none_event():
    """Test that _stop_scheduled_tasks handles None event gracefully."""
    # Arrange
    from server.lifespan import _stop_scheduled_tasks

    # Act
    _stop_scheduled_tasks(None)

    # Assert - Should not raise


@pytest.mark.integration
def test_lifespan_stop_scheduled_tasks_sets_event():
    """Test that _stop_scheduled_tasks sets the stop event."""
    # Arrange
    from server.lifespan import _stop_scheduled_tasks
    from unittest.mock import MagicMock

    mock_event = MagicMock()

    # Act
    _stop_scheduled_tasks(mock_event)

    # Assert
    mock_event.set.assert_called_once()


@pytest.mark.integration
def test_lifespan_get_bot_returns_none_in_test_environment(mock_settings):
    """Test that _get_bot returns None in test environment."""
    # Arrange
    from server.lifespan import _get_bot

    # Act
    bot = _get_bot(mock_settings)

    # Assert
    assert bot is None


@pytest.mark.integration
@patch("server.lifespan._is_test_environment")
def test_lifespan_get_bot_returns_none_when_no_token(mock_is_test, mock_settings):
    """Test that _get_bot returns None when SLACK_TOKEN is empty."""
    # Arrange
    from server.lifespan import _get_bot

    mock_is_test.return_value = False
    mock_settings.slack.SLACK_TOKEN = ""

    # Act
    bot = _get_bot(mock_settings)

    # Assert
    assert bot is None


@pytest.mark.integration
@patch("server.lifespan.App")
@patch("server.lifespan._is_test_environment")
def test_lifespan_get_bot_creates_app_with_token(
    mock_is_test, mock_app_class, mock_settings
):
    """Test that _get_bot creates App instance with token."""
    # Arrange
    from server.lifespan import _get_bot

    mock_is_test.return_value = False
    mock_settings.slack.SLACK_TOKEN = "xoxb-test-token"
    mock_app_instance = MagicMock()
    mock_app_class.return_value = mock_app_instance

    # Act
    bot = _get_bot(mock_settings)

    # Assert
    assert bot == mock_app_instance
    mock_app_class.assert_called_once_with(token="xoxb-test-token")
