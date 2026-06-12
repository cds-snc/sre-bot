from slack_sdk import WebClient
from integrations.slack.settings import get_slack_settings


class SlackClientManager:
    """Manages the Slack API client. Ensures a single instance is used throughout the application."""

    _client = None

    @classmethod
    def get_client(cls) -> WebClient:
        """Returns a singleton instance of the Slack WebClient."""
        if cls._client is None:
            settings = get_slack_settings()
            cls._client = WebClient(token=settings.BOT_TOKEN)
        return cls._client
