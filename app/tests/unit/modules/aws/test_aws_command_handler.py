"""Unit tests for AWS module command handler."""

from unittest.mock import MagicMock, patch

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
@patch("modules.aws.aws.aws_access_requests.request_access_modal")
@patch("modules.aws.aws.slack_commands.parse_command")
def test_should_open_access_modal_when_access_command_given(mock_parse_command, mock_request_access_modal, make_command):
    """Test that access command opens modal."""
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
    mock_request_access_modal.assert_called_once_with(client, body)
    respond.assert_not_called()


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
    mock_spending_data = MagicMock()
    mock_generate.return_value = mock_spending_data

    # Act
    aws.aws_command(ack, command, respond, MagicMock(), MagicMock())

    # Assert
    ack.assert_called_once()
    assert respond.call_count == 2
    mock_generate.assert_called_once()
    mock_update.assert_called_once_with(mock_spending_data)


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


@pytest.mark.unit
@patch("modules.aws.aws.aws_access_requests.create_aws_access_request")
@patch("modules.aws.aws.identity_store")
@patch("modules.aws.aws.get_account_id_by_name")
def test_should_pass_through_account_id_and_user_id_on_success(mock_get_account_id, mock_identity_store, mock_create_request):
    """Test request_aws_account_access pins today's positional call shape into
    create_aws_access_request.

    Stub strategy: get_account_id_by_name and identity_store.get_user_id resolve
    successfully; create_aws_access_request is mocked so no DynamoDB write occurs.
    The assertion pins the exact positional argument order the caller uses today --
    which is shifted relative to create_aws_access_request's real parameter list
    (access_type and start_date_time land in each other's slots) -- as a defect to
    revisit only if this dead code path is ever wired back into production use.
    """
    # Arrange
    mock_get_account_id.return_value = "account-123"
    mock_identity_store.get_user_id.return_value = "user-123"
    mock_create_request.return_value = True

    # Act
    aws.request_aws_account_access(
        "TestAccount",
        "Test rationale",
        "2024-01-01",
        "2024-01-31",
        "user@example.com",
        "read",
    )

    # Assert
    mock_create_request.assert_called_once_with(
        "account-123",
        "TestAccount",
        "user-123",
        "user@example.com",
        "2024-01-01",
        "2024-01-31",
        "read",
        "Test rationale",
    )


@pytest.mark.unit
@patch("modules.aws.aws.aws_access_requests.create_aws_access_request")
@patch("modules.aws.aws.identity_store")
@patch("modules.aws.aws.get_account_id_by_name")
def test_should_proceed_with_false_account_id_when_organizations_lookup_fails(
    mock_get_account_id, mock_identity_store, mock_create_request
):
    """Test request_aws_account_access has no guard against a failed account lookup.

    Stub strategy: get_account_id_by_name returns the literal False that
    handle_aws_api_errors produces on error; there is no `is None`/`if not` check
    on account_id, so create_aws_access_request is still invoked with False.
    """
    # Arrange
    mock_get_account_id.return_value = False
    mock_identity_store.get_user_id.return_value = "user-123"
    mock_create_request.return_value = True

    # Act
    aws.request_aws_account_access(
        "TestAccount",
        "Test rationale",
        "2024-01-01",
        "2024-01-31",
        "user@example.com",
        "read",
    )

    # Assert
    mock_create_request.assert_called_once()
    assert mock_create_request.call_args.args[0] is False


@pytest.mark.unit
@patch("modules.aws.aws.aws_access_requests.create_aws_access_request")
@patch("modules.aws.aws.identity_store")
@patch("modules.aws.aws.get_account_id_by_name")
def test_should_proceed_with_false_user_id_when_identity_store_lookup_fails(
    mock_get_account_id, mock_identity_store, mock_create_request
):
    """Test request_aws_account_access has no guard against a failed user lookup.

    Stub strategy: identity_store.get_user_id returns the literal False that
    handle_aws_api_errors produces on error; there is no guard on user_id, so
    create_aws_access_request is still invoked with False.
    """
    # Arrange
    mock_get_account_id.return_value = "account-123"
    mock_identity_store.get_user_id.return_value = False
    mock_create_request.return_value = True

    # Act
    aws.request_aws_account_access(
        "TestAccount",
        "Test rationale",
        "2024-01-01",
        "2024-01-31",
        "user@example.com",
        "read",
    )

    # Assert
    mock_create_request.assert_called_once()
    assert mock_create_request.call_args.args[2] is False
