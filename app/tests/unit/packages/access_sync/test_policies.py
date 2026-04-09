"""Unit tests for access_sync policies module."""

import pytest

from packages.access_sync.policies import (
    AdapterCapabilities,
    DefaultEntitlementStrategy,
    EffectivePlatformPolicy,
    EntitlementMode,
    EntitlementRule,
    PatternEntitlementMapping,
    PlatformPolicy,
    PolicyEngine,
    resolve_effective_policy,
)


# ---------------------------------------------------------------------------
# PlatformPolicy helpers
# ---------------------------------------------------------------------------


def make_policy(
    platform: str = "aws",
    authn_removal_mode: str = "disable",
    rules=None,
) -> PlatformPolicy:
    return PlatformPolicy(
        platform=platform,
        authn_group_slug=f"sg-{platform}-authn",
        authn_mode="derived",
        authn_removal_mode=authn_removal_mode,
        entitlement_rules=rules or [],
    )


def make_rule(
    group_slug: str = "sg-aws-admin",
    entitlement_type: str = "permission_set",
    entitlement_id: str = "123456789012/AWSAdministratorAccess",
    mode: EntitlementMode = "sync_managed",
) -> EntitlementRule:
    return EntitlementRule(
        group_slug=group_slug,
        entitlement_type=entitlement_type,
        entitlement_id=entitlement_id,
        mode=mode,
    )


@pytest.mark.unit
def test_sync_managed_rules_filters_correctly():
    # Arrange
    rules = [
        make_rule(mode="sync_managed"),
        make_rule(entitlement_id="111/Ephemeral", mode="ephemeral"),
        make_rule(entitlement_id="222/Deactivated", mode="deactivated"),
    ]
    policy = make_policy(rules=rules)

    # Act
    result = policy.sync_managed_rules()

    # Assert
    assert len(result) == 1
    assert result[0].mode == "sync_managed"


@pytest.mark.unit
def test_ephemeral_entitlement_ids():
    # Arrange
    rules = [
        make_rule(entitlement_id="111/A", mode="sync_managed"),
        make_rule(entitlement_id="222/B", mode="ephemeral"),
    ]
    policy = make_policy(rules=rules)

    # Act
    ids = policy.ephemeral_entitlement_ids()

    # Assert
    assert ids == {"222/B"}


@pytest.mark.unit
def test_deactivated_entitlement_ids():
    # Arrange
    rules = [
        make_rule(entitlement_id="111/C", mode="deactivated"),
        make_rule(entitlement_id="222/D", mode="sync_managed"),
    ]
    policy = make_policy(rules=rules)

    # Act
    ids = policy.deactivated_entitlement_ids()

    # Assert
    assert ids == {"111/C"}


@pytest.mark.unit
def test_skip_entitlement_ids_union():
    # Arrange
    rules = [
        make_rule(entitlement_id="111/E", mode="ephemeral"),
        make_rule(entitlement_id="222/F", mode="deactivated"),
        make_rule(entitlement_id="333/G", mode="sync_managed"),
    ]
    policy = make_policy(rules=rules)

    # Act
    ids = policy.skip_entitlement_ids()

    # Assert
    assert ids == {"111/E", "222/F"}


@pytest.mark.unit
def test_effective_rules_default_prefix_adds_discovered_groups():
    # Arrange
    policy = PlatformPolicy(
        platform="aws",
        authn_group_slug="sg-aws-authn",
        authn_mode="derived",
        authn_removal_mode="delete",
        entitlement_rules=[],
        default_entitlement_strategy=DefaultEntitlementStrategy(
            kind="default_prefix",
            source_group_prefix="sg-aws-",
            exclude_group_slugs=["sg-aws-authn"],
            default_entitlement_type="group",
            entitlement_id_template="{token}",
        ),
    )

    # Act
    rules = policy.sync_managed_rules(
        discovered_group_slugs={"sg-aws-authn", "sg-aws-team1-admin"}
    )

    # Assert
    assert len(rules) == 1
    assert rules[0].group_slug == "sg-aws-team1-admin"
    assert rules[0].entitlement_id == "team1-admin"


@pytest.mark.unit
def test_effective_rules_pattern_map_supports_wildcards():
    # Arrange
    policy = PlatformPolicy(
        platform="appname2",
        authn_group_slug="sg-appname2-authn",
        authn_mode="derived",
        authn_removal_mode="delete",
        entitlement_rules=[],
        default_entitlement_strategy=DefaultEntitlementStrategy(
            kind="pattern_map",
            pattern_mappings=[
                PatternEntitlementMapping(
                    source_group_pattern="sg-appname2-first-pattern*",
                    entitlement_type="group",
                    entitlement_id="entitlement-x",
                ),
                PatternEntitlementMapping(
                    source_group_pattern="sg-appname2-second-pattern*",
                    entitlement_type="group",
                    entitlement_id="entitlement-y",
                ),
            ],
        ),
    )

    # Act
    rules = policy.sync_managed_rules(
        discovered_group_slugs={
            "sg-appname2-first-pattern-prod",
            "sg-appname2-second-pattern-dev",
        }
    )

    # Assert
    ids = {rule.entitlement_id for rule in rules}
    assert ids == {"entitlement-x", "entitlement-y"}


# ---------------------------------------------------------------------------
# PolicyEngine.plan_actions
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_plan_actions_user_should_exist_with_entitlements():
    # Arrange
    rule = make_rule(
        entitlement_type="permission_set",
        entitlement_id="123/AdminAccess",
        mode="sync_managed",
    )
    policy = make_policy(rules=[rule])
    capabilities = AdapterCapabilities(
        supports_disable=False,
        supports_delete=True,
        supported_entitlement_types={"permission_set"},
    )
    engine = PolicyEngine()

    # Act
    actions = engine.plan_actions(
        policy=policy,
        capabilities=capabilities,
        user_should_exist=True,
        required_entitlements=policy.sync_managed_rules(),
    )

    # Assert
    assert any(a.action == "ensure_user" for a in actions)
    assert any(
        a.action == "apply_entitlement" and a.entitlement_id == "123/AdminAccess"
        for a in actions
    )


@pytest.mark.unit
def test_plan_actions_user_should_not_exist_disable():
    # Arrange
    policy = make_policy(authn_removal_mode="disable")
    capabilities = AdapterCapabilities(
        supports_disable=True,
        supports_delete=True,
        supported_entitlement_types=set(),
    )
    engine = PolicyEngine()

    # Act
    actions = engine.plan_actions(
        policy=policy,
        capabilities=capabilities,
        user_should_exist=False,
        required_entitlements=[],
    )

    # Assert
    assert any(a.action == "disable_user" for a in actions)
    assert not any(a.action == "remove_user" for a in actions)


@pytest.mark.unit
def test_plan_actions_user_should_not_exist_delete():
    # Arrange
    policy = make_policy(authn_removal_mode="delete")
    capabilities = AdapterCapabilities(
        supports_disable=False,
        supports_delete=True,
        supported_entitlement_types=set(),
    )
    engine = PolicyEngine()

    # Act
    actions = engine.plan_actions(
        policy=policy,
        capabilities=capabilities,
        user_should_exist=False,
        required_entitlements=[],
    )

    # Assert
    assert any(a.action == "remove_user" for a in actions)


@pytest.mark.unit
def test_plan_actions_unsupported_entitlement_type_skipped():
    # Arrange: adapter only supports 'license', not 'permission_set'
    rule = make_rule(entitlement_type="permission_set", entitlement_id="123/Admin")
    policy = make_policy(rules=[rule])
    capabilities = AdapterCapabilities(
        supports_disable=False,
        supports_delete=True,
        supported_entitlement_types={"license"},
    )
    engine = PolicyEngine()

    # Act
    actions = engine.plan_actions(
        policy=policy,
        capabilities=capabilities,
        user_should_exist=True,
        required_entitlements=policy.sync_managed_rules(),
    )

    # Assert: ensure_user planned but no entitlement action
    assert any(a.action == "ensure_user" for a in actions)
    assert not any(a.action == "apply_entitlement" for a in actions)


# ---------------------------------------------------------------------------
# PlatformPolicy.with_ephemeral_entitlement
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_with_ephemeral_entitlement_preserves_all_fields():
    """Regression: with_ephemeral_entitlement must not drop default_entitlement_strategy."""
    # Arrange
    strategy = DefaultEntitlementStrategy(
        kind="default_prefix",
        source_group_prefix="sg-aws-",
    )
    policy = PlatformPolicy(
        platform="aws",
        authn_group_slug="sg-aws-authn",
        authn_mode="derived",
        authn_removal_mode="delete",
        entitlement_rules=[],
        default_entitlement_strategy=strategy,
    )

    # Act
    updated = policy.with_ephemeral_entitlement(
        entitlement_type="permission_set",
        entitlement_id="999/Privileged",
    )

    # Assert — strategy preserved, new ephemeral rule added, original unchanged
    assert updated.default_entitlement_strategy == strategy
    assert "999/Privileged" in updated.ephemeral_entitlement_ids()
    assert "999/Privileged" not in policy.ephemeral_entitlement_ids()
    assert updated is not policy


@pytest.mark.unit
def test_with_ephemeral_entitlement_returns_new_policy():
    """PlatformPolicy.with_ephemeral_entitlement must return a new frozen instance."""
    # Arrange
    policy = make_policy(platform="aws")

    # Act
    updated = policy.with_ephemeral_entitlement(
        entitlement_type="permission_set",
        entitlement_id="123/EphemeralGrant",
    )

    # Assert — original unchanged, new instance has the rule
    assert updated is not policy
    assert "123/EphemeralGrant" in updated.ephemeral_entitlement_ids()
    assert "123/EphemeralGrant" not in policy.ephemeral_entitlement_ids()


# ---------------------------------------------------------------------------
# EffectivePlatformPolicy and resolve_effective_policy
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_resolve_effective_policy_no_strategy_returns_explicit_rules():
    """With no strategy, effective policy contains only the explicitly declared rules."""
    rule = make_rule()
    policy = make_policy(rules=[rule])
    effective = resolve_effective_policy(policy)
    assert effective.entitlement_rules == [rule]
    assert effective.platform == policy.platform
    assert effective.authn_removal_mode == policy.authn_removal_mode


@pytest.mark.unit
def test_resolve_effective_policy_with_strategy_includes_discovered_rules():
    """Strategy-generated rules are folded into effective policy when group slugs are supplied."""
    policy = PlatformPolicy(
        platform="aws",
        authn_group_slug="sg-aws-authn",
        authn_mode="derived",
        authn_removal_mode="delete",
        entitlement_rules=[],
        default_entitlement_strategy=DefaultEntitlementStrategy(
            kind="default_prefix",
            source_group_prefix="sg-aws-",
            exclude_group_slugs=["sg-aws-authn"],
            default_entitlement_type="group",
            entitlement_id_template="{token}",
        ),
    )
    effective = resolve_effective_policy(
        policy, discovered_group_slugs={"sg-aws-team1"}
    )
    assert len(effective.sync_managed_rules()) == 1
    assert effective.sync_managed_rules()[0].group_slug == "sg-aws-team1"


@pytest.mark.unit
def test_effective_policy_sync_managed_rules_no_args():
    """EffectivePlatformPolicy.sync_managed_rules() requires no arguments."""
    rules = [
        EntitlementRule("sg-a", "group", "id-1", "sync_managed"),
        EntitlementRule("sg-b", "group", "id-2", "ephemeral"),
    ]
    effective = EffectivePlatformPolicy(
        platform="aws",
        authn_group_slug="sg-aws-authn",
        authn_mode="derived",
        authn_removal_mode="delete",
        entitlement_rules=rules,
    )
    assert effective.sync_managed_rules() == [rules[0]]
    assert effective.ephemeral_entitlement_ids() == {"id-2"}
    assert effective.skip_entitlement_ids() == {"id-2"}


@pytest.mark.unit
def test_policy_engine_plan_actions_accepts_effective_policy():
    """PolicyEngine.plan_actions() must work when passed an EffectivePlatformPolicy."""
    rule = EntitlementRule("sg-a", "permission_set", "123/Admin", "sync_managed")
    effective = EffectivePlatformPolicy(
        platform="aws",
        authn_group_slug="sg-aws-authn",
        authn_mode="derived",
        authn_removal_mode="delete",
        entitlement_rules=[rule],
    )
    caps = AdapterCapabilities(
        supports_disable=True,
        supports_delete=True,
        supported_entitlement_types={"permission_set"},
    )
    engine = PolicyEngine()
    actions = engine.plan_actions(
        policy=effective,
        capabilities=caps,
        user_should_exist=True,
        required_entitlements=effective.sync_managed_rules(),
    )
    assert any(a.action == "ensure_user" for a in actions)
    assert any(a.action == "apply_entitlement" for a in actions)
