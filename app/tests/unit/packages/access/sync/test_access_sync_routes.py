"""Unit tests for access sync route handlers and job runner."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI, HTTPException, Response
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from infrastructure.operations import OperationResult, OperationStatus
from infrastructure.security import get_current_user
from infrastructure.security.models import AuthPrincipalSource, User
from packages.access.sync.domain import SyncOutcome
from packages.access.sync.interactions.http import router, sync_endpoint
from packages.access.sync.job_runner import run_user_sync_job
from packages.access.sync.providers import (
    get_access_sync_coordinator,
    get_access_sync_settings,
)
from packages.access.sync.schemas import UserSyncRequest


def _get_route(path: str, method: str) -> APIRoute:
    for route in router.routes:
        if isinstance(route, APIRoute) and route.path == path and method in route.methods:
            return route
    raise AssertionError(f"Route {method} {path} not found")


class _FakeCoordinator:
    """Minimal stub that satisfies the access sync application service port."""

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
        self.job_ttl_seconds = 86400
        self.lock_stale_seconds = 14400


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
        source=AuthPrincipalSource.API_JWT,
        platform_id="svc-account",
    )


# ---------------------------------------------------------------------------
# Route handler tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_sync_endpoint_user_sync_enqueues_job_and_returns_202():
    """User sync should enqueue a background job and return 202 with a job_id."""
    fake_idempotency = MagicMock()
    fake_idempotency.get.return_value = None  # no existing lock

    with (
        patch(
            "packages.access.sync.interactions.http.get_idempotency_service",
            return_value=fake_idempotency,
        ),
        patch(
            "packages.access.sync.job_runner.threading",
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
    fake_idempotency.get.return_value = {
        "job_id": existing_job_id,
        "status": "running",
        "started_at": "2026-04-20T10:00:00+00:00",
        "dry_run": False,
    }

    with (
        patch(
            "packages.access.sync.interactions.http.get_idempotency_service",
            return_value=fake_idempotency,
        ),
        patch(
            "packages.access.sync.interactions.ingress.check_lock",
            return_value=fake_idempotency.get.return_value,
        ),
        patch(
            "packages.access.sync.job_runner.threading",
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
def test_sync_endpoint_returns_503_when_disabled():
    """Sync endpoint should return 503 when the feature flag is disabled."""

    fake_idempotency = MagicMock()
    with (
        patch(
            "packages.access.sync.interactions.http.get_idempotency_service",
            return_value=fake_idempotency,
        ),
        pytest.raises(HTTPException) as exc_info,
    ):
        sync_endpoint(
            _make_request(),
            response=Response(),
            coordinator=_FakeCoordinator(OperationResult.success()),
            settings=_Settings(enabled=False),
            current_user=_make_user(),
        )

    assert exc_info.value.status_code == 503


@pytest.mark.unit
def test_sync_endpoint_returns_503_without_coordinator_dependency_assembly():
    app = FastAPI()
    app.include_router(router)

    coordinator_provider_called = False

    def _coordinator_provider() -> _FakeCoordinator:
        nonlocal coordinator_provider_called
        coordinator_provider_called = True
        raise AssertionError("coordinator dependency should not be assembled")

    app.dependency_overrides[get_access_sync_settings] = lambda: _Settings(enabled=False)
    app.dependency_overrides[get_access_sync_coordinator] = _coordinator_provider
    app.dependency_overrides[get_current_user] = _make_user

    client = TestClient(app)
    response = client.post(
        "/access/sync-runs",
        json={
            "sync_type": "user",
            "user_email": "user@example.com",
            "platform": "aws",
            "dry_run": False,
            "request_id": "req-1",
        },
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "Access Sync is not enabled"
    assert coordinator_provider_called is False


@pytest.mark.unit
def test_access_sync_routes_expose_explicit_openapi_metadata() -> None:
    cases = [
        ("/access/sync-runs", "POST", 202, {503}),
        ("/access/sync-runs/{job_id}", "GET", 200, {404}),
    ]

    for path, method, expected_status, expected_non_2xx_codes in cases:
        route = _get_route(path, method)

        assert route.summary
        assert route.description
        assert route.status_code == expected_status

        documented_codes = {int(code) for code in route.responses}
        assert expected_non_2xx_codes.issubset(documented_codes)


# ---------------------------------------------------------------------------
# job_runner tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_run_user_sync_job_stores_completed_outcome():
    """Background job should store completed status with action details."""
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

    run_user_sync_job(
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

    # Called twice: once for the job-id record and once for the lock key.
    assert fake_idempotency.set.call_count == 2

    # Check job outcome record
    args, _ = fake_idempotency.set.call_args_list[0]
    assert args[0] == "job-1"
    stored = args[1]
    assert stored["status"] == "completed"
    assert stored["actions_applied"] == ["provision_user"]
    assert stored["user_email"] == "user@example.com"

    # Check lock release record
    args, _ = fake_idempotency.set.call_args_list[1]
    assert args[0] == "access_sync:user_lock:aws:user@example.com"
    assert args[1]["status"] == "completed"


@pytest.mark.unit
def test_run_user_sync_job_stores_failed_outcome_on_coordinator_error():
    """Background job should store failed status when coordinator returns an error."""
    fake_idempotency = MagicMock()
    coordinator = _FakeCoordinator(
        OperationResult.error(
            OperationStatus.TRANSIENT_ERROR,
            message="IDP timeout",
            error_code="TIMEOUT",
        )
    )

    run_user_sync_job(
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

    assert fake_idempotency.set.call_count == 2

    args, _ = fake_idempotency.set.call_args_list[0]
    assert args[0] == "job-2"
    stored = args[1]
    assert stored["status"] == "failed"
    assert "error" in stored

    args, _ = fake_idempotency.set.call_args_list[1]
    assert args[0] == "access_sync:user_lock:aws:user@example.com"
    assert args[1]["status"] == "failed"


@pytest.mark.unit
def test_run_user_sync_job_stores_failed_outcome_on_exception():
    """Background job should store failed status and not propagate exceptions."""
    fake_idempotency = MagicMock()
    coordinator = MagicMock()
    coordinator.sync_user.side_effect = RuntimeError("unexpected crash")

    run_user_sync_job(
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
    assert args[1]["error"] == "sync_failed"


@pytest.mark.unit
def test_run_user_sync_job_sanitizes_error_to_sync_failed_on_exception():
    """Exception details must never appear in the external error payload."""
    fake_idempotency = MagicMock()
    coordinator = MagicMock()
    coordinator.sync_user.side_effect = ValueError("secret internal detail")

    run_user_sync_job(
        coordinator=coordinator,
        idempotency=fake_idempotency,
        job_id="job-4",
        user_email="user@example.com",
        platform="aws",
        dry_run=False,
        request_id="req-4",
        started_at="2026-04-20T10:00:00+00:00",
        job_ttl_seconds=86400,
    )

    args, _ = fake_idempotency.set.call_args_list[0]
    payload = args[1]
    # Internal exception text must not leak
    assert "secret internal detail" not in payload.get("error", "")
    assert payload["error"] == "sync_failed"
