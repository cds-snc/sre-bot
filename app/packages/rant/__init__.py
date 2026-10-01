"""Rant package - shout a message to the channel in bold uppercase."""

from contracts.slack.registrar import SlackCommandRegistrar
from infrastructure.plugins import hookimpl
from packages.rant.platforms import slack
from packages.rant.service import format_rant


@hookimpl
def register_slack_commands(registrar: SlackCommandRegistrar) -> None:
    """Register rant Slack commands.

    Args:
        registrar: Slack command registrar.
    """
    slack.register_commands(registrar)


__all__ = [
    "format_rant",
]
