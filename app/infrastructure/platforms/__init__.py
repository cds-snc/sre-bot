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

from infrastructure.platforms.adapters import BaseCommandAdapter
from infrastructure.platforms.capabilities.models import (
    CapabilityDeclaration,
    PlatformCapability,
    create_capability_declaration,
)
from infrastructure.platforms.clients import (
    InternalHttpClient,
    SlackClientFacade,
    TeamsClientFacade,
    DiscordClientFacade,
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
from infrastructure.platforms.formatters import (
    BaseResponseFormatter,
    DiscordEmbedFormatter,
    SlackBlockKitFormatter,
    TeamsAdaptiveCardsFormatter,
)
from infrastructure.platforms.models import (
    CardAction,
    CardActionStyle,
    CardDefinition,
    CardElementType,
    CardSection,
    CommandPayload,
    CommandResponse,
    CommandDefinition,
    HttpEndpointRequest,
    HttpEndpointResponse,
    ViewDefinition,
    ViewField,
    ViewSubmission,
)
from infrastructure.platforms.providers import (
    BasePlatformProvider,
    DiscordPlatformProvider,
    SlackPlatformProvider,
    TeamsPlatformProvider,
)
from infrastructure.platforms.registry import (
    PlatformRegistry,
    slack_commands,
    teams_commands,
    discord_commands,
)
from infrastructure.platforms.service import PlatformService

__all__ = [
    # Service
    "PlatformService",
    # Registry
    "PlatformRegistry",
    # Providers
    "BasePlatformProvider",
    "SlackPlatformProvider",
    "TeamsPlatformProvider",
    "DiscordPlatformProvider",
    # Capabilities
    "PlatformCapability",
    "CapabilityDeclaration",
    "create_capability_declaration",
    # Formatters
    "BaseResponseFormatter",
    "SlackBlockKitFormatter",
    "TeamsAdaptiveCardsFormatter",
    "DiscordEmbedFormatter",
    # Adapters
    "BaseCommandAdapter",
    # Clients
    "InternalHttpClient",
    "SlackClientFacade",
    "TeamsClientFacade",
    "DiscordClientFacade",
    # Models - Command
    "CommandPayload",
    "CommandResponse",
    "CommandDefinition",
    # Models - View/Modal
    "ViewField",
    "ViewDefinition",
    "ViewSubmission",
    # Models - Interactive Cards
    "CardElementType",
    "CardActionStyle",
    "CardAction",
    "CardSection",
    "CardDefinition",
    # Models - HTTP
    "HttpEndpointRequest",
    "HttpEndpointResponse",
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
    # Commands
    "slack_commands",
    "teams_commands",
    "discord_commands",
]
