"""Discord platform implementation for geolocate package."""

from typing import TYPE_CHECKING

import structlog

from infrastructure.operations import OperationStatus
from infrastructure.platforms.models import CommandPayload, CommandResponse
from packages.geolocate.schemas import GeolocateResponse
from packages.geolocate.service import geolocate_ip

if TYPE_CHECKING:
    from infrastructure.platforms.providers.discord import DiscordPlatformProvider

logger = structlog.get_logger()


def register_commands(provider: "DiscordPlatformProvider") -> None:
    """Register geolocate Discord commands with the provider.

    Args:
        provider: Discord platform provider instance.
    """
    # Discord provider is not implemented - command registration available but handlers not implemented yet
    # Uncomment when ready to implement:
    # provider.register_command(
    #     command="geolocate",
    #     handler=handle_geolocate_command,
    #     parent="sre",
    #     description="Lookup the geographic location of an IP address using MaxMind GeoIP database",
    #     description_key="geolocate.discord.description",
    #     usage_hint="<ip_address>",
    #     examples=[
    #         "8.8.8.8",
    #         "1.1.1.1",
    #         "2001:4860:4860::8888",
    #     ],
    #     example_keys=[
    #         "geolocate.examples.google_dns",
    #         "geolocate.examples.cloudflare",
    #         "geolocate.examples.ipv6",
    #     ],
    # )
    pass


def handle_geolocate_command(cmd: CommandPayload) -> CommandResponse:
    """Handle /sre geolocate <ip> Discord command.

    Args:
        cmd: Command payload from Discord platform provider

    Returns:
        CommandResponse formatted for Discord (Embed format)
    """
    log = logger.bind(
        command="geolocate", user_id=cmd.user_id, channel_id=cmd.channel_id
    )
    log.info("discord_command_received", text=cmd.text)

    # Parse command text (expect single IP address)
    ip_address = cmd.text.strip()

    # Call service layer directly (no HTTP overhead)
    result = geolocate_ip(ip_address=ip_address)

    if result.is_success:
        # Build GeolocateResponse from result data
        data = GeolocateResponse(ip_address=ip_address, **result.data)
        return CommandResponse(
            message=_format_success_response(data),
            ephemeral=False,
        )
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


def _format_success_response(data: GeolocateResponse) -> str:
    """Format successful geolocation as Discord message."""
    lines = [f"📍 **Location for {data.ip_address}**"]

    if data.city:
        lines.append(f"• **City:** {data.city}")
    if data.country:
        lines.append(f"• **Country:** {data.country}")
    if data.latitude and data.longitude:
        lines.append(f"• **Coordinates:** {data.latitude}, {data.longitude}")
    if data.time_zone:
        lines.append(f"• **Time Zone:** {data.time_zone}")

    return "\n".join(lines)
