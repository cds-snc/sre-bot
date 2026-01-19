"""Unit tests for BasePlatformProvider abstract class."""

import pytest
from typing import Any, Dict, Optional

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

    def send_message(
        self,
        channel: str,
        message: Dict[str, Any],
        thread_ts: Optional[str] = None,
    ) -> OperationResult:
        """Mock send_message implementation."""
        return OperationResult.success(
            data={"channel": channel, "message": message, "thread_ts": thread_ts},
            message="Message sent successfully",
        )

    def format_response(
        self,
        data: Dict[str, Any],
        message_type: str = "success",
    ) -> Dict[str, Any]:
        """Mock format_response implementation."""
        return {
            "type": message_type,
            "data": data,
        }

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

    def test_send_message_success(self):
        """Test send_message() returns OperationResult."""
        provider = ConcretePlatformProvider()
        message = {"text": "Hello, world!"}

        result = provider.send_message(
            channel="C123456",
            message=message,
        )

        assert result.is_success
        assert result.data["channel"] == "C123456"
        assert result.data["message"] == message

    def test_send_message_with_thread(self):
        """Test send_message() with thread_ts parameter."""
        provider = ConcretePlatformProvider()
        message = {"text": "Reply in thread"}

        result = provider.send_message(
            channel="C123456",
            message=message,
            thread_ts="1234567890.123456",
        )

        assert result.is_success
        assert result.data["thread_ts"] == "1234567890.123456"

    def test_format_response_success(self):
        """Test format_response() with success type."""
        provider = ConcretePlatformProvider()
        data = {"user_id": "U123", "status": "completed"}

        result = provider.format_response(data, message_type="success")

        assert result["type"] == "success"
        assert result["data"] == data

    def test_format_response_error(self):
        """Test format_response() with error type."""
        provider = ConcretePlatformProvider()
        data = {"error": "Something went wrong"}

        result = provider.format_response(data, message_type="error")

        assert result["type"] == "error"
        assert result["data"] == data

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

    def test_missing_send_message_raises_error(self):
        """Test that missing send_message() raises TypeError."""

        class IncompleteProvider(BasePlatformProvider):
            def get_capabilities(self):
                return create_capability_declaration(PLATFORM_SLACK)

            def format_response(self, data, message_type="success"):
                return {}

            def generate_help(self, locale="en-US", root_command=None):
                return ""

            def generate_command_help(self, command_name, locale="en-US"):
                return ""

        with pytest.raises(TypeError) as exc_info:
            IncompleteProvider(name="Incomplete")  # type: ignore

        assert "send_message" in str(exc_info.value)

    def test_missing_format_response_raises_error(self):
        """Test that missing format_response() raises TypeError."""

        class IncompleteProvider(BasePlatformProvider):
            def get_capabilities(self):
                return create_capability_declaration(PLATFORM_SLACK)

            def send_message(self, channel, message, thread_ts=None):
                return OperationResult.success(data={})

            def generate_help(self, locale="en-US", root_command=None):
                return ""

            def generate_command_help(self, command_name, locale="en-US"):
                return ""

        with pytest.raises(TypeError) as exc_info:
            IncompleteProvider(name="Incomplete")  # type: ignore

        assert "format_response" in str(exc_info.value)
