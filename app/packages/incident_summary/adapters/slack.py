"""Slack adapter — implements ``IncidentChannelPort`` on the Slack Web API.

Each method issues one Web API call and returns the part of the payload the
handler reads. Web API errors propagate; the handler owns each degradation.
"""

from collections.abc import Mapping, Sequence
from typing import Any

from slack_sdk import WebClient

from integrations.slack.client import get_slack_web_client


class SlackIncidentChannel:
    """Read an incident channel's history, metadata and members from Slack."""

    def __init__(self, client: WebClient) -> None:
        self._client = client

    def fetch_history(self, channel_id: str, *, limit: int, oldest: str) -> Sequence[Mapping[str, Any]]:
        """Return up to ``limit`` messages posted since ``oldest``, newest first."""
        response = self._client.conversations_history(channel=channel_id, limit=limit, oldest=oldest)
        return response.get("messages") or []

    def get_channel(self, channel_id: str) -> Mapping[str, Any]:
        """Return the channel object from ``conversations.info``."""
        response = self._client.conversations_info(channel=channel_id)
        return response.get("channel") or {}

    def get_user(self, user_id: str) -> Mapping[str, Any]:
        """Return the user object from ``users.info``."""
        response = self._client.users_info(user=user_id)
        return response.get("user") or {}


def build_incident_channel() -> SlackIncidentChannel:
    """Build the adapter on the bot's Web client."""
    return SlackIncidentChannel(get_slack_web_client())
