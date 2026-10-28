"""Unit tests for access sync platform_lock wrappers.

These tests validate feature-specific key naming and holder reporting while
lock correctness is delegated to the coordination LeaseStore facade.
"""

from unittest.mock import MagicMock

import pytest

from contracts.coordination import LeaseStore, ReadFailurePolicy
from infrastructure.coordination import InMemoryConditionalWriteStore
from packages.access.sync import platform_lock

pytestmark = pytest.mark.unit


def _store() -> LeaseStore:
    return LeaseStore(
        InMemoryConditionalWriteStore(record_ttl_seconds=3600, in_progress_ttl_seconds=300),
        read_failure_policy=ReadFailurePolicy.FAIL_CLOSED,
    )


def test_acquire_lock_succeeds_once_and_persists_holder_payload() -> None:
    job_status_store = MagicMock()
    lock_store = _store()
    payload = {
        "job_id": "job-123",
        "status": "running",
        "started_at": "2026-07-27T12:00:00+00:00",
        "dry_run": False,
    }
    job_status_store.get.return_value = payload

    claim_token = platform_lock.acquire_lock(
        lock_key="access_sync:user_lock:aws:alice@example.com",
        payload=payload,
        lock_store=lock_store,
        job_status_store=job_status_store,
        ttl_seconds=14400,
    )

    assert claim_token
    job_status_store.put.assert_called_once_with(
        "access_sync:user_lock:aws:alice@example.com:holder",
        payload,
        ttl_seconds=14400,
    )

    current_holder = getattr(platform_lock, "current_holder", None)
    assert callable(current_holder), "packages.access.sync.platform_lock.current_holder must exist"
    assert current_holder("access_sync:user_lock:aws:alice@example.com", job_status_store) == payload


def test_acquire_lock_rejects_second_claim_and_preserves_existing_holder() -> None:
    job_status_store = MagicMock()
    lock_store = _store()
    payload = {
        "job_id": "job-111",
        "status": "running",
        "started_at": "2026-07-27T12:00:00+00:00",
        "dry_run": False,
    }
    job_status_store.get.return_value = payload

    assert platform_lock.acquire_lock(
        lock_key="access_sync:platform_lock:aws",
        payload=payload,
        lock_store=lock_store,
        job_status_store=job_status_store,
        ttl_seconds=14400,
    )

    second = platform_lock.acquire_lock(
        lock_key="access_sync:platform_lock:aws",
        payload={"job_id": "job-222", "status": "running"},
        lock_store=lock_store,
        job_status_store=job_status_store,
        ttl_seconds=14400,
    )

    assert second is None
    job_status_store.put.assert_called_once()


def test_release_lock_allows_future_claim() -> None:
    job_status_store = MagicMock()
    lock_store = _store()
    key = "access_sync:platform_lock:aws"

    claim_token = platform_lock.acquire_lock(
        lock_key=key,
        payload={"job_id": "job-1", "status": "running"},
        lock_store=lock_store,
        job_status_store=job_status_store,
        ttl_seconds=14400,
    )
    assert claim_token is not None

    platform_lock.release_lock(lock_key=key, lock_store=lock_store, claim_token=claim_token)

    assert platform_lock.acquire_lock(
        lock_key=key,
        payload={"job_id": "job-2", "status": "running"},
        lock_store=lock_store,
        job_status_store=job_status_store,
        ttl_seconds=14400,
    )


def test_release_lock_with_a_foreign_token_keeps_the_lock() -> None:
    job_status_store = MagicMock()
    lock_store = _store()
    key = "access_sync:platform_lock:aws"
    platform_lock.acquire_lock(
        lock_key=key,
        payload={"job_id": "job-1", "status": "running"},
        lock_store=lock_store,
        job_status_store=job_status_store,
        ttl_seconds=14400,
    )

    platform_lock.release_lock(lock_key=key, lock_store=lock_store, claim_token="0" * 32)

    assert (
        platform_lock.acquire_lock(
            lock_key=key,
            payload={"job_id": "job-2", "status": "running"},
            lock_store=lock_store,
            job_status_store=job_status_store,
            ttl_seconds=14400,
        )
        is None
    )


def test_holder_record_never_contains_the_claim_token() -> None:
    """Pollers read the holder record, and the token must not leak to them."""
    job_status_store = MagicMock()
    lock_store = _store()
    payload = {"job_id": "job-1", "status": "running"}

    claim_token = platform_lock.acquire_lock(
        lock_key="access_sync:platform_lock:aws",
        payload=payload,
        lock_store=lock_store,
        job_status_store=job_status_store,
        ttl_seconds=14400,
    )

    assert claim_token is not None
    stored = job_status_store.put.call_args.args[1]
    assert claim_token not in repr(stored)


def test_platform_lock_no_longer_exports_legacy_check_lock() -> None:
    """Legacy read-then-acquire lock API should not be exposed anymore."""
    assert not hasattr(platform_lock, "check_lock")
