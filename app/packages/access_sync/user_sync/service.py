"""Access Sync user sync service.

On-demand, single-user convergence: resolves per-user desired state via
IDP group memberships, plans actions via PolicyEngine, and dispatches to
platform adapters. Delegates persistence to SyncRunRepository.
Returns standardized OperationResult[SyncOutcome] for all boundaries.

sync_user_from_context() accepts pre-fetched MembershipContext from
PlatformSyncService to keep batch platform sync at O(groups) IDP calls total.
"""

import uuid
from typing import List, Optional, Set, TYPE_CHECKING

import structlog

from infrastructure.events import Event, EventDispatcher
from infrastructure.operations import OperationResult, OperationStatus
from packages.access_sync import events as sync_events
from packages.access_sync.models import MembershipContext, SyncOutcome, SyncRunRecord
from packages.access_sync.policies import EntitlementRule, PolicyEngine, PolicyRegistry
from packages.access_sync.registry import AccessSyncRegistry

if TYPE_CHECKING:
    from infrastructure.directory.provider import DirectoryProvider
    from packages.access_sync.store import SyncRunRepository

logger = structlog.get_logger()


class UserSyncService:
    """On-demand single-user access sync.

    Computes per-user desired state via IDP group memberships, plans actions
    via PolicyEngine, and dispatches to platform adapters. All cross-cutting

    Args:
        registry: Platform adapter registry.
        policies: Platform policy definitions.
        directory: IDP-agnostic directory provider (group/membership lookups).
        repository: Optional run record repository for audit persistence.
        dispatcher: Optional event dispatcher for domain event emission.
    """

    def __init__(
        self,
        registry: AccessSyncRegistry,
        policies: PolicyRegistry,
        directory: "DirectoryProvider",
        repository: "Optional[SyncRunRepository]" = None,
        dispatcher: Optional[EventDispatcher] = None,
    ) -> None:
        self._registry = registry
        self._policies = policies
        self._directory = directory
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

        # Authn group membership → user_should_exist.
        authn_result = self._check_group_membership(policy.authn_group_slug, user_email)
        if not authn_result.is_success:
            return authn_result
        user_should_exist: bool = authn_result.data

        # Per-user entitlement group membership resolution.
        required_entitlements: List[EntitlementRule] = []
        if user_should_exist:
            required_entitlements = self._resolve_member_entitlements(
                user_email, policy.sync_managed_rules(), log
            )

        return self._execute_sync(
            user_email=user_email,
            platform=platform,
            adapter=adapter,
            policy=policy,
            user_should_exist=user_should_exist,
            required_entitlements=required_entitlements,
            dry_run=dry_run,
            run_id=run_id,
            request_id=request_id,
            log=log,
        )

    def sync_user_from_context(
        self,
        user_email: str,
        platform: str,
        context: MembershipContext,
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
            context: Pre-fetched membership result from PlatformSyncService.
            dry_run: If True, plan but do not execute.
            request_id: Correlation ID from the parent platform sync run.

        Returns:
            OperationResult[SyncOutcome] — same contract as sync_user.
        """
        run_id = request_id or str(uuid.uuid4())
        log = logger.bind(user_email=user_email, platform=platform, run_id=run_id)
        log.info("sync_started_from_context", dry_run=dry_run)

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

        return self._execute_sync(
            user_email=user_email,
            platform=platform,
            adapter=adapter,
            policy=policy,
            user_should_exist=context.user_should_exist,
            required_entitlements=context.required_entitlements,
            dry_run=dry_run,
            run_id=run_id,
            request_id=request_id,
            log=log,
        )

    def compute_desired_state(self, user_email: str, platform: str) -> OperationResult:
        """Return whether the user should exist based on authn group membership.

        Returns:
            OperationResult[bool] where data=True means user should exist.
        """
        policy = self._policies.policies.get(platform)
        if policy is None:
            return OperationResult.error(
                OperationStatus.NOT_FOUND,
                message=f"No policy for platform: {platform}",
                error_code="POLICY_NOT_FOUND",
            )
        return self._check_group_membership(policy.authn_group_slug, user_email)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _execute_sync(
        self,
        user_email: str,
        platform: str,
        adapter,
        policy,
        user_should_exist: bool,
        required_entitlements: List[EntitlementRule],
        dry_run: bool,
        run_id: str,
        request_id: str,
        log,
    ) -> OperationResult:
        """Shared plan-and-execute path for both sync_user and sync_user_from_context."""
        # Current platform state for delta planning.
        current_ids: Set[str] = set()
        current_result = adapter.get_current_entitlement_ids(user_email)
        if current_result.is_success and current_result.data is not None:
            current_ids = current_result.data

        planned = self._engine.plan_actions(
            policy=policy,
            capabilities=adapter.capabilities(),
            user_should_exist=user_should_exist,
            required_entitlements=required_entitlements,
            current_entitlement_ids=current_ids,
        )
        log.info("actions_planned", count=len(planned))

        if dry_run:
            return OperationResult.success(
                data=SyncOutcome(applied_actions=[p.action for p in planned])
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
                    run_id, user_email, platform, applied, "failed", dry_run, request_id
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
                applied_actions=applied, requires_manual_action=requires_manual_action
            )
        )

    def _check_group_membership(
        self, group_slug: str, user_email: str
    ) -> OperationResult:
        """Resolve group slug → email and check membership. Returns OperationResult[bool]."""
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
            group.group_email, user_email
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
        rules: List[EntitlementRule],
        log,
    ) -> List[EntitlementRule]:
        """Return only the entitlement rules for which the user is a group member.

        Each rule's group is checked individually against the IDP before inclusion.
        Lookup failures are logged as warnings and skipped (non-fatal).
        """
        qualified: List[EntitlementRule] = []
        for rule in rules:
            result = self._check_group_membership(rule.group_slug, user_email)
            if result.is_success and result.data:
                qualified.append(rule)
            elif not result.is_success:
                log.warning(
                    "entitlement_group_check_failed",
                    group_slug=rule.group_slug,
                    error=result.message,
                )
        return qualified

    def _execute_action(self, adapter, action, user_email: str) -> OperationResult:
        """Dispatch a single planned action to the adapter."""
        if action.action == "ensure_user":
            return adapter.ensure_user(user_email)
        if action.action == "disable_user":
            return adapter.disable_user(user_email)
        if action.action == "remove_user":
            return adapter.remove_user(user_email)
        if action.action == "apply_entitlement":
            return adapter.apply_entitlement(
                user_email, action.entitlement_type, action.entitlement_id
            )
        if action.action == "remove_entitlement":
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
