"""Unit tests for AWS users command handler."""

import pytest
from unittest.mock import MagicMock, patch

from modules.aws import users


@pytest.mark.unit
def test_should_show_help_text_when_help_command_given():
    """Test that help command returns help text."""
    # Arrange
    client = MagicMock()
    body = MagicMock()
    respond = MagicMock()
    args = ["help"]

    # Act
    users.command_handler(client, body, respond, args)

    # Assert
    respond.assert_called_once_with(users.help_text)


@pytest.mark.unit
def test_should_show_error_for_invalid_users_command():
    """Test error message for invalid users command."""
    # Arrange
    client = MagicMock()
    body = MagicMock()
    respond = MagicMock()
    args = ["invalid"]

    # Act
    users.command_handler(client, body, respond, args)

    # Assert
    respond.assert_called_once()
    assert "Invalid command" in respond.call_args[0][0]


@pytest.mark.unit
@patch("modules.aws.users.request_user_provisioning")
def test_should_delegate_to_provisioning_handler_when_create_command_given(
    mock_provisioning,
):
    """Test that create command delegates to provisioning handler."""
    # Arrange
    client = MagicMock()
    body = MagicMock()
    respond = MagicMock()
    args = ["create", "user@example.com"]

    # Act
    users.command_handler(client, body, respond, args)

    # Assert
    mock_provisioning.assert_called_once_with(
        client, body, respond, ["create", "user@example.com"]
    )


@pytest.mark.unit
@patch("modules.aws.users.request_user_provisioning")
def test_should_delegate_to_provisioning_handler_when_delete_command_given(
    mock_provisioning,
):
    """Test that delete command delegates to provisioning handler."""
    # Arrange
    client = MagicMock()
    body = MagicMock()
    respond = MagicMock()
    args = ["delete", "user@example.com"]

    # Act
    users.command_handler(client, body, respond, args)

    # Assert
    mock_provisioning.assert_called_once_with(
        client, body, respond, ["delete", "user@example.com"]
    )


@pytest.mark.unit
@patch("modules.aws.users.get_settings")
@patch("modules.aws.users.identity_center")
@patch("modules.aws.users.permissions")
@patch("modules.aws.users.slack_users")
def test_should_provision_user_when_user_has_permission(
    mock_slack_users, mock_permissions, mock_identity_center, mock_get_settings
):
    """Test successful user provisioning when user has permission."""
    # Arrange
    client = MagicMock()
    body = MagicMock()
    respond = MagicMock()
    args = ["create", "newuser@example.com"]

    mock_settings = MagicMock()
    mock_settings.aws_feature.AWS_ADMIN_GROUPS = ["admin@test.com"]
    mock_get_settings.return_value = mock_settings

    mock_slack_users.get_user_email_from_body.return_value = "admin@test.com"
    mock_permissions.is_user_member_of_groups.return_value = True
    mock_identity_center.provision_aws_users.return_value = {"status": "success"}

    # Act
    users.request_user_provisioning(client, body, respond, args)

    # Assert
    mock_slack_users.get_user_email_from_body.assert_called_once_with(client, body)
    mock_permissions.is_user_member_of_groups.assert_called_once()
    mock_identity_center.provision_aws_users.assert_called_once_with(
        "create", ["newuser@example.com"]
    )
    respond.assert_called_once()
    assert "success" in respond.call_args[0][0]


@pytest.mark.unit
@patch("modules.aws.users.get_settings")
@patch("modules.aws.users.permissions")
@patch("modules.aws.users.slack_users")
def test_should_deny_provisioning_when_user_lacks_permission(
    mock_slack_users, mock_permissions, mock_get_settings
):
    """Test provisioning denial when user lacks permission."""
    # Arrange
    client = MagicMock()
    body = MagicMock()
    respond = MagicMock()
    args = ["create", "newuser@example.com"]

    mock_settings = MagicMock()
    mock_settings.aws_feature.AWS_ADMIN_GROUPS = ["admin@test.com"]
    mock_get_settings.return_value = mock_settings

    mock_slack_users.get_user_email_from_body.return_value = "user@test.com"
    mock_permissions.is_user_member_of_groups.return_value = False

    # Act
    users.request_user_provisioning(client, body, respond, args)

    # Assert
    mock_slack_users.get_user_email_from_body.assert_called_once_with(client, body)
    mock_permissions.is_user_member_of_groups.assert_called_once()
    respond.assert_called_once()
    assert "restricted" in respond.call_args[0][0].lower()
