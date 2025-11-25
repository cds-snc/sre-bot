"""Command adapters for platform-specific integrations."""

from infrastructure.commands.adapters.base import CommandAdapter
from infrastructure.commands.adapters.slack import (
    SlackCommandAdapter,
    SlackResponseChannel,
)

__all__ = [
    "CommandAdapter",
    "SlackCommandAdapter",
    "SlackResponseChannel",
]
