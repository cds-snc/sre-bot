"""Platform provider implementations (Slack)."""

from infrastructure.platforms.providers.base import BasePlatformProvider
from infrastructure.platforms.providers.slack import SlackPlatformProvider

__all__ = [
    "BasePlatformProvider",
    "SlackPlatformProvider",
]
