"""Unit tests for Microsoft Teams platform provider.

Tests verify Teams Bot Framework integration, HTTP mode operation, and
Adaptive Cards formatting.
"""

import pytest

from infrastructure.operations import OperationStatus
from infrastructure.platforms.capabilities.models import PlatformCapability
from infrastructure.platforms.formatters.teams import TeamsAdaptiveCardsFormatter
from infrastructure.platforms.providers.teams import TeamsPlatformProvider


@pytest.mark.unit
class TestTeamsPlatformProviderInitialization:
    """Test Teams provider initialization."""

    def test_initialization(self, teams_settings):
        """Test provider initializes with correct attributes."""
        provider = TeamsPlatformProvider(settings=teams_settings)

        assert provider.name == "teams"
        assert provider.version == "1.0.0"
        assert provider._settings == teams_settings
        assert isinstance(provider._formatter, TeamsAdaptiveCardsFormatter)

    def test_initialization_with_custom_formatter(
        self, teams_settings, teams_formatter
    ):
        """Test initialization with custom formatter."""
        provider = TeamsPlatformProvider(
            settings=teams_settings, formatter=teams_formatter
        )

        assert provider._formatter is teams_formatter

    def test_initialization_disabled_provider(self, teams_settings_disabled):
        """Test initialization with disabled provider."""
        provider = TeamsPlatformProvider(settings=teams_settings_disabled)

        assert provider.enabled is False

    def test_initialization_custom_name_version(self, teams_settings):
        """Test initialization with custom name and version."""
        provider = TeamsPlatformProvider(
            settings=teams_settings, name="custom-teams", version="2.0.0"
        )

        assert provider.name == "custom-teams"
        assert provider.version == "2.0.0"


@pytest.mark.unit
class TestGetCapabilities:
    """Test get_capabilities() method."""

    def test_get_capabilities_returns_declaration(self, teams_settings):
        """Test that get_capabilities returns CapabilityDeclaration."""
        provider = TeamsPlatformProvider(settings=teams_settings)

        capabilities = provider.get_capabilities()

        assert capabilities is not None
        assert hasattr(capabilities, "capabilities")
        assert hasattr(capabilities, "metadata")

    def test_capabilities_include_messaging(self, teams_settings):
        """Test that capabilities include MESSAGING."""
        provider = TeamsPlatformProvider(settings=teams_settings)

        capabilities = provider.get_capabilities()

        assert capabilities.supports(PlatformCapability.MESSAGING)

    def test_capabilities_include_commands(self, teams_settings):
        """Test that capabilities include COMMANDS."""
        provider = TeamsPlatformProvider(settings=teams_settings)

        capabilities = provider.get_capabilities()

        assert capabilities.supports(PlatformCapability.COMMANDS)

    def test_capabilities_include_interactive_cards(self, teams_settings):
        """Test that capabilities include INTERACTIVE_CARDS."""
        provider = TeamsPlatformProvider(settings=teams_settings)

        capabilities = provider.get_capabilities()

        assert capabilities.supports(PlatformCapability.INTERACTIVE_CARDS)

    def test_capabilities_metadata_platform(self, teams_settings):
        """Test that capabilities metadata includes platform."""
        provider = TeamsPlatformProvider(settings=teams_settings)

        capabilities = provider.get_capabilities()

        assert "platform" in capabilities.metadata
        assert capabilities.metadata["platform"] == "teams"

    def test_capabilities_metadata_bot_framework_version(self, teams_settings):
        """Test that capabilities metadata includes bot_framework_version."""
        provider = TeamsPlatformProvider(settings=teams_settings)

        capabilities = provider.get_capabilities()

        assert "bot_framework_version" in capabilities.metadata
        assert capabilities.metadata["bot_framework_version"] == "4.x"


@pytest.mark.unit
class TestSendMessage:
    """Test send_message() method."""

    def test_send_message_success(self, teams_settings):
        """Test sending a message successfully."""
        provider = TeamsPlatformProvider(settings=teams_settings)

        result = provider.send_message(
            channel="19:abcd@thread.tacv2", message={"text": "Hello Teams"}
        )

        assert result.is_success
        assert result.data["channel"] == "19:abcd@thread.tacv2"
        assert "message_id" in result.data
        assert result.data["message"]["text"] == "Hello Teams"

    def test_send_message_with_adaptive_card(self, teams_settings):
        """Test sending a message with Adaptive Card."""
        provider = TeamsPlatformProvider(settings=teams_settings)
        card = {
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "type": "AdaptiveCard",
            "version": "1.4",
            "body": [{"type": "TextBlock", "text": "Hello"}],
        }

        result = provider.send_message(
            channel="19:abcd@thread.tacv2",
            message={
                "attachments": [
                    {
                        "contentType": "application/vnd.microsoft.card.adaptive",
                        "contentUrl": None,
                        "content": card,
                    }
                ]
            },
        )

        assert result.is_success

    def test_send_message_disabled_provider(self, teams_settings_disabled):
        """Test sending message when provider is disabled."""
        provider = TeamsPlatformProvider(settings=teams_settings_disabled)

        result = provider.send_message(
            channel="19:abcd@thread.tacv2", message={"text": "Test"}
        )

        assert not result.is_success
        assert result.status == OperationStatus.PERMANENT_ERROR
        assert result.error_code == "PROVIDER_DISABLED"

    def test_send_message_empty_content(self, teams_settings):
        """Test sending message with empty content."""
        provider = TeamsPlatformProvider(settings=teams_settings)

        result = provider.send_message(channel="19:abcd@thread.tacv2", message={})

        assert not result.is_success
        assert result.error_code == "EMPTY_CONTENT"

    def test_send_message_none_content(self, teams_settings):
        """Test sending message with None content."""
        provider = TeamsPlatformProvider(settings=teams_settings)

        result = provider.send_message(channel="19:abcd@thread.tacv2", message=None)

        assert not result.is_success
        assert result.error_code == "EMPTY_CONTENT"


@pytest.mark.unit
class TestFormatResponse:
    """Test format_response() method."""

    def test_format_response_success(self, teams_settings):
        """Test formatting a success response."""
        provider = TeamsPlatformProvider(settings=teams_settings)

        response = provider.format_response(data={"user_id": "U123"})

        assert (
            "body" in response[0] if isinstance(response, list) else "body" in response
        )

    def test_format_response_with_error(self, teams_settings):
        """Test formatting an error response."""
        provider = TeamsPlatformProvider(settings=teams_settings)

        response = provider.format_response(data={}, error="Something went wrong")

        assert response is not None

    def test_format_response_empty_data(self, teams_settings):
        """Test formatting response with empty data."""
        provider = TeamsPlatformProvider(settings=teams_settings)

        response = provider.format_response(data={})

        assert response is not None

    def test_format_response_uses_custom_formatter(
        self, teams_settings, teams_formatter
    ):
        """Test that format_response uses the configured formatter."""
        provider = TeamsPlatformProvider(
            settings=teams_settings, formatter=teams_formatter
        )

        provider.format_response(data={"test": "data"})

        assert provider._formatter is teams_formatter


@pytest.mark.unit
class TestInitializeApp:
    """Test initialize_app() method."""

    def test_initialize_app_success(self, teams_settings):
        """Test successful app initialization."""
        provider = TeamsPlatformProvider(settings=teams_settings)

        result = provider.initialize_app()

        assert result.is_success
        assert result.data["initialized"] is True
        assert result.data["app_id"] == "test-app-id"

    def test_initialize_app_disabled_provider(self, teams_settings_disabled):
        """Test initialization when provider is disabled."""
        provider = TeamsPlatformProvider(settings=teams_settings_disabled)

        result = provider.initialize_app()

        assert not result.is_success
        assert result.status == OperationStatus.PERMANENT_ERROR
        assert result.error_code == "PROVIDER_DISABLED"

    def test_initialize_app_missing_app_id(self):
        """Test initialization with missing APP_ID."""
        from tests.unit.infrastructure.platforms.providers.conftest import (
            MockTeamsSettings,
        )

        settings = MockTeamsSettings(app_id=None)
        provider = TeamsPlatformProvider(settings=settings)

        result = provider.initialize_app()

        assert not result.is_success
        assert result.error_code == "MISSING_APP_ID"

    def test_initialize_app_missing_app_password(self):
        """Test initialization with missing APP_PASSWORD."""
        from tests.unit.infrastructure.platforms.providers.conftest import (
            MockTeamsSettings,
        )

        settings = MockTeamsSettings(app_password=None)
        provider = TeamsPlatformProvider(settings=settings)

        result = provider.initialize_app()

        assert not result.is_success
        assert result.error_code == "MISSING_APP_PASSWORD"

    def test_initialize_app_missing_tenant_id(self):
        """Test initialization with missing TENANT_ID."""
        from tests.unit.infrastructure.platforms.providers.conftest import (
            MockTeamsSettings,
        )

        settings = MockTeamsSettings(tenant_id=None)
        provider = TeamsPlatformProvider(settings=settings)

        result = provider.initialize_app()

        assert not result.is_success
        assert result.error_code == "MISSING_TENANT_ID"

    def test_initialize_app_all_credentials_present(self, teams_settings):
        """Test initialization with all required credentials."""
        provider = TeamsPlatformProvider(settings=teams_settings)

        result = provider.initialize_app()

        assert result.is_success


@pytest.mark.unit
class TestProviderIntegration:
    """Test provider integration with base class."""

    def test_supports_capability(self, teams_settings):
        """Test supports_capability() inherited from base class."""
        provider = TeamsPlatformProvider(settings=teams_settings)

        assert provider.supports_capability(PlatformCapability.COMMANDS)
        assert provider.supports_capability(PlatformCapability.MESSAGING)

    def test_repr(self, teams_settings):
        """Test __repr__ string representation."""
        provider = TeamsPlatformProvider(settings=teams_settings)

        repr_str = repr(provider)

        assert "TeamsPlatformProvider" in repr_str
        assert "name='teams'" in repr_str

    def test_provider_enabled_property(self, teams_settings):
        """Test enabled property."""
        provider = TeamsPlatformProvider(settings=teams_settings)

        assert provider.enabled is True

    def test_provider_disabled_property(self, teams_settings_disabled):
        """Test enabled property when disabled."""
        provider = TeamsPlatformProvider(settings=teams_settings_disabled)

        assert provider.enabled is False
