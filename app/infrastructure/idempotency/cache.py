"""Idempotency cache abstract base class."""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class IdempotencyCache(ABC):
    """Abstract base class for idempotency cache implementations.

    Defines the interface for caching API responses to prevent duplicate
    operations when requests are retried. Implementations must provide
    distributed cache support for multi-instance deployments.
    """

    @abstractmethod
    def get(self, key: str) -> Optional[Dict[str, Any]]:
        """Get cached response for idempotency key.

        Args:
            key: Idempotency key (typically request ID or operation hash).

        Returns:
            Cached response dict or None if not found/expired.
        """
        pass

    @abstractmethod
    def set(self, key: str, response: Dict[str, Any], ttl_seconds: int) -> None:
        """Cache a response for the given idempotency key.

        Args:
            key: Idempotency key.
            response: Response dict to cache.
            ttl_seconds: Time-to-live in seconds.
        """
        pass

    @abstractmethod
    def clear(self) -> None:
        """Clear all cached entries (for testing).

        Note: Implementation-specific, may be expensive in distributed cache.
        """
        pass

    @abstractmethod
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dict with cache statistics (implementation-specific).
        """
        pass
