"""Incident core settings: the [incident_core] table of the configuration files.

The record tables, the new-incident system policy, and the incident Google document ids
every subdomain shares. Vendor tenant ids stay in the vendor slices and reach the
incident feature through the configured-systems read. The document ids are non-public
values (decisions/configuration.md): declared empty in base.toml, set only from the
environment as INCIDENT_CORE__<FIELD>. An empty id does not fail boot; the legacy code
fails at first use, and each rebuilt subdomain states the ids it needs when it registers.
"""

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import SettingsConfigDict

from contracts.configuration import ConfigurationSlice, env_only
from contracts.workplace import WorkplaceSystem


class IncidentCoreSettings(ConfigurationSlice):
    """Table names of the incident record, the system that hosts new incidents, and the shared document ids.

    Keys of [incident_core]:
        incidents_table, timeline_table, new_incident_system (absent: unset).

    Environment only (non-public values):
        INCIDENT_CORE__FOLDER_ID, INCIDENT_CORE__REPORT_TEMPLATE_ID, INCIDENT_CORE__LIST_SHEET_ID.
    """

    model_config = SettingsConfigDict(toml_table_header=("incident_core",), env_prefix="INCIDENT_CORE__")

    # Defaults are the tables terraform/dynamodb.tf provisions.
    incidents_table: str = Field(default="incidents", description="Records table holding one item per incident.")
    timeline_table: str = Field(
        default="sre_bot_incident_timeline",
        description="Records table holding the timeline entries of every incident.",
    )
    new_incident_system: WorkplaceSystem | None = Field(
        default=None,
        description=(
            "Workplace system that creates a new incident's report and video call. "
            "Unset means the only configured system (decisions/incident-management.md)."
        ),
    )
    folder_id: str = env_only("Google Drive folder holding every incident's folder.", "codespaces", default="")
    report_template_id: str = env_only("Google Docs template a new incident report is copied from.", "codespaces", default="")
    list_sheet_id: str = env_only("Google Sheets spreadsheet listing every incident.", "codespaces", default="")

    @field_validator("incidents_table", "timeline_table")
    @classmethod
    def _require_table_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("a table name must not be blank")
        return value


@lru_cache(maxsize=1)
def get_incident_core_settings() -> IncidentCoreSettings:
    """Return the process-wide [incident_core] slice."""
    return IncidentCoreSettings()
