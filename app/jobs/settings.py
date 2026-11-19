"""Scheduler settings slice: the [scheduler] table of the configuration files.

The scheduler is a host capability (decisions/reliability.md): [scheduler]
enabled decides whether scheduled jobs start on this deployment, so the run
switch is a configuration-file key, never the environment name.
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import SettingsConfigDict

from contracts.configuration import ConfigurationSlice


class SchedulerSettings(ConfigurationSlice):
    """Whether scheduled jobs run, the shared default for Tier-2 singleton jobs, and their hold margin."""

    model_config = SettingsConfigDict(toml_table_header=("scheduler",), env_prefix="SCHEDULER__")

    enabled: bool = Field(default=False, description="Start the scheduled jobs on this deployment.")
    default_tier2_lease_ttl_seconds: int = Field(
        default=1800, description="Lease time-to-live of a Tier-2 singleton job across replicas, in seconds."
    )
    lease_hold_margin_seconds: int = Field(
        default=5,
        ge=0,
        description=(
            "Seconds a Tier-2 lease's minimum hold stops short of the job's interval: the hold is"
            " min(lease TTL, interval - margin), covering whole-second expiry, the scheduler's poll"
            " and clock skew between replicas."
        ),
    )


@lru_cache(maxsize=1)
def get_scheduler_settings() -> SchedulerSettings:
    """Singleton provider for scheduler settings."""
    return SchedulerSettings()
