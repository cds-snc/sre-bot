"""In-memory fake Access Sync adapter for local and unit testing.

Provides deterministic responses for a non-AWS platform to validate
orchestration paths without external API dependencies.
"""

from typing import Dict, List, Set

import structlog

from infrastructure.operations import OperationResult, OperationStatus
from packages.access.sync.domain import (
    AdapterAssessment,
    DesiredUserState,
    ReconciliationOutcome,
    SyncOutcome,
)
from packages.access.sync.policies import (
    AdapterCapabilities,
    PlannedAction,
    PlanningContext,
    PolicyEngine,
)

logger = structlog.get_logger()


class FakePlatformAdapter:
    """In-memory fake platform adapter with sample users and group memberships."""

    def __init__(self) -> None:
        self._users: Set[str] = {
            "alice@example.com",
            "bob@example.com",
            "carol@example.com",
        }
        self._disabled: Set[str] = set()
        self._members_by_group: Dict[str, Set[str]] = {
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
        group_ids: Set[str] = {
            gid
            for gid, members in self._members_by_group.items()
            if normalized in members
        }
        return AdapterAssessment(
            platform_user_exists=True,
            current_entitlement_ids=group_ids,
        )

    def _execute_planned_actions(
        self,
        user_email: str,
        planned: List[PlannedAction],
    ) -> OperationResult:
        applied: List[str] = []
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
                    result = self.apply_entitlement(
                        user_email, action.entitlement_type, action.entitlement_id
                    )
                else:
                    result = self.remove_entitlement(
                        user_email, action.entitlement_type, action.entitlement_id
                    )
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
                return OperationResult.error(
                    result.status, message=result.message, error_code=result.error_code
                )
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
        desired_states: Dict[str, DesiredUserState],
        context: PlanningContext,
        dry_run: bool = False,
    ) -> OperationResult:
        """Batch reconcile all users on the fake platform."""
        idp_members = set(desired_states.keys())
        orphans = self._users - idp_members
        all_subjects = idp_members | orphans
        engine = PolicyEngine()
        users_synced = 0
        users_converged = 0
        requires_manual_action_count = 0
        per_user: Dict[str, SyncOutcome] = {}

        for email in sorted(all_subjects):
            state = desired_states.get(email, DesiredUserState(user_should_exist=False))
            current = self._assess(email)
            planned = engine.plan_actions(
                policy=context,
                capabilities=self.capabilities(),
                user_should_exist=state.user_should_exist,
                required_entitlements=state.required_entitlements,
                current_entitlement_ids=current.current_entitlement_ids,
                platform_user_exists=current.platform_user_exists,
            )
            if dry_run:
                outcome = SyncOutcome(
                    planned_actions=[a.action for a in planned],
                    applied_actions=[],
                )
            else:
                exec_result = self._execute_planned_actions(email, planned)
                if exec_result.is_success and isinstance(exec_result.data, SyncOutcome):
                    outcome = exec_result.data
                else:
                    users_synced += 1
                    continue
            per_user[email] = outcome
            users_synced += 1
            if outcome.applied_actions:
                users_converged += 1
            if outcome.requires_manual_action:
                requires_manual_action_count += 1

        return OperationResult.success(
            data=ReconciliationOutcome(
                platform=context.platform,
                users_synced=users_synced,
                users_converged=users_converged,
                orphans_found=len(orphans),
                requires_manual_action_count=requires_manual_action_count,
                dry_run=dry_run,
                per_user=per_user,
            )
        )
