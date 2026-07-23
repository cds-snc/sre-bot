"""Desired-state builders for the access sync lifecycle.

This module translates IDP group membership data into the typed
``DesiredUserState`` shape consumed by the coordinator and ``PolicyEngine``.
It makes no adapter calls — all I/O is read-only directory queries.

The coordinator resolves effective policy once per run via
``resolve_effective_policy`` and passes the result to
``build_user_state_from_effective`` (single-user) or
``build_platform_state_from_effective`` (batch reconciliation).  Discovery
of IDP groups is handled by ``discover_group_slugs`` which queries the
directory with the platform prefix and returns matching slugs.
"""

from typing import TYPE_CHECKING

import structlog

from infrastructure.operations import OperationResult, OperationStatus
from packages.access.sync.domain import DesiredPlatformState, DesiredUserState
from packages.access.sync.policies import EffectivePlatformPolicy, EntitlementRule

if TYPE_CHECKING:
    from infrastructure.directory.provider import DirectoryProvider
    from packages.access.common.config import AccessRuntimeConfig

logger = structlog.get_logger()


class DirectoryMembershipBuilder:
    """Build desired access state from IDP directory group membership.

    Injected into ``AccessSyncApplicationService`` at startup via ``providers.py``.
    Calls ``DirectoryProvider`` (the IDP abstraction from
    ``infrastructure.directory``) exclusively; it never touches platform adapters.

    All public methods return ``OperationResult`` so callers can handle IDP
    failures through the standard result contract without catching exceptions.
    """

    def __init__(self, directory: DirectoryProvider) -> None:
        self._directory = directory

    def build_user_state_from_effective(
        self,
        user_email: str,
        effective: EffectivePlatformPolicy,
    ) -> OperationResult[DesiredUserState]:
        """Build desired user state from an already-resolved EffectivePlatformPolicy.

        Two separate IDP calls with different semantics:

        1. Lifecycle (user_should_exist): ``check_membership`` against the authn
           group.  Uses the directory's transitive hasMember check so users who
           are members of the authn group via a nested sub-group (e.g.
           sg-aws-scratch ⊂ sg-aws-authn) are correctly resolved.

        2. Entitlements (required_entitlements): ``get_user_groups`` returns the
           user's direct group memberships, filtered against the run-scoped
           sync_managed rules.  Deactivated tokens (e.g. scratch) are already
           excluded from effective policy so they never produce entitlement rules.

        Skips group discovery — the coordinator resolved effective policy once
        before calling this method.
        """
        log = logger.bind(user_email=user_email, platform=effective.platform)
        authn_result = self._check_group_membership(effective.authn_group_slug, user_email)
        log.debug(
            "check_authn_group_membership_completed",
            authn_group_slug=effective.authn_group_slug,
            is_member=authn_result.data if authn_result.is_success else None,
            result_status=authn_result.status,
        )
        if not authn_result.is_success:
            return OperationResult.error(
                authn_result.status,
                message=authn_result.message,
                error_code=authn_result.error_code,
            )

        user_should_exist: bool = authn_result.data or False

        required_entitlements: list[EntitlementRule] = []
        if user_should_exist:
            user_groups_result = self._directory.get_user_groups(user_email)
            if not user_groups_result.is_success:
                return OperationResult.error(
                    user_groups_result.status,
                    message=user_groups_result.message,
                    error_code=user_groups_result.error_code,
                )

            user_group_slugs: set[str] = {
                group.group_slug.lower() for group in (user_groups_result.data or []) if group.group_slug
            }

            required_entitlements = [
                rule for rule in effective.sync_managed_rules() if rule.group_slug.lower() in user_group_slugs
            ]

        logger.bind(user_email=user_email, platform=effective.platform).info(
            "build_user_state_completed",
            user_should_exist=user_should_exist,
            required_entitlement_count=len(required_entitlements),
            required_entitlement_group_slugs=[rule.group_slug for rule in required_entitlements],
            required_entitlement_ids=[rule.entitlement_id for rule in required_entitlements],
        )
        return OperationResult.success(
            data=DesiredUserState(
                user_should_exist=user_should_exist,
                required_entitlements=required_entitlements,
            )
        )

    def build_platform_state_from_effective(
        self,
        effective: EffectivePlatformPolicy,
    ) -> OperationResult[DesiredPlatformState]:
        """Batch-read authn and entitlement groups into platform-shaped state."""
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

        desired_users: set[str] = {member.email.lower() for member in (authn_members_result.data or [])}
        log.info("build_desired_state_authn_members", count=len(desired_users))

        email_to_rule: dict[str, EntitlementRule] = {}
        for rule in effective.sync_managed_rules():
            group_result = self._directory.get_group(rule.group_slug)
            if not group_result.is_success or not group_result.data:
                log.warning(
                    "build_desired_state_group_not_found",
                    group_slug=rule.group_slug,
                )
                continue
            email_to_rule[group_result.data.group_email] = rule

        desired_members_by_entitlement: dict[str, set[str]] = {}
        entitlement_slug_by_id: dict[str, str] = {rule.entitlement_id: rule.group_slug for rule in effective.sync_managed_rules()}

        if email_to_rule:
            batch_result = self._directory.get_group_members_batch(
                list(email_to_rule.keys()),
                include_member_types={"USER"},
            )
            if not batch_result.is_success:
                log.warning(
                    "build_desired_state_batch_members_failed",
                    error=batch_result.message,
                )
            else:
                for group_email, members in (batch_result.data or {}).items():
                    matched_rule = email_to_rule.get(group_email)
                    if matched_rule is None:
                        continue
                    desired_members_by_entitlement.setdefault(matched_rule.entitlement_id, set()).update(
                        member.email.lower() for member in members if member.email.lower() in desired_users
                    )

        return OperationResult.success(
            data=DesiredPlatformState(
                desired_users=desired_users,
                desired_members_by_entitlement=desired_members_by_entitlement,
                entitlement_slug_by_id=entitlement_slug_by_id,
            )
        )

    def discover_group_slugs(
        self,
        config: AccessRuntimeConfig,
        platform: str,
    ) -> set[str]:
        """Discover IDP group slugs for a platform by querying with the platform prefix.

        Uses ``config.group_prefix(platform)`` as the query and filters results
        to slugs that start with that prefix.  Returns an empty set on IDP
        failure (non-fatal; the coordinator proceeds with an empty rule set).
        """
        prefix = config.group_prefix(platform)
        log = logger.bind(platform=platform, group_prefix=prefix)
        list_result = self._directory.list_groups(query=prefix)
        if not list_result.is_success:
            log.warning(
                "discover_groups_failed",
                error=list_result.message,
            )
            return set()

        groups = list_result.data if isinstance(list_result.data, list) else []
        discovered = {
            group.group_slug.strip().lower()
            for group in groups
            if group.group_slug
            and isinstance(group.group_slug, str)
            and group.group_slug.strip().lower().startswith(prefix.lower())
        }
        log.info(
            "discover_groups_completed",
            discovered_count=len(discovered),
            discovered_group_slugs=sorted(discovered),
        )
        return discovered

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
