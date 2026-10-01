"""Slack platform implementation for the rant package."""

from typing import TYPE_CHECKING

import structlog
from slack_sdk import WebClient

from contracts.slack.models import CommandPayload, CommandResponse
from packages.rant.providers import get_user_identity_lookup
from packages.rant.service import UserIdentity, UserIdentityLookup, format_rant

if TYPE_CHECKING:
    from integrations.slack.provider import SlackPlatformProvider

logger = structlog.get_logger()


def register_commands(provider: SlackPlatformProvider) -> None:
    """Register the top-level ``/rant`` Slack command with the provider.

    Registered without a parent so it is exposed as a root slash command
    (``/rant``) rather than a subcommand of ``/sre``.

    The registered handler is wrapped so it receives the provider's Slack Web
    API client at dispatch time, which is needed to post the message with the
    invoking user's name and avatar (``chat:write.customize``). The user's
    identity is resolved through the package's ``UserIdentityLookup``.

    Args:
        provider: Slack platform provider instance.
    """

    def _dispatch(payload: CommandPayload) -> CommandResponse:
        # Read the client lazily: it is only populated after the provider has
        # started, which happens after command registration.
        return handle_rant_command(payload, provider.client, get_user_identity_lookup())

    provider.register_command(
        command="rant",
        handler=_dispatch,
        description="Shout a message to the channel in bold uppercase",
        usage_hint="<text>",
        examples=["deploys keep failing"],
    )


def handle_rant_command(
    payload: CommandPayload,
    client: WebClient | None,
    identities: UserIdentityLookup,
) -> CommandResponse:
    """Handle ``/rant <text>`` by posting a bold, uppercase message.

    The message is posted with the invoking user's display name and avatar via
    the Slack ``chat:write.customize`` capability, so it visually appears to
    come from that user (the bot remains the technical author, indicated by a
    small ``APP`` badge).

    If the user's identity cannot be resolved or the customized post fails (for
    example, the ``chat:write.customize`` scope is missing), the command
    gracefully falls back to posting as the bot with a mention prefix
    (``<@user_id> ranted: ...``).

    Args:
        payload: Command payload from the Slack platform provider. ``text``
            holds the full message to shout.
        client: Slack Web API client used to post the customized message.
            May be ``None`` before startup.
        identities: Lookup resolving the invoking user's name and avatar.

    Returns:
        An ephemeral confirmation when the message is posted as the user, an
        ephemeral usage hint when no text is provided, or a non-ephemeral
        fallback message attributed via mention when customization is
        unavailable.
    """
    log = logger.bind(command="rant", user_id=payload.user_id, channel_id=payload.channel_id)
    text = payload.text.strip()

    if not text:
        log.info("rant_command_empty")
        return CommandResponse(
            message="Usage: `/rant <text>` — shout a message in bold uppercase.",
            ephemeral=True,
        )

    formatted = format_rant(text)
    identity = _resolve_user_identity(identities, payload.user_id, log) if client else None

    if client is not None and payload.channel_id and identity is not None:
        try:
            client.chat_postMessage(
                channel=payload.channel_id,
                text=formatted,
                username=identity.display_name,
                icon_url=identity.icon_url,
            )
            log.info("rant_command_posted_as_user")
            return CommandResponse(message="✅ Ranted.", ephemeral=True)
        except Exception as e:
            log.warning("rant_post_as_user_failed", error=str(e))

    # Fallback: post as the bot, attributed to the user via a mention prefix.
    log.info("rant_command_posted_as_bot")
    return CommandResponse(message=f"<@{payload.user_id}> ranted: {formatted}", ephemeral=False)


def _resolve_user_identity(
    identities: UserIdentityLookup,
    user_id: str,
    log: structlog.stdlib.BoundLogger,
) -> UserIdentity | None:
    """Resolve the display name and avatar for a Slack user.

    Args:
        identities: Lookup resolving a user's name and avatar.
        user_id: Slack user ID to look up.
        log: Bound logger for contextual logging.

    Returns:
        The user's identity, or ``None`` if the lookup fails or returns no
        usable profile data.
    """
    try:
        return identities.lookup_user_identity(user_id)
    except Exception as e:
        log.warning("rant_user_identity_lookup_failed", error=str(e))
        return None
