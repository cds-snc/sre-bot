"""Dev Module - Development and testing commands

This module provides development and testing functionality for the Slack app.
Only available in development environment (PREFIX=dev-).
"""

import structlog
from infrastructure.services.providers import get_settings
from infrastructure.commands.router import CommandRouter
from infrastructure.commands.providers.slack import SlackCommandProvider
from modules.dev import google, slack, incident
from modules.dev.aws_dev import aws_dev_router


PREFIX = get_settings().PREFIX
logger = structlog.get_logger()


# ============================================================
# COMMAND ROUTER SETUP
# ============================================================

dev_router = CommandRouter(namespace="sre dev")


# ============================================================
# PROVIDER IMPLEMENTATIONS
# ============================================================


class AwsDevProvider(SlackCommandProvider):
    """Provider for AWS client testing commands - delegates to aws_dev_router."""

    def __init__(self):
        super().__init__(config={"enabled": True})
        self.registry = None

    def handle(self, platform_payload):
        """Delegate to AWS dev router for all AWS testing commands."""
        self.acknowledge(platform_payload)

        # The AWS router handles all subcommands
        # Platform payload is passed through unchanged
        aws_dev_router.handle(platform_payload)


class GoogleDevProvider(SlackCommandProvider):
    """Adapter for legacy Google dev commands."""

    def __init__(self):
        super().__init__(config={"enabled": True})
        self.registry = None

    def handle(self, platform_payload):
        """Delegate to legacy Google service handler."""
        self.acknowledge(platform_payload)

        ack = platform_payload["ack"]
        client = platform_payload["client"]
        body = platform_payload["command"]
        respond = platform_payload["respond"]

        google.google_service_command(ack, client, body, respond, logger)


class SlackDevProvider(SlackCommandProvider):
    """Adapter for legacy Slack dev commands."""

    def __init__(self):
        super().__init__(config={"enabled": True})
        self.registry = None

    def handle(self, platform_payload):
        """Delegate to legacy Slack handler."""
        self.acknowledge(platform_payload)

        ack = platform_payload["ack"]
        client = platform_payload["client"]
        body = platform_payload["command"]
        respond = platform_payload["respond"]

        text = body.get("text", "")
        args = text.split() if text else []
        # Remove the "slack" subcommand from args
        if args and args[0] == "slack":
            args.pop(0)

        slack.slack_command(ack, client, body, respond, logger, args)


class StaleChannelProvider(SlackCommandProvider):
    """Test stale channel notification."""

    def __init__(self):
        super().__init__(config={"enabled": True})
        self.registry = None

    def handle(self, platform_payload):
        """Send test stale channel notification."""
        self.acknowledge(platform_payload)

        client = platform_payload["client"]
        body = platform_payload["command"]

        logger.info("test_stale_channel_notification_received", body=body)
        text = """👋  Hi! There have been no updates in this incident channel for 14 days! Consider scheduling a retro or archiving it.\n
        Bonjour! Il n'y a pas eu de mise à jour dans ce canal d'incident depuis 14 jours. Pensez à planifier une rétro ou à l'archiver."""
        attachments = [
            {
                "text": "Would you like to archive the channel now or schedule a retro? | Souhaitez-vous archiver le canal maintenant ou planifier une rétro?",
                "fallback": "You are unable to archive the channel | Vous ne pouvez pas archiver ce canal",
                "callback_id": "archive_channel",
                "color": "#3AA3E3",
                "attachment_type": "default",
                "actions": [
                    {
                        "name": "archive",
                        "text": "Archive channel | Canal d'archives",
                        "type": "button",
                        "value": "archive",
                        "style": "danger",
                    },
                    {
                        "name": "schedule_retro",
                        "text": "Schedule Retro | Calendrier rétro",
                        "type": "button",
                        "value": "schedule_retro",
                        "style": "primary",
                    },
                    {
                        "name": "ignore",
                        "text": "Ignore | Ignorer",
                        "type": "button",
                        "value": "ignore",
                    },
                ],
            }
        ]
        client.chat_postMessage(
            channel=body["channel_id"], text=text, attachments=attachments
        )


class ListIncidentsProvider(SlackCommandProvider):
    """List incidents handler."""

    def __init__(self):
        super().__init__(config={"enabled": True})
        self.registry = None

    def handle(self, platform_payload):
        """Delegate to legacy incident list handler."""
        self.acknowledge(platform_payload)

        ack = platform_payload["ack"]
        client = platform_payload["client"]
        body = platform_payload["command"]
        respond = platform_payload["respond"]

        incident.list_incidents(ack, logger, respond, client, body)


class LoadIncidentsProvider(SlackCommandProvider):
    """Load incidents handler."""

    def __init__(self):
        super().__init__(config={"enabled": True})
        self.registry = None

    def handle(self, platform_payload):
        """Delegate to legacy load incidents handler."""
        self.acknowledge(platform_payload)

        ack = platform_payload["ack"]
        client = platform_payload["client"]
        body = platform_payload["command"]
        respond = platform_payload["respond"]

        incident.load_incidents(ack, logger, respond, client, body)


class AddIncidentProvider(SlackCommandProvider):
    """Add incident handler."""

    def __init__(self):
        super().__init__(config={"enabled": True})
        self.registry = None

    def handle(self, platform_payload):
        """Delegate to legacy add incident handler."""
        self.acknowledge(platform_payload)

        ack = platform_payload["ack"]
        client = platform_payload["client"]
        body = platform_payload["command"]
        respond = platform_payload["respond"]

        incident.add_incident(ack, logger, respond, client, body)


# ============================================================
# REGISTER PROVIDERS
# ============================================================

dev_router.register_subcommand(
    name="aws",
    provider=AwsDevProvider(),
    platform="slack",
    description="Test AWS client integrations (identitystore, organizations, sso, health)",
    description_key="dev.subcommands.aws.description",
)

dev_router.register_subcommand(
    name="google",
    provider=GoogleDevProvider(),
    platform="slack",
    description="Google Workspace development commands",
    description_key="dev.subcommands.google.description",
)

dev_router.register_subcommand(
    name="slack",
    provider=SlackDevProvider(),
    platform="slack",
    description="Slack development commands",
    description_key="dev.subcommands.slack.description",
)

dev_router.register_subcommand(
    name="stale",
    provider=StaleChannelProvider(),
    platform="slack",
    description="Test stale channel notification",
    description_key="dev.subcommands.stale.description",
)

dev_router.register_subcommand(
    name="incident",
    provider=ListIncidentsProvider(),
    platform="slack",
    description="List incidents",
    description_key="dev.subcommands.incident.description",
)

dev_router.register_subcommand(
    name="load-incidents",
    provider=LoadIncidentsProvider(),
    platform="slack",
    description="Load incidents",
    description_key="dev.subcommands.load_incidents.description",
)

dev_router.register_subcommand(
    name="add-incident",
    provider=AddIncidentProvider(),
    platform="slack",
    description="Add incident",
    description_key="dev.subcommands.add_incident.description",
)


# ============================================================
# MAIN COMMAND HANDLER
# ============================================================


def dev_command(ack, respond, client, body, args):
    """Main dev command handler - delegates all subcommands to router.

    Only available in development environment (PREFIX=dev-).
    """
    ack()

    if PREFIX != "dev-":
        respond("This command is only available in the development environment.")
        return

    logger.info(
        "dev_command_received",
        command=body.get("text", ""),
        user_id=body.get("user_id"),
        user_name=body.get("user_name"),
        channel_id=body.get("channel_id"),
    )

    # Build standard payload for router
    payload = {
        "command": dict(body),
        "client": client,
        "respond": respond,
        "ack": ack,
    }

    # Router handles ALL subcommands
    # Router automatically generates help for empty commands
    dev_router.handle(payload)
