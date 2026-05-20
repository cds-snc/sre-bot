"""SRE module - Platform command registration."""

from infrastructure.plugins import hookimpl
from modules.sre.platforms import slack


@hookimpl
def register_slack_commands(provider):
    """Register SRE module Slack commands."""
    slack.register_commands(provider)
