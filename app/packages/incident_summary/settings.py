"""Feature settings for the incident_summary package.

Feature-domain configuration (how much channel history to summarize) lives
with the consuming feature -- vendor transport concerns (OpenAI key/model/timeout) stay in
``integrations.openai.settings``. All fields carry safe defaults so the
package works with no environment configuration.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


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
