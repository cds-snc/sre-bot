"""Self-managed rotation configuration and current-assignment calculation."""

from contracts.plugins.namespace import hookimpl
from contracts.slack.registrar import SlackCommandRegistrar


@hookimpl
def register_slack_commands(registrar: SlackCommandRegistrar) -> None:
    """Register the user-rotation Slack commands."""
    from packages.user_rotations.platforms.slack import register_commands

    register_commands(registrar)
