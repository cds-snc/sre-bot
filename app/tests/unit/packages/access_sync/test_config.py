"""Unit tests for Access Sync config module."""

import pytest

from packages.access_sync.config import (
    AccessSyncRuntimeConfig,
    BundleConfigLoader,
    FileJsonConfigLoader,
    InlineJsonConfigLoader,
    get_access_sync_config_loader,
    normalize_target_key,
)


@pytest.mark.unit
def test_bundle_loader_returns_empty_config():
    # Arrange
    loader = BundleConfigLoader()

    # Act
    result = loader.load(ref="default")

    # Assert
    assert result.is_success
    assert isinstance(result.data, AccessSyncRuntimeConfig)
    # Bundle loader returns empty policies — feature is in "waiting mode"
    assert result.data.policies == {}
    assert result.data.entitlement_mode_overrides == []
    assert "waiting mode" in result.message


@pytest.mark.unit
def test_get_access_sync_config_loader_bundle():
    # Arrange / Act
    loader = get_access_sync_config_loader("bundle")

    # Assert
    assert isinstance(loader, BundleConfigLoader)


@pytest.mark.unit
def test_get_access_sync_config_loader_inline_json():
    # Arrange / Act
    loader = get_access_sync_config_loader("inline_json")

    # Assert
    assert isinstance(loader, InlineJsonConfigLoader)


@pytest.mark.unit
def test_get_access_sync_config_loader_file_json():
    # Arrange / Act
    loader = get_access_sync_config_loader("file_json")

    # Assert
    assert isinstance(loader, FileJsonConfigLoader)


@pytest.mark.unit
def test_inline_json_loader_parses_aws_policy():
    # Arrange
    loader = InlineJsonConfigLoader()
    ref = (
        '{"policies":{"aws":{"platform":"aws","authn_group_slug":"sg-aws-authn",'
        '"authn_mode":"derived","authn_removal_mode":"delete","entitlement_rules":[]}}}'
    )

    # Act
    result = loader.load(ref=ref)

    # Assert
    assert result.is_success
    assert result.data is not None
    assert "aws" in result.data.policies
    assert result.data.policies["aws"].platform == "aws"


@pytest.mark.unit
def test_inline_json_loader_parses_fake_policy_with_entitlements():
    # Arrange
    loader = InlineJsonConfigLoader()
    ref = (
        '{"policies":{"fake":{"platform":"fake","authn_group_slug":"sg-fake-authn",'
        '"authn_mode":"derived","authn_removal_mode":"delete","entitlement_rules":['
        '{"group_slug":"sg-fake-admin","entitlement_type":"group",'
        '"entitlement_id":"fake-group-admin","mode":"sync_managed"},'
        '{"group_slug":"sg-fake-read","entitlement_type":"group",'
        '"entitlement_id":"fake-group-read","mode":"sync_managed"}]}}}'
    )

    # Act
    result = loader.load(ref=ref)

    # Assert
    assert result.is_success
    assert result.data is not None
    assert "fake" in result.data.policies
    fake_policy = result.data.policies["fake"]
    assert fake_policy.platform == "fake"
    assert len(fake_policy.entitlement_rules) == 2
    assert fake_policy.entitlement_rules[0].entitlement_id == "fake-group-admin"


@pytest.mark.unit
def test_inline_json_loader_parses_default_entitlement_strategy():
    # Arrange
    loader = InlineJsonConfigLoader()
    ref = (
        '{"policies":{"aws":{"platform":"aws","authn_group_slug":"sg-aws-authn",'
        '"authn_mode":"derived","authn_removal_mode":"delete","entitlement_rules":[],'
        '"default_entitlement_strategy":{"kind":"default_prefix",'
        '"source_group_prefix":"sg-aws-","exclude_group_slugs":["sg-aws-authn"],'
        '"default_entitlement_type":"group","entitlement_id_template":"{token}",'
        '"mode":"sync_managed"}}}}'
    )

    # Act
    result = loader.load(ref=ref)

    # Assert
    assert result.is_success
    assert result.data is not None
    strategy = result.data.policies["aws"].default_entitlement_strategy
    assert strategy is not None
    assert strategy.kind == "default_prefix"
    assert strategy.source_group_prefix == "sg-aws-"


@pytest.mark.unit
def test_inline_json_loader_rejects_invalid_json():
    # Arrange
    loader = InlineJsonConfigLoader()

    # Act
    result = loader.load(ref="not-json")

    # Assert
    assert not result.is_success
    assert result.error_code == "CONFIG_INVALID_JSON"


@pytest.mark.unit
def test_file_json_loader_parses_aws_policy(tmp_path):
    # Arrange
    loader = FileJsonConfigLoader()
    config_file = tmp_path / "access-sync.json"
    config_file.write_text(
        '{"policies":{"aws":{"platform":"aws","authn_group_slug":"sg-aws-authn",'
        '"authn_mode":"derived","authn_removal_mode":"delete","entitlement_rules":[]}}}',
        encoding="utf-8",
    )

    # Act
    result = loader.load(ref=str(config_file))

    # Assert
    assert result.is_success
    assert result.data is not None
    assert "aws" in result.data.policies


@pytest.mark.unit
def test_file_json_loader_missing_file_returns_not_found(tmp_path):
    # Arrange
    loader = FileJsonConfigLoader()
    missing_path = str(tmp_path / "does-not-exist-access-sync.json")

    # Act
    result = loader.load(ref=missing_path)

    # Assert
    assert not result.is_success
    assert result.error_code == "CONFIG_NOT_FOUND"


@pytest.mark.unit
def test_get_access_sync_config_loader_unknown_raises():
    # Act / Assert
    with pytest.raises(NotImplementedError, match="not yet implemented"):
        get_access_sync_config_loader("dynamodb")


# ---------------------------------------------------------------------------
# normalize_target_key
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_normalize_target_key_lowercases_and_strips():
    assert normalize_target_key("  AWS  ") == "aws"
    assert normalize_target_key("FakePlatform") == "fakeplatform"
    assert normalize_target_key("aws") == "aws"


@pytest.mark.unit
def test_inline_json_loader_normalizes_policy_key():
    """Policy map key must be normalized regardless of how the platform field is cased."""
    loader = InlineJsonConfigLoader()
    ref = (
        '{"policies":{"AWS":{"platform":"AWS","authn_group_slug":"sg-aws-authn",'
        '"authn_mode":"derived","authn_removal_mode":"delete","entitlement_rules":[]}}}'
    )
    result = loader.load(ref=ref)
    assert result.is_success
    assert result.data is not None
    # Key must be normalized: stored as "aws", not "AWS"
    assert "aws" in result.data.policies
    assert "AWS" not in result.data.policies
