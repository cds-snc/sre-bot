"""Unit tests for InMemoryIdempotencyStore (TASK-5.1, AC#4).

Isolated, no I/O. Exercises the same claim/complete/release semantics
required of every IdempotencyStore implementation.
"""

import pytest
from infrastructure.idempotency.in_memory import InMemoryIdempotencyStore
from infrastructure.idempotency.settings import IdempotencySettings

from infrastructure.idempotency.protocol import ClaimResult

pytestmark = pytest.mark.unit


@pytest.fixture
def settings():
    return IdempotencySettings(
        IDEMPOTENCY_TTL_SECONDS=3600, IDEMPOTENCY_IN_PROGRESS_TTL_SECONDS=300
    )


@pytest.fixture
def expiring_settings():
    return IdempotencySettings(
        IDEMPOTENCY_TTL_SECONDS=3600, IDEMPOTENCY_IN_PROGRESS_TTL_SECONDS=-1
    )


@pytest.fixture
def store(settings):
    return InMemoryIdempotencyStore(idempotency_settings=settings)


class TestInMemoryIdempotencyStoreClaim:
    def test_claim_on_unseen_key_returns_new(self, store):
        outcome = store.claim("feature:intent:unseen")
        assert outcome.result is ClaimResult.NEW

    def test_claim_on_unexpired_in_progress_key_returns_in_progress(self, store):
        store.claim("feature:intent:busy")
        outcome = store.claim("feature:intent:busy")
        assert outcome.result is ClaimResult.IN_PROGRESS

    def test_claim_on_completed_key_returns_completed_with_outcome(self, store):
        key = "feature:intent:done"
        store.claim(key)
        store.complete(key, {"status": "ok"})

        outcome = store.claim(key)

        assert outcome.result is ClaimResult.COMPLETED
        assert outcome.outcome == {"status": "ok"}

    def test_claim_on_expired_in_progress_key_returns_new(self, expiring_settings):
        store = InMemoryIdempotencyStore(idempotency_settings=expiring_settings)
        key = "feature:intent:crashed-claimant"

        first = store.claim(key)
        second = store.claim(key)

        assert first.result is ClaimResult.NEW
        assert second.result is ClaimResult.NEW


class TestInMemoryIdempotencyStoreCompleteAndRelease:
    def test_complete_records_exact_outcome_dict(self, store):
        key = "feature:intent:record"
        outcome_payload = {"a": 1, "nested": {"b": 2}}
        store.claim(key)
        store.complete(key, outcome_payload)

        result = store.claim(key)

        assert result.outcome == outcome_payload

    def test_release_after_claim_allows_redelivery_to_claim_new_again(self, store):
        key = "feature:intent:redelivered"
        store.claim(key)

        store.release(key)
        outcome = store.claim(key)

        assert outcome.result is ClaimResult.NEW

    def test_release_on_unknown_key_does_not_raise(self, store):
        store.release("feature:intent:never-claimed")


class TestInMemoryIdempotencyStoreKeyFormat:
    def test_claim_preserves_exact_key_no_hash_no_truncation(self, store):
        key = "groups_notifications:send_notification:eng-team:add_member:" + "x" * 200
        store.claim(key)
        store.complete(key, {"marker": "exact"})

        replay = store.claim(key)

        assert replay.result is ClaimResult.COMPLETED
        assert replay.outcome == {"marker": "exact"}

    def test_distinct_keys_do_not_collide(self, store):
        store.claim("feature:intent:a")
        outcome = store.claim("feature:intent:b")

        assert outcome.result is ClaimResult.NEW
