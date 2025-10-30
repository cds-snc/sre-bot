from typing import Dict

from core.logging import get_module_logger

from modules.groups.orchestration import (
    add_member_to_group as orchestrate_add_member,
    remove_member_from_group as orchestrate_remove_member,
)

logger = get_module_logger()


def add_member_to_group(
    group_id: str,
    member_email: str,
    justification: str,
    provider_type: str,
    requestor_email: str,
) -> Dict:
    """Add member to group using appropriate provider."""
    orchestrate_result = orchestrate_add_member(
        group_id,
        member_email,
        justification,
        provider_type,
        requestor_email,
    )
    return orchestrate_result


def remove_member_from_group(
    group_id: str,
    member_email: str,
    justification: str,
    provider_type: str,
    requestor_email: str,
) -> Dict:
    """Remove member from group using appropriate provider."""
    orchestrate_result = orchestrate_remove_member(
        group_id,
        member_email,
        justification,
        provider_type,
        requestor_email,
    )
    return orchestrate_result
