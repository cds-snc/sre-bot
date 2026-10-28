"""Shared stubs for the coordination facade tests."""

from typing import Any

import pytest

from contracts.coordination import ClaimOutcome
from infrastructure.coordination import InMemoryConditionalWriteStore


class ScriptedConditionalWriteStore:
    """ConditionalWriteStore stub that returns scripted claim outcomes and records every call.

    It lets a test inject ClaimResult.INDETERMINATE, which no real store produces
    without a failing read, and observe whether a facade calls complete() or release().
    """

    def __init__(self, *claim_outcomes: ClaimOutcome, ownership: bool = True) -> None:
        self._claim_outcomes = list(claim_outcomes)
        self._ownership = ownership
        self.calls: list[tuple[str, ...]] = []

    def claim(self, key: str) -> ClaimOutcome:
        self.calls.append(("claim", key))
        return self._claim_outcomes.pop(0)

    def complete(self, key: str, outcome: dict[str, Any], claim_token: str) -> bool:
        self.calls.append(("complete", key, claim_token))
        return self._ownership

    def release(self, key: str, claim_token: str) -> bool:
        self.calls.append(("release", key, claim_token))
        return self._ownership


@pytest.fixture
def in_memory_store() -> InMemoryConditionalWriteStore:
    """Real in-memory primitive for full claim/complete/release lifecycles."""
    return InMemoryConditionalWriteStore(record_ttl_seconds=3600, in_progress_ttl_seconds=300)


@pytest.fixture
def expired_store() -> InMemoryConditionalWriteStore:
    """In-memory primitive whose in-progress claims are already expired, so any claim can be taken over."""
    return InMemoryConditionalWriteStore(record_ttl_seconds=3600, in_progress_ttl_seconds=-1)
