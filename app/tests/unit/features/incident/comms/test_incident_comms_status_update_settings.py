"""Tests for the incident status-update settings defaults and overrides."""

import pytest

from features.incident.comms.settings import (
    IncidentStatusUpdateSettings,
    get_incident_status_update_settings,
)

pytestmark = pytest.mark.unit

_VARS = (
    "INCIDENT_STATUS_UPDATE__MAX_HISTORY_LIMIT",
    "INCIDENT_STATUS_UPDATE__DEFAULT_SINCE_HOURS",
    "INCIDENT_STATUS_UPDATE__NEXT_UPDATE_MINUTES",
    "INCIDENT_STATUS_UPDATE__TIMEZONE",
    "INCIDENT_STATUS_UPDATE__MAX_OUTPUT_TOKENS",
)


class TestIncidentStatusUpdateSettings:
    def test_applies_safe_defaults(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """With no environment the window, cadence, zone and token budget have working defaults."""
        for var in _VARS:
            monkeypatch.delenv(var, raising=False)

        settings = IncidentStatusUpdateSettings()

        assert settings.MAX_HISTORY_LIMIT == 1000
        assert settings.DEFAULT_SINCE_HOURS == 24
        assert settings.NEXT_UPDATE_MINUTES == 30
        assert settings.TIMEZONE == "America/Toronto"
        assert settings.MAX_OUTPUT_TOKENS == 2000

    def test_overrides_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Each value is read from its prefixed environment variable."""
        values = {
            "INCIDENT_STATUS_UPDATE__MAX_HISTORY_LIMIT": "200",
            "INCIDENT_STATUS_UPDATE__DEFAULT_SINCE_HOURS": "6",
            "INCIDENT_STATUS_UPDATE__NEXT_UPDATE_MINUTES": "60",
            "INCIDENT_STATUS_UPDATE__TIMEZONE": "America/Halifax",
            "INCIDENT_STATUS_UPDATE__MAX_OUTPUT_TOKENS": "1500",
        }
        for var, value in values.items():
            monkeypatch.setenv(var, value)

        settings = IncidentStatusUpdateSettings()

        assert (
            settings.MAX_HISTORY_LIMIT,
            settings.DEFAULT_SINCE_HOURS,
            settings.NEXT_UPDATE_MINUTES,
            settings.TIMEZONE,
            settings.MAX_OUTPUT_TOKENS,
        ) == (200, 6, 60, "America/Halifax", 1500)

    def test_get_incident_status_update_settings_is_cached(self) -> None:
        """One settings object serves the process."""
        assert get_incident_status_update_settings() is get_incident_status_update_settings()
