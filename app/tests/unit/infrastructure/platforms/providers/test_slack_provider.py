"""Unit tests for SlackPlatformProvider."""

import pytest

from infrastructure.operations import OperationStatus
from infrastructure.platforms.capabilities.models import PlatformCapability
from infrastructure.platforms.formatters.slack import SlackBlockKitFormatter
from infrastructure.platforms.models import CommandPayload, CommandResponse
from infrastructure.platforms.providers.slack import SlackPlatformProvider


# Fake Slack Bolt classes for unit tests to avoid network/socket operations
@pytest.fixture
def mock_slack_bolt(monkeypatch):
    class FakeApp:
        def __init__(self, token=None):
            self.client = object()

    class FakeSocketModeHandler:
        def __init__(self, app, token):
            self.app = app
            self.token = token

        def connect(self):
            return None

    monkeypatch.setattr("infrastructure.platforms.providers.slack.App", FakeApp)
    monkeypatch.setattr(
        "infrastructure.platforms.providers.slack.SocketModeHandler",
        FakeSocketModeHandler,
    )
    return None


@pytest.mark.unit
class TestSlackPlatformProvider:
    """Test SlackPlatformProvider initialization and basic operations."""

    def test_initialization(self, slack_settings, slack_formatter):
        """Test provider initialization."""
        provider = SlackPlatformProvider(
            settings=slack_settings, formatter=slack_formatter
        )

        assert provider.name == "slack"
        assert provider.version == "1.0.0"
        assert provider.enabled is True
        assert provider.formatter is slack_formatter
        assert provider.settings is slack_settings

    def test_initialization_with_custom_name_version(self, slack_settings):
        """Test initialization with custom name and version."""
        provider = SlackPlatformProvider(
            settings=slack_settings, name="custom-slack", version="2.0.0"
        )

        assert provider.name == "custom-slack"
        assert provider.version == "2.0.0"

    def test_initialization_creates_default_formatter(self, slack_settings):
        """Test that provider creates default formatter if not provided."""
        provider = SlackPlatformProvider(settings=slack_settings)

        assert isinstance(provider.formatter, SlackBlockKitFormatter)

    def test_initialization_disabled_provider(self, slack_settings_disabled):
        """Test initialization with disabled provider."""
        provider = SlackPlatformProvider(settings=slack_settings_disabled)

        assert provider.enabled is False

    def test_provider_properties(self, slack_settings, slack_formatter):
        """Test provider property accessors."""
        provider = SlackPlatformProvider(
            settings=slack_settings, formatter=slack_formatter
        )

        assert provider.formatter is slack_formatter
        assert provider.settings is slack_settings
        assert provider.name == "slack"


@pytest.mark.unit
class TestGetCapabilities:
    """Test get_capabilities() method."""

    def test_get_capabilities_returns_declaration(self, slack_settings):
        """Test that get_capabilities returns CapabilityDeclaration."""
        provider = SlackPlatformProvider(settings=slack_settings)

        capabilities = provider.get_capabilities()

        assert capabilities is not None
        assert hasattr(capabilities, "capabilities")
        assert hasattr(capabilities, "metadata")

    def test_capabilities_include_commands(self, slack_settings):
        """Test that capabilities include COMMANDS."""
        provider = SlackPlatformProvider(settings=slack_settings)

        capabilities = provider.get_capabilities()

        assert capabilities.supports(PlatformCapability.COMMANDS)

    def test_capabilities_include_interactive_cards(self, slack_settings):
        """Test that capabilities include INTERACTIVE_CARDS."""
        provider = SlackPlatformProvider(settings=slack_settings)

        capabilities = provider.get_capabilities()

        assert capabilities.supports(PlatformCapability.INTERACTIVE_CARDS)

    def test_capabilities_include_views_modals(self, slack_settings):
        """Test that capabilities include VIEWS_MODALS."""
        provider = SlackPlatformProvider(settings=slack_settings)

        capabilities = provider.get_capabilities()

        assert capabilities.supports(PlatformCapability.VIEWS_MODALS)

    def test_capabilities_include_threads(self, slack_settings):
        """Test that capabilities include THREADS."""
        provider = SlackPlatformProvider(settings=slack_settings)

        capabilities = provider.get_capabilities()

        assert capabilities.supports(PlatformCapability.THREADS)

    def test_capabilities_include_reactions(self, slack_settings):
        """Test that capabilities include REACTIONS."""
        provider = SlackPlatformProvider(settings=slack_settings)

        capabilities = provider.get_capabilities()

        assert capabilities.supports(PlatformCapability.REACTIONS)

    def test_capabilities_include_file_sharing(self, slack_settings):
        """Test that capabilities include FILE_SHARING."""
        provider = SlackPlatformProvider(settings=slack_settings)

        capabilities = provider.get_capabilities()

        assert capabilities.supports(PlatformCapability.FILE_SHARING)

    def test_capabilities_include_hierarchical_text_commands(self, slack_settings):
        """Test that capabilities include HIERARCHICAL_TEXT_COMMANDS."""
        provider = SlackPlatformProvider(settings=slack_settings)

        capabilities = provider.get_capabilities()

        assert capabilities.supports(PlatformCapability.HIERARCHICAL_TEXT_COMMANDS)

    def test_capabilities_metadata_includes_socket_mode(self, slack_settings):
        """Test that capabilities metadata includes socket_mode."""
        provider = SlackPlatformProvider(settings=slack_settings)

        capabilities = provider.get_capabilities()

        assert "socket_mode" in capabilities.metadata
        assert capabilities.metadata["socket_mode"] is True

    def test_capabilities_metadata_includes_platform(self, slack_settings):
        """Test that capabilities metadata includes platform."""
        provider = SlackPlatformProvider(settings=slack_settings)

        capabilities = provider.get_capabilities()

        assert capabilities.metadata["platform"] == "slack"

    def test_capabilities_metadata_includes_command_parsing(self, slack_settings):
        """Test that capabilities metadata includes command_parsing."""
        provider = SlackPlatformProvider(settings=slack_settings)

        capabilities = provider.get_capabilities()

        assert capabilities.metadata["command_parsing"] == "hierarchical_text"


@pytest.mark.unit
class TestHierarchicalRouting:
    """Test Slack hierarchical command routing behavior."""

    def test_route_hierarchical_command_preserves_quoted_args(
        self, slack_settings: object
    ) -> None:
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

    def test_route_hierarchical_command_recursive_three_levels(
        self, slack_settings: object
    ) -> None:
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

    def test_route_hierarchical_command_recursive_with_options(
        self, slack_settings: object
    ) -> None:
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

    def test_route_hierarchical_command_help_keyword_at_root(
        self, slack_settings: object
    ) -> None:
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

    def test_route_hierarchical_command_help_keyword_at_intermediate_level(
        self, slack_settings: object
    ) -> None:
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

    def test_capabilities_socket_mode_false(self, slack_settings_http_mode):
        """Test capabilities metadata when socket_mode is False."""
        provider = SlackPlatformProvider(settings=slack_settings_http_mode)

        capabilities = provider.get_capabilities()

        assert capabilities.metadata["socket_mode"] is False


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

    def test_initialize_app_disabled_provider(
        self, slack_settings_disabled, mock_slack_bolt
    ):
        """Test initialization when provider is disabled."""
        provider = SlackPlatformProvider(settings=slack_settings_disabled)

        result = provider.initialize_app()

        assert not result.is_success
        assert result.status == OperationStatus.PERMANENT_ERROR
        assert result.error_code == "PROVIDER_DISABLED"

    def test_initialize_app_missing_app_token(self):
        """Test initialization with missing APP_TOKEN in Socket Mode."""
        from tests.unit.infrastructure.platforms.providers.conftest import (
            MockSlackSettings,
        )

        settings = MockSlackSettings(
            socket_mode=True, app_token=None, bot_token="xoxb-test"
        )
        provider = SlackPlatformProvider(settings=settings)

        result = provider.initialize_app()

        assert not result.is_success
        assert result.error_code == "MISSING_APP_TOKEN"

    def test_initialize_app_missing_bot_token(self):
        """Test initialization with missing BOT_TOKEN."""
        from tests.unit.infrastructure.platforms.providers.conftest import (
            MockSlackSettings,
        )

        settings = MockSlackSettings(
            socket_mode=True, app_token="xapp-test", bot_token=None
        )
        provider = SlackPlatformProvider(settings=settings)

        result = provider.initialize_app()

        assert not result.is_success
        assert result.error_code == "MISSING_BOT_TOKEN"

    def test_initialize_app_without_socket_mode(
        self, slack_settings_http_mode, mock_slack_bolt
    ):
        """Test initialization without Socket Mode."""
        provider = SlackPlatformProvider(settings=slack_settings_http_mode)

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
class TestProviderIntegration:
    """Test provider integration with base class."""

    def test_supports_capability(self, slack_settings):
        """Test supports_capability() inherited from base class."""
        provider = SlackPlatformProvider(settings=slack_settings)

        assert provider.supports_capability(PlatformCapability.COMMANDS)
        assert provider.supports_capability(PlatformCapability.THREADS)

    def test_repr(self, slack_settings):
        """Test __repr__ string representation."""
        provider = SlackPlatformProvider(settings=slack_settings)

        repr_str = repr(provider)

        assert "SlackPlatformProvider" in repr_str
        assert "name='slack'" in repr_str

    def test_provider_enabled_property(self, slack_settings):
        """Test enabled property."""
        provider = SlackPlatformProvider(settings=slack_settings)

        assert provider.enabled is True

    def test_provider_disabled_property(self, slack_settings_disabled):
        """Test enabled property when disabled."""
        provider = SlackPlatformProvider(settings=slack_settings_disabled)

        assert provider.enabled is False
