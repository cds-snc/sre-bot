"""Slack integration settings."""

from infrastructure.configuration.base import IntegrationSettings


class SlackSettings(IntegrationSettings):
    """Slack API and bot configuration.

    Environment Variables:
        INCIDENT_CHANNEL: Slack channel ID for incident notifications
        SLACK_SECURITY_USER_GROUP_ID: Security team user group ID
        APP_TOKEN: Slack app-level token (xapp-*)
        SLACK_TOKEN: Slack bot token (xoxb-*)

    Example:
        ```python
        from infrastructure.services import get_settings

        settings = get_settings()

        slack_token = settings.slack.SLACK_TOKEN
        incident_channel = settings.slack.INCIDENT_CHANNEL
        ```
    """

    INCIDENT_CHANNEL: str = ""
    SLACK_SECURITY_USER_GROUP_ID: str = ""
    APP_TOKEN: str = ""
    SLACK_TOKEN: str = ""
