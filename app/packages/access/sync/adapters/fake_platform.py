"""In-memory fake Access Sync adapter for local and unit testing.

Provides deterministic responses for a non-AWS platform to validate
orchestration paths without external API dependencies.
"""

import structlog

from infrastructure.operations import OperationResult, OperationStatus
from packages.access.sync.domain import (
    AdapterAssessment,
    CurrentPlatformState,
    DesiredPlatformState,
    DesiredUserState,
    ReconciliationOutcome,
    SyncOutcome,
)
from packages.access.sync.policies import (
    AdapterCapabilities,
    PlannedAction,
    PlanningContext,
    PlatformReconciliationPlanner,
    PolicyEngine,
)

logger = structlog.get_logger()


class FakePlatformAdapter:
    """In-memory fake platform adapter with sample users and group memberships."""

    def __init__(self) -> None:
        self._users: set[str] = {
            "alice@example.com",
            "bob@example.com",
            "carol@example.com",
        }
        self._disabled: set[str] = set()
        self._members_by_group: dict[str, set[str]] = {
            "fake-group-admin": {"alice@example.com", "carol@example.com"},
            "fake-group-read": {"bob@example.com"},
        }

    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            supports_disable=True,
            supports_delete=True,
            supported_entitlement_types={"group"},
            supports_bulk_user_delta=True,
        )

    def ensure_user(self, user_email: str) -> OperationResult:
        normalized = user_email.lower()
        self._users.add(normalized)
        self._disabled.discard(normalized)
        return OperationResult.success(data={"user_id": f"fake-{normalized}"})

    def disable_user(self, user_email: str) -> OperationResult:
        normalized = user_email.lower()
        if normalized not in self._users:
            return OperationResult.success(message="user_already_absent")
        self._disabled.add(normalized)
        return OperationResult.success(message="user_disabled")

    def remove_user(self, user_email: str) -> OperationResult:
        normalized = user_email.lower()
        self._users.discard(normalized)
        self._disabled.discard(normalized)
        for members in self._members_by_group.values():
            members.discard(normalized)
        return OperationResult.success(message="user_removed")

    def apply_entitlement(
        self,
        user_email: str,
        entitlement_type: str,
        entitlement_id: str,
    ) -> OperationResult:
        normalized = user_email.lower()
        if entitlement_type != "group":
            return OperationResult.error(
                OperationStatus.PERMANENT_ERROR,
                message=f"Unsupported entitlement_type: {entitlement_type}",
                error_code="UNSUPPORTED_ENTITLEMENT_TYPE",
            )
        self._users.add(normalized)
        self._members_by_group.setdefault(entitlement_id, set()).add(normalized)
        return OperationResult.success(message="entitlement_applied")

    def remove_entitlement(
        self,
        user_email: str,
        entitlement_type: str,
        entitlement_id: str,
    ) -> OperationResult:
        normalized = user_email.lower()
        if entitlement_type != "group":
            return OperationResult.error(
                OperationStatus.PERMANENT_ERROR,
                message=f"Unsupported entitlement_type: {entitlement_type}",
                error_code="UNSUPPORTED_ENTITLEMENT_TYPE",
            )
        self._members_by_group.get(entitlement_id, set()).discard(normalized)
        return OperationResult.success(message="entitlement_removed")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def list_all_provisioned_users(self) -> OperationResult:
        """Return the set of all provisioned user emails."""
        return OperationResult.success(data=set(self._users))

    def _assess(self, user_email: str) -> AdapterAssessment:
        normalized = user_email.lower()
        if normalized not in self._users:
            return AdapterAssessment(
                platform_user_exists=False,
                current_entitlement_ids=set(),
            )
        group_ids: set[str] = {gid for gid, members in self._members_by_group.items() if normalized in members}
        return AdapterAssessment(
            platform_user_exists=True,
            current_entitlement_ids=group_ids,
        )

    def _execute_planned_actions(
        self,
        user_email: str,
        planned: list[PlannedAction],
    ) -> OperationResult:
        applied: list[str] = []
        requires_manual_action = False
        for action in planned:
            if action.action == "provision_user":
                result = self.ensure_user(user_email)
            elif action.action == "disable_user":
                result = self.disable_user(user_email)
            elif action.action == "remove_user":
                result = self.remove_user(user_email)
            elif action.action in ("apply_entitlement", "remove_entitlement"):
                if action.entitlement_type is None or action.entitlement_id is None:
                    return OperationResult.error(
                        OperationStatus.PERMANENT_ERROR,
                        message="Missing entitlement metadata",
                        error_code="INVALID_PLANNED_ACTION",
                    )
                if action.action == "apply_entitlement":
                    result = self.apply_entitlement(user_email, action.entitlement_type, action.entitlement_id)
                else:
                    result = self.remove_entitlement(user_email, action.entitlement_type, action.entitlement_id)
            else:
                return OperationResult.error(
                    OperationStatus.PERMANENT_ERROR,
                    message=f"Unknown action: {action.action}",
                    error_code="UNKNOWN_ACTION",
                )
            if result.is_success:
                applied.append(action.action)
            elif result.error_code == "UNSUPPORTED_OPERATION":
                requires_manual_action = True
            else:
                return OperationResult.error(result.status, message=result.message, error_code=result.error_code)
        return OperationResult.success(
            data=SyncOutcome(
                planned_actions=[a.action for a in planned],
                applied_actions=applied,
                requires_manual_action=requires_manual_action,
            )
        )

    # ------------------------------------------------------------------
    # Primary reconciliation interface
    # ------------------------------------------------------------------

    def reconcile_user(
        self,
        user_email: str,
        desired_state: DesiredUserState,
        context: PlanningContext,
        dry_run: bool = False,
    ) -> OperationResult:
        """Assess current state, plan delta, execute changes for one user."""
        current = self._assess(user_email)
        engine = PolicyEngine()
        planned = engine.plan_actions(
            policy=context,
            capabilities=self.capabilities(),
            user_should_exist=desired_state.user_should_exist,
            required_entitlements=desired_state.required_entitlements,
            current_entitlement_ids=current.current_entitlement_ids,
            platform_user_exists=current.platform_user_exists,
        )
        if dry_run:
            return OperationResult.success(
                data=SyncOutcome(
                    planned_actions=[a.action for a in planned],
                    applied_actions=[],
                )
            )
        return self._execute_planned_actions(user_email, planned)

    def reconcile_platform(
        self,
        desired_state: DesiredPlatformState,
        context: PlanningContext,
        dry_run: bool = False,
    ) -> OperationResult:
        """Batch reconcile the fake platform using entitlement-shaped state."""
        planner = PlatformReconciliationPlanner()
        current_state = CurrentPlatformState(
            current_users=set(self._users),
            current_members_by_entitlement={
                entitlement_id: set(members) for entitlement_id, members in self._members_by_group.items()
            },
        )
        plan = planner.plan_platform_actions(
            desired_users=desired_state.desired_users,
            desired_members_by_entitlement=desired_state.desired_members_by_entitlement,
            current_users=current_state.current_users,
            current_members_by_entitlement=current_state.current_members_by_entitlement,
            authn_removal_mode=context.authn_removal_mode,
        )
        actions_by_user: dict[str, list[PlannedAction]] = {}

        for email in sorted(plan.users_to_provision):
            actions_by_user.setdefault(email, []).append(PlannedAction(action="provision_user"))
        for entitlement_id, members in sorted(plan.entitlement_adds_by_id.items()):
            for email in sorted(members):
                actions_by_user.setdefault(email, []).append(
                    PlannedAction(
                        action="apply_entitlement",
                        entitlement_type="group",
                        entitlement_id=entitlement_id,
                    )
                )
        for entitlement_id, members in sorted(plan.entitlement_removes_by_id.items()):
            for email in sorted(members):
                actions_by_user.setdefault(email, []).append(
                    PlannedAction(
                        action="remove_entitlement",
                        entitlement_type="group",
                        entitlement_id=entitlement_id,
                    )
                )
        for email in sorted(plan.users_to_disable):
            actions_by_user.setdefault(email, []).append(PlannedAction(action="disable_user"))
        for email in sorted(plan.users_to_remove):
            actions_by_user.setdefault(email, []).append(PlannedAction(action="remove_user"))

        users_synced = len(desired_state.desired_users | current_state.current_users)
        users_converged = 0
        requires_manual_action_count = 0
        per_user: dict[str, SyncOutcome] = {}
        for email in sorted(actions_by_user):
            planned = actions_by_user[email]
            if dry_run:
                outcome = SyncOutcome(
                    planned_actions=[action.action for action in planned],
                    applied_actions=[],
                )
            else:
                exec_result = self._execute_planned_actions(email, planned)
                if not exec_result.is_success or not isinstance(exec_result.data, SyncOutcome):
                    return exec_result
                outcome = exec_result.data
            per_user[email] = outcome
            if outcome.applied_actions:
                users_converged += 1
            if outcome.requires_manual_action:
                requires_manual_action_count += 1

        return OperationResult.success(
            data=ReconciliationOutcome(
                platform=context.platform,
                users_synced=users_synced,
                users_converged=users_converged,
                orphans_found=len(current_state.current_users - desired_state.desired_users),
                requires_manual_action_count=requires_manual_action_count,
                dry_run=dry_run,
                per_user=per_user,
            )
        )
