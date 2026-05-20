"""Access Requests DynamoDB repository.

Wraps ``StorageService`` to persist and retrieve ``AccessRequest``,
``ApprovalDecision``, and ``RequestAuditEvent`` objects.  Access Requests
owns its key scheme and serialisation; all DynamoDB I/O is delegated to the
infrastructure storage service.

Key scheme in ``sre_bot_access``:
    AccessRequest:
        PK = ``ACCESS_REQUEST#{request_id}``
        SK = ``REQUEST``

    ApprovalDecision:
        PK = ``ACCESS_REQUEST#{request_id}``
        SK = ``DECISION#{decided_at_iso}#{actor_email}``

    RequestAuditEvent:
        PK = ``ACCESS_REQUEST#{request_id}``
        SK = ``AUDIT#{timestamp_iso}#{event_type}``

This key scheme enables atomic reads of request + all decisions + full audit
trail with a single DynamoDB ``query`` against the request's PK, without table
scans or GSIs.
"""

from datetime import datetime, timezone
from typing import List, Optional

import structlog

from infrastructure.storage.protocol import StorageService
from packages.access.request.domain import (
    AccessRequest,
    ApprovalDecision,
    RequestAuditEvent,
)

logger = structlog.get_logger()


class AccessRequestRepository:
    """DynamoDB-backed repository for access request lifecycle records.

    Constructed once at startup in ``providers.py`` using the centralized
    ``StorageService`` singleton from ``infrastructure.storage``.

    Args:
        storage: Configured ``StorageService`` instance injected by provider.
    """

    TABLE = "sre_bot_access_requests"

    def __init__(self, storage: StorageService) -> None:
        self._storage = storage

    # ------------------------------------------------------------------
    # AccessRequest
    # ------------------------------------------------------------------

    def save_request(self, request: AccessRequest) -> None:
        """Persist or overwrite an access request record.

        Failure is logged but not propagated — the service layer checks the
        returned result independently when persistence is critical to flow.
        """
        item = {
            "PK": f"ACCESS_REQUEST#{request.request_id}",
            "SK": "REQUEST",
            "request_id": request.request_id,
            "user_email": request.user_email,
            "actor_email": request.actor_email,
            "actor_type": request.actor_type,
            "platform": request.platform,
            "group_slug": request.group_slug,
            "group_email": request.group_email,
            "provider_group_id": request.provider_group_id,
            "entitlement_type": request.entitlement_type,
            "entitlement_id": request.entitlement_id,
            "request_type": request.request_type,
            "status": request.status,
            "justification": request.justification,
            "resolved_approvers": request.resolved_approvers,
            "ticket_id": request.ticket_id,
            "requested_at": (
                request.requested_at.isoformat() if request.requested_at else None
            ),
            "updated_at": (
                request.updated_at.isoformat() if request.updated_at else None
            ),
        }
        result = self._storage.put(self.TABLE, item)
        if not result.is_success:
            logger.error(
                "access_request_save_failed",
                request_id=request.request_id,
                error=result.message,
            )

    def get_request(self, request_id: str) -> Optional[AccessRequest]:
        """Return the AccessRequest for the given request ID, or None."""
        result = self._storage.get(
            self.TABLE,
            key={
                "PK": f"ACCESS_REQUEST#{request_id}",
                "SK": "REQUEST",
            },
        )
        if not result.is_success or result.data is None:
            return None
        return self._deserialize_request(result.data)

    # ------------------------------------------------------------------
    # ApprovalDecision
    # ------------------------------------------------------------------

    def save_decision(self, decision: ApprovalDecision) -> None:
        """Persist an approval or rejection decision."""
        sk = f"DECISION#{decision.decided_at.isoformat()}#{decision.actor_email}"
        item = {
            "PK": f"ACCESS_REQUEST#{decision.request_id}",
            "SK": sk,
            "request_id": decision.request_id,
            "actor_email": decision.actor_email,
            "decision": decision.decision,
            "comment": decision.comment,
            "decided_at": decision.decided_at.isoformat(),
        }
        result = self._storage.put(self.TABLE, item)
        if not result.is_success:
            logger.error(
                "access_decision_save_failed",
                request_id=decision.request_id,
                error=result.message,
            )

    def get_decisions(self, request_id: str) -> List[ApprovalDecision]:
        """Return all decisions for the given request, ordered by SK."""
        result = self._storage.query(
            self.TABLE,
            key_condition="PK = :pk AND begins_with(SK, :prefix)",
            expression_values={
                ":pk": f"ACCESS_REQUEST#{request_id}",
                ":prefix": "DECISION#",
            },
        )
        if not result.is_success or result.data is None:
            return []
        return [self._deserialize_decision(item) for item in result.data]

    # ------------------------------------------------------------------
    # RequestAuditEvent
    # ------------------------------------------------------------------

    def save_audit_event(self, event: RequestAuditEvent) -> None:
        """Persist an audit trail entry."""
        sk = f"AUDIT#{event.timestamp.isoformat()}#{event.event_type}"
        item = {
            "PK": f"ACCESS_REQUEST#{event.request_id}",
            "SK": sk,
            "event_type": event.event_type,
            "request_id": event.request_id,
            "actor_email": event.actor_email,
            "timestamp": event.timestamp.isoformat(),
            "metadata": event.metadata,
        }
        result = self._storage.put(self.TABLE, item)
        if not result.is_success:
            logger.error(
                "access_audit_event_save_failed",
                request_id=event.request_id,
                event_type=event.event_type,
                error=result.message,
            )

    # ------------------------------------------------------------------
    # Full request context
    # ------------------------------------------------------------------

    def get_request_with_decisions(
        self, request_id: str
    ) -> tuple[Optional[AccessRequest], List[ApprovalDecision]]:
        """Return the access request and all its recorded decisions.

        Uses a single DynamoDB query on the PK prefix to retrieve both
        the REQUEST record and all DECISION records atomically.

        Returns:
            ``(AccessRequest | None, List[ApprovalDecision])``
        """
        result = self._storage.query(
            self.TABLE,
            key_condition="PK = :pk",
            expression_values={":pk": f"ACCESS_REQUEST#{request_id}"},
        )
        if not result.is_success or result.data is None:
            return None, []

        request: Optional[AccessRequest] = None
        decisions: List[ApprovalDecision] = []

        for item in result.data:
            sk = item.get("SK", "")
            if sk == "REQUEST":
                request = self._deserialize_request(item)
            elif sk.startswith("DECISION#"):
                decisions.append(self._deserialize_decision(item))

        return request, decisions

    # ------------------------------------------------------------------
    # Deserialisation helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _deserialize_request(item: dict) -> AccessRequest:
        return AccessRequest(
            request_id=item["request_id"],
            user_email=item["user_email"],
            actor_email=item["actor_email"],
            actor_type=item["actor_type"],
            request_type=item.get("request_type", "grant"),  # type: ignore[arg-type]
            platform=item["platform"],
            group_slug=item["group_slug"],
            group_email=item["group_email"],
            provider_group_id=item["provider_group_id"],
            entitlement_type=item["entitlement_type"],
            entitlement_id=item["entitlement_id"],
            status=item["status"],
            justification=item["justification"],
            resolved_approvers=item.get("resolved_approvers") or [],
            ticket_id=item.get("ticket_id"),
            requested_at=(
                datetime.fromisoformat(item["requested_at"])
                if item.get("requested_at")
                else None
            ),
            updated_at=(
                datetime.fromisoformat(item["updated_at"])
                if item.get("updated_at")
                else None
            ),
        )

    @staticmethod
    def _deserialize_decision(item: dict) -> ApprovalDecision:
        return ApprovalDecision(
            request_id=item["request_id"],
            actor_email=item["actor_email"],
            decision=item["decision"],
            comment=item.get("comment", ""),
            decided_at=datetime.fromisoformat(item["decided_at"]),
        )

    @staticmethod
    def _now() -> datetime:
        """Return current UTC time."""
        return datetime.now(tz=timezone.utc)
