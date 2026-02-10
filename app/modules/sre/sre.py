"""SRE Module

This module contains the main command for the SRE bot. It is responsible for handling the `/sre` command and its subcommands.
"""

from typing import Any, Dict

import structlog
from slack_bolt import Ack, App, Respond
from slack_sdk import WebClient

from infrastructure.commands.providers.slack import SlackCommandProvider
from infrastructure.commands.router import CommandRouter
from infrastructure.platforms.models import CommandPayload
from infrastructure.services import get_platform_service
from core.config import settings
from modules.dev.core import dev_router
from modules.groups import create_slack_provider
from modules.incident import incident_helper
from modules.sre import webhook_helper

PREFIX = settings.PREFIX
GIT_SHA = settings.GIT_SHA

logger = structlog.get_logger()


# ============================================================
# COMMAND ROUTER SETUP
# ============================================================

sre_router = CommandRouter(namespace="sre")

# ============================================================
# NEW ARCHITECTURE: groups subcommand
# ============================================================

groups_provider = create_slack_provider(parent_command="sre")
sre_router.register_subcommand(
    name="groups",
    provider=groups_provider,
    platform="slack",
    description="Manage groups and memberships",
    description_key="sre.subcommands.groups.description",
)

# ============================================================
# LEGACY ARCHITECTURE: incident, webhooks, etc.
# Wrapped in adapter providers for router compatibility
# ============================================================


class LegacyIncidentProvider(SlackCommandProvider):
    """Adapter for legacy incident_helper."""

    def __init__(self):
        super().__init__(settings=settings, config={"enabled": True})
        self.registry = None  # Legacy handlers don't use registry

    def handle(self, platform_payload):
        """Delegate to legacy incident handler."""
        self.acknowledge(platform_payload)

        command = platform_payload["command"]
        client = platform_payload["client"]
        respond = platform_payload["respond"]
        ack = platform_payload["ack"]

        text = command.get("text", "")
        args = text.split() if text else []

        incident_helper.handle_incident_command(
            args, client, platform_payload["command"], respond, ack
        )


class LegacyWebhooksProvider(SlackCommandProvider):
    """Adapter for legacy webhook_helper."""

    def __init__(self):
        super().__init__(settings=settings, config={"enabled": True})
        self.registry = None

    def handle(self, platform_payload):
        """Delegate to legacy webhooks handler."""
        self.acknowledge(platform_payload)

        command = platform_payload["command"]
        client = platform_payload["client"]
        respond = platform_payload["respond"]

        text = command.get("text", "")
        args = text.split() if text else []

        webhook_helper.handle_webhook_command(
            args, client, platform_payload["command"], respond
        )


class VersionProvider(SlackCommandProvider):
    """Adapter for version command."""

    def __init__(self):
        super().__init__(settings=settings, config={"enabled": True})
        self.registry = None

    def handle(self, platform_payload):
        """Send version info."""
        self.acknowledge(platform_payload)
        respond = platform_payload["respond"]
        respond(f"SRE Bot version: {GIT_SHA}")


# ============================================================
# REGISTER LEGACY PROVIDERS
# ============================================================

sre_router.register_subcommand(
    name="incident",
    provider=LegacyIncidentProvider(),
    platform="slack",
    description="Manage incidents",
    description_key="sre.subcommands.incident.description",
)

sre_router.register_subcommand(
    name="webhooks",
    provider=LegacyWebhooksProvider(),
    platform="slack",
    description="Manage webhooks",
    description_key="sre.subcommands.webhooks.description",
)


sre_router.register_subcommand(
    name="version",
    provider=VersionProvider(),
    platform="slack",
    description="Show SRE Bot version",
    description_key="sre.subcommands.version.description",
)

sre_router.register_subcommand(
    name="dev",
    provider=dev_router,
    platform="slack",
    description="Development and testing commands",
    description_key="sre.subcommands.dev.description",
)


def register(bot: App) -> None:
    bot.command(f"/{PREFIX}sre")(sre_command)


def _dispatch_platform_command(
    command: Dict[str, Any],
    respond: Respond,
) -> bool:
    text = (command.get("text") or "").strip()
    if text:
        parts = text.split(maxsplit=1)
        command_name = f"sre.{parts[0]}"
        remaining_text = parts[1] if len(parts) > 1 else ""
    else:
        command_name = "sre"
        remaining_text = ""

    try:
        platform_service = get_platform_service()
        slack_provider = platform_service.get_provider("slack")
    except Exception as exc:  # pylint: disable=broad-except
        logger.debug("platform_provider_unavailable", error=str(exc))
        return False

    payload = CommandPayload(
        text=remaining_text,
        user_id=command.get("user_id", ""),
        user_email=command.get("user_email"),
        channel_id=command.get("channel_id"),
        user_locale=command.get("locale", "en-US"),
        response_url=command.get("response_url"),
        platform_metadata=dict(command),
    )

    response = slack_provider.dispatch_command(command_name, payload)
    unknown_command_message = f"Unknown command: {command_name}"
    if response.message == unknown_command_message:
        return False

    response_type = "ephemeral" if response.ephemeral else "in_channel"
    if response.blocks:
        respond(
            text=response.message or "",
            blocks=response.blocks,
            response_type=response_type,
        )
        return True
    if response.attachments:
        respond(
            text=response.message or "",
            attachments=response.attachments,
            response_type=response_type,
        )
        return True
    if response.message:
        respond(text=response.message, response_type=response_type)
        return True

    respond(text="", response_type=response_type)
    return True


def sre_command(
    ack: Ack,
    command: Dict[str, Any],
    respond: Respond,
    client: WebClient,
) -> None:
    """Main /sre command handler - delegates all subcommands to router."""
    ack()
    logger.info(
        "sre_command_received",
        command=command["text"],
        user_id=command["user_id"],
        user_name=command["user_name"],
        channel_id=command["channel_id"],
        channel_name=command["channel_name"],
    )

    # Build standard payload for router
    payload = {
        "command": dict(command),
        "client": client,
        "respond": respond,
        "ack": ack,
    }

    if _dispatch_platform_command(command, respond):
        return

    # Router handles ALL subcommands (new + legacy)
    # Router automatically generates help for empty commands or `/sre help`
    sre_router.handle(payload)
