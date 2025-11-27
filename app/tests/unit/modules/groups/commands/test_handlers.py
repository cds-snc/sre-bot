"""Unit tests for groups command handlers."""

from unittest.mock import MagicMock
from modules.groups.commands import handlers
from modules.groups.api import schemas
from tests.factories.groups_commands import (
    make_groups_list_context,
    make_group_dict,
    make_member_dict,
)


class TestListHandler:
    """Tests for handle_list command."""

    def test_list_groups_success(
        self, mock_command_context, mock_groups_service, mock_translator
    ):
        """Test successful groups list."""
        # Setup
        mock_groups_service.list_groups.return_value = [
            make_group_dict(
                group_id="group-1",
                name="Group 1",
                members=[make_member_dict(email="test@example.com", role="MANAGER")],
            )
        ]

        # Execute
        handlers.handle_list(mock_command_context)

        # Assert
        assert mock_groups_service.list_groups.called
        assert (
            mock_command_context._responder.send_message.called
        )  # pylint: disable=protected-access
        response_text = mock_command_context._responder.send_message.call_args[0][
            0
        ]  # pylint: disable=protected-access
        assert "Group 1" in response_text

    def test_list_groups_no_results(self, mock_command_context, mock_groups_service):
        """Test list with no groups."""
        mock_groups_service.list_groups.return_value = []

        handlers.handle_list(mock_command_context)

        assert (
            mock_command_context._responder.send_message.called
        )  # pylint: disable=protected-access

    def test_list_groups_with_managed_flag(
        self, mock_command_context, mock_groups_service
    ):
        """Test list with managed_only flag."""
        mock_groups_service.list_groups.return_value = []

        handlers.handle_list(mock_command_context, managed_only=True)

        # Verify service called with correct filter
        call_args = mock_groups_service.list_groups.call_args[0][0]
        assert call_args.filter_by_member_role == ["MANAGER", "OWNER"]

    def test_list_groups_with_provider_filter(
        self, mock_command_context, mock_groups_service
    ):
        """Test list with provider filter."""
        mock_groups_service.list_groups.return_value = []

        handlers.handle_list(mock_command_context, provider="google")

        call_args = mock_groups_service.list_groups.call_args[0][0]
        assert call_args.provider == schemas.ProviderType.GOOGLE

    def test_list_groups_with_role_filter(
        self, mock_command_context, mock_groups_service
    ):
        """Test list with role filter."""
        mock_groups_service.list_groups.return_value = []

        handlers.handle_list(mock_command_context, filter_by_roles=["MANAGER", "OWNER"])

        call_args = mock_groups_service.list_groups.call_args[0][0]
        assert call_args.filter_by_member_role == ["MANAGER", "OWNER"]

    def test_list_groups_no_email_error(self, mock_groups_service):
        """Test error when user email cannot be determined."""
        ctx = make_groups_list_context()
        ctx.metadata["user_email"] = None
        mock_responder = MagicMock()
        ctx._responder = mock_responder  # pylint: disable=protected-access

        handlers.handle_list(ctx)

        assert mock_responder.send_message.called

    def test_list_groups_service_error(self, mock_command_context, mock_groups_service):
        """Test error handling when service fails."""
        mock_groups_service.list_groups.side_effect = Exception("Service error")

        handlers.handle_list(mock_command_context)

        assert (
            mock_command_context._responder.send_message.called
        )  # pylint: disable=protected-access


class TestAddHandler:
    """Tests for handle_add command."""

    def test_add_member_success(self, mock_command_context, mock_groups_service):
        """Test successful member addition."""
        mock_result = MagicMock()
        mock_result.model_dump.return_value = {"success": True, "message": "Added"}
        mock_groups_service.add_member.return_value = mock_result

        handlers.handle_add(
            mock_command_context,
            member_email="new@example.com",
            group_id="group-1",
            provider="google",
            justification="Test justification for adding member",
        )

        assert mock_groups_service.add_member.called
        assert (
            mock_command_context._responder.send_message.called
        )  # pylint: disable=protected-access

    def test_add_member_resolves_slack_handle(
        self, mock_command_context, mock_groups_service, mock_slack_users
    ):
        """Test that Slack handles are resolved to emails."""
        mock_command_context.metadata["slack_client"] = MagicMock()
        mock_result = MagicMock()
        mock_result.model_dump.return_value = {"success": True}
        mock_groups_service.add_member.return_value = mock_result

        handlers.handle_add(
            mock_command_context,
            member_email="@slackuser",
            group_id="group-1",
            provider="google",
            justification="Test justification for adding member",
        )

        assert mock_slack_users.get_user_email_from_handle.called
        call_args = mock_groups_service.add_member.call_args[0][0]
        assert call_args.member_email == "resolved@example.com"

    def test_add_member_handle_resolution_fails(
        self, mock_command_context, mock_slack_users
    ):
        """Test error when Slack handle cannot be resolved."""
        mock_command_context.metadata["slack_client"] = MagicMock()
        mock_slack_users.get_user_email_from_handle.return_value = None

        handlers.handle_add(
            mock_command_context,
            member_email="@invaliduser",
            group_id="group-1",
            provider="google",
            justification="Test",
        )

        assert (
            mock_command_context._responder.send_message.called
        )  # pylint: disable=protected-access

    def test_add_member_no_email_error(self, mock_groups_service):
        """Test error when requestor email cannot be determined."""
        ctx = make_groups_list_context()
        ctx.metadata["user_email"] = None
        mock_responder = MagicMock()
        ctx._responder = mock_responder  # pylint: disable=protected-access

        handlers.handle_add(
            ctx,
            member_email="new@example.com",
            group_id="group-1",
            provider="google",
            justification="Test",
        )

        assert mock_responder.send_message.called

    def test_add_member_service_error(self, mock_command_context, mock_groups_service):
        """Test error handling when service fails."""
        mock_groups_service.add_member.side_effect = Exception("Service error")

        handlers.handle_add(
            mock_command_context,
            member_email="new@example.com",
            group_id="group-1",
            provider="google",
            justification="Test",
        )

        assert (
            mock_command_context._responder.send_message.called
        )  # pylint: disable=protected-access


class TestRemoveHandler:
    """Tests for handle_remove command."""

    def test_remove_member_success(self, mock_command_context, mock_groups_service):
        """Test successful member removal."""
        mock_result = MagicMock()
        mock_result.model_dump.return_value = {"success": True, "message": "Removed"}
        mock_groups_service.remove_member.return_value = mock_result

        handlers.handle_remove(
            mock_command_context,
            member_email="remove@example.com",
            group_id="group-1",
            provider="google",
            justification="Test remove",
        )

        assert mock_groups_service.remove_member.called
        assert (
            mock_command_context._responder.send_message.called
        )  # pylint: disable=protected-access

    def test_remove_member_resolves_slack_handle(
        self, mock_command_context, mock_groups_service, mock_slack_users
    ):
        """Test that Slack handles are resolved to emails for removal."""
        mock_command_context.metadata["slack_client"] = MagicMock()
        mock_result = MagicMock()
        mock_result.model_dump.return_value = {"success": True}
        mock_groups_service.remove_member.return_value = mock_result

        handlers.handle_remove(
            mock_command_context,
            member_email="@slackuser",
            group_id="group-1",
            provider="google",
            justification="Test",
        )

        assert mock_slack_users.get_user_email_from_handle.called


class TestManageHandler:
    """Tests for handle_manage command."""

    def test_manage_lists_groups(self, mock_command_context, mock_groups_service):
        """Test manage command lists all manageable groups."""
        mock_groups_service.list_groups.return_value = [
            make_group_dict(group_id="g1", name="Group 1"),
            make_group_dict(group_id="g2", name="Group 2"),
        ]

        handlers.handle_manage(mock_command_context)

        assert mock_groups_service.list_groups.called
        assert (
            mock_command_context._responder.send_message.called
        )  # pylint: disable=protected-access
        response = mock_command_context._responder.send_message.call_args[0][
            0
        ]  # pylint: disable=protected-access
        assert "Group 1" in response
        assert "Group 2" in response

    def test_manage_no_groups(self, mock_command_context, mock_groups_service):
        """Test manage with no manageable groups."""
        mock_groups_service.list_groups.return_value = []

        handlers.handle_manage(mock_command_context)

        assert (
            mock_command_context._responder.send_message.called
        )  # pylint: disable=protected-access

    def test_manage_with_provider_filter(
        self, mock_command_context, mock_groups_service
    ):
        """Test manage with provider filter."""
        mock_groups_service.list_groups.return_value = []

        handlers.handle_manage(mock_command_context, provider="aws")

        call_args = mock_groups_service.list_groups.call_args[0][0]
        assert call_args.provider == schemas.ProviderType.AWS


class TestHelpHandler:
    """Tests for handle_help command."""

    def test_help_returns_text(self, mock_command_context):
        """Test help command returns help text."""
        handlers.handle_help(mock_command_context)

        assert (
            mock_command_context._responder.send_message.called
        )  # pylint: disable=protected-access
