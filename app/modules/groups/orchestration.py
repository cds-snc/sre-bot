"""Provider-agnostic group mapping and orchestration helpers.

This module contains lightweight helpers used by the orchestration layer.
All heavy imports (provider registry, mapping helpers) are performed lazily
inside functions to avoid import-time failures during incremental rollout.
"""

from typing import Dict
from core.logging import get_module_logger

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
