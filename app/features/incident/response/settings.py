"""Incident response settings: the [incident_response] table of the configuration files.

The declare path's Slack ids are deployment configuration, committed in the environment
file. The handbook id is a non-public value (decisions/configuration.md): declared empty in
base.toml, set only from the environment as INCIDENT_RESPONSE__HANDBOOK_ID. The legacy
declare path in modules/incident reads this slice until it is deleted.
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import SettingsConfigDict

from contracts.configuration import ConfigurationSlice, env_only


class IncidentResponseSettings(ConfigurationSlice):
    """Where a new incident is announced, which groups it invites, and the documents it links to.

    Keys of [incident_response]:
        announcement_channel_id: channel new incidents are announced in; empty for none.
        security_group_id: user group invited to a security incident; empty for none.
        notify_management_group_id: user group invited to a Notify product incident; empty for none.

    Environment only (non-public values):
        INCIDENT_RESPONSE__HANDBOOK_ID.
    """

    model_config = SettingsConfigDict(toml_table_header=("incident_response",), env_prefix="INCIDENT_RESPONSE__")

    announcement_channel_id: str = Field(default="", description="Slack channel id new incidents are announced in.")
    security_group_id: str = Field(default="", description="Slack user group id invited to a security incident.")
    notify_management_group_id: str = Field(default="", description="Slack user group id invited to a Notify product incident.")
    handbook_id: str = env_only("Google Docs id of the incident management handbook.", "codespaces", default="")


@lru_cache(maxsize=1)
def get_incident_response_settings() -> IncidentResponseSettings:
    """Return the process-wide [incident_response] slice."""
    return IncidentResponseSettings()
