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
from typing import Any, List
from uuid import uuid4
from core.logging import get_module_logger
from modules.groups.core import orchestration
from modules.groups.core import orchestration_responses as orr
from modules.groups.events import system as event_system
from modules.groups.api import schemas
from modules.groups.infrastructure.validation import (
    validate_group_id,
    validate_provider_type,
    validate_justification,
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
    GroupProvider,
    OperationResult,
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
    "validate_group_in_provider",
    "OperationResult",
]


def _check_user_is_manager(
    user_email: str, group_id: str, provider_type: str | None = None
) -> bool:
    """Check if user is a manager of the group using primary provider's is_manager().

    Uses the primary provider as the source of truth for permission verification.
    Handles OperationResult wrapper from provider's is_manager() method.

    Args:
        user_email: Email of user to check
        group_id: Group email or ID to check (e.g., "aws-admins@example.com")
        provider_type: Ignored (kept for backward compatibility)

    Returns:
        True if user is a manager, False otherwise

    Raises:
        ValueError: If primary provider not available or group lookup fails
    """
    try:
        try:
            # Use registry helper to obtain the primary provider instance
            primary_provider = _providers.get_primary_provider()
        except Exception as e:
            # Normalize registry errors to ValueError for callers
            raise ValueError(f"Primary provider not available: {e}") from e

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

    except Exception as e:
        logger.warning(
            "permission_check_failed",
            error=str(e),
            user_email=user_email,
            group_id=group_id,
        )
        raise


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
    except Exception:
        logger.warning("failed_to_parse_timestamp", timestamp=ts)
        return datetime.now(timezone.utc)


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

    # Semantic validation: move input validation responsibility to the service
    provider_type = request.provider.value if request.provider else None

    try:
        # Validate provider type
        if provider_type and not validate_provider_type(provider_type):
            raise ValidationError(f"Invalid provider: {provider_type}")

        # Validate group ID format
        validate_group_id(request.group_id, provider_type or "")

        # Validate justification (required by default per config)
        validate_justification(request.justification, required=True)
    except ValidationError as e:
        logger.warning(
            "validation_error_add_member",
            error=str(e),
            group_id=request.group_id,
            member_email=request.member_email,
            provider=provider_type,
        )
        raise

    # Check if requestor is a manager of the group (permission enforcement)
    try:
        if not _check_user_is_manager(
            user_email=request.requestor,
            group_id=request.group_id,
            provider_type=provider_type,
        ):
            raise ValidationError(
                f"User {request.requestor} is not a manager of group {request.group_id}"
            )
    except ValidationError:
        raise
    except Exception as e:
        logger.warning(
            "permission_check_error_add_member",
            error=str(e),
            requestor=request.requestor,
            group_id=request.group_id,
        )
        raise ValidationError(f"Permission check failed: {e}") from e

    # Use group_id directly (now in email format)
    # Orchestration and secondary providers handle identifier resolution
    try:
        orch = orchestration.add_member_to_group(
            primary_group_id=request.group_id,
            member_email=request.member_email,
            justification=request.justification or "",
            provider_hint=(request.provider.value if request.provider else None),
        )
        # If orchestration returns OperationResult objects (raw), map them to
        # the existing orchestration response dict shape using the formatter.
        if (
            isinstance(orch, dict)
            and "primary" in orch
            and not isinstance(orch.get("primary"), dict)
        ):
            try:
                formatted = orr.format_orchestration_response(
                    orch["primary"],
                    orch.get("propagation", {}),
                    orch.get("partial_failures", False),
                    orch.get("correlation_id"),
                    action=orch.get("action", "add_member"),
                    group_id=orch.get("group_id"),
                    member_email=orch.get("member_email"),
                )
            except Exception:
                # Fallback to original raw form if formatting fails
                formatted = orch
        else:
            formatted = orch

        success = bool(
            formatted.get("success", False) if isinstance(formatted, dict) else False
        )

        # Write audit entry (synchronous, before returning)
        audit_entry = create_audit_entry_from_operation(
            correlation_id=correlation_id,
            action="add_member",
            group_id=request.group_id,
            provider=request.provider.value if request.provider else "unknown",
            success=success,
            requestor=request.requestor,
            member_email=request.member_email,
            justification=request.justification,
            metadata={"orchestration": formatted},
        )
        write_audit_entry(audit_entry)

        # Fire-and-forget event for downstream handlers (audit, notifications)
        try:
            event_system.dispatch_background(
                "group.member.added",
                (
                    {"orchestration": formatted, "request": request.model_dump()}
                    if hasattr(request, "model_dump")
                    else {"orchestration": formatted, "request": request.dict()}
                ),
            )
        except Exception:  # pragma: no cover - defensive
            logger.exception("failed_to_schedule_add_member_event")

        ts = _parse_timestamp(
            formatted.get("timestamp") if isinstance(formatted, dict) else None
        )

        response = schemas.ActionResponse(
            success=success,
            action=schemas.OperationType.ADD_MEMBER,
            group_id=(
                formatted.get("group_id") if isinstance(formatted, dict) else None
            ),
            member_email=(
                formatted.get("member_email") if isinstance(formatted, dict) else None
            ),
            provider=request.provider,
            details={"orchestration": formatted, "correlation_id": correlation_id},
            timestamp=ts,
        )

        # Cache successful responses only
        if response.success:
            cache_response(request.idempotency_key, response)

        return response

    except Exception as e:
        # Write failure audit entry
        audit_entry = create_audit_entry_from_operation(
            correlation_id=correlation_id,
            action="add_member",
            group_id=request.group_id,
            provider=request.provider.value if request.provider else "unknown",
            success=False,
            requestor=request.requestor,
            member_email=request.member_email,
            justification=request.justification,
            error_message=str(e),
            metadata={"exception_type": type(e).__name__},
        )
        write_audit_entry(audit_entry)
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

    # Semantic validation performed at service boundary
    provider_type = request.provider.value if request.provider else None

    try:
        # Validate provider type
        if provider_type and not validate_provider_type(provider_type):
            raise ValidationError(f"Invalid provider: {provider_type}")

        # Validate group ID format
        validate_group_id(request.group_id, provider_type or "")

        # Validate justification (required by default per config)
        validate_justification(request.justification, required=True)
    except ValidationError as e:
        logger.warning(
            "validation_error_remove_member",
            error=str(e),
            group_id=request.group_id,
            member_email=request.member_email,
            provider=provider_type,
        )
        raise

    # Check if requestor is a manager of the group (permission enforcement)
    try:
        if not _check_user_is_manager(
            user_email=request.requestor,
            group_id=request.group_id,
            provider_type=provider_type,
        ):
            raise ValidationError(
                f"User {request.requestor} is not a manager of group {request.group_id}"
            )
    except ValidationError:
        raise
    except Exception as e:
        logger.warning(
            "permission_check_error_remove_member",
            error=str(e),
            requestor=request.requestor,
            group_id=request.group_id,
        )
        raise ValidationError(f"Permission check failed: {e}") from e

    # Use group_id directly (now in email format)
    # Orchestration and secondary providers handle identifier resolution
    try:
        orch = orchestration.remove_member_from_group(
            primary_group_id=request.group_id,
            member_email=request.member_email,
            justification=request.justification or "",
            provider_hint=(request.provider.value if request.provider else None),
        )
        # Format orchestration response when orchestration returns raw OperationResult objects
        if (
            isinstance(orch, dict)
            and "primary" in orch
            and not isinstance(orch.get("primary"), dict)
        ):
            try:
                formatted = orr.format_orchestration_response(
                    orch["primary"],
                    orch.get("propagation", {}),
                    orch.get("partial_failures", False),
                    orch.get("correlation_id"),
                    action=orch.get("action", "remove_member"),
                    group_id=orch.get("group_id"),
                    member_email=orch.get("member_email"),
                )
            except Exception:
                formatted = orch
        else:
            formatted = orch

        success = bool(
            formatted.get("success", False) if isinstance(formatted, dict) else False
        )

        # Write audit entry (synchronous, before returning)
        audit_entry = create_audit_entry_from_operation(
            correlation_id=correlation_id,
            action="remove_member",
            group_id=request.group_id,
            provider=request.provider.value if request.provider else "unknown",
            success=success,
            requestor=request.requestor,
            member_email=request.member_email,
            justification=request.justification,
            metadata={"orchestration": formatted},
        )
        write_audit_entry(audit_entry)

        try:
            event_system.dispatch_background(
                "group.member.removed",
                (
                    {"orchestration": formatted, "request": request.model_dump()}
                    if hasattr(request, "model_dump")
                    else {"orchestration": formatted, "request": request.dict()}
                ),
            )
        except Exception:  # pragma: no cover - defensive
            logger.exception("failed_to_schedule_remove_member_event")

        ts = _parse_timestamp(
            formatted.get("timestamp") if isinstance(formatted, dict) else None
        )

        response = schemas.ActionResponse(
            success=success,
            action=schemas.OperationType.REMOVE_MEMBER,
            group_id=(
                formatted.get("group_id") if isinstance(formatted, dict) else None
            ),
            member_email=(
                formatted.get("member_email") if isinstance(formatted, dict) else None
            ),
            provider=request.provider,
            details={"orchestration": formatted, "correlation_id": correlation_id},
            timestamp=ts,
        )

        # Cache successful responses for idempotency
        if response.success:
            cache_response(request.idempotency_key, response)

        return response

    except Exception as e:
        # Write failure audit entry
        audit_entry = create_audit_entry_from_operation(
            correlation_id=correlation_id,
            action="remove_member",
            group_id=request.group_id,
            provider=request.provider.value if request.provider else "unknown",
            success=False,
            requestor=request.requestor,
            member_email=request.member_email,
            justification=request.justification,
            error_message=str(e),
            metadata={"exception_type": type(e).__name__},
        )
        write_audit_entry(audit_entry)
        raise


def list_groups(request: schemas.ListGroupsRequest) -> List[Any]:
    """List groups for a user via orchestration read helpers.

    Returns a list of `NormalizedGroup` dataclasses as produced by the
    orchestration layer. Controllers may convert these to serializable dicts
    using `modules.groups.models.as_canonical_dict`.
    """
    provider_hint = request.provider.value if request.provider else None
    return orchestration.list_groups_for_user(request.user_email, provider_hint)


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
                req = schemas.AddMemberRequest(**payload)
                res = add_member(req)
            elif op == schemas.OperationType.REMOVE_MEMBER:
                req = schemas.RemoveMemberRequest(**payload)
                res = remove_member(req)
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


def validate_group_in_provider(
    group_id: str, provider: GroupProvider, op_status: object | None = None
) -> bool:
    """Check if group exists and is accessible in provider.

    This function used to live in `orchestration.py`. It is a small,
    provider-aware helper that verifies accessibility by attempting a
    read operation (calls `get_group_members`). Moving it into the
    service boundary keeps orchestration focused on flow control while
    keeping caller-facing helpers discoverable on `service`.

    Returns True when the provider indicates success, False otherwise.
    """
    try:
        result = provider.get_group_members(group_id)
        # If OperationResult-like, check the status attribute
        if hasattr(result, "status"):
            status_enum = op_status if op_status is not None else OperationStatus
            return result.status == getattr(status_enum, "SUCCESS", "SUCCESS")
        # otherwise assume success when no exception raised
        return True
    except Exception as e:
        logger.warning(
            "group_validation_failed",
            group_id=group_id,
            provider=provider.__class__.__name__,
            error=str(e),
        )
        return False
