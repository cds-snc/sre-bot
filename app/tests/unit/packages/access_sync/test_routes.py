"""Unit tests for access sync route error sanitization."""

import pytest
from fastapi import HTTPException

from infrastructure.operations import OperationResult, OperationStatus
from packages.access_sync.transport.routes import sync_endpoint
from packages.access_sync.schemas import UserSyncRequest


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
    """Minimal settings stub; only `enabled` is checked by the route."""

    def __init__(self, enabled: bool) -> None:
        self.enabled = enabled


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
def test_sync_endpoint_not_found_masks_internal_error():
    """Route should not expose provider details for NOT_FOUND responses."""
    with pytest.raises(HTTPException) as exc_info:
        sync_endpoint(
            _make_request(),
            coordinator=_FakeCoordinator(
                OperationResult.error(
                    OperationStatus.NOT_FOUND,
                    message="ResourceNotFoundException: USER not found in identity store",
                    error_code="USER_NOT_FOUND",
                )
            ),
            settings=_Settings(enabled=True),
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Requested access sync resource was not found"


@pytest.mark.unit
def test_sync_endpoint_permanent_error_masks_internal_error():
    """Route should return a generic 400 message for permanent errors."""
    with pytest.raises(HTTPException) as exc_info:
        sync_endpoint(
            _make_request(),
            coordinator=_FakeCoordinator(
                OperationResult.error(
                    OperationStatus.PERMANENT_ERROR,
                    message="AccessDeniedException: not authorized",
                    error_code="AccessDeniedException",
                )
            ),
            settings=_Settings(enabled=True),
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Access sync request could not be completed"


@pytest.mark.unit
def test_sync_endpoint_unauthorized_masks_internal_error():
    """Route should map unauthorized results to 403 with safe detail."""
    with pytest.raises(HTTPException) as exc_info:
        sync_endpoint(
            _make_request(),
            coordinator=_FakeCoordinator(
                OperationResult.error(
                    OperationStatus.UNAUTHORIZED,
                    message="Token invalid for account 123456789012",
                    error_code="AUTH_FAILED",
                )
            ),
            settings=_Settings(enabled=True),
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "Not authorized to perform this access sync action"


@pytest.mark.unit
def test_sync_endpoint_internal_error_masks_internal_error():
    """Route should return generic 500 message for unexpected failures."""
    with pytest.raises(HTTPException) as exc_info:
        sync_endpoint(
            _make_request(),
            coordinator=_FakeCoordinator(
                OperationResult.error(
                    OperationStatus.TRANSIENT_ERROR,
                    message="Timeout contacting identity store",
                    error_code="TIMEOUT",
                )
            ),
            settings=_Settings(enabled=True),
        )

    assert exc_info.value.status_code == 500
    assert (
        exc_info.value.detail == "Access sync request failed due to an internal error"
    )


@pytest.mark.unit
def test_sync_endpoint_feature_disabled_returns_service_unavailable():
    """Route should surface feature-disabled as HTTP 503."""
    with pytest.raises(HTTPException) as exc_info:
        sync_endpoint(
            _make_request(),
            coordinator=_FakeCoordinator(OperationResult.success()),
            settings=_Settings(enabled=False),
        )

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == "Access Sync is not enabled"
