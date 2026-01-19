"""Platform provider registry for managing platform implementations."""

from infrastructure.platforms.registry.registry import (
    PlatformProviderRegistry,
    get_platform_registry,
)

# Alias for backward compatibility and convenience
PlatformRegistry = PlatformProviderRegistry

__all__ = [
    # Provider registry
    "PlatformProviderRegistry",
    "PlatformRegistry",
    "get_platform_registry",
]
