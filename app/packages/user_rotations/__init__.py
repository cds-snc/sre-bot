"""Self-managed rotation configuration and current-assignment calculation."""

from contracts.plugins.namespace import hookimpl
from contracts.slack.registrar import SlackCommandRegistrar
from packages.user_rotations.platforms.slack import register_commands


@hookimpl
def register_slack_commands(registrar: SlackCommandRegistrar) -> None:
    """Register the user-rotation Slack commands."""
    register_commands(registrar)
