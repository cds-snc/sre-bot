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

from datetime import datetime
from typing import Any, List
from core.logging import get_module_logger
from modules.groups import orchestration
from modules.groups import event_system
from modules.groups import schemas

logger = get_module_logger()


def _parse_timestamp(ts: str | None) -> datetime:
    """Parse ISO timestamp returned by orchestration into a datetime.

    Orchestration uses timezone-aware ISO strings (with 'Z'). `fromisoformat`
    does not accept literal 'Z', so normalize it to '+00:00' when present.
    """
    if not ts:
        return datetime.utcnow()
    try:
        if ts.endswith("Z"):
            ts = ts[:-1] + "+00:00"
        return datetime.fromisoformat(ts)
    except Exception:
        logger.warning("failed_to_parse_timestamp", timestamp=ts)
        return datetime.utcnow()


def add_member(request: schemas.AddMemberRequest) -> schemas.ActionResponse:
    """Add a member to a group using orchestration.

    Returns an `ActionResponse` Pydantic model summarizing the result. This
    function schedules a background event `group.member.add_requested` with
    the orchestration response plus the original request payload.
    """
    orch = orchestration.add_member_to_group(
        primary_group_id=request.group_id,
        member_email=request.member_email,
        justification=request.justification or "",
        provider_hint=(request.provider.value if request.provider else None),
    )

    # Fire-and-forget event for downstream handlers (audit, notifications)
    try:
        event_system.dispatch_background(
            "group.member.add_requested",
            (
                {"orchestration": orch, "request": request.model_dump()}
                if hasattr(request, "model_dump")
                else {"orchestration": orch, "request": request.dict()}
            ),
        )
    except Exception:  # pragma: no cover - defensive
        logger.exception("failed_to_schedule_add_member_event")

    ts = _parse_timestamp(orch.get("timestamp"))

    return schemas.ActionResponse(
        success=bool(orch.get("success", False)),
        action=schemas.OperationType.ADD_MEMBER,
        group_id=orch.get("group_id"),
        member_email=orch.get("member_email"),
        provider=request.provider,
        details={"orchestration": orch},
        timestamp=ts,
    )


def remove_member(request: schemas.RemoveMemberRequest) -> schemas.ActionResponse:
    """Remove a member from a group using orchestration.

    Schedules `group.member.remove_requested` as a background event and returns
    an `ActionResponse` summarizing the orchestration outcome.
    """
    orch = orchestration.remove_member_from_group(
        primary_group_id=request.group_id,
        member_email=request.member_email,
        justification=request.justification or "",
        provider_hint=(request.provider.value if request.provider else None),
    )

    try:
        event_system.dispatch_background(
            "group.member.remove_requested",
            (
                {"orchestration": orch, "request": request.model_dump()}
                if hasattr(request, "model_dump")
                else {"orchestration": orch, "request": request.dict()}
            ),
        )
    except Exception:  # pragma: no cover - defensive
        logger.exception("failed_to_schedule_remove_member_event")

    ts = _parse_timestamp(orch.get("timestamp"))

    return schemas.ActionResponse(
        success=bool(orch.get("success", False)),
        action=schemas.OperationType.REMOVE_MEMBER,
        group_id=orch.get("group_id"),
        member_email=orch.get("member_email"),
        provider=request.provider,
        details={"orchestration": orch},
        timestamp=ts,
    )


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
                    timestamp=datetime.utcnow(),
                )
        except Exception as e:
            logger.exception("bulk_operation_item_failed", operation=op, error=str(e))
            res = schemas.ActionResponse(
                success=False,
                action=op,
                details={"error": str(e)},
                timestamp=datetime.utcnow(),
            )

        results.append(res)

    # Build simple summary
    summary = {
        "success": sum(1 for r in results if r.success),
        "failed": sum(1 for r in results if not r.success),
    }

    return schemas.BulkOperationResponse(results=results, summary=summary)
