"""Unit tests for FakePlatformAdapter."""

import pytest

from packages.access.sync.adapters.fake_platform import FakePlatformAdapter
from packages.access.sync.domain import (
    DesiredPlatformState,
    DesiredUserState,
    ReconciliationOutcome,
    SyncOutcome,
)
from packages.access.sync.policies import PlanningContext

_EFFECTIVE = PlanningContext(
    platform="fake",
    authn_removal_mode="delete",
    entitlement_rules=[],
)


@pytest.mark.unit
def test_fake_adapter_has_deterministic_seed_data():
    adapter = FakePlatformAdapter()
    users_result = adapter.list_all_provisioned_users()
    assert users_result.is_success
    assert users_result.data == {
        "alice@example.com",
        "bob@example.com",
        "carol@example.com",
    }


@pytest.mark.unit
def test_fake_adapter_apply_and_remove_group_entitlement_updates_state():
    adapter = FakePlatformAdapter()
    user_email = "dana@example.com"
    group_id = "fake-group-read"

    apply_result = adapter.apply_entitlement(
        user_email=user_email,
        entitlement_type="group",
        entitlement_id=group_id,
    )
    assert apply_result.is_success
    assert user_email in adapter._members_by_group[group_id]

    remove_result = adapter.remove_entitlement(
        user_email=user_email,
        entitlement_type="group",
        entitlement_id=group_id,
    )
    assert remove_result.is_success
    assert user_email not in adapter._members_by_group.get(group_id, set())


@pytest.mark.unit
def test_fake_adapter_reconcile_user_provisions_new_user():
    adapter = FakePlatformAdapter()
    desired = DesiredUserState(user_should_exist=True)

    result = adapter.reconcile_user("newuser@example.com", desired, _EFFECTIVE)

    assert result.is_success
    assert isinstance(result.data, SyncOutcome)
    assert "provision_user" in result.data.applied_actions
    assert "newuser@example.com" in adapter._users


@pytest.mark.unit
def test_fake_adapter_reconcile_user_removes_user_not_in_desired():
    adapter = FakePlatformAdapter()  # alice is seeded
    desired = DesiredUserState(user_should_exist=False)

    result = adapter.reconcile_user("alice@example.com", desired, _EFFECTIVE)

    assert result.is_success
    assert result.data is not None
    assert isinstance(result.data, SyncOutcome)
    assert "remove_user" in result.data.applied_actions
    assert "alice@example.com" not in adapter._users


@pytest.mark.unit
def test_fake_adapter_reconcile_platform_returns_outcome():
    adapter = FakePlatformAdapter()
    desired_state = DesiredPlatformState(
        desired_users={"alice@example.com", "bob@example.com"},
        desired_members_by_entitlement={},
        entitlement_slug_by_id={},
    )

    result = adapter.reconcile_platform(desired_state, _EFFECTIVE)

    assert result.is_success
    assert isinstance(result.data, ReconciliationOutcome)
    assert result.data.platform == "fake"


@pytest.mark.unit
def test_fake_adapter_reconcile_platform_dry_run_no_mutations():
    adapter = FakePlatformAdapter()
    users_before = set(adapter._users)
    desired_state = DesiredPlatformState(
        desired_users={"newuser@example.com"},
        desired_members_by_entitlement={},
        entitlement_slug_by_id={},
    )

    result = adapter.reconcile_platform(desired_state, _EFFECTIVE, dry_run=True)

    assert result.is_success
    assert result.data is not None
    assert isinstance(result.data, ReconciliationOutcome)
    assert result.data.dry_run is True
    assert adapter._users == users_before
