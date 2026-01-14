"""Unit tests for Microsoft Teams platform provider.

Tests verify Teams Bot Framework integration, HTTP mode operation, and
Adaptive Cards formatting.
"""

import pytest

from infrastructure.operations import OperationStatus
from infrastructure.platforms.capabilities.models import PlatformCapability
from infrastructure.platforms.formatters.teams import TeamsAdaptiveCardsFormatter
from infrastructure.platforms.providers.teams import TeamsPlatformProvider


# Test Fixtures


class MockTeamsSettings:
    """Mock Teams settings for testing."""

    def __init__(
        self,
        enabled=True,
        app_id="test-app-id",
        app_password="test-app-password",
        tenant_id="test-tenant-id",
    ):
        self.ENABLED = enabled
        self.APP_ID = app_id
        self.APP_PASSWORD = app_password
        self.TENANT_ID = tenant_id


@pytest.fixture
def mock_settings():
    """Provide mock Teams settings."""
    return MockTeamsSettings()


@pytest.fixture
def mock_formatter():
    """Provide mock Teams formatter."""
    return TeamsAdaptiveCardsFormatter()


# Initialization Tests


@pytest.mark.unit
class TestTeamsPlatformProviderInitialization:
    """Test Teams provider initialization."""

    def test_initialization(self, mock_settings):
        """Test provider initializes with correct attributes."""
        provider = TeamsPlatformProvider(settings=mock_settings)

        assert provider.name == "teams"
        assert provider.version == "1.0.0"
        assert provider._settings == mock_settings
        assert isinstance(provider._formatter, TeamsAdaptiveCardsFormatter)
        assert provider._app_initialized is False

    def test_initialization_with_custom_name_version(self, mock_settings):
        """Test provider initialization with custom name and version."""
        provider = TeamsPlatformProvider(
            settings=mock_settings, name="teams-prod", version="2.0.0"
        )

        assert provider.name == "teams-prod"
        assert provider.version == "2.0.0"

    def test_initialization_creates_default_formatter(self, mock_settings):
        """Test provider creates default formatter when none provided."""
        provider = TeamsPlatformProvider(settings=mock_settings)

        assert provider._formatter is not None
        assert isinstance(provider._formatter, TeamsAdaptiveCardsFormatter)

    def test_initialization_disabled_provider(self):
        """Test initialization with disabled provider."""
        settings = MockTeamsSettings(enabled=False)
        provider = TeamsPlatformProvider(settings=settings)

        assert provider.enabled is False

    def test_provider_properties(self, mock_settings):
        """Test provider property accessors."""
        provider = TeamsPlatformProvider(settings=mock_settings)

        assert provider.formatter is not None
        assert provider.settings is mock_settings
        assert provider.name == "teams"


# Capabilities Tests


@pytest.mark.unit
class TestGetCapabilities:
    """Test get_capabilities method."""

    def test_get_capabilities_returns_declaration(self, mock_settings):
        """Test that get_capabilities returns CapabilityDeclaration."""
        provider = TeamsPlatformProvider(settings=mock_settings)

        capabilities = provider.get_capabilities()

        assert capabilities is not None
        assert hasattr(capabilities, "capabilities")
        assert hasattr(capabilities, "metadata")

    def test_capabilities_include_commands(self, mock_settings):
        """Test that capabilities include COMMANDS."""
        provider = TeamsPlatformProvider(settings=mock_settings)

        capabilities = provider.get_capabilities()

        assert capabilities.supports(PlatformCapability.COMMANDS)

    def test_capabilities_include_views_modals(self, mock_settings):
        """Test that capabilities include VIEWS_MODALS."""
        provider = TeamsPlatformProvider(settings=mock_settings)

        capabilities = provider.get_capabilities()

        assert capabilities.supports(PlatformCapability.VIEWS_MODALS)

    def test_capabilities_include_interactive_cards(self, mock_settings):
        """Test that capabilities include INTERACTIVE_CARDS."""
        provider = TeamsPlatformProvider(settings=mock_settings)

        capabilities = provider.get_capabilities()

        assert capabilities.supports(PlatformCapability.INTERACTIVE_CARDS)

    def test_capabilities_include_file_sharing(self, mock_settings):
        """Test that capabilities include FILE_SHARING."""
        provider = TeamsPlatformProvider(settings=mock_settings)

        capabilities = provider.get_capabilities()

        assert capabilities.supports(PlatformCapability.FILE_SHARING)

    def test_capabilities_include_reactions(self, mock_settings):
        """Test that capabilities include REACTIONS."""
        provider = TeamsPlatformProvider(settings=mock_settings)

        capabilities = provider.get_capabilities()

        assert capabilities.supports(PlatformCapability.REACTIONS)

    def test_capabilities_metadata_includes_platform(self, mock_settings):
        """Test that capabilities metadata includes platform info."""
        provider = TeamsPlatformProvider(settings=mock_settings)

        capabilities = provider.get_capabilities()

        assert "platform" in capabilities.metadata
        assert capabilities.metadata["platform"] == "teams"
        assert capabilities.metadata["connection_mode"] == "http"


# Send Message Tests


@pytest.mark.unit
class TestSendMessage:
    """Test send_message method."""

    def test_send_message_success(self, mock_settings):
        """Test sending message successfully."""
        provider = TeamsPlatformProvider(settings=mock_settings)

        result = provider.send_message(
            channel="19:meeting_id@thread.v2", message={"text": "Test message"}
        )

        assert result.is_success
        assert result.status == OperationStatus.SUCCESS
        assert "channel" in result.data
        assert result.data["channel"] == "19:meeting_id@thread.v2"

    def test_send_message_with_adaptive_card(self, mock_settings):
        """Test sending message with Adaptive Card."""
        provider = TeamsPlatformProvider(settings=mock_settings)

        card_message = {
            "type": "message",
            "attachments": [
                {
                    "contentType": "application/vnd.microsoft.card.adaptive",
                    "content": {"type": "AdaptiveCard", "version": "1.4"},
                }
            ],
        }

        result = provider.send_message(
            channel="19:meeting_id@thread.v2", message=card_message
        )

        assert result.is_success
        assert "payload" in result.data
        assert "attachments" in result.data["payload"]

    def test_send_message_with_reply_to(self, mock_settings):
        """Test sending message as a reply."""
        provider = TeamsPlatformProvider(settings=mock_settings)

        result = provider.send_message(
            channel="19:meeting_id@thread.v2",
            message={"text": "Reply message"},
            thread_ts="1234567890",
        )

        assert result.is_success
        assert "replyToId" in result.data["payload"]
        assert result.data["payload"]["replyToId"] == "1234567890"

    def test_send_message_disabled_provider(self):
        """Test sending message when provider is disabled."""
        settings = MockTeamsSettings(enabled=False)
        provider = TeamsPlatformProvider(settings=settings)

        result = provider.send_message(
            channel="19:meeting_id@thread.v2", message={"text": "Test"}
        )

        assert not result.is_success
        assert result.status == OperationStatus.PERMANENT_ERROR
        assert result.error_code == "PROVIDER_DISABLED"

    def test_send_message_empty_message(self, mock_settings):
        """Test sending empty message returns error."""
        provider = TeamsPlatformProvider(settings=mock_settings)

        result = provider.send_message(channel="19:meeting_id@thread.v2", message={})

        assert not result.is_success
        assert result.status == OperationStatus.PERMANENT_ERROR
        assert result.error_code == "INVALID_MESSAGE"

    def test_send_message_none_message(self, mock_settings):
        """Test sending None message returns error."""
        provider = TeamsPlatformProvider(settings=mock_settings)

        result = provider.send_message(channel="19:meeting_id@thread.v2", message=None)

        assert not result.is_success
        assert result.error_code == "INVALID_MESSAGE"


# Format Response Tests


@pytest.mark.unit
class TestFormatResponse:
    """Test format_response method."""

    def test_format_response_success(self, mock_settings):
        """Test formatting a success response."""
        provider = TeamsPlatformProvider(settings=mock_settings)

        response = provider.format_response(data={"user_id": "123"})

        assert response["type"] == "message"
        assert "attachments" in response
        assert (
            response["attachments"][0]["contentType"]
            == "application/vnd.microsoft.card.adaptive"
        )

    def test_format_response_with_error(self, mock_settings):
        """Test formatting an error response."""
        provider = TeamsPlatformProvider(settings=mock_settings)

        response = provider.format_response(data={}, error="Operation failed")

        assert response["type"] == "message"
        assert "attachments" in response

    def test_format_response_empty_data(self, mock_settings):
        """Test formatting response with empty data."""
        provider = TeamsPlatformProvider(settings=mock_settings)

        response = provider.format_response(data={})

        assert response is not None
        assert response["type"] == "message"

    def test_format_response_uses_custom_formatter(self, mock_settings, mock_formatter):
        """Test format_response uses provided formatter."""
        provider = TeamsPlatformProvider(
            settings=mock_settings, formatter=mock_formatter
        )

        response = provider.format_response(data={"test": "data"})

        # Verify it used the formatter (returns Adaptive Card structure)
        assert "attachments" in response


# Initialize App Tests


@pytest.mark.unit
class TestInitializeApp:
    """Test initialize_app method."""

    def test_initialize_app_success(self, mock_settings):
        """Test successful app initialization."""
        provider = TeamsPlatformProvider(settings=mock_settings)

        result = provider.initialize_app()

        assert result.is_success
        assert result.status == OperationStatus.SUCCESS
        assert provider._app_initialized is True

    def test_initialize_app_disabled_provider(self):
        """Test initialize_app when provider is disabled."""
        settings = MockTeamsSettings(enabled=False)
        provider = TeamsPlatformProvider(settings=settings)

        result = provider.initialize_app()

        assert result.is_success
        assert "disabled" in result.message.lower()
        assert provider._app_initialized is False

    def test_initialize_app_missing_app_id(self, mock_settings):
        """Test initialize_app fails with missing APP_ID."""
        mock_settings.APP_ID = None
        provider = TeamsPlatformProvider(settings=mock_settings)

        result = provider.initialize_app()

        assert not result.is_success
        assert result.error_code == "MISSING_APP_ID"

    def test_initialize_app_missing_app_password(self, mock_settings):
        """Test initialize_app fails with missing APP_PASSWORD."""
        mock_settings.APP_PASSWORD = None
        provider = TeamsPlatformProvider(settings=mock_settings)

        result = provider.initialize_app()

        assert not result.is_success
        assert result.error_code == "MISSING_APP_PASSWORD"

    def test_initialize_app_all_credentials_present(self, mock_settings):
        """Test initialize_app succeeds with all credentials."""
        provider = TeamsPlatformProvider(settings=mock_settings)

        result = provider.initialize_app()

        assert result.is_success
        assert "connection_mode" in result.data
        assert result.data["connection_mode"] == "http"


# Integration Tests


@pytest.mark.unit
class TestProviderIntegration:
    """Test provider integration capabilities."""

    def test_supports_capability(self, mock_settings):
        """Test supports_capability() inherited from base class."""
        provider = TeamsPlatformProvider(settings=mock_settings)

        assert provider.supports_capability(PlatformCapability.COMMANDS)
        assert provider.supports_capability(PlatformCapability.VIEWS_MODALS)

    def test_repr(self, mock_settings):
        """Test __repr__ string representation."""
        provider = TeamsPlatformProvider(settings=mock_settings)

        repr_str = repr(provider)

        assert "TeamsPlatformProvider" in repr_str
        assert "name='teams'" in repr_str

    def test_provider_enabled_property(self, mock_settings):
        """Test enabled property."""
        provider = TeamsPlatformProvider(settings=mock_settings)

        assert provider.enabled is True

    def test_provider_disabled_property(self):
        """Test enabled property when disabled."""
        settings = MockTeamsSettings(enabled=False)
        provider = TeamsPlatformProvider(settings=settings)

        assert provider.enabled is False
