import re
from typing import Dict, List, Union

from core.logging import get_module_logger
from models.webhooks import AwsSnsPayload
from modules.webhooks.aws_sns_notification import AwsNotificationPattern
from slack_sdk import WebClient

logger = get_module_logger()


def handle_iam_user_notification(
    payload: AwsSnsPayload, client: WebClient
) -> List[Dict]:
    """
    Handle IAM user creation notifications from AWS SNS.

    Args:
        payload: The AwsSnsPayload containing the IAM user information
        client: The Slack WebClient instance

    Returns:
        List of Slack blocks formatted for the IAM user notification
    """
    msg = payload.Message or ""

    # Extract IAM user details using regex
    user_regex = r"IAM User: (\w.+)"
    user_match = re.search(user_regex, msg)
    user_created = user_match.groups()[0] if user_match else "Unknown User"

    actor_regex = r"Actor: arn:aws:sts::(\d.+):assumed-role/\w.+/(\w.+)"
    actor_match = re.search(actor_regex, msg)

    if actor_match:
        account = actor_match.groups()[0]
        user = actor_match.groups()[1]
    else:
        account = "unknown"
        user = "unknown"

    blocks = [
        {"type": "section", "text": {"type": "mrkdwn", "text": " "}},
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "👾 New IAM User created 👾",
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"New IAM User named {user_created} was created in account {account} by user {user}.",
            },
        },
    ]

    return blocks


def is_iam_user_notification(
    payload: AwsSnsPayload, parsed_message: Union[str, dict]
) -> bool:
    """
    Check if the AWS SNS message is an IAM user creation notification.

    Args:
        payload: The AwsSnsPayload to check
        parsed_message: The parsed message content

    Returns:
        True if this is an IAM user notification, False otherwise
    """
    message = payload.Message or ""
    return "IAM User" in message


IAM_USER_HANDLER: AwsNotificationPattern = AwsNotificationPattern(
    name="iam_user_notification",
    match_type="callable",
    match_target="message",
    pattern="modules.webhooks.patterns.aws_sns_notification.iam_user.is_iam_user_notification",
    handler="modules.webhooks.patterns.aws_sns_notification.iam_user.handle_iam_user_notification",
    priority=30,
    enabled=True,
)
