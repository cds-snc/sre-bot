"""Platform provider registry for managing registered providers.

Provides thread-safe registration and retrieval of platform providers.
"""

import structlog
import threading
from typing import Dict, List, Optional

from infrastructure.platforms.capabilities.models import PlatformCapability
from infrastructure.platforms.providers.base import BasePlatformProvider


logger = structlog.get_logger()


class PlatformProviderRegistry:
    """Thread-safe registry for platform providers.

    Manages registration and retrieval of platform providers (Slack, Teams, Discord, etc.).
    Provides methods to:
    - Register providers
    - Retrieve providers by ID
    - List all providers
    - Filter providers by capability

    Thread-safe for concurrent registration/retrieval in multi-threaded environments
    (e.g., parallel ECS tasks).

    Attributes:
        _providers: Dict mapping platform_id to BasePlatformProvider instances.
        _lock: Threading lock for thread-safe operations.
    """

    def __init__(self):
        """Initialize the registry with empty provider dict and lock."""
        self._providers: Dict[str, BasePlatformProvider] = {}
        self._lock = threading.Lock()

    def register_provider(self, provider: BasePlatformProvider) -> None:
        """Register a platform provider.

        Args:
            provider: BasePlatformProvider instance to register.

        Raises:
            ValueError: If a provider with the same platform_id is already registered.
        """
        platform_id = provider.get_capabilities().platform_id

        with self._lock:
            if platform_id in self._providers:
                raise ValueError(
                    f"Provider with platform_id '{platform_id}' is already registered"
                )

            self._providers[platform_id] = provider
            logger.info(
                "platform_provider_registered",
                platform_id=platform_id,
                provider_name=provider.name,
                version=provider.version,
            )

    def unregister_provider(self, platform_id: str) -> None:
        """Unregister a platform provider.

        Args:
            platform_id: Platform identifier to unregister.

        Raises:
            KeyError: If no provider with the given platform_id is registered.
        """
        with self._lock:
            if platform_id not in self._providers:
                raise KeyError(
                    f"No provider with platform_id '{platform_id}' is registered"
                )

            provider = self._providers.pop(platform_id)
            logger.info(
                "platform_provider_unregistered",
                platform_id=platform_id,
                provider_name=provider.name,
            )

    def get_provider(self, platform_id: str) -> Optional[BasePlatformProvider]:
        """Get a provider by platform ID.

        Args:
            platform_id: Platform identifier (slack, teams, discord).

        Returns:
            BasePlatformProvider instance if found, None otherwise.
        """
        with self._lock:
            return self._providers.get(platform_id)

    def list_providers(self) -> List[BasePlatformProvider]:
        """Get all registered providers.

        Returns:
            List of all registered BasePlatformProvider instances.
        """
        with self._lock:
            return list(self._providers.values())

    def get_providers_by_capability(
        self, capability: PlatformCapability
    ) -> List[BasePlatformProvider]:
        """Get all providers that support a specific capability.

        Args:
            capability: PlatformCapability enum value to filter by.

        Returns:
            List of providers that support the given capability.
        """
        with self._lock:
            matching_providers = []
            for provider in self._providers.values():
                if provider.supports_capability(capability.value):
                    matching_providers.append(provider)

            return matching_providers

    def clear(self) -> None:
        """Clear all registered providers.

        Primarily used for testing. Removes all providers from the registry.
        """
        with self._lock:
            self._providers.clear()
            logger.debug("platform_provider_registry_cleared")

    def count(self) -> int:
        """Get the number of registered providers.

        Returns:
            Count of registered providers.
        """
        with self._lock:
            return len(self._providers)

    def has_provider(self, platform_id: str) -> bool:
        """Check if a provider is registered.

        Args:
            platform_id: Platform identifier to check.

        Returns:
            True if provider is registered, False otherwise.
        """
        with self._lock:
            return platform_id in self._providers


# Global registry instance
_global_registry: Optional[PlatformProviderRegistry] = None
_global_registry_lock = threading.Lock()


def get_platform_registry() -> PlatformProviderRegistry:
    """Get the global platform provider registry singleton.

    Thread-safe singleton pattern. Creates the registry on first call.

    Returns:
        Global PlatformProviderRegistry instance.
    """
    global _global_registry

    if _global_registry is None:
        with _global_registry_lock:
            # Double-check locking pattern
            if _global_registry is None:
                _global_registry = PlatformProviderRegistry()
                logger.debug("global_platform_registry_initialized")

    return _global_registry
