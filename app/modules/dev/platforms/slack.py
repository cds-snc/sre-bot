"""Slack platform implementation for dev module.

Uses decorator-based command registration via auto-discovery.
Registers all /sre dev subcommands (google, slack, stale, incident, load-incidents, add-incident, aws).

Only available in development environment (PREFIX=dev-).
"""

import structlog
from typing import TYPE_CHECKING, Callable, Any, Dict, List

from infrastructure.platforms.models import CommandPayload, CommandResponse
from infrastructure.services import get_slack_client, get_settings
from modules.dev import google, slack as slack_dev, incident
from modules.dev.aws_dev import aws_dev_router

if TYPE_CHECKING:
    from infrastructure.platforms.providers.slack import SlackPlatformProvider


logger = structlog.get_logger()


def _require_dev_environment(payload: CommandPayload) -> CommandResponse | None:
    """Check if running in development environment.

    Returns:
        CommandResponse with error if not in dev environment, None otherwise
    """
    settings = get_settings()
    if settings.PREFIX != "dev-":
        return CommandResponse(
            message="This command is only available in the development environment.",
            ephemeral=True,
        )
    return None


def _call_legacy_handler(
    payload: CommandPayload,
    handler: Callable,
    *handler_args,
    **handler_kwargs,
) -> CommandResponse:
    """Call a legacy handler and capture its response.

    Args:
        payload: Command payload from platform provider
        handler: Legacy handler function to call
        *handler_args: Positional arguments for handler
        **handler_kwargs: Keyword arguments for handler

    Returns:
        CommandResponse with captured output
    """
    captured_responses: List[str] = []

    def capture_respond(text: str | None = None, **kwargs):
        if text:
            captured_responses.append(text)

    # Get Slack client
    slack_facade = get_slack_client()
    client = slack_facade.raw_client

    # Build legacy body dict from payload
    body = {
        "user_id": payload.user_id,
        "channel_id": payload.channel_id,
    }
    if payload.platform_metadata:
        body.update(payload.platform_metadata)

    # Call handler with standard signature
    handler(
        *handler_args,
        client=client,
        body=body,
        respond=capture_respond,
        **handler_kwargs,
    )

    # Return captured response
    message = (
        "\n".join(captured_responses) if captured_responses else "Command completed"
    )
    return CommandResponse(message=message, ephemeral=True)


def handle_google_dev_command(payload: CommandPayload) -> CommandResponse:
    """Handle /sre dev google - test Google Workspace Directory API."""
    logger.info("command_received", command="google", text=payload.text)

    if error := _require_dev_environment(payload):
        return error

    def noop_ack():
        pass

    return _call_legacy_handler(payload, google.google_service_command, noop_ack)


def handle_slack_dev_command(payload: CommandPayload) -> CommandResponse:
    """Handle /sre dev slack - test Slack API operations."""
    logger.info("command_received", command="slack", text=payload.text)

    if error := _require_dev_environment(payload):
        return error

    def noop_ack():
        pass

    args = payload.text.split() if payload.text else []
    return _call_legacy_handler(
        payload, slack_dev.slack_command, noop_ack, logger=logger, args=args
    )


def handle_stale_dev_command(payload: CommandPayload) -> CommandResponse:
    """Handle /sre dev stale - send test stale channel notification."""
    logger.info("command_received", command="stale", channel_id=payload.channel_id)

    if error := _require_dev_environment(payload):
        return error

    slack_facade = get_slack_client()
    client = slack_facade.raw_client

    text = """👋  Hi! There have been no updates in this incident channel for 14 days! Consider scheduling a retro or archiving it.
Bonjour! Il n'y a pas eu de mise à jour dans ce canal d'incident depuis 14 jours. Pensez à planifier une rétro ou à l'archiver."""

    attachments: List[Dict[str, Any]] = [
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

    try:
        client.chat_postMessage(
            channel=payload.channel_id,
            text=text,
            attachments=attachments,
        )
        return CommandResponse(
            message="Stale channel notification sent (check channel for the message)",
            ephemeral=True,
        )
    except Exception as e:
        logger.error("failed_to_send_stale_notification", error=str(e), exc_info=True)
        return CommandResponse(
            message=f"Failed to send stale notification: {str(e)}",
            ephemeral=True,
        )


def handle_incident_dev_command(payload: CommandPayload) -> CommandResponse:
    """Handle /sre dev incident - list incidents from DynamoDB."""
    logger.info("command_received", command="incident", channel_id=payload.channel_id)

    if error := _require_dev_environment(payload):
        return error

    def noop_ack():
        pass

    return _call_legacy_handler(
        payload, incident.list_incidents, noop_ack, logger=logger
    )


def handle_load_incidents_command(payload: CommandPayload) -> CommandResponse:
    """Handle /sre dev load-incidents - load incidents from Google Sheet."""
    logger.info("command_received", command="load-incidents")

    if error := _require_dev_environment(payload):
        return error

    def noop_ack():
        pass

    return _call_legacy_handler(
        payload, incident.load_incidents, noop_ack, logger=logger
    )


def handle_add_incident_command(payload: CommandPayload) -> CommandResponse:
    """Handle /sre dev add-incident - add incident from current channel."""
    logger.info(
        "command_received", command="add-incident", channel_id=payload.channel_id
    )

    if error := _require_dev_environment(payload):
        return error

    def noop_ack():
        pass

    return _call_legacy_handler(payload, incident.add_incident, noop_ack, logger=logger)


def handle_aws_dev_command(payload: CommandPayload) -> CommandResponse:
    """Handle /sre dev aws - test AWS client integrations.

    Routes to subcommands: identitystore, organizations, sso, health
    """
    logger.info("command_received", command="aws", text=payload.text)

    if error := _require_dev_environment(payload):
        return error

    captured_responses: List[str] = []

    def capture_respond(text: str | None = None, **kwargs):
        if text:
            captured_responses.append(text)

    slack_facade = get_slack_client()
    client = slack_facade.raw_client

    # Build payload for legacy router
    router_payload = {
        "command": {
            "text": payload.text or "",
            "user_id": payload.user_id,
            "channel_id": payload.channel_id,
            **(payload.platform_metadata or {}),
        },
        "client": client,
        "respond": capture_respond,
        "ack": lambda: None,
    }

    try:
        aws_dev_router.handle(router_payload)
    except Exception as e:
        logger.error("aws_dev_router_error", error=str(e), exc_info=True)
        return CommandResponse(
            message=f"AWS command error: {str(e)}",
            ephemeral=True,
        )

    message = (
        "\n".join(captured_responses) if captured_responses else "AWS command executed"
    )
    return CommandResponse(message=message, ephemeral=True)


def register_commands(provider: "SlackPlatformProvider") -> None:
    """Register dev module commands with Slack provider.

    Args:
        provider: Slack platform provider instance
    """
    # Register parent dev command (handler=None means auto-generate help for children)
    provider.register_command(
        command="dev",
        handler=None,
        parent="sre",
        description="Development and testing commands",
        description_key="sre.subcommands.dev.description",
    )

    provider.register_command(
        command="google",
        handler=handle_google_dev_command,
        parent="sre.dev",
        description="Google Workspace development commands",
        description_key="dev.subcommands.google.description",
    )

    provider.register_command(
        command="slack",
        handler=handle_slack_dev_command,
        parent="sre.dev",
        description="Slack development commands",
        description_key="dev.subcommands.slack.description",
    )

    provider.register_command(
        command="stale",
        handler=handle_stale_dev_command,
        parent="sre.dev",
        description="Test stale channel notification",
        description_key="dev.subcommands.stale.description",
    )

    provider.register_command(
        command="incident",
        handler=handle_incident_dev_command,
        parent="sre.dev",
        description="List incidents",
        description_key="dev.subcommands.incident.description",
    )

    provider.register_command(
        command="load-incidents",
        handler=handle_load_incidents_command,
        parent="sre.dev",
        description="Load incidents",
        description_key="dev.subcommands.load_incidents.description",
    )

    provider.register_command(
        command="add-incident",
        handler=handle_add_incident_command,
        parent="sre.dev",
        description="Add incident",
        description_key="dev.subcommands.add_incident.description",
    )

    provider.register_command(
        command="aws",
        handler=handle_aws_dev_command,
        parent="sre.dev",
        description="Test AWS client integrations (identitystore, organizations, sso, health)",
        description_key="dev.subcommands.aws.description",
    )
