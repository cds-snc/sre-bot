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

Internal collaborators (each with a single responsibility):
- ``TargetResolver``              — look up policy + adapter by platform key.
- ``PlatformPrefetchPlanner``     — orphan detection + entitlement prefetch.
- ``OptimizationStrategy``        — select which subjects to process this run.
- ``PlatformReconciliationExecutor`` — per-user converge loop and single-user
                                       plan/execute/persist pipeline.
"""

import uuid
from dataclasses import replace
from typing import (
    Any,
    Dict,
    List,
    Mapping,
    Optional,
    Protocol,
    Set,
    Tuple,
    TYPE_CHECKING,
)

import structlog

from infrastructure.events import Event, EventDispatcher
from infrastructure.operations import OperationResult, OperationStatus
from packages.access.common.config import AccessRuntimeConfig, PlatformPolicy
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
    AdapterCapabilities,
    EffectivePlatformPolicy,
    EntitlementRule,
    PlannedAction,
    PolicyEngine,
    resolve_effective_policy,
)

if TYPE_CHECKING:
    from packages.access.sync.store import SyncRunRepository

logger = structlog.get_logger()


# ---------------------------------------------------------------------------
# Public protocol (transport and test contract)
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# TargetResolver — resolve platform key → (policy, adapter)
# ---------------------------------------------------------------------------


class TargetResolver:
    """Resolves a platform key to its policy and adapter.

    Encapsulates the NOT_FOUND / ADAPTER_NOT_FOUND error paths so the
    coordinator body stays focused on orchestration flow.
    """

    def __init__(
        self,
        adapters: Mapping[str, AccessSyncAdapter],
        config: AccessRuntimeConfig,
    ) -> None:
        self._adapters = adapters
        self._config = config

    def resolve(
        self,
        platform: str,
    ) -> Tuple[
        Optional[PlatformPolicy], Optional[AccessSyncAdapter], Optional[OperationResult]
    ]:
        """Return (policy, adapter, None) on success or (None, None, error) on failure."""
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


# ---------------------------------------------------------------------------
# PlatformPrefetchPlanner — orphan detection + entitlement prefetch
# ---------------------------------------------------------------------------


class PlatformPrefetchPlanner:
    """Performs the two read-heavy phases of platform sync.

    Phase 2: Orphan detection — enumerate all provisioned users and find those
             absent from the IDP.
    Phase 3: Current entitlement prefetch — invert platform group membership
             into a per-user entitlement-ID map so the per-user loop needs
             zero additional platform reads.
    """

    def detect_orphans(
        self,
        adapter: AccessSyncAdapter,
        idp_members: Set[str],
        log: Any,
    ) -> Tuple[Set[str], bool, Set[str]]:
        """Return (provisioned, provisioned_known, orphans)."""
        provisioned: Set[str] = set()
        provisioned_known = False
        orphans: Set[str] = set()

        provisioned_result = adapter.list_all_provisioned_users()
        if provisioned_result.is_success and provisioned_result.data is not None:
            provisioned = provisioned_result.data
            provisioned_known = True
            orphans = provisioned - idp_members
            log.info(
                "orphans_detected",
                count=len(orphans),
                orphan_emails=sorted(orphans),
                provisioned_count=len(provisioned),
            )
        else:
            log.warning("orphan_detection_skipped", error=provisioned_result.message)

        return provisioned, provisioned_known, orphans

    def prefetch_current_ids(
        self,
        effective: EffectivePlatformPolicy,
        adapter: AccessSyncAdapter,
        log: Any,
    ) -> Tuple[Dict[str, Set[str]], bool]:
        """Return (email_to_entitlement_ids, prefetch_complete)."""
        prefetch_result = self._fetch_current_entitlements(effective, adapter)
        if prefetch_result.is_success and isinstance(prefetch_result.data, dict):
            precomputed: Dict[str, Set[str]] = prefetch_result.data
            log.info("prefetched_current_entitlements", users=len(precomputed))
            return precomputed, True

        log.warning(
            "prefetch_current_entitlements_skipped",
            error=prefetch_result.message,
        )
        return {}, False

    def _fetch_current_entitlements(
        self,
        effective: EffectivePlatformPolicy,
        adapter: AccessSyncAdapter,
    ) -> OperationResult:
        """Build email → current entitlement IDs from platform group memberships."""
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


# ---------------------------------------------------------------------------
# OptimizationStrategy — subject selection policy
# ---------------------------------------------------------------------------


class OptimizationStrategy:
    """Encapsulates the platform sync subject selection logic.

    Determines which users are candidates for convergence this run.  The
    lifecycle-delta optimization path skips users already in sync when the
    adapter supports bulk-user-delta and there are no sync-managed entitlement
    rules — reducing the processing set to only deltas (new IDP members and
    orphans).
    """

    def select_subjects(
        self,
        idp_members: Set[str],
        orphans: Set[str],
        precomputed_current_ids: Dict[str, Set[str]],
        provisioned: Set[str],
        provisioned_known: bool,
        has_sync_managed: bool,
        capabilities: AdapterCapabilities,
        log: Any,
    ) -> Tuple[Set[str], Set[str], bool]:
        """Return (candidate_subjects, subjects_to_process, lifecycle_delta_optimized)."""
        candidate_subjects: Set[str] = (
            idp_members | orphans | set(precomputed_current_ids)
        )
        lifecycle_delta_optimized = False

        if (
            not has_sync_managed
            and provisioned_known
            and capabilities.supports_bulk_user_delta
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


# ---------------------------------------------------------------------------
# Internal carrier for canonicalized entitlement data
# ---------------------------------------------------------------------------


class _Canon:
    def __init__(
        self,
        effective: EffectivePlatformPolicy,
        required_entitlements: List[EntitlementRule],
    ) -> None:
        self.effective = effective
        self.required_entitlements = required_entitlements


# ---------------------------------------------------------------------------
# PlatformReconciliationExecutor — per-user converge pipeline
# ---------------------------------------------------------------------------


class PlatformReconciliationExecutor:
    """Runs the per-user convergence pipeline for both sync_user and sync_platform.

    Owns:
    - ``execute()``        — the platform-wide loop over all selected subjects.
    - ``converge_user()``  — plan + execute actions for one user (shared path).
    - ``_canonicalize_entitlements()`` — optional adapter-specific ID translation.
    - ``_execute_action()``            — dispatch a single action to the adapter.
    - ``_persist()``                   — write audit record (non-fatal on failure).
    """

    def __init__(
        self,
        engine: PolicyEngine,
        repository: "Optional[SyncRunRepository]",
        dispatcher: Optional[EventDispatcher],
    ) -> None:
        self._engine = engine
        self._repository = repository
        self._dispatcher = dispatcher

    def execute(
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
        log: Any,
        emit_per_user_plan_logs: bool = True,
    ) -> Tuple[int, int, int, Dict[str, SyncOutcome]]:
        """Run per-user convergence over all selected subjects.

        Returns (users_synced, users_converged, requires_manual_action_count, per_user).
        """
        users_synced = 0
        users_converged = 0
        requires_manual_action_count = 0
        per_user: Dict[str, SyncOutcome] = {}

        for email in sorted(all_subjects):
            user_log = logger.bind(
                user_email=email,
                platform=platform,
                run_id=reconcile_id,
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

            result = self.converge_user(
                user_email=email,
                platform=platform,
                adapter=adapter,
                effective=effective,
                desired_state=desired_state,
                dry_run=dry_run,
                run_id=reconcile_id,
                request_id=reconcile_id,
                log=user_log,
                emit_plan_logs=emit_per_user_plan_logs,
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

    def converge_user(
        self,
        user_email: str,
        platform: str,
        adapter: AccessSyncAdapter,
        effective: EffectivePlatformPolicy,
        desired_state: DesiredUserState,
        dry_run: bool,
        run_id: str,
        request_id: str,
        log: Any,
        emit_plan_logs: bool = True,
    ) -> OperationResult:
        """Plan and execute actions for one user against the platform.

        Shared path for both sync_user (live IDP check) and the per-user
        loop inside sync_platform (pre-fetched state reused, zero IDP calls).
        """
        assessment_result = adapter.assess(user_email, desired_state)
        if not assessment_result.is_success or assessment_result.data is None:
            log.error(
                "adapter_assess_failed",
                error_code=assessment_result.error_code,
                error=assessment_result.message,
            )
            return assessment_result
        assessment = assessment_result.data

        if not assessment.platform_user_exists and emit_plan_logs:
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
            current_entitlement_ids=assessment.current_entitlement_ids,
            platform_user_exists=assessment.platform_user_exists,
        )
        planned_actions = [str(a.action) for a in planned]
        should_log_plans = self._should_log_plans(
            planned_actions=planned_actions,
            emit_plan_logs=emit_plan_logs,
        )
        if should_log_plans:
            log.info(
                "actions_planned",
                count=len(planned_actions),
                actions=planned_actions,
                platform_user_exists=assessment.platform_user_exists,
                current_entitlement_count=len(assessment.current_entitlement_ids),
                user_should_exist=desired_state.user_should_exist,
            )

        if dry_run:
            if should_log_plans:
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
                                "request_id": request_id,
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
                        "request_id": request_id,
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

    def _canonicalize_entitlements(
        self,
        adapter: AccessSyncAdapter,
        effective: EffectivePlatformPolicy,
        desired_state: DesiredUserState,
    ) -> "OperationResult[_Canon]":
        """Canonicalize entitlement IDs for stable planner comparisons.

        Only runs when the adapter implements EntitlementCanonicalizingAdapter.
        Returns the effective policy and required entitlements with canonical IDs.

        Entitlement rules that the platform cannot resolve (GROUP_ID_NOT_FOUND,
        AMBIGUOUS_GROUP_NAME) are skipped with a warning so that config drift on
        one group does not block the entire user sync.  All other errors are
        still treated as hard failures.
        """
        _SKIP_CODES = frozenset({"GROUP_ID_NOT_FOUND", "AMBIGUOUS_GROUP_NAME"})

        if not isinstance(adapter, EntitlementCanonicalizingAdapter):
            return OperationResult.success(
                data=_Canon(
                    effective=effective,
                    required_entitlements=desired_state.required_entitlements,
                )
            )

        log = logger.bind(platform=effective.platform)

        rule_by_key: dict = {}
        for rule in effective.entitlement_rules:
            result = adapter.canonicalize_entitlement_id(
                entitlement_type=rule.entitlement_type,
                entitlement_id=rule.entitlement_id,
            )
            if not result.is_success or not isinstance(result.data, str):
                if result.error_code in _SKIP_CODES:
                    log.error(
                        "canonicalize_entitlement_skipped",
                        entitlement_id=rule.entitlement_id,
                        group_slug=rule.group_slug,
                        error_code=result.error_code,
                        reason=result.message,
                    )
                    continue
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
                    if result.error_code in _SKIP_CODES:
                        log.error(
                            "canonicalize_required_entitlement_skipped",
                            entitlement_id=rule.entitlement_id,
                            group_slug=rule.group_slug,
                            error_code=result.error_code,
                            reason=result.message,
                        )
                        continue
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

    @staticmethod
    def _should_log_plans(
        planned_actions: List[str],
        emit_plan_logs: bool,
    ) -> bool:
        """Keep platform sync logs focused while preserving removal visibility."""
        if emit_plan_logs:
            return True
        return any(
            action in {"remove_user", "disable_user"} for action in planned_actions
        )

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


# ---------------------------------------------------------------------------
# AccessSyncCoordinator — thin orchestrator
# ---------------------------------------------------------------------------


class AccessSyncCoordinator:
    """Orchestrates the full access sync lifecycle.

    Wires ``PolicyEngine``, ``DirectoryMembershipBuilder``, and the platform
    adapter together via explicit collaborators.  Each collaborator has a
    single responsibility so the coordinator body is limited to sequencing.

    All business logic stays in ``policies.py``; all IDP reads stay in
    ``desired_state.py``; all platform mutations stay in the adapter.

    Constructed once per process by ``providers.get_access_sync_coordinator``
    and injected into HTTP route handlers via FastAPI ``Depends``.
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
        self._target_resolver = TargetResolver(adapters, config)
        self._prefetch_planner = PlatformPrefetchPlanner()
        self._optimization_strategy = OptimizationStrategy()
        engine = PolicyEngine()
        self._reconciler = PlatformReconciliationExecutor(
            engine, repository, dispatcher
        )
        self._dispatcher = dispatcher

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

        _policy, adapter, error = self._target_resolver.resolve(platform)
        if error is not None:
            return error
        if adapter is None:
            return OperationResult.error(
                OperationStatus.PERMANENT_ERROR,
                message=f"No adapter resolved for platform '{platform}'.",
                error_code="PLATFORM_NOT_CONFIGURED",
            )

        discovered = self._membership_builder.discover_group_slugs(
            self._config, platform
        )
        effective = resolve_effective_policy(self._config, platform, discovered)

        desired_result = self._membership_builder.build_user_state_from_effective(
            user_email=user_email,
            effective=effective,
        )
        log.info(
            "build_user_state_completed",
            user_email=user_email,
            platform=platform,
            result_status=desired_result.status,
            has_desired_state=desired_result.data is not None,
        )
        if not desired_result.is_success or desired_result.data is None:
            return desired_result

        return self._reconciler.converge_user(
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

        _policy, adapter, error = self._target_resolver.resolve(platform)
        if error is not None:
            return error
        if adapter is None:
            return OperationResult.error(
                OperationStatus.PERMANENT_ERROR,
                message=f"No adapter resolved for platform '{platform}'.",
                error_code="PLATFORM_NOT_CONFIGURED",
            )

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
        desired_states: Dict[str, DesiredUserState] = desired_result.data
        idp_members: Set[str] = set(desired_states.keys())

        # Phase 2: orphan detection.
        provisioned, provisioned_known, orphans = self._prefetch_planner.detect_orphans(
            adapter=adapter,
            idp_members=idp_members,
            log=log,
        )

        # Phase 3: current entitlement prefetch for delta planning.
        precomputed_current_ids, prefetch_complete = (
            self._prefetch_planner.prefetch_current_ids(
                effective=effective,
                adapter=adapter,
                log=log,
            )
        )
        has_sync_managed = bool(effective.sync_managed_rules())

        # Select which subjects to process.
        candidate_subjects, all_subjects, lifecycle_delta_optimized = (
            self._optimization_strategy.select_subjects(
                idp_members=idp_members,
                orphans=orphans,
                precomputed_current_ids=precomputed_current_ids,
                provisioned=provisioned,
                provisioned_known=provisioned_known,
                has_sync_managed=has_sync_managed,
                capabilities=adapter_capabilities,
                log=log,
            )
        )

        # Phase 4: per-user convergence — zero additional IDP calls.
        users_synced, users_converged, requires_manual_action_count, per_user = (
            self._reconciler.execute(
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
                emit_per_user_plan_logs=False,
            )
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

        actions_breakdown: Dict[str, int] = {}
        remove_user_targets: List[str] = []
        for outcome in per_user.values():
            for action in outcome.planned_actions:
                actions_breakdown[action] = actions_breakdown.get(action, 0) + 1
        for email, outcome in per_user.items():
            if "remove_user" in outcome.planned_actions:
                remove_user_targets.append(email)
        planned_actions_total = sum(actions_breakdown.values())

        log.info(
            "sync_platform_completed",
            users_synced=users_synced,
            users_converged=users_converged,
            orphans_found=len(orphans),
            requires_manual_action=requires_manual_action_count,
            planned_actions_total=planned_actions_total,
            planned_actions_breakdown=actions_breakdown,
            remove_user_targets=sorted(remove_user_targets),
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
