"""Incident feature settings."""

from functools import lru_cache

from pydantic import Field

from infrastructure.configuration.base import FeatureSettings


class IncidentFeatureSettings(FeatureSettings):
    """Incident management feature configuration.

    Environment Variables:
        INCIDENT_CHANNEL: Slack channel ID for incident notifications
        SLACK_SECURITY_USER_GROUP_ID: Security team user group ID for mentions
        SLACK_NOTIFY_MGMT_USER_GROUP_ID: Notify management team user group ID for Notify product incidents

    Example:
        ```python
        from infrastructure.configuration import get_settings

        settings = get_settings()

        incident_channel = settings.feat_incident.INCIDENT_CHANNEL
        security_group = settings.feat_incident.SLACK_SECURITY_USER_GROUP_ID
        ```
    """

    INCIDENT_CHANNEL: str | None = Field(default=None, alias="INCIDENT_CHANNEL")
    SLACK_SECURITY_USER_GROUP_ID: str | None = Field(
        default=None, alias="SLACK_SECURITY_USER_GROUP_ID"
    )
    SLACK_NOTIFY_MGMT_USER_GROUP_ID: str | None = Field(
        default=None, alias="SLACK_NOTIFY_MGMT_USER_GROUP_ID"
    )


@lru_cache(maxsize=1)
def get_incident_settings() -> IncidentFeatureSettings:
    """Singleton provider for incident feature settings."""
    return IncidentFeatureSettings()
