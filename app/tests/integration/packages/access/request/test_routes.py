"""Integration tests for packages/access/request/interactions/http.py.

Tests route handlers directly by invoking them with stub dependencies,
mirroring the pattern used in packages/access/sync/interactions/http.py tests.

These tests exercise the HTTP-layer mapping (OperationResult → HTTP status)
without touching real DynamoDB, directory providers, or event dispatchers.
"""

from datetime import UTC, datetime

import pytest
from fastapi import HTTPException

from infrastructure.operations import OperationResult, OperationStatus
from infrastructure.security.models import AuthPrincipalSource, User
from packages.access.request.domain import AccessRequest, ApprovalDecision
from packages.access.request.interactions.http import (
    approve_request,
    cancel_request,
    get_request_status,
    reject_request,
    retry_request,
    submit_request,
)
from packages.access.request.schemas import (
    ApproveRequestBody,
    CancelRequestBody,
    RejectRequestBody,
    RetryRequestBody,
    SubmitAccessRequestBody,
)

# ---------------------------------------------------------------------------
# Stubs
# ---------------------------------------------------------------------------


class _Settings:
    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled


def _make_user(email: str = "actor@example.com") -> User:
    return User(
        user_id=email,
        email=email,
        display_name="Test User",
        source=AuthPrincipalSource.API_JWT,
        platform_id=email,
    )


def _make_request(
    request_id: str = "req-001",
    status: str = "pending_approval",
    actor_email: str = "actor@example.com",
) -> AccessRequest:
    return AccessRequest(
        request_id=request_id,
        user_email="user@example.com",
        actor_email=actor_email,
        actor_type="self",
        request_type="grant",
        platform="aws",
        group_slug="sg-aws-admins",
        group_email="sg-aws-admins@example.com",
        provider_group_id="gid-001",
        entitlement_type="group",
        entitlement_id="admins",
        status=status,  # type: ignore[arg-type]
        justification="Need access.",
        resolved_approvers=["approver@example.com"],
        requested_at=datetime.now(tz=UTC),
        updated_at=datetime.now(tz=UTC),
    )


class _FakeService:
    """Configurable service stub."""

    def __init__(self, result: OperationResult) -> None:
        self._result = result

    def submit_request(self, **kwargs) -> OperationResult:
        return self._result

    def approve_request(self, **kwargs) -> OperationResult:
        return self._result

    def reject_request(self, **kwargs) -> OperationResult:
        return self._result

    def cancel_request(self, **kwargs) -> OperationResult:
        return self._result

    def retry_request(self, **kwargs) -> OperationResult:
        return self._result

    def get_request_status(self, **kwargs) -> OperationResult:
        return self._result

    def advance_from_sync_result(self, event) -> None:
        pass


# ---------------------------------------------------------------------------
# submit_request
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_submit_request_returns_202_on_success():
    request = _make_request(status="pending_approval")
    service = _FakeService(OperationResult.success(data=request, message="Submitted."))
    body = SubmitAccessRequestBody(
        platform="aws",
        group_slug="sg-aws-admins",
        justification="Need access.",
    )

    response = submit_request(
        body=body,
        service=service,
        settings=_Settings(enabled=True),
        current_user=_make_user(),
    )

    assert response.request_id == "req-001"
    assert response.status == "pending_approval"


@pytest.mark.integration
def test_submit_request_raises_503_when_disabled():
    service = _FakeService(OperationResult.success(data=_make_request()))
    body = SubmitAccessRequestBody(
        platform="aws",
        group_slug="sg-aws-admins",
        justification="Need access.",
    )

    with pytest.raises(HTTPException) as exc_info:
        submit_request(
            body=body,
            service=service,
            settings=_Settings(enabled=False),
            current_user=_make_user(),
        )
    assert exc_info.value.status_code == 503


@pytest.mark.integration
def test_submit_request_raises_400_on_permanent_error():
    service = _FakeService(
        OperationResult.error(
            OperationStatus.PERMANENT_ERROR,
            message="Already provisioned.",
            error_code="ALREADY_PROVISIONED",
        )
    )
    body = SubmitAccessRequestBody(
        platform="aws",
        group_slug="sg-aws-admins",
        justification="Need access.",
    )

    with pytest.raises(HTTPException) as exc_info:
        submit_request(
            body=body,
            service=service,
            settings=_Settings(enabled=True),
            current_user=_make_user(),
        )
    assert exc_info.value.status_code == 400


# ---------------------------------------------------------------------------
# approve_request
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_approve_request_returns_response_on_success():
    request = _make_request(status="approved")
    service = _FakeService(OperationResult.success(data=(request, [])))
    body = ApproveRequestBody(comment="Looks good.")

    response = approve_request(
        request_id="req-001",
        body=body,
        service=service,
        settings=_Settings(enabled=True),
        current_user=_make_user(email="approver@example.com"),
    )

    assert response.request_id == "req-001"
    assert response.status == "approved"


@pytest.mark.integration
def test_approve_request_raises_404_on_not_found():
    service = _FakeService(
        OperationResult.error(
            OperationStatus.NOT_FOUND,
            message="Request not found.",
            error_code="REQUEST_NOT_FOUND",
        )
    )
    body = ApproveRequestBody()

    with pytest.raises(HTTPException) as exc_info:
        approve_request(
            request_id="missing",
            body=body,
            service=service,
            settings=_Settings(enabled=True),
            current_user=_make_user(),
        )
    assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# reject_request
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_reject_request_returns_response_on_success():
    request = _make_request(status="rejected")
    service = _FakeService(OperationResult.success(data=(request, [])))
    body = RejectRequestBody(comment="Not needed.")

    response = reject_request(
        request_id="req-001",
        body=body,
        service=service,
        settings=_Settings(enabled=True),
        current_user=_make_user(email="approver@example.com"),
    )

    assert response.status == "rejected"


@pytest.mark.integration
def test_reject_request_raises_400_on_invalid_state():
    service = _FakeService(
        OperationResult.error(
            OperationStatus.PERMANENT_ERROR,
            message="Invalid state.",
            error_code="INVALID_STATE_TRANSITION",
        )
    )
    body = RejectRequestBody(comment="Reason required.")

    with pytest.raises(HTTPException) as exc_info:
        reject_request(
            request_id="req-001",
            body=body,
            service=service,
            settings=_Settings(enabled=True),
            current_user=_make_user(),
        )
    assert exc_info.value.status_code == 400


# ---------------------------------------------------------------------------
# cancel_request
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_cancel_request_returns_response_on_success():
    request = _make_request(status="cancelled")
    service = _FakeService(OperationResult.success(data=(request, [])))
    body = CancelRequestBody(comment="Changed my mind.")

    response = cancel_request(
        request_id="req-001",
        body=body,
        service=service,
        settings=_Settings(enabled=True),
        current_user=_make_user(),
    )

    assert response.status == "cancelled"


# ---------------------------------------------------------------------------
# get_request_status
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_get_request_status_returns_full_response():
    request = _make_request(status="pending_approval")
    decisions: list[ApprovalDecision] = []
    service = _FakeService(OperationResult.success(data=(request, decisions)))

    response = get_request_status(
        request_id="req-001",
        service=service,
        settings=_Settings(enabled=True),
        current_user=_make_user(),
    )

    assert response.request_id == "req-001"
    assert response.status == "pending_approval"
    assert response.decisions == []


@pytest.mark.integration
def test_get_request_status_raises_404_on_missing():
    service = _FakeService(
        OperationResult.error(
            OperationStatus.NOT_FOUND,
            message="Request not found.",
            error_code="REQUEST_NOT_FOUND",
        )
    )

    with pytest.raises(HTTPException) as exc_info:
        get_request_status(
            request_id="unknown",
            service=service,
            settings=_Settings(enabled=True),
            current_user=_make_user(),
        )
    assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# retry_request
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_retry_request_returns_approved_response_on_success():
    request = _make_request(status="approved")
    service = _FakeService(OperationResult.success(data=(request, [])))
    body = RetryRequestBody(comment="DWD scopes fixed.")

    response = retry_request(
        request_id="req-001",
        body=body,
        service=service,
        settings=_Settings(enabled=True),
        current_user=_make_user(email="approver@example.com"),
    )

    assert response.request_id == "req-001"
    assert response.status == "approved"


@pytest.mark.integration
def test_retry_request_raises_400_on_invalid_state():
    service = _FakeService(
        OperationResult.error(
            OperationStatus.PERMANENT_ERROR,
            message="Request is in 'pending_approval' state; only 'failed' requests can be retried.",
            error_code="INVALID_STATE_TRANSITION",
        )
    )
    body = RetryRequestBody()

    with pytest.raises(HTTPException) as exc_info:
        retry_request(
            request_id="req-001",
            body=body,
            service=service,
            settings=_Settings(enabled=True),
            current_user=_make_user(email="approver@example.com"),
        )
    assert exc_info.value.status_code == 400


@pytest.mark.integration
def test_retry_request_raises_503_on_idp_failure():
    service = _FakeService(
        OperationResult.error(
            OperationStatus.TRANSIENT_ERROR,
            message="IDP membership write failed again.",
            error_code="IDP_WRITE_FAILED",
        )
    )
    body = RetryRequestBody()

    with pytest.raises(HTTPException) as exc_info:
        retry_request(
            request_id="req-001",
            body=body,
            service=service,
            settings=_Settings(enabled=True),
            current_user=_make_user(email="approver@example.com"),
        )
    assert exc_info.value.status_code == 503


@pytest.mark.integration
def test_retry_request_raises_503_when_disabled():
    service = _FakeService(OperationResult.success(data=_make_request()))
    body = RetryRequestBody()

    with pytest.raises(HTTPException) as exc_info:
        retry_request(
            request_id="req-001",
            body=body,
            service=service,
            settings=_Settings(enabled=False),
            current_user=_make_user(),
        )
    assert exc_info.value.status_code == 503
