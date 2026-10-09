"""Tests for the incident scribe summarize settings defaults and overrides."""

import pytest

from packages.incident.scribe.settings import (
    IncidentSummarySettings,
    get_incident_summary_settings,
)

pytestmark = pytest.mark.unit


class TestIncidentSummarySettings:
    def test_applies_safe_defaults(self, monkeypatch):
        for var in (
            "INCIDENT_SUMMARY__DEFAULT_HISTORY_LIMIT",
            "INCIDENT_SUMMARY__MAX_HISTORY_LIMIT",
            "INCIDENT_SUMMARY__DEFAULT_SINCE_HOURS",
            "INCIDENT_SUMMARY__TIMEZONE",
        ):
            monkeypatch.delenv(var, raising=False)

        settings = IncidentSummarySettings()

        assert settings.DEFAULT_HISTORY_LIMIT == 500
        assert settings.MAX_HISTORY_LIMIT == 1000
        assert settings.DEFAULT_SINCE_HOURS == 24
        assert settings.TIMEZONE == "America/Toronto"

    def test_overrides_from_env(self, monkeypatch):
        monkeypatch.setenv("INCIDENT_SUMMARY__DEFAULT_HISTORY_LIMIT", "50")
        monkeypatch.setenv("INCIDENT_SUMMARY__MAX_HISTORY_LIMIT", "250")
        monkeypatch.setenv("INCIDENT_SUMMARY__TIMEZONE", "America/Vancouver")

        settings = IncidentSummarySettings()

        assert settings.DEFAULT_HISTORY_LIMIT == 50
        assert settings.MAX_HISTORY_LIMIT == 250
        assert settings.TIMEZONE == "America/Vancouver"

    def test_get_incident_summary_settings_is_cached(self):
        assert get_incident_summary_settings() is get_incident_summary_settings()
