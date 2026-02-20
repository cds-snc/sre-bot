"""Integration tests for SRE platform command handlers.

Tests cover command registration with platform providers,
handler execution, and integration with legacy helper functions.

Follows new platform architecture where commands are registered via
platform providers instead of legacy command providers.
"""

from unittest.mock import MagicMock, patch

import pytest

from infrastructure.platforms.models import CommandPayload, CommandResponse
from modules.sre.platforms import slack as sre_slack


@pytest.mark.integration
class TestSRECommandRegistration:
    """Test SRE command registration with platform providers."""

    def test_should_register_all_sre_subcommands(self, slack_provider):
        """SRE module should register all subcommands with platform provider."""
        # Arrange - platform provider created in fixture

        # Act
        sre_slack.register_commands(slack_provider)

        # Assert
        registered_commands = slack_provider._commands
        assert "sre.version" in registered_commands
        assert "sre.incident" in registered_commands
        assert "sre.webhooks" in registered_commands
        assert "sre.groups" in registered_commands

    def test_should_set_correct_description_keys(self, slack_provider):
        """SRE commands should have translation keys for i18n."""
        # Arrange & Act
        sre_slack.register_commands(slack_provider)

        # Assert
        version_cmd = slack_provider._commands.get("sre.version")
        assert version_cmd is not None
        assert version_cmd.description_key == "sre.subcommands.version.description"

        incident_cmd = slack_provider._commands.get("sre.incident")
        assert incident_cmd is not None
        assert incident_cmd.description_key == "sre.subcommands.incident.description"


@pytest.mark.integration
class TestVersionCommandHandler:
    """Test /sre version command handler integration."""

    def test_should_return_version_from_settings(self, monkeypatch):
        """Version handler should return Git SHA from settings."""
        # Arrange
        mock_settings = MagicMock()
        mock_settings.GIT_SHA = "abc123def456"
        monkeypatch.setattr(sre_slack, "get_settings", lambda: mock_settings)

        payload = CommandPayload(
            text="",
            user_id="U12345",
            channel_id="C12345",
        )

        # Act
        response = sre_slack.handle_version_command(payload)

        # Assert
        assert isinstance(response, CommandResponse)
        assert "abc123def456" in response.message
        assert "SRE Bot version:" in response.message
        assert response.ephemeral is True

    def test_should_handle_empty_payload_text(self, monkeypatch):
        """Version handler should work with empty text."""
        # Arrange
        mock_settings = MagicMock()
        mock_settings.GIT_SHA = "test-sha"
        monkeypatch.setattr(sre_slack, "get_settings", lambda: mock_settings)

        payload = CommandPayload(
            text="",
            user_id="U12345",
            channel_id="C12345",
        )

        # Act
        response = sre_slack.handle_version_command(payload)

        # Assert
        assert response.message is not None
        assert "test-sha" in response.message


@pytest.mark.integration
class TestIncidentCommandHandler:
    """Test /sre incident command handler integration."""

    @patch("modules.sre.platforms.slack.incident_helper.handle_incident_command")
    def test_should_delegate_to_legacy_incident_helper(
        self, mock_incident_handler, mock_slack_client
    ):
        """Incident handler should bridge to legacy incident_helper."""
        # Arrange
        payload = CommandPayload(
            text="list",
            user_id="U12345",
            channel_id="C12345",
            platform_metadata={"user_name": "testuser"},
        )

        # Act
        sre_slack.handle_incident_command(payload)

        # Assert
        mock_incident_handler.assert_called_once()
        call_args = mock_incident_handler.call_args
        assert call_args[1]["args"] == ["list"]
        assert call_args[1]["body"]["user_id"] == "U12345"
        assert call_args[1]["body"]["channel_id"] == "C12345"

    @patch("modules.sre.platforms.slack.incident_helper.handle_incident_command")
    def test_should_parse_command_text_into_args(
        self, mock_incident_handler, mock_slack_client
    ):
        """Incident handler should split text into args array."""
        # Arrange
        payload = CommandPayload(
            text="create high-priority bug-123",
            user_id="U12345",
            channel_id="C12345",
        )

        # Act
        sre_slack.handle_incident_command(payload)

        # Assert
        call_args = mock_incident_handler.call_args
        assert call_args[1]["args"] == ["create", "high-priority", "bug-123"]

    @patch("modules.sre.platforms.slack.incident_helper.handle_incident_command")
    def test_should_capture_legacy_respond_blocks(
        self, mock_incident_handler, mock_slack_client
    ):
        """Incident handler should capture blocks from legacy respond calls."""
        # Arrange
        test_blocks = [{"type": "section", "text": {"type": "mrkdwn", "text": "Test"}}]

        def side_effect_respond(args, client, body, respond, ack):
            respond(blocks=test_blocks)

        mock_incident_handler.side_effect = side_effect_respond

        payload = CommandPayload(
            text="list",
            user_id="U12345",
            channel_id="C12345",
        )

        # Act
        response = sre_slack.handle_incident_command(payload)

        # Assert
        assert response.blocks == test_blocks
        assert response.ephemeral is True


@pytest.mark.integration
class TestWebhooksCommandHandler:
    """Test /sre webhooks command handler integration."""

    @patch("modules.sre.platforms.slack.webhook_helper.handle_webhook_command")
    def test_should_delegate_to_legacy_webhook_helper(
        self, mock_webhook_handler, mock_slack_client
    ):
        """Webhooks handler should bridge to legacy webhook_helper."""
        # Arrange
        payload = CommandPayload(
            text="list",
            user_id="U12345",
            channel_id="C12345",
        )

        # Act
        sre_slack.handle_webhooks_command(payload)

        # Assert
        mock_webhook_handler.assert_called_once()
        call_args = mock_webhook_handler.call_args
        assert call_args[1]["args"] == ["list"]
        assert call_args[1]["body"]["user_id"] == "U12345"

    @patch("modules.sre.platforms.slack.webhook_helper.handle_webhook_command")
    def test_should_handle_empty_text(self, mock_webhook_handler, mock_slack_client):
        """Webhooks handler should handle empty text as empty args."""
        # Arrange
        payload = CommandPayload(
            text="",
            user_id="U12345",
            channel_id="C12345",
        )

        # Act
        sre_slack.handle_webhooks_command(payload)

        # Assert
        call_args = mock_webhook_handler.call_args
        assert call_args[1]["args"] == []


@pytest.mark.integration
class TestGroupsCommandHandler:
    """Test /sre groups command handler integration."""

    def test_should_return_migration_message(self):
        """Groups handler should inform about migration to new architecture."""
        # Arrange
        payload = CommandPayload(
            text="list",
            user_id="U12345",
            channel_id="C12345",
        )

        # Act
        response = sre_slack.handle_groups_command(payload)

        # Assert
        assert isinstance(response, CommandResponse)
        assert "Groups management" in response.message
        assert response.ephemeral is True

    def test_should_handle_any_subcommand_text(self):
        """Groups handler should respond consistently regardless of text."""
        # Arrange
        payload = CommandPayload(
            text="create test-group",
            user_id="U12345",
            channel_id="C12345",
        )

        # Act
        response = sre_slack.handle_groups_command(payload)

        # Assert
        assert response.message is not None
        assert response.ephemeral is True
