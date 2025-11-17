"""Service layer for the groups module.

Thin, synchronous service functions that act as the application boundary for
controllers and in-process callers (for example Slack command handlers).

This file provides small adapter functions that accept Pydantic request
models (from `modules.groups.schemas`), call into the orchestration layer,
and schedule event dispatch in the background so callers return quickly.

Note: event dispatch is implemented here as a fire-and-forget submission to a
ThreadPoolExecutor to avoid making changes to the existing synchronous
`event_system` during this initial migration step. Step 4 of the migration
will move the dispatcher into `event_system` itself.
"""

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, List, Optional
from uuid import uuid4
from core.logging import get_module_logger
from modules.groups.core import orchestration
from modules.groups.events import system as event_system
from modules.groups.api import schemas
from modules.groups.infrastructure.validation import (
    ValidationError,
)
from modules.groups.infrastructure.idempotency import (
    get_cached_response,
    cache_response,
)
from modules.groups.infrastructure.audit import (
    create_audit_entry_from_operation,
    write_audit_entry,
)
from modules.groups import providers as _providers
from modules.groups.providers.base import (
    OperationStatus,
    OperationResult,
)

if TYPE_CHECKING:  # avoid runtime import cycles for typing
    from modules.groups.domain.types import (
        OrchestrationResponseTypedDict,
    )

logger = get_module_logger()

# Public service boundary - stable entry points for callers (controllers, Slack
# handlers, and in-process integrations). Mapping implementations live in
# `modules.groups.mappings` and are intentionally kept separate so that
# complex, provider-aware logic stays isolated and testable. Callers should
# import and use the functions exported in `__all__` below instead of
# importing helpers directly from `mappings.py`.

# Explicit public API for the groups service module. Keep this list small and
# stable to reduce churn for callers.
__all__ = [
    "add_member",
    "remove_member",
    "list_groups",
    "bulk_operations",
    "OperationResult",
]


def _check_user_is_manager(
    user_email: str,
    group_id: str,
) -> bool:
    """Check if user is a manager of the group using primary provider's is_manager().

    Uses the primary provider as the source of truth for permission verification.
    Handles OperationResult wrapper from provider's is_manager() method.

    Args:
        user_email: Email of user to check
        group_id: Group email or ID to check (e.g., "aws-admins@example.com")

    Returns:
        True if user is a manager, False otherwise
    """
    # Primary provider is guaranteed to be available - app startup fails if not
    primary_provider = _providers.get_primary_provider()

    # Use group_id directly (now in email format from primary provider)
    # Secondary providers handle their own identifier resolution
    result = primary_provider.is_manager(user_email, group_id)

    # Handle OperationResult wrapper if returned
    if isinstance(result, OperationResult):
        if result.status != OperationStatus.SUCCESS:
            logger.warning(
                "is_manager_operation_failed",
                user_email=user_email,
                group_id=group_id,
                status=result.status,
                message=result.message,
            )
            return False
        return bool(result.data.get("is_manager", False)) if result.data else False

    # Direct boolean return
    return bool(result)


def _parse_timestamp(ts: str | None) -> datetime:
    """Parse ISO timestamp returned by orchestration into a datetime.

    Orchestration uses timezone-aware ISO strings (with 'Z'). `fromisoformat`
    does not accept literal 'Z', so normalize it to '+00:00' when present.
    """
    if not ts:
        return datetime.now(timezone.utc)
    try:
        if ts.endswith("Z"):
            ts = ts[:-1] + "+00:00"
        return datetime.fromisoformat(ts)
    except Exception:  # pylint: disable=broad-except
        logger.warning("failed_to_parse_timestamp", timestamp=ts)
        return datetime.now(timezone.utc)


def _record_operation_audit(
    correlation_id: str,
    action: str,
    request: schemas.AddMemberRequest | schemas.RemoveMemberRequest,
    orchestration_result: "OrchestrationResponseTypedDict",
    success: bool,
    error_message: Optional[str] = None,
) -> None:
    """Record audit entry for group operation.

    Synchronously writes audit entry before returning response to caller.
    All operations (success or failure) are audited for compliance.

    Args:
        correlation_id: Correlation ID for tracing
        action: Operation name ("add_member" or "remove_member")
        request: Original Pydantic request model
        orchestration_result: Result from orchestration layer
        success: Whether operation succeeded
        error_message: Error message if operation failed
    """
    audit_entry = create_audit_entry_from_operation(
        correlation_id=correlation_id,
        action=action,
        group_id=request.group_id,
        provider=request.provider.value if request.provider else "unknown",
        success=success,
        requestor=request.requestor,
        member_email=request.member_email,
        justification=request.justification,
        metadata=(
            {"orchestration": orchestration_result}
            if success
            else {
                "exception_type": (
                    type(error_message).__name__ if error_message else "unknown"
                )
            }
        ),
        error_message=error_message if not success else None,
    )
    write_audit_entry(audit_entry)


def _build_action_response(
    orchestration_result: "OrchestrationResponseTypedDict",
    operation_type: schemas.OperationType,
    provider: Optional[schemas.ProviderType],
    correlation_id: str,
) -> schemas.ActionResponse:
    """Build ActionResponse from orchestration result.

    Args:
        orchestration_result: Dict returned by orchestration layer
        operation_type: Type of operation (ADD_MEMBER or REMOVE_MEMBER)
        provider: Provider type from request
        correlation_id: Correlation ID for tracing

    Returns:
        schemas.ActionResponse with all fields populated
    """
    success = orchestration_result.get("success", False)
    timestamp = _parse_timestamp(orchestration_result.get("timestamp"))

    return schemas.ActionResponse(
        success=success,
        action=operation_type,
        group_id=orchestration_result.get("group_id"),
        member_email=orchestration_result.get("member_email"),
        provider=provider,
        details={
            "orchestration": orchestration_result,
            "correlation_id": correlation_id,
        },
        timestamp=timestamp,
    )


def add_member(request: schemas.AddMemberRequest) -> schemas.ActionResponse:
    """Add a member to a group using orchestration.

    Returns an `ActionResponse` Pydantic model summarizing the result. This
    function schedules a background event `group.member.add_requested` with
    the orchestration response plus the original request payload.

    Implements idempotency: if the same idempotency_key is used within the TTL
    window, the cached response is returned without re-executing the operation.

    All operations are logged to the audit trail synchronously before returning.
    """
    # Generate correlation ID for tracing this request through the system
    correlation_id = str(uuid4())

    # Check idempotency cache first
    cached_response = get_cached_response(request.idempotency_key)
    if cached_response is not None:
        logger.info(
            "idempotent_request_detected",
            idempotency_key=request.idempotency_key,
            group_id=request.group_id,
            member_email=request.member_email,
            correlation_id=correlation_id,
        )
        return cached_response

    # Check if requestor is a manager of the group (permission enforcement)
    if not _check_user_is_manager(
        user_email=request.requestor,
        group_id=request.group_id,
    ):
        raise ValidationError(
            f"User {request.requestor} is not a manager of group {request.group_id}"
        )

    # Orchestration and secondary providers handle identifier resolution
    try:
        orch = orchestration.add_member_to_group(
            primary_group_id=request.group_id,
            member_email=request.member_email,
            justification=request.justification or "",
            provider_hint=(request.provider.value if request.provider else None),
            correlation_id=correlation_id,
        )
        response = _build_action_response(
            orchestration_result=orch,
            operation_type=schemas.OperationType.ADD_MEMBER,
            provider=request.provider,
            correlation_id=correlation_id,
        )

        _record_operation_audit(
            correlation_id=correlation_id,
            action="add_member",
            request=request,
            orchestration_result=orch,
            success=response.success,
        )

        if response.success:
            event_system.dispatch_background(
                "group.member.added",
                {
                    "orchestration": orch,
                    "request": (
                        request.model_dump()
                        if hasattr(request, "model_dump")
                        else request.dict()
                    ),
                },
            )
            cache_response(request.idempotency_key, response)
        return response
    except Exception as e:
        _record_operation_audit(
            correlation_id=correlation_id,
            action="add_member",
            request=request,
            orchestration_result=orch,
            success=response.success,
            error_message=str(e),
        )
        raise


def remove_member(
    request: schemas.RemoveMemberRequest,
) -> schemas.ActionResponse:  # noqa: C901
    """Remove a member from a group using orchestration.

    Schedules `group.member.remove_requested` as a background event and returns
    an `ActionResponse` summarizing the orchestration outcome.

    Idempotency: Requests with the same `idempotency_key` within the TTL window
    (1 hour) will return the cached response without re-executing the operation.
    Failures are not cached to preserve retry semantics.

    All operations are logged to the audit trail synchronously before returning.
    """
    # Generate correlation ID for tracing this request through the system
    correlation_id = str(uuid4())

    # Check cache for idempotent request
    cached_response = get_cached_response(request.idempotency_key)
    if cached_response:
        logger.info(
            "idempotent_request_detected",
            idempotency_key=request.idempotency_key,
            group_id=request.group_id,
            member_email=request.member_email,
            correlation_id=correlation_id,
        )
        return cached_response

    # Check if requestor is a manager of the group (permission enforcement)
    if not _check_user_is_manager(
        user_email=request.requestor,
        group_id=request.group_id,
    ):
        raise ValidationError(
            f"User {request.requestor} is not a manager of group {request.group_id}"
        )

    # Orchestration and secondary providers handle identifier resolution
    try:
        orch = orchestration.remove_member_from_group(
            primary_group_id=request.group_id,
            member_email=request.member_email,
            justification=request.justification or "",
            provider_hint=(request.provider.value if request.provider else None),
            correlation_id=correlation_id,
        )

        response = _build_action_response(
            orchestration_result=orch,
            operation_type=schemas.OperationType.REMOVE_MEMBER,
            provider=request.provider,
            correlation_id=correlation_id,
        )

        _record_operation_audit(
            correlation_id=correlation_id,
            action="remove_member",
            request=request,
            orchestration_result=orch,
            success=response.success,
        )

        if response.success:
            event_system.dispatch_background(
                "group.member.removed",
                {
                    "orchestration": orch,
                    "request": (
                        request.model_dump()
                        if hasattr(request, "model_dump")
                        else request.dict()
                    ),
                },
            )
            cache_response(request.idempotency_key, response)
        return response
    except Exception as e:
        _record_operation_audit(
            correlation_id=correlation_id,
            action="remove_member",
            request=request,
            orchestration_result=orch,
            success=response.success,
            error_message=str(e),
        )
        raise


def list_groups(request: schemas.ListGroupsRequest) -> List[Any]:
    """List groups for a user via orchestration.

    Now routes based on include_members flag to appropriate orchestration function.

    Args:
        request: ListGroupsRequest with all parameters for filtering/enrichment

    Returns:
        List of NormalizedGroup dataclasses (or dicts after normalization)
    """
    provider = request.provider.value if request.provider else None

    # Route to appropriate orchestration function based on include_members flag
    if request.include_members:
        return orchestration.list_groups_with_members_and_filters(
            member_email_filter=request.filter_by_member_email,
            member_role_filters=request.filter_by_member_role,
            include_users_details=request.include_users_details,
            provider_name=provider,
            exclude_empty_groups=request.exclude_empty_groups,
        )
    else:
        return orchestration.list_groups_simple(
            provider_name=request.provider.value if request.provider else None,
        )


def bulk_operations(
    request: schemas.BulkOperationsRequest,
) -> schemas.BulkOperationResponse:
    """Process a bulk operations request.

    Executes operations sequentially (keeps behavior simple and predictable).
    Each item is executed using the service's add/remove helpers so events are
    scheduled for individual operations.
    """
    results: List[schemas.ActionResponse] = []

    for item in request.operations:
        op = item.operation
        payload = item.payload
        try:
            if op == schemas.OperationType.ADD_MEMBER:
                add_req = schemas.AddMemberRequest(**payload)
                res = add_member(add_req)
            elif op == schemas.OperationType.REMOVE_MEMBER:
                remove_req = schemas.RemoveMemberRequest(**payload)
                res = remove_member(remove_req)
            else:
                # Unknown operation - return failure ActionResponse
                res = schemas.ActionResponse(
                    success=False,
                    action=op,
                    timestamp=datetime.now(timezone.utc),
                )
        except Exception as e:
            logger.exception("bulk_operation_item_failed", operation=op, error=str(e))
            res = schemas.ActionResponse(
                success=False,
                action=op,
                details={"error": str(e)},
                timestamp=datetime.now(timezone.utc),
            )

        results.append(res)

    # Build simple summary
    summary = {
        "success": sum(1 for r in results if r.success),
        "failed": sum(1 for r in results if not r.success),
    }

    return schemas.BulkOperationResponse(results=results, summary=summary)
