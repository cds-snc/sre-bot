from unittest.mock import MagicMock, patch

from slack_sdk.errors import SlackApiError

from modules.ops import notifications


@patch("modules.ops.notifications.get_sre_ops_settings")
@patch("modules.ops.notifications.SlackClientManager.get_client")
@patch("modules.ops.notifications.logger")
def test_log_ops_message(mock_logger, mock_get_client, mock_get_sre_ops_settings):
    client = MagicMock()
    mock_get_client.return_value = client
    mock_get_sre_ops_settings.return_value.SRE_OPS_CHANNEL_ID = "C0123456ABC"

    # Patch logger.bind() to return a mock with .info/.error/.warning
    bound_logger = MagicMock()
    mock_logger.bind.return_value = bound_logger

    msg = "foo bar baz"
    notifications.log_ops_message(msg)
    client.chat_postMessage.assert_called_with(
        channel="C0123456ABC", text=msg, as_user=True
    )
    bound_logger.info.assert_any_call(
        "ops_message_log_attempted",
        channel_id="C0123456ABC",
    )
    bound_logger.info.assert_any_call(
        "ops_message_logged",
        channel_id="C0123456ABC",
    )


@patch("modules.ops.notifications.get_sre_ops_settings")
@patch("modules.ops.notifications.SlackClientManager.get_client")
@patch("modules.ops.notifications.logger")
def test_log_ops_message_no_client(
    mock_logger, mock_get_client, mock_get_sre_ops_settings
):
    msg = "foo bar baz"
    mock_get_client.return_value = None
    mock_get_sre_ops_settings.return_value.SRE_OPS_CHANNEL_ID = "C0123456ABC"
    bound_logger = MagicMock()
    mock_logger.bind.return_value = bound_logger

    notifications.log_ops_message(msg)
    bound_logger.error.assert_called_with(
        "slack_client_not_initialized",
    )


@patch("modules.ops.notifications.get_sre_ops_settings")
@patch("modules.ops.notifications.SlackClientManager.get_client")
@patch("modules.ops.notifications.logger")
def test_log_ops_message_no_channel(
    mock_logger, mock_get_client, mock_get_sre_ops_settings
):
    msg = "foo bar baz"
    mock_get_sre_ops_settings.return_value.SRE_OPS_CHANNEL_ID = None
    mock_get_client.return_value = MagicMock()
    bound_logger = MagicMock()
    mock_logger.bind.return_value = bound_logger

    notifications.log_ops_message(msg)
    bound_logger.warning.assert_called_with(
        "ops_channel_id_not_configured",
    )


@patch("modules.ops.notifications.get_sre_ops_settings")
@patch("modules.ops.notifications.SlackClientManager.get_client")
@patch("modules.ops.notifications.logger")
def test_log_ops_message_slack_api_error(
    mock_logger, mock_get_client, mock_get_sre_ops_settings
):
    client = MagicMock()
    mock_get_client.return_value = client
    mock_get_sre_ops_settings.return_value.SRE_OPS_CHANNEL_ID = "C0123456ABC"
    bound_logger = MagicMock()
    mock_logger.bind.return_value = bound_logger
    msg = "foo bar baz"
    error_message = "Some Slack API error"
    mock_response = MagicMock()
    client.chat_postMessage.side_effect = SlackApiError(error_message, mock_response)

    notifications.log_ops_message(msg)

    client.chat_postMessage.assert_called_with(
        channel="C0123456ABC", text=msg, as_user=True
    )
    bound_logger.error.assert_called_with(
        "ops_message_failed",
        channel_id="C0123456ABC",
        error=str(SlackApiError(error_message, mock_response)),
    )
