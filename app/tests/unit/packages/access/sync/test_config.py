"""Unit tests for Access Sync config settings and loaders."""

import json

import pytest

from packages.access.common.config import (
    BundleConfigLoader,
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
    # _access_sync_env_isolation (autouse) already strips all ACCESS_SYNC_* vars.
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
