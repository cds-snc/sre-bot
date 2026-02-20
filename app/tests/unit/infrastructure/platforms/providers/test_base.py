"""Unit tests for BasePlatformProvider abstract class."""

import pytest
from typing import Optional

from infrastructure.operations import OperationResult
from infrastructure.platforms.capabilities.models import (
    CapabilityDeclaration,
    PlatformCapability,
    PLATFORM_SLACK,
    create_capability_declaration,
)
from infrastructure.platforms.providers.base import BasePlatformProvider


class ConcretePlatformProvider(BasePlatformProvider):
    """Concrete implementation of BasePlatformProvider for testing."""

    def __init__(
        self,
        name: str = "Test Provider",
        version: str = "1.0.0",
        enabled: bool = True,
        capabilities: Optional[CapabilityDeclaration] = None,
    ):
        super().__init__(name=name, version=version, enabled=enabled)
        self._capabilities = capabilities or create_capability_declaration(
            PLATFORM_SLACK,
            PlatformCapability.COMMANDS,
            PlatformCapability.MESSAGING,
        )

    def get_capabilities(self) -> CapabilityDeclaration:
        """Return test capabilities."""
        return self._capabilities

    def get_user_locale(self, user_id):
        """Mock get_user_locale implementation."""
        return "en-US"

    def generate_help(
        self,
        locale: str = "en-US",
        root_command: Optional[str] = None,
    ) -> str:
        """Mock generate_help implementation."""
        return "Available commands: help"

    def generate_command_help(
        self,
        command_name: str,
        locale: str = "en-US",
    ) -> str:
        """Mock generate_command_help implementation."""
        return f"Help for {command_name}"


@pytest.mark.unit
class TestBasePlatformProvider:
    """Test BasePlatformProvider abstract base class."""

    def test_cannot_instantiate_abstract_base_class(self):
        """Test that BasePlatformProvider cannot be instantiated directly."""
        with pytest.raises(TypeError) as exc_info:
            BasePlatformProvider(name="Test", version="1.0.0")  # type: ignore

        assert "Can't instantiate abstract class" in str(exc_info.value)

    def test_concrete_provider_initialization(self):
        """Test initializing a concrete provider implementation."""
        provider = ConcretePlatformProvider(
            name="Test Provider",
            version="2.0.0",
            enabled=True,
        )

        assert provider.name == "Test Provider"
        assert provider.version == "2.0.0"
        assert provider.enabled is True

    def test_provider_default_values(self):
        """Test default initialization values."""
        provider = ConcretePlatformProvider(name="Test")

        assert provider.name == "Test"
        assert provider.version == "1.0.0"
        assert provider.enabled is True

    def test_provider_disabled_state(self):
        """Test provider with enabled=False."""
        provider = ConcretePlatformProvider(
            name="Disabled Provider",
            enabled=False,
        )

        assert provider.enabled is False

    def test_get_capabilities(self):
        """Test get_capabilities() returns CapabilityDeclaration."""
        capabilities = create_capability_declaration(
            PLATFORM_SLACK,
            PlatformCapability.COMMANDS,
            PlatformCapability.VIEWS_MODALS,
        )
        provider = ConcretePlatformProvider(capabilities=capabilities)

        result = provider.get_capabilities()

        assert isinstance(result, CapabilityDeclaration)
        assert result.platform_id == PLATFORM_SLACK
        assert PlatformCapability.COMMANDS in result.capabilities
        assert PlatformCapability.VIEWS_MODALS in result.capabilities

    def test_supports_capability_true(self):
        """Test supports_capability() returns True for supported capability."""
        capabilities = create_capability_declaration(
            PLATFORM_SLACK,
            PlatformCapability.COMMANDS,
            PlatformCapability.MESSAGING,
        )
        provider = ConcretePlatformProvider(capabilities=capabilities)

        assert provider.supports_capability(PlatformCapability.COMMANDS.value) is True
        assert provider.supports_capability(PlatformCapability.MESSAGING.value) is True

    def test_supports_capability_false(self):
        """Test supports_capability() returns False for unsupported capability."""
        capabilities = create_capability_declaration(
            PLATFORM_SLACK,
            PlatformCapability.COMMANDS,
        )
        provider = ConcretePlatformProvider(capabilities=capabilities)

        assert (
            provider.supports_capability(PlatformCapability.VIEWS_MODALS.value) is False
        )
        assert provider.supports_capability(PlatformCapability.WORKFLOWS.value) is False

    def test_provider_repr(self):
        """Test __repr__ string representation."""
        provider = ConcretePlatformProvider(
            name="Test Provider",
            version="1.2.3",
            enabled=True,
        )

        repr_str = repr(provider)

        assert "ConcretePlatformProvider" in repr_str
        assert "name='Test Provider'" in repr_str
        assert "version='1.2.3'" in repr_str
        assert "enabled=True" in repr_str

    def test_provider_repr_disabled(self):
        """Test __repr__ with disabled provider."""
        provider = ConcretePlatformProvider(enabled=False)

        repr_str = repr(provider)

        assert "enabled=False" in repr_str

    def test_property_immutability(self):
        """Test that properties cannot be set directly."""
        provider = ConcretePlatformProvider(name="Original")

        # Properties should be read-only (no setter)
        with pytest.raises(AttributeError):
            provider.name = "Modified"  # type: ignore

        with pytest.raises(AttributeError):
            provider.version = "9.9.9"  # type: ignore

        with pytest.raises(AttributeError):
            provider.enabled = False  # type: ignore

    def test_logger_binding(self):
        """Test that logger is bound with provider context."""
        provider = ConcretePlatformProvider(
            name="Logger Test",
            version="3.0.0",
        )

        # Logger should be bound to provider instance
        assert hasattr(provider, "_logger")
        # Note: Direct testing of logger bindings requires accessing internal state


@pytest.mark.unit
class TestAbstractMethodEnforcement:
    """Test that abstract methods must be implemented."""

    def test_missing_get_capabilities_raises_error(self):
        """Test that missing get_capabilities() raises TypeError."""

        class IncompleteProvider(BasePlatformProvider):
            def send_message(self, channel, message, thread_ts=None):
                return OperationResult.success(data={})

            def format_response(self, data, message_type="success"):
                return {}

            def generate_help(self, locale="en-US", root_command=None):
                return ""

            def generate_command_help(self, command_name, locale="en-US"):
                return ""

        with pytest.raises(TypeError) as exc_info:
            IncompleteProvider(name="Incomplete")  # type: ignore

        assert "get_capabilities" in str(exc_info.value)
