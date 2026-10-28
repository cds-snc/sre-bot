"""Incident postmortem settings: the [incident_postmortem] table of the configuration files.

The calendar id is a non-public value (decisions/configuration.md): declared empty in
base.toml, set only from the environment as INCIDENT_POSTMORTEM__CALENDAR_ID.
"""

from functools import lru_cache

from pydantic_settings import SettingsConfigDict

from contracts.configuration import ConfigurationSlice, env_only


class IncidentPostmortemSettings(ConfigurationSlice):
    """Where the retro meeting is booked.

    Environment only (non-public values):
        INCIDENT_POSTMORTEM__CALENDAR_ID.
    """

    model_config = SettingsConfigDict(toml_table_header=("incident_postmortem",), env_prefix="INCIDENT_POSTMORTEM__")

    calendar_id: str = env_only("Google Calendar id the retro meeting is booked on.", "codespaces", default="")


@lru_cache(maxsize=1)
def get_incident_postmortem_settings() -> IncidentPostmortemSettings:
    """Return the process-wide [incident_postmortem] slice."""
    return IncidentPostmortemSettings()
