"""Concrete idempotency service implementation.

Provides a class-based interface to the idempotency cache for easier DI and testing.
This is the DynamoDB-backed concrete implementation. The Protocol contract is defined
in infrastructure.idempotency.protocol.
"""

from typing import Any

from infrastructure.idempotency.cache import IdempotencyCache


class DynamoDBIdempotencyService:
    """DynamoDB-backed idempotency service.

    Wraps the IdempotencyCache interface with a service class to support
    dependency injection and easier testing with mocks.

    This eliminates the global singleton pattern in favor of DI-friendly
    service instances.

    Usage:
        # Via dependency injection
        from infrastructure.idempotency import IdempotencyServiceDep

        @router.post("/action")
        def perform_action(
            idempotency: IdempotencyServiceDep,
            request_id: str
        ):
            cached = idempotency.get(request_id)
            if cached:
                return cached

            result = {"status": "processed"}
            idempotency.set(request_id, result, ttl_seconds=3600)
            return result

        # Direct instantiation
        from infrastructure.idempotency.service import DynamoDBIdempotencyService

        service = DynamoDBIdempotencyService(cache)
    """

    def __init__(
        self,
        cache: IdempotencyCache,
    ):
        """Initialize idempotency service.

        Args:
            cache: Pre-constructed IdempotencyCache instance (injected by providers.py).
        """
        self._cache = cache

    def get(self, key: str) -> dict[str, Any] | None:
        """Get cached response for idempotency key.

        Args:
            key: Idempotency key (typically request ID or operation hash)

        Returns:
            Cached response dict or None if not found/expired
        """
        return self._cache.get(key)

    def set(self, key: str, response: dict[str, Any], ttl_seconds: int) -> None:
        """Cache a response for the given idempotency key.

        Args:
            key: Idempotency key
            response: Response dict to cache
            ttl_seconds: Time-to-live in seconds
        """
        self._cache.set(key, response, ttl_seconds)

    def clear(self) -> None:
        """Clear all cached entries.

        Warning: This may be expensive in distributed caches.
        Primarily intended for testing.
        """
        self._cache.clear()

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dict with cache statistics (implementation-specific)
        """
        return self._cache.get_stats()

    @property
    def cache(self) -> IdempotencyCache:
        """Access underlying IdempotencyCache instance.

        Provided for advanced use cases that need direct access
        to the cache implementation.

        Returns:
            The underlying IdempotencyCache instance
        """
        return self._cache
