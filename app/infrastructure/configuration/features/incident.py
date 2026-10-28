"""Incident feature settings: the [incident] table of the configuration files."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import SettingsConfigDict

from contracts.configuration import ConfigurationSlice


class IncidentFeatureSettings(ConfigurationSlice):
    """Where the legacy declare path announces an incident and which user groups it invites.

    Slack ids are deployment configuration, never a secret: production.toml holds them. Field
    names stay until the incident response slice takes the table over (TASK-111.15.1), which
    also standardises the keys.

    Keys of [incident]:
        incident_channel: channel the declare path announces new incidents in; empty for none.
        slack_security_user_group_id: user group invited to a security incident; empty for none.
        slack_notify_mgmt_user_group_id: user group invited to a Notify product incident; empty for none.
    """

    model_config = SettingsConfigDict(toml_table_header=("incident",), env_prefix="INCIDENT__")

    INCIDENT_CHANNEL: str = Field(default="", description="Slack channel id for incident announcements")
    SLACK_SECURITY_USER_GROUP_ID: str = Field(default="", description="Slack user group id invited to security incidents")
    SLACK_NOTIFY_MGMT_USER_GROUP_ID: str = Field(
        default="", description="Slack user group id invited to Notify product incidents"
    )


@lru_cache(maxsize=1)
def get_incident_settings() -> IncidentFeatureSettings:
    """Singleton provider for incident feature settings."""
    return IncidentFeatureSettings()
