"""Unit tests for coordinator collaborator classes.

Covers:
  TargetResolver           — policy/adapter lookup and error cases.
  PlatformPrefetchPlanner  — orphan detection and entitlement prefetch.
  OptimizationStrategy     — lifecycle-delta subject selection.
"""

import pytest
from typing import Set
from unittest.mock import MagicMock

from infrastructure.operations import OperationResult, OperationStatus
from packages.access.sync.reconciliation import (
    OptimizationStrategy,
    PlatformPrefetchPlanner,
    TargetResolver,
)


# ---------------------------------------------------------------------------
# Local helpers (file-specific)
# ---------------------------------------------------------------------------


def _make_adapter(
    provisioned_users: Set[str] | None = None,
    entitlement_map: dict | None = None,
) -> MagicMock:
    adapter = MagicMock()
    if provisioned_users is not None:
        adapter.list_all_provisioned_users.return_value = OperationResult.success(
            data=provisioned_users
        )
    else:
        adapter.list_all_provisioned_users.return_value = OperationResult.error(
            OperationStatus.PERMANENT_ERROR,
            message="Not supported",
            error_code="UNSUPPORTED_OPERATION",
        )
    return adapter


def _make_log() -> MagicMock:
    return MagicMock()


# ---------------------------------------------------------------------------
# TargetResolver
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_target_resolver_returns_policy_and_adapter_when_both_configured(
    make_runtime_config,
):
    """Should resolve policy and adapter for a known platform."""
    config = make_runtime_config()
    fake_adapter = MagicMock()
    resolver = TargetResolver(adapters={"aws": fake_adapter}, config=config)

    policy, adapter, error = resolver.resolve("aws")

    assert policy is not None
    assert adapter is fake_adapter
    assert error is None


@pytest.mark.unit
def test_target_resolver_returns_error_when_no_policy(make_runtime_config):
    """Should return POLICY_NOT_FOUND when platform has no config."""
    config = make_runtime_config()
    resolver = TargetResolver(adapters={}, config=config)

    policy, adapter, error = resolver.resolve("unknown_platform")

    assert policy is None
    assert adapter is None
    assert error is not None
    assert error.error_code == "POLICY_NOT_FOUND"


@pytest.mark.unit
def test_target_resolver_returns_error_when_no_adapter(make_runtime_config):
    """Should return ADAPTER_NOT_FOUND when policy exists but no adapter is registered."""
    config = make_runtime_config()
    # No adapter in the registry
    resolver = TargetResolver(adapters={}, config=config)

    # Platform "aws" has a policy but no adapter
    policy, adapter, error = resolver.resolve("aws")

    assert policy is None
    assert adapter is None
    assert error is not None
    assert error.error_code == "ADAPTER_NOT_FOUND"


# ---------------------------------------------------------------------------
# PlatformPrefetchPlanner — detect_orphans
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_prefetch_planner_detects_orphans_correctly():
    """Users provisioned on the platform but absent from IDP are orphans."""
    provisioned = {"alice@example.com", "bob@example.com", "carol@example.com"}
    idp_members = {"alice@example.com", "bob@example.com"}
    adapter = _make_adapter(provisioned_users=provisioned)
    planner = PlatformPrefetchPlanner()

    prov_set, prov_known, orphans = planner.detect_orphans(
        adapter=adapter, idp_members=idp_members, log=_make_log()
    )

    assert prov_known is True
    assert orphans == {"carol@example.com"}
    assert prov_set == provisioned


@pytest.mark.unit
def test_prefetch_planner_detect_orphans_handles_unsupported():
    """When adapter cannot list users, orphan set should be empty (not an error)."""
    adapter = _make_adapter(provisioned_users=None)
    planner = PlatformPrefetchPlanner()

    prov_set, prov_known, orphans = planner.detect_orphans(
        adapter=adapter, idp_members={"alice@example.com"}, log=_make_log()
    )

    assert prov_known is False
    assert orphans == set()
    assert prov_set == set()


@pytest.mark.unit
def test_prefetch_planner_no_orphans_when_all_idp_members_provisioned():
    """Should return empty orphans when every provisioned user is in the IDP."""
    provisioned = {"alice@example.com", "bob@example.com"}
    adapter = _make_adapter(provisioned_users=provisioned)
    planner = PlatformPrefetchPlanner()

    _prov_set, _prov_known, orphans = planner.detect_orphans(
        adapter=adapter, idp_members=provisioned, log=_make_log()
    )

    assert orphans == set()


# ---------------------------------------------------------------------------
# OptimizationStrategy
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_optimization_strategy_returns_all_subjects_when_sync_managed_present(
    make_adapter_capabilities,
):
    """When sync_managed entitlement rules exist, all candidates must be processed."""
    strategy = OptimizationStrategy()
    idp_members = {"alice@example.com", "bob@example.com"}
    provisioned = {"alice@example.com"}

    _candidates, subjects, optimized = strategy.select_subjects(
        idp_members=idp_members,
        orphans=set(),
        precomputed_current_ids={},
        provisioned=provisioned,
        provisioned_known=True,
        has_sync_managed=True,  # entitlement rules present → no shortcut
        capabilities=make_adapter_capabilities(supports_bulk_user_delta=True),
        log=_make_log(),
    )

    # All candidates processed, lifecycle delta NOT activated
    assert subjects == idp_members
    assert optimized is False


@pytest.mark.unit
def test_optimization_strategy_activates_lifecycle_delta_when_eligible(
    make_adapter_capabilities,
):
    """When adapter supports bulk_user_delta and no sync_managed rules, only deltas are processed."""
    strategy = OptimizationStrategy()
    idp_members = {"alice@example.com", "bob@example.com", "carol@example.com"}
    provisioned = {"alice@example.com", "bob@example.com"}
    orphans: Set[str] = set()

    _candidates, subjects, optimized = strategy.select_subjects(
        idp_members=idp_members,
        orphans=orphans,
        precomputed_current_ids={},
        provisioned=provisioned,
        provisioned_known=True,
        has_sync_managed=False,  # lifecycle only
        capabilities=make_adapter_capabilities(supports_bulk_user_delta=True),
        log=_make_log(),
    )

    # Only carol (new IDP member) is processed — alice and bob already provisioned
    assert subjects == {"carol@example.com"}
    assert optimized is True


@pytest.mark.unit
def test_optimization_strategy_includes_orphans_in_lifecycle_delta(
    make_adapter_capabilities,
):
    """Orphans must always be included in the subject set even with lifecycle delta."""
    strategy = OptimizationStrategy()
    idp_members = {"alice@example.com"}
    provisioned = {"alice@example.com", "orphan@example.com"}
    orphans = {"orphan@example.com"}

    _candidates, subjects, optimized = strategy.select_subjects(
        idp_members=idp_members,
        orphans=orphans,
        precomputed_current_ids={},
        provisioned=provisioned,
        provisioned_known=True,
        has_sync_managed=False,
        capabilities=make_adapter_capabilities(supports_bulk_user_delta=True),
        log=_make_log(),
    )

    assert "orphan@example.com" in subjects
    assert optimized is True


@pytest.mark.unit
def test_optimization_strategy_skips_lifecycle_delta_when_adapter_does_not_support_bulk(
    make_adapter_capabilities,
):
    """Lifecycle delta should NOT activate when adapter lacks bulk_user_delta."""
    strategy = OptimizationStrategy()
    idp_members = {"alice@example.com", "bob@example.com"}
    provisioned = {"alice@example.com"}

    _candidates, subjects, optimized = strategy.select_subjects(
        idp_members=idp_members,
        orphans=set(),
        precomputed_current_ids={},
        provisioned=provisioned,
        provisioned_known=True,
        has_sync_managed=False,
        capabilities=make_adapter_capabilities(supports_bulk_user_delta=False),
        log=_make_log(),
    )

    # Must fall back to all candidates
    assert subjects == idp_members
    assert optimized is False
