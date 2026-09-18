"""Self-managed rotation configuration and current-assignment calculation."""

from infrastructure.plugins import hookimpl


@hookimpl
def register_slack_commands(provider) -> None:
    """Register the user-rotation Slack commands."""
    from packages.user_rotations.platforms.slack import register_commands

    register_commands(provider)
