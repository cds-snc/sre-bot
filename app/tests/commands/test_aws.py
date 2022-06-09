from commands import aws

from unittest.mock import MagicMock, patch


def test_aws_command_handles_empty_command():
    ack = MagicMock()
    respond = MagicMock()

    aws.aws_command(ack, {"text": ""}, MagicMock(), respond, MagicMock(), MagicMock())
    ack.assert_called
    assert respond.called


def test_aws_command_handles_help_command():
    ack = MagicMock()
    respond = MagicMock()

    aws.aws_command(
        ack, {"text": "help"}, MagicMock(), respond, MagicMock(), MagicMock()
    )
    ack.assert_called
    assert respond.called_with(aws.help_text)


@patch("commands.aws.access_view_handler")
def test_aws_command_handles_access_command(access_view_handler):
    ack = MagicMock()
    respond = MagicMock()
    client = MagicMock()
    body = MagicMock()

    aws.aws_command(ack, {"text": "access"}, MagicMock(), respond, client, body)
    ack.assert_called
    assert access_view_handler.called_with(client, body)


def test_aws_command_handles_unknown_command():
    ack = MagicMock()
    respond = MagicMock()

    aws.aws_command(
        ack, {"text": "unknown"}, MagicMock(), respond, MagicMock(), MagicMock()
    )
    ack.assert_called
    respond.assert_called_with(
        "Unknown command: unknown. Type `/aws help` to see a list of commands."
    )


def test_access_view_handler_returns_errors_with_rational_over_2000_characters():
    ack = MagicMock()
    body = build_body(rationale="a" * 2001)

    aws.access_view_handler(ack, body, MagicMock(), MagicMock())
    ack.assert_called_with(
        response_action="errors",
        errors={"rationale": "Please use less than 2000 characters"},
    )


@patch("commands.aws.log_ops_message")
@patch("commands.aws.aws_sso.get_user_id")
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
        text="<@user_id> (email) is not registered with AWS SSO. Please contact your administrator.",
    )


@patch("commands.aws.log_ops_message")
@patch("commands.aws.aws_sso.get_user_id")
@patch("commands.aws.aws_access_requests.already_has_access")
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


@patch("commands.aws.log_ops_message")
@patch("commands.aws.aws_sso.get_user_id")
@patch("commands.aws.aws_access_requests.already_has_access")
@patch("commands.aws.aws_access_requests.create_aws_access_request")
@patch("commands.aws.aws_sso.add_permissions_for_user")
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
        text="Provisioning access_type access request for account (account_id). This can take a minute or two. Visit <https://cds-snc.awsapps.com/start#/|https://cds-snc.awsapps.com/start#/> to gain access.",
    )


@patch("commands.aws.log_ops_message")
@patch("commands.aws.aws_sso.get_user_id")
@patch("commands.aws.aws_access_requests.already_has_access")
@patch("commands.aws.aws_access_requests.create_aws_access_request")
@patch("commands.aws.aws_sso.add_permissions_for_user")
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
        text="Failed to provision access_type access request for account (account_id). Please drop a note in the <#sre-and-tech-ops> channel.",
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
