"""Incident feature settings."""

from pydantic import Field

from infrastructure.configuration.base import FeatureSettings


class IncidentFeatureSettings(FeatureSettings):
    """Incident management feature configuration.

    Environment Variables:
        INCIDENT_CHANNEL: Slack channel ID for incident notifications
        SLACK_SECURITY_USER_GROUP_ID: Security team user group ID for mentions

    Example:
        ```python
        from infrastructure.configuration import settings

        incident_channel = settings.feat_incident.INCIDENT_CHANNEL
        security_group = settings.feat_incident.SLACK_SECURITY_USER_GROUP_ID
        ```
    """

    INCIDENT_CHANNEL: str | None = Field(default=None, alias="INCIDENT_CHANNEL")
    SLACK_SECURITY_USER_GROUP_ID: str | None = Field(
        default=None, alias="SLACK_SECURITY_USER_GROUP_ID"
    )
