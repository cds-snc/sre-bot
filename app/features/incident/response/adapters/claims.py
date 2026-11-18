"""``Claims`` over the contract's ``IdempotencyStore``: each blocking store call runs in one thread."""

import asyncio
from typing import Any

from contracts.coordination import ClaimOutcome, ConditionalWriteStore, IdempotencyStore
from contracts.coordination.policy import ReadFailurePolicy


class ThreadedClaims:
    """``Claims`` on an ``IdempotencyStore`` that fails closed; the store's blocking calls are offloaded."""

    def __init__(self, store: ConditionalWriteStore) -> None:
        self._claims = IdempotencyStore(store, read_failure_policy=ReadFailurePolicy.FAIL_CLOSED)

    async def claim(self, key: str) -> ClaimOutcome:
        """Claim ``key`` in a worker thread."""
        return await asyncio.to_thread(self._claims.claim, key)

    async def complete(self, key: str, outcome: dict[str, Any], claim_token: str) -> bool:
        """Complete ``key`` in a worker thread."""
        return await asyncio.to_thread(self._claims.complete, key, outcome, claim_token)

    async def release(self, key: str, claim_token: str) -> bool:
        """Release ``key`` in a worker thread."""
        return await asyncio.to_thread(self._claims.release, key, claim_token)
