"""Unit tests for Access Sync config module."""

import pytest

from packages.access.sync.config import (
    AccessSyncRuntimeConfig,
    BundleConfigLoader,
    FileJsonConfigLoader,
    InlineJsonConfigLoader,
    get_access_sync_config_loader,
    normalize_target_key,
)
from packages.access.sync.policies import PlatformPolicy


@pytest.mark.unit
def test_bundle_loader_returns_empty_config():
    # Arrange
    loader = BundleConfigLoader()

    # Act
    result = loader.load(ref="default")

    # Assert
    assert result.is_success
    assert isinstance(result.data, AccessSyncRuntimeConfig)
    assert result.data.platforms == {}
    assert result.data.entitlement_mode_overrides == []
    assert "waiting mode" in result.message


@pytest.mark.unit
def test_get_access_sync_config_loader_bundle():
    loader = get_access_sync_config_loader("bundle")
    assert isinstance(loader, BundleConfigLoader)


@pytest.mark.unit
def test_get_access_sync_config_loader_inline_json():
    loader = get_access_sync_config_loader("inline_json")
    assert isinstance(loader, InlineJsonConfigLoader)


@pytest.mark.unit
def test_get_access_sync_config_loader_file_json():
    loader = get_access_sync_config_loader("file_json")
    assert isinstance(loader, FileJsonConfigLoader)


@pytest.mark.unit
def test_inline_json_loader_parses_aws_policy():
    # Arrange
    loader = InlineJsonConfigLoader()
    ref = (
        '{"dir_prefix":"sg","dir_separator":"-",'
        '"platforms":{"aws":{"authn_token":"authn","authn_removal_mode":"delete"}}}'
    )

    # Act
    result = loader.load(ref=ref)

    # Assert
    assert result.is_success
    assert result.data is not None
    assert "aws" in result.data.platforms
    policy = result.data.platforms["aws"]
    assert isinstance(policy, PlatformPolicy)
    assert policy.authn_token == "authn"
    assert policy.authn_removal_mode == "delete"


@pytest.mark.unit
def test_inline_json_loader_slug_derivation():
    # Arrange
    loader = InlineJsonConfigLoader()
    ref = (
        '{"dir_prefix":"sg","dir_separator":"-",'
        '"platforms":{"aws":{"authn_token":"authn","authn_removal_mode":"delete"}}}'
    )

    # Act
    result = loader.load(ref=ref)

    # Assert
    assert result.is_success
    config = result.data
    assert config.group_prefix("aws") == "sg-aws-"
    assert config.authn_group_slug("aws") == "sg-aws-authn"


@pytest.mark.unit
def test_inline_json_loader_mode_overrides():
    # Arrange
    loader = InlineJsonConfigLoader()
    ref = (
        '{"dir_prefix":"sg","platforms":{"aws":{"authn_token":"authn",'
        '"authn_removal_mode":"delete","mode_overrides":{"breakglass":"ephemeral"}}}}'
    )

    # Act
    result = loader.load(ref=ref)

    # Assert
    assert result.is_success
    policy = result.data.platforms["aws"]
    assert policy.mode_overrides == {"breakglass": "ephemeral"}


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
def test_inline_json_loader_rejects_missing_dir_prefix():
    # Arrange
    loader = InlineJsonConfigLoader()

    # Act
    result = loader.load(ref='{"platforms":{}}')

    # Assert
    assert not result.is_success
    assert result.error_code == "CONFIG_INVALID_SHAPE"


@pytest.mark.unit
def test_file_json_loader_parses_aws_policy(tmp_path):
    # Arrange
    loader = FileJsonConfigLoader()
    config_file = tmp_path / "access-sync.json"
    config_file.write_text(
        '{"dir_prefix":"sg","dir_separator":"-",'
        '"platforms":{"aws":{"authn_token":"authn","authn_removal_mode":"delete"}}}',
        encoding="utf-8",
    )

    # Act
    result = loader.load(ref=str(config_file))

    # Assert
    assert result.is_success
    assert result.data is not None
    assert "aws" in result.data.platforms


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
def test_inline_json_loader_normalizes_platform_key():
    """Platform map key must be normalized regardless of JSON casing."""
    loader = InlineJsonConfigLoader()
    ref = '{"dir_prefix":"sg","platforms":{"AWS":{"authn_token":"authn","authn_removal_mode":"delete"}}}'
    result = loader.load(ref=ref)
    assert result.is_success
    assert result.data is not None
    assert "aws" in result.data.platforms
    assert "AWS" not in result.data.platforms
