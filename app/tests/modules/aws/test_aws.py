from modules import aws

from unittest.mock import MagicMock, patch, call


@patch("modules.aws.aws.logger")
def test_aws_command_handles_empty_command(mock_logger):
    ack = MagicMock()
    respond = MagicMock()
    command = command_helper("")
    aws.aws_command(ack, command, respond, MagicMock(), MagicMock())
    ack.assert_called()
    respond.assert_called()
    mock_logger.info.assert_called_with(
        "aws_command_received",
        command="",
        user_id=command["user_id"],
        user_name=command["user_name"],
        channel_id=command["channel_id"],
        channel_name=command["channel_name"],
    )


@patch("modules.aws.aws.logger")
def test_aws_command_handles_help_command(mock_logger):
    ack = MagicMock()
    respond = MagicMock()
    command = command_helper("help")
    aws.aws_command(ack, command, respond, MagicMock(), MagicMock())
    ack.assert_called()
    respond.assert_called_with(aws.help_text)
    mock_logger.info.assert_called_with(
        "aws_command_received",
        command="help",
        user_id=command["user_id"],
        user_name=command["user_name"],
        channel_id=command["channel_id"],
        channel_name=command["channel_name"],
    )


@patch("modules.aws.aws.aws_access_requests.request_access_modal")
def test_aws_command_handles_access_command(request_access_modal):
    ack = MagicMock()
    respond = MagicMock()
    client = MagicMock()
    body = MagicMock()
    command = command_helper("access")
    aws.aws_command(ack, command, respond, client, body)
    ack.assert_called()
    request_access_modal.assert_called_with(client, body)


@patch("modules.aws.aws.logger")
@patch("modules.aws.aws.slack_commands.parse_command")
@patch("modules.aws.users.command_handler")
def test_aws_command_handles_users_command(
    users_command_handler: MagicMock,
    mock_parse_command: MagicMock,
    mock_logger: MagicMock,
):
    ack = MagicMock()
    respond = MagicMock()
    client = MagicMock()
    body = MagicMock()
    command = command_helper("users sync")
    mock_parse_command.return_value = ["users", "sync"]
    aws.aws_command(ack, command, respond, client, body)
    ack.assert_called()
    users_command_handler.assert_called_with(
        client, body, respond, ["sync"], mock_logger
    )


@patch("modules.aws.aws.logger")
@patch("modules.aws.aws.slack_commands.parse_command")
@patch("modules.aws.groups.command_handler")
def test_aws_command_handles_groups_command(
    groups_command_handler: MagicMock,
    mock_parse_command: MagicMock,
    mock_logger: MagicMock,
):
    ack = MagicMock()
    respond = MagicMock()
    client = MagicMock()
    body = MagicMock()
    command = command_helper("groups sync")
    mock_parse_command.return_value = ["groups", "sync"]
    aws.aws_command(ack, command, respond, client, body)
    ack.assert_called()
    groups_command_handler.assert_called_with(
        client, body, respond, ["sync"], mock_logger
    )


@patch("modules.aws.aws.logger")
@patch("modules.aws.aws.slack_commands.parse_command")
@patch("modules.aws.lambdas.command_handler")
def test_aws_command_handles_lambdas_command(
    lambdas_command_handler: MagicMock,
    mock_parse_command: MagicMock,
    mock_logger: MagicMock,
):
    ack = MagicMock()
    respond = MagicMock()
    client = MagicMock()
    body = MagicMock()
    command = command_helper("lambdas sync")
    mock_parse_command.return_value = ["lambdas", "sync"]
    aws.aws_command(ack, command, respond, client, body)
    ack.assert_called()
    lambdas_command_handler.assert_called_with(
        client, body, respond, ["sync"], mock_logger
    )


@patch("modules.aws.aws.slack_commands.parse_command")
@patch("modules.aws.aws.aws_account_health.request_health_modal")
def test_aws_command_handles_health_command(
    request_health_modal: MagicMock, mock_parse_command: MagicMock
):
    ack = MagicMock()
    respond = MagicMock()
    client = MagicMock()
    body = MagicMock()
    command = command_helper("health")
    mock_parse_command.return_value = ["health"]
    aws.aws_command(ack, command, respond, client, body)
    ack.assert_called()
    request_health_modal.assert_called_with(client, body)


@patch("modules.aws.aws.logger")
@patch("modules.aws.aws.spending")
@patch("modules.aws.aws.slack_commands.parse_command")
def test_aws_command_handles_spending_command(
    mock_parse_command: MagicMock, mock_spending: MagicMock, mock_logger: MagicMock
):
    ack = MagicMock()
    respond = MagicMock()
    client = MagicMock()
    body = MagicMock()
    command = command_helper("spending")
    mock_parse_command.return_value = ["spending"]
    mock_spending.generate_spending_data.return_value = "spending_data"
    aws.aws_command(ack, command, respond, client, body)
    ack.assert_called()
    respond.assert_has_calls(
        [
            call("Generating spending data...\nGénération des données de dépenses..."),
            call(
                "Spending data has been updated.\nLes données de dépenses ont été mises à jour."
            ),
        ]
    )
    mock_spending.generate_spending_data.assert_called_with(mock_logger)
    mock_spending.update_spending_data.assert_called_with("spending_data", mock_logger)


@patch("modules.aws.aws.logger")
@patch("modules.aws.aws.spending")
@patch("modules.aws.aws.slack_commands.parse_command")
def test_aws_command_handles_spending_command_without_data(
    mock_parse_command: MagicMock, mock_spending: MagicMock, mock_logger: MagicMock
):
    ack = MagicMock()
    respond = MagicMock()
    client = MagicMock()
    body = MagicMock()
    command = command_helper("spending")
    mock_parse_command.return_value = ["spending"]
    mock_spending.generate_spending_data.return_value = None
    aws.aws_command(ack, command, respond, client, body)
    ack.assert_called()
    respond.assert_has_calls(
        [
            call("Generating spending data...\nGénération des données de dépenses..."),
            call(
                "Failed to generate spending data. Please try again later.\nÉchec de la génération des données de dépenses. Veuillez réessayer plus tard."
            ),
        ]
    )
    mock_spending.generate_spending_data.assert_called_with(mock_logger)
    mock_spending.update_spending_data.assert_not_called()


@patch("modules.aws.aws.spending")
@patch("modules.aws.aws.slack_commands.parse_command")
def test_aws_command_handles_unknown_command(mock_parse_command, _mock_spending):
    ack = MagicMock()
    respond = MagicMock()
    mock_parse_command.return_value = ["unknown"]
    command = command_helper("unknown")
    aws.aws_command(ack, command, respond, MagicMock(), MagicMock())
    ack.assert_called()
    respond.assert_called_with(
        "Unknown command: `unknown`. Type `/aws help` to see a list of commands.\nCommande inconnue: `unknown`. Tapez `/aws help` pour voir une liste des commandes."
    )


@patch("modules.aws.aws_access_requests.create_aws_access_request")
@patch("integrations.aws.identity_store.get_user_id")
@patch("integrations.aws.organizations.get_account_id_by_name")
@patch("integrations.aws.organizations.list_organization_accounts")
def test_request_aws_account_access_success(
    mock_list_organization_accounts,
    mock_get_account_id_by_name,
    mock_get_user_id,
    mock_create_aws_access_request,
):
    # Mock return value
    mock_accounts = [
        {
            "Id": "345678901234",
            "Arn": "arn:aws:organizations::345678901234:account/o-exampleorgid/345678901234",
            "Email": "example3@example.com",
            "Name": "ExampleAccount",
            "Status": "ACTIVE",
            "JoinedMethod": "INVITED",
            "JoinedTimestamp": "2023-02-15T12:00:00.000000+00:00",
        }
    ]

    mock_list_organization_accounts.return_value = mock_accounts
    mock_get_account_id_by_name.return_value = "345678901234"
    mock_get_user_id.return_value = "user_id_456"
    mock_create_aws_access_request.return_value = (
        True  # Assuming the function returns True on success
    )

    account_name = "ExampleAccount"
    rationale = "test_rationale"
    start_date = "2024-07-01T00:00:00Z"
    end_date = "2024-07-02T00:00:00Z"
    user_email = "user@example.com"
    access_type = "read"

    # Act
    result = aws.request_aws_account_access(
        account_name, rationale, start_date, end_date, user_email, access_type
    )

    # Assert
    assert result is True
    mock_get_user_id.assert_called_once_with(user_email)
    mock_create_aws_access_request.assert_called_once_with(
        "345678901234",
        account_name,
        "user_id_456",
        user_email,
        start_date,
        end_date,
        access_type,
        rationale,
    )


@patch("modules.aws.aws_access_requests.create_aws_access_request")
@patch("integrations.aws.identity_store.get_user_id")
@patch("integrations.aws.organizations.get_account_id_by_name")
@patch("integrations.aws.organizations.list_organization_accounts")
def test_request_aws_account_access_failure(
    mock_list_organization_accounts,
    mock_get_account_id_by_name,
    mock_get_user_id,
    mock_create_aws_access_request,
):
    # Mock return value
    mock_accounts = [
        {
            "Id": "345678901234",
            "Arn": "arn:aws:organizations::345678901234:account/o-exampleorgid/345678901234",
            "Email": "example3@example.com",
            "Name": "ExampleAccount",
            "Status": "ACTIVE",
            "JoinedMethod": "INVITED",
            "JoinedTimestamp": "2023-02-15T12:00:00.000000+00:00",
        }
    ]
    mock_list_organization_accounts.return_value = mock_accounts
    mock_get_account_id_by_name.return_value = "345678901234"
    mock_get_user_id.return_value = "user_id_456"
    mock_create_aws_access_request.return_value = (
        False  # Assuming the function returns False on failure
    )

    account_name = "ExampleAccount"
    rationale = "test_rationale"
    start_date = "2024-07-01T00:00:00Z"
    end_date = "2024-07-02T00:00:00Z"
    user_email = "user@example.com"
    access_type = "read"

    # Act
    result = aws.request_aws_account_access(
        account_name, rationale, start_date, end_date, user_email, access_type
    )

    # Assert
    assert result is False
    mock_get_user_id.assert_called_once_with(user_email)
    mock_create_aws_access_request.assert_called_once_with(
        "345678901234",
        account_name,
        "user_id_456",
        user_email,
        start_date,
        end_date,
        access_type,
        rationale,
    )


def command_helper(text: str):
    """
    Helper function to create a command dictionary.
    """
    return {
        "text": text,
        "user_id": "U123456",
        "user_name": "test_user",
        "channel_id": "C123456",
        "channel_name": "test_channel",
    }
