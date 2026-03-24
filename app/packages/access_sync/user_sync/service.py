"""Access Sync user sync service.

On-demand, single-user convergence: resolves per-user desired state via
IDP group memberships, plans actions via PolicyEngine, and dispatches to
platform adapters. Delegates persistence to SyncRunRepository.
Returns standardized OperationResult[SyncOutcome] for all boundaries.

sync_user_from_context() accepts pre-fetched DesiredUserState from
PlatformSyncService to keep batch platform sync at O(groups) IDP calls total.
"""

import uuid
from typing import List, Mapping, Optional, Set, TYPE_CHECKING

import structlog

from infrastructure.events import Event, EventDispatcher
from infrastructure.operations import OperationResult, OperationStatus
from packages.access_sync import events as sync_events
from packages.access_sync.adapters import AccessSyncAdapter
from packages.access_sync.membership import DirectoryMembershipBuilder
from packages.access_sync.models import DesiredUserState, SyncOutcome, SyncRunRecord
from packages.access_sync.policies import (
    PlannedAction,
    PlatformPolicy,
    PolicyEngine,
)
from packages.access_sync.runtime import resolve_platform_context

if TYPE_CHECKING:
    from infrastructure.directory.provider import DirectoryProvider
    from packages.access_sync.store import SyncRunRepository

logger = structlog.get_logger()


class UserSyncService:
    """On-demand single-user access sync.

    Computes per-user desired state via IDP group memberships, plans actions
    via PolicyEngine, and dispatches to platform adapters. All cross-cutting

    Args:
        adapters: Platform adapter mapping.
        policies: Platform policy definitions.
        directory: IDP-agnostic directory provider (group/membership lookups).
        repository: Optional run record repository for audit persistence.
        dispatcher: Optional event dispatcher for domain event emission.
    """

    def __init__(
        self,
        adapters: Mapping[str, AccessSyncAdapter],
        policies: Mapping[str, PlatformPolicy],
        directory: "DirectoryProvider",
        repository: "Optional[SyncRunRepository]" = None,
        dispatcher: Optional[EventDispatcher] = None,
    ) -> None:
        self._adapters = adapters
        self._policies = policies
        self._repository = repository
        self._dispatcher = dispatcher
        self._engine = PolicyEngine()
        self._membership_builder = DirectoryMembershipBuilder(directory)

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
        """Converge user access on platform to match IDP policy.

        Checks per-user membership in each entitlement group, not just
        the authn group. Passes current platform entitlement IDs to PolicyEngine
        so it can compute additions and removals (delta sync).

        Returns:
            OperationResult[SyncOutcome] on success.
            OperationResult.error on infrastructure or policy failures.
        """
        run_id = request_id or str(uuid.uuid4())
        log = logger.bind(user_email=user_email, platform=platform, run_id=run_id)
        log.info("sync_started", dry_run=dry_run)

        resolved_result = resolve_platform_context(
            platform=platform,
            policies=self._policies,
            adapters=self._adapters,
        )
        if not resolved_result.is_success or resolved_result.data is None:
            return resolved_result

        desired_state_result = self._membership_builder.build_user_state(
            user_email=user_email,
            policy=resolved_result.data.policy,
        )
        if not desired_state_result.is_success or desired_state_result.data is None:
            return desired_state_result

        return self._execute_sync(
            user_email=user_email,
            platform=platform,
            adapter=resolved_result.data.adapter,
            policy=resolved_result.data.policy,
            desired_state=desired_state_result.data,
            dry_run=dry_run,
            run_id=run_id,
            request_id=request_id,
            log=log,
        )

    def sync_user_from_context(
        self,
        user_email: str,
        platform: str,
        desired_state: DesiredUserState,
        dry_run: bool = False,
        request_id: str = "",
    ) -> OperationResult:
        """Converge a user using pre-fetched IDP membership — no directory calls.

        Called by PlatformSyncService during batch platform sync. The caller
        already holds the full group membership map built in O(groups) IDP calls
        for the entire run; passing it here bypasses all per-user IDP lookups,
        keeping the platform sync at O(groups) total regardless of user count.

        Args:
            user_email: Target user.
            platform: Target platform key.
            desired_state: Pre-fetched desired state from PlatformSyncService.
            dry_run: If True, plan but do not execute.
            request_id: Correlation ID from the parent platform sync run.

        Returns:
            OperationResult[SyncOutcome] — same contract as sync_user.
        """
        run_id = request_id or str(uuid.uuid4())
        log = logger.bind(user_email=user_email, platform=platform, run_id=run_id)
        log.info("sync_started_from_context", dry_run=dry_run)

        resolved_result = resolve_platform_context(
            platform=platform,
            policies=self._policies,
            adapters=self._adapters,
        )
        if not resolved_result.is_success or resolved_result.data is None:
            return resolved_result

        return self._execute_sync(
            user_email=user_email,
            platform=platform,
            adapter=resolved_result.data.adapter,
            policy=resolved_result.data.policy,
            desired_state=desired_state,
            dry_run=dry_run,
            run_id=run_id,
            request_id=request_id,
            log=log,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _execute_sync(
        self,
        user_email: str,
        platform: str,
        adapter: AccessSyncAdapter,
        policy: PlatformPolicy,
        desired_state: DesiredUserState,
        dry_run: bool,
        run_id: str,
        request_id: str,
        log,
    ) -> OperationResult:
        """Shared plan-and-execute path for both sync_user and sync_user_from_context."""
        # Current platform state for delta planning.
        current_ids: Set[str] = set()
        platform_user_exists = False

        if desired_state.current_entitlement_ids is not None:
            current_ids = {
                value
                for value in desired_state.current_entitlement_ids
                if isinstance(value, str)
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
                    current_ids = {
                        value for value in current_result.data if isinstance(value, str)
                    }
            elif current_result.status == OperationStatus.NOT_FOUND:
                log.info("platform_user_absent")

        planned = self._engine.plan_actions(
            policy=policy,
            capabilities=adapter.capabilities(),
            user_should_exist=desired_state.user_should_exist,
            required_entitlements=desired_state.required_entitlements,
            current_entitlement_ids=current_ids,
        )
        planned_actions = [str(planned_action.action) for planned_action in planned]
        log.info(
            "actions_planned",
            count=len(planned_actions),
            actions=planned_actions,
            platform_user_exists=platform_user_exists,
            current_entitlement_count=len(current_ids),
            user_should_exist=desired_state.user_should_exist,
        )

        if dry_run:
            log.info(
                "dry_run_plan_ready",
                actions=planned_actions,
                platform_user_exists=platform_user_exists,
            )
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
        log.info("sync_completed", applied=len(applied), status=status)
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

    def _execute_action(
        self,
        adapter: AccessSyncAdapter,
        action: PlannedAction,
        user_email: str,
    ) -> OperationResult:
        """Dispatch a single planned action to the adapter."""
        if action.action == "ensure_user":
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
