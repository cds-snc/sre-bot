from unittest.mock import patch, MagicMock, call, ANY
import datetime
from modules.aws import groups


def test_aws_groups_command_handles_empty_command():
    client = MagicMock()
    body = MagicMock()
    respond = MagicMock()
    args = ""
    logger = MagicMock()

    groups.command_handler(client, body, respond, args, logger)

    respond.assert_called_once_with(
        "Invalid command. Type `/aws groups help` for more information."
    )
    logger.info.assert_not_called()


def test_aws_groups_command_handles_help_command():
    client = MagicMock()
    body = MagicMock()
    respond = MagicMock()
    args = ["help"]
    logger = MagicMock()

    groups.command_handler(client, body, respond, args, logger)

    respond.assert_called_once_with(groups.help_text)
    logger.info.assert_not_called()


@patch("modules.aws.groups.request_groups_sync")
def test_aws_groups_command_handles_sync_command(mock_request_groups_sync):
    client = MagicMock()
    body = MagicMock()
    respond = MagicMock()
    args = ["sync"]
    logger = MagicMock()

    groups.command_handler(client, body, respond, args, logger)

    mock_request_groups_sync.assert_called_once_with(
        client, body, respond, args, logger
    )
    logger.info.assert_not_called()


@patch("modules.aws.groups.request_groups_list")
def test_aws_groups_command_handles_list_command(mock_request_groups_list):
    client = MagicMock()
    body = MagicMock()
    respond = MagicMock()
    args = ["list"]
    logger = MagicMock()

    groups.command_handler(client, body, respond, args, logger)

    mock_request_groups_list.assert_called_once_with(
        client, body, respond, args, logger
    )
    logger.info.assert_not_called()


@patch("modules.aws.groups.request_groups_ops")
def test_aws_groups_command_handles_ops_command(mock_request_groups_ops):
    client = MagicMock()
    body = MagicMock()
    respond = MagicMock()
    args = ["ops"]
    logger = MagicMock()

    groups.command_handler(client, body, respond, args, logger)

    mock_request_groups_ops.assert_called_once_with(client, body, respond, args, logger)
    logger.info.assert_not_called()


@patch("modules.aws.groups.datetime")
@patch("modules.aws.groups.slack_users")
@patch("modules.aws.groups.permissions")
@patch("modules.aws.groups.identity_center")
def test_request_groups_sync_synchronizes_groups(
    mock_identity_center, mock_permissions, mock_slack_users, mock_datetime
):
    client = MagicMock()
    body = MagicMock()
    respond = MagicMock()
    args = []
    logger = MagicMock()

    mock_slack_users.get_user_email_from_body.return_value = "admin.user@test.com"
    mock_permissions.is_user_member_of_groups.return_value = True
    mock_identity_center.synchronize.return_value = None
    mock_datetime.now.side_effect = [
        datetime.datetime(2021, 1, 1, 0, 0, 0),
        datetime.datetime(2021, 1, 1, 0, 0, 20),
    ]

    groups.request_groups_sync(client, body, respond, args, logger)

    mock_slack_users.get_user_email_from_body.assert_called_once_with(client, body)
    mock_permissions.is_user_member_of_groups.assert_called_once_with(
        "admin.user@test.com", groups.AWS_ADMIN_GROUPS
    )
    logger.info.assert_has_calls(
        [
            call(
                "aws_groups_sync_request_received",
                requestor_email="admin.user@test.com",
            ),
        ]
    )

    mock_identity_center.synchronize.assert_called_once_with(
        enable_users_sync=False,
        enable_user_create=False,
        enable_membership_create=True,
        enable_membership_delete=True,
        pre_processing_filters=[],
    )
    respond.assert_has_calls(
        [
            call("AWS Groups Memberships Synchronization Initiated."),
            call(
                "AWS Groups Memberships Synchronization Completed in 20.000000 seconds."
            ),
        ]
    )


@patch("modules.aws.groups.datetime")
@patch("modules.aws.groups.slack_users")
@patch(
    "modules.aws.groups.permissions",
)
@patch("modules.aws.groups.identity_center")
def test_request_groups_sync_synchronizes_groups_with_args(
    mock_identity_center, mock_permissions, mock_slack_users, mock_datetime
):
    client = MagicMock()
    body = MagicMock()
    respond = MagicMock()
    args = ["group1", "group2"]
    logger = MagicMock()
    mock_slack_users.get_user_email_from_body.return_value = "admin.user@test.com"
    mock_permissions.is_user_member_of_groups.return_value = True
    mock_identity_center.synchronize.return_value = None
    mock_datetime.now.side_effect = [
        datetime.datetime(2021, 1, 1, 0, 0, 0),
        datetime.datetime(2021, 1, 1, 0, 0, 20),
    ]

    groups.request_groups_sync(client, body, respond, args, logger)

    mock_slack_users.get_user_email_from_body.assert_called_once_with(client, body)
    mock_permissions.is_user_member_of_groups.assert_called_once_with(
        "admin.user@test.com", groups.AWS_ADMIN_GROUPS
    )
    logger.info.assert_has_calls(
        [
            call(
                "aws_groups_sync_request_received",
                requestor_email="admin.user@test.com",
            ),
        ]
    )
    mock_identity_center.synchronize.assert_called_once_with(
        enable_users_sync=False,
        enable_user_create=False,
        enable_membership_create=True,
        enable_membership_delete=True,
        pre_processing_filters=ANY,
    )
    respond.assert_has_calls(
        [
            call("AWS Groups Memberships Synchronization Initiated."),
            call(
                "AWS Groups Memberships Synchronization Completed in 20.000000 seconds."
            ),
        ]
    )


@patch.object(groups, "AWS_ADMIN_GROUPS", ["admin@test.com"])
@patch("modules.aws.groups.slack_users")
@patch("modules.aws.groups.permissions")
@patch("modules.aws.groups.identity_center")
def test_request_groups_sync_handles_user_without_permission(
    mock_identity_center, mock_permissions, mock_slack_users
):
    client = MagicMock()
    body = MagicMock()
    respond = MagicMock()
    args = []
    logger = MagicMock()

    mock_slack_users.get_user_email_from_body.return_value = "not.admin@test.com"
    mock_permissions.is_user_member_of_groups.return_value = False

    groups.request_groups_sync(client, body, respond, args, logger)

    mock_slack_users.get_user_email_from_body.assert_called_once_with(client, body)
    mock_permissions.is_user_member_of_groups.assert_called_once_with(
        "not.admin@test.com", groups.AWS_ADMIN_GROUPS
    )
    logger.warning.assert_called_once_with(
        "aws_groups_sync_request_denied",
        requestor_email="not.admin@test.com",
        aws_admin_groups=["admin@test.com"],
        error="User does not have permission to sync groups.",
    )
    respond.assert_called_once_with("You do not have permission to sync groups.")

    mock_identity_center.synchronize.assert_not_called()


@patch("modules.aws.groups.provisioning_groups")
@patch("modules.aws.groups.slack_users")
@patch("modules.aws.groups.permissions")
def test_request_groups_list_handles_user_with_permission(
    mock_permissions, mock_slack_users, mock_provisioning_groups
):
    client = MagicMock()
    body = MagicMock()
    respond = MagicMock()
    args = []
    logger = MagicMock()

    mock_slack_users.get_user_email_from_body.return_value = "authorized.user@test.com"
    mock_permissions.is_user_member_of_groups.return_value = True
    mock_provisioning_groups.get_groups_from_integration.return_value = [
        {
            "DisplayName": "Group 1",
            "GroupMemberships": [{"MemberId": {"UserName": "user1"}}],
        },
        {"DisplayName": "Group 2"},
    ]

    groups.request_groups_list(client, body, respond, args, logger)

    mock_slack_users.get_user_email_from_body.assert_called_once_with(client, body)
    mock_permissions.is_user_member_of_groups.assert_called_once_with(
        "authorized.user@test.com", groups.AWS_ADMIN_GROUPS
    )

    respond_calls = [
        call("AWS Groups List request received."),
        call("Groups found:\n • Group 1 (1 members)\n • Group 2 (0 members)\n"),
    ]
    respond.assert_has_calls(respond_calls)
    logger.info.assert_called()
    logger.warning.assert_not_called()
    mock_provisioning_groups.get_groups_from_integration.assert_called_once_with(
        "aws_identity_center"
    )


@patch("modules.aws.groups.slack_users")
@patch("modules.aws.groups.permissions")
def test_request_groups_list_handles_user_without_permission(
    mock_permissions, mock_slack_users
):
    client = MagicMock()
    body = MagicMock()
    respond = MagicMock()
    args = []
    logger = MagicMock()

    mock_slack_users.get_user_email_from_body.return_value = (
        "unauthorized.user@test.com"
    )
    mock_permissions.is_user_member_of_groups.return_value = False

    groups.request_groups_list(client, body, respond, args, logger)

    mock_slack_users.get_user_email_from_body.assert_called_once_with(client, body)
    mock_permissions.is_user_member_of_groups.assert_called_once_with(
        "unauthorized.user@test.com", groups.AWS_ADMIN_GROUPS
    )
    respond.assert_called_once_with("You do not have permission to list groups.")

    logger.info.assert_called_once()
    logger.warning.assert_called_once()


@patch("modules.aws.groups.ops_group_assignment")
@patch("modules.aws.groups.slack_users")
@patch("modules.aws.groups.permissions")
def test_request_groups_ops_handles_user_with_permission(
    mock_permissions, mock_slack_users, mock_ops_group_assignment
):
    client = MagicMock()
    body = MagicMock()
    respond = MagicMock()
    args = []
    logger = MagicMock()

    mock_slack_users.get_user_email_from_body.return_value = "authorized.user@test.com"
    mock_permissions.is_user_member_of_groups.return_value = True
    mock_ops_group_assignment.execute.return_value = {
        "status": "success",
        "message": "Ops group assigned to account 123456789012.",
    }
    groups.request_groups_ops(client, body, respond, args, logger)
    mock_slack_users.get_user_email_from_body.assert_called_once_with(client, body)
    mock_permissions.is_user_member_of_groups.assert_called_once_with(
        "authorized.user@test.com", groups.AWS_ADMIN_GROUPS
    )
    respond_calls = [
        call("AWS Ops Group Assignment request received."),
        call("✅ *Success*: Ops group assigned to account 123456789012."),
    ]
    respond.assert_has_calls(respond_calls)
    logger.info.assert_called()
    logger.warning.assert_not_called()
    mock_ops_group_assignment.execute.assert_called_once()


@patch("modules.aws.groups.ops_group_assignment")
@patch("modules.aws.groups.slack_users")
@patch("modules.aws.groups.permissions")
def test_request_groups_ops_handles_disabled_feature(
    mock_permissions, mock_slack_users, mock_ops_group_assignment
):
    client = MagicMock()
    body = MagicMock()
    respond = MagicMock()
    args = []
    logger = MagicMock()

    mock_slack_users.get_user_email_from_body.return_value = "authorized.user@test.com"
    mock_permissions.is_user_member_of_groups.return_value = True
    mock_ops_group_assignment.execute.return_value = None
    groups.request_groups_ops(client, body, respond, args, logger)
    mock_slack_users.get_user_email_from_body.assert_called_once_with(client, body)
    mock_permissions.is_user_member_of_groups.assert_called_once_with(
        "authorized.user@test.com", groups.AWS_ADMIN_GROUPS
    )
    mock_ops_group_assignment.execute.assert_called_once()
    respond_calls = [
        call("AWS Ops Group Assignment request received."),
        call("⚠️ AWS Ops Group Assignment feature is disabled."),
    ]
    respond.assert_has_calls(respond_calls)
    logger.info.assert_called()
    logger.warning.assert_not_called()


@patch("modules.aws.groups.ops_group_assignment")
@patch("modules.aws.groups.slack_users")
@patch("modules.aws.groups.permissions")
def test_request_groups_ops_handles_status_messages(
    mock_permissions, mock_slack_users, mock_ops_group_assignment
):
    client = MagicMock()
    body = MagicMock()
    respond = MagicMock()
    args = []
    logger = MagicMock()

    statuses = [
        (
            "success",
            "Operation completed successfully.",
            "✅ *Success*: Operation completed successfully.",
        ),
        (
            "failed",
            "Operation failed due to an error.",
            "❌ *Error*: Operation failed due to an error.",
        ),
        ("ok", "No changes were necessary.", "ℹ️ *Info*: No changes were necessary."),
        ("unknown", "This is an unknown status.", "⚠️ This is an unknown status."),
    ]

    for status, message, expected_response in statuses:
        mock_slack_users.get_user_email_from_body.return_value = (
            "authorized.user@test.com"
        )
        mock_permissions.is_user_member_of_groups.return_value = True
        mock_ops_group_assignment.execute.return_value = {
            "status": status,
            "message": message,
        }
        respond.reset_mock()
        groups.request_groups_ops(client, body, respond, args, logger)
        respond_calls = [
            call("AWS Ops Group Assignment request received."),
            call(expected_response),
        ]
        respond.assert_has_calls(respond_calls)
        respond.reset_mock()


@patch("modules.aws.groups.ops_group_assignment")
@patch("modules.aws.groups.slack_users")
@patch("modules.aws.groups.permissions")
def test_request_groups_ops_handles_user_without_permission(
    mock_permissions, mock_slack_users, mock_ops_group_assignment
):
    client = MagicMock()
    body = MagicMock()
    respond = MagicMock()
    args = []
    logger = MagicMock()

    mock_slack_users.get_user_email_from_body.return_value = (
        "unauthorized.user@test.com"
    )
    mock_permissions.is_user_member_of_groups.return_value = False
    groups.request_groups_ops(client, body, respond, args, logger)
    mock_slack_users.get_user_email_from_body.assert_called_once_with(client, body)
    mock_permissions.is_user_member_of_groups.assert_called_once_with(
        "unauthorized.user@test.com", groups.AWS_ADMIN_GROUPS
    )
    respond.assert_called_once_with("You do not have permission to assign Ops group.")
    logger.info.assert_called_once()
    logger.warning.assert_called_once()
    mock_ops_group_assignment.execute.assert_not_called()
