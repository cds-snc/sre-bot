"""Incident response settings: the [incident_response] table of the configuration files.

The handbook id is a non-public value (decisions/configuration.md): declared empty in
base.toml, set only from the environment as INCIDENT_RESPONSE__HANDBOOK_ID.
"""

from functools import lru_cache

from pydantic_settings import SettingsConfigDict

from contracts.configuration import ConfigurationSlice, env_only


class IncidentResponseSettings(ConfigurationSlice):
    """Documents the live incident links to.

    Environment only (non-public values):
        INCIDENT_RESPONSE__HANDBOOK_ID.
    """

    model_config = SettingsConfigDict(toml_table_header=("incident_response",), env_prefix="INCIDENT_RESPONSE__")

    handbook_id: str = env_only("Google Docs id of the incident management handbook.", "codespaces", default="")


@lru_cache(maxsize=1)
def get_incident_response_settings() -> IncidentResponseSettings:
    """Return the process-wide [incident_response] slice."""
    return IncidentResponseSettings()
