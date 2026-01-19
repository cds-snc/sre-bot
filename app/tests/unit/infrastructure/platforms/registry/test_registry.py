"""Unit tests for PlatformProviderRegistry."""

import pytest
import threading
import time
from typing import Any, Dict, Optional

from infrastructure.operations import OperationResult
from infrastructure.platforms.capabilities.models import (
    CapabilityDeclaration,
    PlatformCapability,
    PLATFORM_SLACK,
    PLATFORM_TEAMS,
    PLATFORM_DISCORD,
    create_capability_declaration,
)
from infrastructure.platforms.providers.base import BasePlatformProvider
from infrastructure.platforms.registry.registry import (
    PlatformProviderRegistry,
    get_platform_registry,
)


class MockPlatformProvider(BasePlatformProvider):
    """Mock provider for testing."""

    def __init__(
        self,
        platform_id: str,
        name: str = "Mock Provider",
        capabilities: Optional[list] = None,
    ):
        super().__init__(name=name)
        self._platform_id = platform_id
        self._capabilities = capabilities or [PlatformCapability.COMMANDS]

    def get_capabilities(self) -> CapabilityDeclaration:
        return create_capability_declaration(
            self._platform_id,
            *self._capabilities,
        )

    def send_message(
        self,
        channel: str,
        message: Dict[str, Any],
        thread_ts: Optional[str] = None,
    ) -> OperationResult:
        return OperationResult.success(data={"channel": channel})

    def format_response(
        self,
        data: Dict[str, Any],
        message_type: str = "success",
    ) -> Dict[str, Any]:
        return {"type": message_type, "data": data}

    def generate_help(
        self,
        locale: str = "en-US",
        root_command: Optional[str] = None,
    ) -> str:
        return "Mock help"

    def generate_command_help(
        self,
        command_name: str,
        locale: str = "en-US",
    ) -> str:
        return f"Help for {command_name}"


@pytest.fixture
def registry():
    """Create a fresh registry for each test."""
    reg = PlatformProviderRegistry()
    yield reg
    reg.clear()


@pytest.mark.unit
class TestPlatformProviderRegistry:
    """Test PlatformProviderRegistry class."""

    def test_registry_initialization(self, registry):
        """Test registry initializes empty."""
        assert registry.count() == 0
        assert registry.list_providers() == []

    def test_register_provider(self, registry):
        """Test registering a provider."""
        provider = MockPlatformProvider(PLATFORM_SLACK, name="Slack Provider")

        registry.register_provider(provider)

        assert registry.count() == 1
        assert registry.has_provider(PLATFORM_SLACK) is True

    def test_register_multiple_providers(self, registry):
        """Test registering multiple providers."""
        slack_provider = MockPlatformProvider(PLATFORM_SLACK, name="Slack")
        teams_provider = MockPlatformProvider(PLATFORM_TEAMS, name="Teams")
        discord_provider = MockPlatformProvider(PLATFORM_DISCORD, name="Discord")

        registry.register_provider(slack_provider)
        registry.register_provider(teams_provider)
        registry.register_provider(discord_provider)

        assert registry.count() == 3
        assert registry.has_provider(PLATFORM_SLACK) is True
        assert registry.has_provider(PLATFORM_TEAMS) is True
        assert registry.has_provider(PLATFORM_DISCORD) is True

    def test_register_duplicate_raises_error(self, registry):
        """Test registering duplicate platform_id raises ValueError."""
        provider1 = MockPlatformProvider(PLATFORM_SLACK, name="Provider 1")
        provider2 = MockPlatformProvider(PLATFORM_SLACK, name="Provider 2")

        registry.register_provider(provider1)

        with pytest.raises(ValueError) as exc_info:
            registry.register_provider(provider2)

        assert "already registered" in str(exc_info.value)
        assert PLATFORM_SLACK in str(exc_info.value)
        assert registry.count() == 1  # Only first provider registered

    def test_get_provider_success(self, registry):
        """Test retrieving a registered provider."""
        provider = MockPlatformProvider(PLATFORM_SLACK, name="Slack Provider")
        registry.register_provider(provider)

        retrieved = registry.get_provider(PLATFORM_SLACK)

        assert retrieved is not None
        assert retrieved.name == "Slack Provider"
        assert retrieved.get_capabilities().platform_id == PLATFORM_SLACK

    def test_get_provider_not_found(self, registry):
        """Test retrieving non-existent provider returns None."""
        result = registry.get_provider("nonexistent")

        assert result is None

    def test_unregister_provider(self, registry):
        """Test unregistering a provider."""
        provider = MockPlatformProvider(PLATFORM_SLACK, name="Slack")
        registry.register_provider(provider)

        assert registry.count() == 1

        registry.unregister_provider(PLATFORM_SLACK)

        assert registry.count() == 0
        assert registry.has_provider(PLATFORM_SLACK) is False

    def test_unregister_nonexistent_raises_error(self, registry):
        """Test unregistering non-existent provider raises KeyError."""
        with pytest.raises(KeyError) as exc_info:
            registry.unregister_provider("nonexistent")

        assert "No provider" in str(exc_info.value)
        assert "nonexistent" in str(exc_info.value)

    def test_list_providers(self, registry):
        """Test listing all providers."""
        slack = MockPlatformProvider(PLATFORM_SLACK, name="Slack")
        teams = MockPlatformProvider(PLATFORM_TEAMS, name="Teams")

        registry.register_provider(slack)
        registry.register_provider(teams)

        providers = registry.list_providers()

        assert len(providers) == 2
        provider_names = [p.name for p in providers]
        assert "Slack" in provider_names
        assert "Teams" in provider_names

    def test_list_providers_empty(self, registry):
        """Test listing providers when none registered."""
        providers = registry.list_providers()

        assert providers == []

    def test_get_providers_by_capability(self, registry):
        """Test filtering providers by capability."""
        slack = MockPlatformProvider(
            PLATFORM_SLACK,
            name="Slack",
            capabilities=[
                PlatformCapability.COMMANDS,
                PlatformCapability.VIEWS_MODALS,
            ],
        )
        teams = MockPlatformProvider(
            PLATFORM_TEAMS,
            name="Teams",
            capabilities=[PlatformCapability.COMMANDS],
        )
        discord = MockPlatformProvider(
            PLATFORM_DISCORD,
            name="Discord",
            capabilities=[PlatformCapability.MESSAGING],
        )

        registry.register_provider(slack)
        registry.register_provider(teams)
        registry.register_provider(discord)

        # Get providers that support COMMANDS
        command_providers = registry.get_providers_by_capability(
            PlatformCapability.COMMANDS
        )
        assert len(command_providers) == 2
        names = [p.name for p in command_providers]
        assert "Slack" in names
        assert "Teams" in names

        # Get providers that support VIEWS_MODALS
        modal_providers = registry.get_providers_by_capability(
            PlatformCapability.VIEWS_MODALS
        )
        assert len(modal_providers) == 1
        assert modal_providers[0].name == "Slack"

        # Get providers that support MESSAGING
        messaging_providers = registry.get_providers_by_capability(
            PlatformCapability.MESSAGING
        )
        assert len(messaging_providers) == 1
        assert messaging_providers[0].name == "Discord"

    def test_get_providers_by_capability_none_match(self, registry):
        """Test filtering when no providers match capability."""
        provider = MockPlatformProvider(
            PLATFORM_SLACK,
            capabilities=[PlatformCapability.COMMANDS],
        )
        registry.register_provider(provider)

        # No providers support WORKFLOWS
        workflow_providers = registry.get_providers_by_capability(
            PlatformCapability.WORKFLOWS
        )

        assert workflow_providers == []

    def test_clear(self, registry):
        """Test clearing all providers."""
        registry.register_provider(MockPlatformProvider(PLATFORM_SLACK))
        registry.register_provider(MockPlatformProvider(PLATFORM_TEAMS))

        assert registry.count() == 2

        registry.clear()

        assert registry.count() == 0
        assert registry.list_providers() == []

    def test_has_provider(self, registry):
        """Test checking if provider exists."""
        provider = MockPlatformProvider(PLATFORM_SLACK)
        registry.register_provider(provider)

        assert registry.has_provider(PLATFORM_SLACK) is True
        assert registry.has_provider(PLATFORM_TEAMS) is False


@pytest.mark.unit
class TestRegistryThreadSafety:
    """Test thread safety of the registry."""

    def test_concurrent_registration(self, registry):
        """Test concurrent provider registration is thread-safe."""
        num_threads = 10
        providers_per_thread = 5
        errors = []

        def register_providers(thread_id):
            try:
                for i in range(providers_per_thread):
                    platform_id = f"platform_{thread_id}_{i}"
                    provider = MockPlatformProvider(platform_id, name=platform_id)
                    registry.register_provider(provider)
            except Exception as e:
                errors.append(e)

        threads = []
        for i in range(num_threads):
            thread = threading.Thread(target=register_providers, args=(i,))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        # All providers should be registered without errors
        assert len(errors) == 0
        assert registry.count() == num_threads * providers_per_thread

    def test_concurrent_read_write(self, registry):
        """Test concurrent reads and writes are thread-safe."""
        # Register initial providers
        for i in range(5):
            provider = MockPlatformProvider(f"platform_{i}", name=f"Provider {i}")
            registry.register_provider(provider)

        read_results = []
        errors = []

        def read_providers():
            try:
                for _ in range(100):
                    providers = registry.list_providers()
                    read_results.append(len(providers))
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)

        def write_providers():
            try:
                for i in range(5, 10):
                    provider = MockPlatformProvider(
                        f"platform_{i}", name=f"Provider {i}"
                    )
                    registry.register_provider(provider)
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)

        read_thread = threading.Thread(target=read_providers)
        write_thread = threading.Thread(target=write_providers)

        read_thread.start()
        write_thread.start()

        read_thread.join()
        write_thread.join()

        # Should complete without errors
        assert len(errors) == 0
        # Final count should be 10
        assert registry.count() == 10


@pytest.mark.unit
class TestGetPlatformRegistry:
    """Test global registry singleton."""

    def test_get_platform_registry_returns_singleton(self):
        """Test that get_platform_registry returns same instance."""
        registry1 = get_platform_registry()
        registry2 = get_platform_registry()

        assert registry1 is registry2

    def test_singleton_persists_across_calls(self):
        """Test that singleton maintains state across calls."""
        registry = get_platform_registry()
        registry.clear()  # Start fresh

        # Register provider via first reference
        provider = MockPlatformProvider(PLATFORM_SLACK)
        registry.register_provider(provider)

        # Get registry again
        registry2 = get_platform_registry()

        # Should have the same provider
        assert registry2.count() == 1
        assert registry2.has_provider(PLATFORM_SLACK) is True

        # Clean up
        registry.clear()

    def test_singleton_thread_safety(self):
        """Test that singleton initialization is thread-safe."""
        # Clear any existing singleton
        import infrastructure.platforms.registry.registry as registry_module

        registry_module._global_registry = None

        results = []

        def get_registry():
            reg = get_platform_registry()
            results.append(id(reg))

        threads = [threading.Thread(target=get_registry) for _ in range(10)]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        # All threads should get the same instance
        assert len(set(results)) == 1
