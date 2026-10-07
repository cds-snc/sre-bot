"""Feature settings for the incident scribe subdomain.

Feature-domain configuration (how much channel history feeds a draft or a
summary) lives with the consuming feature -- vendor transport concerns (OpenAI
key/model/timeout, Google credentials) stay in their respective integration
settings. All fields carry safe defaults so the package works with no
environment configuration.
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class IncidentDraftSettings(BaseSettings):
    """History-bounding settings for the ``/sre incident draft`` command."""

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )

    DEFAULT_HISTORY_LIMIT: int = Field(default=500, alias="INCIDENT_DRAFT__DEFAULT_HISTORY_LIMIT")
    MAX_HISTORY_LIMIT: int = Field(default=1000, alias="INCIDENT_DRAFT__MAX_HISTORY_LIMIT")
    DEFAULT_SINCE_HOURS: int = Field(default=24, alias="INCIDENT_DRAFT__DEFAULT_SINCE_HOURS")

    # Timeline entries are stamped in this zone, matching the ET convention the
    # 💾-curated timeline in modules.incident already uses. Named rather than
    # fixed-offset so the abbreviation follows daylight saving (EDT/EST).
    TIMEZONE: str = Field(default="America/Toronto", alias="INCIDENT_DRAFT__TIMEZONE")

    # Drafting emits one JSON object covering every section of the report --
    # timelines, Q&A chains, bulleted retrospectives -- so it needs far more
    # completion budget than a single catch-up summary (the vendor default of
    # 800 truncates the JSON mid-object). A truncated run still writes a draft
    # from the sections that arrived whole, marked partial, but the later
    # sections are missing from it, so the budget is kept generous.
    MAX_OUTPUT_TOKENS: int = Field(default=4000, alias="INCIDENT_DRAFT__MAX_OUTPUT_TOKENS")


@lru_cache(maxsize=1)
def get_incident_draft_settings() -> IncidentDraftSettings:
    """Return the process-wide ``IncidentDraftSettings`` singleton."""
    return IncidentDraftSettings()


class IncidentSummarySettings(BaseSettings):
    """History-bounding settings for the ``/sre incident summarize`` command."""

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )

    DEFAULT_HISTORY_LIMIT: int = Field(default=500, alias="INCIDENT_SUMMARY__DEFAULT_HISTORY_LIMIT")
    MAX_HISTORY_LIMIT: int = Field(default=1000, alias="INCIDENT_SUMMARY__MAX_HISTORY_LIMIT")
    DEFAULT_SINCE_HOURS: int = Field(default=24, alias="INCIDENT_SUMMARY__DEFAULT_SINCE_HOURS")


@lru_cache(maxsize=1)
def get_incident_summary_settings() -> IncidentSummarySettings:
    """Return the process-wide ``IncidentSummarySettings`` singleton."""
    return IncidentSummarySettings()


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
