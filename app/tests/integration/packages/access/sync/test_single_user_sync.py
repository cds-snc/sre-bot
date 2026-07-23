"""Integration tests for AccessSyncApplicationService.sync_user.

Exercises the complete single-user sync pipeline end-to-end using
FakeDirectory and SpyAdapter from conftest so no real external APIs are
involved.
"""

import pytest

from packages.access.sync.domain import SyncOutcome

pytestmark = pytest.mark.integration

_USER = "test.user@example.com"
_ALICE = "alice@example.com"


# ---------------------------------------------------------------------------
# D1: Catchall user already provisioned — MUST plan zero actions
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_should_plan_no_actions_when_catchall_user_is_already_provisioned(
    make_coordinator,
):
    coordinator, adapter = make_coordinator(
        mode_overrides={"scratch": "ephemeral"},
        discovered_slugs={"sg-aws-scratch"},
        transitive_membership_slugs={"sg-aws-authn"},
        user_direct_group_slugs={"sg-aws-scratch"},
        current_entitlement_ids=set(),
        user_exists=True,
    )

    result = coordinator.sync_user(_USER, "aws")

    assert result.is_success
    assert isinstance(result.data, SyncOutcome)
    assert result.data.planned_actions == [], f"Unexpected actions: {result.data.planned_actions}"
    assert result.data.applied_actions == []
    reconcile_calls = [c for c in adapter.calls if c[0] == "reconcile_user"]
    assert len(reconcile_calls) == 1
    assert reconcile_calls[0][1] == _USER


# ---------------------------------------------------------------------------
# D1b: Adapter returns empty set — user exists with no groups
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_should_recognize_user_exists_when_adapter_returns_empty_group_set(
    make_coordinator,
):
    coordinator, adapter = make_coordinator(
        user_direct_group_slugs=set(),
        user_exists=True,
        current_entitlement_ids=set(),
    )

    result = coordinator.sync_user(_USER, "aws")

    assert result.is_success, f"sync_user failed: {result.error_code}"
    assert result.data.planned_actions == [], (
        f"User exists on platform with correct entitlements but coordinator planned: {result.data.planned_actions}."
    )
    reconcile_calls = [c for c in adapter.calls if c[0] == "reconcile_user"]
    assert len(reconcile_calls) == 1


# ---------------------------------------------------------------------------
# D2: New user — provision_user
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_should_plan_and_apply_provision_user_for_new_authn_member(
    make_coordinator,
):
    coordinator, adapter = make_coordinator(user_exists=False)

    result = coordinator.sync_user(_ALICE, "aws")

    assert result.is_success
    assert "provision_user" in result.data.planned_actions
    assert "provision_user" in result.data.applied_actions
    assert any(c[0] == "ensure_user" for c in adapter.calls)


# ---------------------------------------------------------------------------
# D3: Missing entitlement — apply_entitlement
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_should_plan_apply_entitlement_when_user_missing_required_group(
    make_coordinator,
):
    coordinator, adapter = make_coordinator(
        discovered_slugs={"sg-aws-admin"},
        user_direct_group_slugs={"sg-aws-admin"},
        current_entitlement_ids=set(),
        user_exists=True,
    )

    result = coordinator.sync_user(_ALICE, "aws")

    assert result.is_success
    assert "apply_entitlement" in result.data.planned_actions
    assert "apply_entitlement" in result.data.applied_actions


# ---------------------------------------------------------------------------
# D4: Extra entitlement — remove_entitlement
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_should_plan_remove_entitlement_when_user_has_extra_group_on_platform(
    make_coordinator,
):
    coordinator, adapter = make_coordinator(
        discovered_slugs={"sg-aws-readonly"},
        user_direct_group_slugs=set(),
        current_entitlement_ids={"readonly"},
        user_exists=True,
    )

    result = coordinator.sync_user(_ALICE, "aws")

    assert result.is_success
    assert "remove_entitlement" in result.data.planned_actions
    assert "remove_entitlement" in result.data.applied_actions


# ---------------------------------------------------------------------------
# D5: User removed from authn — remove_user (delete mode)
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_should_plan_remove_user_when_not_in_authn_group(make_coordinator):
    coordinator, adapter = make_coordinator(
        authn_removal_mode="delete",
        transitive_membership_slugs=set(),
        user_direct_group_slugs=set(),
        current_entitlement_ids=set(),
        user_exists=True,
    )

    result = coordinator.sync_user(_ALICE, "aws")

    assert result.is_success
    assert "remove_user" in result.data.planned_actions
    assert "remove_user" in result.data.applied_actions
    assert any(c[0] == "remove_user" for c in adapter.calls)


# ---------------------------------------------------------------------------
# D6: Dry-run — planned but not applied
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_should_not_apply_actions_in_dry_run_mode(make_coordinator):
    coordinator, adapter = make_coordinator(user_exists=False)

    result = coordinator.sync_user(_ALICE, "aws", dry_run=True)

    assert result.is_success
    assert result.data.applied_actions == []
    assert "provision_user" in result.data.planned_actions
    assert not any(c[0] == "ensure_user" for c in adapter.calls)


# ---------------------------------------------------------------------------
# D7: Unknown platform → POLICY_NOT_FOUND
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_should_return_policy_not_found_for_unconfigured_platform(make_coordinator):
    coordinator, _ = make_coordinator()

    result = coordinator.sync_user(_ALICE, "unknown_platform")

    assert not result.is_success
    assert result.error_code == "POLICY_NOT_FOUND"


# ---------------------------------------------------------------------------
# D8: Catchall WITHOUT ephemeral override — entitlement IS planned
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_should_plan_apply_entitlement_when_catchall_group_is_sync_managed(
    make_coordinator,
):
    coordinator, adapter = make_coordinator(
        mode_overrides={},
        discovered_slugs={"sg-aws-scratch"},
        transitive_membership_slugs={"sg-aws-authn"},
        user_direct_group_slugs={"sg-aws-scratch"},
        current_entitlement_ids=set(),
        user_exists=True,
    )

    result = coordinator.sync_user(_USER, "aws")

    assert result.is_success
    assert "apply_entitlement" in result.data.planned_actions
