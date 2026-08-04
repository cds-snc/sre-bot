"""Integration tests for the access_sync adapter group-mapping pipeline.

These tests exercise the full chain from config construction through policy
resolution through adapter canonicalization — with no real AWS API calls.
The only boundary mocked is the AWS IdentityStore client; everything else
(AccessSyncRuntimeConfig, resolve_effective_policy, AwsIdentityCenterAdapter,
the group index build) runs for real.

This is the recommended way to verify the naming convention:

    IDP group slug  →  token (entitlement_id)  →  AWS IC GroupId
    sg-aws-{token}  →  {token}                 →  UUID from group index

Run with:
    pytest tests/integration/packages/access/sync/ -v
"""

import pytest

from packages.access.common.config import AccessRuntimeConfig as AccessSyncRuntimeConfig
from packages.access.sync.policies import resolve_effective_policy

from .conftest import make_adapter

# ---------------------------------------------------------------------------
# Config slug derivation
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_config_derives_correct_aws_prefix(aws_config: AccessSyncRuntimeConfig):
    """dir_prefix + dir_separator + platform produce the expected group prefix."""
    assert aws_config.group_prefix("aws") == "sg-aws-"


@pytest.mark.integration
def test_config_derives_correct_authn_slug(aws_config: AccessSyncRuntimeConfig):
    """group_prefix + authn_token produce the expected authn group slug."""
    assert aws_config.authn_group_slug("aws") == "sg-aws-authn"


# ---------------------------------------------------------------------------
# Policy resolution: IDP slug → entitlement_id (token)
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_resolve_effective_policy_strips_prefix_to_token(
    aws_config: AccessSyncRuntimeConfig,
):
    """sg-aws-{token} → entitlement_id={token} after resolve_effective_policy."""
    discovered = {
        "sg-aws-authn",  # excluded — this is the authn group
        "sg-aws-my-security-group",
        "sg-aws-finops-readonly",
    }
    effective = resolve_effective_policy(aws_config, "aws", discovered)

    token_map = {r.group_slug: r.entitlement_id for r in effective.entitlement_rules}
    assert token_map == {
        "sg-aws-my-security-group": "my-security-group",
        "sg-aws-finops-readonly": "finops-readonly",
    }


@pytest.mark.integration
def test_resolve_effective_policy_excludes_authn_group(
    aws_config: AccessSyncRuntimeConfig,
):
    """The authn group slug must never appear in the sync rules."""
    discovered = {"sg-aws-authn", "sg-aws-viewer"}
    effective = resolve_effective_policy(aws_config, "aws", discovered)

    slugs = {r.group_slug for r in effective.entitlement_rules}
    assert "sg-aws-authn" not in slugs


@pytest.mark.integration
def test_resolve_effective_policy_excludes_non_platform_slugs(
    aws_config: AccessSyncRuntimeConfig,
):
    """Groups from other platforms must not bleed into an aws effective policy."""
    discovered = {
        "sg-aws-admin",
        "sg-gcp-viewer",  # different platform
        "sg-fake-operator",  # different platform
        "unrelated-group",  # no matching prefix at all
    }
    effective = resolve_effective_policy(aws_config, "aws", discovered)

    slugs = {r.group_slug for r in effective.entitlement_rules}
    assert slugs == {"sg-aws-admin"}


# ---------------------------------------------------------------------------
# Adapter: token → AWS IC GroupId
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_adapter_resolves_token_to_group_id_exact_match(
    aws_config: AccessSyncRuntimeConfig,
):
    """Token matches AWS IC group display name exactly → GroupId returned."""
    discovered = {"sg-aws-my-security-group"}
    effective = resolve_effective_policy(aws_config, "aws", discovered)

    adapter, _ = make_adapter(
        [
            {"GroupId": "aaa-111-uuid", "DisplayName": "my-security-group"},
        ]
    )

    rule = effective.entitlement_rules[0]
    assert rule.entitlement_id == "my-security-group"

    result = adapter.canonicalize_entitlement_id("group", rule.entitlement_id)

    assert result.is_success, result.message
    assert result.data == "aaa-111-uuid"


@pytest.mark.integration
def test_adapter_resolves_token_to_group_id_normalized_match(
    aws_config: AccessSyncRuntimeConfig,
):
    """Token resolves via casefold when AWS IC uses mixed-case display name."""
    discovered = {"sg-aws-finops-readonly"}
    effective = resolve_effective_policy(aws_config, "aws", discovered)

    adapter, _ = make_adapter(
        [
            {"GroupId": "bbb-222-uuid", "DisplayName": "FinOps-ReadOnly"},
        ]
    )

    rule = effective.entitlement_rules[0]
    assert rule.entitlement_id == "finops-readonly"

    result = adapter.canonicalize_entitlement_id("group", rule.entitlement_id)

    assert result.is_success, result.message
    assert result.data == "bbb-222-uuid"


@pytest.mark.integration
def test_full_pipeline_multiple_groups(aws_config: AccessSyncRuntimeConfig):
    """Full pipeline: config → IDP discovery → policy → adapter resolution.

    Verifies the naming convention end-to-end:
        sg-aws-{token}  in IDP
        →  entitlement_id = {token}  in effective policy
        →  AWS IC group display name matches {token}  (exact or normalized)
        →  GroupId returned for planner use
    """
    discovered = {
        "sg-aws-authn",
        "sg-aws-my-security-group",
        "sg-aws-finops-readonly",
        "sg-aws-breakglass-admin",
    }
    effective = resolve_effective_policy(aws_config, "aws", discovered)

    adapter, _ = make_adapter(
        [
            {"GroupId": "aaa-111-uuid", "DisplayName": "my-security-group"},
            {"GroupId": "bbb-222-uuid", "DisplayName": "FinOps-ReadOnly"},
            {"GroupId": "ccc-333-uuid", "DisplayName": "breakglass-admin"},
        ]
    )

    expected = {
        "my-security-group": "aaa-111-uuid",
        "finops-readonly": "bbb-222-uuid",
        "breakglass-admin": "ccc-333-uuid",
    }

    resolved = {}
    for rule in effective.entitlement_rules:
        result = adapter.canonicalize_entitlement_id("group", rule.entitlement_id)
        assert result.is_success, f"Failed to resolve {rule.entitlement_id!r}: {result.message}"
        resolved[rule.entitlement_id] = result.data

    assert resolved == expected


@pytest.mark.integration
def test_adapter_returns_error_for_unknown_token(aws_config: AccessSyncRuntimeConfig):
    """A token with no matching AWS IC group returns GROUP_ID_NOT_FOUND."""
    discovered = {"sg-aws-orphaned-token"}
    effective = resolve_effective_policy(aws_config, "aws", discovered)

    adapter, _ = make_adapter([])  # empty AWS IC — nothing matches

    rule = effective.entitlement_rules[0]
    result = adapter.canonicalize_entitlement_id("group", rule.entitlement_id)

    assert not result.is_success
    assert result.error_code == "GROUP_ID_NOT_FOUND"
