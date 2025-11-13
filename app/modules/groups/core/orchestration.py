"""Provider-agnostic group mapping and orchestration helpers.

This module contains lightweight helpers used by the orchestration layer.
All heavy imports (provider registry, mapping helpers) are performed lazily
inside functions to avoid import-time failures during incremental rollout.
"""

from datetime import datetime, timezone
from uuid import uuid4
from typing import Any, Dict, List, TYPE_CHECKING, Optional, cast, Mapping
from core.logging import get_module_logger
from modules.groups.reconciliation import integration as ri
from modules.groups.providers import (
    get_active_providers,
    get_primary_provider,
    get_primary_provider_name,
)
from modules.groups.providers.base import (
    OperationStatus,
    OperationResult,
    GroupProvider,
)
from modules.groups.domain.models import NormalizedGroup

if TYPE_CHECKING:  # avoid runtime import cycles for typing
    from modules.groups.domain.types import (
        OrchestrationResponseTypedDict,
        OperationResultLike,
    )

logger = get_module_logger()


def _call_provider_method(
    provider: GroupProvider,
    method_name: str,
    *p_args,
    correlation_id: str | None = None,
    **p_kwargs,
) -> OperationResult:
    """Call a provider method safely and return an OperationResult.

    Handles missing methods and exceptions, returning a transient error
    OperationResult on failure.
    """
    method = getattr(provider, method_name, None)
    if not callable(method):
        logger.error(
            "provider_missing_method",
            correlation_id=correlation_id,
            provider=provider.__class__.__name__,
            method=method_name,
        )
        return OperationResult.transient_error(
            f"Provider {provider.__class__.__name__} missing method {method_name}"
        )
    try:
        return method(*p_args, **p_kwargs)
    except Exception as e:
        logger.warning(
            "provider_method_exception",
            correlation_id=correlation_id,
            provider=provider.__class__.__name__,
            method=method_name,
            error=str(e),
        )
        return OperationResult.transient_error(str(e))


def _propagate_to_secondaries(
    primary_group_id: str,
    member_email: str,
    op_name: str,
    action: str,
    correlation_id: str,
) -> Dict[str, "OperationResultLike"]:
    """Propagate an operation to all secondary providers.

    Passes the full group email (from primary provider) directly to secondary providers.
    Each secondary provider is responsible for decomposing the email and resolving it
    to its own identifier format.
    The secondary provider is identified by the prefix of the email passed.

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
    secondaries = get_active_providers()
    primary_name = get_primary_provider_name()

    for name, prov in secondaries.items():
        if name == primary_name:
            continue
        try:
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

            if getattr(sec_op, "status", None) != OperationStatus.SUCCESS:
                err_msg = getattr(sec_op, "message", "")
                try:
                    ri.enqueue_failed_propagation(
                        correlation_id=correlation_id,
                        provider=name,
                        group_email=primary_group_id,
                        member_email=member_email,
                        action=action,
                        error_message=err_msg,
                    )
                except Exception:
                    logger.exception("enqueue_failed_propagation_failed", provider=name)

        except Exception as e:
            results[name] = OperationResult.transient_error(str(e))
            logger.error(
                "propagation_failed",
                correlation_id=correlation_id,
                provider=name,
                error=str(e),
            )

    return results


def _perform_read_operation(
    op_name: str,
    action: str,
    *p_args,
    **p_kwargs,
) -> OperationResult:
    """Call a read-only provider method safely and return an OperationResult.

    Handles missing methods and exceptions, returning a transient error
    OperationResult on failure.
    """

    primary = get_primary_provider()

    logger.info(
        "perform_read_op_start",
        primary=primary.__class__.__name__,
        op_name=op_name,
        action=action,
    )

    try:
        result = _call_provider_method(primary, op_name, *p_args, **p_kwargs)
    except Exception as e:
        logger.error(
            "primary_read_op_exception",
            error=str(e),
            exc_info=True,
        )
        result = OperationResult.transient_error(str(e))
    if getattr(result, "status", None) != OperationStatus.SUCCESS:
        logger.warning(
            "perform_read_op_failed",
            primary_status=getattr(result, "status", None),
        )
    return result


def _format_orchestration_response(
    primary: "OperationResultLike",
    propagation: Dict[str, "OperationResultLike"],
    partial_failures: bool,
    correlation_id: str,
    action: str = "operation",
    group_id: Optional[str] = None,
    member_email: Optional[str] = None,
) -> "OrchestrationResponseTypedDict":
    """Format orchestration response with primary and propagation results.

    `primary` is expected to be an OperationResult-like object. We avoid
    importing OperationResult at module import time to keep this module
    lightweight.
    """
    try:
        overall_success = getattr(primary, "status").name == "SUCCESS"
    except Exception:
        overall_success = False

    primary_data = {
        "status": (
            getattr(primary, "status").name
            if hasattr(primary, "status") and getattr(primary, "status") is not None
            else None
        ),
        "message": getattr(primary, "message", ""),
    }
    if getattr(primary, "data", None):
        primary_data["data"] = getattr(primary, "data")
    if getattr(primary, "error_code", None):
        primary_data["error_code"] = getattr(primary, "error_code")
    if getattr(primary, "retry_after", None):
        primary_data["retry_after"] = getattr(primary, "retry_after")

    propagation_data: Dict[str, Any] = {}
    for provider_name, result in (propagation or {}).items():
        propagation_data[provider_name] = {
            "status": (
                getattr(result, "status").name
                if hasattr(result, "status") and getattr(result, "status") is not None
                else None
            ),
            "message": getattr(result, "message", ""),
        }
        if getattr(result, "data", None):
            propagation_data[provider_name]["data"] = getattr(result, "data")
        if getattr(result, "error_code", None):
            propagation_data[provider_name]["error_code"] = getattr(
                result, "error_code"
            )
        if getattr(result, "retry_after", None):
            propagation_data[provider_name]["retry_after"] = getattr(
                result, "retry_after"
            )

    response = {
        "success": overall_success,
        "correlation_id": correlation_id,
        "action": action,
        "primary": primary_data,
        "propagation": propagation_data,
        "partial_failures": partial_failures,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    if group_id:
        response["group_id"] = group_id
    if member_email:
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
        Orchestration response dict from orchestration_responses.format_orchestration_response.

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

    try:
        primary_result = _call_provider_method(
            primary,
            op_name,
            primary_group_id,
            member_email,
            correlation_id=correlation_id,
        )
    except Exception as e:
        logger.error(
            "primary_op_exception",
            correlation_id=correlation_id,
            error=str(e),
            exc_info=True,
        )
        primary_result = OperationResult.transient_error(str(e))

    # If primary failed, do not propagate.
    if getattr(primary_result, "status", None) != OperationStatus.SUCCESS:
        logger.warning(
            "orchestration_primary_failed",
            correlation_id=correlation_id,
            primary_status=getattr(primary_result, "status", None),
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
        getattr(r, "status", None) != OperationStatus.SUCCESS
        for r in propagation_results.values()
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

    Returns an orchestration response dict as produced by
    `orchestration_responses.format_orchestration_response`.
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

    Returns an orchestration response dict.
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


def list_groups_for_user(
    user_email: str,
    provider_type: str | None = None,
) -> List[NormalizedGroup]:
    """Get groups for a user from the primary provider.

    Args:
        user_email: Email of the user to look up.
        provider_type: Optional provider type hint.
    """
    op = _perform_read_operation(
        op_name="list_groups_for_user",
        action="list_groups_for_user",
        user_key=user_email,
        provider_name=provider_type,
    )

    # On failure, return an empty list rather than an OperationResult
    if getattr(op, "status", None) != OperationStatus.SUCCESS:
        return []
    if op.data is None or not isinstance(op.data, dict):
        return []
    return op.data.get("groups", [])


def list_groups_managed_by_user(
    user_email: str,
    provider_type: str | None = None,
) -> List[NormalizedGroup]:
    """Get groups manageable by a user from the primary provider.

    Args:
        user_email: Email of the user to look up.
        provider_type: Optional provider type hint.
    """
    op = _perform_read_operation(
        op_name="list_groups_managed_by_user",
        action="list_groups_managed_by_user",
        user_key=user_email,
        provider_name=provider_type,
    )

    # On failure, return an empty list rather than an OperationResult
    if getattr(op, "status", None) != OperationStatus.SUCCESS:
        return []
    if op.data is None or not isinstance(op.data, dict):
        return []
    return op.data.get("groups", [])
