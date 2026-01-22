"""Dev module - Platform command registration."""

from infrastructure.services import hookimpl
from modules.dev.platforms import slack as slack_platform


@hookimpl
def register_slack_commands(provider):
    """Register dev module Slack commands."""
    slack_platform.register_commands(provider)
