"""Provider-agnostic group mapping and orchestration helpers.

This module contains lightweight helpers used by the orchestration layer.
All heavy imports (provider registry, mapping helpers) are performed lazily
inside functions to avoid import-time failures during incremental rollout.
"""

from uuid import uuid4
from typing import Dict
from core.logging import get_module_logger
from modules.groups import reconciliation_integration as ri
from modules.groups import orchestration_responses as orr

logger = get_module_logger()


def get_primary_provider_name() -> str:
    """Return configured primary provider name (lazy re-export).

    Performs a lazy import from `modules.groups.providers` to avoid importing
    the entire provider registry at module import time. This keeps the file
    safe to import during phased rollout.
    """
    from modules.groups.providers import get_primary_provider_name as _get_primary

    return _get_primary()


def get_enabled_secondary_providers() -> Dict[str, object]:
    """Return all active providers except the primary.

    Returns a mapping of provider name -> provider instance for non-primary
    providers. The provider types are referenced as strings to avoid hard
    runtime typing requirements at import time.
    """
    # Local import to avoid heavy import at module load time
    from modules.groups.providers import get_active_providers

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
    """Map a secondary provider's group id into the primary provider format.

    Uses `modules.groups.group_name_mapping.map_provider_group_id` lazily and
    translates errors into ValueError for callers.
    """
    primary_provider_name = get_primary_provider_name()

    try:
        # lazy import mapping helper
        from modules.groups.group_name_mapping import map_provider_group_id

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
    """Map primary provider group id to a secondary provider format.

    Reverse mapping used during propagation to secondary providers.
    """
    primary_provider_name = get_primary_provider_name()

    try:
        from modules.groups.group_name_mapping import map_provider_group_id

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


def normalize_member_for_provider(member_email: str, provider_type: str) -> object:
    """Normalize an email into a provider-specific NormalizedMember.

    This function performs light validation and returns a `NormalizedMember`
    instance (imported lazily) to avoid importing Pydantic models at module
    import time.
    """
    if not member_email or "@" not in member_email:
        raise ValueError(f"Invalid email: {member_email}")

    # lazy import of the schema model
    from modules.groups.schemas import NormalizedMember

    return NormalizedMember(
        email=member_email,
        id=None,
        role=None,
        provider_member_id=None,
        raw=None,
    )


def validate_group_in_provider(group_id: str, provider: object) -> bool:
    """Verify that a group exists and is accessible in the given provider.

    Calls `provider.get_group_members()` and inspects returned OperationResult
    where possible. Any exception results in False.
    """
    try:
        result = provider.get_group_members(group_id)
        # If OperationResult-like, check status attribute
        if hasattr(result, "status"):
            from modules.groups.providers.base import OperationStatus

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
    # lazy imports
    from uuid import uuid4

    if not correlation_id:
        correlation_id = str(uuid4())

    from modules.groups.providers import get_primary_provider, get_active_providers
    from modules.groups.providers.base import OperationStatus

    primary = get_primary_provider()

    # Normalize member for primary provider
    member_obj = normalize_member_for_provider(
        member_email, provider_type=provider_hint or ""
    )

    logger.info(
        "orchestration_add_member_start",
        correlation_id=correlation_id,
        primary=primary.__class__.__name__,
        group=primary_group_id,
        member=member_email,
    )

    # Call primary provider
    try:
        primary_result = primary.add_member(primary_group_id, member_obj, justification)
    except Exception as e:
        logger.error(
            "primary_add_member_exception",
            correlation_id=correlation_id,
            error=str(e),
            exc_info=True,
        )
        # Synthesize a transient error OperationResult-like object
        from modules.groups.providers.base import OperationResult

        primary_result = OperationResult.transient_error(str(e))

    # If primary failed, do not propagate
    if getattr(primary_result, "status", None) != OperationStatus.SUCCESS:
        logger.info(
            "orchestration_primary_failed",
            correlation_id=correlation_id,
            primary_status=getattr(primary_result, "status", None),
        )
        propagation = {}
        partial_failures = False
        return orr.format_orchestration_response(
            primary_result,
            propagation,
            partial_failures,
            correlation_id,
            action="add_member",
            group_id=primary_group_id,
            member_email=member_email,
        )

    # Primary succeeded; propagate to secondaries
    secondaries = get_active_providers()
    primary_name = getattr(primary, "__class__", None)
    # Filter out primary by comparing configured primary name
    try:
        from modules.groups.providers import get_primary_provider_name

        primary_name = get_primary_provider_name()
    except Exception:
        primary_name = None

    propagation_results = {}
    for name, prov in secondaries.items():
        if name == primary_name:
            continue
        try:
            # map primary group id to secondary format
            sec_group = map_primary_to_secondary_group(primary_group_id, name)
            sec_member = normalize_member_for_provider(member_email, provider_type=name)
            try:
                sec_op = prov.add_member(sec_group, sec_member, justification)
            except Exception as e:
                logger.warning(
                    "secondary_add_member_exception",
                    correlation_id=correlation_id,
                    provider=name,
                    error=str(e),
                )
                from modules.groups.providers.base import OperationResult

                sec_op = OperationResult.transient_error(str(e))

            propagation_results[name] = sec_op

            # Enqueue failed propagation for reconciliation when needed
            if getattr(sec_op, "status", None) != OperationStatus.SUCCESS:
                # Extract an error message where available
                err_msg = getattr(sec_op, "message", "")
                try:
                    ri.enqueue_failed_propagation(
                        correlation_id=correlation_id,
                        provider=name,
                        group_id=sec_group,
                        member_email=member_email,
                        action="add_member",
                        justification=justification,
                        error_message=err_msg,
                    )
                except Exception:
                    logger.exception("enqueue_failed_propagation_failed", provider=name)

        except Exception as e:
            # mapping or provider invocation errors
            from modules.groups.providers.base import OperationResult

            propagation_results[name] = OperationResult.transient_error(str(e))
            logger.error(
                "propagation_mapping_or_call_failed",
                correlation_id=correlation_id,
                provider=name,
                error=str(e),
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
        action="add_member",
        group_id=primary_group_id,
        member_email=member_email,
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

    if not correlation_id:
        correlation_id = str(uuid4())

    from modules.groups.providers import get_primary_provider, get_active_providers
    from modules.groups.providers.base import OperationStatus

    primary = get_primary_provider()
    member_obj = normalize_member_for_provider(
        member_email, provider_type=provider_hint or ""
    )

    logger.info(
        "orchestration_remove_member_start",
        correlation_id=correlation_id,
        primary=primary.__class__.__name__,
        group=primary_group_id,
        member=member_email,
    )

    try:
        primary_result = primary.remove_member(
            primary_group_id, member_obj, justification
        )
    except Exception as e:
        logger.error(
            "primary_remove_member_exception",
            correlation_id=correlation_id,
            error=str(e),
            exc_info=True,
        )
        from modules.groups.providers.base import OperationResult

        primary_result = OperationResult.transient_error(str(e))

    if getattr(primary_result, "status", None) != OperationStatus.SUCCESS:
        return orr.format_orchestration_response(
            primary_result,
            {},
            False,
            correlation_id,
            action="remove_member",
            group_id=primary_group_id,
            member_email=member_email,
        )

    # propagate
    secondaries = get_active_providers()
    try:
        from modules.groups.providers import get_primary_provider_name

        primary_name = get_primary_provider_name()
    except Exception:
        primary_name = None

    propagation_results = {}
    for name, prov in secondaries.items():
        if name == primary_name:
            continue
        try:
            sec_group = map_primary_to_secondary_group(primary_group_id, name)
            sec_member = normalize_member_for_provider(member_email, provider_type=name)
            try:
                sec_op = prov.remove_member(sec_group, sec_member, justification)
            except Exception as e:
                from modules.groups.providers.base import OperationResult

                sec_op = OperationResult.transient_error(str(e))
            propagation_results[name] = sec_op

            if getattr(sec_op, "status", None) != OperationStatus.SUCCESS:
                try:
                    ri.enqueue_failed_propagation(
                        correlation_id=correlation_id,
                        provider=name,
                        group_id=sec_group,
                        member_email=member_email,
                        action="remove_member",
                        justification=justification,
                        error_message=getattr(sec_op, "message", ""),
                    )
                except Exception:
                    logger.exception("enqueue_failed_propagation_failed", provider=name)

        except Exception as e:
            from modules.groups.providers.base import OperationResult

            propagation_results[name] = OperationResult.transient_error(str(e))

    has_partial = any(
        getattr(r, "status", None) != OperationStatus.SUCCESS
        for r in propagation_results.values()
    )

    return orr.format_orchestration_response(
        primary_result,
        propagation_results,
        has_partial,
        correlation_id,
        action="remove_member",
        group_id=primary_group_id,
        member_email=member_email,
    )
