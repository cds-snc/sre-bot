"""Unit tests for scheduler settings and provider.

The scheduler owns a single shared default Tier-2 lease TTL rather than one TTL
field per job, so these tests assert the single default value, its env override,
and the singleton identity of the provider.
"""

import pytest
from jobs.settings import SchedulerSettings, get_scheduler_settings

pytestmark = pytest.mark.unit


class TestSchedulerSettings:
    """Tests for the scheduler's single shared default Tier-2 lease TTL."""

    @pytest.mark.unit
    def test_scheduler_settings_default(self) -> None:
        """SchedulerSettings exposes one shared default Tier-2 lease TTL."""
        settings = SchedulerSettings()

        assert settings.DEFAULT_TIER2_LEASE_TTL_SECONDS == 1800

    @pytest.mark.unit
    def test_scheduler_settings_env_var_override(self, monkeypatch) -> None:
        """The single default TTL honours its env var override."""
        monkeypatch.setenv("DEFAULT_TIER2_LEASE_TTL_SECONDS", "3600")

        settings = SchedulerSettings()

        assert settings.DEFAULT_TIER2_LEASE_TTL_SECONDS == 3600

    @pytest.mark.unit
    def test_get_scheduler_settings_returns_singleton(self) -> None:
        """get_scheduler_settings() returns the same singleton instance."""
        get_scheduler_settings.cache_clear()

        settings1 = get_scheduler_settings()
        settings2 = get_scheduler_settings()

        # Should be the same instance (singleton)
        assert settings1 is settings2
