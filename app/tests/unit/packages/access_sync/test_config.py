"""Unit tests for Access Sync config module."""

import pytest

from packages.access_sync.config import (
    AccessSyncRuntimeConfig,
    BundleConfigLoader,
    FileJsonConfigLoader,
    InlineJsonConfigLoader,
    get_access_sync_config_loader,
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
def test_file_json_loader_missing_file_returns_not_found():
    # Arrange
    loader = FileJsonConfigLoader()

    # Act
    result = loader.load(ref="/tmp/does-not-exist-access-sync.json")

    # Assert
    assert not result.is_success
    assert result.error_code == "CONFIG_NOT_FOUND"


@pytest.mark.unit
def test_get_access_sync_config_loader_unknown_raises():
    # Act / Assert
    with pytest.raises(NotImplementedError, match="not yet implemented"):
        get_access_sync_config_loader("dynamodb")
