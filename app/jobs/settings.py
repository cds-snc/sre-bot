"""Scheduler-owned settings for background job coordination."""

from functools import lru_cache

from pydantic import Field

from infrastructure.configuration.base import InfrastructureSettings


class SchedulerSettings(InfrastructureSettings):
    """Shared scheduler defaults for Tier-2 singleton jobs."""

    DEFAULT_TIER2_LEASE_TTL_SECONDS: int = Field(
        default=1800,
        alias="DEFAULT_TIER2_LEASE_TTL_SECONDS",
    )


@lru_cache(maxsize=1)
def get_scheduler_settings() -> SchedulerSettings:
    """Singleton provider for scheduler settings."""
    return SchedulerSettings()
