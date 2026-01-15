"""Slack platform features for geolocate package."""

from typing import Any, Dict

import structlog

from infrastructure.operations import OperationStatus
from infrastructure.platforms.models import CommandPayload, CommandResponse
from infrastructure.services import (
    get_slack_provider,
)  # ✅ Ergonomic accessor (validated pattern)
from packages.geolocate.schemas import GeolocateResponse
from packages.geolocate.service import geolocate_ip


logger = structlog.get_logger()


def handle_geolocate_command(cmd: CommandPayload) -> CommandResponse:
    """Handle /geolocate <ip> Slack command.

    Args:
        cmd: Command payload from Slack platform provider

    Returns:
        CommandResponse formatted for Slack
    """
    log = logger.bind(
        command="geolocate", user_id=cmd.user_id, channel_id=cmd.channel_id
    )
    log.info("slack_command_received", text=cmd.text)

    # Parse command text (expect single IP address)
    ip_address = cmd.text.strip()

    # Call service layer directly (no HTTP overhead)
    result = geolocate_ip(ip_address=ip_address)

    if result.is_success:
        # Build GeolocateResponse from result data
        data = GeolocateResponse(ip_address=ip_address, **result.data)
        blocks = _format_success_blocks(data)
        return CommandResponse(message="", ephemeral=False, blocks=blocks)
    elif result.status == OperationStatus.NOT_FOUND:
        return CommandResponse(
            message=f"❌ Location not found for IP: {ip_address}",
            ephemeral=True,
        )
    elif result.status == OperationStatus.PERMANENT_ERROR:
        return CommandResponse(message=f"❌ {result.message}", ephemeral=True)
    else:
        log.error("service_error", status=result.status, error=result.message)
        return CommandResponse(
            message="❌ Geolocation service error. Please try again.",
            ephemeral=True,
        )


def _format_success_blocks(data: GeolocateResponse) -> list[Dict[str, Any]]:
    """Format successful geolocation as Slack blocks."""
    fields = []

    if data.city:
        fields.append({"type": "mrkdwn", "text": f"*City:*\n{data.city}"})
    if data.country:
        fields.append({"type": "mrkdwn", "text": f"*Country:*\n{data.country}"})
    if data.latitude and data.longitude:
        fields.append(
            {
                "type": "mrkdwn",
                "text": f"*Coordinates:*\n{data.latitude}, {data.longitude}",
            }
        )
    if data.time_zone:
        fields.append({"type": "mrkdwn", "text": f"*Time Zone:*\n{data.time_zone}"})

    return [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"📍 Location for {data.ip_address}",
            },
        },
        {"type": "section", "fields": fields},
    ]


# ============================================================
# PUBLIC REGISTRATION FUNCTION - Called explicitly from main.py
# ============================================================
# This follows the FastAPI pattern: explicit registration, not auto-discovery


def register_slack_commands() -> None:
    """Register geolocate Slack commands.

    This function should be called explicitly from main.py during startup,
    just like FastAPI's app.include_router() pattern.

    Pattern validated in docs/architecture-review/PLATFORM_PROVIDERS_VALIDATION.md
    - ✅ Explicit registration (called from main.py)
    - ✅ Uses ergonomic accessor (get_slack_provider)
    - ✅ No import side-effects
    - ✅ Testable (can mock get_slack_provider)

    Example:
        # main.py
        from packages.geolocate.slack import register_slack_commands

        register_slack_commands()  # Explicit registration
    """
    logger.info("registering_slack_commands", package="geolocate")

    # Use ergonomic accessor (validated pattern - Phase 1 enhancement)
    slack_provider = get_slack_provider()

    # Register command with Slack provider (using parent="sre" for hierarchical structure)
    slack_provider.register_command(
        command="geolocate",
        handler=handle_geolocate_command,
        description="Lookup the geographic location of an IP address using MaxMind GeoIP database",
        description_key="geolocate.slack.description",
        usage_hint="<ip_address>",
        examples=[
            "8.8.8.8",
            "1.1.1.1",
            "2001:4860:4860::8888",
        ],
        example_keys=[
            "geolocate.examples.google_dns",
            "geolocate.examples.cloudflare",
            "geolocate.examples.ipv6",
        ],
        parent="sre",
    )

    logger.info("slack_commands_registered", package="geolocate", count=1)
