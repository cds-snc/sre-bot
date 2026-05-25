"""Slack platform implementation for geolocate package."""

from typing import TYPE_CHECKING, Any, Dict

import structlog

from infrastructure.i18n import t
from infrastructure.operations import OperationStatus
from integrations.slack.models import CommandPayload, CommandResponse
from integrations.slack.parser import Argument, ArgumentType
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
        description_key="geolocate.description",
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
        locale = payload.user_locale or "en-US"
        blocks = _format_success_blocks(data, locale=locale)
        return CommandResponse(message="", ephemeral=False, blocks=blocks)
    elif result.status == OperationStatus.NOT_FOUND:
        locale = payload.user_locale or "en-US"
        msg = t(
            "geolocate.result.not_found",
            locale,
            f"❌ Location not found for IP: {ip_address}",
            ip_address=ip_address,
        )
        return CommandResponse(message=msg, ephemeral=True)
    elif result.status == OperationStatus.PERMANENT_ERROR:
        return CommandResponse(message=f"❌ {result.message}", ephemeral=True)
    else:
        log.error("service_error", status=result.status, error=result.message)
        locale = payload.user_locale or "en-US"
        msg = t(
            "geolocate.result.service_error",
            locale,
            "❌ Geolocation service error. Please try again.",
        )
        return CommandResponse(message=msg, ephemeral=True)


def _format_success_blocks(
    data: GeolocateResponse, locale: str = "en-US"
) -> list[Dict[str, Any]]:
    """Format successful geolocation as Slack blocks."""
    fields = []

    if data.city:
        label = t("geolocate.result.city_label", locale, "City")
        fields.append({"type": "mrkdwn", "text": f"*{label}:*\n{data.city}"})
    if data.country:
        label = t("geolocate.result.country_label", locale, "Country")
        fields.append({"type": "mrkdwn", "text": f"*{label}:*\n{data.country}"})
    if data.country_code:
        label = t("geolocate.result.country_code_label", locale, "Country Code")
        fields.append({"type": "mrkdwn", "text": f"*{label}:*\n{data.country_code}"})
    if data.postal_code:
        label = t("geolocate.result.postal_code_label", locale, "Postal Code")
        fields.append({"type": "mrkdwn", "text": f"*{label}:*\n{data.postal_code}"})
    if data.latitude is not None and data.longitude is not None:
        label = t("geolocate.result.coordinates_label", locale, "Coordinates")
        coordinates_text = f"{data.latitude}, {data.longitude}"
        if data.map_links:
            coordinates_text = (
                f"{coordinates_text}\n<{data.map_links.openstreetmap}|OpenStreetMap>"
            )
        fields.append(
            {
                "type": "mrkdwn",
                "text": f"*{label}:*\n{coordinates_text}",
            }
        )
    if data.time_zone:
        label = t("geolocate.result.time_zone_label", locale, "Time Zone")
        fields.append({"type": "mrkdwn", "text": f"*{label}:*\n{data.time_zone}"})

    if not fields:
        no_data = t(
            "geolocate.result.no_data",
            locale,
            "No location data available for this IP.",
        )
        fields.append({"type": "mrkdwn", "text": f"*Details:*\n{no_data}"})

    header_text = t(
        "geolocate.result.header",
        locale,
        f"📍 Location for {data.ip_address}",
        ip_address=data.ip_address,
    )
    return [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": header_text,
            },
        },
        {"type": "section", "fields": fields},
    ]
