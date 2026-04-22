"""Access Sync application service — public orchestration entrypoint.

This is the canonical place to understand the full sync business flow.
Transport layers (HTTP routes, Slack commands) and tests depend on
``AccessSyncCoordinatorPort``; the concrete ``AccessSyncCoordinator`` is
constructed once per process by ``providers.py``.

Sync flow for a single user:
  1. Resolve adapter and platform policy.
  2. Discover IDP group slugs; resolve run-scoped effective policy.
  3. Build desired state from IDP membership (no adapter calls).
  4. Ask adapter to assess current platform state (``adapter.assess()``).
  5. Plan actions via ``PolicyEngine`` (pure, side-effect-free).
  6. Execute actions via adapter, or return plan for dry-run.
  7. Persist audit record and emit domain events.

For platform sync an additional batch prefetch phase (steps 2–4 above in
bulk) precedes the per-user loop so the full reconciliation runs in O(groups)
IDP calls and O(1) adapter reads per user.
"""

import uuid
from typing import Dict, List, Mapping, Optional, Protocol, Set, TYPE_CHECKING

import structlog

from infrastructure.events import Event, EventDispatcher
from infrastructure.operations import OperationResult
from packages.access.common.config import AccessRuntimeConfig
from packages.access.sync import events as sync_events
from packages.access.sync.adapters import AccessSyncAdapter
from packages.access.sync.desired_state import DirectoryMembershipBuilder
from packages.access.sync.domain import DesiredUserState, ReconciliationOutcome
from packages.access.sync.policies import PolicyEngine, resolve_effective_policy
from packages.access.sync.reconciliation import (
    OptimizationStrategy,
    PlatformPrefetchPlanner,
    PlatformReconciliationExecutor,
    TargetResolver,
)

if TYPE_CHECKING:
    from packages.access.sync.store import SyncRunRepository

logger = structlog.get_logger()


# ---------------------------------------------------------------------------
# Public protocol — transport and test contract
# ---------------------------------------------------------------------------


class AccessSyncCoordinatorPort(Protocol):
    """Structural contract for the access sync coordinator.

    Transport handlers and test stubs depend on this Protocol rather than the
    concrete class, keeping them decoupled from implementation details.
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
# AccessSyncCoordinator — thin orchestrator
# ---------------------------------------------------------------------------


class AccessSyncCoordinator:
    """Orchestrates the full access sync lifecycle.

    Wires ``PolicyEngine``, ``DirectoryMembershipBuilder``, and the platform
    adapter together via explicit collaborators.  Each collaborator has a
    single responsibility; the coordinator body is limited to sequencing.

    All business logic stays in ``policies.py``; all IDP reads in
    ``desired_state.py``; all platform assessment and mutations in adapters;
    all reconciliation looping in ``reconciliation.py``.

    Constructed once per process by ``providers.get_access_sync_coordinator``
    and injected into route handlers via FastAPI ``Depends``.
    """

    def __init__(
        self,
        adapters: Mapping[str, AccessSyncAdapter],
        config: AccessRuntimeConfig,
        membership_builder: DirectoryMembershipBuilder,
        repository: "Optional[SyncRunRepository]" = None,
        dispatcher: Optional[EventDispatcher] = None,
    ) -> None:
        self._membership_builder = membership_builder
        self._config = config
        self._target_resolver = TargetResolver(adapters, config)
        self._prefetch_planner = PlatformPrefetchPlanner()
        self._optimization_strategy = OptimizationStrategy()
        self._reconciler = PlatformReconciliationExecutor(
            PolicyEngine(), repository, dispatcher
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

        Performs a live IDP membership check for the user, then plans and
        executes the required actions via the adapter.

        Returns:
            ``OperationResult[SyncOutcome]`` on success.
            ``OperationResult.error`` on infrastructure or policy failures.
        """
        run_id = request_id or str(uuid.uuid4())
        log = logger.bind(user_email=user_email, platform=platform, run_id=run_id)
        log.info("sync_user_started", dry_run=dry_run)

        _policy, adapter, error = self._target_resolver.resolve(platform)
        if error is not None:
            return error

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

        return self._reconciler.converge_user(
            user_email=user_email,
            platform=platform,
            adapter=adapter,  # type: ignore[arg-type]
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

        Phase 1: Batch IDP reads — one call per policy group (O(groups)).
        Phase 2: Orphan detection — list all provisioned users on the platform.
        Phase 3: Entitlement prefetch — invert group membership per user.
        Phase 4: Per-user convergence — zero additional IDP calls per user.

        Returns:
            ``OperationResult[ReconciliationOutcome]`` on completion (even partial).
            ``OperationResult.error`` if policy or adapter cannot be resolved.
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

        discovered = self._membership_builder.discover_group_slugs(
            self._config, platform
        )
        effective = resolve_effective_policy(self._config, platform, discovered)
        adapter_capabilities = adapter.capabilities()  # type: ignore[union-attr]

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
            adapter=adapter,  # type: ignore[arg-type]
            idp_members=idp_members,
            log=log,
        )

        # Phase 3: entitlement prefetch for delta planning.
        precomputed_current_ids, prefetch_complete = (
            self._prefetch_planner.prefetch_current_ids(
                effective=effective,
                adapter=adapter,  # type: ignore[arg-type]
                log=log,
            )
        )

        # Select subjects to process this run.
        candidate_subjects, all_subjects, lifecycle_delta_optimized = (
            self._optimization_strategy.select_subjects(
                idp_members=idp_members,
                orphans=orphans,
                precomputed_current_ids=precomputed_current_ids,
                provisioned=provisioned,
                provisioned_known=provisioned_known,
                has_sync_managed=bool(effective.sync_managed_rules()),
                capabilities=adapter_capabilities,
                log=log,
            )
        )

        # Phase 4: per-user convergence — zero additional IDP calls.
        users_synced, users_converged, requires_manual_action_count, per_user = (
            self._reconciler.execute(
                all_subjects=all_subjects,
                platform=platform,
                adapter=adapter,  # type: ignore[arg-type]
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

        actions_breakdown: Dict[str, int] = {}
        remove_user_targets: List[str] = []
        for outcome in per_user.values():
            for action in outcome.planned_actions:
                actions_breakdown[action] = actions_breakdown.get(action, 0) + 1
        for email, outcome in per_user.items():
            if "remove_user" in outcome.planned_actions:
                remove_user_targets.append(email)

        log.info(
            "sync_platform_completed",
            users_synced=users_synced,
            users_converged=users_converged,
            orphans_found=len(orphans),
            requires_manual_action=requires_manual_action_count,
            planned_actions_total=sum(actions_breakdown.values()),
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
                        "requires_manual_action_count": (requires_manual_action_count),
                        "dry_run": dry_run,
                        "subjects_total": len(candidate_subjects),
                        "subjects_processed": len(all_subjects),
                        "lifecycle_delta_optimized": lifecycle_delta_optimized,
                    },
                )
            )

        return OperationResult.success(
            data=ReconciliationOutcome(
                platform=platform,
                users_synced=users_synced,
                users_converged=users_converged,
                orphans_found=len(orphans),
                requires_manual_action_count=requires_manual_action_count,
                dry_run=dry_run,
                per_user=per_user,
            )
        )
