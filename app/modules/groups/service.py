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
from modules.groups import validation
from modules.groups import mappings
from modules.groups import providers as _providers
from modules.groups.providers.base import OperationStatus, GroupProvider

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
    "map_provider_group_id",
    "parse_primary_group_name",
    "primary_group_to_canonical",
    "normalize_member_for_provider",
    "map_normalized_groups_to_providers",
    "filter_groups_for_user_roles",
    "map_primary_to_secondary_group",
]


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
    # Semantic validation: move input validation responsibility to the service
    provider_type = request.provider.value if request.provider else None
    if provider_type and not validation.validate_provider_type(provider_type):
        raise ValueError(f"invalid provider: {provider_type}")

    if not validation.validate_group_id(request.group_id, provider_type or ""):
        raise ValueError(
            f"invalid group_id for provider {provider_type}: {request.group_id}"
        )

    if request.justification and not validation.validate_justification(
        request.justification
    ):
        raise ValueError("justification too short")

    # If caller supplied a non-primary provider group id, map it to the
    # primary provider format before calling orchestration. This keeps
    # orchestration focused on provider coordination and reduces mapping
    # responsibilities there.
    primary_group_id = request.group_id
    try:
        primary_name = _providers.get_primary_provider_name()
    except Exception:
        primary_name = None

    if provider_type and primary_name and provider_type != primary_name:
        try:
            primary_group_id = mappings.map_provider_group_id(
                from_provider=provider_type,
                from_group_id=request.group_id,
                to_provider=primary_name,
            )
        except Exception as e:
            raise ValueError(f"failed_to_map_group_id: {e}")

    orch = orchestration.add_member_to_group(
        primary_group_id=primary_group_id,
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
    # Semantic validation performed at service boundary
    provider_type = request.provider.value if request.provider else None
    if provider_type and not validation.validate_provider_type(provider_type):
        raise ValueError(f"invalid provider: {provider_type}")

    if not validation.validate_group_id(request.group_id, provider_type or ""):
        raise ValueError(
            f"invalid group_id for provider {provider_type}: {request.group_id}"
        )

    if request.justification and not validation.validate_justification(
        request.justification
    ):
        raise ValueError("justification too short")

    primary_group_id = request.group_id
    try:
        primary_name = _providers.get_primary_provider_name()
    except Exception:
        primary_name = None

    if provider_type and primary_name and provider_type != primary_name:
        try:
            primary_group_id = mappings.map_provider_group_id(
                from_provider=provider_type,
                from_group_id=request.group_id,
                to_provider=primary_name,
            )
        except Exception as e:
            raise ValueError(f"failed_to_map_group_id: {e}")

    orch = orchestration.remove_member_from_group(
        primary_group_id=primary_group_id,
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


def primary_group_to_canonical(
    primary_group_name: str, prefixes: list | None = None
) -> str:
    """Return canonical group name for a primary provider identifier.

    Use this service wrapper instead of importing the mapping helper directly.
    The implementation lives in `modules.groups.mappings`; this wrapper is the
    supported public boundary so mapping internals can change without
    impacting callers.
    """
    return mappings.primary_group_to_canonical(primary_group_name, prefixes)


def parse_primary_group_name(
    primary_group_name: str, *, provider_registry: dict | None = None
) -> dict:
    """Parse a primary provider group identifier into prefix + canonical.

    Public wrapper around the mapping implementation. Callers should use this
    function rather than `mappings.parse_primary_group_name` so the service
    boundary remains stable.
    """
    # Delegate to mappings implementation. Keep signature compatible with
    # existing callers (accept `provider_registry` for deterministic tests).
    return mappings.parse_primary_group_name(
        primary_group_name, provider_registry=provider_registry
    )


def map_provider_group_id(
    from_provider: str,
    from_group_id: str,
    to_provider: str,
    *,
    provider_registry: dict | None = None,
) -> str:
    """Map a group id from one provider to another.

    Public wrapper. Use this function as the canonical mapping API; the heavy
    implementation lives in `modules.groups.mappings` and may change over
    time. Keeping callers pointed at the service reduces coupling.
    """
    return mappings.map_provider_group_id(
        from_provider=from_provider,
        from_group_id=from_group_id,
        to_provider=to_provider,
        provider_registry=provider_registry,
    )


def map_primary_to_secondary_group(
    primary_group_id: str, secondary_provider: str
) -> str:
    """Map a primary provider group id to a secondary provider's id.

    Public wrapper around `mappings.map_primary_to_secondary_group` so
    callers can rely on the service boundary rather than importing mapping
    helpers directly from `mappings`.
    """
    return mappings.map_primary_to_secondary_group(primary_group_id, secondary_provider)


def normalize_member_for_provider(member_email: str, provider_type: str):
    """Normalize a member identifier for a specific provider.

    Public wrapper around the mapping implementation. Callers should import
    and use this service function so provider-specific normalization logic is
    encapsulated and can evolve without changing call sites.
    """
    return mappings.normalize_member_for_provider(member_email, provider_type)


def map_normalized_groups_to_providers(
    groups, *, associate: bool = False, provider_registry: dict | None = None
) -> dict:
    """Group a list of normalized groups by provider (optionally associate by prefix).

    Public wrapper that delegates to the mapping implementation. Use this
    wrapper as the maintained public API for grouping behavior.
    """
    return mappings.map_normalized_groups_to_providers(
        groups, associate=associate, provider_registry=provider_registry
    )


def filter_groups_for_user_roles(groups, user_email: str, user_roles: list):
    """Filter a groups map to only include groups the user holds the given roles in.

    Public wrapper. Callers should use this service function to keep
    role-filtering logic behind the service boundary instead of relying on
    internal mapping helpers.
    """
    return mappings.filter_groups_for_user_roles(groups, user_email, user_roles)


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
