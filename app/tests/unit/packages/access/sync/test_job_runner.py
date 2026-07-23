"""Unit tests for access sync transport job_runner module."""

from unittest.mock import MagicMock

import pytest

from infrastructure.operations import OperationResult, OperationStatus
from packages.access.sync.domain import ReconciliationOutcome, SyncOutcome
from packages.access.sync.job_models import JobStatus, SyncJobError
from packages.access.sync.job_runner import (
    run_platform_sync_job,
    run_user_sync_job,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_coordinator(result: OperationResult) -> MagicMock:
    coord = MagicMock()
    coord.sync_user.return_value = result
    coord.sync_platform.return_value = result
    return coord


# ---------------------------------------------------------------------------
# run_user_sync_job
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_run_user_sync_job_writes_completed_record_with_action_lists():
    """Completed user sync must write typed record with planned/applied lists."""
    idempotency = MagicMock()
    coordinator = _make_coordinator(
        OperationResult.success(
            data=SyncOutcome(
                planned_actions=["provision_user", "apply_entitlement"],
                applied_actions=["provision_user", "apply_entitlement"],
                requires_manual_action=False,
            )
        )
    )

    run_user_sync_job(
        coordinator=coordinator,
        idempotency=idempotency,
        job_id="job-completed-1",
        user_email="alice@example.com",
        platform="aws",
        dry_run=False,
        request_id="req-completed-1",
        started_at="2026-04-21T00:00:00+00:00",
        job_ttl_seconds=86400,
    )

    assert idempotency.set.call_count == 2
    job_args, _ = idempotency.set.call_args_list[0]
    record = job_args[1]
    assert record["status"] == JobStatus.COMPLETED
    assert record["actions_planned"] == ["provision_user", "apply_entitlement"]
    assert record["actions_applied"] == ["provision_user", "apply_entitlement"]
    assert record["requires_manual_action"] is False


@pytest.mark.unit
def test_run_user_sync_job_writes_failed_record_on_coordinator_failure():
    """Failed coordinator result must produce a typed failed record."""
    idempotency = MagicMock()
    coordinator = _make_coordinator(
        OperationResult.error(
            OperationStatus.TRANSIENT_ERROR,
            message="Directory API unreachable",
            error_code="DIRECTORY_ERROR",
        )
    )

    run_user_sync_job(
        coordinator=coordinator,
        idempotency=idempotency,
        job_id="job-fail-1",
        user_email="bob@example.com",
        platform="aws",
        dry_run=False,
        request_id="req-fail-1",
        started_at="2026-04-21T00:00:00+00:00",
        job_ttl_seconds=86400,
    )

    job_args, _ = idempotency.set.call_args_list[0]
    record = job_args[1]
    assert record["status"] == JobStatus.FAILED
    assert "error" in record


@pytest.mark.unit
def test_run_user_sync_job_sanitizes_exception_to_sync_failed():
    """Unhandled exceptions must be sanitized — internal detail must not appear in the record."""
    idempotency = MagicMock()
    coordinator = MagicMock()
    coordinator.sync_user.side_effect = RuntimeError("internal database credential")

    run_user_sync_job(
        coordinator=coordinator,
        idempotency=idempotency,
        job_id="job-exc-1",
        user_email="carol@example.com",
        platform="aws",
        dry_run=False,
        request_id="req-exc-1",
        started_at="2026-04-21T00:00:00+00:00",
        job_ttl_seconds=86400,
    )

    job_args, _ = idempotency.set.call_args_list[0]
    record = job_args[1]
    assert record["status"] == JobStatus.FAILED
    assert record["error"] == SyncJobError.SYNC_FAILED
    assert "credential" not in record.get("error", "")


@pytest.mark.unit
def test_run_user_sync_job_releases_lock_after_completion():
    """After completion the user lock key must also be updated."""
    idempotency = MagicMock()
    coordinator = _make_coordinator(
        OperationResult.success(
            data=SyncOutcome(
                planned_actions=[],
                applied_actions=[],
                requires_manual_action=False,
            )
        )
    )

    run_user_sync_job(
        coordinator=coordinator,
        idempotency=idempotency,
        job_id="job-lock-1",
        user_email="dave@example.com",
        platform="aws",
        dry_run=False,
        request_id="req-lock-1",
        started_at="2026-04-21T00:00:00+00:00",
        job_ttl_seconds=86400,
    )

    lock_args, _ = idempotency.set.call_args_list[1]
    assert "access_sync:user_lock:aws:dave@example.com" in lock_args[0]


# ---------------------------------------------------------------------------
# run_platform_sync_job
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_run_platform_sync_job_writes_in_progress_sentinel_then_completed():
    """Platform sync must write in_progress first, then final completed record."""
    idempotency = MagicMock()
    coordinator = _make_coordinator(
        OperationResult.success(
            data=ReconciliationOutcome(
                platform="aws",
                users_synced=10,
                users_converged=3,
                orphans_found=1,
                requires_manual_action_count=0,
                changed_user_count=4,
                unchanged_user_count=6,
                action_counts={"apply_entitlement": 2, "remove_user": 1},
                lifecycle_actions={"remove_user": ["carol@example.com"]},
                entitlements_by_action={
                    "apply_entitlement": {
                        "sg-aws-admin": ["alice@example.com"],
                    }
                },
            )
        )
    )

    run_platform_sync_job(
        coordinator=coordinator,
        idempotency=idempotency,
        job_id="plat-job-1",
        platform="aws",
        dry_run=False,
        request_id="plat-req-1",
        started_at="2026-04-21T00:00:00+00:00",
        job_ttl_seconds=86400,
    )

    # Calls: sentinel (in_progress), final record, lock release
    assert idempotency.set.call_count == 3

    sentinel_args, _ = idempotency.set.call_args_list[0]
    assert sentinel_args[1]["status"] == JobStatus.IN_PROGRESS

    final_args, _ = idempotency.set.call_args_list[1]
    final = final_args[1]
    assert final["status"] == JobStatus.COMPLETED
    assert final["users_synced"] == 10
    assert final["users_converged"] == 3
    assert final["orphans_found"] == 1
    assert final["changed_user_count"] == 4
    assert final["unchanged_user_count"] == 6
    assert final["action_counts"]["apply_entitlement"] == 2
    assert final["lifecycle_actions"]["remove_user"] == ["carol@example.com"]
    assert final["entitlements_by_action"]["apply_entitlement"]["sg-aws-admin"] == ["alice@example.com"]


@pytest.mark.unit
def test_run_platform_sync_job_releases_platform_lock_on_failure():
    """Platform lock must be released even when the sync fails."""
    idempotency = MagicMock()
    coordinator = _make_coordinator(
        OperationResult.error(
            OperationStatus.PERMANENT_ERROR,
            message="Adapter not configured",
            error_code="ADAPTER_NOT_FOUND",
        )
    )

    run_platform_sync_job(
        coordinator=coordinator,
        idempotency=idempotency,
        job_id="plat-fail-1",
        platform="aws",
        dry_run=False,
        request_id="plat-req-2",
        started_at="2026-04-21T00:00:00+00:00",
        job_ttl_seconds=86400,
    )

    lock_args, _ = idempotency.set.call_args_list[-1]
    assert "platform_lock" in lock_args[0]
    assert lock_args[1]["status"] == JobStatus.FAILED


@pytest.mark.unit
def test_run_platform_sync_job_sanitizes_exception_to_sync_failed():
    """Unhandled exceptions in platform sync must be sanitized."""
    idempotency = MagicMock()
    coordinator = MagicMock()
    coordinator.sync_platform.side_effect = ConnectionError("network down")

    run_platform_sync_job(
        coordinator=coordinator,
        idempotency=idempotency,
        job_id="plat-exc-1",
        platform="aws",
        dry_run=False,
        request_id="plat-req-3",
        started_at="2026-04-21T00:00:00+00:00",
        job_ttl_seconds=86400,
    )

    # Find the final (non-sentinel) set call for the job record
    final_args, _ = idempotency.set.call_args_list[-2]
    record = final_args[1]
    assert record["status"] == JobStatus.FAILED
    assert record["error"] == SyncJobError.SYNC_FAILED
    assert "network down" not in record.get("error", "")
