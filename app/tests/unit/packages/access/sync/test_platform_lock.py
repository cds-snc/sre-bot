"""Unit tests for access sync platform_lock wrappers.

These tests validate feature-specific key naming and holder reporting while
lock correctness is delegated to shared infrastructure lease helpers.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from infrastructure.idempotency import IdempotencySettings, InMemoryIdempotencyStore
from packages.access.sync import platform_lock

pytestmark = pytest.mark.unit


def _store() -> InMemoryIdempotencyStore:
    settings = IdempotencySettings(IDEMPOTENCY_TTL_SECONDS=3600, IDEMPOTENCY_IN_PROGRESS_TTL_SECONDS=300)
    return InMemoryIdempotencyStore(idempotency_settings=settings)


def test_acquire_lock_succeeds_once_and_persists_holder_payload() -> None:
    idempotency = MagicMock()
    lock_store = _store()
    payload = {
        "job_id": "job-123",
        "status": "running",
        "started_at": "2026-07-27T12:00:00+00:00",
        "dry_run": False,
    }
    idempotency.get.return_value = payload

    acquired = platform_lock.acquire_lock(
        lock_key="access_sync:user_lock:aws:alice@example.com",
        payload=payload,
        lock_store=lock_store,
        idempotency=idempotency,
        ttl_seconds=14400,
    )

    assert acquired is True
    idempotency.set.assert_called_once_with(
        "access_sync:user_lock:aws:alice@example.com:holder",
        payload,
        ttl_seconds=14400,
    )

    current_holder = getattr(platform_lock, "current_holder", None)
    assert callable(current_holder), "packages.access.sync.platform_lock.current_holder must exist"
    assert current_holder("access_sync:user_lock:aws:alice@example.com", idempotency) == payload


def test_acquire_lock_rejects_second_claim_and_preserves_existing_holder() -> None:
    idempotency = MagicMock()
    lock_store = _store()
    payload = {
        "job_id": "job-111",
        "status": "running",
        "started_at": "2026-07-27T12:00:00+00:00",
        "dry_run": False,
    }
    idempotency.get.return_value = payload

    assert (
        platform_lock.acquire_lock(
            lock_key="access_sync:platform_lock:aws",
            payload=payload,
            lock_store=lock_store,
            idempotency=idempotency,
            ttl_seconds=14400,
        )
        is True
    )

    second = platform_lock.acquire_lock(
        lock_key="access_sync:platform_lock:aws",
        payload={"job_id": "job-222", "status": "running"},
        lock_store=lock_store,
        idempotency=idempotency,
        ttl_seconds=14400,
    )

    assert second is False
    idempotency.set.assert_called_once()


def test_release_lock_allows_future_claim() -> None:
    idempotency = MagicMock()
    lock_store = _store()
    key = "access_sync:platform_lock:aws"

    assert platform_lock.acquire_lock(
        lock_key=key,
        payload={"job_id": "job-1", "status": "running"},
        lock_store=lock_store,
        idempotency=idempotency,
        ttl_seconds=14400,
    )

    platform_lock.release_lock(lock_key=key, lock_store=lock_store)

    assert platform_lock.acquire_lock(
        lock_key=key,
        payload={"job_id": "job-2", "status": "running"},
        lock_store=lock_store,
        idempotency=idempotency,
        ttl_seconds=14400,
    )


def test_platform_lock_no_longer_exports_legacy_check_lock() -> None:
    """Legacy read-then-acquire lock API should not be exposed anymore."""
    assert not hasattr(platform_lock, "check_lock")
