import re
from typing import Dict, List, Union

from core.logging import get_module_logger
from models.webhooks import AwsSnsPayload
from modules.webhooks.aws_sns_notification import AwsNotificationPattern
from slack_sdk import WebClient

logger = get_module_logger()


def handle_budget_notification(payload: AwsSnsPayload, client: WebClient) -> List[Dict]:
    """
    Handle AWS Budget notifications from AWS SNS.

    Args:
        payload: The AwsSnsPayload containing the budget information
        client: The Slack WebClient instance

    Returns:
        List of Slack blocks formatted for the budget notification
    """
    # Extract account ID from TopicArn
    regex = r"arn:aws:sns:\w.*:(\d.*):\w.*"
    topic_match = re.search(regex, payload.TopicArn or "")
    account = topic_match.groups()[0] if topic_match else "unknown"

    subject = payload.Subject or "Budget Notification"
    message = payload.Message or "No details available"

    blocks = [
        {"type": "section", "text": {"type": "mrkdwn", "text": " "}},
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*<https://console.amazon.com/billing/home#/budgets| 💸 Budget Alert | {account}>*",
            },
        },
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"{subject}"},
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"{message}"},
        },
    ]

    return blocks


def is_budget_notification(
    payload: AwsSnsPayload, parsed_message: Union[str, dict]
) -> bool:
    """
    Check if the AWS SNS message is a budget notification.

    Args:
        payload: The AwsSnsPayload to check
        parsed_message: The parsed message content

    Returns:
        True if this is a budget notification, False otherwise
    """
    message = payload.Message or ""
    return "AWS Budget Notification" in message


BUDGET_NOTIFICATION_HANDLER: AwsNotificationPattern = AwsNotificationPattern(
    name="budget_notification",
    match_type="callable",
    match_target="message",
    pattern="modules.webhooks.patterns.aws_sns_notification.budget_notification.is_budget_notification",
    handler="modules.webhooks.patterns.aws_sns_notification.budget_notification.handle_budget_notification",
    priority=40,
    enabled=True,
)
