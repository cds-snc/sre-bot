"""Integration tests for AccessSyncApplicationService.sync_platform.

Exercises the full batch-reconciliation pipeline end-to-end using
``FakeDirectory`` and ``SpyAdapter`` from conftest.

Scenarios covered:

  E1  Batch with authn members — all users in desired states receive the
      correct outcomes (provisioned + no extra actions).

  E2  Orphan detection — user provisioned on the platform but absent from
      the authn group is detected and marked for removal.

  E3  Entitlement application in batch — users in sync-managed groups
      receive apply_entitlement during reconciliation.

  E4  Dry-run — reconciliation outcome populated, no mutations applied.

  E5  Unknown platform → POLICY_NOT_FOUND error returned.
"""

import pytest

from packages.access.sync.domain import ReconciliationOutcome

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# E1: Basic batch — authn members are reconciled
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_should_return_reconciliation_outcome_for_authn_members(
    make_coordinator,
):
    """sync_platform returns ReconciliationOutcome with platform set correctly.

    Note: when all IDP members are already provisioned and there are no
    sync-managed entitlement rules, the lifecycle-delta optimisation fires
    and no subjects need to be processed (users_synced=0 is correct — zero
    changes required).
    """
    # Arrange
    authn_members = ["alice@example.com", "bob@example.com"]
    coordinator, adapter = make_coordinator(
        group_members={"sg-aws-authn": authn_members},
        provisioned_users={"alice@example.com", "bob@example.com"},
    )

    # Act
    result = coordinator.sync_platform("aws")

    # Assert
    assert result.is_success
    assert isinstance(result.data, ReconciliationOutcome)
    assert result.data.platform == "aws"
    assert result.data.dry_run is False


@pytest.mark.integration
def test_should_provision_all_authn_members_not_yet_on_platform(
    make_coordinator,
):
    """Users in authn but absent on the platform receive provision_user."""
    # Arrange — neither user is provisioned yet
    authn_members = ["alice@example.com", "bob@example.com"]
    coordinator, adapter = make_coordinator(
        group_members={"sg-aws-authn": authn_members},
        user_exists=False,
        provisioned_users=set(),
    )

    # Act
    result = coordinator.sync_platform("aws")

    # Assert
    assert result.is_success
    ensure_calls = [c for c in adapter.calls if c[0] == "ensure_user"]
    assert len(ensure_calls) == 2
    ensured_emails = {c[1] for c in ensure_calls}
    assert ensured_emails == {"alice@example.com", "bob@example.com"}


# ---------------------------------------------------------------------------
# E2: Orphan detection
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_should_detect_and_remove_orphaned_users(
    make_coordinator,
):
    """User provisioned on platform but no longer in authn → remove_user."""
    # Arrange
    # carol is on the platform but NOT in authn (not in group_members)
    authn_members = ["alice@example.com"]
    coordinator, adapter = make_coordinator(
        group_members={"sg-aws-authn": authn_members},
        provisioned_users={"alice@example.com", "carol@example.com"},  # carol is extra
        user_exists=True,
        current_entitlement_ids=set(),
    )

    # Act
    result = coordinator.sync_platform("aws")

    # Assert
    assert result.is_success
    assert result.data.orphans_found == 1
    remove_calls = [c for c in adapter.calls if c[0] == "remove_user"]
    removed = {c[1] for c in remove_calls}
    assert "carol@example.com" in removed


@pytest.mark.integration
def test_should_report_zero_orphans_when_platform_matches_idp(
    make_coordinator,
):
    """When platform membership matches IDP exactly, no orphans detected."""
    # Arrange
    authn_members = ["alice@example.com", "bob@example.com"]
    coordinator, adapter = make_coordinator(
        group_members={"sg-aws-authn": authn_members},
        provisioned_users={"alice@example.com", "bob@example.com"},
    )

    # Act
    result = coordinator.sync_platform("aws")

    # Assert
    assert result.is_success
    assert result.data.orphans_found == 0


# ---------------------------------------------------------------------------
# E3: Entitlement application in batch
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_should_apply_entitlements_for_authn_members_in_sync_managed_groups(
    make_coordinator,
):
    """Users in a sync-managed group receive apply_entitlement during batch sync."""
    # Arrange
    coordinator, adapter = make_coordinator(
        discovered_slugs={"sg-aws-admin"},
        group_members={
            "sg-aws-authn": ["alice@example.com"],
            "sg-aws-admin": ["alice@example.com"],
        },
        provisioned_users={"alice@example.com"},
        current_entitlement_ids=set(),  # platform has no groups yet
        adapter_group_members={},
    )

    # Act
    result = coordinator.sync_platform("aws")

    # Assert
    assert result.is_success
    apply_calls = [c for c in adapter.calls if c[0] == "apply_entitlement"]
    assert len(apply_calls) == 1
    assert apply_calls[0][1] == "alice@example.com"


# ---------------------------------------------------------------------------
# E4: Dry-run — no mutations
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_should_populate_outcome_but_apply_no_mutations_in_dry_run(
    make_coordinator,
):
    """Dry-run: outcome populated with planned actions, no ensure_user called."""
    # Arrange
    authn_members = ["alice@example.com"]
    coordinator, adapter = make_coordinator(
        group_members={"sg-aws-authn": authn_members},
        user_exists=False,
        provisioned_users=set(),
    )

    # Act
    result = coordinator.sync_platform("aws", dry_run=True)

    # Assert
    assert result.is_success
    assert result.data.dry_run is True
    # No mutations must have been applied
    mutation_calls = [
        c
        for c in adapter.calls
        if c[0]
        in {
            "ensure_user",
            "disable_user",
            "remove_user",
            "apply_entitlement",
            "remove_entitlement",
        }
    ]
    assert mutation_calls == []


# ---------------------------------------------------------------------------
# E5: Unknown platform → error
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_should_return_error_for_unconfigured_platform(
    make_coordinator,
):
    """sync_platform for a platform with no policy → POLICY_NOT_FOUND."""
    # Arrange
    coordinator, _ = make_coordinator()

    # Act
    result = coordinator.sync_platform("nonexistent")

    # Assert
    assert not result.is_success
    assert result.error_code == "POLICY_NOT_FOUND"
