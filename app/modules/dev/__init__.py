"""Dev module - Platform command registration.

Only available in development environment (PREFIX=dev-).
Provides testing and development commands for Google Workspace, Slack and incidents.
"""

from contracts.slack.registrar import SlackCommandRegistrar
from infrastructure.plugins import hookimpl
from modules.dev.platforms import slack


@hookimpl
def register_slack_commands(registrar: SlackCommandRegistrar) -> None:
    """Register dev module Slack commands (under /sre dev hierarchy)."""
    slack.register_commands(registrar)
