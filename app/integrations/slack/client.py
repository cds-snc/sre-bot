from slack_sdk import WebClient
from core.config import settings


class SlackClientManager:
    """Manages the Slack API client. Ensures a single instance is used throughout the application."""

    _client = None

    @classmethod
    def get_client(cls) -> WebClient:
        """Returns a singleton instance of the Slack WebClient."""
        if cls._client is None:
            cls._client = WebClient(token=settings.slack.SLACK_TOKEN)
        return cls._client
