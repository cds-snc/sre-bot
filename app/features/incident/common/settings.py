"""Incident core settings: the record tables and the new-incident system policy.

Feature-domain configuration only; vendor tenant ids stay in the vendor slices
and reach the incident feature through the configured-systems read. All fields
carry safe defaults so the package works with no environment configuration.
"""

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from contracts.workplace import WorkplaceSystem


class IncidentCoreSettings(BaseSettings):
    """Table names of the incident record and the system that hosts new incidents."""

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )

    # Defaults are the tables terraform/dynamodb.tf provisions.
    INCIDENTS_TABLE: str = Field(
        default="incidents",
        alias="INCIDENT_CORE__INCIDENTS_TABLE",
        description="Records table holding one item per incident.",
    )
    TIMELINE_TABLE: str = Field(
        default="sre_bot_incident_timeline",
        alias="INCIDENT_CORE__TIMELINE_TABLE",
        description="Records table holding the timeline entries of every incident.",
    )
    NEW_INCIDENT_SYSTEM: WorkplaceSystem | None = Field(
        default=None,
        alias="INCIDENT_CORE__NEW_INCIDENT_SYSTEM",
        description=(
            "Workplace system that creates a new incident's report and video call. "
            "Unset means the only configured system (decisions/incident-management.md)."
        ),
    )

    @field_validator("INCIDENTS_TABLE", "TIMELINE_TABLE")
    @classmethod
    def _require_table_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("a table name must not be blank")
        return value


@lru_cache(maxsize=1)
def get_incident_core_settings() -> IncidentCoreSettings:
    """Return the process-wide ``IncidentCoreSettings`` singleton."""
    return IncidentCoreSettings()
