"""Scheduler-owned settings for background job coordination."""

from functools import lru_cache

from infrastructure.configuration.base import InfrastructureSettings


class SchedulerSettings(InfrastructureSettings):
    """Shared scheduler defaults for Tier-2 singleton jobs."""

    default_tier2_lease_ttl_seconds: int = 1800


@lru_cache(maxsize=1)
def get_scheduler_settings() -> SchedulerSettings:
    """Singleton provider for scheduler settings."""
    return SchedulerSettings()
