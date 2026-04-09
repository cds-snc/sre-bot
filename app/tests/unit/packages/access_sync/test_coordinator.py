"""Unit tests for AccessSyncCoordinator.

Covers:
  F-01  sync_user returns OperationResult[SyncOutcome]
  F-02  sync_platform returns OperationResult[ReconciliationOutcome]
  F-03  POLICY_NOT_FOUND and ADAPTER_NOT_FOUND errors surface correctly
  F-04  dry_run returns planned actions without executing them
  F-05  UNSUPPORTED_OPERATION from adapter sets requires_manual_action
  D-01  per-user entitlement group qualification
"""

from typing import Dict, List, Set

import pytest

from infrastructure.directory.models import (
    DirectoryGroup,
    MembershipCheckResult,
)
from infrastructure.operations import OperationResult, OperationStatus
from packages.access_sync.coordinator import AccessSyncCoordinator
from packages.access_sync.desired_state import DirectoryMembershipBuilder
from packages.access_sync.domain import ReconciliationOutcome, SyncOutcome
from packages.access_sync.policies import (
    AdapterCapabilities,
    EntitlementRule,
    PlatformPolicy,
)


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


class FakeAdapter:
    """Records all calls; configurable return values per method."""

    def __init__(self, current_entitlement_ids: Set[str] | None = None) -> None:
        self.calls: List[tuple] = []
        self._current_ids: Set[str] = current_entitlement_ids or set()
        self._disable_fails = False

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

    def get_current_entitlement_ids(self, email: str) -> OperationResult:
        self.calls.append(("get_current_entitlement_ids", email))
        return OperationResult.success(data=set(self._current_ids))

    def list_all_provisioned_users(self) -> OperationResult:
        self.calls.append(("list_all_provisioned_users",))
        return OperationResult.error(
            OperationStatus.PERMANENT_ERROR,
            message="not supported",
            error_code="UNSUPPORTED_OPERATION",
        )

    def list_group_members(self, group_id: str) -> OperationResult:
        self.calls.append(("list_group_members", group_id))
        return OperationResult.success(data=set())


class FakeDirectory:
    """Static group/member fixtures. Configurable per-group membership."""

    def __init__(self, is_member: bool = True) -> None:
        self._is_member = is_member
        self._per_group: Dict[str, bool] = {}

    def set_membership(self, group_slug: str, value: bool) -> None:
        self._per_group[group_slug] = value

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

    def get_group_members(
        self, group_email: str, include_member_types: set | None = None
    ) -> OperationResult:
        return OperationResult.success(data=[])

    def list_groups(self, query: str = "") -> OperationResult:
        return OperationResult.success(data=[])


def make_coordinator(
    platform: str = "aws",
    rules: List[EntitlementRule] | None = None,
    authn_removal_mode: str = "delete",
    is_member: bool = True,
    current_ids: Set[str] | None = None,
    adapter: FakeAdapter | None = None,
) -> tuple[AccessSyncCoordinator, FakeAdapter]:
    if adapter is None:
        adapter = FakeAdapter(current_entitlement_ids=current_ids or set())
    policy = PlatformPolicy(
        platform=platform,
        authn_group_slug=f"sg-{platform}-authn",
        authn_mode="derived",
        authn_removal_mode=authn_removal_mode,
        entitlement_rules=rules or [],
    )
    directory = FakeDirectory(is_member=is_member)
    membership_builder = DirectoryMembershipBuilder(directory)
    coordinator = AccessSyncCoordinator(
        adapters={platform: adapter},
        policies={platform: policy},
        membership_builder=membership_builder,
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
def test_sync_user_member_ensures_user():
    coordinator, adapter = make_coordinator(is_member=True)
    result = coordinator.sync_user("alice@example.com", "aws")
    assert result.is_success
    assert "ensure_user" in result.data.planned_actions
    assert "ensure_user" in result.data.applied_actions
    assert any(c[0] == "ensure_user" for c in adapter.calls)


@pytest.mark.unit
def test_sync_user_non_member_removes_user():
    coordinator, adapter = make_coordinator(
        is_member=False, authn_removal_mode="delete"
    )
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
    policy = PlatformPolicy(
        platform="aws",
        authn_group_slug="sg-aws-authn",
        authn_mode="derived",
        authn_removal_mode="delete",
        entitlement_rules=[],
    )
    coordinator = AccessSyncCoordinator(
        adapters={},  # no adapter registered
        policies={"aws": policy},
        membership_builder=DirectoryMembershipBuilder(FakeDirectory()),
    )
    result = coordinator.sync_user("alice@example.com", "aws")
    assert not result.is_success
    assert result.error_code == "ADAPTER_NOT_FOUND"


# ---------------------------------------------------------------------------
# F-04 dry_run
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_sync_user_dry_run_no_action_calls():
    coordinator, adapter = make_coordinator(is_member=True)
    result = coordinator.sync_user("alice@example.com", "aws", dry_run=True)
    assert result.is_success
    assert result.data.applied_actions == []
    assert "ensure_user" in result.data.planned_actions
    # Only get_current_entitlement_ids is allowed before dry-run stops
    exec_calls = [
        c for c in adapter.calls if c[0] not in {"get_current_entitlement_ids"}
    ]
    assert exec_calls == []


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
    )
    result = coordinator.sync_user("alice@example.com", "aws")
    assert result.is_success
    assert result.data.requires_manual_action is True


# ---------------------------------------------------------------------------
# D-01 per-user entitlement group qualification
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_sync_user_entitlement_not_applied_when_not_in_group():
    """Entitlement is only applied when user is a member of the entitlement group."""
    rule = EntitlementRule(
        group_slug="sg-aws-admin",
        entitlement_type="permission_set",
        entitlement_id="123/AdminAccess",
        mode="sync_managed",
    )
    adapter = FakeAdapter()
    policy = PlatformPolicy(
        platform="aws",
        authn_group_slug="sg-aws-authn",
        authn_mode="derived",
        authn_removal_mode="delete",
        entitlement_rules=[rule],
    )
    directory = FakeDirectory(is_member=True)
    # Member of authn but NOT of entitlement group
    directory.set_membership("sg-aws-admin", False)
    coordinator = AccessSyncCoordinator(
        adapters={"aws": adapter},
        policies={"aws": policy},
        membership_builder=DirectoryMembershipBuilder(directory),
    )
    result = coordinator.sync_user("alice@example.com", "aws")
    assert result.is_success
    call_names = [c[0] for c in adapter.calls]
    assert "ensure_user" in call_names
    assert "apply_entitlement" not in call_names


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
