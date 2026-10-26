"""Unit tests for the per-plugin access settings classes.

Each access plugin's settings class reads only its own ``ACCESS_<SUB>_``
environment names, under the same names production and ``.env`` files already
use, so building one never validates a sibling plugin's settings. No class
carries an on/off switch: enablement is the ``[plugins.platform_access]``
configuration key. The access-root conftest strips every ``ACCESS_*`` variable
and the ``.env`` file, so each test sees only what it sets.
"""

import pytest
from pydantic import ValidationError

from packages.access.common.settings import (
    AccessConfigSettings,
    AccessRequestsSettings,
    AccessSyncSettings,
)

pytestmark = pytest.mark.unit


def test_config_settings_defaults() -> None:
    """The config settings default to the bundle source and the default ref."""
    s = AccessConfigSettings()

    assert s.source == "bundle"
    assert s.ref == "default"
    assert s.refresh_seconds == 300


def test_config_settings_read_access_config_names(monkeypatch: pytest.MonkeyPatch) -> None:
    """ACCESS_CONFIG_* names populate the config settings."""
    monkeypatch.setenv("ACCESS_CONFIG_SOURCE", "inline_json")
    monkeypatch.setenv("ACCESS_CONFIG_REF", "myref")
    monkeypatch.setenv("ACCESS_CONFIG_REFRESH_SECONDS", "60")

    s = AccessConfigSettings()

    assert (s.source, s.ref, s.refresh_seconds) == ("inline_json", "myref", 60)


def test_config_settings_reject_unimplemented_source(monkeypatch: pytest.MonkeyPatch) -> None:
    """An unknown loader source fails with the env name in the message."""
    monkeypatch.setenv("ACCESS_CONFIG_SOURCE", "dynamodb")

    with pytest.raises(ValidationError, match="ACCESS_CONFIG_SOURCE"):
        AccessConfigSettings()


def test_sync_settings_defaults() -> None:
    """The sync settings default to no reconciliation and the provisioned tables."""
    s = AccessSyncSettings()

    assert s.reconciliation_enabled is False
    assert s.reconciliation_schedule == "03:00"
    assert s.job_ttl_seconds == 86400
    assert s.lock_stale_seconds == 14400
    assert s.table_name == "sre_bot_access"
    assert s.job_status_table_name == "sre_bot_idempotency"


def test_sync_settings_read_access_sync_names(monkeypatch: pytest.MonkeyPatch) -> None:
    """ACCESS_SYNC_* names populate the sync settings, including multi-word fields."""
    monkeypatch.setenv("ACCESS_SYNC_RECONCILIATION_ENABLED", "true")
    monkeypatch.setenv("ACCESS_SYNC_RECONCILIATION_SCHEDULE", "02:30")
    monkeypatch.setenv("ACCESS_SYNC_JOB_TTL_SECONDS", "7200")
    monkeypatch.setenv("ACCESS_SYNC_LOCK_STALE_SECONDS", "1800")
    monkeypatch.setenv("ACCESS_SYNC_TABLE_NAME", "sync_elsewhere")
    monkeypatch.setenv("ACCESS_SYNC_JOB_STATUS_TABLE_NAME", "jobs_elsewhere")

    s = AccessSyncSettings()

    assert s.reconciliation_enabled is True
    assert s.reconciliation_schedule == "02:30"
    assert s.job_ttl_seconds == 7200
    assert s.lock_stale_seconds == 1800
    assert s.table_name == "sync_elsewhere"
    assert s.job_status_table_name == "jobs_elsewhere"


def test_requests_settings_read_access_requests_names(monkeypatch: pytest.MonkeyPatch) -> None:
    """ACCESS_REQUESTS_* names populate the requests settings."""
    monkeypatch.setenv("ACCESS_REQUESTS_FALLBACK_APPROVER_SLUG", "sg-admins")
    monkeypatch.setenv("ACCESS_REQUESTS_MIN_APPROVER_COUNT", "2")
    monkeypatch.setenv("ACCESS_REQUESTS_REQUEST_TTL_HOURS", "48")
    monkeypatch.setenv("ACCESS_REQUESTS_TABLE_NAME", "requests_elsewhere")

    s = AccessRequestsSettings()

    assert s.fallback_approver_slug == "sg-admins"
    assert s.min_approver_count == 2
    assert s.request_ttl_hours == 48
    assert s.table_name == "requests_elsewhere"


@pytest.mark.parametrize("settings_class", [AccessConfigSettings, AccessSyncSettings, AccessRequestsSettings])
def test_no_access_settings_class_has_an_enabled_switch(settings_class: type) -> None:
    """Enablement is the plugin key, so no access settings class declares ``enabled``."""
    assert "enabled" not in settings_class.model_fields


def test_legacy_enabled_switches_change_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    """ACCESS_*_ENABLED values left in an environment are ignored, not rejected."""
    for name in ("ACCESS_SYNC_ENABLED", "ACCESS_REQUESTS_ENABLED", "ACCESS_CATALOG_ENABLED"):
        monkeypatch.setenv(name, "true")
    monkeypatch.setenv("ACCESS_REQUESTS_FALLBACK_APPROVER_SLUG", "sg-admins")

    assert AccessSyncSettings().model_dump() == AccessSyncSettings.model_construct().model_dump()
    assert not hasattr(AccessRequestsSettings(), "enabled")
