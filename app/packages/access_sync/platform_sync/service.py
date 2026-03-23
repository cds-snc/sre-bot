"""Access Sync platform sync service.

Batch, group-driven convergence for all users on a platform.
Primary scheduled operation — runs daily or more frequently.

Phase 1: Batch IDP reads — one get_group_members call per policy group.
         Builds email → List[EntitlementRule] desired-state map in O(groups).
Phase 2: Orphan detection — list all provisioned users on the platform.
Phase 3: Per-user convergence — delegates to UserSyncService.sync_user_from_context
         with pre-fetched MembershipContext (zero additional IDP calls per user).
Phase 4: Emit PLATFORM_SYNC_STARTED / PLATFORM_SYNC_COMPLETED domain events.
"""

import uuid
from typing import Dict, List, Mapping, Optional, Set, TYPE_CHECKING

import structlog

from infrastructure.events import Event, EventDispatcher
from infrastructure.operations import OperationResult, OperationStatus
from packages.access_sync.adapters import AccessSyncAdapter, BulkGroupMembershipAdapter
from packages.access_sync import events as sync_events
from packages.access_sync.models import (
    MembershipContext,
    ReconciliationOutcome,
    SyncOutcome,
)
from packages.access_sync.policies import (
    EntitlementRule,
    PlatformPolicy,
    PolicyRegistry,
)
from packages.access_sync.registry import AccessSyncRegistry

if TYPE_CHECKING:
    from infrastructure.directory.provider import DirectoryProvider
    from packages.access_sync.user_sync.service import UserSyncService

logger = structlog.get_logger()


class PlatformSyncService:
    """Batch platform-wide convergence orchestration.

    Fetches IDP group membership once per policy group (O(groups) total),
    detects orphaned users on the platform, then delegates per-user
    convergence to UserSyncService.sync_user_from_context with pre-fetched
    MembershipContext — eliminating all per-user IDP calls in the batch loop.

    Args:
        sync_service: UserSyncService for per-user convergence.
        registry: Platform adapter registry (for orphan detection).
        policies: Platform policy definitions.
        directory: IDP-agnostic directory provider (group/membership lookups).
        dispatcher: Optional event dispatcher for domain event emission.
    """

    def __init__(
        self,
        sync_service: "UserSyncService",
        registry: AccessSyncRegistry,
        policies: PolicyRegistry,
        directory: "DirectoryProvider",
        dispatcher: Optional[EventDispatcher] = None,
    ) -> None:
        self._sync_service = sync_service
        self._registry = registry
        self._policies = policies
        self._directory = directory
        self._dispatcher = dispatcher

    def sync_platform(
        self,
        platform: str,
        dry_run: bool = False,
        run_id: str = "",
    ) -> OperationResult:
        """Converge all users on a platform to match IDP group membership policy.

        Phase 1: Batch IDP reads — one get_group_members call per policy group.
        Phase 2: Orphan detection — list all provisioned users on the platform.
        Phase 3: Per-user sync — delegates to UserSyncService.sync_user_from_context.
        Phase 4: Emit RECONCILIATION_COMPLETED event with drift summary.

        Returns:
            OperationResult[ReconciliationOutcome] on completion (even partial).
            OperationResult.error if the policy or adapter cannot be resolved.
        """
        reconcile_id = run_id or str(uuid.uuid4())
        log = logger.bind(platform=platform, reconcile_id=reconcile_id, dry_run=dry_run)
        log.info("platform_sync_started")

        if self._dispatcher:
            self._dispatcher.dispatch_background(
                Event(
                    event_type=sync_events.PLATFORM_SYNC_STARTED,
                    metadata={"platform": platform, "dry_run": dry_run},
                )
            )

        policy = self._policies.policies.get(platform)
        if policy is None:
            return OperationResult.error(
                OperationStatus.NOT_FOUND,
                message=f"No policy for platform: {platform}",
                error_code="POLICY_NOT_FOUND",
            )

        try:
            adapter = self._registry.get_adapter(platform)
        except KeyError:
            return OperationResult.error(
                OperationStatus.NOT_FOUND,
                message=f"No adapter for platform: {platform}",
                error_code="ADAPTER_NOT_FOUND",
            )

        # Phase 1: batch IDP state — O(groups) not O(users).
        desired_state_result = self._build_desired_state(policy)
        if not desired_state_result.is_success:
            return desired_state_result
        desired_state: Dict[str, List[EntitlementRule]] = (
            desired_state_result.data or {}
        )
        idp_members: Set[str] = set(desired_state.keys())

        # Phase 2: orphan detection.
        provisioned: Set[str] = set()
        provisioned_known = False
        provisioned_result = adapter.list_all_provisioned_users()
        orphans: Set[str] = set()
        if provisioned_result.is_success and provisioned_result.data is not None:
            provisioned = provisioned_result.data
            provisioned_known = True
            orphans = provisioned - idp_members
            log.info("orphans_detected", count=len(orphans))
        else:
            log.warning("orphan_detection_skipped", error=provisioned_result.message)

        # Phase 2.5: platform-side group membership prefetch.
        precomputed_current_ids: Dict[str, Set[str]] = {}
        prefetch_complete = False
        prefetch_result = self._prefetch_current_entitlements(policy, adapter)
        if prefetch_result.is_success and isinstance(prefetch_result.data, dict):
            precomputed_current_ids = prefetch_result.data
            prefetch_complete = True
            log.info(
                "prefetched_current_entitlements",
                users=len(precomputed_current_ids),
            )
        else:
            log.warning(
                "prefetch_current_entitlements_skipped",
                error=prefetch_result.message,
            )

        all_subjects: Set[str] = idp_members | orphans | set(precomputed_current_ids)

        # Phase 3: per-user sync via UserSyncService.sync_user_from_context.
        # MembershipContext carries the pre-fetched IDP state built in Phase 1,
        # so no directory calls are made here — O(groups) total for the whole run.
        users_synced = 0
        users_converged = 0
        requires_manual_action_count = 0
        per_user: Dict[str, SyncOutcome] = {}

        for email in sorted(all_subjects):
            # Orphans have no desired-state entry — context marks them as non-members.
            context = MembershipContext(
                user_should_exist=email in idp_members,
                required_entitlements=desired_state.get(email, []),
            )
            current_ids_for_user: Optional[Set[str]] = None
            if prefetch_complete:
                current_ids_for_user = precomputed_current_ids.get(email, set())
            precomputed_exists: Optional[bool] = None
            if provisioned_known:
                precomputed_exists = email in provisioned
            elif current_ids_for_user is not None:
                precomputed_exists = bool(current_ids_for_user)

            result = self._sync_service.sync_user_from_context(
                user_email=email,
                platform=platform,
                context=context,
                current_entitlement_ids=current_ids_for_user,
                platform_user_exists=precomputed_exists,
                dry_run=dry_run,
                request_id=reconcile_id,
            )
            users_synced += 1
            if result.is_success and result.data is not None:
                outcome: SyncOutcome = result.data
                per_user[email] = outcome
                if outcome.applied_actions:
                    users_converged += 1
                if outcome.requires_manual_action:
                    requires_manual_action_count += 1
            else:
                log.warning(
                    "platform_sync_user_failed",
                    user_email=email,
                    error_code=result.error_code,
                )

        reconciliation_outcome = ReconciliationOutcome(
            platform=platform,
            users_synced=users_synced,
            users_converged=users_converged,
            orphans_found=len(orphans),
            requires_manual_action_count=requires_manual_action_count,
            dry_run=dry_run,
            per_user=per_user,
        )
        log.info(
            "platform_sync_completed",
            users_synced=users_synced,
            users_converged=users_converged,
            orphans_found=len(orphans),
            requires_manual_action=requires_manual_action_count,
        )

        if self._dispatcher:
            self._dispatcher.dispatch_background(
                Event(
                    event_type=sync_events.PLATFORM_SYNC_COMPLETED,
                    metadata={
                        "platform": platform,
                        "users_synced": users_synced,
                        "users_converged": users_converged,
                        "orphans_found": len(orphans),
                        "requires_manual_action_count": requires_manual_action_count,
                        "dry_run": dry_run,
                    },
                )
            )

        return OperationResult.success(data=reconciliation_outcome)

    def _prefetch_current_entitlements(
        self,
        policy: PlatformPolicy,
        adapter: AccessSyncAdapter,
    ) -> OperationResult:
        """Build email -> current entitlement IDs from platform group memberships.

        Performs group-driven reads for all sync-managed group entitlements and
        avoids per-user platform membership lookups in batch reconciliation.
        """
        managed_group_ids: Set[str] = {
            rule.entitlement_id
            for rule in policy.sync_managed_rules()
            if rule.entitlement_type == "group"
        }
        if not managed_group_ids:
            return OperationResult.success(data={})

        # Adapter-specific fast path: single bulk read for many groups.
        if isinstance(adapter, BulkGroupMembershipAdapter):
            response = adapter.list_members_for_groups(managed_group_ids)
            if not response.is_success:
                return OperationResult.error(
                    response.status,
                    message=response.message,
                    error_code=response.error_code,
                )

            data = response.data
            if not isinstance(data, Mapping):
                return OperationResult.error(
                    OperationStatus.PERMANENT_ERROR,
                    message="Invalid list_members_for_groups payload",
                    error_code="INVALID_PLATFORM_RESPONSE",
                )

            return self._invert_group_membership_map(data)

        # Generic fallback: one call per group via adapter contract.
        group_to_members: Dict[str, Set[str]] = {}
        for group_id in managed_group_ids:
            response = adapter.list_group_members(group_id)
            if not response.is_success:
                return OperationResult.error(
                    response.status,
                    message=response.message,
                    error_code=response.error_code,
                )
            if not isinstance(response.data, set):
                return OperationResult.error(
                    OperationStatus.PERMANENT_ERROR,
                    message="Invalid list_group_members payload",
                    error_code="INVALID_PLATFORM_RESPONSE",
                )
            group_to_members[group_id] = {
                email for email in response.data if isinstance(email, str)
            }

        return self._invert_group_membership_map(group_to_members)

    @staticmethod
    def _invert_group_membership_map(group_to_members: Mapping) -> OperationResult:
        """Convert group->members mapping into email->entitlement IDs."""
        by_user: Dict[str, Set[str]] = {}
        for group_id, members in group_to_members.items():
            if not isinstance(group_id, str):
                continue
            if not isinstance(members, (set, list, tuple)):
                continue
            for email in members:
                if not isinstance(email, str):
                    continue
                normalized_email = email.lower()
                if normalized_email not in by_user:
                    by_user[normalized_email] = set()
                by_user[normalized_email].add(group_id)
        return OperationResult.success(data=by_user)

    def _build_desired_state(self, policy: PlatformPolicy) -> OperationResult:
        """Batch-read IDP group membership for all policy groups.

        Makes one get_group_members call per policy group (authn + all
        sync_managed entitlement rules) and builds a mapping of
        email → qualifying EntitlementRules for every user who should exist.

        Returns:
            OperationResult[Dict[str, List[EntitlementRule]]] where keys are
            emails of users in the authn group, and values are the entitlement
            rules they individually qualify for.
        """
        log = logger.bind(platform=policy.platform)

        # Authn group resolves who must have any access at all.
        authn_result = self._directory.get_group(policy.authn_group_slug)
        if not authn_result.is_success or not authn_result.data:
            return OperationResult.error(
                OperationStatus.NOT_FOUND,
                message=f"Authn group not found: {policy.authn_group_slug}",
                error_code="GROUP_NOT_FOUND",
            )

        authn_email = authn_result.data.group_email
        members_result = self._directory.get_group_members(authn_email)
        if not members_result.is_success:
            return OperationResult.error(
                members_result.status,
                message=members_result.message,
                error_code=members_result.error_code,
            )

        desired: Dict[str, List[EntitlementRule]] = {
            m.email.lower(): [] for m in (members_result.data or [])
        }
        log.info("build_desired_state_authn_members", count=len(desired))

        # Entitlement groups: resolve which rules each authn member qualifies for.
        for rule in policy.sync_managed_rules():
            group_result = self._directory.get_group(rule.group_slug)
            if not group_result.is_success or not group_result.data:
                log.warning(
                    "build_desired_state_group_not_found",
                    group_slug=rule.group_slug,
                )
                continue

            rule_members_result = self._directory.get_group_members(
                group_result.data.group_email
            )
            if not rule_members_result.is_success:
                log.warning(
                    "build_desired_state_members_failed",
                    group_slug=rule.group_slug,
                    error=rule_members_result.message,
                )
                continue

            for member in rule_members_result.data or []:
                email = member.email.lower()
                if email in desired:
                    desired[email].append(rule)

        return OperationResult.success(data=desired)
