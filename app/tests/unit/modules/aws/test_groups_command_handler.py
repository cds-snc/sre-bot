"""Unit tests for AWS groups command handler."""

import pytest
from unittest.mock import MagicMock, patch
import datetime

from modules.aws import groups


@pytest.mark.unit
def test_should_show_error_when_groups_command_empty():
    """Test that empty groups command shows error."""
    # Arrange
    client = MagicMock()
    body = MagicMock()
    respond = MagicMock()
    args = ""

    # Act
    groups.command_handler(client, body, respond, args)

    # Assert
    respond.assert_called_once_with(
        "Invalid command. Type `/aws groups help` for more information."
    )


@pytest.mark.unit
def test_should_show_help_text_when_help_command_given():
    """Test that help command returns help text."""
    # Arrange
    client = MagicMock()
    body = MagicMock()
    respond = MagicMock()
    args = ["help"]

    # Act
    groups.command_handler(client, body, respond, args)

    # Assert
    respond.assert_called_once_with(groups.help_text)


@pytest.mark.unit
@patch("modules.aws.groups.request_groups_sync")
def test_should_delegate_to_sync_handler_when_sync_command_given(
    mock_request_groups_sync,
):
    """Test that sync command delegates to handler."""
    # Arrange
    client = MagicMock()
    body = MagicMock()
    respond = MagicMock()
    args = ["sync"]

    # Act
    groups.command_handler(client, body, respond, args)

    # Assert
    mock_request_groups_sync.assert_called_once_with(client, body, respond, args)


@pytest.mark.unit
@patch("modules.aws.groups.request_groups_list")
def test_should_delegate_to_list_handler_when_list_command_given(
    mock_request_groups_list,
):
    """Test that list command delegates to handler."""
    # Arrange
    client = MagicMock()
    body = MagicMock()
    respond = MagicMock()
    args = ["list"]

    # Act
    groups.command_handler(client, body, respond, args)

    # Assert
    mock_request_groups_list.assert_called_once_with(client, body, respond, args)


@pytest.mark.unit
@patch("modules.aws.groups.request_groups_ops")
def test_should_delegate_to_ops_handler_when_ops_command_given(
    mock_request_groups_ops,
):
    """Test that ops command delegates to handler."""
    # Arrange
    client = MagicMock()
    body = MagicMock()
    respond = MagicMock()
    args = ["ops"]

    # Act
    groups.command_handler(client, body, respond, args)

    # Assert
    mock_request_groups_ops.assert_called_once_with(client, body, respond, args)


@pytest.mark.unit
@patch("modules.aws.groups.get_settings")
@patch("modules.aws.groups.identity_center")
@patch("modules.aws.groups.permissions")
@patch("modules.aws.groups.slack_users")
@patch("modules.aws.groups.datetime")
def test_should_synchronize_groups_when_user_has_permission(
    mock_datetime,
    mock_slack_users,
    mock_permissions,
    mock_identity_center,
    mock_get_settings,
):
    """Test successful group synchronization when user has permission."""
    # Arrange
    client = MagicMock()
    body = MagicMock()
    respond = MagicMock()
    args = []

    mock_settings = MagicMock()
    mock_settings.aws_feature.AWS_ADMIN_GROUPS = ["admin@test.com"]
    mock_get_settings.return_value = mock_settings

    mock_slack_users.get_user_email_from_body.return_value = "admin.user@test.com"
    mock_permissions.is_user_member_of_groups.return_value = True
    mock_identity_center.synchronize.return_value = None
    mock_datetime.now.side_effect = [
        datetime.datetime(2021, 1, 1, 0, 0, 0),
        datetime.datetime(2021, 1, 1, 0, 0, 20),
    ]

    # Act
    groups.request_groups_sync(client, body, respond, args)

    # Assert
    mock_slack_users.get_user_email_from_body.assert_called_once_with(client, body)
    mock_permissions.is_user_member_of_groups.assert_called_once()
    mock_identity_center.synchronize.assert_called_once()
    assert respond.call_count == 2


@pytest.mark.unit
@patch("modules.aws.groups.get_settings")
@patch("modules.aws.groups.permissions")
@patch("modules.aws.groups.slack_users")
def test_should_deny_sync_when_user_lacks_permission(
    mock_slack_users, mock_permissions, mock_get_settings
):
    """Test sync denial when user lacks permission."""
    # Arrange
    client = MagicMock()
    body = MagicMock()
    respond = MagicMock()
    args = []

    mock_settings = MagicMock()
    mock_settings.aws_feature.AWS_ADMIN_GROUPS = ["admin@test.com"]
    mock_get_settings.return_value = mock_settings

    mock_slack_users.get_user_email_from_body.return_value = "user@test.com"
    mock_permissions.is_user_member_of_groups.return_value = False

    # Act
    groups.request_groups_sync(client, body, respond, args)

    # Assert
    mock_slack_users.get_user_email_from_body.assert_called_once_with(client, body)
    mock_permissions.is_user_member_of_groups.assert_called_once()
    respond.assert_called_once_with("You do not have permission to sync groups.")


@pytest.mark.unit
@patch("modules.aws.groups.get_settings")
@patch("modules.aws.groups.provisioning_groups")
@patch("modules.aws.groups.permissions")
@patch("modules.aws.groups.slack_users")
def test_should_list_groups_when_user_has_permission(
    mock_slack_users, mock_permissions, mock_provisioning_groups, mock_get_settings
):
    """Test successful group listing when user has permission."""
    # Arrange
    client = MagicMock()
    body = MagicMock()
    respond = MagicMock()
    args = []

    mock_settings = MagicMock()
    mock_settings.aws_feature.AWS_ADMIN_GROUPS = ["admin@test.com"]
    mock_get_settings.return_value = mock_settings

    mock_slack_users.get_user_email_from_body.return_value = "admin.user@test.com"
    mock_permissions.is_user_member_of_groups.return_value = True
    mock_provisioning_groups.get_groups_from_integration.return_value = [
        {
            "DisplayName": "Group1",
            "GroupMemberships": [{"MemberId": "user1"}, {"MemberId": "user2"}],
        },
        {
            "DisplayName": "Group2",
            "GroupMemberships": [{"MemberId": "user3"}],
        },
    ]

    # Act
    groups.request_groups_list(client, body, respond, args)

    # Assert
    mock_slack_users.get_user_email_from_body.assert_called_once_with(client, body)
    mock_permissions.is_user_member_of_groups.assert_called_once()
    assert respond.call_count == 2
    assert "Group1" in respond.call_args_list[1][0][0]
    assert "Group2" in respond.call_args_list[1][0][0]


@pytest.mark.unit
@patch("modules.aws.groups.get_settings")
@patch("modules.aws.groups.permissions")
@patch("modules.aws.groups.slack_users")
def test_should_deny_list_when_user_lacks_permission(
    mock_slack_users, mock_permissions, mock_get_settings
):
    """Test list denial when user lacks permission."""
    # Arrange
    client = MagicMock()
    body = MagicMock()
    respond = MagicMock()
    args = []

    mock_settings = MagicMock()
    mock_settings.aws_feature.AWS_ADMIN_GROUPS = ["admin@test.com"]
    mock_get_settings.return_value = mock_settings

    mock_slack_users.get_user_email_from_body.return_value = "user@test.com"
    mock_permissions.is_user_member_of_groups.return_value = False

    # Act
    groups.request_groups_list(client, body, respond, args)

    # Assert
    mock_slack_users.get_user_email_from_body.assert_called_once_with(client, body)
    mock_permissions.is_user_member_of_groups.assert_called_once()
    respond.assert_called_once_with("You do not have permission to list groups.")
