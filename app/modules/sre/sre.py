"""SRE Module

This module contains the main command for the SRE bot. It is responsible for handling the `/sre` command and its subcommands.
"""

import structlog
from core.config import settings
from infrastructure.commands.router import CommandRouter
from infrastructure.commands.providers.slack import SlackCommandProvider
from modules.groups import create_slack_provider
from modules.incident import incident_helper
from modules.sre import geolocate_helper, webhook_helper
from modules.dev.core import dev_command
from slack_bolt import Ack, App, Respond
from slack_sdk import WebClient

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
        super().__init__(config={"enabled": True})
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
        super().__init__(config={"enabled": True})
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


class GeolocateProvider(SlackCommandProvider):
    """Adapter for geolocate helper."""

    def __init__(self):
        super().__init__(config={"enabled": True})
        self.registry = None

    def handle(self, platform_payload):
        """Handle geolocate command."""
        self.acknowledge(platform_payload)

        command = platform_payload["command"]
        respond = platform_payload["respond"]

        text = command.get("text", "")
        args = text.split() if text else []

        if not args:
            respond("Please provide an IP address.\n" "SVP fournir une adresse IP")
            return

        geolocate_helper.geolocate(args, respond)


class VersionProvider(SlackCommandProvider):
    """Adapter for version command."""

    def __init__(self):
        super().__init__(config={"enabled": True})
        self.registry = None

    def handle(self, platform_payload):
        """Send version info."""
        self.acknowledge(platform_payload)
        respond = platform_payload["respond"]
        respond(f"SRE Bot version: {GIT_SHA}")


class LegacyTestProvider(SlackCommandProvider):
    """Adapter for legacy test command."""

    def __init__(self):
        super().__init__(config={"enabled": True})
        self.registry = None

    def handle(self, platform_payload):
        """Delegate to legacy test handler."""
        self.acknowledge(platform_payload)

        command = platform_payload["command"]
        client = platform_payload["client"]
        respond = platform_payload["respond"]
        ack = platform_payload["ack"]

        text = command.get("text", "")
        args = text.split() if text else []

        dev_command(ack, respond, client, command, args)


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
    name="geolocate",
    provider=GeolocateProvider(),
    platform="slack",
    description="Geolocate an IP address",
    description_key="sre.subcommands.geolocate.description",
)

sre_router.register_subcommand(
    name="version",
    provider=VersionProvider(),
    platform="slack",
    description="Show SRE Bot version",
    description_key="sre.subcommands.version.description",
)

sre_router.register_subcommand(
    name="test",
    provider=LegacyTestProvider(),
    platform="slack",
    description="Run test commands",
    description_key="sre.subcommands.test.description",
)


def register(bot: App):
    bot.command(f"/{PREFIX}sre")(sre_command)


def sre_command(
    ack: Ack,
    command,
    respond: Respond,
    client: WebClient,
):
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

    # Router handles ALL subcommands (new + legacy)
    # Router automatically generates help for empty commands or `/sre help`
    sre_router.handle(payload)
