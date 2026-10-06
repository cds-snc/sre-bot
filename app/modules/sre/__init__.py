"""SRE module - Platform command registration."""

from contracts.slack.registrar import SlackCommandRegistrar
from modules.sre.platforms import slack


def register_commands(registrar: SlackCommandRegistrar) -> None:
    """Register SRE module Slack commands."""
    slack.register_commands(registrar)
