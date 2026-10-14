"""Idempotency (dedup) facade over the conditional-write primitive."""

from typing import Any, final

from contracts.coordination.policy import ReadFailurePolicy, resolve_indeterminate
from contracts.coordination.store import ClaimOutcome, ConditionalWriteStore


@final
class IdempotencyStore:
    """Deduplicate retried operations: claim a key, then complete it or release it.

    claim() never returns INDETERMINATE: the read-failure policy resolves it, so a
    caller sees only NEW (proceed, holding the token), COMPLETED (replay the
    stored outcome) or IN_PROGRESS (another execution owns the key).
    """

    def __init__(self, store: ConditionalWriteStore, *, read_failure_policy: ReadFailurePolicy) -> None:
        self._store = store
        self._read_failure_policy = read_failure_policy

    def claim(self, key: str) -> ClaimOutcome:
        """Claim key for execution; the token is set exactly when the result is NEW."""
        return resolve_indeterminate(self._store.claim(key), self._read_failure_policy)

    def complete(self, key: str, outcome: dict[str, Any], claim_token: str) -> bool:
        """Record the outcome; False, writing nothing, when claim_token no longer holds the key."""
        return self._store.complete(key, outcome, claim_token)

    def release(self, key: str, claim_token: str) -> bool:
        """Free an in-progress claim so a redelivery can retry; False when claim_token does not hold it."""
        return self._store.release(key, claim_token)
