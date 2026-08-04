"""Unit tests for AccessSyncApplicationService.

Covers:
  F-01  sync_user returns OperationResult[SyncOutcome]
  F-02  sync_platform returns OperationResult[ReconciliationOutcome]
  F-03  POLICY_NOT_FOUND and ADAPTER_NOT_FOUND errors surface correctly
  F-04  dry_run returns planned actions without executing them
  F-05  UNSUPPORTED_OPERATION from adapter sets requires_manual_action
"""

from typing import Any

import pytest

from infrastructure.directory.models import (
    DirectoryGroup,
    DirectoryMember,
    MembershipCheckResult,
)
from infrastructure.operations import OperationResult, OperationStatus
from packages.access.common.config import AccessRuntimeConfig, PlatformPolicy
from packages.access.sync.application import AccessSyncApplicationService
from packages.access.sync.desired_state import DirectoryMembershipBuilder
from packages.access.sync.domain import (
    AdapterAssessment,
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

# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


class FakeAdapter:
    """Records calls; uses PolicyEngine internally for reconcile methods."""

    def __init__(
        self,
        current_entitlement_ids: set[str] | None = None,
        user_exists: bool = True,
        disable_fails: bool = False,
    ) -> None:
        self.calls: list[tuple] = []
        self._current_ids: set[str] = current_entitlement_ids or set()
        self._user_exists = user_exists
        self._disable_fails = disable_fails

    def set_disable_fails(self) -> None:
        self._disable_fails = True

    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            supports_disable=True,
            supports_delete=True,
            supported_entitlement_types={"permission_set", "group"},
            supports_bulk_user_delta=True,
        )

    def ensure_user(self, email: str) -> OperationResult:
        self.calls.append(("ensure_user", email))
        return OperationResult.success()

    def disable_user(self, email: str) -> OperationResult:
        self.calls.append(("disable_user", email))
        if self._disable_fails:
            return OperationResult.error(
                OperationStatus.PERMANENT_ERROR,
                message="Disable not supported",
                error_code="UNSUPPORTED_OPERATION",
            )
        return OperationResult.success()

    def remove_user(self, email: str) -> OperationResult:
        self.calls.append(("remove_user", email))
        return OperationResult.success()

    def apply_entitlement(self, email: str, etype: str, eid: str) -> OperationResult:
        self.calls.append(("apply_entitlement", email, etype, eid))
        return OperationResult.success()

    def remove_entitlement(self, email: str, etype: str, eid: str) -> OperationResult:
        self.calls.append(("remove_entitlement", email, etype, eid))
        return OperationResult.success()

    def _assess(self, email: str) -> AdapterAssessment:
        if not self._user_exists:
            return AdapterAssessment(platform_user_exists=False, current_entitlement_ids=set())
        return AdapterAssessment(
            platform_user_exists=True,
            current_entitlement_ids=set(self._current_ids),
        )

    def _execute(self, email: str, planned: list) -> SyncOutcome:
        applied: list[str] = []
        requires_manual = False
        for action in planned:
            if action.action == "provision_user":
                r = self.ensure_user(email)
            elif action.action == "disable_user":
                r = self.disable_user(email)
            elif action.action == "remove_user":
                r = self.remove_user(email)
            elif action.action == "apply_entitlement":
                r = self.apply_entitlement(email, action.entitlement_type or "", action.entitlement_id or "")
            elif action.action == "remove_entitlement":
                r = self.remove_entitlement(email, action.entitlement_type or "", action.entitlement_id or "")
            else:
                continue
            if r.is_success:
                applied.append(action.action)
            elif r.error_code == "UNSUPPORTED_OPERATION":
                requires_manual = True
        return SyncOutcome(
            planned_actions=[a.action for a in planned],
            applied_actions=applied,
            requires_manual_action=requires_manual,
        )

    def reconcile_user(
        self,
        user_email: str,
        desired_state: DesiredUserState,
        context: PlanningContext,
        dry_run: bool = False,
    ) -> OperationResult:
        self.calls.append(("reconcile_user", user_email))
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
        return OperationResult.success(data=self._execute(user_email, planned))

    def reconcile_platform(
        self,
        desired_state: DesiredPlatformState,
        context: PlanningContext,
        dry_run: bool = False,
    ) -> OperationResult:
        self.calls.append(("reconcile_platform",))
        planner = PlatformReconciliationPlanner()
        plan = planner.plan_platform_actions(
            desired_users=desired_state.desired_users,
            desired_members_by_entitlement=desired_state.desired_members_by_entitlement,
            current_users=set(),
            current_members_by_entitlement={},
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
        for email in sorted(plan.users_to_disable):
            actions_by_user.setdefault(email, []).append(PlannedAction(action="disable_user"))
        for email in sorted(plan.users_to_remove):
            actions_by_user.setdefault(email, []).append(PlannedAction(action="remove_user"))

        per_user: dict[str, SyncOutcome] = {}
        users_converged = 0
        for email, planned in sorted(actions_by_user.items()):
            if dry_run:
                outcome = SyncOutcome(
                    planned_actions=[action.action for action in planned],
                    applied_actions=[],
                )
            else:
                outcome = self._execute(email, planned)
            per_user[email] = outcome
            if outcome.applied_actions:
                users_converged += 1
        return OperationResult.success(
            data=ReconciliationOutcome(
                platform=context.platform,
                users_synced=len(desired_state.desired_users),
                users_converged=users_converged,
                orphans_found=0,
                requires_manual_action_count=0,
                dry_run=dry_run,
                per_user=per_user,
            )
        )


class FakeDirectory:
    """Static IDP fixture for unit tests."""

    def __init__(
        self,
        is_member: bool = True,
        groups: set[str] | None = None,
        user_group_slugs: set[str] | None = None,
    ) -> None:
        self._is_member = is_member
        self._per_group: dict[str, bool] = {}
        self._groups: set[str] = groups or set()
        self._user_group_slugs: set[str] | None = user_group_slugs

    def set_membership(self, group_slug: str, value: bool) -> None:
        self._per_group[group_slug] = value

    def get_user_groups(self, user_email: str) -> OperationResult:
        if self._user_group_slugs is not None:
            slugs = self._user_group_slugs
        else:
            slugs = {slug for slug in self._groups if self._per_group.get(slug, self._is_member)}
        return OperationResult.success(
            data=[
                DirectoryGroup(
                    group_email=f"{slug}@example.com",
                    group_slug=slug,
                    provider_group_id=f"gid-{slug}",
                )
                for slug in slugs
            ]
        )

    def get_group(self, slug: str) -> OperationResult:
        return OperationResult.success(
            data=DirectoryGroup(
                group_email=f"{slug}@example.com",
                group_slug=slug,
                provider_group_id=f"gid-{slug}",
            )
        )

    def check_membership(self, group_email: str, user_email: str) -> OperationResult:
        slug = group_email.split("@")[0]
        is_member = self._per_group.get(slug, self._is_member)
        return OperationResult.success(
            data=MembershipCheckResult(
                group_email=group_email,
                group_slug=slug,
                provider_group_id=None,
                user_email=user_email,
                is_member=is_member,
            )
        )

    def get_group_members(self, group_email: str, include_member_types: set | None = None) -> OperationResult:
        slug = group_email.split("@", 1)[0]
        if slug not in (self._user_group_slugs or set()):
            return OperationResult.success(data=[])
        return OperationResult.success(data=[DirectoryMember(email="alice@example.com", member_type="USER")])

    def get_group_members_batch(
        self,
        group_emails: list[str],
        include_member_types: set | None = None,
    ) -> OperationResult:
        mapping: dict[str, list[DirectoryMember]] = {}
        for group_email in group_emails:
            slug = group_email.split("@", 1)[0]
            if slug in (self._user_group_slugs or set()):
                mapping[group_email] = [DirectoryMember(email="alice@example.com", member_type="USER")]
            else:
                mapping[group_email] = []
        return OperationResult.success(data=mapping)

    def list_groups(self, query: str = "") -> OperationResult:
        matching = [
            DirectoryGroup(
                group_email=f"{slug}@example.com",
                group_slug=slug,
                provider_group_id=f"gid-{slug}",
            )
            for slug in self._groups
            if not query or slug.startswith(query)
        ]
        return OperationResult.success(data=matching)


def make_coordinator(
    platform: str = "aws",
    authn_removal_mode: str = "delete",
    is_member: bool = True,
    current_ids: set[str] | None = None,
    user_exists: bool = True,
    adapter: FakeAdapter | None = None,
    discovered_groups: set[str] | None = None,
) -> tuple:
    if adapter is None:
        adapter = FakeAdapter(current_entitlement_ids=current_ids or set(), user_exists=user_exists)
    config = AccessRuntimeConfig(
        dir_prefix="sg",
        platforms={
            platform: PlatformPolicy(
                authn_token="authn",
                authn_removal_mode=authn_removal_mode,
            )
        },
    )
    authn_slug = config.authn_group_slug(platform)
    user_group_slugs = ({authn_slug} | (discovered_groups or set())) if is_member else set()
    directory = FakeDirectory(
        is_member=is_member,
        groups=discovered_groups or set(),
        user_group_slugs=user_group_slugs,
    )
    directory_provider: Any = directory
    coordinator = AccessSyncApplicationService(
        adapters={platform: adapter},
        config=config,
        membership_builder=DirectoryMembershipBuilder(directory_provider),
    )
    return coordinator, adapter


# ---------------------------------------------------------------------------
# F-01 sync_user returns OperationResult[SyncOutcome]
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_sync_user_returns_operation_result_with_sync_outcome():
    coordinator, _ = make_coordinator(is_member=True)
    result = coordinator.sync_user("alice@example.com", "aws")
    assert isinstance(result, OperationResult)
    assert result.is_success
    assert isinstance(result.data, SyncOutcome)


@pytest.mark.unit
def test_sync_user_existing_member_no_lifecycle_action():
    coordinator, adapter = make_coordinator(is_member=True, user_exists=True)
    result = coordinator.sync_user("alice@example.com", "aws")
    assert result.is_success
    assert "provision_user" not in result.data.planned_actions
    assert not any(c[0] == "ensure_user" for c in adapter.calls)


@pytest.mark.unit
def test_sync_user_new_member_provisions_user():
    coordinator, adapter = make_coordinator(is_member=True, user_exists=False)
    result = coordinator.sync_user("alice@example.com", "aws")
    assert result.is_success
    assert "provision_user" in result.data.planned_actions
    assert "provision_user" in result.data.applied_actions
    assert any(c[0] == "ensure_user" for c in adapter.calls)


@pytest.mark.unit
def test_sync_user_non_member_removes_user():
    coordinator, adapter = make_coordinator(is_member=False, authn_removal_mode="delete")
    result = coordinator.sync_user("alice@example.com", "aws")
    assert result.is_success
    assert "remove_user" in result.data.planned_actions
    assert "remove_user" in result.data.applied_actions


# ---------------------------------------------------------------------------
# F-03 Policy / adapter not found
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_sync_user_policy_not_found():
    coordinator, _ = make_coordinator()
    result = coordinator.sync_user("alice@example.com", "nonexistent")
    assert not result.is_success
    assert result.error_code == "POLICY_NOT_FOUND"


@pytest.mark.unit
def test_sync_user_adapter_not_found():
    config = AccessRuntimeConfig(
        dir_prefix="sg",
        platforms={"aws": PlatformPolicy()},
    )
    directory_provider: Any = FakeDirectory()
    coordinator = AccessSyncApplicationService(
        adapters={},
        config=config,
        membership_builder=DirectoryMembershipBuilder(directory_provider),
    )
    result = coordinator.sync_user("alice@example.com", "aws")
    assert not result.is_success
    assert result.error_code == "ADAPTER_NOT_FOUND"


# ---------------------------------------------------------------------------
# F-04 dry_run
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_sync_user_dry_run_no_action_calls():
    coordinator, adapter = make_coordinator(is_member=False, user_exists=True)
    result = coordinator.sync_user("alice@example.com", "aws", dry_run=True)
    assert result.is_success
    assert result.data.applied_actions == []
    assert not any(c[0] == "remove_user" for c in adapter.calls)


# ---------------------------------------------------------------------------
# F-05 UNSUPPORTED_OPERATION → requires_manual_action
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_sync_user_disable_unsupported_sets_requires_manual_action():
    adapter = FakeAdapter()
    adapter.set_disable_fails()
    coordinator, _ = make_coordinator(
        authn_removal_mode="disable",
        is_member=False,
        adapter=adapter,
        user_exists=True,
    )
    result = coordinator.sync_user("alice@example.com", "aws")
    assert result.is_success
    assert result.data.requires_manual_action is True


# ---------------------------------------------------------------------------
# F-02 sync_platform returns OperationResult[ReconciliationOutcome]
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_sync_platform_returns_reconciliation_outcome():
    coordinator, _ = make_coordinator()
    result = coordinator.sync_platform("aws")
    assert isinstance(result, OperationResult)
    assert result.is_success
    assert isinstance(result.data, ReconciliationOutcome)


@pytest.mark.unit
def test_sync_platform_unknown_platform_returns_error():
    coordinator, _ = make_coordinator()
    result = coordinator.sync_platform("nonexistent")
    assert not result.is_success
    assert result.error_code == "POLICY_NOT_FOUND"
