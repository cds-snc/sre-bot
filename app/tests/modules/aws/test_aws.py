from modules import aws

from unittest.mock import MagicMock, patch


def test_aws_command_handles_empty_command():
    ack = MagicMock()
    respond = MagicMock()

    aws.aws_command(ack, {"text": ""}, MagicMock(), respond, MagicMock(), MagicMock())
    ack.assert_called()
    respond.assert_called()


def test_aws_command_handles_help_command():
    ack = MagicMock()
    respond = MagicMock()

    aws.aws_command(
        ack, {"text": "help"}, MagicMock(), respond, MagicMock(), MagicMock()
    )
    ack.assert_called()
    respond.assert_called_with(aws.help_text)


@patch("modules.aws.aws.aws_access_requests.request_access_modal")
def test_aws_command_handles_access_command(request_access_modal):
    ack = MagicMock()
    respond = MagicMock()
    client = MagicMock()
    body = MagicMock()
    aws.aws_command(ack, {"text": "access"}, MagicMock(), respond, client, body)
    ack.assert_called()
    request_access_modal.assert_called_with(client, body)


@patch("modules.aws.aws.slack_commands.parse_command")
@patch("modules.aws.aws.request_user_provisioning")
def test_aws_command_handles_provision_command(
    mock_request_provisioning: MagicMock, mock_parse_command: MagicMock
):
    ack = MagicMock()
    logger = MagicMock()
    respond = MagicMock()
    client = MagicMock()
    body = MagicMock()
    mock_parse_command.return_value = ["user", "create", "user.name@email.com"]
    aws.aws_command(
        ack, {"text": "user create user.name@email.com"}, logger, respond, client, body
    )
    ack.assert_called()
    mock_request_provisioning.assert_called_with(
        client, body, respond, ["create", "user.name@email.com"], logger
    )


@patch("modules.aws.aws.slack_commands.parse_command")
@patch("modules.aws.groups.command_handler")
def test_aws_command_handles_groups_command(
    command_handler: MagicMock, mock_parse_command: MagicMock
):
    ack = MagicMock()
    respond = MagicMock()
    client = MagicMock()
    body = MagicMock()
    logger = MagicMock()
    mock_parse_command.return_value = ["groups", "sync"]
    aws.aws_command(ack, {"text": "groups sync"}, logger, respond, client, body)
    ack.assert_called()
    command_handler.assert_called_with(client, body, respond, ["sync"], logger)


@patch("modules.aws.aws.slack_commands.parse_command")
@patch("modules.aws.aws.aws_account_health.request_health_modal")
def test_aws_command_handles_health_command(
    request_health_modal: MagicMock, mock_parse_command: MagicMock
):
    ack = MagicMock()
    respond = MagicMock()
    client = MagicMock()
    body = MagicMock()
    mock_parse_command.return_value = ["health"]
    aws.aws_command(ack, {"text": "health"}, MagicMock(), respond, client, body)
    ack.assert_called()
    request_health_modal.assert_called_with(client, body)


@patch("modules.aws.aws.slack_commands.parse_command")
def test_aws_command_handles_unknown_command(mock_parse_command):
    ack = MagicMock()
    respond = MagicMock()
    mock_parse_command.return_value = ["unknown"]
    aws.aws_command(
        ack, {"text": "unknown"}, MagicMock(), respond, MagicMock(), MagicMock()
    )
    ack.assert_called()
    respond.assert_called_with(
        "Unknown command: `unknown`. Type `/aws help` to see a list of commands.\nCommande inconnue: `unknown`. Tapez `/aws help` pour voir une liste des commandes."
    )


@patch("modules.aws.aws.AWS_ADMIN_GROUPS", ["admin-group@email.com"])
@patch("modules.aws.aws.provision_aws_users")
@patch("modules.aws.aws.permissions")
@patch("modules.aws.aws.slack_users")
def test_request_user_provisioning(
    mock_slack_users, mock_permissions, mock_provision_aws_user
):
    client = MagicMock()
    body = MagicMock()
    respond = MagicMock()
    logger = MagicMock()
    mock_slack_users.get_user_email_from_body.return_value = "user.name@email.com"
    mock_provision_aws_user.return_value = True
    aws.request_user_provisioning(
        client, body, respond, ["create", "user.email"], logger
    )
    mock_slack_users.get_user_email_from_body.assert_called_with(client, body)
    mock_permissions.is_user_member_of_groups.assert_called_with(
        "user.name@email.com", ["admin-group@email.com"]
    )
    respond.assert_called_with("Request completed:\ntrue")
    logger.info.assert_called_with("Completed user provisioning request")


@patch("modules.aws.aws.AWS_ADMIN_GROUPS", ["admin-group@email.com"])
@patch("modules.aws.aws.provision_aws_users")
@patch("modules.aws.aws.permissions")
@patch("modules.aws.aws.slack_users")
def test_request_user_provisioning_requestor_not_admin(
    mock_slack_users,
    mock_permissions,
    mock_provision_aws_user,
):
    client = MagicMock()
    body = MagicMock()
    respond = MagicMock()
    logger = MagicMock()
    mock_slack_users.get_user_email_from_body.return_value = "notadmin.name@email.com"
    mock_permissions.is_user_member_of_groups.return_value = False
    mock_provision_aws_user.return_value = True
    aws.request_user_provisioning(
        client, body, respond, ["create", "user.email"], logger
    )
    mock_slack_users.get_user_email_from_body.assert_called_with(client, body)
    mock_permissions.is_user_member_of_groups.assert_called_with(
        "notadmin.name@email.com", ["admin-group@email.com"]
    )
    respond.assert_called_with(
        "This function is restricted to admins only. Please contact #sre-and-tech-ops for assistance."
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
