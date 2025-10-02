import re
from typing import Dict, List, Union

from core.logging import get_module_logger
from models.webhooks import AwsSnsPayload
from modules.webhooks.aws_sns_notification import AwsNotificationPattern
from slack_sdk import WebClient

logger = get_module_logger()


def handle_auto_mitigation(payload: AwsSnsPayload, client: WebClient) -> List[Dict]:
    """
    Handle auto-mitigation notifications from AWS SNS.

    Args:
        payload: The AwsSnsPayload containing the auto-mitigation information
        client: The Slack WebClient instance

    Returns:
        List of Slack blocks formatted for the auto-mitigation notification
    """
    msg = payload.Message or ""

    # Extract details using regex
    regex = r"security group: (\w.+) that was added by arn:aws:sts::(\d.+):assumed-role/\w.+/(\w.+): \[{\"IpProtocol\": \"tcp\", \"FromPort\": (\d.+), \"ToPort\":"
    match = re.search(regex, msg)

    if not match:
        logger.warning("failed_to_parse_auto_mitigation_message", message=msg)
        return []

    security_group = match.groups()[0]
    account = match.groups()[1]
    user = match.groups()[2]
    port = match.groups()[3]

    blocks = [
        {"type": "section", "text": {"type": "mrkdwn", "text": " "}},
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"🛠 Auto-mitigated: Port {port} opened in account {account} by {user} 🔩",
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"Inbound rule change on port {port} created by user {user} for Security group {security_group} on account {account} has been reversed.",
            },
        },
    ]

    return blocks


def is_auto_mitigation(
    payload: AwsSnsPayload, parsed_message: Union[str, dict]
) -> bool:
    """
    Check if the AWS SNS message is an auto-mitigation notification.

    Args:
        payload: The AwsSnsPayload to check
        parsed_message: The parsed message content

    Returns:
        True if this is an auto-mitigation notification, False otherwise
    """
    message = payload.Message or ""
    return "AUTO-MITIGATED" in message


AUTO_MITIGATION_HANDLER: AwsNotificationPattern = AwsNotificationPattern(
    name="auto_mitigation",
    match_type="callable",
    match_target="message",
    pattern="modules.webhooks.patterns.aws_sns_notification.auto_mitigation.is_auto_mitigation",
    handler="modules.webhooks.patterns.aws_sns_notification.auto_mitigation.handle_auto_mitigation",
    priority=35,
    enabled=True,
)
