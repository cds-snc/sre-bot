import re
from typing import Dict, List, Union

from core.logging import get_module_logger
from models.webhooks import AwsSnsPayload
from modules.webhooks.aws_sns_notification import AwsNotificationPattern
from slack_sdk import WebClient

logger = get_module_logger()


def nested_get(dictionary, keys):
    """Safely get nested dictionary values."""
    for key in keys:
        try:
            dictionary = dictionary[key]
        except (KeyError, TypeError):
            return None
    return dictionary


def handle_abuse_notification(payload: AwsSnsPayload, client: WebClient) -> List[Dict]:
    """
    Handle AWS abuse notifications from AWS SNS.

    Args:
        payload: The AwsSnsPayload containing the abuse information
        client: The Slack WebClient instance

    Returns:
        List of Slack blocks formatted for the abuse notification
    """
    try:
        import json

        message = payload.Message
        if message is None:
            return []

        msg = json.loads(message)
    except (json.JSONDecodeError, TypeError):
        logger.warning(
            "failed_to_parse_abuse_notification_message", message=payload.Message
        )
        return []

    # Extract account ID from TopicArn
    regex = r"arn:aws:sns:\w.*:(\d.*):\w.*"
    topic_match = re.search(regex, payload.TopicArn or "")
    account = topic_match.groups()[0] if topic_match else "unknown"

    event_type_code = nested_get(msg, ["detail", "eventTypeCode"]) or "Unknown Event"
    event_description = (
        nested_get(msg, ["detail", "eventDescription", 0, "latestDescription"])
        or "No description available"
    )

    # Format the event type code for display
    formatted_event_type = event_type_code.replace("_", " ")

    blocks = [
        {"type": "section", "text": {"type": "mrkdwn", "text": " "}},
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*<https://health.amazon.com/health/home#/account/dashboard/open-issues| 🚨 Abuse Alert | {account}>*",
            },
        },
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"{formatted_event_type}",
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"{event_description}",
            },
        },
    ]

    return blocks


def is_abuse_notification(
    payload: AwsSnsPayload, parsed_message: Union[str, dict]
) -> bool:
    """
    Check if the AWS SNS message is an abuse notification.

    Args:
        payload: The AwsSnsPayload to check
        parsed_message: The parsed message content

    Returns:
        True if this is an abuse notification, False otherwise
    """
    if not isinstance(parsed_message, dict):
        return False

    # Abuse notifications have a specific structure with service field set to "ABUSE"
    return nested_get(parsed_message, ["detail", "service"]) == "ABUSE"


ABUSE_NOTIFICATION_HANDLER: AwsNotificationPattern = AwsNotificationPattern(
    name="abuse_notification",
    match_type="callable",
    match_target="parsed_message",
    pattern="modules.webhooks.patterns.aws_sns_notification.abuse_notification.is_abuse_notification",
    handler="modules.webhooks.patterns.aws_sns_notification.abuse_notification.handle_abuse_notification",
    priority=45,
    enabled=True,
)
