import json
import re

from slack_sdk import WebClient

from models.webhooks import AwsSnsPayload
from modules.webhooks.aws_sns_notification import AwsNotificationPattern


def _message_text(payload: AwsSnsPayload) -> str:
    message = payload.Message or ""
    try:
        decoded_message = json.loads(message)
    except json.JSONDecodeError, TypeError:
        return message

    if isinstance(decoded_message, str):
        return decoded_message
    return message


def _extract_fields(message: str) -> tuple[str, dict[str, str]]:
    lines = [line.strip() for line in message.splitlines() if line.strip()]
    title = lines[0] if lines else "Unexpected DynamoDB access"
    fields: dict[str, str] = {}

    for line in lines[1:]:
        match = re.match(r"^(?P<key>[A-Za-z ]+):\s*(?P<value>.*)$", line)
        if not match:
            continue

        key = match.group("key").strip().lower().replace(" ", "_")
        fields[key] = match.group("value").strip()

    return title, fields


def _field_line(label: str, value: str) -> str:
    if not value:
        return ""
    return f"*{label}:* `{value}`"


def handle_dynamodb_access(payload: AwsSnsPayload, client: WebClient) -> list[dict]:
    """
    Handle unexpected DynamoDB access notifications from AWS SNS.

    The incoming SNS Message may be a JSON-encoded string, so decode it before
    extracting the line-oriented alert details.
    """
    message = _message_text(payload)
    title, fields = _extract_fields(message)

    detail_lines = [
        _field_line("Event", fields.get("event", "")),
        _field_line("Principal", fields.get("principal", "")),
        _field_line(
            "Source IP",
            fields.get("source_ip", "") or fields.get("source_ip_address", ""),
        ),
        _field_line("Region", fields.get("region", "")),
        _field_line("Resource", fields.get("resource", "")),
        _field_line("Time", fields.get("time", "")),
    ]
    details = "\n".join(line for line in detail_lines if line)

    blocks = [
        {"type": "section", "text": {"type": "mrkdwn", "text": " "}},
        {
            "type": "header",
            "text": {"type": "plain_text", "text": title[:150]},
        },
    ]

    if details:
        blocks.append(
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": details},
            }
        )
    else:
        blocks.append(
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": message},
            }
        )

    return blocks


def is_dynamodb_access(payload: AwsSnsPayload, parsed_message: str | dict) -> bool:
    """
    Check if the AWS SNS message is an unexpected DynamoDB access notification.
    """
    message = parsed_message if isinstance(parsed_message, str) else _message_text(payload)

    return "Unexpected DynamoDB access" in message


DYNAMODB_ACCESS_HANDLER: AwsNotificationPattern = AwsNotificationPattern(
    name="dynamodb_access",
    match_type="callable",
    match_target="parsed_message",
    pattern="modules.webhooks.patterns.aws_sns_notification.dynamodb_access.is_dynamodb_access",
    handler="modules.webhooks.patterns.aws_sns_notification.dynamodb_access.handle_dynamodb_access",
    priority=55,
    enabled=True,
)
