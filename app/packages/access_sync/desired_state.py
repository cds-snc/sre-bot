"""Desired-state builders for the access sync lifecycle.

This module translates IDP group membership data into the typed
``DesiredUserState`` shape consumed by the coordinator and ``PolicyEngine``.
It makes no adapter calls — all I/O is read-only directory queries.

The coordinator resolves effective policy once per run via
``resolve_effective_policy`` and passes the result to
``build_user_state_from_effective`` (single-user) or
``build_platform_states_from_effective`` (batch reconciliation).  Discovery
of IDP groups is handled by ``discover_group_slugs`` which queries the
directory with the platform prefix and returns matching slugs.
"""

from typing import Dict, List, Set, TYPE_CHECKING

import structlog

from infrastructure.operations import OperationResult, OperationStatus
from packages.access_sync.domain import DesiredUserState
from packages.access_sync.policies import (
    EffectivePlatformPolicy,
    EntitlementRule,
)

if TYPE_CHECKING:
    from infrastructure.directory.provider import DirectoryProvider
    from packages.access_sync.config.settings import AccessSyncRuntimeConfig

logger = structlog.get_logger()


class DirectoryMembershipBuilder:
    """Build desired access state from IDP directory group membership.

    Injected into ``AccessSyncCoordinator`` at startup via ``providers.py``.
    Calls ``DirectoryProvider`` (the IDP abstraction from
    ``infrastructure.services``) exclusively; it never touches platform adapters.

    All public methods return ``OperationResult`` so callers can handle IDP
    failures through the standard result contract without catching exceptions.
    """

    def __init__(self, directory: "DirectoryProvider") -> None:
        self._directory = directory

    def build_user_state_from_effective(
        self,
        user_email: str,
        effective: EffectivePlatformPolicy,
    ) -> OperationResult[DesiredUserState]:
        """Build desired user state from an already-resolved EffectivePlatformPolicy.

        Skips group discovery — the coordinator resolved effective policy once
        before calling this method.
        """
        authn_result = self._check_group_membership(
            effective.authn_group_slug, user_email
        )
        if not authn_result.is_success:
            return OperationResult.error(
                authn_result.status,
                message=authn_result.message,
                error_code=authn_result.error_code,
            )
        if not isinstance(authn_result.data, bool):
            return OperationResult.error(
                OperationStatus.PERMANENT_ERROR,
                message="Invalid authn membership result",
                error_code="INVALID_MEMBERSHIP_RESULT",
            )

        required_entitlements: List[EntitlementRule] = []
        if authn_result.data:
            required_entitlements = self._resolve_member_entitlements(
                user_email=user_email,
                platform=effective.platform,
                rules=effective.sync_managed_rules(),
            )

        return OperationResult.success(
            data=DesiredUserState(
                user_should_exist=authn_result.data,
                required_entitlements=required_entitlements,
            )
        )

    def build_platform_states_from_effective(
        self,
        effective: EffectivePlatformPolicy,
    ) -> OperationResult[Dict[str, DesiredUserState]]:
        """Batch-read authn and entitlement groups into per-user desired state.

        Accepts pre-resolved EffectivePlatformPolicy so the coordinator can
        resolve effective policy once and reuse it across state building,
        prefetch, and engine planning.
        """
        log = logger.bind(platform=effective.platform)

        authn_group_result = self._directory.get_group(effective.authn_group_slug)
        if not authn_group_result.is_success or not authn_group_result.data:
            return OperationResult.error(
                OperationStatus.NOT_FOUND,
                message=f"Authn group not found: {effective.authn_group_slug}",
                error_code="GROUP_NOT_FOUND",
            )

        authn_email = authn_group_result.data.group_email
        authn_members_result = self._directory.get_group_members(
            authn_email,
            include_member_types={"USER"},
        )
        if not authn_members_result.is_success:
            return OperationResult.error(
                authn_members_result.status,
                message=authn_members_result.message,
                error_code=authn_members_result.error_code,
            )

        desired: Dict[str, DesiredUserState] = {
            member.email.lower(): DesiredUserState(user_should_exist=True)
            for member in (authn_members_result.data or [])
        }
        log.info("build_desired_state_authn_members", count=len(desired))

        for rule in effective.sync_managed_rules():
            group_result = self._directory.get_group(rule.group_slug)
            if not group_result.is_success or not group_result.data:
                log.warning(
                    "build_desired_state_group_not_found",
                    group_slug=rule.group_slug,
                )
                continue

            rule_members_result = self._directory.get_group_members(
                group_result.data.group_email,
                include_member_types={"USER"},
            )
            if not rule_members_result.is_success:
                log.warning(
                    "build_desired_state_members_failed",
                    group_slug=rule.group_slug,
                    error=rule_members_result.message,
                )
                continue

            for member in rule_members_result.data or []:
                normalized_email = member.email.lower()
                state = desired.get(normalized_email)
                if state is None:
                    continue
                desired[normalized_email] = DesiredUserState(
                    user_should_exist=True,
                    required_entitlements=state.required_entitlements + [rule],
                )

        return OperationResult.success(data=desired)

    def discover_group_slugs(
        self,
        config: "AccessSyncRuntimeConfig",
        platform: str,
    ) -> Set[str]:
        """Discover IDP group slugs for a platform by querying with the platform prefix.

        Uses ``config.group_prefix(platform)`` as the query and filters results
        to slugs that start with that prefix.  Returns an empty set on IDP
        failure (non-fatal; the coordinator proceeds with an empty rule set).
        """
        prefix = config.group_prefix(platform)
        list_result = self._directory.list_groups(query=prefix)
        if not list_result.is_success:
            logger.bind(platform=platform).warning(
                "discover_groups_failed",
                error=list_result.message,
            )
            return set()

        groups = list_result.data if isinstance(list_result.data, list) else []
        return {
            group.group_slug.strip().lower()
            for group in groups
            if group.group_slug
            and isinstance(group.group_slug, str)
            and group.group_slug.strip().lower().startswith(prefix.lower())
        }

    def _check_group_membership(
        self,
        group_slug: str,
        user_email: str,
    ) -> OperationResult[bool]:
        """Resolve group slug to email and check user membership."""
        group_result = self._directory.get_group(group_slug)
        if not group_result.is_success:
            return OperationResult.error(
                group_result.status,
                message=group_result.message,
                error_code=group_result.error_code,
            )

        group = group_result.data
        if not group or not group.group_email:
            return OperationResult.error(
                OperationStatus.NOT_FOUND,
                message=f"Group not found or has no email: {group_slug}",
                error_code="GROUP_NOT_FOUND",
            )

        membership_result = self._directory.check_membership(
            group.group_email,
            user_email,
        )
        if not membership_result.is_success:
            return OperationResult.error(
                membership_result.status,
                message=membership_result.message,
                error_code=membership_result.error_code,
            )

        member = membership_result.data
        return OperationResult.success(data=member.is_member if member else False)

    def _resolve_member_entitlements(
        self,
        user_email: str,
        platform: str,
        rules: List[EntitlementRule],
    ) -> List[EntitlementRule]:
        """Return only sync-managed entitlement rules the user qualifies for."""
        log = logger.bind(user_email=user_email, platform=platform)
        qualified: List[EntitlementRule] = []
        for rule in rules:
            result = self._check_group_membership(rule.group_slug, user_email)
            if result.is_success and result.data:
                qualified.append(rule)
                continue
            if not result.is_success:
                log.warning(
                    "entitlement_group_check_failed",
                    group_slug=rule.group_slug,
                    error=result.message,
                )
        return qualified
