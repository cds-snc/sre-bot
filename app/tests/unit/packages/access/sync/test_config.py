"""Unit tests for Access Sync config settings and loaders."""

import json

import pytest

from packages.access.common.config import (
    BundleConfigLoader,
    EnvConfigLoader,
    FileJsonConfigLoader,
    InlineJsonConfigLoader,
    get_access_config_loader,
    normalize_target_key,
)
from packages.access.common.settings import AccessSettings

# ---------------------------------------------------------------------------
# AccessSyncSettings defaults
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_access_sync_settings_defaults(make_sync_settings):
    """AccessSyncSettings must provide sane defaults without env vars."""
    # Access-root conftest autouse fixture already strips ACCESS_* vars.
    settings = make_sync_settings()
    assert settings.enabled is False
    assert settings.reconciliation_enabled is False
    assert settings.reconciliation_schedule == "03:00"
    assert settings.job_ttl_seconds == 86400
    assert settings.lock_stale_seconds == 14400


@pytest.mark.unit
def test_access_sync_settings_env_overrides(monkeypatch):
    """AccessSettings must read ACCESS_SYNC_* env vars into the sync slice."""
    monkeypatch.setenv("ACCESS_SYNC_ENABLED", "true")
    monkeypatch.setenv("ACCESS_SYNC_JOB_TTL_SECONDS", "3600")

    settings = AccessSettings(_env_file=None).sync
    assert settings.enabled is True
    assert settings.job_ttl_seconds == 3600


# ---------------------------------------------------------------------------
# normalize_target_key
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_normalize_target_key_lowercases_and_strips():
    assert normalize_target_key("  AWS  ") == "aws"
    assert normalize_target_key("GitHub") == "github"
    assert normalize_target_key("aws") == "aws"


# ---------------------------------------------------------------------------
# get_access_config_loader factory (canonical)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_get_access_config_loader_returns_bundle_by_default():
    """config_source='bundle' must return a BundleConfigLoader."""
    loader = get_access_config_loader("bundle")
    assert isinstance(loader, BundleConfigLoader)


@pytest.mark.unit
def test_get_access_config_loader_returns_inline_json():
    """config_source='inline_json' must return an InlineJsonConfigLoader."""
    loader = get_access_config_loader("inline_json")
    assert isinstance(loader, InlineJsonConfigLoader)


@pytest.mark.unit
def test_get_access_config_loader_returns_file_json():
    """config_source='file_json' must return a FileJsonConfigLoader."""
    loader = get_access_config_loader("file_json")
    assert isinstance(loader, FileJsonConfigLoader)


# ---------------------------------------------------------------------------
# BundleConfigLoader and InlineJsonConfigLoader smoke tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_bundle_config_loader_load_returns_success():
    """BundleConfigLoader.load() must return a successful OperationResult."""
    loader = BundleConfigLoader()
    result = loader.load("default")
    assert result.is_success


@pytest.mark.unit
def test_inline_json_config_loader_parses_platforms():
    """InlineJsonConfigLoader.load() must return AccessRuntimeConfig with correct platforms."""
    payload = json.dumps(
        {
            "dir_prefix": "sg",
            "dir_separator": "-",
            "platforms": {
                "aws": {
                    "authn_token": "authn",
                    "authn_removal_mode": "delete",
                    "mode_overrides": {},
                }
            },
        }
    )
    loader = InlineJsonConfigLoader()
    result = loader.load(payload)
    assert result.is_success
    assert result.data is not None
    assert "aws" in result.data.platforms
    assert result.data.group_prefix("aws") == "sg-aws-"
    assert result.data.authn_group_slug("aws") == "sg-aws-authn"


@pytest.mark.unit
def test_inline_json_loader_preserves_extensions_for_catalog():
    payload = json.dumps(
        {
            "dir_prefix": "sg",
            "dir_separator": "-",
            "platforms": {
                "aws": {
                    "authn_token": "authn",
                    "authn_removal_mode": "delete",
                    "mode_overrides": {},
                }
            },
            "extensions": {"catalog": {"platform_display_names": {"aws": "Amazon Web Services"}}},
        }
    )

    result = InlineJsonConfigLoader().load(payload)

    assert result.is_success
    assert result.data is not None
    assert result.data.extensions == {"catalog": {"platform_display_names": {"aws": "Amazon Web Services"}}}


@pytest.mark.unit
def test_env_config_loader_reads_access_config_env_names(monkeypatch):
    monkeypatch.setenv("ACCESS_CONFIG_ENV_DIR_PREFIX", "sg")
    monkeypatch.setenv("ACCESS_CONFIG_ENV_DIR_SEPARATOR", "-")
    monkeypatch.setenv(
        "ACCESS_CONFIG_ENV_PLATFORMS_JSON",
        '{"aws": {"authn_token": "authn", "authn_removal_mode": "delete", "mode_overrides": {}}}',
    )

    result = EnvConfigLoader().load("unused")

    assert result.is_success
    assert result.data is not None
    assert result.data.dir_prefix == "sg"
    assert "aws" in result.data.platforms


@pytest.mark.unit
def test_env_config_loader_rejects_legacy_access_sync_env_names(monkeypatch):
    monkeypatch.setenv("ACCESS_SYNC_DIR_PREFIX", "sg")
    monkeypatch.setenv("ACCESS_SYNC_DIR_SEPARATOR", "-")
    monkeypatch.setenv(
        "ACCESS_SYNC_PLATFORMS_JSON",
        '{"aws": {"authn_token": "authn", "authn_removal_mode": "delete", "mode_overrides": {}}}',
    )

    result = EnvConfigLoader().load("unused")

    assert not result.is_success
    assert result.error_code == "CONFIG_INVALID_SHAPE"
    assert "ACCESS_CONFIG_ENV_DIR_PREFIX" in (result.message or "")
