"""Unit tests for access sync transport presenters."""

from typing import Any

import pytest

from packages.access.sync.job_models import JobStatus
from packages.access.sync.presenters import (
    to_http_status_response,
    to_slack_status_message,
)
from packages.access.sync.schemas import SyncJobStatusResponse

# ---------------------------------------------------------------------------
# to_http_status_response
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_to_http_status_response_maps_completed_platform_record():
    """Should return a SyncJobStatusResponse for a completed platform job."""
    record = {
        "job_id": "j-1",
        "platform": "aws",
        "sync_type": "platform",
        "dry_run": False,
        "status": JobStatus.COMPLETED,
        "started_at": "2026-04-21T00:00:00+00:00",
        "completed_at": "2026-04-21T00:10:00+00:00",
        "users_synced": 20,
        "users_converged": 3,
        "orphans_found": 1,
        "requires_manual_action_count": 0,
    }
    response = to_http_status_response(record)
    assert response.job_id == "j-1"
    assert response.status == JobStatus.COMPLETED
    assert response.users_synced == 20
    assert response.users_converged == 3
    assert response.orphans_found == 1


@pytest.mark.unit
def test_to_http_status_response_maps_completed_user_record():
    """Should return a SyncJobStatusResponse for a completed user job."""
    record = {
        "job_id": "j-2",
        "platform": "aws",
        "sync_type": "user",
        "user_email": "alice@example.com",
        "dry_run": False,
        "status": JobStatus.COMPLETED,
        "started_at": "2026-04-21T00:00:00+00:00",
        "completed_at": "2026-04-21T00:01:00+00:00",
        "actions_planned": ["provision_user"],
        "actions_applied": ["provision_user"],
        "requires_manual_action": False,
    }
    response = to_http_status_response(record)
    assert response.job_id == "j-2"
    assert response.status == JobStatus.COMPLETED
    assert response.user_email == "alice@example.com"
    assert response.actions_applied == ["provision_user"]


@pytest.mark.unit
def test_to_http_status_response_maps_failed_record():
    """Should return a SyncJobStatusResponse for a failed job."""
    record = {
        "job_id": "j-3",
        "platform": "aws",
        "dry_run": False,
        "status": JobStatus.FAILED,
        "started_at": "2026-04-21T00:00:00+00:00",
        "completed_at": "2026-04-21T00:01:00+00:00",
        "error": "sync_failed",
    }
    response = to_http_status_response(record)
    assert response.status == JobStatus.FAILED
    assert response.error == "sync_failed"


# ---------------------------------------------------------------------------
# to_slack_status_message — in_progress
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_to_slack_status_message_in_progress_contains_job_id():
    """In-progress status message must include the job ID."""
    record: dict[str, Any] = {
        "job_id": "j-4",
        "platform": "aws",
        "dry_run": False,
        "status": JobStatus.IN_PROGRESS,
        "started_at": "2026-04-21T00:00:00+00:00",
    }
    message = to_slack_status_message(SyncJobStatusResponse(**record), locale="en-US")
    assert "j-4" in message


# ---------------------------------------------------------------------------
# to_slack_status_message — completed platform
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_to_slack_status_message_completed_platform_contains_metrics():
    """Completed platform status message must include reconciliation metrics."""
    record: dict[str, Any] = {
        "job_id": "j-5",
        "platform": "aws",
        "sync_type": "platform",
        "dry_run": False,
        "status": JobStatus.COMPLETED,
        "started_at": "2026-04-21T00:00:00+00:00",
        "completed_at": "2026-04-21T00:10:00+00:00",
        "users_synced": 50,
        "users_converged": 5,
        "orphans_found": 2,
        "requires_manual_action_count": 1,
        "changed_user_count": 9,
        "unchanged_user_count": 41,
        "action_counts": {
            "apply_entitlement": 3,
            "provision_user": 2,
            "remove_user": 1,
            "disable_user": 0,
            "remove_entitlement": 0,
        },
        "lifecycle_actions": {
            "provision_user": ["alice@example.com"],
            "remove_user": ["carol@example.com"],
            "disable_user": [],
        },
        "entitlements_by_action": {
            "apply_entitlement": {
                "sg-aws-admin": ["alice@example.com", "bob@example.com"],
            },
            "remove_entitlement": {},
        },
    }
    message = to_slack_status_message(SyncJobStatusResponse(**record), locale="en-US")
    assert "j-5" in message
    assert "50" in message
    assert "Changed: 9" in message
    assert "Users to provision (1): alice@example.com" in message
    assert "Entitlement adds" in message
    assert "sg-aws-admin" in message


# ---------------------------------------------------------------------------
# to_slack_status_message — completed user
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_to_slack_status_message_completed_user_contains_email():
    """Completed user status message must include the user email."""
    record: dict[str, Any] = {
        "job_id": "j-6",
        "platform": "aws",
        "sync_type": "user",
        "user_email": "alice@example.com",
        "dry_run": False,
        "status": JobStatus.COMPLETED,
        "started_at": "2026-04-21T00:00:00+00:00",
        "completed_at": "2026-04-21T00:01:00+00:00",
        "actions_planned": ["provision_user", "apply_entitlement"],
        "actions_applied": ["provision_user"],
        "requires_manual_action": False,
    }
    message = to_slack_status_message(SyncJobStatusResponse(**record), locale="en-US")
    assert "alice@example.com" in message
    assert "j-6" in message
    assert "Actions planned: 2 | Applied: 1" in message
    assert "Planned actions:" in message


# ---------------------------------------------------------------------------
# to_slack_status_message — failed
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_to_slack_status_message_failed_contains_error():
    """Failed status message must include the error string."""
    record: dict[str, Any] = {
        "job_id": "j-7",
        "platform": "aws",
        "dry_run": False,
        "status": JobStatus.FAILED,
        "error": "sync_failed",
    }
    message = to_slack_status_message(SyncJobStatusResponse(**record), locale="en-US")
    assert "sync_failed" in message
    assert "j-7" in message


# ---------------------------------------------------------------------------
# to_slack_status_message — unknown status
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_to_slack_status_message_unknown_status_does_not_raise():
    """Unknown status must not raise — it should return a fallback message."""
    record: dict[str, Any] = {
        "job_id": "j-8",
        "platform": "aws",
        "dry_run": False,
        "status": "weird_unknown_status",
    }
    message = to_slack_status_message(SyncJobStatusResponse(**record), locale="en-US")
    assert isinstance(message, str)
    assert len(message) > 0
