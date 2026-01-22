"""Slack platform implementation for geolocate package."""

from typing import Any, Dict, TYPE_CHECKING

import structlog

from infrastructure.operations import OperationStatus
from infrastructure.platforms.models import CommandPayload, CommandResponse
from infrastructure.platforms.parsing import Argument, ArgumentType
from packages.geolocate.schemas import GeolocateResponse
from packages.geolocate.service import geolocate_ip

if TYPE_CHECKING:
    from infrastructure.platforms.providers.slack import SlackPlatformProvider

logger = structlog.get_logger()


def register_commands(provider: "SlackPlatformProvider") -> None:
    """Register geolocate Slack commands with the provider.

    Args:
        provider: Slack platform provider instance.
    """
    provider.register_command(
        command="geolocate",
        handler=handle_geolocate_command,
        parent="sre",
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
        arguments=[
            Argument(
                name="ip_address",
                type=ArgumentType.STRING,
                required=True,
                description="IPv4 or IPv6 address to geolocate",
            )
        ],
    )


def handle_geolocate_command(
    payload: CommandPayload,
    parsed_args: Dict[str, Any],
) -> CommandResponse:
    """Handle /sre geolocate <ip> Slack command.

    Args:
        payload: Command payload from Slack platform provider
        parsed_args: Parsed and validated command arguments (automatically provided by framework)

    Returns:
        CommandResponse formatted for Slack
    """
    log = logger.bind(
        command="geolocate", user_id=payload.user_id, channel_id=payload.channel_id
    )
    log.info("slack_command_received", text=payload.text)

    # Get the IP address from parsed arguments (framework ensures it's present and valid)
    ip_address = parsed_args.get("ip_address", "").strip()

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
