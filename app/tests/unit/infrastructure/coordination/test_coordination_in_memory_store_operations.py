"""Unit tests for InMemoryConditionalWriteStore.

Isolated, no I/O. Exercises the same claim/complete/release semantics
required of every ConditionalWriteStore implementation.
"""

import pytest

from contracts.coordination import ClaimResult
from infrastructure.coordination.in_memory import InMemoryConditionalWriteStore
from infrastructure.coordination.settings import ConditionalWriteSettings

pytestmark = pytest.mark.unit


@pytest.fixture
def settings():
    return ConditionalWriteSettings(IDEMPOTENCY_TTL_SECONDS=3600, IDEMPOTENCY_IN_PROGRESS_TTL_SECONDS=300)


@pytest.fixture
def expiring_settings():
    return ConditionalWriteSettings(IDEMPOTENCY_TTL_SECONDS=3600, IDEMPOTENCY_IN_PROGRESS_TTL_SECONDS=-1)


@pytest.fixture
def store(settings):
    return InMemoryConditionalWriteStore(settings=settings)


class TestInMemoryConditionalWriteStoreClaim:
    def test_claim_on_unseen_key_returns_new(self, store):
        outcome = store.claim("feature:intent:unseen")
        assert outcome.result is ClaimResult.NEW

    def test_claim_on_unexpired_in_progress_key_returns_in_progress(self, store):
        store.claim("feature:intent:busy")
        outcome = store.claim("feature:intent:busy")
        assert outcome.result is ClaimResult.IN_PROGRESS

    def test_claim_on_completed_key_returns_completed_with_outcome(self, store):
        key = "feature:intent:done"
        claimed = store.claim(key)
        store.complete(key, {"status": "ok"}, claimed.claim_token)

        outcome = store.claim(key)

        assert outcome.result is ClaimResult.COMPLETED
        assert outcome.outcome == {"status": "ok"}

    def test_claim_on_expired_in_progress_key_returns_new(self, expiring_settings):
        store = InMemoryConditionalWriteStore(settings=expiring_settings)
        key = "feature:intent:crashed-claimant"

        first = store.claim(key)
        second = store.claim(key)

        assert first.result is ClaimResult.NEW
        assert second.result is ClaimResult.NEW


class TestInMemoryConditionalWriteStoreCompleteAndRelease:
    def test_complete_records_exact_outcome_dict(self, store):
        key = "feature:intent:record"
        outcome_payload = {"a": 1, "nested": {"b": 2}}
        claimed = store.claim(key)
        store.complete(key, outcome_payload, claimed.claim_token)

        result = store.claim(key)

        assert result.outcome == outcome_payload

    def test_release_after_claim_allows_redelivery_to_claim_new_again(self, store):
        key = "feature:intent:redelivered"
        claimed = store.claim(key)

        store.release(key, claimed.claim_token)
        outcome = store.claim(key)

        assert outcome.result is ClaimResult.NEW

    def test_release_on_unknown_key_returns_false(self, store):
        assert store.release("feature:intent:never-claimed", "0" * 32) is False


class TestInMemoryConditionalWriteStoreKeyFormat:
    def test_claim_preserves_exact_key_no_hash_no_truncation(self, store):
        key = "groups_notifications:send_notification:eng-team:add_member:" + "x" * 200
        claimed = store.claim(key)
        store.complete(key, {"marker": "exact"}, claimed.claim_token)

        replay = store.claim(key)

        assert replay.result is ClaimResult.COMPLETED
        assert replay.outcome == {"marker": "exact"}

    def test_distinct_keys_do_not_collide(self, store):
        store.claim("feature:intent:a")
        outcome = store.claim("feature:intent:b")

        assert outcome.result is ClaimResult.NEW
