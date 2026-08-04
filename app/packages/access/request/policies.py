"""Access Requests policy evaluation functions.

All functions here are pure: no persistence, no external I/O, no side
effects.  Every function is independently testable with plain inputs.

This is the single source of truth for Access Requests business rules.
The service layer (service.py) calls these functions and enforces the
outcomes — policy functions only evaluate and return; they do not persist
or raise exceptions.

Pattern mirrors PolicyEngine in packages/access/sync/policies.py.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from packages.access.common.config import EntitlementMode

if TYPE_CHECKING:
    from infrastructure.directory.models import DirectoryGroup
    from infrastructure.directory.provider import DirectoryProvider
    from packages.access.common.config import AccessRuntimeConfig
    from packages.access.request.domain import AccessRequest, ApprovalDecision


def check_entitlement_mode(
    runtime_config: AccessRuntimeConfig,
    platform: str,
    group_slug: str,
) -> EntitlementMode:
    """Return the effective entitlement mode for a platform + group slug.

    Resolution order:
    1. Extract entitlement token from the group slug by removing the platform
       group prefix (for example, extract ``"admins"`` from ``"sg-aws-admins"``
       using platform prefix ``"sg-aws-"``).
    2. Look up the extracted token in ``mode_overrides`` — token-keyed lookup only
       (canonical semantics, consistent with sync and catalog sub-features).
    3. ``"sync_managed"`` default — all managed groups are automatable unless
       overridden.

    Unknown platforms return ``"deactivated"`` so they are always rejected
    at intake without requiring an explicit override.

    Args:
        runtime_config: Access runtime config loaded by the sync provider.
        platform: Platform key (e.g. ``"aws"``).
        group_slug: IDP group slug to look up (e.g. ``"sg-aws-admins"``).

    Returns:
        ``EntitlementMode`` — ``"sync_managed"``, ``"ephemeral"``, or
        ``"deactivated"``.
    """
    platform_policy = runtime_config.platforms.get(platform)
    if platform_policy is None:
        return "deactivated"
    normalized_slug = group_slug.strip().lower()
    token = normalized_slug
    prefix = runtime_config.group_prefix(platform).lower()
    if normalized_slug.startswith(prefix):
        token = normalized_slug[len(prefix) :]

    override = platform_policy.mode_overrides.get(token)
    if override is not None:
        return override
    return "sync_managed"


def resolve_approver_candidates(
    directory_group: DirectoryGroup,
    fallback_slug: str,
    directory: DirectoryProvider,
) -> list[str]:
    """Resolve an ordered list of eligible approver emails for a target group.

    Resolution order:
    1. Members of ``directory_group`` whose role is ``OWNER`` or ``MANAGER``.
    2. If none found: all members of ``fallback_slug`` (org-level fallback).
    3. If fallback also fails or is empty: returns ``[]``.

    The caller (service layer) is responsible for treating an empty result as
    a permanent policy error (``NO_APPROVERS_FOUND``).

    Args:
        directory_group: Resolved canonical group from the IDP.
        fallback_slug: Org-level fallback group slug (e.g. ``"sg-org-admins"``).
        directory: IDP directory provider; read-only calls only.

    Returns:
        Ordered list of approver email strings; may be empty.
    """
    members_result = directory.get_group_members(
        group_key=directory_group.group_email,
        include_member_types={"USER"},
    )
    if members_result.is_success and members_result.data:
        owners = [m.email for m in members_result.data if m.role is not None and m.role.upper() in ("OWNER", "MANAGER")]
        if owners:
            return owners

    fallback_result = directory.get_group_members(
        group_key=fallback_slug,
        include_member_types={"USER"},
    )
    if fallback_result.is_success and fallback_result.data:
        return [m.email for m in fallback_result.data]

    return []


def is_auto_approvable(
    actor_type: str,
    sensitive_entitlement_types: frozenset[str] | None = None,
    entitlement_type: str = "group",
) -> bool:
    """Return True if the request qualifies for auto-approval.

    Auto-approval applies to delegated requests from authorized managers for
    non-sensitive entitlement types.  V1 implementation: delegated actor only,
    with optional sensitive-type exclusion.

    Args:
        actor_type: ``"self"`` or ``"delegated"``.
        sensitive_entitlement_types: Set of entitlement type strings that are
            excluded from auto-approval.  ``None`` means no exclusions.
        entitlement_type: Entitlement type of this request.

    Returns:
        ``True`` if eligible for auto-approval, ``False`` otherwise.
    """
    if actor_type != "delegated":
        return False
    return not (sensitive_entitlement_types and entitlement_type in sensitive_entitlement_types)


def is_self_approval(
    request: AccessRequest,
    approver_email: str,
) -> bool:
    """Return True if the approver is the same person as the actor.

    Separation of duties: the user who submitted the request cannot approve it.
    We check against ``actor_email`` (not ``user_email``) so delegated
    submissions cannot be approved by the submitting manager.

    Args:
        request: The access request being decided.
        approver_email: Email of the user attempting to approve.

    Returns:
        ``True`` if the approval would be a self-approval (reject it).
    """
    return approver_email.lower() == request.actor_email.lower()


def meets_minimum_approver_count(
    decisions: list[ApprovalDecision],
    required_count: int,
) -> bool:
    """Return True if the approved-decision count meets the required minimum.

    Args:
        decisions: All decisions recorded for the request so far.
        required_count: Minimum number of affirmative decisions required.

    Returns:
        ``True`` if the count of ``"approved"`` decisions >= ``required_count``.
    """
    approved_count = sum(1 for d in decisions if d.decision == "approved")
    return approved_count >= required_count
