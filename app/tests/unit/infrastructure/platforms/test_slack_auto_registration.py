"""Test SlackPlatformProvider auto-registration of root commands.

Tests verify that the platform provider automatically registers root Slack commands
(e.g., /sre, /geolocate) when child commands are registered during initialization.

Follows AAA pattern and factory fixture conventions.
"""

from unittest.mock import Mock

import pytest

from infrastructure.configuration.infrastructure.platforms import (
    SlackPlatformSettings,
)
from infrastructure.platforms.formatters.slack import SlackBlockKitFormatter
from infrastructure.platforms.providers.slack import SlackPlatformProvider
from infrastructure.platforms.models import CommandPayload, CommandResponse


@pytest.fixture
def make_slack_settings():
    """Factory for creating Slack settings with customizable values."""

    def _make(
        enabled: bool = True,
        socket_mode: bool = True,
        app_token: str = "xapp-test",
        bot_token: str = "xoxb-test",
    ):
        return SlackPlatformSettings(
            ENABLED=enabled,
            SOCKET_MODE=socket_mode,
            APP_TOKEN=app_token,
            BOT_TOKEN=bot_token,
        )

    return _make


@pytest.fixture
def slack_provider(make_slack_settings, monkeypatch):
    """Create SlackPlatformProvider instance with mocked Bolt components."""

    # Mock Slack Bolt classes to avoid network calls
    class FakeApp:
        def __init__(self, token=None):
            self.client = Mock()

        def command(self, command_name):
            """Mock command decorator."""

            def decorator(func):
                return func

            return decorator

    class FakeSocketModeHandler:
        def __init__(self, app, token):
            self.app = app
            self.token = token

    monkeypatch.setattr("infrastructure.platforms.providers.slack.App", FakeApp)
    monkeypatch.setattr(
        "infrastructure.platforms.providers.slack.SocketModeHandler",
        FakeSocketModeHandler,
    )

    settings = make_slack_settings()
    formatter = SlackBlockKitFormatter()
    provider = SlackPlatformProvider(
        settings=settings,
        formatter=formatter,
    )
    return provider


@pytest.fixture
def make_command_handler():
    """Factory for creating test command handlers."""

    def _make(message: str = "test"):
        def handler(payload: CommandPayload) -> CommandResponse:
            return CommandResponse(message=message)

        return handler

    return _make


@pytest.mark.unit
class TestRootCommandAutoRegistration:
    """Test automatic registration of root Slack commands."""

    def test_should_extract_unique_roots_from_command_tree(
        self, slack_provider, make_command_handler
    ):
        """Should extract unique root commands from registered command tree."""
        # Arrange - Register commands with various parents
        handler = make_command_handler()

        slack_provider.register_command(
            command="incident",
            parent="sre",
            handler=handler,
            description="Incident commands",
        )
        slack_provider.register_command(
            command="webhooks",
            parent="sre",
            handler=handler,
            description="Webhook commands",
        )
        slack_provider.register_command(
            command="version",
            parent="sre",
            handler=handler,
            description="Version info",
        )
        slack_provider.register_command(
            command="coordinates",
            parent="geolocate",
            handler=handler,
            description="Geolocate commands",
        )

        # Act - Initialize app (triggers auto-registration)
        slack_provider.initialize_app()

        # Assert - App was created
        assert slack_provider.app is not None

        # Assert - Commands are registered in command tree
        assert "sre.incident" in slack_provider._commands
        assert "sre.webhooks" in slack_provider._commands
        assert "sre.version" in slack_provider._commands
        assert "geolocate.coordinates" in slack_provider._commands

        # Assert - Root nodes were auto-generated
        assert "sre" in slack_provider._commands
        assert "geolocate" in slack_provider._commands

    def test_should_create_handlers_for_each_unique_root(
        self, slack_provider, make_command_handler
    ):
        """Should create Slack Bolt handlers for each unique root command."""
        # Arrange
        handler = make_command_handler()

        # Register commands under "sre" root
        slack_provider.register_command(
            command="incident",
            parent="sre",
            handler=handler,
            description="Incident",
        )

        # Register commands under "aws" root
        slack_provider.register_command(
            command="list",
            parent="aws",
            handler=handler,
            description="AWS list",
        )

        # Act
        slack_provider.initialize_app()

        # Assert - App created
        assert slack_provider.app is not None

        # Assert - Both roots exist in command tree
        assert "sre" in slack_provider._commands
        assert "aws" in slack_provider._commands

        # Assert - Child commands registered
        assert "sre.incident" in slack_provider._commands
        assert "aws.list" in slack_provider._commands

    def test_should_skip_auto_registration_when_app_not_initialized(
        self, slack_provider
    ):
        """Should skip auto-registration if app is None."""
        # Arrange - Force app to None (simulating initialization failure)
        slack_provider._app = None

        # Act - Try to auto-register (should log warning and skip gracefully)
        slack_provider._auto_register_root_commands()

        # Assert - No error raised, just skips gracefully
        assert slack_provider._app is None

    def test_should_handle_nested_parent_paths(
        self, slack_provider, make_command_handler
    ):
        """Should handle commands with nested parent paths (e.g., sre.dev.aws)."""
        # Arrange
        handler = make_command_handler()

        # Register command with nested parent "sre.dev"
        slack_provider.register_command(
            command="aws",
            parent="sre.dev",
            handler=handler,
            description="AWS dev commands",
        )

        # Act
        slack_provider.initialize_app()

        # Assert - Should extract root "sre" and register /sre
        assert slack_provider.app is not None

        # Assert - Intermediate nodes auto-generated
        assert slack_provider._commands.get("sre") is not None  # Auto-generated
        assert slack_provider._commands.get("sre.dev") is not None  # Auto-generated
        assert (
            slack_provider._commands.get("sre.dev.aws") is not None
        )  # Explicit registration

    def test_should_handle_empty_command_tree(self, slack_provider):
        """Should handle initialization with no registered commands."""
        # Arrange - No commands registered

        # Act
        slack_provider.initialize_app()

        # Assert - App initialized without errors
        assert slack_provider.app is not None
        assert len(slack_provider._commands) == 0


@pytest.mark.unit
class TestCommandResponseSending:
    """Test sending CommandResponse to Slack using respond function."""

    def test_should_send_response_with_blocks(self, slack_provider):
        """Should send response with blocks to Slack."""
        # Arrange
        response = CommandResponse(
            message="Test message",
            blocks=[{"type": "section", "text": {"type": "mrkdwn", "text": "Test"}}],
            ephemeral=True,
        )
        mock_respond = Mock()

        # Act
        slack_provider._send_command_response(response, mock_respond)

        # Assert
        mock_respond.assert_called_once_with(
            text="Test message",
            blocks=response.blocks,
            response_type="ephemeral",
        )

    def test_should_send_response_with_attachments(self, slack_provider):
        """Should send response with attachments to Slack."""
        # Arrange
        response = CommandResponse(
            message="Test message",
            attachments=[{"color": "#36a64f", "text": "Attachment"}],
            ephemeral=False,
        )
        mock_respond = Mock()

        # Act
        slack_provider._send_command_response(response, mock_respond)

        # Assert
        mock_respond.assert_called_once_with(
            text="Test message",
            attachments=response.attachments,
            response_type="in_channel",
        )

    def test_should_send_plain_text_response(self, slack_provider):
        """Should send plain text response to Slack."""
        # Arrange
        response = CommandResponse(
            message="Simple message",
            ephemeral=True,
        )
        mock_respond = Mock()

        # Act
        slack_provider._send_command_response(response, mock_respond)

        # Assert
        mock_respond.assert_called_once_with(
            text="Simple message",
            response_type="ephemeral",
        )

    def test_should_send_empty_response_when_no_content(self, slack_provider):
        """Should send empty response if no content provided."""
        # Arrange
        response = CommandResponse(message="", ephemeral=False)
        mock_respond = Mock()

        # Act
        slack_provider._send_command_response(response, mock_respond)

        # Assert
        mock_respond.assert_called_once_with(
            text="",
            response_type="in_channel",
        )

    def test_should_use_in_channel_when_not_ephemeral(self, slack_provider):
        """Should use in_channel response type when ephemeral is False."""
        # Arrange
        response = CommandResponse(message="Public message", ephemeral=False)
        mock_respond = Mock()

        # Act
        slack_provider._send_command_response(response, mock_respond)

        # Assert
        mock_respond.assert_called_once()
        call_kwargs = mock_respond.call_args.kwargs
        assert call_kwargs["response_type"] == "in_channel"

    def test_should_prioritize_blocks_over_attachments(self, slack_provider):
        """Should send blocks when both blocks and attachments provided."""
        # Arrange - Response with both blocks and attachments
        response = CommandResponse(
            message="Test",
            blocks=[{"type": "section", "text": {"type": "mrkdwn", "text": "Block"}}],
            attachments=[{"text": "Attachment"}],
            ephemeral=True,
        )
        mock_respond = Mock()

        # Act
        slack_provider._send_command_response(response, mock_respond)

        # Assert - Should send blocks, not attachments
        assert mock_respond.call_args.kwargs.get("blocks") is not None
        assert "attachments" not in mock_respond.call_args.kwargs
