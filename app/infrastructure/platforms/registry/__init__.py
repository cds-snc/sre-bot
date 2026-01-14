"""Platform provider registry for managing platform implementations."""

from infrastructure.platforms.registry.registry import PlatformProviderRegistry

# Alias for backward compatibility and convenience
PlatformRegistry = PlatformProviderRegistry

__all__ = ["PlatformProviderRegistry", "PlatformRegistry"]
