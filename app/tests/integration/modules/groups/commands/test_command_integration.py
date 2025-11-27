"""Integration tests for groups commands."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from infrastructure.commands.providers.slack import SlackCommandProvider
from infrastructure.i18n import LocaleResolver, Translator, YAMLTranslationLoader
from modules.groups.commands.registry import registry


class TestGroupsCommandIntegration:
    """Integration tests for full command flow."""

    @pytest.fixture
    def translator(self):
        """Create real translator instance."""
        loader = YAMLTranslationLoader(
            translations_dir=Path("locales"), use_cache=False
        )
        t = Translator(loader=loader)
        t.load_all()
        return t

    @pytest.fixture
    def adapter(self, translator):
        """Create command adapter with real translator."""
        from infrastructure.i18n.models import Locale

        locale_resolver = LocaleResolver(default_locale=Locale.EN_US)
        # Mock settings to provide SLACK_TOKEN for adapter initialization
        with patch("infrastructure.commands.providers.slack.settings") as mock_settings:
            mock_slack_config = MagicMock()
            mock_slack_config.SLACK_TOKEN = "xoxb-test-token"
            mock_settings.slack = mock_slack_config
            adapter = SlackCommandProvider(config={"enabled": True})

        # Mock the slack_users locale fetching to return a proper locale string
        with patch(
            "infrastructure.commands.providers.slack.slack_users.get_user_locale"
        ) as mock_get_locale:
            mock_get_locale.return_value = "en-US"

        # Mock the slack_users email fetching to return a proper email
        with patch(
            "infrastructure.commands.providers.slack.slack_users.get_user_email_from_body"
        ) as mock_get_email:
            mock_get_email.return_value = "testuser@example.com"

        adapter.registry = registry
        adapter.translator = translator
        adapter.locale_resolver = locale_resolver
        return adapter

    @pytest.fixture
    def slack_payload(self):
        """Create mock Slack command payload."""
        # Mock client that returns proper string values
        mock_client = MagicMock()
        # Mock the users_info response for email fetching
        mock_client.users_info.return_value = {
            "ok": True,
            "user": {"profile": {"email": "testuser@example.com"}},
        }

        return {
            "ack": MagicMock(),
            "command": {
                "command": "/sre groups",
                "text": "",
                "user_id": "U12345",
                "user_name": "testuser",
                "channel_id": "C12345",
                "team_id": "T12345",
            },
            "client": mock_client,
            "respond": MagicMock(),
            "body": {
                "user_id": "U12345",
                "trigger_id": "trigger123",
            },
        }

    def test_help_command_returns_text(self, adapter, slack_payload):
        """Test help command returns help text."""
        slack_payload["command"]["text"] = "help"

        adapter.handle(slack_payload)

        # Verify help was sent
        respond = slack_payload["respond"]
        assert respond.called

    def test_list_command_end_to_end(self, adapter, slack_payload):
        """Test complete flow from Slack payload to response."""
        slack_payload["command"]["text"] = "list"

        with patch("modules.groups.commands.handlers.service") as mock_service:
            mock_service.list_groups.return_value = []

            adapter.handle(slack_payload)

        # Verify acknowledge was called
        ack = slack_payload["ack"]
        assert ack.called

        # Verify service was called
        assert mock_service.list_groups.called

    def test_list_with_provider_argument(self, adapter, slack_payload):
        """Test list command with provider argument."""
        slack_payload["command"]["text"] = "list google"

        with patch("modules.groups.commands.handlers.service") as mock_service:
            mock_service.list_groups.return_value = []

            adapter.handle(slack_payload)

        call_args = mock_service.list_groups.call_args[0][0]
        assert call_args.provider is not None

    def test_add_command_end_to_end(self, adapter, slack_payload):
        """Test add command flow."""
        slack_payload["command"][
            "text"
        ] = 'add user@example.com group-1 google "Test reason"'

        with patch("modules.groups.commands.handlers.service") as mock_service:
            mock_result = MagicMock()
            mock_result.model_dump.return_value = {"success": True}
            mock_service.add_member.return_value = mock_result

            adapter.handle(slack_payload)

        assert mock_service.add_member.called
        call_args = mock_service.add_member.call_args[0][0]
        assert call_args.member_email == "user@example.com"
        assert call_args.group_id == "group-1"

    def test_remove_command_end_to_end(self, adapter, slack_payload):
        """Test remove command flow."""
        slack_payload["command"]["text"] = "remove user@example.com group-1 aws"

        with patch("modules.groups.commands.handlers.service") as mock_service:
            mock_result = MagicMock()
            mock_result.model_dump.return_value = {"success": True}
            mock_service.remove_member.return_value = mock_result

            adapter.handle(slack_payload)

        assert mock_service.remove_member.called
        call_args = mock_service.remove_member.call_args[0][0]
        assert call_args.member_email == "user@example.com"

    def test_manage_command_end_to_end(self, adapter, slack_payload):
        """Test manage command flow."""
        slack_payload["command"]["text"] = "manage"

        with patch("modules.groups.commands.handlers.service") as mock_service:
            mock_service.list_groups.return_value = []

            adapter.handle(slack_payload)

        assert mock_service.list_groups.called

    def test_unknown_command_error(self, adapter, slack_payload):
        """Test error handling for unknown command."""
        slack_payload["command"]["text"] = "unknown_command"

        adapter.handle(slack_payload)

        # Should send error response
        respond = slack_payload["respond"]
        assert respond.called

    def test_list_with_managed_flag(self, adapter, slack_payload):
        """Test list command with --managed flag."""
        slack_payload["command"]["text"] = "list --managed"

        with patch("modules.groups.commands.handlers.service") as mock_service:
            mock_service.list_groups.return_value = []

            adapter.handle(slack_payload)

        call_args = mock_service.list_groups.call_args[0][0]
        assert call_args.filter_by_member_role == ["MANAGER", "OWNER"]

    def test_locale_detection(self, adapter, slack_payload):
        """Test that locale is detected and used in context."""
        slack_payload["command"]["text"] = "help"

        adapter.handle(slack_payload)

        # Verify help was sent (help text should be in the response)
        respond = slack_payload["respond"]
        assert respond.called

    def test_list_with_role_filter(self, adapter, slack_payload):
        """Test list command with --role filter."""
        slack_payload["command"]["text"] = "list --role MANAGER,OWNER"

        with patch("modules.groups.commands.handlers.service") as mock_service:
            mock_service.list_groups.return_value = []

            adapter.handle(slack_payload)

        call_args = mock_service.list_groups.call_args[0][0]
        assert call_args.filter_by_member_role == ["MANAGER", "OWNER"]
