"""Unit tests for access sync route error sanitization."""

import pytest
from fastapi import HTTPException

from infrastructure.operations import OperationResult, OperationStatus
from packages.access_sync import routes
from packages.access_sync.schemas import UserSyncRequest


class _FakeService:
    """Minimal service stub that returns a fixed OperationResult."""

    def __init__(self, result: OperationResult) -> None:
        self._result = result

    def sync(self, request: UserSyncRequest) -> OperationResult:
        return self._result


def _make_request() -> UserSyncRequest:
    """Create a valid user-sync request payload."""
    return UserSyncRequest(
        sync_type="user",
        user_email="user@example.com",
        platform="aws",
        dry_run=False,
        request_id="test-request",
    )


@pytest.mark.unit
def test_sync_endpoint_not_found_masks_internal_error(monkeypatch: pytest.MonkeyPatch):
    """Route should not expose provider details for NOT_FOUND responses."""
    monkeypatch.setattr(
        routes,
        "get_access_sync_service",
        lambda: _FakeService(
            OperationResult.error(
                OperationStatus.NOT_FOUND,
                message="ResourceNotFoundException: USER not found in identity store",
                error_code="USER_NOT_FOUND",
            )
        ),
    )

    with pytest.raises(HTTPException) as exc_info:
        routes.sync_endpoint(_make_request())

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Requested access sync resource was not found"


@pytest.mark.unit
def test_sync_endpoint_permanent_error_masks_internal_error(
    monkeypatch: pytest.MonkeyPatch,
):
    """Route should return a generic 400 message for permanent errors."""
    monkeypatch.setattr(
        routes,
        "get_access_sync_service",
        lambda: _FakeService(
            OperationResult.error(
                OperationStatus.PERMANENT_ERROR,
                message=(
                    "AccessDeniedException: User arn:aws:sts::123:assumed-role/dev "
                    "is not authorized to perform identitystore:CreateUser"
                ),
                error_code="AccessDeniedException",
            )
        ),
    )

    with pytest.raises(HTTPException) as exc_info:
        routes.sync_endpoint(_make_request())

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Access sync request could not be completed"


@pytest.mark.unit
def test_sync_endpoint_unauthorized_masks_internal_error(
    monkeypatch: pytest.MonkeyPatch,
):
    """Route should map unauthorized results to 403 with safe detail."""
    monkeypatch.setattr(
        routes,
        "get_access_sync_service",
        lambda: _FakeService(
            OperationResult.error(
                OperationStatus.UNAUTHORIZED,
                message="Token invalid for account 123456789012",
                error_code="AUTH_FAILED",
            )
        ),
    )

    with pytest.raises(HTTPException) as exc_info:
        routes.sync_endpoint(_make_request())

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "Not authorized to perform this access sync action"


@pytest.mark.unit
def test_sync_endpoint_internal_error_masks_internal_error(
    monkeypatch: pytest.MonkeyPatch,
):
    """Route should return generic 500 message for unexpected failures."""
    monkeypatch.setattr(
        routes,
        "get_access_sync_service",
        lambda: _FakeService(
            OperationResult.error(
                OperationStatus.TRANSIENT_ERROR,
                message="Timeout contacting identity store in region ca-central-1",
                error_code="TIMEOUT",
            )
        ),
    )

    with pytest.raises(HTTPException) as exc_info:
        routes.sync_endpoint(_make_request())

    assert exc_info.value.status_code == 500
    assert (
        exc_info.value.detail == "Access sync request failed due to an internal error"
    )


@pytest.mark.unit
def test_sync_endpoint_feature_disabled_returns_service_unavailable(
    monkeypatch: pytest.MonkeyPatch,
):
    """Route should surface feature-disabled errors as HTTP 503."""
    monkeypatch.setattr(
        routes,
        "get_access_sync_service",
        lambda: _FakeService(
            OperationResult.error(
                OperationStatus.PERMANENT_ERROR,
                message="Access Sync is not enabled",
                error_code="FEATURE_DISABLED",
            )
        ),
    )

    with pytest.raises(HTTPException) as exc_info:
        routes.sync_endpoint(_make_request())

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == "Access Sync is not enabled"
