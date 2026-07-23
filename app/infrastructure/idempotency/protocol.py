"""Protocol contract for idempotency services.

Defines the runtime-checkable interface consumed by features and
infrastructure. Concrete implementations can vary by backing store.
"""

from typing import Any, Protocol, runtime_checkable

from infrastructure.idempotency.cache import IdempotencyCache


@runtime_checkable
class IdempotencyService(Protocol):
    """Idempotency service contract.

    Abstracts storage and retrieval of responses for idempotent operations
    across retries. Implementation must be distributed-cache-safe for
    multi-instance deployments.
    """

    def get(self, key: str) -> dict[str, Any] | None:
        """Get cached response for idempotency key.

        Args:
            key: Idempotency key (typically request ID or operation hash)

        Returns:
            Cached response dict or None if not found/expired
        """
        ...

    def set(self, key: str, response: dict[str, Any], ttl_seconds: int) -> None:
        """Cache a response for the given idempotency key.

        Args:
            key: Idempotency key
            response: Response dict to cache
            ttl_seconds: Time-to-live in seconds
        """
        ...

    def clear(self) -> None:
        """Clear all cached entries.

        Warning: This may be expensive in distributed caches.
        Primarily intended for testing.
        """
        ...

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dict with cache statistics (implementation-specific)
        """
        ...

    @property
    def cache(self) -> IdempotencyCache:
        """Access underlying IdempotencyCache instance.

        Provided for advanced use cases that need direct access
        to the cache implementation.

        Returns:
            The underlying IdempotencyCache instance
        """
        ...
