"""Slack domain package.

Focused package for Slack bot lifecycle, command routing, and interaction handling.
Client authentication and settings are in infrastructure.clients.slack.
"""

from infrastructure.slack.formatter import SlackBlockKitFormatter
from infrastructure.slack.help import SlackHelpGenerator
from infrastructure.slack.models import (
    CommandDefinition,
    CommandPayload,
    CommandResponse,
)
from infrastructure.slack.parsing import Argument, ArgumentType, CommandArgumentParser
from infrastructure.slack.routing import CommandRouter
from infrastructure.slack.service import SlackBot

__all__ = [
    "SlackBot",
    "CommandRouter",
    "SlackBlockKitFormatter",
    "SlackHelpGenerator",
    "CommandDefinition",
    "CommandPayload",
    "CommandResponse",
    "Argument",
    "ArgumentType",
    "CommandArgumentParser",
]
