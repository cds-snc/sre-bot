"""Feature settings for the incident comms subdomain.

Feature-domain configuration (the drafting window, the update cadence, the
public time zone and the model budget) lives with the consuming feature --
vendor transport concerns (OpenAI key/model/timeout) stay in their integration
settings. All fields carry safe defaults so the package works with no
environment configuration.
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class IncidentStatusUpdateSettings(BaseSettings):
    """Window, cadence and model budget for ``/sre incident status-update``."""

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )

    MAX_HISTORY_LIMIT: int = Field(default=1000, alias="INCIDENT_STATUS_UPDATE__MAX_HISTORY_LIMIT")
    # Used for an incident's first update when the conversation's start is unknown.
    DEFAULT_SINCE_HOURS: int = Field(default=24, alias="INCIDENT_STATUS_UPDATE__DEFAULT_SINCE_HOURS")
    # A public update follows about every 30 minutes (decisions/incident-management.md).
    NEXT_UPDATE_MINUTES: int = Field(default=30, alias="INCIDENT_STATUS_UPDATE__NEXT_UPDATE_MINUTES")
    # Public times are shown in Eastern time; named so EDT/EST follows daylight saving.
    TIMEZONE: str = Field(default="America/Toronto", alias="INCIDENT_STATUS_UPDATE__TIMEZONE")
    # Eight short fields in two languages need far less than a report draft.
    MAX_OUTPUT_TOKENS: int = Field(default=2000, alias="INCIDENT_STATUS_UPDATE__MAX_OUTPUT_TOKENS")


@lru_cache(maxsize=1)
def get_incident_status_update_settings() -> IncidentStatusUpdateSettings:
    """Return the process-wide ``IncidentStatusUpdateSettings`` singleton."""
    return IncidentStatusUpdateSettings()
