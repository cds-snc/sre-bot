"""Dev module - Platform command registration.

Only available in development environment (PREFIX=dev-).
Provides testing and development commands for Google Workspace, Slack, AWS, and incidents.
"""

from infrastructure.services import hookimpl
from modules.dev.platforms import slack


@hookimpl
def register_slack_commands(provider):
    """Register dev module Slack commands (under /sre dev hierarchy)."""
    slack.register_commands(provider)
