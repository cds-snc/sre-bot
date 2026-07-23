"""Access Requests Pydantic HTTP boundary models.

These are the only models that cross the HTTP boundary (request bodies and
response shapes).  They are never returned from the service layer — the
service layer works exclusively with domain.py dataclasses.

Route handlers translate between these schemas and internal domain models.
"""

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Request bodies
# ---------------------------------------------------------------------------


class SubmitAccessRequestBody(BaseModel):
    """Body for POST /api/v1/access/requests."""

    platform: str = Field(..., description="Target platform key (e.g. 'aws').")
    group_slug: str = Field(
        ...,
        description=(
            "IDP group slug identifying the entitlement "
            "(e.g. 'sg-aws-scratch'). The entitlement token is derived "
            "server-side from this slug."
        ),
    )
    entitlement_type: str = Field(default="group", description="Entitlement classification. Defaults to 'group'.")
    actor_type: str = Field(
        default="self",
        description="'self' for self-service; 'delegated' for manager-submitted.",
    )
    request_type: str = Field(
        default="grant",
        description="'grant' to add access; 'revoke' to remove access.",
    )
    user_email: str | None = Field(
        default=None,
        description=(
            "Target user email. Required for delegated requests; defaults to the authenticated actor for self-service requests."
        ),
    )
    justification: str = Field(..., min_length=1, description="Reason for the request.")
    ticket_id: str | None = Field(default=None, description="Optional external ticket reference.")


class ApproveRequestBody(BaseModel):
    """Body for POST /api/v1/access/requests/{request_id}/approve."""

    comment: str = Field(default="", description="Optional approver comment.")


class RejectRequestBody(BaseModel):
    """Body for POST /api/v1/access/requests/{request_id}/reject."""

    comment: str = Field(..., min_length=1, description="Required reason for rejection.")


class CancelRequestBody(BaseModel):
    """Body for POST /api/v1/access/requests/{request_id}/cancel."""

    comment: str = Field(default="", description="Optional cancellation comment.")


class RetryRequestBody(BaseModel):
    """Body for POST /api/v1/access/requests/{request_id}/retry."""

    comment: str = Field(default="", description="Optional operator comment.")


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class ApprovalDecisionResponse(BaseModel):
    """Single approval or rejection decision in a response."""

    request_id: str
    actor_email: str
    decision: str
    comment: str
    decided_at: str  # ISO 8601


class AccessRequestStatusResponse(BaseModel):
    """Response for GET /api/v1/access/requests/{request_id}."""

    request_id: str
    user_email: str
    actor_email: str
    actor_type: str
    platform: str
    group_slug: str
    group_email: str
    provider_group_id: str
    entitlement_type: str
    entitlement_id: str
    request_type: str
    status: str
    justification: str
    resolved_approvers: list[str]
    ticket_id: str | None = None
    requested_at: str | None = None
    updated_at: str | None = None
    decisions: list[ApprovalDecisionResponse] = Field(
        default_factory=list,
        description=(
            "Approval decision history. This list is empty for cancel and retry "
            "operations when no new approval decision is created."
        ),
    )


class SubmitAccessRequestResponse(BaseModel):
    """Response for POST /api/v1/access/requests on successful submission."""

    request_id: str
    status: str
    message: str
