"""The lock's claim token travels from ingress admission into the spawned sync job.

Ingress runs against a real in-memory lock store with the thread spawn helpers
patched out, so the test can read the claim token handed to the background job
and prove it is the one that owns the lock: releasing with it succeeds.
"""

from dataclasses import dataclass
from unittest.mock import MagicMock, patch

import pytest

from contracts.coordination import LeaseStore, ReadFailurePolicy
from infrastructure.coordination import InMemoryConditionalWriteStore
from packages.access.sync.interactions.ingress import enqueue_platform_sync, enqueue_user_sync
from packages.access.sync.platform_lock import platform_lock_key, user_lock_key

pytestmark = pytest.mark.unit


@dataclass(frozen=True)
class _Settings:
    job_ttl_seconds: int = 14400


def _lock_store() -> LeaseStore:
    return LeaseStore(InMemoryConditionalWriteStore(record_ttl_seconds=3600, in_progress_ttl_seconds=300), read_failure_policy=ReadFailurePolicy.FAIL_CLOSED)


def test_enqueue_user_sync_hands_the_lock_owner_token_to_the_job() -> None:
    lock_store = _lock_store()

    with patch("packages.access.sync.interactions.ingress.spawn_user_sync_thread") as spawn:
        enqueue_user_sync(
            coordinator=MagicMock(),
            job_status_store=MagicMock(),
            lock_store=lock_store,
            settings=_Settings(),
            user_email="alice@example.com",
            platform="aws",
        )

    claim_token = spawn.call_args.kwargs["claim_token"]
    assert lock_store.release(user_lock_key("aws", "alice@example.com"), claim_token) is True


def test_enqueue_platform_sync_hands_the_lock_owner_token_to_the_job() -> None:
    lock_store = _lock_store()

    with patch("packages.access.sync.interactions.ingress.spawn_platform_sync_thread") as spawn:
        enqueue_platform_sync(
            coordinator=MagicMock(),
            job_status_store=MagicMock(),
            lock_store=lock_store,
            settings=_Settings(),
            platform="aws",
        )

    claim_token = spawn.call_args.kwargs["claim_token"]
    assert lock_store.release(platform_lock_key("aws"), claim_token) is True
