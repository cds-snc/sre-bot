"""Service layer for the groups module.

Thin, synchronous service functions that act as the application boundary for
controllers and in-process callers (for example Slack command handlers).

This file provides small adapter functions that accept Pydantic request
models (from `modules.groups.schemas`), call into the orchestration layer,
and schedule event dispatch in the background so callers return quickly.
"""

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, List, Optional
from uuid import uuid4
import structlog
from infrastructure.events import dispatch_background, Event
from infrastructure.idempotency import get_cache
from modules.groups.core import orchestration
from modules.groups.api import schemas
from modules.groups.domain.errors import ValidationError
from modules.groups import providers as _providers
from modules.groups.providers.base import (
    OperationStatus,
    OperationResult,
)

if TYPE_CHECKING:
    from modules.groups.domain.types import (
        OrchestrationResponseTypedDict,
    )

logger = structlog.get_logger()

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
    function schedules a background event `group.member.added` with
    the orchestration response plus the original request payload.

    Implements idempotency: if the same idempotency_key is used within the TTL
    window, the cached response is returned without re-executing the operation.

    Audit logging is handled automatically by the centralized event system.
    """
    correlation_id = uuid4()
    idempotency_cache = get_cache()

    cached_data = idempotency_cache.get(request.idempotency_key)
    if cached_data is not None:
        logger.info(
            "idempotent_request_detected",
            idempotency_key=request.idempotency_key,
            group_id=request.group_id,
            member_email=request.member_email,
            correlation_id=correlation_id,
        )
        return schemas.ActionResponse(**cached_data)

    if not _check_user_is_manager(
        user_email=request.requestor,
        group_id=request.group_id,
    ):
        raise ValidationError(
            f"User {request.requestor} is not a manager of group {request.group_id}"
        )

    try:
        orch = orchestration.add_member_to_group(
            primary_group_id=request.group_id,
            member_email=request.member_email,
            justification=request.justification or "",
            provider_hint=(request.provider.value if request.provider else None),
            correlation_id=str(correlation_id),
        )
        response = _build_action_response(
            orchestration_result=orch,
            operation_type=schemas.OperationType.ADD_MEMBER,
            provider=request.provider,
            correlation_id=str(correlation_id),
        )

        if response.success:
            event = Event(
                event_type="group.member.added",
                correlation_id=correlation_id,
                user_email=request.requestor,
                metadata={
                    "orchestration": orch,
                    "request": request.model_dump(),
                },
            )
            dispatch_background(event)
            idempotency_cache.set(
                request.idempotency_key,
                response.model_dump(mode="json"),
                ttl_seconds=3600,
            )
        return response
    except Exception as e:
        logger.error(
            "add_member_failed",
            correlation_id=correlation_id,
            group_id=request.group_id,
            member_email=request.member_email,
            error=str(e),
        )
        raise


def remove_member(
    request: schemas.RemoveMemberRequest,
) -> schemas.ActionResponse:
    """Remove a member from a group using orchestration.

    Schedules `group.member.removed` as a background event and returns
    an `ActionResponse` summarizing the orchestration outcome.

    Idempotency: Requests with the same `idempotency_key` within the TTL window
    (1 hour) will return the cached response without re-executing the operation.

    Audit logging is handled automatically by the centralized event system.
    """
    correlation_id = uuid4()
    idempotency_cache = get_cache()

    cached_data = idempotency_cache.get(request.idempotency_key)
    if cached_data:
        logger.info(
            "idempotent_request_detected",
            idempotency_key=request.idempotency_key,
            group_id=request.group_id,
            member_email=request.member_email,
            correlation_id=correlation_id,
        )
        return schemas.ActionResponse(**cached_data)

    if not _check_user_is_manager(
        user_email=request.requestor,
        group_id=request.group_id,
    ):
        raise ValidationError(
            f"User {request.requestor} is not a manager of group {request.group_id}"
        )

    try:
        orch = orchestration.remove_member_from_group(
            primary_group_id=request.group_id,
            member_email=request.member_email,
            justification=request.justification or "",
            provider_hint=(request.provider.value if request.provider else None),
            correlation_id=str(correlation_id),
        )

        response = _build_action_response(
            orchestration_result=orch,
            operation_type=schemas.OperationType.REMOVE_MEMBER,
            provider=request.provider,
            correlation_id=str(correlation_id),
        )

        if response.success:
            event = Event(
                event_type="group.member.removed",
                correlation_id=correlation_id,
                user_email=request.requestor,
                metadata={
                    "orchestration": orch,
                    "request": request.model_dump(),
                },
            )
            dispatch_background(event)
            idempotency_cache.set(
                request.idempotency_key,
                response.model_dump(mode="json"),
                ttl_seconds=3600,
            )
        return response
    except Exception as e:
        logger.error(
            "remove_member_failed",
            correlation_id=correlation_id,
            group_id=request.group_id,
            member_email=request.member_email,
            error=str(e),
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
    correlation_id = uuid4()
    provider = request.provider.value if request.provider else None

    # Route to appropriate orchestration function based on include_members flag
    if request.include_members:
        groups = orchestration.list_groups_with_members_and_filters(
            member_email_filter=request.filter_by_member_email,
            member_role_filters=request.filter_by_member_role,
            include_users_details=request.include_users_details,
            provider_name=provider,
            exclude_empty_groups=request.exclude_empty_groups,
        )
    else:
        groups = orchestration.list_groups_simple(
            provider_name=request.provider.value if request.provider else None,
        )

    # Emit event for audit and tracking
    # Use the same nested structure as add_member/remove_member for consistency
    event = Event(
        event_type="group.listed",
        correlation_id=correlation_id,
        user_email=request.requestor,
        metadata={
            "request": {
                "provider": provider,
                "requestor": request.requestor,
                "include_members": request.include_members,
                "filter_by_member_email": request.filter_by_member_email,
                "filter_by_member_role": request.filter_by_member_role,
                "include_users_details": request.include_users_details,
                "exclude_empty_groups": request.exclude_empty_groups,
            },
            "orchestration": {
                "correlation_id": correlation_id,
                "action": "list_groups",
                "provider": provider or "unknown",
                "success": True,
                "group_count": len(groups) if groups else 0,
            },
        },
    )
    dispatch_background(event)

    return groups


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
