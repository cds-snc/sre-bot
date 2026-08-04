"""Unit tests for access_sync policies module."""

import pytest

from packages.access.common.config import (
    AccessRuntimeConfig as AccessSyncRuntimeConfig,
)
from packages.access.common.config import (
    PlatformPolicy,
)
from packages.access.sync.policies import (
    AdapterCapabilities,
    EffectivePlatformPolicy,
    EntitlementRule,
    PlanningContext,
    PolicyEngine,
    resolve_effective_policy,
)

# ---------------------------------------------------------------------------
# Local helpers (policies-specific)
# ---------------------------------------------------------------------------


def make_effective(
    platform: str = "aws",
    authn_group_slug: str = "sg-aws-authn",
    authn_removal_mode: str = "delete",
    rules: list | None = None,
) -> EffectivePlatformPolicy:
    return EffectivePlatformPolicy(
        platform=platform,
        authn_group_slug=authn_group_slug,
        authn_removal_mode=authn_removal_mode,
        entitlement_rules=rules or [],
    )


def make_planning_context(
    platform: str = "aws",
    authn_removal_mode: str = "delete",
    rules: list | None = None,
) -> PlanningContext:
    return PlanningContext(
        platform=platform,
        authn_removal_mode=authn_removal_mode,
        entitlement_rules=rules or [],
    )


def make_rule(
    group_slug: str = "sg-aws-admin",
    entitlement_id: str = "admin",
    entitlement_type: str = "group",
    mode: str = "sync_managed",
) -> EntitlementRule:
    return EntitlementRule(
        group_slug=group_slug,
        entitlement_id=entitlement_id,
        entitlement_type=entitlement_type,
        mode=mode,
    )


# ---------------------------------------------------------------------------
# PlatformPolicy
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_platform_policy_defaults():
    policy = PlatformPolicy()
    assert policy.authn_token == "authn"
    assert policy.authn_removal_mode == "delete"
    assert policy.mode_overrides == {}


@pytest.mark.unit
def test_platform_policy_custom_values():
    policy = PlatformPolicy(
        authn_token="login",
        authn_removal_mode="disable",
        mode_overrides={"breakglass": "ephemeral"},
    )
    assert policy.authn_token == "login"
    assert policy.authn_removal_mode == "disable"
    assert policy.mode_overrides == {"breakglass": "ephemeral"}


# ---------------------------------------------------------------------------
# AccessSyncRuntimeConfig slug derivation
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_group_prefix_derives_from_dir_prefix_and_platform(make_runtime_config):
    config = make_runtime_config(platform="aws", dir_prefix="sg", dir_separator="-")
    assert config.group_prefix("aws") == "sg-aws-"


@pytest.mark.unit
def test_group_prefix_custom_separator():
    config = AccessSyncRuntimeConfig(
        dir_prefix="corp",
        dir_separator=".",
        platforms={"gcp": PlatformPolicy()},
    )
    assert config.group_prefix("gcp") == "corp.gcp."


@pytest.mark.unit
def test_authn_group_slug_derives_correctly(make_runtime_config):
    config = make_runtime_config(platform="aws", authn_token="authn")
    assert config.authn_group_slug("aws") == "sg-aws-authn"


@pytest.mark.unit
def test_authn_group_slug_custom_token():
    config = AccessSyncRuntimeConfig(
        dir_prefix="sg",
        dir_separator="-",
        platforms={"aws": PlatformPolicy(authn_token="login")},
    )
    assert config.authn_group_slug("aws") == "sg-aws-login"


# ---------------------------------------------------------------------------
# resolve_effective_policy
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_resolve_effective_policy_excludes_authn_group(make_runtime_config):
    config = make_runtime_config(platform="aws", authn_token="authn")
    discovered = {"sg-aws-authn", "sg-aws-admin"}
    effective = resolve_effective_policy(config, "aws", discovered)
    slugs = {r.group_slug for r in effective.entitlement_rules}
    assert "sg-aws-authn" not in slugs
    assert "sg-aws-admin" in slugs


@pytest.mark.unit
def test_resolve_effective_policy_excludes_non_platform_slugs(make_runtime_config):
    config = make_runtime_config(platform="aws")
    discovered = {"sg-aws-admin", "sg-gcp-viewer", "other-group"}
    effective = resolve_effective_policy(config, "aws", discovered)
    slugs = {r.group_slug for r in effective.entitlement_rules}
    assert all(s.startswith("sg-aws-") for s in slugs)


@pytest.mark.unit
def test_resolve_effective_policy_strips_prefix_for_entitlement_id(make_runtime_config):
    config = make_runtime_config(platform="aws")
    discovered = {"sg-aws-finops-readonly"}
    effective = resolve_effective_policy(config, "aws", discovered)
    assert len(effective.entitlement_rules) == 1
    assert effective.entitlement_rules[0].entitlement_id == "finops-readonly"
    assert effective.entitlement_rules[0].group_slug == "sg-aws-finops-readonly"


@pytest.mark.unit
def test_resolve_effective_policy_excludes_ephemeral_override(make_runtime_config):
    config = make_runtime_config(
        platform="aws",
        mode_overrides={"breakglass-admin": "ephemeral"},
    )
    discovered = {"sg-aws-admin", "sg-aws-breakglass-admin"}
    effective = resolve_effective_policy(config, "aws", discovered)
    slugs = {r.group_slug for r in effective.entitlement_rules}
    assert "sg-aws-breakglass-admin" not in slugs
    assert "sg-aws-admin" in slugs


@pytest.mark.unit
def test_resolve_effective_policy_excludes_deactivated_override(make_runtime_config):
    config = make_runtime_config(
        platform="aws",
        mode_overrides={"legacy-access": "deactivated"},
    )
    discovered = {"sg-aws-legacy-access", "sg-aws-finops"}
    effective = resolve_effective_policy(config, "aws", discovered)
    slugs = {r.group_slug for r in effective.entitlement_rules}
    assert "sg-aws-legacy-access" not in slugs
    assert "sg-aws-finops" in slugs


@pytest.mark.unit
def test_resolve_effective_policy_returns_correct_metadata(make_runtime_config):
    config = make_runtime_config(
        platform="aws",
        authn_token="authn",
        authn_removal_mode="delete",
    )
    discovered = {"sg-aws-admin"}
    effective = resolve_effective_policy(config, "aws", discovered)
    assert effective.platform == "aws"
    assert effective.authn_group_slug == "sg-aws-authn"
    assert effective.authn_removal_mode == "delete"


@pytest.mark.unit
def test_resolve_effective_policy_empty_discovery(make_runtime_config):
    config = make_runtime_config(platform="aws")
    effective = resolve_effective_policy(config, "aws", set())
    assert effective.entitlement_rules == []


@pytest.mark.unit
def test_resolve_effective_policy_normalizes_slug_case(make_runtime_config):
    config = make_runtime_config(platform="aws")
    discovered = {"SG-AWS-Admin"}
    effective = resolve_effective_policy(config, "aws", discovered)
    slugs = {r.group_slug for r in effective.entitlement_rules}
    assert "sg-aws-admin" in slugs


# ---------------------------------------------------------------------------
# PolicyEngine.plan_actions -- uses PlanningContext
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_plan_actions_user_should_exist_with_entitlements():
    rule = make_rule(entitlement_type="group", entitlement_id="admin")
    effective = make_planning_context(authn_removal_mode="delete", rules=[rule])
    capabilities = AdapterCapabilities(
        supports_disable=False,
        supports_delete=True,
        supported_entitlement_types={"group"},
    )
    engine = PolicyEngine()
    actions = engine.plan_actions(
        policy=effective,
        capabilities=capabilities,
        user_should_exist=True,
        required_entitlements=[rule],
        platform_user_exists=False,
    )

    assert any(a.action == "provision_user" for a in actions)
    assert any(a.action == "apply_entitlement" and a.entitlement_id == "admin" for a in actions)


@pytest.mark.unit
def test_plan_actions_user_should_not_exist_delete():
    effective = make_planning_context(authn_removal_mode="delete")
    capabilities = AdapterCapabilities(
        supports_disable=False,
        supports_delete=True,
        supported_entitlement_types=set(),
    )
    engine = PolicyEngine()

    actions = engine.plan_actions(
        policy=effective,
        capabilities=capabilities,
        user_should_exist=False,
        required_entitlements=[],
        platform_user_exists=True,
    )
    assert any(a.action == "remove_user" for a in actions)
    assert not any(a.action == "disable_user" for a in actions)


@pytest.mark.unit
def test_plan_actions_user_should_not_exist_already_absent():
    """No lifecycle action when user_should_exist=False and platform_user_exists=False."""
    effective = make_planning_context(authn_removal_mode="delete")
    capabilities = AdapterCapabilities(
        supports_disable=False,
        supports_delete=True,
        supported_entitlement_types=set(),
    )
    engine = PolicyEngine()

    actions = engine.plan_actions(
        policy=effective,
        capabilities=capabilities,
        user_should_exist=False,
        required_entitlements=[],
        platform_user_exists=False,
    )
    assert not any(a.action in {"remove_user", "disable_user"} for a in actions)


@pytest.mark.unit
def test_plan_actions_user_should_not_exist_disable():
    effective = make_planning_context(authn_removal_mode="disable")
    capabilities = AdapterCapabilities(
        supports_disable=True,
        supports_delete=True,
        supported_entitlement_types=set(),
    )
    engine = PolicyEngine()

    actions = engine.plan_actions(
        policy=effective,
        capabilities=capabilities,
        user_should_exist=False,
        required_entitlements=[],
        platform_user_exists=True,
    )

    assert any(a.action == "disable_user" for a in actions)
    assert not any(a.action == "remove_user" for a in actions)


@pytest.mark.unit
def test_plan_actions_removes_stale_entitlements():
    rule = make_rule(entitlement_id="admin")
    effective = make_planning_context(rules=[rule])
    capabilities = AdapterCapabilities(
        supports_disable=True,
        supports_delete=True,
        supported_entitlement_types={"group"},
    )
    engine = PolicyEngine()

    actions = engine.plan_actions(
        policy=effective,
        capabilities=capabilities,
        user_should_exist=True,
        required_entitlements=[],
        current_entitlement_ids={"admin"},
        platform_user_exists=True,
    )
    assert any(a.action == "remove_entitlement" and a.entitlement_id == "admin" for a in actions)


@pytest.mark.unit
def test_plan_actions_no_removal_when_current_ids_unknown():
    rule = make_rule(entitlement_id="admin")
    effective = make_planning_context(rules=[rule])
    capabilities = AdapterCapabilities(
        supports_disable=True,
        supports_delete=True,
        supported_entitlement_types={"group"},
    )
    engine = PolicyEngine()
    actions = engine.plan_actions(
        policy=effective,
        capabilities=capabilities,
        user_should_exist=True,
        required_entitlements=[],
        current_entitlement_ids=None,
        platform_user_exists=True,
    )

    assert not any(a.action == "remove_entitlement" for a in actions)


@pytest.mark.unit
def test_plan_actions_entitlement_only_removal_mode_no_lifecycle():
    """entitlement_only mode: no lifecycle action planned when user should not exist."""
    effective = make_planning_context(authn_removal_mode="entitlement_only")
    capabilities = AdapterCapabilities(
        supports_disable=True,
        supports_delete=True,
        supported_entitlement_types=set(),
    )
    engine = PolicyEngine()

    actions = engine.plan_actions(
        policy=effective,
        capabilities=capabilities,
        user_should_exist=False,
        required_entitlements=[],
    )
    lifecycle = [a.action for a in actions if a.action in {"disable_user", "remove_user"}]
    assert lifecycle == []
