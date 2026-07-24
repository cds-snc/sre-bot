"""Protocol contract for idempotency services.

Defines the runtime-checkable interface consumed by features and
infrastructure. Concrete implementations can vary by backing store.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Protocol, runtime_checkable

from infrastructure.idempotency.cache import IdempotencyCache


class ClaimResult(Enum):
    """Result of attempting to claim an idempotency key."""

    NEW = "new"
    COMPLETED = "completed"
    IN_PROGRESS = "in_progress"


@dataclass(frozen=True)
class ClaimOutcome:
    """Domain outcome returned by IdempotencyStore.claim()."""

    result: ClaimResult
    outcome: dict[str, Any] | None = None


@runtime_checkable
class IdempotencyStore(Protocol):
    """Atomic idempotency store primitive.

    Implementations provide a claim/complete/release lifecycle that allows
    callers to deduplicate retries without exposing vendor details.
    """

    def claim(self, key: str) -> ClaimOutcome:
        """Attempt to claim a key for execution."""
        ...

    def complete(self, key: str, outcome: dict[str, Any]) -> None:
        """Record the final outcome for a claimed key."""
        ...

    def release(self, key: str) -> None:
        """Release a claimed key so redelivery can retry execution."""
        ...


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
