"""Access Requests FastAPI route handlers — HTTP transport layer only.

Five endpoints:
    POST   /api/v1/access/requests                          — submit request.
    POST   /api/v1/access/requests/{request_id}/approve     — approve.
    POST   /api/v1/access/requests/{request_id}/reject      — reject.
    POST   /api/v1/access/requests/{request_id}/cancel      — cancel.
    GET    /api/v1/access/requests/{request_id}             — status + history.

Handlers validate the incoming body, delegate to the service via
``AccessRequestServicePort``, and map ``OperationResult`` to HTTP.
No business logic lives here.
"""

from typing import Annotated, Protocol

import structlog
from fastapi import APIRouter, Depends, HTTPException, Security

from infrastructure.operations import OperationResult, OperationStatus
from infrastructure.security import get_current_user
from infrastructure.security.models import User
from packages.access.request.domain import AccessRequest, ApprovalDecision
from packages.access.request.providers import (
    get_access_request_service,
    get_access_request_settings,
)
from packages.access.request.schemas import (
    AccessRequestStatusResponse,
    ApprovalDecisionResponse,
    ApproveRequestBody,
    CancelRequestBody,
    RejectRequestBody,
    RetryRequestBody,
    SubmitAccessRequestBody,
    SubmitAccessRequestResponse,
)

logger = structlog.get_logger()
router = APIRouter(prefix="/access/requests", tags=["Access Requests"])


class _AccessRequestSettingsPort(Protocol):
    """Structural contract for settings consumed by route handlers."""

    enabled: bool


class _AccessRequestServicePort(Protocol):
    """Structural contract for service methods consumed by route handlers."""

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
        ticket_id: str | None = None,
    ) -> OperationResult[AccessRequest]: ...

    def approve_request(
        self,
        request_id: str,
        approver_email: str,
        comment: str = "",
    ) -> OperationResult[tuple[AccessRequest, list[ApprovalDecision]]]: ...

    def reject_request(
        self,
        request_id: str,
        approver_email: str,
        comment: str,
    ) -> OperationResult[tuple[AccessRequest, list[ApprovalDecision]]]: ...

    def cancel_request(
        self,
        request_id: str,
        actor_email: str,
        comment: str = "",
    ) -> OperationResult[tuple[AccessRequest, list[ApprovalDecision]]]: ...

    def retry_request(
        self,
        request_id: str,
        actor_email: str,
        comment: str = "",
    ) -> OperationResult[tuple[AccessRequest, list[ApprovalDecision]]]: ...

    def get_request_status(
        self,
        request_id: str,
    ) -> OperationResult[tuple[AccessRequest, list[ApprovalDecision]]]: ...


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _map_status(status: OperationStatus) -> int:
    """Map OperationStatus to an HTTP status code."""
    if status == OperationStatus.NOT_FOUND:
        return 404
    if status == OperationStatus.PERMANENT_ERROR:
        return 400
    if status == OperationStatus.TRANSIENT_ERROR:
        return 503
    if status == OperationStatus.UNAUTHORIZED:
        return 403
    return 500


def _build_decision_response(decision: ApprovalDecision) -> ApprovalDecisionResponse:
    return ApprovalDecisionResponse(
        request_id=decision.request_id,
        actor_email=decision.actor_email,
        decision=decision.decision,
        comment=decision.comment,
        decided_at=decision.decided_at.isoformat(),
    )


def _build_request_response(
    request: AccessRequest,
    decisions: list[ApprovalDecision],
) -> AccessRequestStatusResponse:
    return AccessRequestStatusResponse(
        request_id=request.request_id,
        user_email=request.user_email,
        actor_email=request.actor_email,
        actor_type=request.actor_type,
        platform=request.platform,
        group_slug=request.group_slug,
        group_email=request.group_email,
        provider_group_id=request.provider_group_id,
        entitlement_type=request.entitlement_type,
        entitlement_id=request.entitlement_id,
        request_type=request.request_type,
        status=request.status,
        justification=request.justification,
        resolved_approvers=request.resolved_approvers,
        ticket_id=request.ticket_id,
        requested_at=request.requested_at.isoformat() if request.requested_at else None,
        updated_at=request.updated_at.isoformat() if request.updated_at else None,
        decisions=[_build_decision_response(d) for d in decisions],
    )


def _resolve_service(
    service: _AccessRequestServicePort | None,
) -> _AccessRequestServicePort:
    """Resolve the request service lazily after feature-gate checks."""
    return service if service is not None else get_access_request_service()


def _noop_request_service() -> _AccessRequestServicePort | None:
    """No-op dependency used to defer heavy service assembly until after gating."""
    return None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post(
    "",
    response_model=SubmitAccessRequestResponse,
    summary="Submit an access request",
    description=("Submit a new access request for the authenticated user or, for delegated requests, on behalf of another user."),
    status_code=202,
    responses={
        400: {"description": "Invalid request payload or policy violation."},
        403: {"description": "Caller is not authorized."},
        503: {"description": "Access Requests feature is disabled."},
    },
)
def submit_request(
    body: SubmitAccessRequestBody,
    settings: Annotated[_AccessRequestSettingsPort, Depends(get_access_request_settings)],
    current_user: Annotated[User, Security(get_current_user, scopes=["sre-bot:access-requests"])],
    service: Annotated[_AccessRequestServicePort | None, Depends(_noop_request_service)] = None,
) -> SubmitAccessRequestResponse:
    """Submit a new access request."""
    if not settings.enabled:
        raise HTTPException(status_code=503, detail="Access Requests feature is disabled.")
    service_dep = _resolve_service(service)

    user_email = body.user_email or current_user.email
    actor_email = current_user.email

    log = logger.bind(
        endpoint="POST /api/v1/access/requests",
        actor_email=actor_email,
        user_email=user_email,
        platform=body.platform,
        group_slug=body.group_slug,
    )
    log.info("access_request_submit_handler")

    result = service_dep.submit_request(
        user_email=user_email,
        actor_email=actor_email,
        actor_type=body.actor_type,
        request_type=body.request_type,
        platform=body.platform,
        group_slug=body.group_slug,
        entitlement_type=body.entitlement_type,
        justification=body.justification,
        ticket_id=body.ticket_id,
    )

    if not result.is_success:
        raise HTTPException(
            status_code=_map_status(result.status),
            detail=result.message,
        )

    if result.data is None:
        raise HTTPException(status_code=500, detail="Internal server error.")
    request: AccessRequest = result.data
    return SubmitAccessRequestResponse(
        request_id=request.request_id,
        status=request.status,
        message=result.message,
    )


@router.post(
    "/{request_id}/approve",
    response_model=AccessRequestStatusResponse,
    summary="Approve an access request",
    description="Approve a pending access request as an authorized approver.",
    status_code=200,
    responses={
        403: {"description": "Caller is not authorized to approve requests."},
        404: {"description": "Access request not found."},
        409: {"description": "Request state does not allow approval."},
        503: {"description": "Access Requests feature is disabled."},
    },
)
def approve_request(
    request_id: str,
    body: ApproveRequestBody,
    settings: Annotated[_AccessRequestSettingsPort, Depends(get_access_request_settings)],
    current_user: Annotated[User, Security(get_current_user, scopes=["sre-bot:access-requests"])],
    service: Annotated[_AccessRequestServicePort | None, Depends(_noop_request_service)] = None,
) -> AccessRequestStatusResponse:
    """Submit an approval decision for a pending access request."""
    if not settings.enabled:
        raise HTTPException(status_code=503, detail="Access Requests feature is disabled.")
    service_dep = _resolve_service(service)

    log = logger.bind(
        endpoint=f"POST /api/v1/access/requests/{request_id}/approve",
        approver_email=current_user.email,
        request_id=request_id,
    )
    log.info("access_request_approve_handler")

    result = service_dep.approve_request(
        request_id=request_id,
        approver_email=current_user.email,
        comment=body.comment,
    )

    if not result.is_success:
        raise HTTPException(
            status_code=_map_status(result.status),
            detail=result.message,
        )

    if result.data is None:
        raise HTTPException(status_code=500, detail="Internal server error.")
    request, decisions = result.data
    return _build_request_response(request, decisions)


@router.post(
    "/{request_id}/reject",
    response_model=AccessRequestStatusResponse,
    summary="Reject an access request",
    description="Reject a pending access request as an authorized approver.",
    status_code=200,
    responses={
        403: {"description": "Caller is not authorized to reject requests."},
        404: {"description": "Access request not found."},
        409: {"description": "Request state does not allow rejection."},
        503: {"description": "Access Requests feature is disabled."},
    },
)
def reject_request(
    request_id: str,
    body: RejectRequestBody,
    settings: Annotated[_AccessRequestSettingsPort, Depends(get_access_request_settings)],
    current_user: Annotated[User, Security(get_current_user, scopes=["sre-bot:access-requests"])],
    service: Annotated[_AccessRequestServicePort | None, Depends(_noop_request_service)] = None,
) -> AccessRequestStatusResponse:
    """Submit a rejection decision for a pending access request."""
    if not settings.enabled:
        raise HTTPException(status_code=503, detail="Access Requests feature is disabled.")
    service_dep = _resolve_service(service)

    log = logger.bind(
        endpoint=f"POST /api/v1/access/requests/{request_id}/reject",
        approver_email=current_user.email,
        request_id=request_id,
    )
    log.info("access_request_reject_handler")

    result = service_dep.reject_request(
        request_id=request_id,
        approver_email=current_user.email,
        comment=body.comment,
    )

    if not result.is_success:
        raise HTTPException(
            status_code=_map_status(result.status),
            detail=result.message,
        )

    if result.data is None:
        raise HTTPException(status_code=500, detail="Internal server error.")
    request, decisions = result.data
    return _build_request_response(request, decisions)


@router.post(
    "/{request_id}/cancel",
    response_model=AccessRequestStatusResponse,
    summary="Cancel an access request",
    description="Cancel a pending access request when the current state allows it.",
    status_code=200,
    responses={
        403: {"description": "Caller is not authorized to cancel this request."},
        404: {"description": "Access request not found."},
        409: {"description": "Request state does not allow cancellation."},
        503: {"description": "Access Requests feature is disabled."},
    },
)
def cancel_request(
    request_id: str,
    body: CancelRequestBody,
    settings: Annotated[_AccessRequestSettingsPort, Depends(get_access_request_settings)],
    current_user: Annotated[User, Security(get_current_user, scopes=["sre-bot:access-requests"])],
    service: Annotated[_AccessRequestServicePort | None, Depends(_noop_request_service)] = None,
) -> AccessRequestStatusResponse:
    """Cancel a pending access request (requester only)."""
    if not settings.enabled:
        raise HTTPException(status_code=503, detail="Access Requests feature is disabled.")
    service_dep = _resolve_service(service)

    log = logger.bind(
        endpoint=f"POST /api/v1/access/requests/{request_id}/cancel",
        actor_email=current_user.email,
        request_id=request_id,
    )
    log.info("access_request_cancel_handler")

    result = service_dep.cancel_request(
        request_id=request_id,
        actor_email=current_user.email,
        comment=body.comment,
    )

    if not result.is_success:
        raise HTTPException(
            status_code=_map_status(result.status),
            detail=result.message,
        )

    if result.data is None:
        raise HTTPException(status_code=500, detail="Internal server error.")
    request, decisions = result.data
    return _build_request_response(request, decisions)


@router.post(
    "/{request_id}/retry",
    response_model=AccessRequestStatusResponse,
    summary="Retry a failed access request",
    description=(
        "Re-attempt IDP provisioning for a request in 'failed' state. "
        "Only authorized approvers may call this endpoint. "
        "Use this to recover from transient infrastructure failures "
        "(e.g. Google DWD misconfiguration) without requiring a full re-submission."
    ),
    status_code=200,
    responses={
        403: {"description": "Caller is not authorized to retry this request."},
        404: {"description": "Access request not found."},
        409: {"description": "Request state does not allow retry."},
        503: {"description": "Access Requests feature is disabled."},
    },
)
def retry_request(
    request_id: str,
    body: RetryRequestBody,
    settings: Annotated[_AccessRequestSettingsPort, Depends(get_access_request_settings)],
    current_user: Annotated[User, Security(get_current_user, scopes=["sre-bot:access-requests"])],
    service: Annotated[_AccessRequestServicePort | None, Depends(_noop_request_service)] = None,
) -> AccessRequestStatusResponse:
    """Retry IDP provisioning for a failed access request."""
    if not settings.enabled:
        raise HTTPException(status_code=503, detail="Access Requests feature is disabled.")
    service_dep = _resolve_service(service)

    log = logger.bind(
        endpoint=f"POST /api/v1/access/requests/{request_id}/retry",
        actor_email=current_user.email,
        request_id=request_id,
    )
    log.info("access_request_retry_handler")

    result = service_dep.retry_request(
        request_id=request_id,
        actor_email=current_user.email,
        comment=body.comment,
    )

    if not result.is_success:
        raise HTTPException(
            status_code=_map_status(result.status),
            detail=result.message,
        )

    if result.data is None:
        raise HTTPException(status_code=500, detail="Internal server error.")
    request, decisions = result.data
    return _build_request_response(request, decisions)


@router.get(
    "/{request_id}",
    response_model=AccessRequestStatusResponse,
    summary="Get access request status",
    description="Return current request state, resolved approvers, and decisions.",
    status_code=200,
    responses={
        404: {"description": "Access request not found."},
        503: {"description": "Access Requests feature is disabled."},
    },
)
def get_request_status(
    request_id: str,
    settings: Annotated[_AccessRequestSettingsPort, Depends(get_access_request_settings)],
    current_user: Annotated[User, Security(get_current_user, scopes=["sre-bot:access-requests"])],
    service: Annotated[_AccessRequestServicePort | None, Depends(_noop_request_service)] = None,
) -> AccessRequestStatusResponse:
    """Fetch request status, resolved approvers, and decision history."""
    if not settings.enabled:
        raise HTTPException(status_code=503, detail="Access Requests feature is disabled.")
    service_dep = _resolve_service(service)

    log = logger.bind(
        endpoint=f"GET /api/v1/access/requests/{request_id}",
        requested_by=current_user.email,
        request_id=request_id,
    )
    log.info("access_request_status_handler")

    result = service_dep.get_request_status(request_id=request_id)

    if not result.is_success:
        raise HTTPException(
            status_code=_map_status(result.status),
            detail=result.message,
        )

    if result.data is None:
        raise HTTPException(status_code=500, detail="Internal server error.")
    request, decisions = result.data
    return _build_request_response(request, decisions)
