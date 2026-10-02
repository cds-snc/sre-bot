import json
import re
from dataclasses import dataclass

from slack_sdk import WebClient

from models.webhooks import AwsSnsPayload
from modules.webhooks.aws_sns_notification import AwsNotificationPattern

BLAZER_SUBJECT = "Blazer check"
BLAZER_SOURCE = "blazer"

# Slack rejects header text over 150 characters and section text over 3000.
HEADER_MAX_LENGTH = 150
SECTION_MAX_LENGTH = 3000

STATE_EMOJI = {
    "passing": "✅",
    "failing": "🔥",
    "error": "⚠️",
    "timed out": "⏱️",
    "disabled": "🚫",
}
DEFAULT_EMOJI = "🔔"

# Blazer's plain text title, e.g. "Check Failing: my query".
PLAIN_TEXT_TITLE = re.compile(r"^Check (?P<state>.+?): (?P<name>.+)$")


@dataclass(frozen=True)
class BlazerCheck:
    """A Blazer check notification normalised from either supported wire format."""

    title: str
    state: str | None = None
    url: str | None = None
    description: str | None = None
    detail: str | None = None


def _parse_plain_text(message: str) -> BlazerCheck:
    """Parse Blazer's default Slack text: title, optional detail lines, then a link.

    Blazer escapes `&`, `<` and `>` itself, so the text is passed through as is.
    """
    lines = [line.strip() for line in message.splitlines() if line.strip()]
    if not lines:
        return BlazerCheck(title="Blazer check")

    title = lines[0]
    rest = lines[1:]
    url = rest.pop() if rest and rest[-1].startswith(("http://", "https://")) else None
    detail = "\n".join(rest) or None

    match = PLAIN_TEXT_TITLE.match(title)
    if match:
        return BlazerCheck(title=match["name"], state=match["state"], url=url, detail=detail)
    return BlazerCheck(title=title, url=url, detail=detail)


def _escape(text: str) -> str:
    """Escape the characters Slack treats as control sequences in mrkdwn."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _parse_json(data: dict) -> BlazerCheck:
    """Parse the structured form, which can carry the query description.

    Fields: `query_name`, `state`, `query_url`, `description` and `message`.
    """

    def text(key: str) -> str | None:
        value = data.get(key)
        return _escape(str(value)) if value else None

    return BlazerCheck(
        title=str(data.get("query_name") or "Blazer check"),
        state=str(data["state"]) if data.get("state") else None,
        url=str(data["query_url"]) if data.get("query_url") else None,
        description=text("description"),
        detail=text("message"),
    )


def _section(text: str) -> dict:
    return {"type": "section", "text": {"type": "mrkdwn", "text": text[:SECTION_MAX_LENGTH]}}


def handle_blazer_check(payload: AwsSnsPayload, client: WebClient) -> list[dict]:
    """
    Handle Blazer check notifications published to SNS.

    Accepts both Blazer's default plain text message and the structured JSON form
    (marked with `"source": "blazer"`), which can additionally carry the query description.

    Args:
        payload: The AwsSnsPayload containing the Blazer check notification
        client: The Slack WebClient instance

    Returns:
        List of Slack blocks formatted for the Blazer check notification
    """
    message = payload.Message or ""
    try:
        data = json.loads(message)
    except json.JSONDecodeError, TypeError:
        data = None

    check = _parse_json(data) if isinstance(data, dict) else _parse_plain_text(message)

    emoji = STATE_EMOJI.get((check.state or "").lower(), DEFAULT_EMOJI)
    banner = f"{emoji} Blazer Check"
    banner = f"<{check.url}|{banner}>" if check.url else banner

    blocks = [
        {"type": "section", "text": {"type": "mrkdwn", "text": " "}},
        _section(f"*{banner}*"),
        {"type": "header", "text": {"type": "plain_text", "text": check.title[:HEADER_MAX_LENGTH]}},
    ]
    if check.description:
        blocks.append(_section(check.description))
    if check.detail:
        blocks.append(_section(check.detail))
    if check.state:
        blocks.append({"type": "section", "fields": [{"type": "mrkdwn", "text": f"*State:*\n {check.state}"}]})

    return blocks


def is_blazer_check_notification(payload: AwsSnsPayload, parsed_message: str | dict) -> bool:
    """
    Check if the AWS SNS message is a Blazer check notification.

    Args:
        payload: The AwsSnsPayload to check
        parsed_message: The parsed message content

    Returns:
        True if the subject is Blazer's or the JSON message is marked as from Blazer
    """
    if payload.Subject == BLAZER_SUBJECT:
        return True
    return isinstance(parsed_message, dict) and parsed_message.get("source") == BLAZER_SOURCE


BLAZER_CHECK_HANDLER: AwsNotificationPattern = AwsNotificationPattern(
    name="blazer_check",
    match_type="callable",
    match_target="message",
    pattern="modules.webhooks.patterns.aws_sns_notification.blazer_check.is_blazer_check_notification",
    handler="modules.webhooks.patterns.aws_sns_notification.blazer_check.handle_blazer_check",
    priority=45,
    enabled=True,
)
