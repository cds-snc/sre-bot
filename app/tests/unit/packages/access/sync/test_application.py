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
from packages.access.common.config import AccessRuntimeConfig as AccessSyncRuntimeConfig
from packages.access.sync.application import AccessSyncCoordinator
from packages.access.sync.desired_state import DirectoryMembershipBuilder
from packages.access.sync.domain import (
    AdapterAssessment,
    DesiredUserState,
    ReconciliationOutcome,
    SyncOutcome,
)
from packages.access.common.config import PlatformPolicy
from packages.access.sync.policies import (
    AdapterCapabilities,
)


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


class FakeAdapter:
    """Records all calls; configurable return values per method."""

    def __init__(
        self, current_entitlement_ids: Set[str] | None = None, user_exists: bool = True
    ) -> None:
        self.calls: List[tuple] = []
        self._current_ids: Set[str] = current_entitlement_ids or set()
        self._disable_fails = False
        self._user_exists = user_exists

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
        if not self._user_exists:
            return OperationResult.error(
                OperationStatus.NOT_FOUND,
                message="User not found",
                error_code="USER_NOT_FOUND",
            )
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

    def assess(self, email: str, desired_state: DesiredUserState) -> OperationResult:
        self.calls.append(("assess", email))
        if not self._user_exists:
            return OperationResult.success(
                data=AdapterAssessment(
                    platform_user_exists=False,
                    current_entitlement_ids=set(),
                )
            )
        return OperationResult.success(
            data=AdapterAssessment(
                platform_user_exists=True,
                current_entitlement_ids=set(self._current_ids),
            )
        )


class FakeDirectory:
    """Static group/member fixtures. Configurable per-group membership and list_groups."""

    def __init__(
        self,
        is_member: bool = True,
        groups: Set[str] | None = None,
        user_group_slugs: Set[str] | None = None,
    ) -> None:
        self._is_member = is_member
        self._per_group: Dict[str, bool] = {}
        self._groups: Set[str] = groups or set()
        self._user_group_slugs: Set[str] | None = user_group_slugs

    def set_membership(self, group_slug: str, value: bool) -> None:
        self._per_group[group_slug] = value

    def get_user_groups(self, user_email: str) -> OperationResult:
        if self._user_group_slugs is not None:
            slugs = self._user_group_slugs
        else:
            slugs = {
                slug
                for slug in self._groups
                if self._per_group.get(slug, self._is_member)
            }
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

    def get_group_members(
        self, group_email: str, include_member_types: set | None = None
    ) -> OperationResult:
        return OperationResult.success(data=[])

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
    current_ids: Set[str] | None = None,
    user_exists: bool = True,
    adapter: FakeAdapter | None = None,
    discovered_groups: Set[str] | None = None,
) -> tuple[AccessSyncCoordinator, FakeAdapter]:
    if adapter is None:
        adapter = FakeAdapter(
            current_entitlement_ids=current_ids or set(), user_exists=user_exists
        )
    config = AccessSyncRuntimeConfig(
        dir_prefix="sg",
        platforms={
            platform: PlatformPolicy(
                authn_token="authn",
                authn_removal_mode=authn_removal_mode,
            )
        },
    )
    authn_slug = config.authn_group_slug(platform)
    if is_member:
        user_group_slugs = {authn_slug} | (discovered_groups or set())
    else:
        user_group_slugs = set()
    directory = FakeDirectory(
        is_member=is_member,
        groups=discovered_groups or set(),
        user_group_slugs=user_group_slugs,
    )
    membership_builder = DirectoryMembershipBuilder(directory)
    coordinator = AccessSyncCoordinator(
        adapters={platform: adapter},
        config=config,
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
    config = AccessSyncRuntimeConfig(
        dir_prefix="sg",
        platforms={"aws": PlatformPolicy()},
    )
    coordinator = AccessSyncCoordinator(
        adapters={},  # no adapter registered
        config=config,
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
    assert "provision_user" not in result.data.planned_actions
    exec_calls = [c for c in adapter.calls if c[0] not in {"assess"}]
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
def test_sync_user_entitlement_not_applied_when_not_in_group(make_runtime_config):
    """Entitlement is only applied when user is a member of the entitlement group."""
    adapter = FakeAdapter()
    directory = FakeDirectory(
        is_member=True, groups={"sg-aws-admin"}, user_group_slugs={"sg-aws-authn"}
    )
    # Member of authn but NOT of entitlement group
    directory.set_membership("sg-aws-admin", False)
    config = make_runtime_config()
    coordinator = AccessSyncCoordinator(
        adapters={"aws": adapter},
        config=config,
        membership_builder=DirectoryMembershipBuilder(directory),
    )
    result = coordinator.sync_user("alice@example.com", "aws")
    assert result.is_success
    call_names = [c[0] for c in adapter.calls]
    assert "ensure_user" not in call_names
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
