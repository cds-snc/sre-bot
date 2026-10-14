"""Unit tests for the IdempotencyStore (dedup) facade over ConditionalWriteStore.

Lifecycle cases run on the real in-memory primitive. The read-failure cases use a
scripted store to inject INDETERMINATE and check that a fail-closed dedup caller
gets IN_PROGRESS with no token, so it can never re-execute an operation that may
already have completed.
"""

import pytest

from contracts.coordination import ClaimOutcome, ClaimResult, ConditionalWriteStore, IdempotencyStore, ReadFailurePolicy
from infrastructure.coordination import InMemoryConditionalWriteStore

from .conftest import ScriptedConditionalWriteStore

pytestmark = pytest.mark.unit

KEY = "webhooks:delivery:abc-123"


def _idempotency_store(store: ConditionalWriteStore) -> IdempotencyStore:
    return IdempotencyStore(store, read_failure_policy=ReadFailurePolicy.FAIL_CLOSED)


class TestIdempotencyStoreConstruction:
    def test_read_failure_policy_is_required(self, in_memory_store: InMemoryConditionalWriteStore) -> None:
        with pytest.raises(TypeError):
            IdempotencyStore(in_memory_store)  # type: ignore[call-arg]

    def test_read_failure_policy_is_keyword_only(self, in_memory_store: InMemoryConditionalWriteStore) -> None:
        with pytest.raises(TypeError):
            IdempotencyStore(in_memory_store, ReadFailurePolicy.FAIL_CLOSED)  # type: ignore[misc]


class TestIdempotencyStoreLifecycle:
    def test_completed_claim_replays_its_outcome(self, in_memory_store: InMemoryConditionalWriteStore) -> None:
        dedup = _idempotency_store(in_memory_store)
        first = dedup.claim(KEY)
        assert first.result is ClaimResult.NEW
        assert first.claim_token is not None

        assert dedup.complete(KEY, {"status": "done"}, first.claim_token) is True

        replay = dedup.claim(KEY)
        assert replay.result is ClaimResult.COMPLETED
        assert replay.outcome == {"status": "done"}

    def test_released_claim_can_be_claimed_again(self, in_memory_store: InMemoryConditionalWriteStore) -> None:
        dedup = _idempotency_store(in_memory_store)
        first = dedup.claim(KEY)
        assert first.claim_token is not None

        assert dedup.release(KEY, first.claim_token) is True
        assert dedup.claim(KEY).result is ClaimResult.NEW

    def test_concurrent_claim_sees_in_progress(self, in_memory_store: InMemoryConditionalWriteStore) -> None:
        dedup = _idempotency_store(in_memory_store)
        dedup.claim(KEY)

        assert dedup.claim(KEY) == ClaimOutcome(result=ClaimResult.IN_PROGRESS)

    def test_foreign_token_cannot_complete_or_release(self, in_memory_store: InMemoryConditionalWriteStore) -> None:
        dedup = _idempotency_store(in_memory_store)
        dedup.claim(KEY)

        assert dedup.complete(KEY, {"status": "done"}, "0" * 32) is False
        assert dedup.release(KEY, "0" * 32) is False
        assert dedup.claim(KEY).result is ClaimResult.IN_PROGRESS


class TestIdempotencyStoreReadFailure:
    def test_fail_closed_indeterminate_claim_becomes_in_progress(self) -> None:
        """The caller never sees INDETERMINATE and holds no token, so it cannot proceed."""
        store = ScriptedConditionalWriteStore(ClaimOutcome(result=ClaimResult.INDETERMINATE))

        assert _idempotency_store(store).claim(KEY) == ClaimOutcome(result=ClaimResult.IN_PROGRESS)

    def test_fail_closed_does_not_re_execute_a_possibly_completed_operation(self) -> None:
        """Why fail-closed is the dedup default: the unreadable record may be a COMPLETED one.

        The first delivery completes; a redelivery's re-read then fails. Proceeding
        would run the operation twice, so the facade must report IN_PROGRESS.
        """
        store = ScriptedConditionalWriteStore(
            ClaimOutcome(result=ClaimResult.NEW, claim_token="a" * 32),
            ClaimOutcome(result=ClaimResult.INDETERMINATE),
        )
        dedup = _idempotency_store(store)
        dedup.claim(KEY)
        dedup.complete(KEY, {"status": "done"}, "a" * 32)

        redelivery = dedup.claim(KEY)

        assert redelivery.result is ClaimResult.IN_PROGRESS
        assert redelivery.claim_token is None

    def test_complete_and_release_pass_tokens_through(self) -> None:
        store = ScriptedConditionalWriteStore(ownership=False)
        dedup = _idempotency_store(store)

        assert dedup.complete(KEY, {"status": "done"}, "a" * 32) is False
        assert dedup.release(KEY, "a" * 32) is False
        assert store.calls == [("complete", KEY, "a" * 32), ("release", KEY, "a" * 32)]
