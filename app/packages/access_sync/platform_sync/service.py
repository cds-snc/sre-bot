"""Access Sync platform sync service.

Batch, group-driven convergence for all users on a platform.
Primary scheduled operation — runs daily or more frequently.

Phase 1: Batch IDP reads — one get_group_members call per policy group.
         Builds email → List[EntitlementRule] desired-state map in O(groups).
Phase 2: Orphan detection — list all provisioned users on the platform.
Phase 3: Per-user convergence — delegates to UserSyncService.sync_user_from_context
         with pre-fetched DesiredUserState (zero additional IDP calls per user).
Phase 4: Emit PLATFORM_SYNC_STARTED / PLATFORM_SYNC_COMPLETED domain events.
"""

import uuid
from dataclasses import replace
from typing import Dict, Mapping, Optional, Set, TYPE_CHECKING

import structlog

from infrastructure.events import Event, EventDispatcher
from infrastructure.operations import OperationResult, OperationStatus
from packages.access_sync import events as sync_events
from packages.access_sync.adapters import AccessSyncAdapter, BulkGroupMembershipAdapter
from packages.access_sync.membership import DirectoryMembershipBuilder
from packages.access_sync.models import (
    DesiredUserState,
    ReconciliationOutcome,
    SyncOutcome,
)
from packages.access_sync.policies import (
    PlatformPolicy,
)
from packages.access_sync.runtime import resolve_platform_context

if TYPE_CHECKING:
    from infrastructure.directory.provider import DirectoryProvider
    from packages.access_sync.user_sync.service import UserSyncService

logger = structlog.get_logger()


class PlatformSyncService:
    """Batch platform-wide convergence orchestration.

    Fetches IDP group membership once per policy group (O(groups) total),
    detects orphaned users on the platform, then delegates per-user
    convergence to UserSyncService.sync_user_from_context with pre-fetched
    DesiredUserState — eliminating all per-user IDP calls in the batch loop.

    Args:
        sync_service: UserSyncService for per-user convergence.
        adapters: Platform adapter mapping (for orphan detection).
        policies: Platform policy definitions.
        directory: IDP-agnostic directory provider (group/membership lookups).
        dispatcher: Optional event dispatcher for domain event emission.
    """

    def __init__(
        self,
        sync_service: "UserSyncService",
        adapters: Mapping[str, AccessSyncAdapter],
        policies: Mapping[str, PlatformPolicy],
        directory: "DirectoryProvider",
        dispatcher: Optional[EventDispatcher] = None,
    ) -> None:
        self._sync_service = sync_service
        self._adapters = adapters
        self._policies = policies
        self._dispatcher = dispatcher
        self._membership_builder = DirectoryMembershipBuilder(directory)

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

        resolved_result = resolve_platform_context(
            platform=platform,
            policies=self._policies,
            adapters=self._adapters,
        )
        if not resolved_result.is_success or resolved_result.data is None:
            return resolved_result

        policy = resolved_result.data.policy
        adapter = resolved_result.data.adapter

        # Phase 1: batch IDP state — O(groups) not O(users).
        desired_state_result = self._membership_builder.build_platform_states(policy)
        if not desired_state_result.is_success or desired_state_result.data is None:
            return desired_state_result
        desired_states = desired_state_result.data
        idp_members: Set[str] = set(desired_states.keys())

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
        # DesiredUserState carries the pre-fetched IDP state built in Phase 1,
        # so no directory calls are made here — O(groups) total for the whole run.
        users_synced = 0
        users_converged = 0
        requires_manual_action_count = 0
        per_user: Dict[str, SyncOutcome] = {}

        for email in sorted(all_subjects):
            desired_state = desired_states.get(
                email,
                DesiredUserState(user_should_exist=False),
            )
            current_ids_for_user: Optional[Set[str]] = None
            if prefetch_complete:
                current_ids_for_user = precomputed_current_ids.get(email, set())
            precomputed_exists: Optional[bool] = None
            if provisioned_known:
                precomputed_exists = email in provisioned
            elif current_ids_for_user is not None:
                precomputed_exists = bool(current_ids_for_user)

            desired_state = replace(
                desired_state,
                current_entitlement_ids=current_ids_for_user,
                platform_user_exists=precomputed_exists,
            )

            result = self._sync_service.sync_user_from_context(
                user_email=email,
                platform=platform,
                desired_state=desired_state,
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
