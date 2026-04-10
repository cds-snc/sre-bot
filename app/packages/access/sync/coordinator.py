"""Access Sync coordinator — single orchestration entrypoint.

This is the canonical place to understand the full sync business flow.
A new engineer should be able to read this file and understand what
happens when we sync one user or one platform.

Two public methods:
    sync_user()     — on-demand single-user convergence.
    sync_platform() — batch group-driven reconciliation of all users.

Internal flow:
1. Resolve target: look up policy and adapter by normalized key.
2. Discover IDP group slugs and resolve effective policy once for the run.
3. Build desired state from IDP group membership (no adapter calls here).
4. Prefetch current platform state for delta planning (platform sync only).
5. Plan actions via PolicyEngine (pure, no side effects).
6. Execute planned actions via adapter (or skip for dry-run).
7. Persist audit record and emit domain events.
"""

import uuid
from dataclasses import replace
from typing import Dict, List, Mapping, Optional, Protocol, Set, TYPE_CHECKING

import structlog

from infrastructure.events import Event, EventDispatcher
from infrastructure.operations import OperationResult, OperationStatus
from packages.access.common.config import AccessRuntimeConfig
from packages.access.sync import events as sync_events
from packages.access.sync.adapters import (
    AccessSyncAdapter,
    BulkGroupMembershipAdapter,
    EntitlementCanonicalizingAdapter,
)
from packages.access.sync.desired_state import DirectoryMembershipBuilder
from packages.access.sync.domain import (
    DesiredUserState,
    ReconciliationOutcome,
    SyncOutcome,
    SyncRunRecord,
)
from packages.access.sync.policies import (
    EffectivePlatformPolicy,
    EntitlementRule,
    PlannedAction,
    PlatformPolicy,
    PolicyEngine,
    resolve_effective_policy,
)

if TYPE_CHECKING:
    from packages.access.sync.store import SyncRunRepository

logger = structlog.get_logger()


class AccessSyncCoordinatorPort(Protocol):
    """Structural contract for the access sync coordinator.

    Transport handlers (HTTP routes, Slack commands) and test stubs depend on
    this Protocol rather than the concrete class, so they remain decoupled from
    implementation details and are trivially substitutable in tests.
    """

    def sync_user(
        self,
        user_email: str,
        platform: str,
        dry_run: bool = False,
        request_id: str = "",
    ) -> OperationResult: ...

    def sync_platform(
        self,
        platform: str,
        dry_run: bool = False,
        request_id: str = "",
    ) -> OperationResult: ...


class AccessSyncCoordinator:
    """Orchestrates the full access sync lifecycle.

    Wires ``PolicyEngine``, ``DirectoryMembershipBuilder``, and the platform
    adapter together.  All business logic stays in ``policies.py``; all IDP
    reads stay in ``desired_state.py``; all platform mutations stay in the
    adapter.  The coordinator's own role is sequencing.

    Constructed once per process by ``providers.get_access_sync_coordinator``
    and injected into HTTP route handlers and the scheduled task via FastAPI
    ``Depends``.
    """

    def __init__(
        self,
        adapters: Mapping[str, AccessSyncAdapter],
        config: AccessRuntimeConfig,
        membership_builder: DirectoryMembershipBuilder,
        repository: "Optional[SyncRunRepository]" = None,
        dispatcher: Optional[EventDispatcher] = None,
    ) -> None:
        self._adapters = adapters
        self._config = config
        self._membership_builder = membership_builder
        self._repository = repository
        self._dispatcher = dispatcher
        self._engine = PolicyEngine()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def sync_user(
        self,
        user_email: str,
        platform: str,
        dry_run: bool = False,
        request_id: str = "",
    ) -> OperationResult:
        """Converge one user's access on a platform to match IDP policy.

        Performs a live IDP membership check for the user across all
        relevant groups, then plans and executes the required actions.

        Returns:
            OperationResult[SyncOutcome] on success.
            OperationResult.error on infrastructure or policy failures.
        """
        run_id = request_id or str(uuid.uuid4())
        log = logger.bind(user_email=user_email, platform=platform, run_id=run_id)
        log.info("sync_user_started", dry_run=dry_run)

        policy, adapter, error = self._resolve_target(platform)
        if error is not None:
            return error

        assert policy is not None and adapter is not None  # narrowing

        discovered = self._membership_builder.discover_group_slugs(
            self._config, platform
        )
        effective = resolve_effective_policy(self._config, platform, discovered)

        desired_result = self._membership_builder.build_user_state_from_effective(
            user_email=user_email,
            effective=effective,
        )
        if not desired_result.is_success or desired_result.data is None:
            return desired_result

        return self._converge_user(
            user_email=user_email,
            platform=platform,
            adapter=adapter,
            effective=effective,
            desired_state=desired_result.data,
            dry_run=dry_run,
            run_id=run_id,
            request_id=request_id,
            log=log,
        )

    def sync_platform(
        self,
        platform: str,
        dry_run: bool = False,
        request_id: str = "",
    ) -> OperationResult:
        """Converge all users on a platform to match IDP group membership.

        Phase 1: Batch IDP reads — one get_group_members call per policy
                 group. Builds desired state in O(groups) not O(users).
        Phase 2: Orphan detection — list all provisioned users on the platform.
        Phase 3: Current entitlement prefetch — inverts platform group membership
                 into a per-user entitlement-ID map for delta planning.
        Phase 4: Per-user convergence — plan and execute with zero additional
                 IDP calls (pre-fetched state reused from Phase 1).

        Returns:
            OperationResult[ReconciliationOutcome] on completion (even partial).
            OperationResult.error if policy or adapter cannot be resolved.
        """
        reconcile_id = request_id or str(uuid.uuid4())
        log = logger.bind(platform=platform, reconcile_id=reconcile_id, dry_run=dry_run)
        log.info("sync_platform_started")

        if self._dispatcher:
            self._dispatcher.dispatch_background(
                Event(
                    event_type=sync_events.PLATFORM_SYNC_STARTED,
                    metadata={"platform": platform, "dry_run": dry_run},
                )
            )

        policy, adapter, error = self._resolve_target(platform)
        if error is not None:
            return error

        assert policy is not None and adapter is not None  # narrowing

        # Resolve effective policy once for the entire run.
        discovered = self._membership_builder.discover_group_slugs(
            self._config, platform
        )
        effective = resolve_effective_policy(self._config, platform, discovered)

        adapter_capabilities = adapter.capabilities()

        # Phase 1: batch IDP desired state — O(groups) not O(users).
        desired_result = self._membership_builder.build_platform_states_from_effective(
            effective=effective,
        )
        if not desired_result.is_success or desired_result.data is None:
            return desired_result
        desired_states = desired_result.data
        idp_members: Set[str] = set(desired_states.keys())

        # Phase 2: orphan detection.
        provisioned, provisioned_known, orphans = self._detect_orphans(
            adapter=adapter,
            idp_members=idp_members,
            log=log,
        )

        # Phase 3: current entitlement prefetch for delta planning.
        precomputed_current_ids, prefetch_complete = self._prefetch_current_ids(
            effective=effective,
            adapter=adapter,
            log=log,
        )
        has_sync_managed = bool(effective.sync_managed_rules())

        # Lifecycle-only policies can skip users already in sync.
        candidate_subjects, all_subjects, lifecycle_delta_optimized = (
            self._select_subjects(
                idp_members=idp_members,
                orphans=orphans,
                precomputed_current_ids=precomputed_current_ids,
                provisioned=provisioned,
                provisioned_known=provisioned_known,
                has_sync_managed=has_sync_managed,
                adapter_capabilities=adapter_capabilities,
                log=log,
            )
        )

        # Phase 4: per-user convergence — zero additional IDP calls.
        (
            users_synced,
            users_converged,
            requires_manual_action_count,
            per_user,
        ) = self._sync_platform_users(
            all_subjects=all_subjects,
            platform=platform,
            adapter=adapter,
            effective=effective,
            desired_states=desired_states,
            dry_run=dry_run,
            reconcile_id=reconcile_id,
            prefetch_complete=prefetch_complete,
            precomputed_current_ids=precomputed_current_ids,
            provisioned_known=provisioned_known,
            provisioned=provisioned,
            log=log,
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

        # Build action breakdown from per-user planned actions for a single
        # queryable summary line — avoids scanning N per-user log lines to
        # answer "what would this run actually do?".
        actions_breakdown: Dict[str, int] = {}
        for outcome in per_user.values():
            for action in outcome.planned_actions:
                actions_breakdown[action] = actions_breakdown.get(action, 0) + 1
        planned_actions_total = sum(actions_breakdown.values())

        log.info(
            "sync_platform_completed",
            users_synced=users_synced,
            users_converged=users_converged,
            orphans_found=len(orphans),
            requires_manual_action=requires_manual_action_count,
            planned_actions_total=planned_actions_total,
            planned_actions_breakdown=actions_breakdown,
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
                        "subjects_total": len(candidate_subjects),
                        "subjects_processed": len(all_subjects),
                        "lifecycle_delta_optimized": lifecycle_delta_optimized,
                    },
                )
            )

        return OperationResult.success(data=reconciliation_outcome)

    def _detect_orphans(
        self,
        adapter: AccessSyncAdapter,
        idp_members: Set[str],
        log,
    ) -> tuple[Set[str], bool, Set[str]]:
        """Return provisioned users, whether that set is known, and orphan users."""
        provisioned: Set[str] = set()
        provisioned_known = False
        orphans: Set[str] = set()

        provisioned_result = adapter.list_all_provisioned_users()
        if provisioned_result.is_success and provisioned_result.data is not None:
            provisioned = provisioned_result.data
            provisioned_known = True
            orphans = provisioned - idp_members
            log.info("orphans_detected", count=len(orphans))
        else:
            log.warning("orphan_detection_skipped", error=provisioned_result.message)

        return provisioned, provisioned_known, orphans

    def _prefetch_current_ids(
        self,
        effective: EffectivePlatformPolicy,
        adapter: AccessSyncAdapter,
        log,
    ) -> tuple[Dict[str, Set[str]], bool]:
        """Prefetch and return platform entitlement IDs by user."""
        precomputed_current_ids: Dict[str, Set[str]] = {}
        prefetch_result = self._prefetch_current_entitlements(effective, adapter)
        if prefetch_result.is_success and isinstance(prefetch_result.data, dict):
            precomputed_current_ids = prefetch_result.data
            log.info(
                "prefetched_current_entitlements",
                users=len(precomputed_current_ids),
            )
            return precomputed_current_ids, True

        log.warning(
            "prefetch_current_entitlements_skipped",
            error=prefetch_result.message,
        )
        return precomputed_current_ids, False

    def _select_subjects(
        self,
        idp_members: Set[str],
        orphans: Set[str],
        precomputed_current_ids: Dict[str, Set[str]],
        provisioned: Set[str],
        provisioned_known: bool,
        has_sync_managed: bool,
        adapter_capabilities,
        log,
    ) -> tuple[Set[str], Set[str], bool]:
        """Select all candidate users and the subset to process this run."""
        candidate_subjects: Set[str] = (
            idp_members | orphans | set(precomputed_current_ids)
        )
        lifecycle_delta_optimized = False

        if (
            not has_sync_managed
            and provisioned_known
            and adapter_capabilities.supports_bulk_user_delta
        ):
            all_subjects: Set[str] = (idp_members - provisioned) | orphans
            lifecycle_delta_optimized = True
            log.info("lifecycle_delta_subjects_selected", count=len(all_subjects))
        else:
            all_subjects = candidate_subjects

        log.info(
            "sync_platform_subject_counts",
            subjects_total=len(candidate_subjects),
            subjects_processed=len(all_subjects),
            lifecycle_delta_optimized=lifecycle_delta_optimized,
        )
        return candidate_subjects, all_subjects, lifecycle_delta_optimized

    def _sync_platform_users(
        self,
        all_subjects: Set[str],
        platform: str,
        adapter: AccessSyncAdapter,
        effective: EffectivePlatformPolicy,
        desired_states: Dict[str, DesiredUserState],
        dry_run: bool,
        reconcile_id: str,
        prefetch_complete: bool,
        precomputed_current_ids: Dict[str, Set[str]],
        provisioned_known: bool,
        provisioned: Set[str],
        log,
    ) -> tuple[int, int, int, Dict[str, SyncOutcome]]:
        """Run per-user convergence over all selected subjects."""
        users_synced = 0
        users_converged = 0
        requires_manual_action_count = 0
        per_user: Dict[str, SyncOutcome] = {}

        for email in sorted(all_subjects):
            user_run_id = reconcile_id
            user_log = logger.bind(
                user_email=email,
                platform=platform,
                run_id=user_run_id,
            )
            desired_state = desired_states.get(
                email,
                DesiredUserState(user_should_exist=False),
            )

            current_ids_for_user: Optional[Set[str]] = None
            if prefetch_complete:
                current_ids_for_user = precomputed_current_ids.get(email)

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

            result = self._converge_user(
                user_email=email,
                platform=platform,
                adapter=adapter,
                effective=effective,
                desired_state=desired_state,
                dry_run=dry_run,
                run_id=user_run_id,
                request_id=reconcile_id,
                log=user_log,
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
                    "sync_platform_user_failed",
                    user_email=email,
                    error_code=result.error_code,
                )

        return users_synced, users_converged, requires_manual_action_count, per_user

    # ------------------------------------------------------------------
    # Private: target resolution
    # ------------------------------------------------------------------

    def _resolve_target(
        self,
        platform: str,
    ) -> "tuple[Optional[PlatformPolicy], Optional[AccessSyncAdapter], Optional[OperationResult]]":
        """Look up policy and adapter for a platform key.

        Returns (policy, adapter, None) on success or (None, None, error) on failure.
        """
        policy = self._config.platforms.get(platform)
        if policy is None:
            return (
                None,
                None,
                OperationResult.error(
                    OperationStatus.NOT_FOUND,
                    message=f"No policy configured for platform: {platform}",
                    error_code="POLICY_NOT_FOUND",
                ),
            )

        adapter = self._adapters.get(platform)
        if adapter is None:
            return (
                None,
                None,
                OperationResult.error(
                    OperationStatus.NOT_FOUND,
                    message=f"No adapter registered for platform: {platform}",
                    error_code="ADAPTER_NOT_FOUND",
                ),
            )

        return policy, adapter, None

    # ------------------------------------------------------------------
    # Private: single-user plan + execute
    # ------------------------------------------------------------------

    def _converge_user(
        self,
        user_email: str,
        platform: str,
        adapter: AccessSyncAdapter,
        effective: EffectivePlatformPolicy,
        desired_state: DesiredUserState,
        dry_run: bool,
        run_id: str,
        request_id: str,
        log,
    ) -> OperationResult:
        """Plan and execute actions for one user against the platform.

        Shared path for both sync_user (live IDP check) and the per-user
        loop inside sync_platform (pre-fetched state reused, zero IDP calls).
        """
        current_ids: Set[str] = set()
        platform_user_exists = False

        if desired_state.current_entitlement_ids is not None:
            current_ids = {
                v for v in desired_state.current_entitlement_ids if isinstance(v, str)
            }
            if desired_state.platform_user_exists is not None:
                platform_user_exists = desired_state.platform_user_exists
            else:
                platform_user_exists = bool(current_ids)
            if not platform_user_exists:
                log.info("platform_user_absent")
        else:
            current_result = adapter.get_current_entitlement_ids(user_email)
            platform_user_exists = current_result.is_success
            if current_result.is_success and current_result.data is not None:
                if isinstance(current_result.data, set):
                    current_ids = {v for v in current_result.data if isinstance(v, str)}
            elif current_result.status == OperationStatus.NOT_FOUND:
                log.info("platform_user_absent")

        canonicalized = self._canonicalize_entitlements(
            adapter=adapter,
            effective=effective,
            desired_state=desired_state,
        )
        if not canonicalized.is_success or canonicalized.data is None:
            return canonicalized

        canon = canonicalized.data
        planned = self._engine.plan_actions(
            policy=canon.effective,
            capabilities=adapter.capabilities(),
            user_should_exist=desired_state.user_should_exist,
            required_entitlements=canon.required_entitlements,
            current_entitlement_ids=current_ids,
            platform_user_exists=platform_user_exists,
        )
        planned_actions = [str(a.action) for a in planned]
        log.info(
            "actions_planned",
            count=len(planned_actions),
            actions=planned_actions,
            platform_user_exists=platform_user_exists,
            current_entitlement_count=len(current_ids),
            user_should_exist=desired_state.user_should_exist,
        )

        if dry_run:
            log.info("dry_run_plan_ready", actions=planned_actions)
            return OperationResult.success(
                data=SyncOutcome(planned_actions=planned_actions, applied_actions=[])
            )

        applied: List[str] = []
        requires_manual_action = False
        for action in planned:
            result = self._execute_action(adapter, action, user_email)
            if result.is_success:
                applied.append(action.action)
            elif result.error_code == "UNSUPPORTED_OPERATION":
                requires_manual_action = True
                log.info("action_requires_manual_intervention", action=action.action)
            else:
                log.error("action_failed", action=action.action)
                self._persist(
                    run_id,
                    user_email,
                    platform,
                    applied,
                    "failed",
                    dry_run,
                    request_id,
                    error_message=result.message,
                )
                if self._dispatcher:
                    self._dispatcher.dispatch_background(
                        Event(
                            event_type=sync_events.SYNC_FAILED,
                            user_email=user_email,
                            metadata={
                                "platform": platform,
                                "error_code": result.error_code,
                            },
                        )
                    )
                return OperationResult.error(
                    result.status,
                    message=result.message,
                    error_code=result.error_code,
                )

        status = "manual_action_required" if requires_manual_action else "success"
        self._persist(
            run_id, user_email, platform, applied, status, dry_run, request_id
        )
        log.info("sync_user_completed", applied=len(applied), status=status)

        if self._dispatcher:
            self._dispatcher.dispatch_background(
                Event(
                    event_type=sync_events.SYNC_COMPLETED,
                    user_email=user_email,
                    metadata={
                        "platform": platform,
                        "applied": len(applied),
                        "dry_run": dry_run,
                    },
                )
            )
            if requires_manual_action:
                self._dispatcher.dispatch_background(
                    Event(
                        event_type=sync_events.MANUAL_ACTION_REQUIRED,
                        user_email=user_email,
                        metadata={"platform": platform},
                    )
                )

        return OperationResult.success(
            data=SyncOutcome(
                planned_actions=planned_actions,
                applied_actions=applied,
                requires_manual_action=requires_manual_action,
            )
        )

    # ------------------------------------------------------------------
    # Private: entitlement canonicalization
    # ------------------------------------------------------------------

    def _canonicalize_entitlements(
        self,
        adapter: AccessSyncAdapter,
        effective: EffectivePlatformPolicy,
        desired_state: DesiredUserState,
    ) -> "OperationResult[_Canon]":
        """Canonicalize entitlement IDs for stable planner comparisons.

        Only runs when the adapter implements EntitlementCanonicalizingAdapter.
        Returns the effective policy and required entitlements with canonical IDs.
        """
        if not isinstance(adapter, EntitlementCanonicalizingAdapter):
            return OperationResult.success(
                data=_Canon(
                    effective=effective,
                    required_entitlements=desired_state.required_entitlements,
                )
            )

        rule_by_key: dict = {}
        for rule in effective.entitlement_rules:
            result = adapter.canonicalize_entitlement_id(
                entitlement_type=rule.entitlement_type,
                entitlement_id=rule.entitlement_id,
            )
            if not result.is_success or not isinstance(result.data, str):
                return OperationResult.error(
                    result.status,
                    message=result.message,
                    error_code=result.error_code,
                )
            rule_by_key[
                (rule.group_slug, rule.entitlement_type, rule.entitlement_id)
            ] = EntitlementRule(
                group_slug=rule.group_slug,
                entitlement_type=rule.entitlement_type,
                entitlement_id=result.data,
                mode=rule.mode,
            )

        canonical_required: List[EntitlementRule] = []
        for rule in desired_state.required_entitlements:
            canonical = rule_by_key.get(
                (rule.group_slug, rule.entitlement_type, rule.entitlement_id)
            )
            if canonical is None:
                result = adapter.canonicalize_entitlement_id(
                    entitlement_type=rule.entitlement_type,
                    entitlement_id=rule.entitlement_id,
                )
                if not result.is_success or not isinstance(result.data, str):
                    return OperationResult.error(
                        result.status,
                        message=result.message,
                        error_code=result.error_code,
                    )
                canonical = EntitlementRule(
                    group_slug=rule.group_slug,
                    entitlement_type=rule.entitlement_type,
                    entitlement_id=result.data,
                    mode=rule.mode,
                )
            canonical_required.append(canonical)

        return OperationResult.success(
            data=_Canon(
                effective=replace(
                    effective, entitlement_rules=list(rule_by_key.values())
                ),
                required_entitlements=canonical_required,
            )
        )

    # ------------------------------------------------------------------
    # Private: action dispatch
    # ------------------------------------------------------------------

    def _execute_action(
        self,
        adapter: AccessSyncAdapter,
        action: PlannedAction,
        user_email: str,
    ) -> OperationResult:
        """Dispatch a single planned action to the adapter."""
        if action.action == "provision_user":
            return adapter.ensure_user(user_email)
        if action.action == "disable_user":
            return adapter.disable_user(user_email)
        if action.action == "remove_user":
            return adapter.remove_user(user_email)
        if action.action == "apply_entitlement":
            if action.entitlement_type is None or action.entitlement_id is None:
                return OperationResult.error(
                    OperationStatus.PERMANENT_ERROR,
                    message="Missing entitlement metadata for apply_entitlement",
                    error_code="INVALID_PLANNED_ACTION",
                )
            return adapter.apply_entitlement(
                user_email, action.entitlement_type, action.entitlement_id
            )
        if action.action == "remove_entitlement":
            if action.entitlement_type is None or action.entitlement_id is None:
                return OperationResult.error(
                    OperationStatus.PERMANENT_ERROR,
                    message="Missing entitlement metadata for remove_entitlement",
                    error_code="INVALID_PLANNED_ACTION",
                )
            return adapter.remove_entitlement(
                user_email, action.entitlement_type, action.entitlement_id
            )
        return OperationResult.error(
            OperationStatus.PERMANENT_ERROR,
            message=f"Unknown action: {action.action}",
            error_code="UNKNOWN_ACTION",
        )

    # ------------------------------------------------------------------
    # Private: platform entitlement prefetch
    # ------------------------------------------------------------------

    def _prefetch_current_entitlements(
        self,
        effective: EffectivePlatformPolicy,
        adapter: AccessSyncAdapter,
    ) -> OperationResult:
        """Build email → current entitlement IDs from platform group memberships.

        Avoids per-user platform membership lookups during batch reconciliation
        by reading at the group level and inverting the result.
        """
        managed_group_ids: Set[str] = {
            rule.entitlement_id
            for rule in effective.sync_managed_rules()
            if rule.entitlement_type == "group"
        }
        if not managed_group_ids:
            return OperationResult.success(data={})

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

        # Generic fallback: one call per group.
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
        """Convert group → members mapping into email → entitlement IDs."""
        by_user: Dict[str, Set[str]] = {}
        for group_id, members in group_to_members.items():
            if not isinstance(group_id, str):
                continue
            if not isinstance(members, (set, list, tuple)):
                continue
            for email in members:
                if not isinstance(email, str):
                    continue
                normalized = email.lower()
                if normalized not in by_user:
                    by_user[normalized] = set()
                by_user[normalized].add(group_id)
        return OperationResult.success(data=by_user)

    # ------------------------------------------------------------------
    # Private: audit persistence
    # ------------------------------------------------------------------

    def _persist(
        self,
        run_id: str,
        user_email: str,
        platform: str,
        applied: List[str],
        status: str,
        dry_run: bool,
        request_id: str,
        error_message: Optional[str] = None,
    ) -> None:
        """Persist run record if repository is available. Failures are non-fatal."""
        if self._repository is None:
            return
        self._repository.save(
            SyncRunRecord(
                run_id=run_id,
                user_email=user_email,
                platform=platform,
                actions_applied=applied,
                status=status,  # type: ignore[arg-type]
                dry_run=dry_run,
                request_id=request_id or None,
                error_message=error_message,
            )
        )


class _Canon:
    """Internal carrier for canonicalized entitlement data."""

    def __init__(
        self,
        effective: EffectivePlatformPolicy,
        required_entitlements: List[EntitlementRule],
    ) -> None:
        self.effective = effective
        self.required_entitlements = required_entitlements
