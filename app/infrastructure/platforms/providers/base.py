"""Base platform provider abstract class.

All platform-specific providers (Slack, Teams, Discord) inherit from this base class.
"""

import structlog
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from infrastructure.operations import OperationResult
from infrastructure.platforms.capabilities.models import CapabilityDeclaration


logger = structlog.get_logger()


class BasePlatformProvider(ABC):
    """Abstract base class for all platform providers.

    Platform providers wrap collaboration platform SDKs (Slack Bolt, Teams Bot SDK, etc.)
    and provide a unified interface for sending messages, formatting responses, and
    declaring capabilities.

    All providers must:
    - Declare their capabilities via get_capabilities()
    - Implement send_message() for posting to the platform
    - Implement format_response() for converting data to platform-native format
    - Provide metadata (name, version, enabled status)

    Attributes:
        _name: Human-readable provider name (e.g., "Slack Provider").
        _version: Provider version string (e.g., "1.0.0").
        _enabled: Whether this provider is enabled in configuration.
    """

    def __init__(self, name: str, version: str = "1.0.0", enabled: bool = True):
        """Initialize the platform provider.

        Args:
            name: Human-readable provider name.
            version: Provider version string.
            enabled: Whether provider is enabled.
        """
        self._name = name
        self._version = version
        self._enabled = enabled
        self._logger = logger.bind(provider=name, version=version)

    @property
    def name(self) -> str:
        """Get the provider name."""
        return self._name

    @property
    def version(self) -> str:
        """Get the provider version."""
        return self._version

    @property
    def enabled(self) -> bool:
        """Check if the provider is enabled."""
        return self._enabled

    @abstractmethod
    def get_capabilities(self) -> CapabilityDeclaration:
        """Get the capability declaration for this provider.

        Returns:
            CapabilityDeclaration instance describing supported features.
        """
        pass

    @abstractmethod
    def send_message(
        self,
        channel: str,
        message: Dict[str, Any],
        thread_ts: Optional[str] = None,
    ) -> OperationResult:
        """Send a message to the platform.

        Args:
            channel: Channel/conversation ID or user ID.
            message: Platform-specific message payload (Block Kit, Adaptive Card, etc.).
            thread_ts: Optional thread timestamp for threaded messages.

        Returns:
            OperationResult with message metadata on success, error on failure.
        """
        pass

    @abstractmethod
    def format_response(
        self,
        data: Dict[str, Any],
        message_type: str = "success",
    ) -> Dict[str, Any]:
        """Format a response dict into platform-native format.

        Args:
            data: Data dictionary to format.
            message_type: Type of message ("success", "error", "info", "warning").

        Returns:
            Platform-specific message payload (Block Kit, Adaptive Card, Embed, etc.).
        """
        pass

    def supports_capability(self, capability: str) -> bool:
        """Check if this provider supports a specific capability.

        Args:
            capability: Capability identifier (from PlatformCapability enum).

        Returns:
            True if capability is supported, False otherwise.
        """
        capabilities = self.get_capabilities()
        return any(cap.value == capability for cap in capabilities.capabilities)

    def __repr__(self) -> str:
        """String representation of the provider."""
        return (
            f"{self.__class__.__name__}("
            f"name={self._name!r}, "
            f"version={self._version!r}, "
            f"enabled={self._enabled})"
        )
