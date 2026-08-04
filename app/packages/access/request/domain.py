"""Access Requests internal typed models.

These dataclasses are the canonical internal representation used throughout
the service, store, and policy layers.  They are NOT returned across the HTTP
boundary — schemas.py defines separate Pydantic models for that purpose.

All models are frozen (immutable) to prevent accidental mutation during
orchestration flows.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

ActorType = Literal["self", "delegated"]

RequestType = Literal["grant", "revoke"]

RequestStatus = Literal[
    "submitted",
    "pending_approval",
    "approved",
    "rejected",
    "cancelled",
    "expired",
    "completed",
    "failed",
]

DecisionType = Literal["approved", "rejected"]


@dataclass(frozen=True)
class AccessRequest:
    """Canonical internal representation of an access request.

    Captured once at submission time and updated by creating a new instance
    (dataclass replace pattern) on each state transition.

    Attributes:
        request_id: UUID string — stable primary key for this request.
        user_email: Email of the user who will receive access.
        actor_email: Email of the user who submitted the request (may differ
            from user_email for delegated requests).
        actor_type: "self" for self-service requests; "delegated" for
            manager-submitted requests on behalf of another user.
        platform: Target platform key (e.g. "aws").
        group_slug: IDP group slug identifying the entitlement group.
        group_email: Resolved canonical group email from the IDP — the trusted
            lookup key for membership operations.
        provider_group_id: Immutable provider-assigned group identifier used as
            audit correlation identity.
        entitlement_type: Entitlement classification (e.g. "group").
        entitlement_id: Platform-specific entitlement identifier.
        status: Current lifecycle state.
        justification: Requester-provided reason.
        resolved_approvers: Approver email list captured at submission time.
            Decisions are validated against this snapshot, not re-resolved.
        ticket_id: Optional external ticket reference.
        requested_at: Submission timestamp.
        updated_at: Timestamp of last state transition.
    """

    request_id: str
    user_email: str
    actor_email: str
    actor_type: ActorType
    request_type: RequestType
    platform: str
    group_slug: str
    group_email: str
    provider_group_id: str
    entitlement_type: str
    entitlement_id: str
    status: RequestStatus
    justification: str
    resolved_approvers: list[str] = field(default_factory=list)
    ticket_id: str | None = None
    requested_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True)
class ApprovalDecision:
    """Canonical representation of a single approval or rejection decision.

    Attributes:
        request_id: UUID string referring to the parent AccessRequest.
        actor_email: Email of the approver who submitted this decision.
        decision: "approved" or "rejected".
        comment: Approver-supplied rationale (required for rejections).
        decided_at: Timestamp when the decision was recorded.
    """

    request_id: str
    actor_email: str
    decision: DecisionType
    comment: str
    decided_at: datetime


@dataclass(frozen=True)
class RequestAuditEvent:
    """Immutable audit trail entry for a request lifecycle event.

    Persisted alongside AccessRequest and ApprovalDecision in DynamoDB.

    Attributes:
        event_type: Short event label (e.g. "access_request_submitted").
        request_id: UUID string referring to the parent AccessRequest.
        actor_email: Email of the actor who triggered this event.
        timestamp: When the event occurred.
        metadata: Arbitrary additional context (should be JSON-serialisable).
    """

    event_type: str
    request_id: str
    actor_email: str
    timestamp: datetime
    metadata: dict = field(default_factory=dict)
