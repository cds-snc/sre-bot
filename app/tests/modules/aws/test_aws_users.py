from unittest.mock import patch, MagicMock, call
from modules.aws import users


def test_aws_users_command_handles_empty_command():
    client = MagicMock()
    body = MagicMock()
    respond = MagicMock()
    args = ""
    logger = MagicMock()

    users.command_handler(client, body, respond, args, logger)

    respond.assert_called_once_with(
        "Invalid command. Type `/aws users help` for more information."
    )
    logger.info.assert_not_called()


def test_aws_users_command_handles_help_command():
    client = MagicMock()
    body = MagicMock()
    respond = MagicMock()
    args = ["help"]
    logger = MagicMock()

    users.command_handler(client, body, respond, args, logger)

    respond.assert_called_once_with(users.help_text)
    logger.info.assert_not_called()


@patch("modules.aws.users.request_user_provisioning")
def test_aws_users_command_handles_create_command(mock_request_user_provisioning):
    client = MagicMock()
    body = MagicMock()
    respond = MagicMock()
    args = ["create", "@username"]
    logger = MagicMock()

    users.command_handler(client, body, respond, args, logger)

    mock_request_user_provisioning.assert_called_once_with(
        client, body, respond, args, logger
    )


@patch("modules.aws.users.AWS_ADMIN_GROUPS", ["admin-group@email.com"])
@patch("modules.aws.users.identity_center.provision_aws_users")
@patch("modules.aws.users.permissions")
@patch("modules.aws.users.slack_users")
def test_request_user_provisioning(
    mock_slack_users, mock_permissions, mock_provision_aws_user
):
    client = MagicMock()
    body = MagicMock()
    respond = MagicMock()
    logger = MagicMock()
    mock_slack_users.get_user_email_from_body.return_value = "user.name@email.com"
    mock_provision_aws_user.return_value = True
    users.request_user_provisioning(
        client, body, respond, ["create", "user.email"], logger
    )
    mock_slack_users.get_user_email_from_body.assert_called_with(client, body)
    mock_permissions.is_user_member_of_groups.assert_called_with(
        "user.name@email.com", ["admin-group@email.com"]
    )
    respond.assert_called_with("Request completed:\ntrue")
    logger.info.assert_called_with("Completed user provisioning request")


@patch("modules.aws.users.AWS_ADMIN_GROUPS", ["admin-group@email.com"])
@patch("modules.aws.users.identity_center.provision_aws_users")
@patch("modules.aws.users.permissions")
@patch("modules.aws.users.slack_users")
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
    users.request_user_provisioning(
        client, body, respond, ["create", "user.email"], logger
    )
    mock_slack_users.get_user_email_from_body.assert_called_with(client, body)
    mock_permissions.is_user_member_of_groups.assert_called_with(
        "notadmin.name@email.com", ["admin-group@email.com"]
    )
    respond.assert_called_with(
        "This function is restricted to admins only. Please contact #sre-and-tech-ops for assistance."
    )
