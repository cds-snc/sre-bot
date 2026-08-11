"""Slack platform implementation for the rant package."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from integrations.slack.models import CommandPayload, CommandResponse
from packages.rant.service import format_rant

if TYPE_CHECKING:
    from integrations.slack.provider import SlackPlatformProvider

logger = structlog.get_logger()


def register_commands(provider: SlackPlatformProvider) -> None:
    """Register the top-level ``/rant`` Slack command with the provider.

    Registered without a parent so it is exposed as a root slash command
    (``/rant``) rather than a subcommand of ``/sre``.

    Args:
        provider: Slack platform provider instance.
    """
    provider.register_command(
        command="rant",
        handler=handle_rant_command,
        description="Shout a message to the channel in bold uppercase",
        usage_hint="<text>",
        examples=["deploys keep failing"],
    )


def handle_rant_command(payload: CommandPayload) -> CommandResponse:
    """Handle ``/rant <text>`` by posting a bold, uppercase message.

    Args:
        payload: Command payload from the Slack platform provider. ``text``
            holds the full message to shout.

    Returns:
        A non-ephemeral CommandResponse posted to the channel, or an
        ephemeral usage hint when no text is provided.
    """
    log = logger.bind(command="rant", user_id=payload.user_id, channel_id=payload.channel_id)
    text = payload.text.strip()

    if not text:
        log.info("rant_command_empty")
        return CommandResponse(
            message="Usage: `/rant <text>` — shout a message in bold uppercase.",
            ephemeral=True,
        )

    log.info("rant_command_received")
    return CommandResponse(message=format_rant(text), ephemeral=False)
