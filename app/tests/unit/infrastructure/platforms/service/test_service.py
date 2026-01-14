"""Tests for PlatformService."""

from unittest.mock import Mock

import pytest

from infrastructure.configuration import Settings
from infrastructure.operations import OperationResult
from infrastructure.platforms.capabilities.models import PlatformCapability
from infrastructure.platforms.exceptions import (
    CapabilityNotSupportedError,
    ProviderNotFoundError,
)
from infrastructure.platforms.providers.base import BasePlatformProvider
from infrastructure.platforms.service import PlatformService


class MockProvider(BasePlatformProvider):
    """Mock provider for testing."""

    def __init__(self, name="mock", version="1.0.0", enabled=True):
        from infrastructure.platforms.capabilities.models import (
            create_capability_declaration,
        )

        self._name = name
        self._version = version
        self._enabled = enabled
        self._capabilities = create_capability_declaration(
            name,  # platform_id as first positional arg
            PlatformCapability.COMMANDS,
            PlatformCapability.INTERACTIVE_CARDS,
            metadata={"platform": name},
        )

    @property
    def name(self):
        return self._name

    @property
    def version(self):
        return self._version

    @property
    def enabled(self):
        return self._enabled

    def get_capabilities(self):
        return self._capabilities

    def send_message(self, channel, message, **kwargs):
        if not self.enabled:
            return OperationResult.permanent_error(
                message="Provider disabled", error_code="DISABLED"
            )
        return OperationResult.success(
            data={"message_id": "123"}, message="Message sent"
        )

    def format_response(self, data, message_type="success"):
        """Format response based on message_type."""
        if message_type == "error":
            return {"type": "error", "message": data.get("error", "Unknown error")}
        return {"type": "success", "data": data}

    def initialize_app(self):
        if not self.enabled:
            return OperationResult.permanent_error(
                message="Provider disabled", error_code="DISABLED"
            )
        return OperationResult.success(message="Initialized")


@pytest.fixture
def mock_settings():
    """Create mock settings."""
    return Mock(spec=Settings)


@pytest.fixture
def service(mock_settings):
    """Create PlatformService instance."""
    return PlatformService(settings=mock_settings)


@pytest.mark.unit
class TestPlatformServiceInitialization:
    """Test PlatformService initialization."""

    def test_initialization(self, mock_settings):
        """Test service initializes with settings."""
        service = PlatformService(settings=mock_settings)

        assert service._settings is mock_settings
        assert service._registry is not None

    def test_registry_property(self, service):
        """Test registry property accessor."""
        registry = service.registry

        assert registry is service._registry


@pytest.mark.unit
class TestLoadProviders:
    """Test load_providers method."""

    def test_load_providers_returns_registered_providers(self, service):
        """Test that load_providers returns registered providers as dict."""
        # Register mock providers directly
        mock_slack = MockProvider(name="slack")
        mock_teams = MockProvider(name="teams")
        service._registry.register_provider(mock_slack)
        service._registry.register_provider(mock_teams)

        # Call load_providers (it will try to import but won't find new modules)
        # We're testing that it returns registered providers as a dict
        providers = service.load_providers()

        # Verify returns dict keyed by platform_id
        assert isinstance(providers, dict)
        assert "slack" in providers
        assert "teams" in providers
        assert providers["slack"] is mock_slack
        assert providers["teams"] is mock_teams
        assert providers["teams"] is mock_teams


@pytest.mark.unit
class TestGetProvider:
    """Test get_provider method."""

    def test_get_provider_returns_registered_provider(self, service):
        """Test getting registered provider."""
        mock_provider = MockProvider(name="slack")
        service._registry.register_provider(mock_provider)

        provider = service.get_provider("slack")

        assert provider is mock_provider

    def test_get_provider_raises_on_missing(self, service):
        """Test get_provider raises ProviderNotFoundError."""
        with pytest.raises(ProviderNotFoundError):
            service.get_provider("nonexistent")


@pytest.mark.unit
class TestGetEnabledProviders:
    """Test get_enabled_providers method."""

    def test_get_enabled_providers_filters_disabled(self, service):
        """Test that only enabled providers are returned."""
        enabled1 = MockProvider(name="slack", enabled=True)
        disabled = MockProvider(name="teams", enabled=False)
        enabled2 = MockProvider(name="discord", enabled=True)

        service._registry.register_provider(enabled1)
        service._registry.register_provider(disabled)
        service._registry.register_provider(enabled2)

        enabled = service.get_enabled_providers()

        assert len(enabled) == 2
        assert enabled1 in enabled
        assert enabled2 in enabled
        assert disabled not in enabled


@pytest.mark.unit
class TestSend:
    """Test send method."""

    def test_send_success(self, service):
        """Test sending message successfully."""
        mock_provider = MockProvider(name="slack")
        service._registry.register_provider(mock_provider)

        result = service.send(
            platform="slack", channel="C123456", message={"text": "Hello"}
        )

        assert result.is_success
        assert result.data["message_id"] == "123"

    def test_send_provider_not_found(self, service):
        """Test send with nonexistent provider."""
        result = service.send(
            platform="nonexistent", channel="C123456", message={"text": "Hello"}
        )

        assert not result.is_success
        assert result.error_code == "PROVIDER_NOT_FOUND"

    def test_send_provider_disabled(self, service):
        """Test send with disabled provider."""
        disabled = MockProvider(name="slack", enabled=False)
        service._registry.register_provider(disabled)

        result = service.send(
            platform="slack", channel="C123456", message={"text": "Hello"}
        )

        assert not result.is_success
        assert result.error_code == "PROVIDER_DISABLED"


@pytest.mark.unit
class TestFormatResponse:
    """Test format_response method."""

    def test_format_response_success(self, service):
        """Test formatting success response."""
        mock_provider = MockProvider(name="slack")
        service._registry.register_provider(mock_provider)

        response = service.format_response(platform="slack", data={"user_id": "U123"})

        assert response["type"] == "success"
        assert response["data"]["user_id"] == "U123"

    def test_format_response_error(self, service):
        """Test formatting error response."""
        mock_provider = MockProvider(name="slack")
        service._registry.register_provider(mock_provider)

        response = service.format_response(platform="slack", error="Something failed")

        assert response["type"] == "error"
        assert response["message"] == "Something failed"

    def test_format_response_provider_not_found(self, service):
        """Test format_response with nonexistent provider."""
        with pytest.raises(ProviderNotFoundError):
            service.format_response(platform="nonexistent", data={})


@pytest.mark.unit
class TestSupportsCapability:
    """Test supports_capability method."""

    def test_supports_capability_true(self, service):
        """Test checking supported capability."""
        mock_provider = MockProvider(name="slack")
        service._registry.register_provider(mock_provider)

        supports = service.supports_capability("slack", PlatformCapability.COMMANDS)

        assert supports is True

    def test_supports_capability_false(self, service):
        """Test checking unsupported capability."""
        mock_provider = MockProvider(name="slack")
        service._registry.register_provider(mock_provider)

        supports = service.supports_capability("slack", PlatformCapability.THREADS)

        assert supports is False

    def test_supports_capability_provider_not_found(self, service):
        """Test supports_capability with nonexistent provider."""
        supports = service.supports_capability(
            "nonexistent", PlatformCapability.COMMANDS
        )

        assert supports is False


@pytest.mark.unit
class TestRequireCapability:
    """Test require_capability method."""

    def test_require_capability_supported(self, service):
        """Test requiring a supported capability."""
        mock_provider = MockProvider(name="slack")
        service._registry.register_provider(mock_provider)

        # Should not raise
        service.require_capability("slack", PlatformCapability.COMMANDS)

    def test_require_capability_not_supported(self, service):
        """Test requiring an unsupported capability."""
        mock_provider = MockProvider(name="slack")
        service._registry.register_provider(mock_provider)

        with pytest.raises(CapabilityNotSupportedError):
            service.require_capability("slack", PlatformCapability.THREADS)

    def test_require_capability_provider_not_found(self, service):
        """Test require_capability with nonexistent provider."""
        with pytest.raises(ProviderNotFoundError):
            service.require_capability("nonexistent", PlatformCapability.COMMANDS)


@pytest.mark.unit
class TestInitializeProvider:
    """Test initialize_provider method."""

    def test_initialize_provider_success(self, service):
        """Test initializing provider successfully."""
        mock_provider = MockProvider(name="slack")
        service._registry.register_provider(mock_provider)

        result = service.initialize_provider("slack")

        assert result.is_success

    def test_initialize_provider_disabled(self, service):
        """Test initializing disabled provider."""
        disabled = MockProvider(name="slack", enabled=False)
        service._registry.register_provider(disabled)

        result = service.initialize_provider("slack")

        assert not result.is_success
        assert result.error_code == "PROVIDER_DISABLED"

    def test_initialize_provider_not_found(self, service):
        """Test initializing nonexistent provider."""
        with pytest.raises(ProviderNotFoundError):
            service.initialize_provider("nonexistent")


@pytest.mark.unit
class TestInitializeAllProviders:
    """Test initialize_all_providers method."""

    def test_initialize_all_providers_success(self, service):
        """Test initializing all enabled providers."""
        enabled1 = MockProvider(name="slack", enabled=True)
        enabled2 = MockProvider(name="teams", enabled=True)
        disabled = MockProvider(name="discord", enabled=False)

        service._registry.register_provider(enabled1)
        service._registry.register_provider(enabled2)
        service._registry.register_provider(disabled)

        results = service.initialize_all_providers()

        # Should initialize enabled providers only
        assert "slack" in results
        assert "teams" in results
        assert results["slack"].is_success
        assert results["teams"].is_success

    def test_initialize_all_providers_empty(self, service):
        """Test initializing when no providers enabled."""
        results = service.initialize_all_providers()

        assert len(results) == 0


@pytest.mark.unit
class TestHealthCheck:
    """Test health_check method."""

    def test_health_check_enabled_provider(self, service):
        """Test health check on enabled provider."""
        mock_provider = MockProvider(name="slack")
        service._registry.register_provider(mock_provider)

        result = service.health_check("slack")

        assert result.is_success
        assert result.data["platform"] == "slack"
        assert result.data["enabled"] is True

    def test_health_check_disabled_provider(self, service):
        """Test health check on disabled provider."""
        disabled = MockProvider(name="slack", enabled=False)
        service._registry.register_provider(disabled)

        result = service.health_check("slack")

        assert not result.is_success
        assert result.error_code == "PROVIDER_DISABLED"

    def test_health_check_provider_not_found(self, service):
        """Test health check on nonexistent provider."""
        with pytest.raises(ProviderNotFoundError):
            service.health_check("nonexistent")


@pytest.mark.unit
class TestGetPlatformInfo:
    """Test get_platform_info method."""

    def test_get_platform_info(self, service):
        """Test getting platform information."""
        mock_provider = MockProvider(name="slack", version="2.5.0")
        service._registry.register_provider(mock_provider)

        info = service.get_platform_info("slack")

        assert info["name"] == "slack"
        assert info["version"] == "2.5.0"
        assert info["enabled"] is True
        assert PlatformCapability.COMMANDS.value in info["capabilities"]
        assert info["metadata"]["platform"] == "slack"

    def test_get_platform_info_provider_not_found(self, service):
        """Test get_platform_info with nonexistent provider."""
        with pytest.raises(ProviderNotFoundError):
            service.get_platform_info("nonexistent")
