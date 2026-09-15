"""Unit tests for AWS module command handler."""

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from modules.aws import aws


@pytest.fixture
def make_command():
    """Factory for creating command dictionaries."""

    def _make(text: str = ""):
        return {
            "text": text,
            "user_id": "U123456",
            "user_name": "test_user",
            "channel_id": "C123456",
            "channel_name": "test_channel",
        }

    return _make


@pytest.mark.unit
@patch("modules.aws.aws.slack_commands.parse_command")
def test_should_acknowledge_and_show_help_when_command_text_empty(mock_parse_command, make_command):
    """Test that empty command text shows help message."""
    # Arrange
    ack = MagicMock()
    respond = MagicMock()
    command = make_command("")
    mock_parse_command.return_value = []

    # Act
    aws.aws_command(ack, command, respond, MagicMock(), MagicMock())

    # Assert
    ack.assert_called_once()
    respond.assert_called_once()
    assert "Type `/aws help`" in respond.call_args[0][0]


@pytest.mark.unit
@patch("modules.aws.aws.slack_commands.parse_command")
def test_should_respond_with_help_text_when_help_command_given(mock_parse_command, make_command):
    """Test that help command returns help text."""
    # Arrange
    ack = MagicMock()
    respond = MagicMock()
    command = make_command("help")
    mock_parse_command.return_value = ["help"]

    # Act
    aws.aws_command(ack, command, respond, MagicMock(), MagicMock())

    # Assert
    ack.assert_called_once()
    respond.assert_called_once_with(aws.help_text)


@pytest.mark.unit
@patch("modules.aws.aws.slack_commands.parse_command")
def test_should_reply_unknown_command_when_access_command_given(mock_parse_command, make_command):
    """The `access` action is not routed and falls through to the unknown-command reply.

    Stub strategy: parse_command returns the bare action. client is a MagicMock,
    so any attempt to open a Slack modal is recorded. Asserts a single reply
    naming `access` as unknown, and that no view is opened.
    """
    # Arrange
    ack = MagicMock()
    respond = MagicMock()
    client = MagicMock()
    body = {"trigger_id": "test_trigger"}
    command = make_command("access")
    mock_parse_command.return_value = ["access"]

    # Act
    aws.aws_command(ack, command, respond, client, body)

    # Assert
    ack.assert_called_once()
    respond.assert_called_once()
    assert "Unknown command: `access`" in respond.call_args[0][0]
    client.views_open.assert_not_called()


@pytest.mark.unit
def test_should_not_advertise_or_expose_aws_account_access_requests():
    """The help text does not list `/aws access`, and the module exposes no account-access request helper.

    Asserts on the module's public surface directly; no stubs are needed.
    """
    assert "/aws access" not in aws.help_text
    assert not hasattr(aws, "request_aws_account_access")


@pytest.mark.unit
@patch("modules.aws.aws.aws_account_health.request_health_modal")
@patch("modules.aws.aws.slack_commands.parse_command")
def test_should_open_health_modal_when_health_command_given(mock_parse_command, mock_request_health_modal, make_command):
    """Test that health command opens modal."""
    # Arrange
    ack = MagicMock()
    respond = MagicMock()
    client = MagicMock()
    body = {"trigger_id": "test_trigger"}
    command = make_command("health")
    mock_parse_command.return_value = ["health"]

    # Act
    aws.aws_command(ack, command, respond, client, body)

    # Assert
    ack.assert_called_once()
    mock_request_health_modal.assert_called_once_with(client, body)
    respond.assert_not_called()


@pytest.mark.unit
@patch("modules.aws.aws.users.command_handler")
@patch("modules.aws.aws.slack_commands.parse_command")
def test_should_delegate_to_users_handler_when_users_command_given(mock_parse_command, mock_users_handler, make_command):
    """Test that users command delegates to handler."""
    # Arrange
    ack = MagicMock()
    respond = MagicMock()
    client = MagicMock()
    body = MagicMock()
    command = make_command("users sync")
    mock_parse_command.return_value = ["users", "sync"]

    # Act
    aws.aws_command(ack, command, respond, client, body)

    # Assert
    ack.assert_called_once()
    mock_users_handler.assert_called_once_with(client, body, respond, ["sync"])


@pytest.mark.unit
@patch("modules.aws.aws.groups.command_handler")
@patch("modules.aws.aws.slack_commands.parse_command")
def test_should_delegate_to_groups_handler_when_groups_command_given(mock_parse_command, mock_groups_handler, make_command):
    """Test that groups command delegates to handler."""
    # Arrange
    ack = MagicMock()
    respond = MagicMock()
    client = MagicMock()
    body = MagicMock()
    command = make_command("groups sync")
    mock_parse_command.return_value = ["groups", "sync"]

    # Act
    aws.aws_command(ack, command, respond, client, body)

    # Assert
    ack.assert_called_once()
    mock_groups_handler.assert_called_once_with(client, body, respond, ["sync"])


@pytest.mark.unit
@patch("modules.aws.aws.lambdas.command_handler")
@patch("modules.aws.aws.slack_commands.parse_command")
def test_should_delegate_to_lambdas_handler_when_lambdas_command_given(mock_parse_command, mock_lambdas_handler, make_command):
    """Test that lambdas command delegates to handler."""
    # Arrange
    ack = MagicMock()
    respond = MagicMock()
    client = MagicMock()
    body = MagicMock()
    command = make_command("lambdas list")
    mock_parse_command.return_value = ["lambdas", "list"]

    # Act
    aws.aws_command(ack, command, respond, client, body)

    # Assert
    ack.assert_called_once()
    mock_lambdas_handler.assert_called_once_with(client, body, respond, ["list"])


@pytest.mark.unit
@patch("modules.aws.aws.spending.update_spending_data")
@patch("modules.aws.aws.spending.generate_spending_data")
@patch("modules.aws.aws.slack_commands.parse_command")
def test_should_generate_and_update_spending_when_spending_command_given(
    mock_parse_command, mock_generate, mock_update, make_command
):
    """Test that spending command generates and updates data."""
    # Arrange
    ack = MagicMock()
    respond = MagicMock()
    command = make_command("spending")
    mock_parse_command.return_value = ["spending"]
    mock_spending_data = pd.DataFrame({"Linked account": ["123456789012"], "Cost Amount": [100.00]})
    mock_generate.return_value = mock_spending_data
    mock_update.return_value = True

    # Act
    aws.aws_command(ack, command, respond, MagicMock(), MagicMock())

    # Assert
    ack.assert_called_once()
    assert respond.call_count == 2
    mock_generate.assert_called_once()
    mock_update.assert_called_once_with(mock_spending_data)
    assert "has been updated" in respond.call_args_list[1][0][0]


@pytest.mark.unit
@patch("modules.aws.aws.spending.update_spending_data")
@patch("modules.aws.aws.spending.generate_spending_data")
@patch("modules.aws.aws.slack_commands.parse_command")
def test_should_show_error_when_spending_sheet_update_fails(mock_parse_command, mock_generate, mock_update, make_command):
    """A failed sheet write is reported to the user instead of a success message.

    Stub strategy: generation returns a non-empty DataFrame and
    update_spending_data returns False, its signal for a skipped or failed write.
    """
    # Arrange
    ack = MagicMock()
    respond = MagicMock()
    command = make_command("spending")
    mock_parse_command.return_value = ["spending"]
    mock_generate.return_value = pd.DataFrame({"Linked account": ["123456789012"], "Cost Amount": [100.00]})
    mock_update.return_value = False

    # Act
    aws.aws_command(ack, command, respond, MagicMock(), MagicMock())

    # Assert
    replies = [call.args[0] for call in respond.call_args_list]
    assert len(replies) == 2
    assert "Failed" in replies[1]
    assert "Échec" in replies[1]
    assert not any("has been updated" in reply for reply in replies)


@pytest.mark.unit
@patch("modules.aws.aws.spending.update_spending_data")
@patch("modules.aws.aws.spending.generate_spending_data")
@patch("modules.aws.aws.slack_commands.parse_command")
def test_should_show_error_without_writing_when_spending_data_is_empty(
    mock_parse_command, mock_generate, mock_update, make_command
):
    """An empty spending report is reported as a failure and never written, so it cannot wipe the sheet.

    Stub strategy: generation returns an empty DataFrame; the update function is
    observed to prove no write is attempted.
    """
    # Arrange
    ack = MagicMock()
    respond = MagicMock()
    command = make_command("spending")
    mock_parse_command.return_value = ["spending"]
    mock_generate.return_value = pd.DataFrame()

    # Act
    aws.aws_command(ack, command, respond, MagicMock(), MagicMock())

    # Assert
    mock_update.assert_not_called()
    assert respond.call_count == 2
    assert "Failed" in respond.call_args_list[1][0][0]


@pytest.mark.unit
@patch("modules.aws.aws.spending.generate_spending_data")
@patch("modules.aws.aws.slack_commands.parse_command")
def test_should_show_error_when_spending_data_generation_fails(mock_parse_command, mock_generate, make_command):
    """Test error handling when spending data generation fails."""
    # Arrange
    ack = MagicMock()
    respond = MagicMock()
    command = make_command("spending")
    mock_parse_command.return_value = ["spending"]
    mock_generate.return_value = None

    # Act
    aws.aws_command(ack, command, respond, MagicMock(), MagicMock())

    # Assert
    ack.assert_called_once()
    assert respond.call_count == 2
    assert "Failed" in respond.call_args_list[1][0][0]


@pytest.mark.unit
@patch("modules.aws.aws.slack_commands.parse_command")
def test_should_show_error_for_unknown_command(mock_parse_command, make_command):
    """Test error message for unknown command."""
    # Arrange
    ack = MagicMock()
    respond = MagicMock()
    command = make_command("invalid_command")
    mock_parse_command.return_value = ["invalid_command"]

    # Act
    aws.aws_command(ack, command, respond, MagicMock(), MagicMock())

    # Assert
    ack.assert_called_once()
    respond.assert_called_once()
    assert "Unknown command" in respond.call_args[0][0]
    assert "invalid_command" in respond.call_args[0][0]
