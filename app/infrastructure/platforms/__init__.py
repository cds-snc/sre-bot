"""Platform abstraction layer for collaboration platforms (Slack, Teams, Discord).

This package provides a unified interface for integrating with multiple collaboration
platforms while keeping business logic platform-agnostic.
"""

from infrastructure.platforms.capabilities.models import (
    CapabilityDeclaration,
    PlatformCapability,
    create_capability_declaration,
)
from infrastructure.platforms.exceptions import (
    AuthenticationError,
    CapabilityNotSupportedError,
    ConnectionError,
    FormatterError,
    InvalidMessageFormatError,
    PlatformError,
    ProviderAlreadyRegisteredError,
    ProviderInitializationError,
    ProviderNotFoundError,
    RateLimitExceededError,
)
from infrastructure.platforms.registry import PlatformRegistry
from infrastructure.platforms.service import PlatformService

__all__ = [
    # Service
    "PlatformService",
    # Registry
    "PlatformRegistry",
    # Capabilities
    "PlatformCapability",
    "CapabilityDeclaration",
    "create_capability_declaration",
    # Exceptions
    "PlatformError",
    "ProviderNotFoundError",
    "ProviderAlreadyRegisteredError",
    "CapabilityNotSupportedError",
    "ProviderInitializationError",
    "InvalidMessageFormatError",
    "ConnectionError",
    "AuthenticationError",
    "RateLimitExceededError",
    "FormatterError",
]
