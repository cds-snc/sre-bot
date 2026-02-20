"""Unit tests for Microsoft Teams platform provider.

Tests verify Teams Bot Framework integration, HTTP mode operation, and
Adaptive Cards formatting.
"""

import pytest

from infrastructure.platforms.capabilities.models import PlatformCapability
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

    def test_capabilities_include_views_modals(self, teams_settings):
        """Test that capabilities include VIEWS_MODALS."""
        provider = TeamsPlatformProvider(settings=teams_settings)

        capabilities = provider.get_capabilities()

        assert capabilities.supports(PlatformCapability.VIEWS_MODALS)

    def test_capabilities_metadata_platform(self, teams_settings):
        """Test that capabilities metadata includes platform."""
        provider = TeamsPlatformProvider(settings=teams_settings)

        capabilities = provider.get_capabilities()

        assert "platform" in capabilities.metadata
        assert capabilities.metadata["platform"] == "teams"

    def test_capabilities_metadata_bot_framework(self, teams_settings):
        """Test that capabilities metadata includes bot framework info."""
        provider = TeamsPlatformProvider(settings=teams_settings)

        capabilities = provider.get_capabilities()

        assert "framework" in capabilities.metadata
        assert capabilities.metadata["framework"] == "botframework"
        assert "connection_mode" in capabilities.metadata
        assert capabilities.metadata["connection_mode"] == "http"


@pytest.mark.unit
class TestInitializeApp:
    """Test initialize_app() method."""

    def test_initialize_app_success(self, teams_settings):
        """Test successful app initialization."""
        provider = TeamsPlatformProvider(settings=teams_settings)

        result = provider.initialize_app()

        assert result.is_success
        assert result.data["initialized"] is True
        assert result.data["connection_mode"] == "http"

    def test_initialize_app_disabled_provider(self, teams_settings_disabled):
        """Test initialization when provider is disabled.

        Note: Provider returns success even when disabled; this is by design
        to avoid cascading errors in initialization chains.
        """
        provider = TeamsPlatformProvider(settings=teams_settings_disabled)

        result = provider.initialize_app()

        assert result.is_success
        assert "disabled" in result.message.lower()

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

    def test_initialize_app_tenant_id_not_validated(self):
        """Test that TENANT_ID is not validated in initialize_app.

        Teams provider only validates APP_ID and APP_PASSWORD.
        TENANT_ID validation (if needed) would occur elsewhere.
        """
        from tests.unit.infrastructure.platforms.providers.conftest import (
            MockTeamsSettings,
        )

        settings = MockTeamsSettings(tenant_id=None)
        provider = TeamsPlatformProvider(settings=settings)

        result = provider.initialize_app()

        # TENANT_ID is not validated, so this succeeds
        assert result.is_success
        assert result.data["initialized"] is True

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
        assert provider.supports_capability(PlatformCapability.INTERACTIVE_CARDS)

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
