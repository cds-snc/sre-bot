import json
import re
import urllib.parse
from typing import Dict, List, Union

from core.logging import get_module_logger
from models.webhooks import AwsSnsPayload
from modules.webhooks.aws_sns_notification import AwsNotificationPattern
from slack_sdk import WebClient

logger = get_module_logger()


def handle_cloudwatch_alarm(payload: AwsSnsPayload, client: WebClient) -> List[Dict]:
    """
    Handle CloudWatch alarm notifications from AWS SNS.

    Args:
        payload: The AwsSnsPayload containing the alarm information
        client: The Slack WebClient instance

    Returns:
        List of Slack blocks formatted for the alarm notification
    """
    try:
        message = payload.Message
        if message is None:
            return []

        msg = json.loads(message)
    except (json.JSONDecodeError, TypeError):
        logger.warning(
            "failed_to_parse_cloudwatch_alarm_message", message=payload.Message
        )
        return []

    # Extract alarm details
    alarm_arn = msg.get("AlarmArn", "")
    regex = r"arn:aws:cloudwatch:(\w.*):\d.*:alarm:\w.*"
    region_match = re.search(regex, alarm_arn)
    region = region_match.groups()[0] if region_match else "unknown"

    new_state = msg.get("NewStateValue", "UNKNOWN")
    if new_state == "ALARM":
        emoji = "🔥"
    elif new_state == "OK":
        emoji = "✅"
    else:
        emoji = "🤷‍♀️"

    alarm_name = msg.get("AlarmName", "Unknown Alarm")
    alarm_description = msg.get("AlarmDescription") or " "
    new_state_reason = msg.get("NewStateReason", "")
    old_state = msg.get("OldStateValue", "UNKNOWN")
    account_id = msg.get("AWSAccountId", "unknown")

    # Create the CloudWatch console link
    link = f"https://console.aws.amazon.com/cloudwatch/home?region={region}#alarm:alarmFilter=ANY;name={urllib.parse.quote(alarm_name)}"

    blocks = [
        {"type": "section", "text": {"type": "mrkdwn", "text": " "}},
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*<{link}|{emoji} CloudWatch Alert | {region} | {account_id}>*",
            },
        },
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"{alarm_name}"},
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"{alarm_description}"},
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"{new_state_reason}"},
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*New State:*\n {new_state}"},
                {"type": "mrkdwn", "text": f"*Old State:*\n {old_state}"},
            ],
        },
        {"type": "divider"},
        {"type": "section", "text": {"type": "mrkdwn", "text": link}},
    ]

    return blocks


def is_cloudwatch_alarm_message(
    payload: AwsSnsPayload, parsed_message: Union[str, dict]
) -> bool:
    """
    Check if the AWS SNS message is a CloudWatch alarm notification.

    Args:
        payload: The AwsSnsPayload to check
        parsed_message: The parsed message content

    Returns:
        True if this is a CloudWatch alarm message, False otherwise
    """
    if not isinstance(parsed_message, dict):
        return False

    # CloudWatch alarms always have an AlarmArn field
    return "AlarmArn" in parsed_message


CLOUDWATCH_ALARM_HANDLER: AwsNotificationPattern = AwsNotificationPattern(
    name="cloudwatch_alarm",
    match_type="callable",
    match_target="parsed_message",
    pattern="modules.webhooks.patterns.aws_sns_notification.cloudwatch_alarm.is_cloudwatch_alarm_message",
    handler="modules.webhooks.patterns.aws_sns_notification.cloudwatch_alarm.handle_cloudwatch_alarm",
    priority=50,  # High priority since it's a specific structural match
    enabled=True,
)
