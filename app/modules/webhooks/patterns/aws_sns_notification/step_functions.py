import json
import re
from datetime import datetime
from typing import Dict, List, Union

from core.logging import get_module_logger
from models.webhooks import AwsSnsPayload
from modules.webhooks.aws_sns_notification import AwsNotificationPattern
from slack_sdk import WebClient

logger = get_module_logger()


def format_timestamp(timestamp_ms: Union[str, int]) -> str:
    """
    Format a Unix timestamp in milliseconds to a human-readable datetime string.

    Args:
        timestamp_ms: Unix timestamp in milliseconds

    Returns:
        Formatted datetime string
    """
    try:
        timestamp_sec = int(timestamp_ms) / 1000
        dt = datetime.fromtimestamp(timestamp_sec)
        return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    except (ValueError, TypeError):
        return str(timestamp_ms)


def extract_account_name(input_data: str) -> str:
    """
    Extract AWS account name from the Step Functions input data.

    Args:
        input_data: JSON string containing the input data

    Returns:
        Account name if found, otherwise "Unknown"
    """
    try:
        input_json = json.loads(input_data)
        # Try different paths where account name might be
        account_name = (
            input_json.get("control_tower_event", {})
            .get("account_request", {})
            .get("control_tower_parameters", {})
            .get("AccountName")
        )
        if not account_name:
            account_name = (
                input_json.get("account_request", {})
                .get("control_tower_parameters", {})
                .get("AccountName")
            )
        if not account_name:
            account_name = (
                input_json.get("account_info", {}).get("account", {}).get("name")
            )

        return account_name or "Unknown"
    except (json.JSONDecodeError, TypeError, AttributeError):
        return "Unknown"


def extract_change_info(input_data: str) -> tuple[str, str]:
    """
    Extract change reason and requester from the Step Functions input data.

    Args:
        input_data: JSON string containing the input data

    Returns:
        Tuple of (change_reason, change_requested_by)
    """
    try:
        input_json = json.loads(input_data)
        # Try different paths where change info might be
        change_params = (
            input_json.get("control_tower_event", {})
            .get("account_request", {})
            .get("change_management_parameters", {})
        )
        if not change_params:
            change_params = input_json.get("account_request", {}).get(
                "change_management_parameters", {}
            )

        reason = change_params.get("change_reason", "Not specified")
        requester = change_params.get("change_requested_by", "Unknown")

        return reason, requester
    except (json.JSONDecodeError, TypeError, AttributeError):
        return "Not specified", "Unknown"


def handle_step_functions_notification(
    payload: AwsSnsPayload, client: WebClient
) -> List[Dict]:
    """
    Handle AWS Step Functions state machine execution notifications from AWS SNS.

    Args:
        payload: The AwsSnsPayload containing the Step Functions execution information
        client: The Slack WebClient instance

    Returns:
        List of Slack blocks formatted for the Step Functions notification
    """
    try:
        message = payload.Message
        if message is None:
            return []

        msg = json.loads(message)
    except (json.JSONDecodeError, TypeError):
        logger.warning(
            "failed_to_parse_step_functions_message", message=payload.Message
        )
        return []

    # Extract execution details
    execution_arn = msg.get("ExecutionArn", "")
    state_machine_arn = msg.get("StateMachineArn", "")
    status = msg.get("Status", "UNKNOWN")
    execution_name = msg.get("Name", "Unknown")
    start_date = msg.get("StartDate", "")
    stop_date = msg.get("StopDate", "")
    input_data = msg.get("Input", "")

    # Extract region and account from ARN
    region_regex = r"arn:aws:states:([^:]+):(\d+):stateMachine:(.+)"
    arn_match = re.search(region_regex, state_machine_arn)

    if arn_match:
        region = arn_match.group(1)
        account_id = arn_match.group(2)
        state_machine_name = arn_match.group(3)
    else:
        region = "unknown"
        account_id = "unknown"
        state_machine_name = state_machine_arn

    # Determine emoji and header based on status
    if status == "SUCCEEDED":
        emoji = "✅"
        header_text = "Step Functions Execution Succeeded"
    elif status == "FAILED":
        emoji = "❌"
        header_text = "Step Functions Execution Failed"
    elif status == "TIMED_OUT":
        emoji = "⏱️"
        header_text = "Step Functions Execution Timed Out"
    elif status == "ABORTED":
        emoji = "🛑"
        header_text = "Step Functions Execution Aborted"
    else:
        emoji = "ℹ️"
        header_text = f"Step Functions Execution: {status}"

    # Extract AFT-specific details if available
    account_name = extract_account_name(input_data)
    change_reason, change_requester = extract_change_info(input_data)

    # Format timestamps
    start_time = format_timestamp(start_date) if start_date else "N/A"
    stop_time = format_timestamp(stop_date) if stop_date else "N/A"

    # Create console link
    execution_link = f"https://console.aws.amazon.com/states/home?region={region}#/executions/details/{execution_arn}"

    blocks = [
        {"type": "section", "text": {"type": "mrkdwn", "text": " "}},
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*<{execution_link}|{emoji} {header_text} | {region} | {account_id}>*",
            },
        },
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"{state_machine_name}",
            },
        },
    ]

    # Add AFT-specific details if this is an AFT provisioning workflow
    if "aft-account-provisioning" in state_machine_name.lower():
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Account:* {account_name}\n*Change Reason:* {change_reason}\n*Requested By:* {change_requester}",
                },
            }
        )

    # Add execution details
    blocks.extend(
        [
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Status:*\n{status}"},
                    {"type": "mrkdwn", "text": f"*Execution:*\n{execution_name[:50]}"},
                ],
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Started:*\n{start_time}"},
                    {"type": "mrkdwn", "text": f"*Stopped:*\n{stop_time}"},
                ],
            },
        ]
    )

    # Add output/error information if failed
    if status == "FAILED":
        error = msg.get("Error", "Unknown error")
        cause = msg.get("Cause", "No cause provided")
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Error:* {error}\n*Cause:* {cause}",
                },
            }
        )

    blocks.extend(
        [
            {"type": "divider"},
            {"type": "section", "text": {"type": "mrkdwn", "text": execution_link}},
        ]
    )

    return blocks


def is_step_functions_notification(
    payload: AwsSnsPayload, parsed_message: Union[str, dict]
) -> bool:
    """
    Check if the AWS SNS message is a Step Functions execution notification.

    Args:
        payload: The AwsSnsPayload to check
        parsed_message: The parsed message content

    Returns:
        True if this is a Step Functions notification, False otherwise
    """
    if not isinstance(parsed_message, dict):
        return False

    # Step Functions notifications have ExecutionArn and StateMachineArn fields
    required_keys = {"ExecutionArn", "StateMachineArn", "Status"}
    has_required_keys = required_keys <= set(parsed_message.keys())

    if not has_required_keys:
        return False

    # Verify the ARN format to be extra sure
    state_machine_arn = parsed_message.get("StateMachineArn", "")
    return "arn:aws:states:" in state_machine_arn


STEP_FUNCTIONS_HANDLER: AwsNotificationPattern = AwsNotificationPattern(
    name="step_functions_notification",
    match_type="callable",
    match_target="parsed_message",
    pattern="modules.webhooks.patterns.aws_sns_notification.step_functions.is_step_functions_notification",
    handler="modules.webhooks.patterns.aws_sns_notification.step_functions.handle_step_functions_notification",
    priority=55,  # High priority - specific structural match
    enabled=True,
)
