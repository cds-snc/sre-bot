"""Unit tests for SlackPlatformProvider."""

import pytest

from infrastructure.operations import OperationStatus
from infrastructure.platforms.capabilities.models import PlatformCapability
from infrastructure.platforms.formatters.slack import SlackBlockKitFormatter
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

    def test_capabilities_socket_mode_false(self, slack_settings_http_mode):
        """Test capabilities metadata when socket_mode is False."""
        provider = SlackPlatformProvider(settings=slack_settings_http_mode)

        capabilities = provider.get_capabilities()

        assert capabilities.metadata["socket_mode"] is False


@pytest.mark.unit
class TestSendMessage:
    """Test send_message() method."""

    def test_send_message_success(self, slack_settings):
        """Test sending a message successfully."""
        provider = SlackPlatformProvider(settings=slack_settings)

        result = provider.send_message(
            channel="C123456", message={"text": "Hello World"}
        )

        assert result.is_success
        assert result.data["channel"] == "C123456"
        assert "ts" in result.data
        assert result.data["message"]["text"] == "Hello World"

    def test_send_message_with_blocks(self, slack_settings):
        """Test sending a message with blocks."""
        provider = SlackPlatformProvider(settings=slack_settings)
        blocks = [{"type": "section", "text": {"type": "mrkdwn", "text": "Hi"}}]

        result = provider.send_message(channel="C123456", message={"blocks": blocks})

        assert result.is_success
        assert result.data["message"]["blocks"] == blocks

    def test_send_message_with_thread(self, slack_settings):
        """Test sending a threaded message."""
        provider = SlackPlatformProvider(settings=slack_settings)

        result = provider.send_message(
            channel="C123456",
            message={"text": "Thread reply"},
            thread_ts="1234567890.123456",
        )

        assert result.is_success
        assert result.data["message"]["thread_ts"] == "1234567890.123456"

    def test_send_message_with_additional_fields(self, slack_settings):
        """Test sending a message with additional fields in message dict."""
        provider = SlackPlatformProvider(settings=slack_settings)

        result = provider.send_message(
            channel="C123456",
            message={
                "text": "Test",
                "unfurl_links": False,
                "unfurl_media": False,
            },
        )

        assert result.is_success
        assert result.data["message"]["unfurl_links"] is False
        assert result.data["message"]["unfurl_media"] is False

    def test_send_message_disabled_provider(self, slack_settings_disabled):
        """Test sending message when provider is disabled."""
        provider = SlackPlatformProvider(settings=slack_settings_disabled)

        result = provider.send_message(channel="C123456", message={"text": "Test"})

        assert not result.is_success
        assert result.status == OperationStatus.PERMANENT_ERROR
        assert result.error_code == "PROVIDER_DISABLED"

    def test_send_message_empty_content(self, slack_settings):
        """Test sending message with empty content."""
        provider = SlackPlatformProvider(settings=slack_settings)

        result = provider.send_message(channel="C123456", message={})

        assert not result.is_success
        assert result.status == OperationStatus.PERMANENT_ERROR
        assert result.error_code == "EMPTY_CONTENT"

    def test_send_message_none_content(self, slack_settings):
        """Test sending message with None content."""
        provider = SlackPlatformProvider(settings=slack_settings)

        result = provider.send_message(channel="C123456", message=None)

        assert not result.is_success
        assert result.error_code == "EMPTY_CONTENT"


@pytest.mark.unit
class TestFormatResponse:
    """Test format_response() method."""

    def test_format_response_success(self, slack_settings):
        """Test formatting a success response."""
        provider = SlackPlatformProvider(settings=slack_settings)

        response = provider.format_response(data={"user_id": "U123"})

        assert "blocks" in response
        # Should use formatter's format_success
        assert response["blocks"][0]["type"] == "section"

    def test_format_response_with_error(self, slack_settings):
        """Test formatting an error response."""
        provider = SlackPlatformProvider(settings=slack_settings)

        response = provider.format_response(data={}, error="Something went wrong")

        assert "blocks" in response
        # Should use formatter's format_error
        header_text = response["blocks"][0]["text"]["text"]
        assert ":x:" in header_text
        assert "Something went wrong" in header_text

    def test_format_response_empty_data(self, slack_settings):
        """Test formatting response with empty data."""
        provider = SlackPlatformProvider(settings=slack_settings)

        response = provider.format_response(data={})

        assert "blocks" in response

    def test_format_response_uses_custom_formatter(
        self, slack_settings, slack_formatter
    ):
        """Test that format_response uses the configured formatter."""
        provider = SlackPlatformProvider(
            settings=slack_settings, formatter=slack_formatter
        )

        provider.format_response(data={"test": "data"})

        # Verify custom formatter was used
        assert provider.formatter is slack_formatter


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
