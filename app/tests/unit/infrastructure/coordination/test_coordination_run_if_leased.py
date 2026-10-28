"""Unit tests for run_if_leased, the host's lease enforcement around a job.

Lease correctness comes from the LeaseStore facade over the real in-memory
primitive, so these tests cover only acquire-run-release orchestration: skip when
held, release on failure, takeover after expiry, and no release of a lease that a
second holder took over mid-run.
"""

from unittest.mock import MagicMock

import pytest

from contracts.coordination import ClaimOutcome, ClaimResult, LeaseStore, ReadFailurePolicy
from infrastructure.coordination import InMemoryConditionalWriteStore, run_if_leased

pytestmark = pytest.mark.unit

NAME = "scheduler:test_job"


def _lease_store(in_progress_ttl_seconds: int = 300) -> LeaseStore:
    return LeaseStore(
        InMemoryConditionalWriteStore(record_ttl_seconds=3600, in_progress_ttl_seconds=in_progress_ttl_seconds),
        read_failure_policy=ReadFailurePolicy.FAIL_CLOSED,
    )


def test_run_if_leased_executes_job_when_acquired() -> None:
    job = MagicMock()

    run_if_leased(_lease_store(), NAME, job)

    job.assert_called_once()


def test_run_if_leased_skips_job_when_lease_held() -> None:
    lease_store = _lease_store()
    assert lease_store.acquire(NAME) is not None
    job = MagicMock()

    run_if_leased(lease_store, NAME, job)

    job.assert_not_called()


def test_run_if_leased_skips_job_and_release_when_claim_is_indeterminate() -> None:
    """A fail-closed INDETERMINATE claim runs nothing and releases nothing."""
    store = MagicMock()
    store.claim.return_value = ClaimOutcome(result=ClaimResult.INDETERMINATE)
    job = MagicMock()

    run_if_leased(LeaseStore(store, read_failure_policy=ReadFailurePolicy.FAIL_CLOSED), NAME, job)

    job.assert_not_called()
    store.release.assert_not_called()


def test_run_if_leased_releases_lease_even_on_job_exception() -> None:
    lease_store = _lease_store()

    def failing_job() -> None:
        raise ValueError("Job failed")

    with pytest.raises(ValueError, match="Job failed"):
        run_if_leased(lease_store, NAME, failing_job)

    successful_job = MagicMock()
    run_if_leased(lease_store, NAME, successful_job)
    successful_job.assert_called_once()


def test_run_if_leased_takes_over_expired_lease() -> None:
    lease_store = _lease_store(in_progress_ttl_seconds=0)
    first_job = MagicMock()
    second_job = MagicMock()

    run_if_leased(lease_store, NAME, first_job)
    run_if_leased(lease_store, NAME, second_job)

    first_job.assert_called_once()
    second_job.assert_called_once()


def test_run_if_leased_does_not_release_a_lease_taken_over_mid_run() -> None:
    """A job that outlives its TTL must not free the lease a second holder took over.

    The second holder's own release succeeding afterwards proves the record survived.
    """
    lease_store = _lease_store(in_progress_ttl_seconds=-1)
    takeover_tokens: list[str | None] = []

    def job_overtaken_mid_run() -> None:
        takeover_tokens.append(lease_store.acquire(NAME))

    run_if_leased(lease_store, NAME, job_overtaken_mid_run)

    [takeover_token] = takeover_tokens
    assert takeover_token is not None
    assert lease_store.release(NAME, takeover_token) is True
