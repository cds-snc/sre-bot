"""Feature settings for the incident_draft package.

Feature-domain configuration (how much channel history feeds the draft) lives
with the consuming feature -- vendor transport concerns (OpenAI key/model/timeout,
Google credentials) stay in their respective integration settings. All fields
carry safe defaults so the package works with no environment configuration.
"""

from __future__ import annotations

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

    # Drafting emits one JSON object covering every section of the report --
    # timelines, Q&A chains, bulleted retrospectives -- so it needs far more
    # completion budget than a single catch-up summary (the vendor default of
    # 800 truncates the JSON mid-object). A truncated run is discarded rather
    # than written, so this being generous costs little.
    MAX_OUTPUT_TOKENS: int = Field(default=8000, alias="INCIDENT_DRAFT__MAX_OUTPUT_TOKENS")


@lru_cache(maxsize=1)
def get_incident_draft_settings() -> IncidentDraftSettings:
    """Return the process-wide ``IncidentDraftSettings`` singleton."""
    return IncidentDraftSettings()
