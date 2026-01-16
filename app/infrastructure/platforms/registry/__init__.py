"""Platform provider registry for managing platform implementations."""

from infrastructure.platforms.registry.registry import (
    PlatformProviderRegistry,
    get_platform_registry,
)
from infrastructure.platforms.registry.auto_discovery import (
    AutoDiscovery,
    ProviderCommandRegistry,
    get_auto_discovery,
    slack_commands,
    teams_commands,
    discord_commands,
)

# Alias for backward compatibility and convenience
PlatformRegistry = PlatformProviderRegistry

__all__ = [
    # Provider registry
    "PlatformProviderRegistry",
    "PlatformRegistry",
    "get_platform_registry",
    # Command auto-discovery
    "AutoDiscovery",
    "ProviderCommandRegistry",
    "get_auto_discovery",
    "slack_commands",
    "teams_commands",
    "discord_commands",
]
