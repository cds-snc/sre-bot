"""Unit tests for access sync route handlers."""

import pytest
from unittest.mock import MagicMock, patch
from fastapi import Response

from infrastructure.identity.models import IdentitySource, User
from infrastructure.operations import OperationResult, OperationStatus
from packages.access.sync.transport.routes import sync_endpoint, _run_user_sync_job
from packages.access.sync.schemas import UserSyncRequest


class _FakeCoordinator:
    """Minimal coordinator stub that satisfies AccessSyncCoordinatorPort."""

    def __init__(self, result: OperationResult) -> None:
        self._result = result

    def sync_user(
        self,
        user_email: str,
        platform: str,
        dry_run: bool = False,
        request_id: str = "",
    ) -> OperationResult:
        return self._result

    def sync_platform(
        self,
        platform: str,
        dry_run: bool = False,
        request_id: str = "",
    ) -> OperationResult:
        return self._result


class _Settings:
    """Minimal settings stub satisfying the _AccessSyncSettingsPort protocol."""

    def __init__(self, enabled: bool) -> None:
        self.enabled = enabled
        self.sync_job_ttl_seconds = 86400
        self.sync_lock_stale_after_seconds = 14400


def _make_request() -> UserSyncRequest:
    """Create a valid user-sync request payload."""
    return UserSyncRequest(
        sync_type="user",
        user_email="user@example.com",
        platform="aws",
        dry_run=False,
        request_id="test-request",
    )


def _make_user() -> User:
    """Create a stub authenticated user for direct route invocation."""
    return User(
        user_id="svc-account@example.com",
        email="svc-account@example.com",
        display_name="Test Service Account",
        source=IdentitySource.API_JWT,
        platform_id="svc-account",
    )


@pytest.mark.unit
def test_sync_endpoint_user_sync_enqueues_job_and_returns_202():
    """User sync should enqueue a background job and return 202 with a job_id."""
    fake_idempotency = MagicMock()
    fake_idempotency.get.return_value = None  # no existing lock

    with (
        patch(
            "packages.access.sync.transport.routes.get_idempotency_service",
            return_value=fake_idempotency,
        ),
        patch(
            "packages.access.sync.transport.routes.threading",
        ) as mock_threading,
    ):
        mock_threading.Thread.return_value.start = MagicMock()
        response = Response()
        result = sync_endpoint(
            _make_request(),
            response=response,
            coordinator=_FakeCoordinator(OperationResult.success()),
            settings=_Settings(enabled=True),
            current_user=_make_user(),
        )

    assert response.status_code == 202
    assert result.success is True
    assert result.status == "in_progress"
    assert result.job_id != ""
    assert result.platform == "aws"
    assert result.user_email == "user@example.com"
    mock_threading.Thread.return_value.start.assert_called_once()


@pytest.mark.unit
def test_sync_endpoint_user_sync_returns_existing_job_when_lock_held():
    """When a user sync lock is active, return the existing job without spawning a new thread."""
    existing_job_id = "existing-job-123"
    fake_idempotency = MagicMock()
    # Mocking the lock record.
    fake_idempotency.get.return_value = {
        "job_id": existing_job_id,
        "status": "running",
        "started_at": "2026-04-20T10:00:00+00:00",
        "dry_run": False,
    }

    with (
        patch(
            "packages.access.sync.transport.routes.get_idempotency_service",
            return_value=fake_idempotency,
        ),
        patch(
            "packages.access.sync.transport.routes.check_lock",
            return_value=fake_idempotency.get.return_value,
        ),
        patch(
            "packages.access.sync.transport.routes.threading",
        ) as mock_threading,
    ):
        response = Response()
        result = sync_endpoint(
            _make_request(),
            response=response,
            coordinator=_FakeCoordinator(OperationResult.success()),
            settings=_Settings(enabled=True),
            current_user=_make_user(),
        )

    assert response.status_code == 202
    assert result.job_id == existing_job_id
    assert result.status == "in_progress"
    mock_threading.Thread.assert_not_called()


@pytest.mark.unit
def test_run_user_sync_job_stores_completed_outcome():
    """Background job should store completed status with action details."""
    from packages.access.sync.domain import SyncOutcome

    fake_idempotency = MagicMock()
    coordinator = _FakeCoordinator(
        OperationResult.success(
            data=SyncOutcome(
                planned_actions=["provision_user"],
                applied_actions=["provision_user"],
                requires_manual_action=False,
            )
        )
    )

    _run_user_sync_job(
        coordinator=coordinator,
        idempotency=fake_idempotency,
        job_id="job-1",
        user_email="user@example.com",
        platform="aws",
        dry_run=False,
        request_id="req-1",
        started_at="2026-04-20T10:00:00+00:00",
        job_ttl_seconds=86400,
    )

    # It's called twice: once for the job ID and once for the platform+user lock key.
    assert fake_idempotency.set.call_count == 2

    # Check the first call (job outcome)
    args, _ = fake_idempotency.set.call_args_list[0]
    assert args[0] == "job-1"
    stored = args[1]
    assert stored["status"] == "completed"
    assert stored["actions_applied"] == ["provision_user"]
    assert stored["user_email"] == "user@example.com"

    # Check the second call (releasing the user lock)
    args, _ = fake_idempotency.set.call_args_list[1]
    assert args[0] == "access_sync:user_lock:aws:user@example.com"
    assert args[1]["status"] == "completed"


@pytest.mark.unit
def test_run_user_sync_job_stores_failed_outcome_on_error():
    """Background job should store failed status when coordinator returns an error."""
    fake_idempotency = MagicMock()
    coordinator = _FakeCoordinator(
        OperationResult.error(
            OperationStatus.TRANSIENT_ERROR,
            message="IDP timeout",
            error_code="TIMEOUT",
        )
    )

    _run_user_sync_job(
        coordinator=coordinator,
        idempotency=fake_idempotency,
        job_id="job-2",
        user_email="user@example.com",
        platform="aws",
        dry_run=False,
        request_id="req-2",
        started_at="2026-04-20T10:00:00+00:00",
        job_ttl_seconds=86400,
    )

    # It's called twice: once for the job ID and once for the platform+user lock key.
    assert fake_idempotency.set.call_count == 2

    # Check the first call (job outcome)
    args, _ = fake_idempotency.set.call_args_list[0]
    assert args[0] == "job-2"
    stored = args[1]
    assert stored["status"] == "failed"
    assert "error" in stored

    # Check the second call (releasing the user lock)
    args, _ = fake_idempotency.set.call_args_list[1]
    assert args[0] == "access_sync:user_lock:aws:user@example.com"
    assert args[1]["status"] == "failed"


@pytest.mark.unit
def test_run_user_sync_job_stores_failed_outcome_on_exception():
    """Background job should store failed status and not propagate exceptions."""
    fake_idempotency = MagicMock()
    coordinator = MagicMock()
    coordinator.sync_user.side_effect = RuntimeError("unexpected crash")

    _run_user_sync_job(
        coordinator=coordinator,
        idempotency=fake_idempotency,
        job_id="job-3",
        user_email="user@example.com",
        platform="aws",
        dry_run=False,
        request_id="req-3",
        started_at="2026-04-20T10:00:00+00:00",
        job_ttl_seconds=86400,
    )

    assert fake_idempotency.set.call_count == 2
    args, _ = fake_idempotency.set.call_args_list[0]
    assert args[0] == "job-3"
    assert args[1]["status"] == "failed"
    assert "error" in args[1]
