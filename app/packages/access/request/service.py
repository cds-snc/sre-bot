"""Access Requests service — lifecycle orchestration and policy enforcement.

This is the canonical place to understand the full access-request flow.

Public methods:
    submit_request()         — intake, pre-checks, persistence, notification.
    approve_request()        — approver submits affirmative decision.
    reject_request()         — approver submits rejection decision.
    cancel_request()         — requester cancels a pending request.
    get_request_status()     — read request + decision history.
    advance_from_sync_result() — handle sync_completed / sync_failed events.

The service owns no persistence directly — it delegates to
``AccessRequestRepository``.  It enforces all policy rules by calling pure
functions from ``policies.py``.

Protocol port ``AccessRequestServicePort`` decouples route handlers from the
concrete class and makes the service trivially substitutable in tests.
"""

from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Protocol

import structlog

from infrastructure.events import Event, EventDispatcher
from infrastructure.operations import OperationResult, OperationStatus
from packages.access.common.config import AccessRuntimeConfig
from packages.access.common.events import SYNC_COMPLETED, SYNC_FAILED
from packages.access.request import events as request_events
from packages.access.request.domain import (
    AccessRequest,
    ApprovalDecision,
    RequestAuditEvent,
)
from packages.access.request.policies import (
    check_entitlement_mode,
    is_auto_approvable,
    is_self_approval,
    meets_minimum_approver_count,
    resolve_approver_candidates,
)
from packages.access.request.store import AccessRequestRepository

if TYPE_CHECKING:
    from infrastructure.directory.models import DirectoryMember
    from infrastructure.directory.provider import DirectoryProvider

logger = structlog.get_logger()


class AccessRequestServicePort(Protocol):
    """Structural contract for the access request service.

    Route handlers and test stubs depend on this Protocol rather than the
    concrete class, mirroring the ``AccessSyncApplicationServicePort`` pattern.
    """

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

    def get_request_status(self, request_id: str) -> OperationResult[tuple[AccessRequest, list[ApprovalDecision]]]: ...

    def advance_from_sync_result(self, event: Event) -> None: ...


class AccessRequestService:
    """Orchestrates the full access request lifecycle.

    Constructed once per process by ``providers.get_access_request_service``.

    Args:
        repository: DynamoDB-backed repository for request persistence.
        directory: IDP directory provider for group resolution and membership
            checks.
        runtime_config: Access runtime config shared with Access Sync —
            the single source of truth for entitlement mode semantics.
        dispatcher: Event dispatcher for publishing domain events.
        fallback_approver_slug: Org-level fallback approver group slug.
        min_approver_count: Minimum number of approvals required.
    """

    def __init__(
        self,
        repository: AccessRequestRepository,
        directory: DirectoryProvider,
        runtime_config: AccessRuntimeConfig,
        dispatcher: EventDispatcher,
        fallback_approver_slug: str = "sg-org-admins",
        min_approver_count: int = 1,
    ) -> None:
        self._repo = repository
        self._directory = directory
        self._config = runtime_config
        self._dispatcher = dispatcher
        self._fallback_approver_slug = fallback_approver_slug
        self._min_approver_count = min_approver_count
        self.logger = logger

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

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
    ) -> OperationResult[AccessRequest]:
        """Accept and process a new access request through intake.

        Flow:
            1. Resolve group_slug → DirectoryGroup (group_email, provider_group_id).
            2. Pre-check entitlement mode (ephemeral/deactivated → reject).
            3. Eligibility: for grant, reject if already a member.
               For revoke, reject if not a member.
            4. For delegated: verify actor is OWNER or MANAGER of target group.
            5. Resolve approver candidates; reject with NO_APPROVERS_FOUND if empty.
            6. Check auto-approval eligibility.
            7. Persist AccessRequest + audit event.
            8. Publish domain events (APPROVAL_REQUIRED or REQUEST_APPROVED).

        Returns:
            OperationResult[AccessRequest] on success or permanent/transient
            error on failure.
        """
        request_id = str(uuid.uuid4())
        log = self.logger.bind(
            request_id=request_id,
            user_email=user_email,
            actor_email=actor_email,
            platform=platform,
            group_slug=group_slug,
            operation="submit_request",
        )
        log.info("access_request_intake_started")

        # Step 1: resolve group
        group_result = self._directory.get_group(group_slug)
        if not group_result.is_success or group_result.data is None:
            log.warning(
                "access_request_intake_rejected",
                reason="group_not_found",
                error=group_result.message,
            )
            return OperationResult.error(
                OperationStatus.NOT_FOUND,
                message=f"Group not found: {group_slug}",
                error_code="GROUP_NOT_FOUND",
            )
        directory_group = group_result.data

        if not directory_group.group_email:
            log.warning(
                "access_request_intake_rejected",
                reason="directory_group_email_required",
            )
            return OperationResult.error(
                OperationStatus.PERMANENT_ERROR,
                message="Managed group has no email address; cannot process request.",
                error_code="DIRECTORY_GROUP_EMAIL_REQUIRED",
            )

        # Derive entitlement_id from the group slug by stripping the platform prefix.
        # For sg-aws-scratch with platform=aws and prefix sg-aws-, token is "scratch".
        group_prefix = self._config.group_prefix(platform)
        entitlement_id = group_slug[len(group_prefix) :] if group_slug.startswith(group_prefix) else group_slug

        # Step 2: entitlement mode pre-check
        mode = check_entitlement_mode(self._config, platform, group_slug)
        if mode == "deactivated":
            log.warning(
                "access_request_intake_rejected",
                reason="entitlement_mode_deactivated",
                mode=mode,
            )
            return OperationResult.error(
                OperationStatus.PERMANENT_ERROR,
                message=("Automation is suspended for this group. Contact an administrator."),
                error_code="ENTITLEMENT_MODE_DEACTIVATED",
            )
        if mode == "ephemeral":
            log.warning(
                "access_request_intake_rejected",
                reason="entitlement_mode_ephemeral",
                mode=mode,
            )
            return OperationResult.error(
                OperationStatus.PERMANENT_ERROR,
                message=("This group uses ephemeral access. Use the elevated-access workflow instead."),
                error_code="ENTITLEMENT_MODE_EPHEMERAL",
            )

        # Step 3: eligibility — direction-aware membership check
        membership_result = self._directory.check_membership(directory_group.group_email, user_email)
        if membership_result.is_success and membership_result.data is not None:
            is_member = membership_result.data.is_member
            if request_type == "grant" and is_member:
                log.info(
                    "access_request_intake_rejected",
                    reason="already_provisioned",
                )
                return OperationResult.error(
                    OperationStatus.PERMANENT_ERROR,
                    message="User is already a member of this group.",
                    error_code="ALREADY_PROVISIONED",
                )
            if request_type == "revoke" and not is_member:
                log.info(
                    "access_request_intake_rejected",
                    reason="not_provisioned",
                )
                return OperationResult.error(
                    OperationStatus.PERMANENT_ERROR,
                    message="User is not a member of this group.",
                    error_code="NOT_PROVISIONED",
                )

        # Step 4: delegated actor authorization — actor must be OWNER or MANAGER
        # of the specific target group, not a member of a global manager group.
        if actor_type == "delegated":
            members_result = self._directory.get_group_members(
                group_key=directory_group.group_email,
                include_member_types={"USER"},
            )
            if not members_result.is_success:
                log.warning(
                    "access_request_intake_rejected",
                    reason="delegated_actor_membership_check_failed",
                )
                return OperationResult.error(
                    OperationStatus.TRANSIENT_ERROR,
                    message="Could not verify delegated actor authorization.",
                    error_code="ACTOR_AUTHORIZATION_CHECK_FAILED",
                )
            members = members_result.data or []
            actor_is_owner_or_manager = any(
                m.email.lower() == actor_email.lower() and m.role is not None and m.role.upper() in ("OWNER", "MANAGER")
                for m in members
            )
            if not actor_is_owner_or_manager:
                log.warning(
                    "access_request_intake_rejected",
                    reason="delegated_actor_not_authorized",
                )
                return OperationResult.error(
                    OperationStatus.PERMANENT_ERROR,
                    message="Actor is not an owner or manager of the target group.",
                    error_code="DELEGATED_ACTOR_NOT_AUTHORIZED",
                )

        # Step 5: resolve approvers
        approvers = resolve_approver_candidates(
            directory_group=directory_group,
            fallback_slug=self._fallback_approver_slug,
            directory=self._directory,
        )
        if not approvers:
            log.error(
                "no_approvers_found",
                group_slug=group_slug,
                fallback=self._fallback_approver_slug,
            )
            self._dispatcher.dispatch_background(
                Event(
                    event_type="access_requests.operator_alert",
                    metadata={
                        "reason": "NO_APPROVERS_FOUND",
                        "group_slug": group_slug,
                        "platform": platform,
                    },
                )
            )
            return OperationResult.error(
                OperationStatus.PERMANENT_ERROR,
                message="No eligible approvers found for this group.",
                error_code="NO_APPROVERS_FOUND",
            )

        # Step 6: auto-approval check
        auto_approved = is_auto_approvable(
            actor_type=actor_type,
            entitlement_type=entitlement_type,
        )

        now = datetime.now(tz=UTC)
        initial_status = "approved" if auto_approved else "pending_approval"

        request = AccessRequest(
            request_id=request_id,
            user_email=user_email,
            actor_email=actor_email,
            actor_type=actor_type,  # type: ignore[arg-type]
            request_type=request_type,  # type: ignore[arg-type]
            platform=platform,
            group_slug=group_slug,
            group_email=directory_group.group_email,
            provider_group_id=directory_group.provider_group_id,
            entitlement_type=entitlement_type,
            entitlement_id=entitlement_id,
            status=initial_status,  # type: ignore[arg-type]
            justification=justification,
            resolved_approvers=approvers,
            ticket_id=ticket_id,
            requested_at=now,
            updated_at=now,
        )

        # Step 7: persist
        self._repo.save_request(request)
        self._repo.save_audit_event(
            RequestAuditEvent(
                event_type="access_request_submitted",
                request_id=request_id,
                actor_email=actor_email,
                timestamp=now,
                metadata={"status": initial_status, "auto_approved": auto_approved},
            )
        )

        # Step 8: for auto-approved requests, write the membership change to the
        # IDP immediately. Direction is determined by request_type.
        if auto_approved:
            idp_result: OperationResult[DirectoryMember] | OperationResult[None]
            if request_type == "grant":
                idp_result = self._directory.add_group_member(directory_group.group_email, user_email)
            else:
                idp_result = self._directory.remove_group_member(directory_group.group_email, user_email)
            if not idp_result.is_success:
                fail_now = datetime.now(tz=UTC)
                failed = replace(request, status="failed", updated_at=fail_now)
                self._repo.save_request(failed)
                self._repo.save_audit_event(
                    RequestAuditEvent(
                        event_type="access_request_failed",
                        request_id=request_id,
                        actor_email="system",
                        timestamp=fail_now,
                        metadata={
                            "reason": "idp_write_failed",
                            "error": idp_result.message,
                        },
                    )
                )
                log.error(
                    "access_request_idp_write_failed",
                    request_id=request_id,
                    error=idp_result.message,
                )
                return OperationResult.error(
                    OperationStatus.TRANSIENT_ERROR,
                    message="Failed to update IDP membership. The request has been marked as failed.",
                    error_code="IDP_WRITE_FAILED",
                )

        # Step 9: publish domain events
        if auto_approved:
            log.info("access_request_auto_approved", request_id=request_id)
            self._dispatcher.dispatch_background(
                Event(
                    event_type=request_events.REQUEST_SUBMITTED,
                    user_email=user_email,
                    metadata={
                        "request_id": request_id,
                        "platform": platform,
                        "group_slug": group_slug,
                    },
                )
            )
            self._dispatcher.dispatch_background(
                Event(
                    event_type=request_events.REQUEST_APPROVED,
                    user_email=user_email,
                    metadata={
                        "request_id": request_id,
                        "platform": platform,
                        "request_type": request_type,
                        "entitlement_type": entitlement_type,
                        "entitlement_id": entitlement_id,
                    },
                )
            )
        else:
            log.info(
                "access_request_submitted",
                request_id=request_id,
                approver_count=len(approvers),
            )
            self._dispatcher.dispatch_background(
                Event(
                    event_type=request_events.REQUEST_SUBMITTED,
                    user_email=user_email,
                    metadata={
                        "request_id": request_id,
                        "platform": platform,
                        "group_slug": group_slug,
                    },
                )
            )
            self._dispatcher.dispatch_background(
                Event(
                    event_type=request_events.APPROVAL_REQUIRED,
                    user_email=user_email,
                    metadata={
                        "request_id": request_id,
                        "resolved_approvers": approvers,
                    },
                )
            )

        return OperationResult.success(
            data=request,
            message="Access request submitted.",
        )

    def approve_request(
        self,
        request_id: str,
        approver_email: str,
        comment: str = "",
    ) -> OperationResult[tuple[AccessRequest, list[ApprovalDecision]]]:
        """Record an approval decision and advance state when threshold is met.

        Flow:
            1. Load request; reject if not pending_approval.
            2. Verify approver is in resolved_approvers.
            3. Enforce no self-approval.
            4. Persist ApprovalDecision.
            5. Check minimum approver count; if met, transition to approved
               and publish access_request_approved.

        Returns:
            OperationResult[tuple[AccessRequest, List[ApprovalDecision]]] with
            updated state and decision history.
        """
        log = self.logger.bind(
            request_id=request_id,
            approver_email=approver_email,
            operation="approve_request",
        )
        log.info("access_request_approval_started")

        request, decisions = self._repo.get_request_with_decisions(request_id)
        if request is None:
            return OperationResult.error(
                OperationStatus.NOT_FOUND,
                message=f"Request not found: {request_id}",
                error_code="REQUEST_NOT_FOUND",
            )

        if request.status != "pending_approval":
            return OperationResult.error(
                OperationStatus.PERMANENT_ERROR,
                message=(f"Request is in '{request.status}' state; only 'pending_approval' requests can be approved."),
                error_code="INVALID_STATE_TRANSITION",
            )

        if approver_email.lower() not in [a.lower() for a in request.resolved_approvers]:
            return OperationResult.error(
                OperationStatus.PERMANENT_ERROR,
                message="Actor is not in the resolved approver list.",
                error_code="APPROVER_NOT_AUTHORIZED",
            )

        if is_self_approval(request, approver_email):
            return OperationResult.error(
                OperationStatus.PERMANENT_ERROR,
                message="Self-approval is not permitted.",
                error_code="SELF_APPROVAL_DENIED",
            )

        now = datetime.now(tz=UTC)
        decision = ApprovalDecision(
            request_id=request_id,
            actor_email=approver_email,
            decision="approved",
            comment=comment,
            decided_at=now,
        )
        self._repo.save_decision(decision)
        self._repo.save_audit_event(
            RequestAuditEvent(
                event_type="access_request_approved",
                request_id=request_id,
                actor_email=approver_email,
                timestamp=now,
                metadata={"comment": comment},
            )
        )

        all_decisions = decisions + [decision]
        if meets_minimum_approver_count(all_decisions, self._min_approver_count):
            # Write the membership change to the IDP — source of truth — before
            # publishing the event. Direction is determined by request_type.
            idp_result: OperationResult[DirectoryMember] | OperationResult[None]
            if request.request_type == "grant":
                idp_result = self._directory.add_group_member(request.group_email, request.user_email)
            else:
                idp_result = self._directory.remove_group_member(request.group_email, request.user_email)
            if not idp_result.is_success:
                failed = replace(request, status="failed", updated_at=now)
                self._repo.save_request(failed)
                self._repo.save_audit_event(
                    RequestAuditEvent(
                        event_type="access_request_failed",
                        request_id=request_id,
                        actor_email="system",
                        timestamp=now,
                        metadata={
                            "reason": "idp_write_failed",
                            "error": idp_result.message,
                        },
                    )
                )
                log.error(
                    "access_request_idp_write_failed",
                    request_id=request_id,
                    error=idp_result.message,
                )
                return OperationResult.error(
                    OperationStatus.TRANSIENT_ERROR,
                    message="Failed to update IDP membership. The request has been marked as failed.",
                    error_code="IDP_WRITE_FAILED",
                )

            updated = replace(request, status="approved", updated_at=now)
            self._repo.save_request(updated)
            log.info("access_request_approved", request_id=request_id)
            self._dispatcher.dispatch_background(
                Event(
                    event_type=request_events.REQUEST_APPROVED,
                    user_email=request.user_email,
                    metadata={
                        "request_id": request_id,
                        "platform": request.platform,
                        "request_type": request.request_type,
                        "entitlement_type": request.entitlement_type,
                        "entitlement_id": request.entitlement_id,
                    },
                )
            )
            return OperationResult.success(
                data=(updated, all_decisions),
                message="Request approved and access provisioning triggered.",
            )

        log.info("access_request_decision_recorded", request_id=request_id)
        return OperationResult.success(
            data=(request, all_decisions),
            message="Approval recorded; waiting for additional approvers.",
        )

    def reject_request(
        self,
        request_id: str,
        approver_email: str,
        comment: str,
    ) -> OperationResult[tuple[AccessRequest, list[ApprovalDecision]]]:
        """Record a rejection decision and close the request.

        Returns:
            OperationResult[tuple[AccessRequest, List[ApprovalDecision]]] with
            updated state and decision history.
        """
        log = self.logger.bind(
            request_id=request_id,
            approver_email=approver_email,
            operation="reject_request",
        )
        log.info("access_request_rejection_started")

        request, decisions = self._repo.get_request_with_decisions(request_id)
        if request is None:
            return OperationResult.error(
                OperationStatus.NOT_FOUND,
                message=f"Request not found: {request_id}",
                error_code="REQUEST_NOT_FOUND",
            )

        if request.status != "pending_approval":
            return OperationResult.error(
                OperationStatus.PERMANENT_ERROR,
                message=(f"Request is in '{request.status}' state; only 'pending_approval' requests can be rejected."),
                error_code="INVALID_STATE_TRANSITION",
            )

        if approver_email.lower() not in [a.lower() for a in request.resolved_approvers]:
            return OperationResult.error(
                OperationStatus.PERMANENT_ERROR,
                message="Actor is not in the resolved approver list.",
                error_code="APPROVER_NOT_AUTHORIZED",
            )

        now = datetime.now(tz=UTC)
        decision = ApprovalDecision(
            request_id=request_id,
            actor_email=approver_email,
            decision="rejected",
            comment=comment,
            decided_at=now,
        )
        self._repo.save_decision(decision)
        all_decisions = decisions + [decision]

        updated = replace(request, status="rejected", updated_at=now)
        self._repo.save_request(updated)
        self._repo.save_audit_event(
            RequestAuditEvent(
                event_type="access_request_rejected",
                request_id=request_id,
                actor_email=approver_email,
                timestamp=now,
                metadata={"comment": comment},
            )
        )

        log.info("access_request_rejected", request_id=request_id)
        self._dispatcher.dispatch_background(
            Event(
                event_type=request_events.REQUEST_REJECTED,
                user_email=request.user_email,
                metadata={
                    "request_id": request_id,
                    "platform": request.platform,
                },
            )
        )
        return OperationResult.success(
            data=(updated, all_decisions),
            message="Request rejected.",
        )

    def cancel_request(
        self,
        request_id: str,
        actor_email: str,
        comment: str = "",
    ) -> OperationResult[tuple[AccessRequest, list[ApprovalDecision]]]:
        """Cancel a pending request at the requester's initiative.

        Only ``submitted`` or ``pending_approval`` requests may be cancelled.
        Only the original requester (actor_email) may cancel.

        Returns:
            OperationResult[tuple[AccessRequest, List[ApprovalDecision]]] with
            updated state and current decision history.
        """
        log = self.logger.bind(
            request_id=request_id,
            actor_email=actor_email,
            operation="cancel_request",
        )
        log.info("access_request_cancellation_started")

        request, decisions = self._repo.get_request_with_decisions(request_id)
        if request is None:
            return OperationResult.error(
                OperationStatus.NOT_FOUND,
                message=f"Request not found: {request_id}",
                error_code="REQUEST_NOT_FOUND",
            )

        if request.status not in ("submitted", "pending_approval"):
            return OperationResult.error(
                OperationStatus.PERMANENT_ERROR,
                message=(f"Request is in '{request.status}' state and cannot be cancelled."),
                error_code="INVALID_STATE_TRANSITION",
            )

        if actor_email.lower() != request.actor_email.lower():
            return OperationResult.error(
                OperationStatus.PERMANENT_ERROR,
                message="Only the original requester may cancel this request.",
                error_code="CANCELLATION_NOT_AUTHORIZED",
            )

        now = datetime.now(tz=UTC)
        updated = replace(request, status="cancelled", updated_at=now)
        self._repo.save_request(updated)
        self._repo.save_audit_event(
            RequestAuditEvent(
                event_type="access_request_cancelled",
                request_id=request_id,
                actor_email=actor_email,
                timestamp=now,
                metadata={"comment": comment},
            )
        )

        log.info("access_request_cancelled", request_id=request_id)
        self._dispatcher.dispatch_background(
            Event(
                event_type=request_events.REQUEST_CANCELLED,
                user_email=request.user_email,
                metadata={"request_id": request_id, "platform": request.platform},
            )
        )
        return OperationResult.success(
            data=(updated, decisions),
            message="Request cancelled.",
        )

    def retry_request(
        self,
        request_id: str,
        actor_email: str,
        comment: str = "",
    ) -> OperationResult[tuple[AccessRequest, list[ApprovalDecision]]]:
        """Re-attempt IDP provisioning for a request that previously failed.

        Only ``failed`` requests can be retried.  Only an actor present in
        ``resolved_approvers`` may trigger a retry — this is an operator-level
        action confirming the underlying infrastructure issue has been resolved.

        Flow:
            1. Load request; reject if not ``failed``.
            2. Verify actor is in resolved_approvers.
            3. Re-attempt directory.add_group_member().
            4. On success: transition to ``approved``, save audit event, dispatch
               REQUEST_APPROVED so Access Sync re-propagates to external platforms.
            5. On failure: keep as ``failed``, save audit event, return transient error.

        Returns:
            OperationResult[tuple[AccessRequest, List[ApprovalDecision]]] with
            updated state and current decision history.
        """
        log = self.logger.bind(
            request_id=request_id,
            actor_email=actor_email,
            operation="retry_request",
        )
        log.info("access_request_retry_started")

        request, decisions = self._repo.get_request_with_decisions(request_id)
        if request is None:
            return OperationResult.error(
                OperationStatus.NOT_FOUND,
                message=f"Request not found: {request_id}",
                error_code="REQUEST_NOT_FOUND",
            )

        if request.status != "failed":
            return OperationResult.error(
                OperationStatus.PERMANENT_ERROR,
                message=(f"Request is in '{request.status}' state; only 'failed' requests can be retried."),
                error_code="INVALID_STATE_TRANSITION",
            )

        if actor_email.lower() not in [a.lower() for a in request.resolved_approvers]:
            return OperationResult.error(
                OperationStatus.PERMANENT_ERROR,
                message="Only an authorized approver may retry a failed request.",
                error_code="APPROVER_NOT_AUTHORIZED",
            )

        now = datetime.now(tz=UTC)

        idp_result: OperationResult[DirectoryMember] | OperationResult[None]
        if request.request_type == "grant":
            idp_result = self._directory.add_group_member(request.group_email, request.user_email)
        else:
            idp_result = self._directory.remove_group_member(request.group_email, request.user_email)
        if not idp_result.is_success:
            self._repo.save_audit_event(
                RequestAuditEvent(
                    event_type="access_request_retry_failed",
                    request_id=request_id,
                    actor_email=actor_email,
                    timestamp=now,
                    metadata={
                        "reason": "idp_write_failed",
                        "error": idp_result.message,
                        "comment": comment,
                    },
                )
            )
            log.error(
                "access_request_retry_idp_write_failed",
                request_id=request_id,
                error=idp_result.message,
            )
            return OperationResult.error(
                OperationStatus.TRANSIENT_ERROR,
                message="IDP membership write failed again. Request remains in 'failed' state.",
                error_code="IDP_WRITE_FAILED",
            )

        updated = replace(request, status="approved", updated_at=now)
        self._repo.save_request(updated)
        self._repo.save_audit_event(
            RequestAuditEvent(
                event_type="access_request_retry_succeeded",
                request_id=request_id,
                actor_email=actor_email,
                timestamp=now,
                metadata={"comment": comment},
            )
        )
        log.info("access_request_retry_succeeded", request_id=request_id)
        self._dispatcher.dispatch_background(
            Event(
                event_type=request_events.REQUEST_APPROVED,
                user_email=request.user_email,
                metadata={
                    "request_id": request_id,
                    "platform": request.platform,
                    "request_type": request.request_type,
                    "entitlement_type": request.entitlement_type,
                    "entitlement_id": request.entitlement_id,
                },
            )
        )
        return OperationResult.success(
            data=(updated, decisions),
            message="Retry succeeded. Access provisioning re-triggered.",
        )

    def get_request_status(self, request_id: str) -> OperationResult[tuple[AccessRequest, list[ApprovalDecision]]]:
        """Return the access request and all recorded decisions.

        Returns:
            OperationResult[tuple[AccessRequest, List[ApprovalDecision]]]
        """
        log = self.logger.bind(request_id=request_id, operation="get_request_status")
        log.info("access_request_status_queried")

        request, decisions = self._repo.get_request_with_decisions(request_id)
        if request is None:
            return OperationResult.error(
                OperationStatus.NOT_FOUND,
                message=f"Request not found: {request_id}",
                error_code="REQUEST_NOT_FOUND",
            )

        return OperationResult.success(data=(request, decisions))

    def advance_from_sync_result(self, event: Event) -> None:
        """Handle sync_completed or sync_failed events from Access Sync.

        Matches the event back to the originating access request via
        ``request_id`` in the event metadata, then transitions the request
        to ``completed`` or ``failed``.

        Idempotent: repeated delivery of the same event for an already-terminal
        request is a no-op.

        Args:
            event: Domain event with ``event_type`` SYNC_COMPLETED or SYNC_FAILED.
        """
        metadata = event.metadata or {}
        request_id = metadata.get("request_id", "") if isinstance(metadata, dict) else ""
        if not request_id:
            return

        log = self.logger.bind(
            request_id=request_id,
            event_type=event.event_type,
            operation="advance_from_sync_result",
        )

        request, _ = self._repo.get_request_with_decisions(request_id)
        if request is None:
            log.warning(
                "advance_from_sync_result_request_not_found",
                request_id=request_id,
            )
            return

        if request.status not in ("approved",):
            log.info(
                "advance_from_sync_result_skipped",
                current_status=request.status,
            )
            return

        now = datetime.now(tz=UTC)

        if event.event_type == SYNC_COMPLETED:
            updated = replace(request, status="completed", updated_at=now)
            event_type = request_events.REQUEST_COMPLETED
            log.info("access_request_completed", request_id=request_id)
        elif event.event_type == SYNC_FAILED:
            updated = replace(request, status="failed", updated_at=now)
            event_type = request_events.REQUEST_FAILED
            log.error(
                "access_request_failed",
                request_id=request_id,
                error_code=metadata.get("error_code"),
            )
        else:
            return

        self._repo.save_request(updated)
        self._repo.save_audit_event(
            RequestAuditEvent(
                event_type=event_type,
                request_id=request_id,
                actor_email="system",
                timestamp=now,
                metadata={"triggered_by": event.event_type},
            )
        )
        self._dispatcher.dispatch_background(
            Event(
                event_type=event_type,
                user_email=request.user_email,
                metadata={"request_id": request_id, "platform": request.platform},
            )
        )
