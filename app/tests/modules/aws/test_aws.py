from modules import aws

from unittest.mock import ANY, MagicMock, patch


def test_aws_command_handles_empty_command():
    ack = MagicMock()
    respond = MagicMock()

    aws.aws_command(ack, {"text": ""}, MagicMock(), respond, MagicMock(), MagicMock())
    ack.assert_called
    respond.assert_called


def test_aws_command_handles_help_command():
    ack = MagicMock()
    respond = MagicMock()

    aws.aws_command(
        ack, {"text": "help"}, MagicMock(), respond, MagicMock(), MagicMock()
    )
    ack.assert_called
    respond.assert_called_with(aws.help_text)


@patch("modules.aws.aws.request_access_modal")
def test_aws_command_handles_access_command(request_access_modal):
    ack = MagicMock()
    respond = MagicMock()
    client = MagicMock()
    body = MagicMock()
    aws.aws_command(ack, {"text": "access"}, MagicMock(), respond, client, body)
    ack.assert_called
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
    ack.assert_called
    command_handler.assert_called_with(client, body, respond, ["sync"], logger)


@patch("modules.aws.aws.slack_commands.parse_command")
@patch("modules.aws.aws.request_health_modal")
def test_aws_command_handles_health_command(
    request_health_modal: MagicMock, mock_parse_command: MagicMock
):
    ack = MagicMock()
    respond = MagicMock()
    client = MagicMock()
    body = MagicMock()
    mock_parse_command.return_value = ["health"]
    aws.aws_command(ack, {"text": "health"}, MagicMock(), respond, client, body)
    ack.assert_called
    request_health_modal.assert_called_with(client, body)


@patch("modules.aws.aws.slack_commands.parse_command")
def test_aws_command_handles_unknown_command(mock_parse_command):
    ack = MagicMock()
    respond = MagicMock()
    mock_parse_command.return_value = ["unknown"]
    aws.aws_command(
        ack, {"text": "unknown"}, MagicMock(), respond, MagicMock(), MagicMock()
    )
    ack.assert_called
    respond.assert_called_with(
        "Unknown command: `unknown`. Type `/aws help` to see a list of commands.\nCommande inconnue: `unknown`. Tapez `/aws help` pour voir une liste des commandes."
    )


def test_access_view_handler_returns_errors_with_rational_over_2000_characters():
    ack = MagicMock()
    body = build_body(rationale="a" * 2001)

    aws.access_view_handler(ack, body, MagicMock(), MagicMock())
    ack.assert_called_with(
        response_action="errors",
        errors={"rationale": "Please use less than 2000 characters"},
    )


@patch("modules.aws.aws.log_ops_message")
@patch("modules.aws.aws.aws_sso.get_user_id")
def test_access_view_handler_with_unknown_sso_user(
    get_user_id_mock, log_ops_message_mock
):
    ack = MagicMock()
    body = build_body()
    logger = MagicMock()
    client = MagicMock()

    client.users_info.return_value = {
        "user": {"id": "user_id", "profile": {"email": "email"}}
    }

    get_user_id_mock.return_value = None

    aws.access_view_handler(ack, body, logger, client)
    ack.assert_called
    client.users_info.assert_called_with(user="user_id")
    logger.info.assert_called_with(
        "<@user_id> (email) requested access to account (account_id) with access_type priviliges.\n\nRationale: rationale"
    )
    log_ops_message_mock.assert_called_with(
        client,
        "<@user_id> (email) requested access to account (account_id) with access_type priviliges.\n\nRationale: rationale",
    )
    client.chat_postEphemeral.assert_called_with(
        channel="user_id",
        user="user_id",
        text="<@user_id> (email) is not registered with AWS SSO. Please contact your administrator.\n<@user_id> (email) n'est pas enregistré avec AWS SSO. SVP contactez votre administrateur.",
    )


@patch("modules.aws.aws.log_ops_message")
@patch("modules.aws.aws.aws_sso.get_user_id")
@patch("modules.aws.aws.aws_access_requests.already_has_access")
def test_access_view_handler_with_existing_access(
    already_has_access_mock, get_user_id_mock, log_ops_message_mock
):
    ack = MagicMock()
    body = build_body()
    logger = MagicMock()
    client = MagicMock()

    client.users_info.return_value = {
        "user": {"id": "user_id", "profile": {"email": "email"}}
    }

    get_user_id_mock.return_value = "aws_user_id"
    already_has_access_mock.return_value = 10

    aws.access_view_handler(ack, body, logger, client)
    ack.assert_called
    client.users_info.assert_called_with(user="user_id")
    logger.info.assert_called_with(
        "<@user_id> (email) requested access to account (account_id) with access_type priviliges.\n\nRationale: rationale"
    )
    log_ops_message_mock.assert_called_with(
        client,
        "<@user_id> (email) requested access to account (account_id) with access_type priviliges.\n\nRationale: rationale",
    )
    client.chat_postEphemeral.assert_called_with(
        channel="user_id",
        user="user_id",
        text="You already have access to account (account_id) with access type access_type. Your access will expire in 10 minutes.",
    )


@patch("modules.aws.aws.log_ops_message")
@patch("modules.aws.aws.aws_sso.get_user_id")
@patch("modules.aws.aws.aws_access_requests.already_has_access")
@patch("modules.aws.aws.aws_access_requests.create_aws_access_request")
@patch("modules.aws.aws.aws_sso.add_permissions_for_user")
def test_access_view_handler_successful_access_request(
    add_permissions_for_user_mock,
    create_aws_access_request_mock,
    already_has_access_mock,
    get_user_id_mock,
    log_ops_message_mock,
):
    ack = MagicMock()
    body = build_body()
    logger = MagicMock()
    client = MagicMock()

    client.users_info.return_value = {
        "user": {"id": "user_id", "profile": {"email": "email"}}
    }

    get_user_id_mock.return_value = "aws_user_id"
    already_has_access_mock.return_value = False
    create_aws_access_request_mock.return_value = True
    add_permissions_for_user_mock.return_value = True

    aws.access_view_handler(ack, body, logger, client)
    ack.assert_called
    client.users_info.assert_called_with(user="user_id")
    logger.info.assert_called_with(
        "<@user_id> (email) requested access to account (account_id) with access_type priviliges.\n\nRationale: rationale"
    )
    log_ops_message_mock.assert_called_with(
        client,
        "<@user_id> (email) requested access to account (account_id) with access_type priviliges.\n\nRationale: rationale",
    )
    client.chat_postEphemeral.assert_called_with(
        channel="user_id",
        user="user_id",
        text="Provisioning access_type access request for account (account_id). This can take a minute or two. Visit <https://cds-snc.awsapps.com/start#/|https://cds-snc.awsapps.com/start#/> to gain access.\nTraitement de la requête d'accès access_type pour le compte account (account_id) en cours. Cela peut prendre quelques minutes. Visitez <https://cds-snc.awsapps.com/start#/|https://cds-snc.awsapps.com/start#/> pour y accéder",
    )


@patch("modules.aws.aws.log_ops_message")
@patch("modules.aws.aws.aws_sso.get_user_id")
@patch("modules.aws.aws.aws_access_requests.already_has_access")
@patch("modules.aws.aws.aws_access_requests.create_aws_access_request")
@patch("modules.aws.aws.aws_sso.add_permissions_for_user")
def test_access_view_handler_failed_access_request(
    add_permissions_for_user_mock,
    create_aws_access_request_mock,
    already_has_access_mock,
    get_user_id_mock,
    log_ops_message_mock,
):
    ack = MagicMock()
    body = build_body()
    logger = MagicMock()
    client = MagicMock()

    client.users_info.return_value = {
        "user": {"id": "user_id", "profile": {"email": "email"}}
    }

    get_user_id_mock.return_value = "aws_user_id"
    already_has_access_mock.return_value = False
    create_aws_access_request_mock.return_value = True
    add_permissions_for_user_mock.return_value = False

    aws.access_view_handler(ack, body, logger, client)
    ack.assert_called
    client.users_info.assert_called_with(user="user_id")
    logger.info.assert_called_with(
        "<@user_id> (email) requested access to account (account_id) with access_type priviliges.\n\nRationale: rationale"
    )
    log_ops_message_mock.assert_called_with(
        client,
        "<@user_id> (email) requested access to account (account_id) with access_type priviliges.\n\nRationale: rationale",
    )
    client.chat_postEphemeral.assert_called_with(
        channel="user_id",
        user="user_id",
        text="Failed to provision access_type access request for account (account_id). Please drop a note in the <#sre-and-tech-ops> channel.\nLa requête d'accès access_type pour account (account_id) a échouée. Envoyez une note sur le canal <#sre-and-tech-ops>",
    )


@patch("modules.aws.aws.aws_account_health.get_account_health")
def test_health_view_handler(get_account_health_mock):
    ack = MagicMock()
    body = {
        "trigger_id": "trigger_id",
        "view": {
            "state": {
                "values": {
                    "account": {
                        "account": {
                            "selected_option": {
                                "value": "account_id",
                                "text": {"text": "account_name"},
                            }
                        }
                    }
                }
            }
        },
    }
    client = MagicMock()

    aws.health_view_handler(ack, body, MagicMock(), client)
    ack.assert_called
    client.views_open.assert_called_with(
        trigger_id="trigger_id",
        view=ANY,
    )


@patch("modules.aws.aws.aws_sso.get_accounts")
def test_request_access_modal(get_accounts_mock):
    get_accounts_mock.return_value = {"id": "name"}

    client = MagicMock()
    body = {"trigger_id": "trigger_id", "view": {"state": {"values": {}}}}

    aws.request_access_modal(client, body)
    client.views_open.assert_called_with(
        trigger_id="trigger_id",
        view=ANY,
    )


@patch("modules.aws.aws.aws_account_health.get_accounts")
def test_request_health_modal(get_accounts_mocks):
    client = MagicMock()
    body = {"trigger_id": "trigger_id", "view": {"state": {"values": {}}}}

    get_accounts_mocks.return_value = {"id": "name"}

    aws.request_health_modal(client, body)
    client.views_open.assert_called_with(
        trigger_id="trigger_id",
        view=ANY,
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


def build_body(
    rationale="rationale",
    account="account",
    account_id="account_id",
    access_type="access_type",
):
    return {
        "view": {
            "state": {
                "values": {
                    "rationale": {"rationale": {"value": rationale}},
                    "account": {
                        "account": {
                            "selected_option": {
                                "text": {"text": account},
                                "value": account_id,
                            }
                        }
                    },
                    "access_type": {
                        "access_type": {"selected_option": {"value": access_type}}
                    },
                }
            }
        },
        "user": {"id": "user_id"},
    }


@patch("modules.aws.aws_access_requests.create_aws_access_request")
@patch("modules.aws.aws_sso.get_user_id")
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
@patch("modules.aws.aws_sso.get_user_id")
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
