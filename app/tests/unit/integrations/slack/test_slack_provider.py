"""Unit tests for SlackPlatformProvider."""

import logging
from unittest.mock import MagicMock

import pytest

import integrations.slack.provider as provider_module
from contracts.operations import OperationStatus
from contracts.slack.models import CommandPayload, CommandResponse
from infrastructure.logging.formatters import SLACK_SOCKET_MODE_LOGGER
from integrations.slack.formatter import SlackBlockKitFormatter
from integrations.slack.provider import SlackPlatformProvider


# Fake Slack Bolt classes for unit tests to avoid network/socket operations
@pytest.fixture
def mock_slack_bolt(monkeypatch):
    class FakeApp:
        def __init__(self, token=None):
            self.client = object()

    class FakeSocketModeHandler:
        def __init__(self, app, token, logger=None):
            self.app = app
            self.token = token
            self.logger = logger

        def connect(self):
            return None

    monkeypatch.setattr("integrations.slack.provider.App", FakeApp)
    monkeypatch.setattr(
        "integrations.slack.provider.SocketModeHandler",
        FakeSocketModeHandler,
    )
    return None


@pytest.mark.unit
class TestSlackPlatformProvider:
    """Test SlackPlatformProvider initialization and basic operations."""

    def test_initialization(self, slack_settings, slack_formatter):
        """Test provider initialization."""
        provider = SlackPlatformProvider(settings=slack_settings, formatter=slack_formatter)

        assert provider.name == "slack"
        assert provider.version == "1.0.0"
        assert provider.enabled is True
        assert provider.formatter is slack_formatter
        assert provider.settings is slack_settings

    def test_initialization_with_custom_name_version(self, slack_settings):
        """Test initialization with custom name and version."""
        provider = SlackPlatformProvider(settings=slack_settings, name="custom-slack", version="2.0.0")

        assert provider.name == "custom-slack"
        assert provider.version == "2.0.0"

    def test_initialization_creates_default_formatter(self, slack_settings):
        """Test that provider creates default formatter if not provided."""
        provider = SlackPlatformProvider(settings=slack_settings)

        assert isinstance(provider.formatter, SlackBlockKitFormatter)

    def test_provider_properties(self, slack_settings, slack_formatter):
        """Test provider property accessors."""
        provider = SlackPlatformProvider(settings=slack_settings, formatter=slack_formatter)

        assert provider.formatter is slack_formatter
        assert provider.settings is slack_settings
        assert provider.name == "slack"


@pytest.mark.unit
class TestHierarchicalRouting:
    """Test Slack hierarchical command routing behavior."""

    def test_route_hierarchical_command_preserves_quoted_args(self, slack_settings: object) -> None:
        """Should preserve quoted arguments when routing to subcommands."""
        # Arrange
        provider = SlackPlatformProvider(settings=slack_settings)

        def handler(payload: CommandPayload) -> CommandResponse:
            return CommandResponse(message=payload.text)

        provider.register_command(
            command="create",
            parent="incident",
            handler=handler,
            description="Create incident",
        )
        payload = CommandPayload(text="", user_id="U123", channel_id="C123")

        # Act
        response = provider.route_hierarchical_command(
            root_command="incident",
            text='create --title "Database outage in prod"',
            payload=payload,
        )

        # Assert
        assert response.message == "--title Database outage in prod"

    def test_route_hierarchical_command_recursive_three_levels(self, slack_settings: object) -> None:
        """Should route recursively through multiple command levels (3+)."""
        # Arrange
        provider = SlackPlatformProvider(settings=slack_settings)

        def handler(payload: CommandPayload) -> CommandResponse:
            return CommandResponse(message=f"received:{payload.text}")

        # Register 3-level hierarchy: sre → groups → add
        provider.register_command(
            command="create",
            parent="sre.groups",
            handler=handler,
            description="Create group",
        )
        payload = CommandPayload(text="", user_id="U123", channel_id="C123")

        # Act: Route through 3 levels
        response = provider.route_hierarchical_command(
            root_command="sre",
            text="groups create admin@example.com",
            payload=payload,
        )

        # Assert: Handler receives only the email (arguments, not command names)
        assert response.message == "received:admin@example.com"

    def test_route_hierarchical_command_recursive_with_options(self, slack_settings: object) -> None:
        """Should preserve options and flags through recursive routing."""
        # Arrange
        provider = SlackPlatformProvider(settings=slack_settings)

        def handler(payload: CommandPayload) -> CommandResponse:
            return CommandResponse(message=f"args:{payload.text}")

        # Register 2-level hierarchy: sre → groups → list
        provider.register_command(
            command="list",
            parent="sre.groups",
            handler=handler,
            description="List groups",
        )
        payload = CommandPayload(text="", user_id="U123", channel_id="C123")

        # Act: Route with complex options
        response = provider.route_hierarchical_command(
            root_command="sre",
            text='groups list --provider aws --managed --name "Security Team"',
            payload=payload,
        )

        # Assert: All options passed to leaf handler
        # Note: Quotes are removed by tokenizer but quoted content is preserved
        assert "--provider aws --managed --name" in response.message
        assert "Security Team" in response.message

    def test_route_hierarchical_command_help_keyword_at_root(self, slack_settings: object) -> None:
        """Should process help keyword at root level without recursing."""
        # Arrange
        provider = SlackPlatformProvider(settings=slack_settings)

        # Register 2-level hierarchy
        provider.register_command(
            command="list",
            parent="sre.groups",
            handler=lambda p: CommandResponse(message="list handler"),
            description="List groups",
        )
        payload = CommandPayload(text="", user_id="U123", channel_id="C123")

        # Act: Help keyword at root
        response = provider.route_hierarchical_command(
            root_command="sre",
            text="help",  # Should not recurse, should show help for "sre"
            payload=payload,
        )

        # Assert: Response contains help, not routing error
        assert response.ephemeral is True
        assert response.message  # Should have some help text

    def test_route_hierarchical_command_help_keyword_at_intermediate_level(self, slack_settings: object) -> None:
        """Should process help keyword at intermediate routing levels."""
        # Arrange
        provider = SlackPlatformProvider(settings=slack_settings)

        # Register 2-level hierarchy
        provider.register_command(
            command="list",
            parent="sre.groups",
            handler=lambda p: CommandResponse(message="list handler"),
            description="List groups",
        )
        payload = CommandPayload(text="", user_id="U123", channel_id="C123")

        # Act: Help keyword after routing one level
        response = provider.route_hierarchical_command(
            root_command="sre",
            text="groups help",  # Help after routing to groups
            payload=payload,
        )

        # Assert: Response contains help for groups commands
        assert response.ephemeral is True
        assert response.message  # Should have some help text


@pytest.mark.unit
class TestInitializeApp:
    """Test initialize_app() method."""

    def test_initialize_app_success(self, slack_settings, mock_slack_bolt):
        """Test successful app initialization."""
        provider = SlackPlatformProvider(settings=slack_settings)

        result = provider.initialize_app()

        assert result.is_success
        assert result.data["initialized"] is True
        assert result.data["socket_mode"] is True

    def test_initialize_app_routes_socket_mode_logs_to_dedicated_logger(self, slack_settings, mock_slack_bolt):
        """Socket Mode handler logs through ``slack_sdk.socket_mode``, not Bolt's app logger.

        The fake handler records the ``logger`` argument; a dedicated name lets the logging
        pipeline downgrade transient websocket errors without touching listener errors.
        """
        provider = SlackPlatformProvider(settings=slack_settings)

        assert provider.initialize_app().is_success

        handler = provider.socket_mode_handler
        assert handler is not None
        assert handler.logger is logging.getLogger(SLACK_SOCKET_MODE_LOGGER)

    def test_initialize_app_disabled_provider(self, slack_settings, mock_slack_bolt):
        """With the transport switched off, initialization is skipped."""
        provider = SlackPlatformProvider(settings=slack_settings, enabled=False)

        result = provider.initialize_app()

        assert not result.is_success
        assert result.status == OperationStatus.PERMANENT_ERROR
        assert result.error_code == "PROVIDER_DISABLED"

    def test_initialize_app_missing_app_token(self):
        """Test initialization with missing APP_TOKEN in Socket Mode."""
        settings = MagicMock()
        settings.app_token = None
        settings.bot_token = "xoxb-test"

        provider = SlackPlatformProvider(settings=settings)
        result = provider.initialize_app()

        assert not result.is_success
        assert result.error_code == "MISSING_APP_TOKEN"

    def test_initialize_app_missing_bot_token(self):
        """Test initialization with missing BOT_TOKEN."""
        settings = MagicMock()
        settings.app_token = "xapp-test"
        settings.bot_token = None
        provider = SlackPlatformProvider(settings=settings)
        result = provider.initialize_app()

        assert not result.is_success
        assert result.error_code == "MISSING_BOT_TOKEN"

    def test_initialize_app_without_socket_mode(self, slack_settings_http_mode, mock_slack_bolt):
        """Test initialization without Socket Mode."""
        provider = SlackPlatformProvider(settings=slack_settings_http_mode, socket_mode=False)

        result = provider.initialize_app()

        # Should succeed even without APP_TOKEN when socket_mode is False
        assert result.is_success
        assert result.data["socket_mode"] is False

    def test_initialize_app_all_tokens_present(self, slack_settings, mock_slack_bolt):
        """Test initialization with all required tokens."""
        provider = SlackPlatformProvider(settings=slack_settings)

        result = provider.initialize_app()

        assert result.is_success


@pytest.mark.unit
class TestSlackProviderFactory:
    """Test get_slack_provider assembly behavior."""

    def test_passes_the_host_transport_values_into_the_provider(self, monkeypatch):
        """The factory builds the provider from the values the host passes, reading no transport slice."""
        captured: dict[str, object] = {}

        class FakeConstructedProvider:
            def __init__(self, *, settings, formatter, command_prefix, enabled, socket_mode):
                captured.update(command_prefix=command_prefix, enabled=enabled, socket_mode=socket_mode)

        provider_module.get_slack_provider.cache_clear()
        try:
            monkeypatch.setattr(provider_module, "SlackPlatformProvider", FakeConstructedProvider)
            monkeypatch.setattr(provider_module, "get_slack_settings", lambda: object())
            monkeypatch.setattr(provider_module, "SlackBlockKitFormatter", lambda: object())

            provider_module.get_slack_provider(enabled=True, socket_mode=False, command_prefix="dev-")
        finally:
            provider_module.get_slack_provider.cache_clear()

        assert captured == {"command_prefix": "dev-", "enabled": True, "socket_mode": False}
