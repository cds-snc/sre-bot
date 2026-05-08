"""Slack client package.

Provides authenticated Slack SDK client with OperationResult error handling.
Settings are available for bootstrap configuration only.
"""

from infrastructure.clients.slack.client import SlackClient
from infrastructure.clients.slack.settings import SlackSettings, get_slack_settings

__all__ = ["SlackClient", "SlackSettings", "get_slack_settings"]
