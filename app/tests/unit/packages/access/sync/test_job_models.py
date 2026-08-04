"""Unit tests for access sync transport job models."""

import pytest

from packages.access.sync.job_models import (
    CompletedPlatformRecord,
    CompletedUserRecord,
    FailedPlatformRecord,
    FailedUserRecord,
    JobStatus,
    PlatformRunningRecord,
    SyncJobError,
    UserRunningRecord,
)

# ---------------------------------------------------------------------------
# JobStatus / SyncJobError constants
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_job_status_has_expected_constants():
    """JobStatus should provide the four expected status strings."""
    assert JobStatus.RUNNING == "running"
    assert JobStatus.IN_PROGRESS == "in_progress"
    assert JobStatus.COMPLETED == "completed"
    assert JobStatus.FAILED == "failed"


@pytest.mark.unit
def test_sync_job_error_sanitizes_to_sync_failed():
    """SyncJobError.SYNC_FAILED must not contain internal detail."""
    assert SyncJobError.SYNC_FAILED == "sync_failed"


# ---------------------------------------------------------------------------
# UserRunningRecord
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_user_running_record_to_dict_contains_required_fields():
    """UserRunningRecord.to_dict() must include all fields the idempotency store expects."""
    record = UserRunningRecord(
        job_id="j-1",
        user_email="alice@example.com",
        platform="aws",
        dry_run=False,
        started_at="2026-04-21T00:00:00+00:00",
    )
    d = record.to_dict()
    assert d["job_id"] == "j-1"
    assert d["user_email"] == "alice@example.com"
    assert d["platform"] == "aws"
    assert d["dry_run"] is False
    assert d["status"] == JobStatus.RUNNING
    assert d["sync_type"] == "user"


@pytest.mark.unit
def test_user_running_record_is_immutable():
    """UserRunningRecord is frozen so it is safe to share across threads."""
    record = UserRunningRecord(
        job_id="j-1",
        user_email="alice@example.com",
        platform="aws",
        dry_run=False,
        started_at="2026-04-21T00:00:00+00:00",
    )
    with pytest.raises((AttributeError, TypeError)):
        record.job_id = "mutated"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# CompletedUserRecord
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_completed_user_record_to_dict_has_actions():
    """CompletedUserRecord must carry action lists in its dict representation."""
    record = CompletedUserRecord(
        job_id="j-2",
        user_email="bob@example.com",
        platform="aws",
        dry_run=False,
        started_at="2026-04-21T00:00:00+00:00",
        completed_at="2026-04-21T00:01:00+00:00",
        actions_planned=["provision_user", "apply_entitlement"],
        actions_applied=["provision_user", "apply_entitlement"],
        requires_manual_action=False,
    )
    d = record.to_dict()
    assert d["status"] == JobStatus.COMPLETED
    assert d["actions_planned"] == ["provision_user", "apply_entitlement"]
    assert d["actions_applied"] == ["provision_user", "apply_entitlement"]
    assert d["requires_manual_action"] is False


# ---------------------------------------------------------------------------
# FailedUserRecord
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_failed_user_record_uses_sanitized_error():
    """FailedUserRecord error field should contain the sanitized error string."""
    record = FailedUserRecord(
        job_id="j-3",
        user_email="carol@example.com",
        platform="aws",
        dry_run=True,
        started_at="2026-04-21T00:00:00+00:00",
        completed_at="2026-04-21T00:01:00+00:00",
        error=SyncJobError.SYNC_FAILED,
    )
    d = record.to_dict()
    assert d["status"] == JobStatus.FAILED
    assert d["error"] == "sync_failed"


# ---------------------------------------------------------------------------
# PlatformRunningRecord
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_platform_running_record_to_dict_does_not_include_user_email():
    """PlatformRunningRecord must not carry user-specific fields."""
    record = PlatformRunningRecord(
        job_id="j-4",
        platform="aws",
        dry_run=False,
        started_at="2026-04-21T00:00:00+00:00",
    )
    d = record.to_dict()
    assert "user_email" not in d
    assert d["sync_type"] == "platform"
    assert d["status"] == JobStatus.RUNNING


# ---------------------------------------------------------------------------
# CompletedPlatformRecord
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_completed_platform_record_carries_reconciliation_metrics():
    """CompletedPlatformRecord must include all reconciliation summary metrics."""
    record = CompletedPlatformRecord(
        job_id="j-5",
        platform="aws",
        dry_run=False,
        started_at="2026-04-21T00:00:00+00:00",
        completed_at="2026-04-21T00:10:00+00:00",
        users_synced=50,
        users_converged=5,
        orphans_found=2,
        requires_manual_action_count=1,
        changed_user_count=7,
        unchanged_user_count=43,
        action_counts={"apply_entitlement": 4, "remove_user": 2},
        lifecycle_actions={"remove_user": ["carol@example.com"]},
        entitlements_by_action={
            "apply_entitlement": {
                "sg-aws-admin": ["alice@example.com"],
            }
        },
    )
    d = record.to_dict()
    assert d["users_synced"] == 50
    assert d["users_converged"] == 5
    assert d["orphans_found"] == 2
    assert d["requires_manual_action_count"] == 1
    assert d["changed_user_count"] == 7
    assert d["unchanged_user_count"] == 43
    assert d["action_counts"]["apply_entitlement"] == 4
    assert d["lifecycle_actions"]["remove_user"] == ["carol@example.com"]
    assert d["entitlements_by_action"]["apply_entitlement"]["sg-aws-admin"] == ["alice@example.com"]
    assert d["status"] == JobStatus.COMPLETED


# ---------------------------------------------------------------------------
# FailedPlatformRecord
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_failed_platform_record_to_dict_structure():
    """FailedPlatformRecord must produce the expected dict layout."""
    record = FailedPlatformRecord(
        job_id="j-6",
        platform="aws",
        dry_run=False,
        started_at="2026-04-21T00:00:00+00:00",
        completed_at="2026-04-21T00:05:00+00:00",
        error=SyncJobError.SYNC_FAILED,
    )
    d = record.to_dict()
    assert d["status"] == JobStatus.FAILED
    assert d["platform"] == "aws"
    assert d["error"] == "sync_failed"
