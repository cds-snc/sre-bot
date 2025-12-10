"""Provider-agnostic group mapping and orchestration helpers.

This module contains lightweight helpers used by the orchestration layer.
All heavy imports (provider registry, mapping helpers) are performed lazily
inside functions to avoid import-time failures during incremental rollout.
"""

from datetime import datetime, timezone
from uuid import uuid4
from typing import Any, Dict, List, TYPE_CHECKING, Optional, cast
from infrastructure.observability import get_module_logger
from modules.groups.reconciliation import integration as ri
from modules.groups.providers import (
    get_primary_provider,
    get_secondary_providers,
)
from modules.groups.providers.base import (
    OperationStatus,
    OperationResult,
    GroupProvider,
)
from modules.groups.domain.models import NormalizedGroup

if TYPE_CHECKING:  # avoid runtime import cycles for typing
    from modules.groups.domain.types import OrchestrationResponseTypedDict

logger = get_module_logger()


# TODO: clarify if providers shouldn't be responsible to raise an error instead.
def _call_provider_method(
    provider: GroupProvider,
    method_name: str,
    *p_args,
    correlation_id: str | None = None,
    **p_kwargs,
) -> OperationResult:
    """Call a provider method and return an OperationResult.

    Provider methods are defined by GroupProvider protocol. If a provider
    doesn't implement a required method, it's a programming error that should
    fail fast, not be caught.

    Args:
        provider: GroupProvider instance
        method_name: Name of method to call on provider
        *p_args: Positional arguments to pass to method
        correlation_id: Optional correlation ID for logging
        **p_kwargs: Keyword arguments to pass to method

    Returns:
        OperationResult from the provider method call

    Raises:
        AttributeError: If provider is missing the required method (programming error)

    Transient errors returned:
        - If method returns non-OperationResult type (type contract violation)
        - If method raises any exception during execution
    """
    try:
        method = getattr(provider, method_name)
        result = method(*p_args, **p_kwargs)

        # Validate return type - must be OperationResult
        if not isinstance(result, OperationResult):
            logger.error(
                "provider_invalid_return_type",
                correlation_id=correlation_id,
                provider=provider.__class__.__name__,
                method=method_name,
                expected_type="OperationResult",
                actual_type=type(result).__name__,
            )
            return OperationResult.transient_error(
                f"Provider {provider.__class__.__name__}.{method_name}() "
                f"returned {type(result).__name__}, expected OperationResult"
            )

        return result

    except AttributeError as e:
        # Provider missing required method - this is a programming error, fail fast
        logger.error(
            "provider_missing_method",
            correlation_id=correlation_id,
            provider=provider.__class__.__name__,
            method=method_name,
            error=str(e),
        )
        raise  # Re-raise to fail fast

    except Exception as e:  # pylint: disable=broad-except
        # Provider method raised an exception during execution
        logger.warning(
            "provider_method_failed",
            correlation_id=correlation_id,
            provider=provider.__class__.__name__,
            method=method_name,
            error=str(e),
            exc_info=True,
        )
        return OperationResult.transient_error(str(e))


# TODO: Tighten propagation to only specific secondaries based on provider type
def _propagate_to_secondaries(
    primary_group_id: str,
    member_email: str,
    op_name: str,
    action: str,
    correlation_id: str,
) -> Dict[str, OperationResult]:
    """Propagate an operation to all secondary providers.

    Passes the full group email (from primary provider) directly to secondary providers.
    Each secondary provider is responsible for decomposing the email and resolving it
    to its own identifier format.

    Args:
        primary_group_id: Full group email from primary provider (e.g., "aws-admins@example.com")
        member_email: Member email address
        op_name: Provider method name (add_member, remove_member)
        action: Action label for logging/queuing
        correlation_id: Correlation ID for tracing

    Returns:
        Dict mapping provider name -> OperationResult.
    """
    results: Dict[str, OperationResult] = {}
    secondaries = get_secondary_providers()

    for name, prov in secondaries.items():
        # Pass full group email directly to secondary provider
        # Secondary provider is responsible for email decomposition and identifier resolution
        sec_op = _call_provider_method(
            prov,
            op_name,
            primary_group_id,
            member_email,
            correlation_id=correlation_id,
        )
        results[name] = sec_op

        # Check if operation succeeded using explicit attribute access
        # _call_provider_method guarantees OperationResult type
        if sec_op.status != OperationStatus.SUCCESS:
            try:
                ri.enqueue_failed_propagation(
                    correlation_id=correlation_id,
                    provider=name,
                    group_email=primary_group_id,
                    member_email=member_email,
                    action=action,
                    error_message=sec_op.message,
                )
            except Exception:
                logger.exception(
                    "enqueue_failed_propagation_failed",
                    provider=name,
                    correlation_id=correlation_id,
                )
    return results


def _perform_read_operation(
    op_name: str,
    action: str,
    *p_args,
    **p_kwargs,
) -> OperationResult:
    """Call a read-only provider method and return an OperationResult.

    Delegates exception handling to _call_provider_method(), which guarantees
    a valid OperationResult on return (or raises AttributeError for missing methods).
    """

    primary = get_primary_provider()

    logger.info(
        "perform_read_op_start",
        primary=primary.__class__.__name__,
        op_name=op_name,
        action=action,
    )

    result = _call_provider_method(primary, op_name, *p_args, **p_kwargs)

    if result.status != OperationStatus.SUCCESS:
        logger.warning(
            "perform_read_op_failed",
            primary_status=result.status,
        )
    return result


def _format_orchestration_response(
    primary: OperationResult,
    propagation: Dict[str, OperationResult],
    partial_failures: bool,
    correlation_id: str,
    action: str = "operation",
    group_id: Optional[str] = None,
    member_email: Optional[str] = None,
) -> "OrchestrationResponseTypedDict":
    """Format orchestration response from concrete OperationResult instances.

    This narrowed version assumes all result objects are the standard
    OperationResult produced by providers or orchestration helpers.
    """
    overall_success = primary.status == OperationStatus.SUCCESS

    # Build primary result data (include optional fields only if present)
    primary_data: Dict[str, Any] = {
        "status": primary.status.name,
        "message": primary.message,
    }
    if primary.data is not None:
        primary_data["data"] = primary.data
    if primary.error_code is not None:
        primary_data["error_code"] = primary.error_code
    if primary.retry_after is not None:
        primary_data["retry_after"] = primary.retry_after

    # Build propagation results
    propagation_data: Dict[str, Any] = {}
    for provider_name, result in propagation.items():
        item: Dict[str, Any] = {
            "status": result.status.name,
            "message": result.message,
        }
        if result.data is not None:
            item["data"] = result.data
        if result.error_code is not None:
            item["error_code"] = result.error_code
        if result.retry_after is not None:
            item["retry_after"] = result.retry_after
        propagation_data[provider_name] = item

    response: Dict[str, Any] = {
        "success": overall_success,
        "correlation_id": correlation_id,
        "action": action,
        "primary": primary_data,
        "propagation": propagation_data,
        "partial_failures": partial_failures,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if group_id is not None:
        response["group_id"] = group_id
    if member_email is not None:
        response["member_email"] = member_email
    return cast("OrchestrationResponseTypedDict", response)


def _orchestrate_write_operation(
    primary_group_id: str,
    member_email: str,
    justification: str,
    op_name: str,
    action: str,
    provider_hint: str | None = None,
    correlation_id: str | None = None,
) -> "OrchestrationResponseTypedDict":
    """Generic orchestration: run primary op then propagate to secondaries.

    Args:
        primary_group_id: Group id on the primary provider.
        member_email: Member email to operate on.
        justification: Justification text for the operation.
        op_name: Provider method name to call (e.g. "add_member", "remove_member").
        action: Action label for responses/enqueue (e.g. "add_member").
        provider_hint: Optional hint for primary normalization.
        correlation_id: Optional correlation id; generated if omitted.

    Returns:
        Orchestration response dict from _format_orchestration_response.

    TODO: Justification handling/enforcement to audit logs.
        Providers do not handle the justification, they provide wrappers around the API calls only.
    """
    if not correlation_id:
        correlation_id = str(uuid4())

    primary = get_primary_provider()

    logger.info(
        "orchestration_member_operation_start",
        correlation_id=correlation_id,
        primary=primary.__class__.__name__,
        group=primary_group_id,
        action=action,
    )

    primary_result = _call_provider_method(
        primary,
        op_name,
        primary_group_id,
        member_email,
        correlation_id=correlation_id,
    )

    # If primary failed, do not propagate.
    if primary_result.status != OperationStatus.SUCCESS:
        logger.warning(
            "orchestration_primary_failed",
            correlation_id=correlation_id,
            primary_status=primary_result.status,
        )
        return _format_orchestration_response(
            primary=primary_result,
            propagation={},
            partial_failures=False,
            correlation_id=correlation_id,
            action=action,
            group_id=primary_group_id,
            member_email=member_email,
        )

    # TODO: record justification for audit
    logger.warning(
        "justification_recording_not_implemented", justification=justification
    )

    # Primary succeeded; propagate to secondaries using helper
    propagation_results = _propagate_to_secondaries(
        primary_group_id, member_email, op_name, action, correlation_id
    )

    has_partial = any(
        r.status != OperationStatus.SUCCESS for r in propagation_results.values()
    )

    # Return raw results; formatting (to dicts/timestamps) lives on the
    # service boundary so controllers and consumers receive stable
    # serializable payloads from the service layer.
    return _format_orchestration_response(
        primary=primary_result,
        propagation=propagation_results,
        partial_failures=has_partial,
        correlation_id=correlation_id,
        action=action,
        group_id=primary_group_id,
        member_email=member_email,
    )


def add_member_to_group(
    primary_group_id: str,
    member_email: str,
    justification: str,
    provider_hint: str | None = None,
    correlation_id: str | None = None,
) -> "OrchestrationResponseTypedDict":
    """Orchestrate adding a member: primary-first then propagate to secondaries.

    Returns an orchestration response dict produced internally.
    """
    return _orchestrate_write_operation(
        primary_group_id=primary_group_id,
        member_email=member_email,
        justification=justification,
        op_name="add_member",
        action="add_member",
        provider_hint=provider_hint,
        correlation_id=correlation_id,
    )


def remove_member_from_group(
    primary_group_id: str,
    member_email: str,
    justification: str,
    provider_hint: str | None = None,
    correlation_id: str | None = None,
) -> "OrchestrationResponseTypedDict":
    """Orchestrate removing a member: primary-first then propagate to secondaries.

    Returns an orchestration response dict produced internally.
    """
    return _orchestrate_write_operation(
        primary_group_id=primary_group_id,
        member_email=member_email,
        justification=justification,
        op_name="remove_member",
        action="remove_member",
        provider_hint=provider_hint,
        correlation_id=correlation_id,
    )


def list_groups_simple(
    provider_name: Optional[str] = None,
) -> List[NormalizedGroup]:
    """List all groups (no members, minimal data).

    Args:
        provider_name: Optional provider filter

    Returns:
        List of normalized groups (no members)
    """
    op = _perform_read_operation(
        op_name="list_groups",
        action="list_groups",
        provider_name=provider_name,
    )
    if op.status != OperationStatus.SUCCESS:
        return []
    if op.data is None or not isinstance(op.data, dict):
        return []
    return cast(List[NormalizedGroup], op.data.get("groups", []))


def list_groups_with_members_and_filters(
    provider_name: Optional[str] = None,
    member_email_filter: Optional[str] = None,
    member_role_filters: Optional[List[str]] = None,
    include_users_details: bool = False,
    exclude_empty_groups: bool = True,
) -> List[NormalizedGroup]:
    """List groups with members, optionally filtered.

    Args:
        user_email: Email of user making request
        provider_hint: Optional provider filter
        member_email: Filter groups by this member's email
        member_role_filters: Filter groups by member role(s)
        include_users_details: Whether to enrich with full user details
        include_empty_groups: Whether to include groups with no members

    Returns:
        List of normalized groups with members assembled and filtered
    """
    op = _perform_read_operation(
        op_name="list_groups_with_members",
        action="list_groups_with_members",
        member_email_filter=member_email_filter,
        member_role_filters=member_role_filters,
        include_users_details=include_users_details,
        provider_name=provider_name,
        exclude_empty_groups=exclude_empty_groups,
    )
    if op.status != OperationStatus.SUCCESS:
        return []
    if op.data is None or not isinstance(op.data, dict):
        return []
    return cast(List[NormalizedGroup], op.data.get("groups", []))
