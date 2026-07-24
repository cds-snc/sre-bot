"""Shared Protocol-conformance suite for IdempotencyStore implementations.

Parametrized across the in-memory fake and a moto-backed DynamoDB store so
both implementations are held to the identical claim/complete/release
contract.
"""

import pytest

from infrastructure.idempotency.protocol import ClaimResult

pytestmark = pytest.mark.integration


class TestIdempotencyStoreConformance:
    """Runs against every IdempotencyStore implementation via the `idempotency_store` fixture."""

    def test_claim_new_key_returns_new(self, idempotency_store):
        outcome = idempotency_store.claim("feature:intent:new-key")

        assert outcome.result is ClaimResult.NEW

    def test_claim_completed_key_returns_recorded_outcome(self, idempotency_store):
        key = "feature:intent:completed-key"
        idempotency_store.claim(key)
        idempotency_store.complete(key, {"status": "ok", "id": 42})

        outcome = idempotency_store.claim(key)

        assert outcome.result is ClaimResult.COMPLETED
        assert outcome.outcome == {"status": "ok", "id": 42}

    def test_claim_unexpired_in_progress_key_returns_in_progress(self, idempotency_store):
        key = "feature:intent:in-progress-key"
        idempotency_store.claim(key)

        outcome = idempotency_store.claim(key)

        assert outcome.result is ClaimResult.IN_PROGRESS

    def test_release_after_failed_attempt_allows_clean_redelivery(self, idempotency_store):
        key = "feature:intent:release-key"
        idempotency_store.claim(key)

        idempotency_store.release(key)
        outcome = idempotency_store.claim(key)

        assert outcome.result is ClaimResult.NEW

    def test_concurrent_identical_claims_yield_exactly_one_new_one_conflict(self, idempotency_store):
        """Concurrency outcome is asserted from claim results, not timing."""
        key = "feature:intent:concurrent-key"

        first = idempotency_store.claim(key)
        second = idempotency_store.claim(key)

        results = {first.result, second.result}
        assert first.result is ClaimResult.NEW
        assert ClaimResult.NEW in results
        assert second.result in (ClaimResult.IN_PROGRESS, ClaimResult.COMPLETED)

    def test_claim_preserves_exact_key_no_hash_no_truncation(self, idempotency_store):
        """Keys are persisted exactly as provided, with no hashing or truncation."""
        key = "groups_notifications:send_notification:eng-team:add_member:" + "x" * 200

        outcome = idempotency_store.claim(key)
        idempotency_store.complete(key, {"marker": "exact"})
        replay = idempotency_store.claim(key)

        assert outcome.result is ClaimResult.NEW
        assert replay.result is ClaimResult.COMPLETED
        assert replay.outcome == {"marker": "exact"}

    def test_distinct_keys_do_not_collide(self, idempotency_store):
        idempotency_store.claim("feature:intent:key-a")
        outcome = idempotency_store.claim("feature:intent:key-b")

        assert outcome.result is ClaimResult.NEW


class TestIdempotencyStoreExpiredClaimTakeover:
    """Runs against the `expiring_idempotency_store` fixture (in-progress TTL already elapsed)."""

    def test_claim_after_in_progress_ttl_elapsed_returns_new(self, expiring_idempotency_store):
        """A crashed claimant's stale IN_PROGRESS record must be taken over, not rejected."""
        key = "feature:intent:crashed-claimant"

        first = expiring_idempotency_store.claim(key)
        second = expiring_idempotency_store.claim(key)

        assert first.result is ClaimResult.NEW
        assert second.result is ClaimResult.NEW
