"""Platform abstraction layer for collaboration platforms (Slack, Teams, Discord).

This package provides a unified interface for integrating with multiple collaboration
platforms while keeping business logic platform-agnostic.

Key Components:
    - Platform Providers: Slack, Teams, Discord implementations
    - Platform Registry: Provider registration and lookup
    - Platform Service: Unified service facade
    - Capabilities: Feature declarations (commands, views, cards)
    - Formatters: Platform-specific response formatting
    - Adapters: HTTP endpoint wrappers
    - Models: Platform-agnostic data structures
    - Clients: Internal HTTP and platform SDK facades
"""

from infrastructure.platforms.capabilities.models import (
    CapabilityDeclaration,
    PlatformCapability,
    create_capability_declaration,
)
from infrastructure.platforms.formatters import (
    BaseResponseFormatter,
    DiscordEmbedFormatter,
    SlackBlockKitFormatter,
    TeamsAdaptiveCardsFormatter,
)
from infrastructure.platforms.providers import (
    BasePlatformProvider,
    SlackPlatformProvider,
)

__all__ = [
    # Providers
    "BasePlatformProvider",
    "SlackPlatformProvider",
    # Capabilities
    "PlatformCapability",
    "CapabilityDeclaration",
    "create_capability_declaration",
    # Formatters
    "BaseResponseFormatter",
    "SlackBlockKitFormatter",
    "TeamsAdaptiveCardsFormatter",
    "DiscordEmbedFormatter",
]
