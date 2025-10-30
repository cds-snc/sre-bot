"""Provider-agnostic group mapping and orchestration helpers.

This module contains lightweight helpers used by the orchestration layer.
All heavy imports (provider registry, mapping helpers) are performed lazily
inside functions to avoid import-time failures during incremental rollout.
"""

from uuid import uuid4
from typing import Dict, List, TYPE_CHECKING, cast
from core.logging import get_module_logger
from modules.groups import (
    reconciliation_integration as ri,
    orchestration_responses as orr,
)
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
from modules.groups.schemas import NormalizedGroup
from modules.groups.mappings import (
    map_primary_to_secondary_group,
    normalize_member_for_provider,
)

if TYPE_CHECKING:  # avoid runtime import cycles for typing
    from modules.groups.types import OrchestrationResponseTypedDict, OperationResultLike

logger = get_module_logger()


def get_enabled_secondary_providers() -> Dict[str, GroupProvider]:
    """Return all active providers EXCEPT primary.

    Returns:
        Dict mapping provider name → provider instance for non-primary providers

    Example:
        If primary is 'google', returns {'aws': AwsProvider, 'azure': AzureProvider}
    """
    primary_name = get_primary_provider_name()
    all_providers = get_active_providers()

    return {
        name: provider
        for name, provider in all_providers.items()
        if name != primary_name
    }


def validate_group_in_provider(group_id: str, provider: GroupProvider) -> bool:
    """Check if group exists and is accessible in provider.

    Attempts a read operation (get_group_members) to verify group accessibility.

    Args:
        group_id: Group ID to validate
        provider: GroupProvider instance

    Returns:
        True if group exists and is accessible, False otherwise
    """
    try:
        result = provider.get_group_members(group_id)
        # If OperationResult-like, check status attribute
        if hasattr(result, "status"):

            return result.status == OperationStatus.SUCCESS
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


def _unwrap_opresult_data(op):
    """Return the inner data payload from an OperationResult-like object.

    Providers wrap returned payloads as OperationResult.data with a single
    key (e.g., {'result': {...}} or {'members': [...]}) depending on the
    operation. This helper returns the underlying value when possible.
    """
    try:
        data = getattr(op, "data", None)
        if not isinstance(data, dict) or len(data) == 0:
            return data
        # return the first value - convention is a single data_key
        return next(iter(data.values()))
    except Exception:
        return None


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

    Returns a dict mapping provider name -> OperationResult.
    """
    results: Dict[str, OperationResult] = {}
    secondaries = get_active_providers()
    try:
        primary_name = get_primary_provider_name()
    except Exception:
        primary_name = None

    for name, prov in secondaries.items():
        if name == primary_name:
            continue
        try:
            sec_group = map_primary_to_secondary_group(primary_group_id, name)
            sec_member = normalize_member_for_provider(member_email, provider_type=name)

            sec_op = _call_provider_method(
                prov, op_name, sec_group, sec_member, correlation_id
            )
            results[name] = sec_op

            if getattr(sec_op, "status", None) != OperationStatus.SUCCESS:
                err_msg = getattr(sec_op, "message", "")
                try:
                    ri.enqueue_failed_propagation(
                        correlation_id=correlation_id,
                        provider=name,
                        group_id=sec_group,
                        member_email=member_email,
                        action=action,
                        error_message=err_msg,
                    )
                except Exception:
                    logger.exception("enqueue_failed_propagation_failed", provider=name)

        except Exception as e:
            results[name] = OperationResult.transient_error(str(e))
            logger.error(
                "propagation_mapping_or_call_failed",
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
    member_obj = normalize_member_for_provider(
        member_email, provider_type=provider_hint or ""
    )

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
            member_obj,
            correlation_id,
        )
    except Exception as e:
        logger.error(
            "primary_op_exception",
            correlation_id=correlation_id,
            error=str(e),
            exc_info=True,
        )
        primary_result = OperationResult.transient_error(str(e))

    # If primary failed, do not propagate
    if getattr(primary_result, "status", None) != OperationStatus.SUCCESS:
        logger.warning(
            "orchestration_primary_failed",
            correlation_id=correlation_id,
            primary_status=getattr(primary_result, "status", None),
        )
        return cast(
            "OrchestrationResponseTypedDict",
            orr.format_orchestration_response(
                primary_result,
                {},
                False,
                correlation_id,
                action=action,
                group_id=primary_group_id,
                member_email=member_email,
            ),
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

    # cast propagation results to OperationResultLike mapping for formatter
    propagation_like = cast(Dict[str, "OperationResultLike"], propagation_results)

    return cast(
        "OrchestrationResponseTypedDict",
        orr.format_orchestration_response(
            primary_result,
            propagation_like,
            has_partial,
            correlation_id,
            action=action,
            group_id=primary_group_id,
            member_email=member_email,
        ),
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


def get_groups_for_user(
    user_email: str,
    provider_type: str | None = None,
) -> List[NormalizedGroup]:
    """Get groups for a user from the primary provider.

    Args:
        user_email: Email of the user to look up.
        provider_type: Optional provider type hint.
    """
    op = _perform_read_operation(
        op_name="get_groups_for_user",
        action="get_groups_for_user",
        user_key=user_email,
        provider_name=provider_type,
    )

    # On failure, return an empty list rather than an OperationResult
    if getattr(op, "status", None) != OperationStatus.SUCCESS:
        return []
    if op.data is None or not isinstance(op.data, dict):
        return []
    return op.data.get("groups", [])

