from unittest.mock import MagicMock, patch

from slack_sdk.errors import SlackApiError
from modules.ops import notifications


@patch("modules.ops.notifications.OPS_CHANNEL_ID", "C0123456ABC")
@patch("modules.ops.notifications.logger")
def test_log_ops_message(mock_logger):
    client = MagicMock()
    msg = "foo bar baz"
    notifications.log_ops_message(client, msg)
    client.chat_postMessage.assert_called_with(
        channel="C0123456ABC", text=msg, as_user=True
    )
    mock_logger.info.assert_called_with("ops_message_logged", message=msg)


@patch("modules.ops.notifications.OPS_CHANNEL_ID", "")
@patch("modules.ops.notifications.logger")
def test_log_ops_message_no_channel(mock_logger):
    client = MagicMock()
    msg = "foo bar baz"
    notifications.log_ops_message(client, msg)
    client.chat_postMessage.assert_not_called()
    client.conversations_join.assert_not_called()
    mock_logger.warning.assert_called_with("ops_channel_id_not_configured")


@patch("modules.ops.notifications.OPS_CHANNEL_ID", "C0123456ABC")
@patch("modules.ops.notifications.logger")
def test_log_ops_message_slack_api_error(mock_logger):
    client = MagicMock()
    msg = "foo bar baz"
    error_message = "Some Slack API error"
    mock_response = MagicMock()
    client.chat_postMessage.side_effect = SlackApiError(error_message, mock_response)

    notifications.log_ops_message(client, msg)

    client.chat_postMessage.assert_called_with(
        channel="C0123456ABC", text=msg, as_user=True
    )
    mock_logger.error.assert_called_with(
        "ops_message_failed",
        message=msg,
        error=f"{error_message}\nThe server responded with: {mock_response}",
    )
