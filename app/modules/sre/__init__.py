"""SRE module - Platform command registration."""

from contracts.slack.registrar import SlackCommandRegistrar
from infrastructure.plugins import hookimpl
from modules.sre.platforms import slack


@hookimpl
def register_slack_commands(registrar: SlackCommandRegistrar) -> None:
    """Register SRE module Slack commands."""
    slack.register_commands(registrar)
