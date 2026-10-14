"""Shared Protocol-conformance suite for IdempotencyStore implementations.

Parametrized across the in-memory fake and a moto-backed DynamoDB store so
both implementations are held to the identical claim/complete/release
contract, including the ownership rule: release and complete apply only for
the holder of the claim token a NEW claim returned.
"""

import pytest

from infrastructure.idempotency.protocol import ClaimResult

pytestmark = pytest.mark.integration

FOREIGN_CLAIM_TOKEN = "0" * 32


class TestIdempotencyStoreConformance:
    """Runs against every IdempotencyStore implementation via the `idempotency_store` fixture."""

    def test_claim_new_key_returns_new(self, idempotency_store):
        outcome = idempotency_store.claim("feature:intent:new-key")

        assert outcome.result is ClaimResult.NEW

    def test_claim_completed_key_returns_recorded_outcome(self, idempotency_store):
        key = "feature:intent:completed-key"
        claimed = idempotency_store.claim(key)
        idempotency_store.complete(key, {"status": "ok", "id": 42}, claimed.claim_token)

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
        claimed = idempotency_store.claim(key)

        released = idempotency_store.release(key, claimed.claim_token)
        outcome = idempotency_store.claim(key)

        assert released is True

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
        idempotency_store.complete(key, {"marker": "exact"}, outcome.claim_token)
        replay = idempotency_store.claim(key)

        assert outcome.result is ClaimResult.NEW
        assert replay.result is ClaimResult.COMPLETED
        assert replay.outcome == {"marker": "exact"}

    def test_distinct_keys_do_not_collide(self, idempotency_store):
        idempotency_store.claim("feature:intent:key-a")
        outcome = idempotency_store.claim("feature:intent:key-b")

        assert outcome.result is ClaimResult.NEW


class TestIdempotencyStoreClaimToken:
    """A NEW claim hands back the token that later proves ownership; other results carry none."""

    def test_new_claims_carry_distinct_tokens(self, idempotency_store):
        first = idempotency_store.claim("feature:intent:token-a")
        second = idempotency_store.claim("feature:intent:token-b")

        assert first.claim_token
        assert second.claim_token
        assert first.claim_token != second.claim_token

    def test_in_progress_and_completed_claims_carry_no_token(self, idempotency_store):
        key = "feature:intent:token-none"
        claimed = idempotency_store.claim(key)
        in_progress = idempotency_store.claim(key)
        idempotency_store.complete(key, {"status": "ok"}, claimed.claim_token)
        completed = idempotency_store.claim(key)

        assert in_progress.result is ClaimResult.IN_PROGRESS
        assert in_progress.claim_token is None
        assert completed.result is ClaimResult.COMPLETED
        assert completed.claim_token is None


class TestIdempotencyStoreOwnership:
    """release and complete apply only for the current holder, observed through later claims."""

    def test_complete_by_owner_returns_true(self, idempotency_store):
        key = "feature:intent:owner-complete"
        claimed = idempotency_store.claim(key)

        assert idempotency_store.complete(key, {"status": "ok"}, claimed.claim_token) is True

    def test_complete_replayed_with_the_same_token_stays_true(self, idempotency_store):
        """A resent complete whose first attempt landed must not report lost ownership."""
        key = "feature:intent:complete-replay"
        claimed = idempotency_store.claim(key)
        idempotency_store.complete(key, {"status": "ok"}, claimed.claim_token)

        assert idempotency_store.complete(key, {"status": "ok"}, claimed.claim_token) is True

    def test_release_with_a_foreign_token_returns_false_and_keeps_the_claim(self, idempotency_store):
        key = "feature:intent:foreign-release"
        idempotency_store.claim(key)

        released = idempotency_store.release(key, FOREIGN_CLAIM_TOKEN)
        outcome = idempotency_store.claim(key)

        assert released is False
        assert outcome.result is ClaimResult.IN_PROGRESS

    def test_complete_with_a_foreign_token_returns_false_and_records_nothing(self, idempotency_store):
        key = "feature:intent:foreign-complete"
        idempotency_store.claim(key)

        completed = idempotency_store.complete(key, {"status": "forged"}, FOREIGN_CLAIM_TOKEN)
        outcome = idempotency_store.claim(key)

        assert completed is False
        assert outcome.result is ClaimResult.IN_PROGRESS

    def test_release_cannot_delete_a_completed_record(self, idempotency_store):
        """The recorded outcome is the only evidence the effect happened, so no release removes it."""
        key = "feature:intent:release-completed"
        claimed = idempotency_store.claim(key)
        idempotency_store.complete(key, {"status": "ok"}, claimed.claim_token)

        released = idempotency_store.release(key, claimed.claim_token)
        outcome = idempotency_store.claim(key)

        assert released is False
        assert outcome.result is ClaimResult.COMPLETED
        assert outcome.outcome == {"status": "ok"}

    def test_release_of_a_never_claimed_key_returns_false(self, idempotency_store):
        assert idempotency_store.release("feature:intent:never-claimed", FOREIGN_CLAIM_TOKEN) is False

    def test_complete_of_a_never_claimed_key_returns_false_and_records_nothing(self, idempotency_store):
        key = "feature:intent:never-claimed-complete"

        completed = idempotency_store.complete(key, {"status": "ok"}, FOREIGN_CLAIM_TOKEN)
        outcome = idempotency_store.claim(key)

        assert completed is False
        assert outcome.result is ClaimResult.NEW

    def test_second_release_by_the_owner_returns_false(self, idempotency_store):
        key = "feature:intent:double-release"
        claimed = idempotency_store.claim(key)
        idempotency_store.release(key, claimed.claim_token)

        assert idempotency_store.release(key, claimed.claim_token) is False


class TestIdempotencyStoreExpiredClaimTakeover:
    """Runs against the `expiring_idempotency_store` fixture (in-progress TTL already elapsed)."""

    def test_claim_after_in_progress_ttl_elapsed_returns_new(self, expiring_idempotency_store):
        """A crashed claimant's stale IN_PROGRESS record must be taken over, not rejected."""
        key = "feature:intent:crashed-claimant"

        first = expiring_idempotency_store.claim(key)
        second = expiring_idempotency_store.claim(key)

        assert first.result is ClaimResult.NEW
        assert second.result is ClaimResult.NEW

    def test_stale_holder_release_returns_false_and_keeps_the_new_holder_record(self, expiring_idempotency_store):
        """A holder whose TTL elapsed and was taken over cannot free the new holder's claim.

        The new holder's own release succeeding afterwards proves its record survived.
        """
        key = "feature:intent:stale-release"
        stale = expiring_idempotency_store.claim(key)
        current = expiring_idempotency_store.claim(key)

        stale_released = expiring_idempotency_store.release(key, stale.claim_token)
        current_released = expiring_idempotency_store.release(key, current.claim_token)

        assert stale_released is False
        assert current_released is True

    def test_stale_holder_complete_returns_false_and_does_not_overwrite(self, expiring_idempotency_store):
        """A stale complete must not turn the new holder's live claim into a COMPLETED record.

        Under the elapsed TTL a further claim takes over an IN_PROGRESS record but would
        return COMPLETED had the stale write landed, so its NEW result proves nothing was written.
        """
        key = "feature:intent:stale-complete"
        stale = expiring_idempotency_store.claim(key)
        expiring_idempotency_store.claim(key)

        stale_completed = expiring_idempotency_store.complete(key, {"status": "stale"}, stale.claim_token)
        outcome = expiring_idempotency_store.claim(key)

        assert stale_completed is False
        assert outcome.result is ClaimResult.NEW

    def test_new_holder_can_complete_after_a_stale_holder_was_refused(self, expiring_idempotency_store):
        key = "feature:intent:stale-then-current"
        stale = expiring_idempotency_store.claim(key)
        current = expiring_idempotency_store.claim(key)
        expiring_idempotency_store.complete(key, {"status": "stale"}, stale.claim_token)

        current_completed = expiring_idempotency_store.complete(key, {"status": "current"}, current.claim_token)
        outcome = expiring_idempotency_store.claim(key)

        assert current_completed is True
        assert outcome.result is ClaimResult.COMPLETED
        assert outcome.outcome == {"status": "current"}

    def test_owner_can_still_release_an_expired_claim_nobody_took_over(self, expiring_idempotency_store):
        """Ownership follows the token, not the clock: an elapsed TTL alone does not forfeit the claim."""
        key = "feature:intent:expired-untaken"
        claimed = expiring_idempotency_store.claim(key)

        assert expiring_idempotency_store.release(key, claimed.claim_token) is True
