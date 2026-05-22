"""Platform provider implementations (Slack)."""

from infrastructure.platforms.providers.base import BasePlatformProvider
from infrastructure.platforms.providers.slack import (
    SlackPlatformProvider,
    get_slack_provider,
)

__all__ = [
    "BasePlatformProvider",
    "SlackPlatformProvider",
    "get_slack_provider",
]
