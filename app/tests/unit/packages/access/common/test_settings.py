"""Unit tests for the unified AccessSettings model.

Validates that all four sub-feature slices (config, sync, requests, catalog)
resolve their env vars correctly from the single root object, and that
defaults are applied when no env vars are set.
"""

import pytest
from pydantic import ValidationError

from packages.access.common.settings import (
    AccessCatalogSettings,
    AccessConfigSettings,
    AccessRequestsSettings,
    AccessSettings,
    AccessSyncSettings,
)

# ---------------------------------------------------------------------------
# Sub-model plain BaseModel defaults (no env reads needed)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_access_config_settings_defaults():
    """AccessConfigSettings must provide correct defaults with no env vars."""
    s = AccessConfigSettings()
    assert s.source == "bundle"
    assert s.ref == "default"
    assert s.refresh_seconds == 300


@pytest.mark.unit
def test_access_sync_settings_defaults():
    """AccessSyncSettings must provide correct defaults with no env vars."""
    s = AccessSyncSettings()
    assert s.enabled is False
    assert s.reconciliation_enabled is False
    assert s.reconciliation_schedule == "03:00"
    assert s.job_ttl_seconds == 86400
    assert s.lock_stale_seconds == 14400


@pytest.mark.unit
def test_access_requests_settings_defaults():
    """AccessRequestsSettings must provide correct defaults with no env vars."""
    s = AccessRequestsSettings()
    assert s.enabled is False
    assert s.manager_group_slug == "sg-managers"
    assert s.fallback_approver_slug == "sg-org-admins"
    assert s.min_approver_count == 1
    assert s.request_ttl_hours == 72


@pytest.mark.unit
def test_access_catalog_settings_defaults():
    """AccessCatalogSettings must provide correct defaults with no env vars."""
    s = AccessCatalogSettings()
    assert s.enabled is False


# ---------------------------------------------------------------------------
# AccessSettings — flat env var loading via env_nested_delimiter
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_access_settings_defaults_with_no_env_vars():
    """AccessSettings must produce safe defaults when no env vars are set."""
    s = AccessSettings(_env_file=None)
    assert s.config.source == "bundle"
    assert s.sync.enabled is False
    assert s.requests.enabled is False
    assert s.catalog.enabled is False


@pytest.mark.unit
def test_access_settings_reads_sync_flat_env_vars(monkeypatch):
    """AccessSettings must resolve ACCESS_SYNC_* flat env vars into the sync slice."""
    monkeypatch.setenv("ACCESS_SYNC_ENABLED", "true")
    monkeypatch.setenv("ACCESS_SYNC_JOB_TTL_SECONDS", "7200")
    monkeypatch.setenv("ACCESS_SYNC_LOCK_STALE_SECONDS", "1800")
    monkeypatch.setenv("ACCESS_SYNC_RECONCILIATION_SCHEDULE", "02:30")

    s = AccessSettings(_env_file=None).sync
    assert s.enabled is True
    assert s.job_ttl_seconds == 7200
    assert s.lock_stale_seconds == 1800
    assert s.reconciliation_schedule == "02:30"


@pytest.mark.unit
def test_access_settings_reads_config_flat_env_vars(monkeypatch):
    """AccessSettings must resolve ACCESS_CONFIG_* flat env vars into the config slice."""
    monkeypatch.setenv("ACCESS_CONFIG_SOURCE", "inline_json")
    monkeypatch.setenv("ACCESS_CONFIG_REF", "myref")
    monkeypatch.setenv("ACCESS_CONFIG_REFRESH_SECONDS", "60")

    s = AccessSettings(_env_file=None).config
    assert s.source == "inline_json"
    assert s.ref == "myref"
    assert s.refresh_seconds == 60


@pytest.mark.unit
def test_access_settings_reads_requests_flat_env_vars(monkeypatch):
    """AccessSettings must resolve ACCESS_REQUESTS_* flat env vars into the requests slice."""
    monkeypatch.setenv("ACCESS_REQUESTS_ENABLED", "true")
    monkeypatch.setenv("ACCESS_REQUESTS_MANAGER_GROUP_SLUG", "sg-leads")
    monkeypatch.setenv("ACCESS_REQUESTS_FALLBACK_APPROVER_SLUG", "sg-admins")
    monkeypatch.setenv("ACCESS_REQUESTS_MIN_APPROVER_COUNT", "2")
    monkeypatch.setenv("ACCESS_REQUESTS_REQUEST_TTL_HOURS", "48")

    s = AccessSettings(_env_file=None).requests
    assert s.enabled is True
    assert s.manager_group_slug == "sg-leads"
    assert s.fallback_approver_slug == "sg-admins"
    assert s.min_approver_count == 2
    assert s.request_ttl_hours == 48


@pytest.mark.unit
def test_access_settings_reads_catalog_flat_env_var(monkeypatch):
    """AccessSettings must resolve ACCESS_CATALOG_ENABLED into the catalog slice."""
    monkeypatch.setenv("ACCESS_CATALOG_ENABLED", "true")

    s = AccessSettings(_env_file=None).catalog
    assert s.enabled is True


# ---------------------------------------------------------------------------
# JSON blob loading — sub-model set via a single JSON env var
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_access_settings_accepts_sync_json_blob(monkeypatch):
    """ACCESS_SYNC may be set as a JSON blob to configure the entire sync slice."""
    monkeypatch.setenv(
        "ACCESS_SYNC",
        '{"enabled": true, "job_ttl_seconds": 3600, "lock_stale_seconds": 900}',
    )

    s = AccessSettings(_env_file=None).sync
    assert s.enabled is True
    assert s.job_ttl_seconds == 3600
    assert s.lock_stale_seconds == 900


@pytest.mark.unit
def test_access_settings_accepts_requests_json_blob(monkeypatch):
    """ACCESS_REQUESTS may be set as a JSON blob to configure the entire requests slice."""
    monkeypatch.setenv(
        "ACCESS_REQUESTS",
        '{"enabled": true, "min_approver_count": 3, "request_ttl_hours": 24}',
    )

    s = AccessSettings(_env_file=None).requests
    assert s.enabled is True
    assert s.min_approver_count == 3
    assert s.request_ttl_hours == 24


@pytest.mark.unit
def test_access_settings_rejects_unimplemented_config_sources(monkeypatch):
    monkeypatch.setenv("ACCESS_CONFIG_SOURCE", "dynamodb")

    with pytest.raises(ValidationError, match="ACCESS_CONFIG_SOURCE"):
        AccessSettings(_env_file=None)
