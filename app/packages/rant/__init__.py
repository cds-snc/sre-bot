"""Rant package - shout a message to the channel in bold uppercase."""

from infrastructure.plugins import hookimpl
from packages.rant.platforms import slack
from packages.rant.service import format_rant


@hookimpl
def register_slack_commands(provider):
    """Register rant Slack commands.

    Args:
        provider: Slack platform provider instance.
    """
    slack.register_commands(provider)


__all__ = [
    "format_rant",
]
