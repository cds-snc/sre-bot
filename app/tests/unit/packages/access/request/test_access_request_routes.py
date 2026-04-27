"""Unit tests for packages.access.request.transport.routes.

Tests invoke route handlers directly with fakes to validate HTTP mapping and
response-shape behavior at the transport boundary.
"""

from datetime import datetime, timezone
from typing import Optional

import pytest
from fastapi import FastAPI
from fastapi import HTTPException
from fastapi.testclient import TestClient

from infrastructure.identity.models import IdentitySource, User
from infrastructure.services import get_current_user
from infrastructure.operations import OperationResult, OperationStatus
from packages.access.request.domain import AccessRequest, ApprovalDecision
from packages.access.request.providers import (
    get_access_request_service,
    get_access_request_settings,
)
from packages.access.request.schemas import ApproveRequestBody, SubmitAccessRequestBody
from packages.access.request.transport.routes import (
    approve_request,
    router,
    submit_request,
)


class _FakeSettings:
    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled


class _FakeAccessRequestService:
    def __init__(
        self,
        submit_result: Optional[OperationResult] = None,
        approve_result: Optional[OperationResult] = None,
    ) -> None:
        self._submit_result = submit_result
        self._approve_result = approve_result

    def submit_request(
        self,
        user_email: str,
        actor_email: str,
        actor_type: str,
        request_type: str,
        platform: str,
        group_slug: str,
        entitlement_type: str,
        justification: str,
        ticket_id: Optional[str] = None,
    ) -> OperationResult:
        return self._submit_result or OperationResult.success(data=_make_request())

    def approve_request(
        self,
        request_id: str,
        approver_email: str,
        comment: str = "",
    ) -> OperationResult:
        if self._approve_result is not None:
            return self._approve_result
        return OperationResult.success(
            data=(_make_request(), [_make_decision(request_id)])
        )


def _make_user(email: str = "approver@example.com") -> User:
    return User(
        user_id=email,
        email=email,
        display_name="Approver",
        source=IdentitySource.API_JWT,
        platform_id=email,
    )


def _make_request(request_id: str = "req-1") -> AccessRequest:
    now = datetime.now(tz=timezone.utc)
    return AccessRequest(
        request_id=request_id,
        user_email="user@example.com",
        actor_email="user@example.com",
        actor_type="self",
        request_type="grant",
        platform="aws",
        group_slug="sg-aws-admins",
        group_email="sg-aws-admins@example.com",
        provider_group_id="gid-1",
        entitlement_type="group",
        entitlement_id="admins",
        status="approved",
        justification="Need access",
        resolved_approvers=["approver@example.com"],
        requested_at=now,
        updated_at=now,
    )


def _make_decision(request_id: str = "req-1") -> ApprovalDecision:
    return ApprovalDecision(
        request_id=request_id,
        actor_email="approver@example.com",
        decision="approved",
        comment="approved",
        decided_at=datetime.now(tz=timezone.utc),
    )


@pytest.mark.unit
def test_submit_request_maps_permanent_error_to_400() -> None:
    service = _FakeAccessRequestService(
        submit_result=OperationResult.error(
            OperationStatus.PERMANENT_ERROR,
            message="business rule denied",
        )
    )

    with pytest.raises(HTTPException) as exc_info:
        submit_request(
            body=SubmitAccessRequestBody(
                platform="aws",
                group_slug="sg-aws-admins",
                entitlement_type="group",
                actor_type="self",
                request_type="grant",
                justification="Need access",
            ),
            service=service,
            settings=_FakeSettings(enabled=True),
            current_user=_make_user("caller@example.com"),
        )

    assert exc_info.value.status_code == 400


@pytest.mark.unit
def test_approve_request_includes_decisions_in_response() -> None:
    service = _FakeAccessRequestService()

    response = approve_request(
        request_id="req-1",
        body=ApproveRequestBody(comment="Looks good"),
        service=service,
        settings=_FakeSettings(enabled=True),
        current_user=_make_user("approver@example.com"),
    )

    assert response.request_id == "req-1"
    assert len(response.decisions) == 1
    assert response.decisions[0].decision == "approved"


@pytest.mark.unit
def test_submit_request_returns_503_without_service_dependency_assembly() -> None:
    app = FastAPI()
    app.include_router(router)

    service_provider_called = False

    def _service_provider() -> _FakeAccessRequestService:
        nonlocal service_provider_called
        service_provider_called = True
        raise AssertionError("service dependency should not be assembled")

    app.dependency_overrides[get_access_request_settings] = lambda: _FakeSettings(
        enabled=False
    )
    app.dependency_overrides[get_access_request_service] = _service_provider
    app.dependency_overrides[get_current_user] = lambda: _make_user(
        "caller@example.com"
    )

    client = TestClient(app)
    response = client.post(
        "/access/requests",
        json={
            "platform": "aws",
            "group_slug": "sg-aws-admins",
            "entitlement_type": "group",
            "actor_type": "self",
            "request_type": "grant",
            "justification": "Need access",
        },
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "Access Requests feature is disabled."
    assert service_provider_called is False
