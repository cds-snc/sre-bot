from unittest.mock import MagicMock, patch

from slack_sdk.errors import SlackApiError
from modules.ops import notifications


@patch("modules.ops.notifications.OPS_CHANNEL_ID", "C0123456ABC")
@patch("modules.ops.notifications.SlackClientManager.get_client")
@patch("modules.ops.notifications.logger")
def test_log_ops_message(mock_logger, mock_get_client):
    client = MagicMock()
    mock_get_client.return_value = client
    msg = "foo bar baz"
    notifications.log_ops_message(msg)
    client.chat_postMessage.assert_called_with(
        channel="C0123456ABC", text=msg, as_user=True
    )
    mock_logger.info.assert_called_with("ops_message_logged", message=msg)


@patch("modules.ops.notifications.OPS_CHANNEL_ID", "C0123456ABC")
@patch("modules.ops.notifications.SlackClientManager.get_client")
@patch("modules.ops.notifications.logger")
def test_log_ops_message_no_client(mock_logger, mock_get_client):
    msg = "foo bar baz"
    mock_get_client.return_value = None
    notifications.log_ops_message(msg)
    mock_logger.error.assert_called_with("slack_client_not_initialized")


@patch("modules.ops.notifications.OPS_CHANNEL_ID", "")
@patch("modules.ops.notifications.SlackClientManager.get_client")
@patch("modules.ops.notifications.logger")
def test_log_ops_message_no_channel(mock_logger, mock_get_client):
    msg = "foo bar baz"
    mock_get_client.return_value = MagicMock()
    notifications.log_ops_message(msg)
    mock_logger.warning.assert_called_with("ops_channel_id_not_configured")


@patch("modules.ops.notifications.OPS_CHANNEL_ID", "C0123456ABC")
@patch("modules.ops.notifications.SlackClientManager.get_client")
@patch("modules.ops.notifications.logger")
def test_log_ops_message_slack_api_error(mock_logger, mock_get_client):
    client = MagicMock()
    mock_get_client.return_value = client
    msg = "foo bar baz"
    error_message = "Some Slack API error"
    mock_response = MagicMock()
    client.chat_postMessage.side_effect = SlackApiError(error_message, mock_response)

    notifications.log_ops_message(msg)

    client.chat_postMessage.assert_called_with(
        channel="C0123456ABC", text=msg, as_user=True
    )
    mock_logger.error.assert_called_with(
        "ops_message_failed",
        message=msg,
        error=f"{error_message}\nThe server responded with: {mock_response}",
    )
