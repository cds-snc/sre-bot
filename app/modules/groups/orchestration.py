"""Provider-agnostic group mapping and orchestration helpers.

This module contains lightweight helpers used by the orchestration layer.
All heavy imports (provider registry, mapping helpers) are performed lazily
inside functions to avoid import-time failures during incremental rollout.
"""

from uuid import uuid4
from typing import Dict
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
from modules.groups.group_name_mapping import map_provider_group_id
from modules.groups.schemas import NormalizedMember


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


def map_secondary_to_primary_group(
    secondary_provider: str, secondary_group_id: str
) -> str:
    """Map secondary provider's group ID to primary provider's equivalent.

    Uses `group_name_mapping.py` helpers to translate between provider-specific
    group ID formats.

    Args:
        secondary_provider: Name of secondary provider (e.g., 'aws', 'google')
        secondary_group_id: Group ID in secondary provider format

    Returns:
        Group ID in primary provider format

    Raises:
        ValueError: If mapping cannot be performed
    """
    primary_provider_name = get_primary_provider_name()

    try:
        primary_group_id = map_provider_group_id(
            from_provider=secondary_provider,
            from_group_id=secondary_group_id,
            to_provider=primary_provider_name,
        )
        logger.info(
            "group_mapping_secondary_to_primary",
            from_provider=secondary_provider,
            from_id=secondary_group_id,
            to_id=primary_group_id,
        )
        return primary_group_id
    except Exception as e:
        logger.error(
            "group_mapping_failed",
            from_provider=secondary_provider,
            from_id=secondary_group_id,
            error=str(e),
        )
        raise ValueError(
            f"Cannot map {secondary_provider} group '{secondary_group_id}' to {primary_provider_name}: {e}"
        ) from e


def map_primary_to_secondary_group(
    primary_group_id: str, secondary_provider: str
) -> str:
    """Map primary provider's group ID to secondary provider's equivalent.

    Reverse mapping for propagation: used when executing operations on secondary providers.

    Args:
        primary_group_id: Group ID in primary provider format
        secondary_provider: Name of secondary provider to map to

    Returns:
        Group ID in secondary provider format

    Raises:
        ValueError: If mapping cannot be performed
    """
    primary_provider_name = get_primary_provider_name()

    try:
        secondary_group_id = map_provider_group_id(
            from_provider=primary_provider_name,
            from_group_id=primary_group_id,
            to_provider=secondary_provider,
        )
        logger.info(
            "group_mapping_primary_to_secondary",
            from_id=primary_group_id,
            to_provider=secondary_provider,
            to_id=secondary_group_id,
        )
        return secondary_group_id
    except Exception as e:
        logger.error(
            "group_mapping_failed",
            from_id=primary_group_id,
            to_provider=secondary_provider,
            error=str(e),
        )
        raise ValueError(
            f"Cannot map {primary_provider_name} group '{primary_group_id}' to {secondary_provider}: {e}"
        ) from e


def normalize_member_for_provider(
    member_email: str, provider_type: str
) -> NormalizedMember:
    """Convert email address to provider-specific NormalizedMember.

    Each provider may have different member identifier requirements.
    This function normalizes the input to what the provider expects.

    Args:
        member_email: Email address of member
        provider_type: Name of provider

    Returns:
        NormalizedMember instance ready for provider API call

    Raises:
        ValueError: If email is invalid or provider unknown
    """
    if not member_email or "@" not in member_email:
        raise ValueError(f"Invalid email: {member_email}")

    # All providers currently use email-only normalization
    # Future: extend this to provider-specific logic as needed
    return NormalizedMember(
        email=member_email,
        id=None,
        role=None,
        provider_member_id=None,
        raw=None,
    )


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
    group_id: str,
    member: NormalizedMember,
    justification: str,
    correlation_id: str | None = None,
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
        return method(group_id, member, justification)
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
    justification: str,
    op_name: str,
    action: str,
    correlation_id: str | None = None,
) -> Dict[str, OperationResult]:
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
                prov, op_name, sec_group, sec_member, justification, correlation_id
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
                        justification=justification,
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


def _orchestrate_member_operation(
    primary_group_id: str,
    member_email: str,
    justification: str,
    op_name: str,
    action: str,
    provider_hint: str | None = None,
    correlation_id: str | None = None,
) -> dict:
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
            justification,
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
        logger.info(
            "orchestration_primary_failed",
            correlation_id=correlation_id,
            primary_status=getattr(primary_result, "status", None),
        )
        return orr.format_orchestration_response(
            primary_result,
            {},
            False,
            correlation_id,
            action=action,
            group_id=primary_group_id,
            member_email=member_email,
        )

    # Primary succeeded; propagate to secondaries using helper
    propagation_results = _propagate_to_secondaries(
        primary_group_id, member_email, justification, op_name, action, correlation_id
    )

    has_partial = any(
        getattr(r, "status", None) != OperationStatus.SUCCESS
        for r in propagation_results.values()
    )

    return orr.format_orchestration_response(
        primary_result,
        propagation_results,
        has_partial,
        correlation_id,
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
):
    """Orchestrate adding a member: primary-first then propagate to secondaries.

    Returns an orchestration response dict as produced by
    `orchestration_responses.format_orchestration_response`.
    """
    return _orchestrate_member_operation(
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
):
    """Orchestrate removing a member: primary-first then propagate to secondaries.

    Returns an orchestration response dict.
    """
    return _orchestrate_member_operation(
        primary_group_id=primary_group_id,
        member_email=member_email,
        justification=justification,
        op_name="remove_member",
        action="remove_member",
        provider_hint=provider_hint,
        correlation_id=correlation_id,
    )
