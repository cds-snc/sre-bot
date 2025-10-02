from typing import Dict, List, Union

from core.logging import get_module_logger
from models.webhooks import AwsSnsPayload
from modules.webhooks.aws_sns_notification import AwsNotificationPattern
from slack_sdk import WebClient

logger = get_module_logger()


def handle_budget_auto_adjustment(
    payload: AwsSnsPayload, client: WebClient
) -> List[Dict]:
    """
    Handle AWS budget auto-adjustment notifications from AWS SNS.

    Args:
        payload: The AwsSnsPayload containing the budget auto-adjustment information
        client: The Slack WebClient instance

    Returns:
        Empty list as these events are just logged and not posted to Slack
    """
    logger.info(
        "budget_auto_adjustment_event",
        message=payload.Message,
    )

    # Return empty blocks as these events are not posted to Slack
    return []


def is_budget_auto_adjustment(
    payload: AwsSnsPayload, parsed_message: Union[str, dict]
) -> bool:
    """
    Check if the AWS SNS message is a budget auto-adjustment notification.

    Args:
        payload: The AwsSnsPayload to check
        parsed_message: The parsed message content

    Returns:
        True if this is a budget auto-adjustment notification, False otherwise
    """
    if not isinstance(parsed_message, dict):
        return False

    # Budget auto-adjustment messages have both previousBudgetLimit and currentBudgetLimit fields
    required_keys = {"previousBudgetLimit", "currentBudgetLimit"}
    return required_keys <= set(parsed_message.keys())


BUDGET_AUTO_ADJUSTMENT_HANDLER: AwsNotificationPattern = AwsNotificationPattern(
    name="budget_auto_adjustment",
    match_type="callable",
    match_target="parsed_message",
    pattern="modules.webhooks.patterns.aws_sns_notification.budget_auto_adjustment.is_budget_auto_adjustment",
    handler="modules.webhooks.patterns.aws_sns_notification.budget_auto_adjustment.handle_budget_auto_adjustment",
    priority=25,
    enabled=True,
)
