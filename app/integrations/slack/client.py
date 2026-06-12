from slack_sdk import WebClient
from infrastructure.configuration.integrations.slack import SlackSettings


class SlackClientManager:
    """Manages the Slack API client. Ensures a single instance is used throughout the application."""

    _client = None

    @classmethod
    def get_client(cls) -> WebClient:
        """Returns a singleton instance of the Slack WebClient."""
        if cls._client is None:
            slack_settings = SlackSettings()
            cls._client = WebClient(token=slack_settings.SLACK_TOKEN)
        return cls._client
