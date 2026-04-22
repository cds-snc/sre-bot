"""Integration tests for AccessSyncCoordinator.sync_user.

Exercises the complete single-user sync pipeline end-to-end using
``FakeDirectory`` and ``SpyAdapter`` from conftest so no real external
APIs are involved.

Scenarios covered:

  D1  **The catchall-user bug scenario** — user reaches authn transitively
      via sg-aws-scratch (a subgroup of sg-aws-authn), is already provisioned
      on the platform, and holds no entitlements.  Because the catchall token
      is marked ephemeral in ``mode_overrides``, zero actions must be planned.
      This is the exact scenario that was producing a spurious ``provision_user``
      in the runtime logs.

  D2  New user in authn group, not yet provisioned → ``provision_user`` planned
      and applied.

  D3  Provisioned user missing a required entitlement group →
      ``apply_entitlement`` planned and applied.

  D4  Provisioned user holds an entitlement group they should no longer have →
      ``remove_entitlement`` planned and applied.

  D5  User not in authn, provisioned → ``remove_user`` (delete mode) planned
      and applied.

  D6  Dry-run mode — actions planned but none applied; adapter not called for
      mutations.

  D7  Unknown platform → ``POLICY_NOT_FOUND`` error returned.

  D8  Catchall user without mode_override — sg-aws-scratch IS sync-managed →
      ``apply_entitlement`` planned (proves the override is required to suppress
      the entitlement).
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
    """
    Reproduces the bug scenario observed in runtime logs:

    Setup
    -----
    * IDP:  test.user is a direct member of sg-aws-scratch only.
            sg-aws-scratch is a subgroup of sg-aws-authn (transitive).
    * Config: mode_overrides={"scratch": "ephemeral"} — catchall not sync-managed.
    * Platform: test.user exists, no group memberships.

    Expected
    --------
    * user_should_exist=True  (reached authn transitively)
    * required_entitlements=[]  (catchall is ephemeral, excluded from policy)
    * platform_user_exists=True
    * planned_actions=[]  — NO changes needed
    """
    # Arrange
    coordinator, adapter = make_coordinator(
        mode_overrides={"scratch": "ephemeral"},
        discovered_slugs={"sg-aws-scratch"},
        transitive_membership_slugs={"sg-aws-authn"},
        user_direct_group_slugs={"sg-aws-scratch"},
        current_entitlement_ids=set(),
        user_exists=True,
    )

    # Act
    result = coordinator.sync_user(_USER, "aws")

    # Assert
    assert result.is_success
    assert isinstance(result.data, SyncOutcome)
    assert (
        result.data.planned_actions == []
    ), f"Expected no actions but got: {result.data.planned_actions}"
    assert result.data.applied_actions == []
    # Adapter must NOT have called ensure_user or apply_entitlement
    mutation_calls = [
        c[0] for c in adapter.calls if c[0] != "get_current_entitlement_ids"
    ]
    assert mutation_calls == [], f"Unexpected adapter mutations: {mutation_calls}"
    # Validate that adapter.get_current_entitlement_ids() WAS called and returned
    # success(set()) for user with no groups — proving platform_user_exists=True
    get_current_calls = [
        c for c in adapter.calls if c[0] == "get_current_entitlement_ids"
    ]
    assert (
        len(get_current_calls) == 1
    ), f"Expected one get_current_entitlement_ids call but got {len(get_current_calls)}"
    # The call must have been for the correct user
    assert get_current_calls[0][1] == _USER


# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# D1b: Adapter returns success(empty set) — user exists with no groups
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_should_recognize_user_exists_when_adapter_returns_empty_group_set(
    make_coordinator,
):
    """
    CRITICAL PATH: Validates coordinator correctly interprets adapter response.

    This test isolates the exact scenario that was failing in production logs.

    When adapter.get_current_entitlement_ids(user) returns:
        OperationResult.success(data=set())  — User exists, zero group memberships

    The coordinator must:
        1. Set platform_user_exists=True  (NOT False)
        2. Plan NO actions if user_should_exist=True and no required entitlements

    This validates that an empty set is NOT treated the same as NOT_FOUND.
    If this assertion fails, the bug from production logs has regressed.
    """
    # Arrange: Minimal setup
    # - User in authn (user_should_exist=True)
    # - No sync-managed groups (required_entitlements=[])
    # - Platform: user exists with zero groups (adapter returns success(set()))
    coordinator, adapter = make_coordinator(
        # IDP state: authn member with no sync-managed groups
        user_direct_group_slugs=set(),  # No sync-managed groups
        # Platform state: user exists, no groups
        user_exists=True,
        current_entitlement_ids=set(),
    )

    # Act
    result = coordinator.sync_user(_USER, "aws")

    # Assert: No actions planned because user is in sync (exists + no entitlements)
    assert result.is_success, f"sync_user failed: {result.error_code}"
    assert result.data.planned_actions == [], (
        f"User exists on platform with correct entitlements but "
        f"coordinator planned: {result.data.planned_actions}. "
        f"This indicates platform_user_exists was incorrectly computed as False."
    )
    # Verify the adapter was consulted
    get_current_calls = [
        c for c in adapter.calls if c[0] == "get_current_entitlement_ids"
    ]
    assert len(get_current_calls) >= 1, "Adapter must be queried for current state"


@pytest.mark.integration
def test_should_not_plan_provision_when_not_found_is_recovered_from_inventory(
    make_coordinator,
):
    """Recover platform presence via list_all_provisioned_users on false NOT_FOUND.

    This mirrors the real incident shape:
    - IDP says user should exist
    - required entitlements are empty
    - point entitlement lookup returns NOT_FOUND
    - platform inventory still contains the user

    Expected: no actions planned.
    """
    coordinator, adapter = make_coordinator(
        user_direct_group_slugs=set(),
        user_exists=False,
        current_entitlement_ids=set(),
        provisioned_users={_USER},
    )

    result = coordinator.sync_user(_USER, "aws")

    assert result.is_success
    assert result.data.planned_actions == []
    assert result.data.applied_actions == []
    assert any(call[0] == "list_all_provisioned_users" for call in adapter.calls)


# D2: New user — provision_user
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_should_plan_and_apply_provision_user_for_new_authn_member(
    make_coordinator,
):
    """New user in authn group, not yet on platform → provision_user."""
    # Arrange
    coordinator, adapter = make_coordinator(
        user_exists=False,
    )

    # Act
    result = coordinator.sync_user(_ALICE, "aws")

    # Assert
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
    """User in authn + sg-aws-admin but platform has no groups → apply_entitlement."""
    # Arrange
    coordinator, adapter = make_coordinator(
        discovered_slugs={"sg-aws-admin"},
        user_direct_group_slugs={"sg-aws-admin"},
        current_entitlement_ids=set(),
        user_exists=True,
    )

    # Act
    result = coordinator.sync_user(_ALICE, "aws")

    # Assert
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
    """User no longer in sg-aws-readonly but platform still has it → remove_entitlement."""
    # Arrange
    coordinator, adapter = make_coordinator(
        discovered_slugs={"sg-aws-readonly"},
        # user_direct_group_slugs omitted → user is NOT in sg-aws-readonly
        user_direct_group_slugs=set(),
        current_entitlement_ids={"readonly"},  # platform still has the group
        user_exists=True,
    )

    # Act
    result = coordinator.sync_user(_ALICE, "aws")

    # Assert
    assert result.is_success
    assert "remove_entitlement" in result.data.planned_actions
    assert "remove_entitlement" in result.data.applied_actions


# ---------------------------------------------------------------------------
# D5: User removed from authn — remove_user (delete mode)
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_should_plan_remove_user_when_not_in_authn_group(
    make_coordinator,
):
    """User left authn group; delete removal mode → remove_user."""
    # Arrange
    coordinator, adapter = make_coordinator(
        authn_removal_mode="delete",
        transitive_membership_slugs=set(),  # NOT in authn
        user_direct_group_slugs=set(),
        current_entitlement_ids=set(),
        user_exists=True,
    )

    # Act
    result = coordinator.sync_user(_ALICE, "aws")

    # Assert
    assert result.is_success
    assert "remove_user" in result.data.planned_actions
    assert "remove_user" in result.data.applied_actions
    assert any(c[0] == "remove_user" for c in adapter.calls)


# ---------------------------------------------------------------------------
# D6: Dry-run — planned but not applied
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_should_not_apply_actions_in_dry_run_mode(
    make_coordinator,
):
    """Dry-run: provision_user planned but ensure_user must NOT be called."""
    # Arrange
    coordinator, adapter = make_coordinator(
        user_exists=False,
    )

    # Act
    result = coordinator.sync_user(_ALICE, "aws", dry_run=True)

    # Assert
    assert result.is_success
    assert result.data.applied_actions == []
    assert "provision_user" in result.data.planned_actions
    assert not any(c[0] == "ensure_user" for c in adapter.calls)


# ---------------------------------------------------------------------------
# D7: Unknown platform → POLICY_NOT_FOUND
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_should_return_policy_not_found_for_unconfigured_platform(
    make_coordinator,
):
    """Requesting sync for a platform with no policy → POLICY_NOT_FOUND."""
    # Arrange
    coordinator, _ = make_coordinator()

    # Act
    result = coordinator.sync_user(_ALICE, "unknown_platform")

    # Assert
    assert not result.is_success
    assert result.error_code == "POLICY_NOT_FOUND"


# ---------------------------------------------------------------------------
# D8: Catchall WITHOUT ephemeral override — entitlement IS planned
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_should_plan_apply_entitlement_when_catchall_group_is_sync_managed(
    make_coordinator,
):
    """
    When sg-aws-scratch has NO mode_override, it is sync_managed.
    The user is a direct member → apply_entitlement must be planned.

    This confirms that the ephemeral override in D1 is the mechanism that
    suppresses the spurious entitlement — without it the entitlement IS correct.
    """
    # Arrange — no mode_override, scratch is sync_managed
    coordinator, adapter = make_coordinator(
        mode_overrides={},  # scratch is sync_managed
        discovered_slugs={"sg-aws-scratch"},
        transitive_membership_slugs={"sg-aws-authn"},
        user_direct_group_slugs={"sg-aws-scratch"},
        current_entitlement_ids=set(),
        user_exists=True,
    )

    # Act
    result = coordinator.sync_user(_USER, "aws")

    # Assert
    assert result.is_success
    # Without the override, the entitlement IS required; apply_entitlement planned
    assert "apply_entitlement" in result.data.planned_actions
