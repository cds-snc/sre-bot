"""Protocol contract for idempotency services.

Defines the runtime-checkable interface consumed by features and
infrastructure. Concrete implementations can vary by backing store.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Protocol, runtime_checkable


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
