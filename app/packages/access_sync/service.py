"""Access Sync core orchestration service.

Computes desired state from IDP membership, resolves planned actions via the
PolicyEngine, and dispatches each action to the appropriate platform adapter.
Policy semantics live in policies.py — this module wires them together.
"""

import uuid
from typing import List, TYPE_CHECKING

import structlog

from infrastructure.operations import OperationResult, OperationStatus
from packages.access_sync.adapters import AccessSyncAdapter
from packages.access_sync.policies import (
    AdapterCapabilities,
    PlannedAction,
    PolicyEngine,
    PolicyRegistry,
)
from packages.access_sync.registry import AccessSyncRegistry
from packages.access_sync.result import AccessSyncResult
from packages.access_sync.store import InMemorySyncRunStore, SyncRunRecord, SyncRunStore

if TYPE_CHECKING:
    from infrastructure.directory.provider import DirectoryProvider

logger = structlog.get_logger()


class AccessSyncService:
    """Core access sync orchestration service.

    Responsibilities:
    - Resolve effective authn-group membership from the IDP.
    - Use PolicyEngine to compute planned actions.
    - Dispatch actions to the correct platform adapter.
    - Persist run records via the injected store.
    """

    def __init__(
        self,
        registry: AccessSyncRegistry,
        policies: PolicyRegistry,
        directory: "DirectoryProvider",
        store: SyncRunStore = None,  # type: ignore[assignment]
    ) -> None:
        self._registry = registry
        self._policies = policies
        self._directory = directory
        self._store: SyncRunStore = (
            store if store is not None else InMemorySyncRunStore()
        )
        self._engine = PolicyEngine()

    # ------------------------------------------------------------------
    # Desired-state helpers
    # ------------------------------------------------------------------

    def compute_desired_state(
        self,
        user_email: str,
        platform: str,
    ) -> OperationResult[bool]:
        """Resolve whether *user_email* should retain authn access on *platform*.

        Resolves policy group slug → canonical DirectoryGroup, then checks
        effective membership (direct + indirect) in the authn group.

        Returns:
            OperationResult[bool] where data=True means the user should exist.
        """
        log = logger.bind(user_email=user_email, platform=platform)

        policy = self._policies.policies.get(platform)
        if policy is None:
            return OperationResult.error(
                OperationStatus.NOT_FOUND,
                message=f"No policy registered for platform: {platform}",
                error_code="POLICY_NOT_FOUND",
            )

        # Resolve authn group using provider-agnostic directory contract.
        # group_key accepts slug or canonical email depending provider rules.
        group_result = self._directory.get_group(policy.authn_group_slug)
        if not group_result.is_success:
            log.error(
                "authn_group_resolution_failed",
                slug=policy.authn_group_slug,
                error=group_result.message,
            )
            return OperationResult.error(
                group_result.status,
                message=group_result.message,
                error_code=group_result.error_code,
            )

        authn_group = group_result.data
        if authn_group is None:
            return OperationResult.error(
                OperationStatus.NOT_FOUND,
                message=f"Authn group not found in IDP: {policy.authn_group_slug}",
                error_code="AUTHN_GROUP_NOT_FOUND",
            )

        if not authn_group.group_email:
            return OperationResult.error(
                OperationStatus.PERMANENT_ERROR,
                message=(
                    f"Authn group {policy.authn_group_slug} has no email. "
                    "Ensure the group is mail-enabled."
                ),
                error_code="DIRECTORY_GROUP_EMAIL_REQUIRED",
            )

        # Effective membership — honors nested groups via the DirectoryProvider.
        membership_result = self._directory.check_membership(
            authn_group.group_email,
            user_email,
        )
        if not membership_result.is_success:
            log.error(
                "membership_check_failed",
                group_email=authn_group.group_email,
                error=membership_result.message,
            )
            return OperationResult.error(
                membership_result.status,
                message=membership_result.message,
                error_code=membership_result.error_code,
            )

        membership = membership_result.data
        user_should_exist = membership.is_member if membership is not None else False

        log.info(
            "desired_state_resolved",
            authn_mode=policy.authn_mode,
            group_slug=authn_group.group_slug,
            group_email=authn_group.group_email,
            provider_group_id=authn_group.provider_group_id,
            user_should_exist=user_should_exist,
        )
        return OperationResult.success(data=user_should_exist)

    # ------------------------------------------------------------------
    # Main sync entry point
    # ------------------------------------------------------------------

    def sync_user(
        self,
        user_email: str,
        platform: str,
        dry_run: bool = False,
        request_id: str = "",
    ) -> AccessSyncResult:
        """Sync a single user's state on *platform* to match IDP policy.

        Steps:
        1. Verify a policy exists for the platform.
        2. Compute desired state (authn group membership check).
        3. Plan actions via PolicyEngine.
        4. Execute each action unless dry_run=True.
        5. Persist the run record.

        Args:
            user_email: The user to sync.
            platform: Target platform key (e.g. 'aws').
            dry_run: If True, compute and return planned actions without executing.
            request_id: Correlation ID for tracing across components.

        Returns:
            AccessSyncResult with applied actions and status. Includes
            requires_manual_action=True if any operations cannot be automated.
        """
        run_id = request_id or str(uuid.uuid4())
        log = logger.bind(user_email=user_email, platform=platform, run_id=run_id)
        log.info("access_sync_started", dry_run=dry_run)

        # --- Policy check ---
        policy = self._policies.policies.get(platform)
        if policy is None:
            log.error(
                "policy_not_found",
                platform=platform,
            )
            return AccessSyncResult(
                success=False,
                applied_actions=[],
                message=f"No policy registered for platform: {platform}",
                error_message=f"No policy registered for platform: {platform}",
                error_code="POLICY_NOT_FOUND",
                status="failed",
            )

        # --- Adapter lookup ---
        try:
            adapter = self._registry.get_adapter(platform)
        except KeyError:
            log.error(
                "adapter_not_registered",
                platform=platform,
            )
            return AccessSyncResult(
                success=False,
                applied_actions=[],
                message=f"No adapter registered for platform: {platform}",
                error_message=f"No adapter registered for platform: {platform}",
                error_code="ADAPTER_NOT_REGISTERED",
                status="failed",
            )

        # --- Desired state ---
        desired_result = self.compute_desired_state(
            user_email=user_email, platform=platform
        )
        if not desired_result.is_success:
            log.error("desired_state_failed", error=desired_result.message)
            return AccessSyncResult(
                success=False,
                applied_actions=[],
                message=desired_result.message,
                error_message=desired_result.message,
                status="failed",
            )
        user_should_exist: bool = desired_result.data  # type: ignore[assignment]

        # --- Plan actions ---
        capabilities: AdapterCapabilities = adapter.capabilities()
        planned: List[PlannedAction] = self._engine.plan_actions(
            policy=policy,
            capabilities=capabilities,
            user_should_exist=user_should_exist,
            required_entitlements=policy.sync_managed_rules(),
        )
        action_names: list[str] = [p.action for p in planned]
        log.info("actions_planned", planned_actions=action_names, dry_run=dry_run)

        if dry_run:
            return AccessSyncResult(
                success=True,
                applied_actions=action_names,
                message="dry_run_completed",
            )

        # --- Execute ---
        applied: List[str] = []
        requires_manual_action = False
        run_status = "success"
        last_error: str = ""

        for planned_action in planned:
            result = self._execute_action(
                adapter=adapter,
                planned=planned_action,
                user_email=user_email,
                log=log,
            )
            if result.is_success:
                applied.append(planned_action.action)
            elif result.error_code == "UNSUPPORTED_OPERATION":
                # Operation cannot be automated; requires manual intervention
                requires_manual_action = True
                last_error = result.message
                log.warning(
                    "unsupported_operation",
                    action=planned_action.action,
                    reason=result.message,
                )
            else:
                # Technical failure; stop processing
                run_status = "failed"
                last_error = result.message
                log.error(
                    "action_failed", action=planned_action.action, error=result.message
                )
                break

        # --- Persist run record ---
        self._store.save_run(
            SyncRunRecord(
                run_id=run_id,
                user_email=user_email,
                platform=platform,
                actions_applied=applied,
                status=run_status,  # type: ignore[arg-type]
                dry_run=dry_run,
                request_id=request_id,
                error_message=last_error or None,
            )
        )

        if run_status == "failed":
            log.error("access_sync_failed", actions_applied=applied, error=last_error)
            return AccessSyncResult(
                success=False,
                applied_actions=applied,
                message=last_error,
                error_message=last_error,
                status="failed",
            )

        # Successful completion, possibly with manual action required
        final_status = "manual_action_required" if requires_manual_action else "success"
        log.info("access_sync_completed", actions_applied=applied, status=final_status)
        return AccessSyncResult(
            success=True,
            applied_actions=applied,
            requires_manual_action=requires_manual_action,
            message=final_status,
            status=final_status,
        )

    # ------------------------------------------------------------------
    # Internal action dispatcher
    # ------------------------------------------------------------------

    def _execute_action(
        self,
        adapter: AccessSyncAdapter,
        planned: PlannedAction,
        user_email: str,
        log: object,
    ) -> OperationResult:
        """Dispatch a single PlannedAction to the adapter."""
        if planned.action == "ensure_user":
            return adapter.ensure_user(user_email)
        if planned.action == "disable_user":
            return adapter.disable_user(user_email)
        if planned.action == "remove_user":
            return adapter.remove_user(user_email)
        if planned.action == "apply_entitlement":
            if planned.entitlement_type is None or planned.entitlement_id is None:
                return OperationResult.error(
                    OperationStatus.PERMANENT_ERROR,
                    message="Planned action missing entitlement fields",
                    error_code="INVALID_PLANNED_ACTION",
                )
            return adapter.apply_entitlement(
                user_email,
                planned.entitlement_type,
                planned.entitlement_id,
            )
        if planned.action == "remove_entitlement":
            if planned.entitlement_type is None or planned.entitlement_id is None:
                return OperationResult.error(
                    OperationStatus.PERMANENT_ERROR,
                    message="Planned action missing entitlement fields",
                    error_code="INVALID_PLANNED_ACTION",
                )
            return adapter.remove_entitlement(
                user_email,
                planned.entitlement_type,
                planned.entitlement_id,
            )
        return OperationResult.error(
            OperationStatus.PERMANENT_ERROR,
            message=f"Unknown planned action: {planned.action}",
            error_code="UNKNOWN_ACTION",
        )
