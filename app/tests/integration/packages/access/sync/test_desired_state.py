"""Integration tests for DirectoryMembershipBuilder.

Verifies that IDP group membership data is correctly translated into
``DesiredUserState`` objects consumed by the coordinator and PolicyEngine.

All IDP calls are handled by ``FakeDirectory`` from conftest — no real
Google Workspace API calls are made.

Scenarios covered:

  A1  User reaches authn via a transitive subgroup (catchall pattern).
      check_membership returns True; get_user_groups returns only the
      direct catchall group.  When the catchall token is ephemeral the
      desired state must carry zero required entitlements.

  A2  User is a direct member of the authn group AND a sync-managed
      entitlement group.  Both the lifecycle flag and the entitlement
      rule must appear in the desired state.

  A3  User is not a member of the authn group.  user_should_exist must
      be False and required_entitlements must be empty.

  A4  User is in authn and in a group whose token is ephemeral.
      The ephemeral group must not produce an entitlement rule.

  A5  User is in authn but get_user_groups returns a group that is NOT
      in the effective policy (e.g. a foreign-platform group).
      Required entitlements must remain empty.

  B1  Platform-state build happy path.

  B2  IDP batch-membership failure must propagate, never surface as a
      success carrying an empty desired membership map (TASK-77).

  B3  A per-rule NOT_FOUND group lookup remains a legitimate skip.

  B4  A per-rule non-NOT_FOUND group lookup failure must propagate.

  B5  A per-rule group outside the managed domain must propagate as a
      hard error rather than being silently skipped.

  C1  Group discovery returns the platform-prefixed slugs and filters out
      foreign-platform groups.

  C2  An IDP failure during group discovery must propagate, never surface
      as a success carrying an empty slug set (TASK-78).
"""

import pytest

from infrastructure.directory.models import DirectoryGroup
from infrastructure.operations import OperationResult, OperationStatus
from packages.access.common.config import AccessRuntimeConfig as AccessSyncRuntimeConfig
from packages.access.common.config import PlatformPolicy
from packages.access.common.group_policy import ManagedGroupPolicy
from packages.access.sync.desired_state import DirectoryMembershipBuilder
from packages.access.sync.policies import resolve_effective_policy

from .conftest import FakeDirectory

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_builder_and_effective(
    *,
    discovered_slugs: set,
    transitive_membership_slugs: set,
    user_direct_group_slugs: set,
    mode_overrides: dict | None = None,
    platform: str = "aws",
) -> tuple:
    """Return (DirectoryMembershipBuilder, EffectivePlatformPolicy)."""
    config = AccessSyncRuntimeConfig(
        dir_prefix="sg",
        dir_domain="example.com",
        platforms={
            platform: PlatformPolicy(
                authn_token="authn",
                authn_removal_mode="delete",
                mode_overrides=mode_overrides or {},
            )
        },
    )
    directory = FakeDirectory(
        discovered_slugs=discovered_slugs,
        transitive_membership_slugs=transitive_membership_slugs,
        user_direct_group_slugs=user_direct_group_slugs,
    )
    builder = DirectoryMembershipBuilder(directory, ManagedGroupPolicy.from_config(config))
    effective = resolve_effective_policy(config, platform, discovered_slugs)
    return builder, effective


# ---------------------------------------------------------------------------
# A1: Transitive authn membership via catchall — zero entitlements
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_should_mark_user_as_existing_when_authn_reached_via_catchall():
    """User in sg-aws-scratch (subgroup of sg-aws-authn) → user_should_exist=True."""
    # Arrange
    builder, effective = _make_builder_and_effective(
        discovered_slugs={"sg-aws-scratch"},
        transitive_membership_slugs={"sg-aws-authn"},  # authn check returns True
        user_direct_group_slugs={"sg-aws-scratch"},  # get_user_groups: direct only
        mode_overrides={"scratch": "ephemeral"},  # catchall excluded from sync
    )

    # Act
    result = builder.build_user_state_from_effective(
        user_email="test.user@example.com",
        effective=effective,
    )

    # Assert
    assert result.is_success
    assert result.data is not None
    assert result.data.user_should_exist is True


@pytest.mark.integration
def test_should_require_no_entitlements_when_catchall_is_ephemeral():
    """sg-aws-scratch is ephemeral → required_entitlements must be empty."""
    # Arrange
    builder, effective = _make_builder_and_effective(
        discovered_slugs={"sg-aws-scratch"},
        transitive_membership_slugs={"sg-aws-authn"},
        user_direct_group_slugs={"sg-aws-scratch"},
        mode_overrides={"scratch": "ephemeral"},
    )

    # Act
    result = builder.build_user_state_from_effective(
        user_email="test.user@example.com",
        effective=effective,
    )

    # Assert
    assert result.is_success
    assert result.data.required_entitlements == []


# ---------------------------------------------------------------------------
# A2: Direct authn member with a sync-managed entitlement group
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_should_require_entitlement_when_user_is_direct_member_of_sync_managed_group():
    """User in sg-aws-authn AND sg-aws-admin (sync-managed) → one entitlement rule."""
    # Arrange
    builder, effective = _make_builder_and_effective(
        discovered_slugs={"sg-aws-admin"},
        transitive_membership_slugs={"sg-aws-authn"},
        user_direct_group_slugs={"sg-aws-admin"},  # direct member of admin
        mode_overrides={},  # all sync_managed by default
    )

    # Act
    result = builder.build_user_state_from_effective(
        user_email="alice@example.com",
        effective=effective,
    )

    # Assert
    assert result.is_success
    assert result.data.user_should_exist is True
    assert len(result.data.required_entitlements) == 1
    assert result.data.required_entitlements[0].group_slug == "sg-aws-admin"


@pytest.mark.integration
def test_should_collect_all_entitlements_when_user_in_multiple_sync_managed_groups():
    """User in sg-aws-admin AND sg-aws-readonly → two entitlement rules."""
    # Arrange
    builder, effective = _make_builder_and_effective(
        discovered_slugs={"sg-aws-admin", "sg-aws-readonly"},
        transitive_membership_slugs={"sg-aws-authn"},
        user_direct_group_slugs={"sg-aws-admin", "sg-aws-readonly"},
        mode_overrides={},
    )

    # Act
    result = builder.build_user_state_from_effective(
        user_email="alice@example.com",
        effective=effective,
    )

    # Assert
    assert result.is_success
    assert len(result.data.required_entitlements) == 2
    slugs = {r.group_slug for r in result.data.required_entitlements}
    assert slugs == {"sg-aws-admin", "sg-aws-readonly"}


# ---------------------------------------------------------------------------
# A3: User not in authn group
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_should_mark_user_as_absent_when_not_in_authn_group():
    """check_membership returns False → user_should_exist=False."""
    # Arrange
    builder, effective = _make_builder_and_effective(
        discovered_slugs=set(),
        transitive_membership_slugs=set(),  # no group has True membership
        user_direct_group_slugs=set(),
        mode_overrides={},
    )

    # Act
    result = builder.build_user_state_from_effective(
        user_email="contractor@external.com",
        effective=effective,
    )

    # Assert
    assert result.is_success
    assert result.data.user_should_exist is False
    assert result.data.required_entitlements == []


@pytest.mark.integration
def test_should_require_no_entitlements_when_user_absent_from_authn():
    """Even if user is in a sync-managed group, no entitlements without authn."""
    # Arrange
    builder, effective = _make_builder_and_effective(
        discovered_slugs={"sg-aws-admin"},
        transitive_membership_slugs=set(),  # not in authn
        user_direct_group_slugs={"sg-aws-admin"},  # direct group member
        mode_overrides={},
    )

    # Act
    result = builder.build_user_state_from_effective(
        user_email="contractor@external.com",
        effective=effective,
    )

    # Assert
    assert result.is_success
    assert result.data.user_should_exist is False
    assert result.data.required_entitlements == []


# ---------------------------------------------------------------------------
# A4: Ephemeral token excluded from entitlements
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_should_exclude_ephemeral_group_from_required_entitlements():
    """A group with mode=ephemeral must not produce an entitlement rule."""
    # Arrange
    builder, effective = _make_builder_and_effective(
        discovered_slugs={"sg-aws-breakglass"},
        transitive_membership_slugs={"sg-aws-authn"},
        user_direct_group_slugs={"sg-aws-breakglass"},
        mode_overrides={"breakglass": "ephemeral"},
    )

    # Act
    result = builder.build_user_state_from_effective(
        user_email="alice@example.com",
        effective=effective,
    )

    # Assert
    assert result.is_success
    assert result.data.user_should_exist is True
    assert result.data.required_entitlements == []


# ---------------------------------------------------------------------------
# A5: Foreign platform group ignored
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_should_not_include_entitlement_for_group_outside_effective_policy():
    """A group the user belongs to that is not in the effective policy is ignored."""
    # Arrange — sg-gcp-viewer is not in discovered_slugs so never in effective policy
    builder, effective = _make_builder_and_effective(
        discovered_slugs={"sg-aws-readonly"},
        transitive_membership_slugs={"sg-aws-authn"},
        user_direct_group_slugs={"sg-gcp-viewer"},  # different platform
        mode_overrides={},
    )

    # Act
    result = builder.build_user_state_from_effective(
        user_email="alice@example.com",
        effective=effective,
    )

    # Assert
    assert result.is_success
    assert result.data.user_should_exist is True
    assert result.data.required_entitlements == []


# ---------------------------------------------------------------------------
# B: build_platform_state_from_effective
# ---------------------------------------------------------------------------


def _make_platform_builder_and_effective(
    *,
    discovered_slugs: set,
    group_members: dict | None = None,
    batch_members_result: OperationResult | None = None,
    group_result_by_slug: dict | None = None,
    platform: str = "aws",
) -> tuple:
    """Return (DirectoryMembershipBuilder, EffectivePlatformPolicy) for platform builds."""
    config = AccessSyncRuntimeConfig(
        dir_prefix="sg",
        dir_domain="example.com",
        platforms={
            platform: PlatformPolicy(
                authn_token="authn",
                authn_removal_mode="delete",
                mode_overrides={},
            )
        },
    )
    directory = FakeDirectory(
        discovered_slugs=discovered_slugs,
        group_members=group_members or {},
        batch_members_result=batch_members_result,
        group_result_by_slug=group_result_by_slug,
    )
    builder = DirectoryMembershipBuilder(directory, ManagedGroupPolicy.from_config(config))
    effective = resolve_effective_policy(config, platform, discovered_slugs)
    return builder, effective


@pytest.mark.integration
def test_should_build_platform_state_from_authn_and_entitlement_groups():
    """Happy path: desired members are authn members present in each entitlement group."""
    # Arrange
    builder, effective = _make_platform_builder_and_effective(
        discovered_slugs={"sg-aws-admin", "sg-aws-readonly"},
        group_members={
            "sg-aws-authn": ["alice@example.com", "bob@example.com"],
            "sg-aws-admin": ["alice@example.com", "ghost@example.com"],
            "sg-aws-readonly": ["bob@example.com"],
        },
    )

    # Act
    result = builder.build_platform_state_from_effective(effective)

    # Assert
    assert result.is_success
    assert result.data is not None
    assert result.data.desired_users == {"alice@example.com", "bob@example.com"}
    assert result.data.desired_members_by_entitlement == {
        "admin": {"alice@example.com"},
        "readonly": {"bob@example.com"},
    }
    assert result.data.entitlement_slug_by_id == {
        "admin": "sg-aws-admin",
        "readonly": "sg-aws-readonly",
    }


@pytest.mark.integration
def test_should_propagate_error_when_batch_members_fetch_fails():
    """A failing get_group_members_batch must not surface as success with empty members."""
    # Arrange
    builder, effective = _make_platform_builder_and_effective(
        discovered_slugs={"sg-aws-admin", "sg-aws-readonly"},
        group_members={
            "sg-aws-authn": ["alice@example.com"],
            "sg-aws-admin": ["alice@example.com"],
        },
        batch_members_result=OperationResult.error(
            OperationStatus.TRANSIENT_ERROR,
            message="rate limited",
            error_code="429",
            retry_after=30,
        ),
    )

    # Act
    result = builder.build_platform_state_from_effective(effective)

    # Assert
    assert not result.is_success
    assert result.status == OperationStatus.TRANSIENT_ERROR
    assert result.error_code == "429"
    assert result.retry_after == 30
    assert result.data is None


@pytest.mark.integration
def test_should_skip_entitlement_when_group_not_found():
    """NOT_FOUND on a rule's group is legitimate absence: skip only that entitlement."""
    # Arrange
    builder, effective = _make_platform_builder_and_effective(
        discovered_slugs={"sg-aws-admin", "sg-aws-readonly"},
        group_members={
            "sg-aws-authn": ["alice@example.com", "bob@example.com"],
            "sg-aws-readonly": ["bob@example.com"],
        },
        group_result_by_slug={
            "sg-aws-admin": OperationResult.error(
                OperationStatus.NOT_FOUND,
                message="group not found",
                error_code="GROUP_NOT_FOUND",
            )
        },
    )

    # Act
    result = builder.build_platform_state_from_effective(effective)

    # Assert
    assert result.is_success
    assert result.data is not None
    assert "admin" not in result.data.desired_members_by_entitlement
    assert result.data.desired_members_by_entitlement["readonly"] == {"bob@example.com"}


@pytest.mark.integration
def test_should_propagate_error_when_group_lookup_transiently_fails():
    """A non-NOT_FOUND per-rule failure must fail the whole build, not skip the rule."""
    # Arrange
    builder, effective = _make_platform_builder_and_effective(
        discovered_slugs={"sg-aws-admin", "sg-aws-readonly"},
        group_members={
            "sg-aws-authn": ["alice@example.com", "bob@example.com"],
            "sg-aws-readonly": ["bob@example.com"],
        },
        group_result_by_slug={
            "sg-aws-admin": OperationResult.error(
                OperationStatus.TRANSIENT_ERROR,
                message="backend error",
                error_code="503",
                retry_after=15,
            )
        },
    )

    # Act
    result = builder.build_platform_state_from_effective(effective)

    # Assert
    assert not result.is_success
    assert result.status == OperationStatus.TRANSIENT_ERROR
    assert result.error_code == "503"
    assert result.data is None


@pytest.mark.integration
def test_should_propagate_error_when_rule_group_is_outside_managed_domain():
    """An explicitly configured out-of-domain group is a fault, not a silent skip."""
    # Arrange
    builder, effective = _make_platform_builder_and_effective(
        discovered_slugs={"sg-aws-admin", "sg-aws-readonly"},
        group_members={
            "sg-aws-authn": ["alice@example.com", "bob@example.com"],
            "sg-aws-readonly": ["bob@example.com"],
        },
        group_result_by_slug={
            "sg-aws-admin": OperationResult.success(
                data=DirectoryGroup(
                    group_email="sg-aws-admin@other-tenant.com",
                    group_slug="sg-aws-admin",
                    provider_group_id="gid-sg-aws-admin",
                )
            )
        },
    )

    # Act
    result = builder.build_platform_state_from_effective(effective)

    # Assert
    assert not result.is_success
    assert result.error_code == "DIRECTORY_GROUP_DOMAIN_MISMATCH"


# ---------------------------------------------------------------------------
# C: discover_group_slugs
# ---------------------------------------------------------------------------


def _make_discovery_builder(
    *,
    discovered_slugs: set,
    list_groups_result: OperationResult | None = None,
    platform: str = "aws",
) -> tuple:
    """Return (DirectoryMembershipBuilder, AccessSyncRuntimeConfig) for discovery."""
    config = AccessSyncRuntimeConfig(
        dir_prefix="sg",
        dir_domain="example.com",
        platforms={
            platform: PlatformPolicy(
                authn_token="authn",
                authn_removal_mode="delete",
                mode_overrides={},
            )
        },
    )
    directory = FakeDirectory(
        discovered_slugs=discovered_slugs,
        list_groups_result=list_groups_result,
    )
    return DirectoryMembershipBuilder(directory, ManagedGroupPolicy.from_config(config)), config


@pytest.mark.integration
def test_should_discover_matching_group_slugs():
    """Happy path: prefixed slugs are returned, non-matching slugs filtered out."""
    # Arrange
    builder, config = _make_discovery_builder(
        discovered_slugs={"sg-aws-admin", "sg-aws-readonly", "sg-gcp-viewer"},
    )

    # Act
    result = builder.discover_group_slugs(config, "aws")

    # Assert
    assert result.is_success
    assert result.data == {"sg-aws-admin", "sg-aws-readonly"}


@pytest.mark.integration
def test_should_propagate_error_when_group_discovery_fails():
    """A failing list_groups must not surface as success with an empty slug set."""
    # Arrange
    builder, config = _make_discovery_builder(
        discovered_slugs={"sg-aws-admin"},
        list_groups_result=OperationResult.error(
            OperationStatus.TRANSIENT_ERROR,
            message="rate limited",
            error_code="429",
            retry_after=30,
        ),
    )

    # Act
    result = builder.discover_group_slugs(config, "aws")

    # Assert
    assert not result.is_success
    assert result.status == OperationStatus.TRANSIENT_ERROR
    assert result.error_code == "429"
    assert result.retry_after == 30
    assert result.data is None
