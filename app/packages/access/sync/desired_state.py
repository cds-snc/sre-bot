"""Desired-state builders for the access sync lifecycle.

This module translates IDP group membership data into the typed
``DesiredUserState`` shape consumed by the coordinator and ``PolicyEngine``.
It makes no adapter calls — all I/O is read-only directory queries.

The coordinator resolves effective policy once per run via
``resolve_effective_policy`` and passes the result to
``build_user_state_from_effective`` (single-user) or
``build_platform_state_from_effective`` (batch reconciliation).  Discovery
of IDP groups is handled by ``discover_group_slugs`` which lists the
directory generically and applies the platform prefix and managed-group
policy locally, propagating any directory failure to the caller.
"""

from typing import TYPE_CHECKING

import structlog

from infrastructure.operations import OperationResult, OperationStatus
from packages.access.common.group_policy import ManagedGroupPolicy
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

    def __init__(self, directory: DirectoryProvider, policy: ManagedGroupPolicy) -> None:
        self._directory = directory
        self._policy = policy

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

            user_group_slugs: set[str] = set()
            for group in user_groups_result.data or []:
                # A listing must not fail because one group is out of domain.
                if not self._policy.is_managed(group):
                    log.warning(
                        "user_group_outside_managed_domain",
                        group_slug=group.group_slug,
                    )
                    continue
                slug = self._policy.canonical_slug(group)
                if slug:
                    user_group_slugs.add(slug)

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
        """Batch-read authn and entitlement groups into platform-shaped state.

        Any IDP failure is propagated as an error result: a caller must never be
        able to mistake an unreachable directory for "these entitlements have no
        members", since reconciliation removes memberships absent from the
        desired state.  The single exception is a ``NOT_FOUND`` on a rule's own
        group, which is legitimate absence and skips only that entitlement.
        """
        log = logger.bind(platform=effective.platform)

        authn_group_result = self._directory.get_group(self._policy.group_key(effective.authn_group_slug))
        if not authn_group_result.is_success or not authn_group_result.data:
            return OperationResult.error(
                OperationStatus.NOT_FOUND,
                message=f"Authn group not found: {effective.authn_group_slug}",
                error_code="GROUP_NOT_FOUND",
            )

        if not self._policy.is_managed(authn_group_result.data):
            return OperationResult.error(
                OperationStatus.PERMANENT_ERROR,
                message=f"Authn group outside managed domain: {effective.authn_group_slug}",
                error_code="DIRECTORY_GROUP_DOMAIN_MISMATCH",
            )

        authn_email = self._policy.canonical_email(authn_group_result.data)
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
            group_result = self._directory.get_group(self._policy.group_key(rule.group_slug))
            if not group_result.is_success and group_result.status != OperationStatus.NOT_FOUND:
                return OperationResult.error(
                    group_result.status,
                    message=group_result.message,
                    error_code=group_result.error_code,
                    retry_after=group_result.retry_after,
                )
            if not group_result.is_success or not group_result.data:
                log.warning(
                    "build_desired_state_group_not_found",
                    group_slug=rule.group_slug,
                )
                continue
            # An explicitly configured group out of domain is a configuration fault.
            if not self._policy.is_managed(group_result.data):
                return OperationResult.error(
                    OperationStatus.PERMANENT_ERROR,
                    message=f"Group outside managed domain: {rule.group_slug}",
                    error_code="DIRECTORY_GROUP_DOMAIN_MISMATCH",
                )
            email_to_rule[self._policy.canonical_email(group_result.data)] = rule

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
                return OperationResult.error(
                    batch_result.status,
                    message=batch_result.message,
                    error_code=batch_result.error_code,
                    retry_after=batch_result.retry_after,
                )
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
    ) -> OperationResult[set[str]]:
        """Discover IDP group slugs for a platform via a generic directory listing.

        Results are filtered client-side to ``config.group_prefix(platform)``
        and to the managed domain.  An IDP failure is propagated as an error
        result: a caller must never be able to mistake an unreachable directory
        for "this platform declares no managed groups", since an empty rule set
        silently disables entitlement enforcement.
        """
        prefix = config.group_prefix(platform)
        log = logger.bind(platform=platform, group_prefix=prefix)
        list_result = self._directory.list_groups()
        if not list_result.is_success:
            log.warning(
                "discover_groups_failed",
                error=list_result.message,
            )
            return OperationResult.error(
                list_result.status,
                message=list_result.message,
                error_code=list_result.error_code,
                retry_after=list_result.retry_after,
            )

        groups = list_result.data if isinstance(list_result.data, list) else []
        discovered: set[str] = set()
        for group in groups:
            if not self._policy.matches_prefix(group, prefix):
                continue
            # Discovery must not be taken down by one out-of-domain group.
            if not self._policy.is_managed(group):
                log.warning(
                    "discover_groups_outside_managed_domain",
                    group_slug=group.group_slug,
                )
                continue
            slug = self._policy.canonical_slug(group)
            if slug.startswith(prefix.lower()):
                discovered.add(slug)
        log.info(
            "discover_groups_completed",
            discovered_count=len(discovered),
            discovered_group_slugs=sorted(discovered),
        )
        return OperationResult.success(data=discovered)

    def _check_group_membership(
        self,
        group_slug: str,
        user_email: str,
    ) -> OperationResult[bool]:
        """Resolve group slug to its canonical email and check user membership."""
        group_result = self._directory.get_group(self._policy.group_key(group_slug))
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

        # An explicitly requested group out of domain is a configuration fault.
        if not self._policy.is_managed(group):
            return OperationResult.error(
                OperationStatus.PERMANENT_ERROR,
                message=f"Group outside managed domain: {group_slug}",
                error_code="DIRECTORY_GROUP_DOMAIN_MISMATCH",
            )

        membership_result = self._directory.check_membership(
            self._policy.canonical_email(group),
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
