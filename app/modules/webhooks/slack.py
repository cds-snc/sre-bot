import ipaddress
import re
from urllib.parse import quote

from infrastructure.configuration import get_settings
from integrations.slack.users import (
    replace_users_emails_in_dict,
    replace_users_emails_with_mention,
)
from models.webhooks import WebhookPayload

IP_ADDRESS_PATTERN = re.compile(
    r"(?<![\w./:-])"
    r"("
    r"(?:\d{1,3}\.){3}\d{1,3}"
    r"|"
    r"(?:[0-9A-Fa-f]{1,4}:){2,}[0-9A-Fa-f:.]*"
    r")"
    r"(?![\w/:-])"
)


def map_emails_to_slack_users(webhook_payload: WebhookPayload) -> WebhookPayload:
    """Replace email addresses in a Slack webhook payload's 'blocks' or top-level 'text'
    with Slack user mentions when resolvable; return the modified payload."""
    if webhook_payload.text:
        webhook_payload.text = replace_users_emails_with_mention(webhook_payload.text)
    if webhook_payload.blocks:
        webhook_payload.blocks = replace_users_emails_in_dict(webhook_payload.blocks)
    return webhook_payload


def _is_inside_slack_link(text: str, start: int) -> bool:
    last_open = text.rfind("<", 0, start)
    last_close = text.rfind(">", 0, start)
    return last_open > last_close


def _geolocate_url(ip_address: str, base_url: str | None = None) -> str:
    if base_url is None:
        base_url = get_settings().server.BACKEND_URL
    return f"{base_url.rstrip('/')}/geolocate/{quote(ip_address, safe='')}"


def link_ip_addresses_to_geolocate(text: str, base_url: str | None = None) -> str:
    """Replace valid IP addresses in Slack text with geolocation links."""

    def replace_match(match: re.Match) -> str:
        ip_address = match.group(1)
        if _is_inside_slack_link(text, match.start(1)):
            return ip_address

        try:
            ipaddress.ip_address(ip_address)
        except ValueError:
            return ip_address

        return f"<{_geolocate_url(ip_address, base_url)}|{ip_address}>"

    return IP_ADDRESS_PATTERN.sub(replace_match, text)


def link_ip_addresses_in_dict(data, base_url: str | None = None):
    """Recursively replace IP addresses in all string values with Slack links."""
    if isinstance(data, dict):
        return {k: link_ip_addresses_in_dict(v, base_url) for k, v in data.items()}
    elif isinstance(data, list):
        return [link_ip_addresses_in_dict(item, base_url) for item in data]
    elif isinstance(data, str):
        return link_ip_addresses_to_geolocate(data, base_url)
    else:
        return data


def hydrate_ip_addresses(webhook_payload: WebhookPayload) -> WebhookPayload:
    """Link IP addresses in a Slack webhook payload to the geolocation endpoint."""
    if isinstance(webhook_payload.text, str) and webhook_payload.text:
        webhook_payload.text = link_ip_addresses_to_geolocate(webhook_payload.text)
    if isinstance(webhook_payload.blocks, (dict, list)) and webhook_payload.blocks:
        webhook_payload.blocks = link_ip_addresses_in_dict(webhook_payload.blocks)
    return webhook_payload
