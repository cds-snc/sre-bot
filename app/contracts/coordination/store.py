"""Protocol contract for the conditional-write store.

Defines the runtime-checkable interface consumed by features and
infrastructure. Concrete implementations can vary by backing store.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Protocol, runtime_checkable


class ClaimResult(Enum):
    """Result of attempting to claim a key."""

    NEW = "new"
    COMPLETED = "completed"
    IN_PROGRESS = "in_progress"


@dataclass(frozen=True)
class ClaimOutcome:
    """Domain outcome returned by ConditionalWriteStore.claim().

    claim_token is set exactly when result is NEW. It is an opaque string that
    proves ownership of the claim: the caller hands it back to complete() or
    release(), and only the current holder's token is accepted.
    """

    result: ClaimResult
    outcome: dict[str, Any] | None = None
    claim_token: str | None = None


@runtime_checkable
class ConditionalWriteStore(Protocol):
    """Atomic conditional-write store primitive.

    Implementations provide a claim/complete/release lifecycle that allows
    callers to deduplicate retries or hold a lease without exposing vendor
    details.

    Ownership: complete() and release() apply only for the caller holding the
    claim token of the current claim. A claimant whose in-progress TTL elapsed
    and whose claim was taken over gets False and changes nothing, so a stale
    holder cannot destroy a live holder's record. This is not fencing: the
    protected work itself may still run twice.
    """

    def claim(self, key: str) -> ClaimOutcome:
        """Attempt to claim a key for execution."""
        ...

    def complete(self, key: str, outcome: dict[str, Any], claim_token: str) -> bool:
        """Record the final outcome for a claimed key.

        Returns False, writing nothing, when claim_token does not hold the key.
        A repeated complete with the same token stays True.
        """
        ...

    def release(self, key: str, claim_token: str) -> bool:
        """Release an in-progress claim so redelivery can retry execution.

        Returns False, deleting nothing, when claim_token does not hold the key
        or the key is already completed.
        """
        ...
