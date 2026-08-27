"""Tests for incident_draft feature settings defaults and overrides."""

from __future__ import annotations

import pytest

from packages.incident_draft.settings import (
    IncidentDraftSettings,
    get_incident_draft_settings,
)

pytestmark = pytest.mark.unit


class TestIncidentDraftSettings:
    def test_applies_safe_defaults(self, monkeypatch):
        for var in (
            "INCIDENT_DRAFT__DEFAULT_HISTORY_LIMIT",
            "INCIDENT_DRAFT__MAX_HISTORY_LIMIT",
            "INCIDENT_DRAFT__DEFAULT_SINCE_HOURS",
        ):
            monkeypatch.delenv(var, raising=False)

        settings = IncidentDraftSettings()

        assert settings.DEFAULT_HISTORY_LIMIT == 500
        assert settings.MAX_HISTORY_LIMIT == 1000
        assert settings.DEFAULT_SINCE_HOURS == 24

    def test_overrides_from_env(self, monkeypatch):
        monkeypatch.setenv("INCIDENT_DRAFT__DEFAULT_HISTORY_LIMIT", "50")
        monkeypatch.setenv("INCIDENT_DRAFT__MAX_HISTORY_LIMIT", "250")

        settings = IncidentDraftSettings()

        assert settings.DEFAULT_HISTORY_LIMIT == 50
        assert settings.MAX_HISTORY_LIMIT == 250

    def test_get_incident_draft_settings_is_cached(self):
        assert get_incident_draft_settings() is get_incident_draft_settings()
