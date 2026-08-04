"""Access Sync application service — thin orchestrator.

Responsibilities:
  1. Resolve adapter and effective policy.
  2. Derive desired state from the IDP.
  3. Delegate to adapter.reconcile_user() or adapter.reconcile_platform().
  4. Persist audit record and emit domain events.

All platform state assessment, planning, and execution is owned by adapters.
"""

import uuid
from collections.abc import Mapping
from typing import TYPE_CHECKING, Protocol

import structlog

from infrastructure.events import Event, EventDispatcher
from infrastructure.operations import OperationResult, OperationStatus
from packages.access.common.config import AccessRuntimeConfig
from packages.access.sync import events as sync_events
from packages.access.sync.adapters import AccessSyncAdapter
from packages.access.sync.desired_state import DirectoryMembershipBuilder
from packages.access.sync.domain import SyncOutcome, SyncRunRecord
from packages.access.sync.policies import (
    EffectivePlatformPolicy,
    PlanningContext,
    resolve_effective_policy,
)

if TYPE_CHECKING:
    from packages.access.sync.store import SyncRunRepository

logger = structlog.get_logger()


# ---------------------------------------------------------------------------
# Public protocol
# ---------------------------------------------------------------------------


class AccessSyncApplicationServicePort(Protocol):
    """Structural contract for the access sync application service."""

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
# AccessSyncApplicationService
# ---------------------------------------------------------------------------


class AccessSyncApplicationService:
    """Thin orchestrator: IDP → adapter.reconcile_*() → persist/emit."""

    def __init__(
        self,
        adapters: Mapping[str, AccessSyncAdapter],
        config: AccessRuntimeConfig,
        membership_builder: DirectoryMembershipBuilder,
        repository: SyncRunRepository | None = None,
        dispatcher: EventDispatcher | None = None,
    ) -> None:
        self._adapters = adapters
        self._config = config
        self._membership_builder = membership_builder
        self._repository = repository
        self._dispatcher = dispatcher

    def _resolve(
        self, platform: str
    ) -> tuple[
        AccessSyncAdapter | None,
        EffectivePlatformPolicy | None,
        OperationResult | None,
    ]:
        """Return (adapter, effective_policy, None) or (None, None, error)."""
        if platform not in self._config.platforms:
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
        discovered = self._membership_builder.discover_group_slugs(self._config, platform)
        effective = resolve_effective_policy(self._config, platform, discovered)
        return adapter, effective, None

    def _persist(
        self,
        run_id: str,
        user_email: str,
        platform: str,
        outcome: SyncOutcome,
        dry_run: bool,
        request_id: str,
    ) -> None:
        if self._repository is None:
            return
        status = "manual_action_required" if outcome.requires_manual_action else "success"
        self._repository.save(
            SyncRunRecord(
                run_id=run_id,
                user_email=user_email,
                platform=platform,
                actions_applied=outcome.applied_actions,
                status=status,  # type: ignore[arg-type]
                dry_run=dry_run,
                request_id=request_id or None,
            )
        )

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
        run_id = request_id or str(uuid.uuid4())
        log = logger.bind(user_email=user_email, platform=platform, run_id=run_id)
        log.info("sync_user_started", dry_run=dry_run)

        adapter, effective, error = self._resolve(platform)
        if error is not None:
            return error
        assert adapter is not None  # noqa: S101 -- adapter/effective are guaranteed after _resolve() returns no error
        assert effective is not None  # noqa: S101 -- adapter/effective are guaranteed after _resolve() returns no error

        desired_result = self._membership_builder.build_user_state_from_effective(
            user_email=user_email,
            effective=effective,
        )
        if not desired_result.is_success or desired_result.data is None:
            return desired_result

        result = adapter.reconcile_user(
            user_email=user_email,
            desired_state=desired_result.data,
            context=PlanningContext.from_effective(effective),
            dry_run=dry_run,
        )

        if result.is_success and isinstance(result.data, SyncOutcome):
            self._persist(run_id, user_email, platform, result.data, dry_run, request_id)
            if self._dispatcher:
                self._dispatcher.dispatch_background(
                    Event(
                        event_type=sync_events.SYNC_COMPLETED,
                        user_email=user_email,
                        metadata={
                            "platform": platform,
                            "applied": len(result.data.applied_actions),
                            "dry_run": dry_run,
                            "request_id": request_id,
                        },
                    )
                )
                if result.data.requires_manual_action:
                    self._dispatcher.dispatch_background(
                        Event(
                            event_type=sync_events.MANUAL_ACTION_REQUIRED,
                            user_email=user_email,
                            metadata={"platform": platform},
                        )
                    )
        else:
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
        return result

    def sync_platform(
        self,
        platform: str,
        dry_run: bool = False,
        request_id: str = "",
    ) -> OperationResult:
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

        adapter, effective, error = self._resolve(platform)
        if error is not None:
            return error
        assert adapter is not None  # noqa: S101 -- adapter/effective are guaranteed after _resolve() returns no error
        assert effective is not None  # noqa: S101 -- adapter/effective are guaranteed after _resolve() returns no error

        desired_result = self._membership_builder.build_platform_state_from_effective(
            effective=effective,
        )
        if not desired_result.is_success or desired_result.data is None:
            return desired_result

        result = adapter.reconcile_platform(
            desired_state=desired_result.data,
            context=PlanningContext.from_effective(effective),
            dry_run=dry_run,
        )

        if result.is_success and result.data is not None:
            outcome = result.data
            log.info(
                "sync_platform_completed",
                users_synced=outcome.users_synced,
                users_converged=outcome.users_converged,
                orphans_found=outcome.orphans_found,
                requires_manual_action_count=outcome.requires_manual_action_count,
            )
            if self._dispatcher:
                self._dispatcher.dispatch_background(
                    Event(
                        event_type=sync_events.PLATFORM_SYNC_COMPLETED,
                        metadata={
                            "platform": platform,
                            "users_synced": outcome.users_synced,
                            "users_converged": outcome.users_converged,
                            "orphans_found": outcome.orphans_found,
                            "requires_manual_action_count": outcome.requires_manual_action_count,
                            "dry_run": dry_run,
                        },
                    )
                )
        return result
