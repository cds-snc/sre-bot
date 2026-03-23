"""Unit tests for AccessSyncService.

Covers F-01 (OperationResult[SyncOutcome] contract), F-05 (UNSUPPORTED_OPERATION
manual action), and D-01 (per-user entitlement group qualification).
"""

import pytest

from infrastructure.directory.models import (
    DirectoryGroup,
    MembershipCheckResult,
)
from infrastructure.operations import OperationResult, OperationStatus
from packages.access_sync.models import SyncOutcome
from packages.access_sync.policies import (
    AdapterCapabilities,
    EntitlementRule,
    PlatformPolicy,
    PolicyRegistry,
)
from packages.access_sync.registry import AccessSyncRegistry
from packages.access_sync.user_sync.service import UserSyncService


class FakeAdapter:
    """Test double for adapter. Tracks calls for assertion."""

    def __init__(self, current_entitlement_ids=None):
        self.calls = []
        self._current_ids = current_entitlement_ids or set()

    def capabilities(self):
        return AdapterCapabilities(
            supports_disable=False,
            supports_delete=True,
            supported_entitlement_types={"permission_set"},
        )

    def ensure_user(self, email):
        self.calls.append(("ensure_user", email))
        return OperationResult.success()

    def disable_user(self, email):
        self.calls.append(("disable_user", email))
        return OperationResult.error(
            OperationStatus.PERMANENT_ERROR,
            message="Disable not supported",
            error_code="UNSUPPORTED_OPERATION",
        )

    def remove_user(self, email):
        self.calls.append(("remove_user", email))
        return OperationResult.success(message="removed")

    def apply_entitlement(self, email, etype, eid):
        self.calls.append(("apply_entitlement", email, etype, eid))
        return OperationResult.success()

    def remove_entitlement(self, email, etype, eid):
        self.calls.append(("remove_entitlement", email, etype, eid))
        return OperationResult.success()

    def get_current_entitlement_ids(self, email):
        self.calls.append(("get_current_entitlement_ids", email))
        return OperationResult.success(data=set(self._current_ids))


class FakeDirectoryProvider:
    """Test double for directory provider."""

    def __init__(self, is_member=True):
        self.is_member = is_member

    def get_group(self, slug):
        return OperationResult.success(
            data=DirectoryGroup(
                group_email=f"{slug}@example.com",
                group_slug=slug,
                provider_group_id=f"gid-{slug}",
            )
        )

    def check_membership(self, group_email, user_email):
        return OperationResult.success(
            data=MembershipCheckResult(
                group_email=group_email,
                group_slug=group_email.split("@")[0],
                provider_group_id=None,
                user_email=user_email,
                is_member=self.is_member,
            )
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_service(
    is_member=True,
    platform="aws",
    rules=None,
    authn_removal_mode="delete",
    current_ids=None,
):
    """Create a minimal test service."""
    adapter = FakeAdapter(current_entitlement_ids=current_ids or set())
    policy = PlatformPolicy(
        platform=platform,
        authn_group_slug=f"sg-{platform}-authn",
        authn_mode="derived",
        authn_removal_mode=authn_removal_mode,
        entitlement_rules=rules or [],
    )
    registry = AccessSyncRegistry(adapters={platform: adapter})
    policies = PolicyRegistry(policies={platform: policy})
    directory = FakeDirectoryProvider(is_member=is_member)
    service = UserSyncService(registry=registry, policies=policies, directory=directory)
    return service, adapter


# ---------------------------------------------------------------------------
# Tests — F-01: OperationResult[SyncOutcome] boundary contract
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_sync_user_returns_operation_result_with_sync_outcome():
    """F-01: sync_user returns OperationResult[SyncOutcome], not a custom type."""
    service, _ = make_service(is_member=True)
    result = service.sync_user("alice@example.com", "aws")

    assert isinstance(result, OperationResult)
    assert result.is_success
    assert isinstance(result.data, SyncOutcome)


@pytest.mark.unit
def test_sync_user_member_applies_ensure_user():
    """Member: ensure_user action is executed and appears in applied_actions."""
    service, adapter = make_service(is_member=True)
    result = service.sync_user("alice@example.com", "aws")

    assert result.is_success
    assert "ensure_user" in result.data.applied_actions
    assert any(c[0] == "ensure_user" for c in adapter.calls)


@pytest.mark.unit
def test_sync_user_non_member_removes_user():
    """Non-member: remove_user action is planned and executed."""
    service, adapter = make_service(is_member=False, authn_removal_mode="delete")
    result = service.sync_user("alice@example.com", "aws")

    assert result.is_success
    assert "remove_user" in result.data.applied_actions


# ---------------------------------------------------------------------------
# Tests — F-05: UNSUPPORTED_OPERATION = requires_manual_action
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_sync_user_disable_mode_sets_requires_manual_action():
    """F-05: disable_user returning UNSUPPORTED_OPERATION sets requires_manual_action=True."""
    service, adapter = make_service(is_member=False, authn_removal_mode="disable")
    result = service.sync_user("alice@example.com", "aws")

    assert result.is_success
    assert result.data.requires_manual_action is True


# ---------------------------------------------------------------------------
# Tests — D-01: per-user entitlement group qualification
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_sync_user_does_not_apply_entitlement_when_not_in_group():
    """D-01: entitlement is only applied when user IS a member of the entitlement group."""
    rule = EntitlementRule(
        group_slug="sg-aws-admin",
        entitlement_type="permission_set",
        entitlement_id="123456789012/AWSAdministratorAccess",
        mode="sync_managed",
    )
    # User is member of authn group but NOT of the entitlement group.
    # We model this by using a FakeDirectoryProvider with per-group control.
    adapter = FakeAdapter()
    policy = PlatformPolicy(
        platform="aws",
        authn_group_slug="sg-aws-authn",
        authn_mode="derived",
        authn_removal_mode="delete",
        entitlement_rules=[rule],
    )

    class SelectiveMembershipProvider(FakeDirectoryProvider):
        """Member of authn group only, not of the entitlement group."""

        def check_membership(self, group_email, user_email):
            is_member = "authn" in group_email  # only authn group
            return OperationResult.success(
                data=MembershipCheckResult(
                    group_email=group_email,
                    group_slug=group_email.split("@")[0],
                    provider_group_id=None,
                    user_email=user_email,
                    is_member=is_member,
                )
            )

    service = UserSyncService(
        registry=AccessSyncRegistry(adapters={"aws": adapter}),
        policies=PolicyRegistry(policies={"aws": policy}),
        directory=SelectiveMembershipProvider(),
    )
    result = service.sync_user("alice@example.com", "aws")

    assert result.is_success
    # ensure_user should be called but NOT apply_entitlement
    action_names = [c[0] for c in adapter.calls]
    assert "ensure_user" in action_names
    assert "apply_entitlement" not in action_names


@pytest.mark.unit
def test_compute_desired_state_member():
    """Authn group member → user_should_exist=True."""
    service, _ = make_service(is_member=True)
    result = service.compute_desired_state("alice@example.com", "aws")
    assert result.is_success
    assert result.data is True


@pytest.mark.unit
def test_compute_desired_state_non_member():
    """Not in authn group → user_should_exist=False."""
    service, _ = make_service(is_member=False)
    result = service.compute_desired_state("alice@example.com", "aws")
    assert result.is_success
    assert result.data is False


@pytest.mark.unit
def test_sync_user_dry_run_returns_planned_actions():
    """Dry-run returns planned actions without executing them."""
    service, adapter = make_service(is_member=True)
    result = service.sync_user("alice@example.com", "aws", dry_run=True)

    assert result.is_success
    assert isinstance(result.data, SyncOutcome)
    assert len(result.data.applied_actions) >= 1
    # No adapter calls should have been made (only get_current_entitlement_ids is OK)
    execution_calls = [
        c for c in adapter.calls if c[0] != "get_current_entitlement_ids"
    ]
    assert execution_calls == []
