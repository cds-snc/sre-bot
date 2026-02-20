import re
from typing import Dict, List, Union

from core.config import settings
from core.logging import get_module_logger
from integrations import notify
from models.webhooks import AwsSnsPayload
from modules.webhooks.aws_sns_notification import AwsNotificationPattern
from slack_sdk import WebClient

logger = get_module_logger()
NOTIFY_OPS_CHANNEL_ID = settings.server.NOTIFY_OPS_CHANNEL_ID


def send_message_to_notify_channel(client: WebClient, blocks: List[Dict]):
    """Send message to the notification ops channel."""
    # Raise an exception if the NOTIFY_OPS_CHANNEL_ID is not set
    assert NOTIFY_OPS_CHANNEL_ID, "NOTIFY_OPS_CHANNEL_ID is not set in the environment"

    if not settings.is_production:
        client.chat_postMessage(channel="C033L7RGCT0", blocks=blocks)
    else:
        # post the message to the notification channel
        client.chat_postMessage(channel=NOTIFY_OPS_CHANNEL_ID, blocks=blocks)


def handle_api_key_detected(payload: AwsSnsPayload, client: WebClient) -> List[Dict]:
    """
    Handle API key detection notifications from AWS SNS.

    Args:
        payload: The AwsSnsPayload containing the API key detection information
        client: The Slack WebClient instance

    Returns:
        List of Slack blocks formatted for the API key detection notification
    """
    msg = payload.Message or ""

    # Extract API key details using regex
    regex = r"API Key with value token='(\w.+)', type='(\w.+)' and source='(\w.+)' has been detected in url='(\w.+)'!"
    match = re.search(regex, msg)

    if not match:
        logger.warning("failed_to_parse_api_key_detection_message", message=msg)
        return []

    api_key = match.groups()[0]
    key_type = match.groups()[1]
    source = match.groups()[2]
    github_repo = match.groups()[3]

    # Extract the service id from the API key
    api_regex = r"(?P<prefix>gcntfy-)(?P<keyname>.*)(?P<service_id>[-A-Za-z0-9]{36})-(?P<key_id>[-A-Za-z0-9]{36})"
    pattern = re.compile(api_regex)
    service_match = pattern.search(api_key)

    if service_match:
        service_id = service_match.group("service_id")
        # Extract the API key name (remove prefix and suffix)
        api_key_name = api_key[7 : len(api_key) - 74]
    else:
        service_id = "Unknown"
        api_key_name = "Unknown Key"

    # Attempt to revoke the API key
    revocation_result = notify.revoke_api_key(
        api_key, key_type, github_repo, source
    )

    if revocation_result == "revoked":
        revoke_api_key_message = (
            f"API key {api_key_name} has been successfully revoked."
        )
        header_text = "🙀 Notify API Key has been exposed and revoked! 😌"
    elif revocation_result == "not_found":
        revoke_api_key_message = (
            f"API key {api_key_name} was not found and may have already been revoked."
        )
        header_text = "🙀 Notify API Key has been exposed but was not found! 🤔"
    else:
        revoke_api_key_message = (
            f"API key {api_key_name} could not be revoked due to an error."
        )
        header_text = "🙀 Notify API Key has been exposed but could not be revoked! 😱"

    blocks = [
        {"type": "section", "text": {"type": "mrkdwn", "text": " "}},
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"{header_text}"},
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"Notify API Key Name {api_key_name} from service id {service_id} was committed in github file {github_repo}.\n",
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*{revoke_api_key_message}*",
            },
        },
    ]

    # Send the message to the notify ops channel
    send_message_to_notify_channel(client, blocks)

    return blocks


def is_api_key_detected(
    payload: AwsSnsPayload, parsed_message: Union[str, dict]
) -> bool:
    """
    Check if the AWS SNS message is an API key detection notification.

    Args:
        payload: The AwsSnsPayload to check
        parsed_message: The parsed message content

    Returns:
        True if this is an API key detection notification, False otherwise
    """
    message = payload.Message or ""
    return "API Key with value token=" in message


API_KEY_DETECTED_HANDLER: AwsNotificationPattern = AwsNotificationPattern(
    name="api_key_detected",
    match_type="callable",
    match_target="message",
    pattern="modules.webhooks.patterns.aws_sns_notification.api_key_detected.is_api_key_detected",
    handler="modules.webhooks.patterns.aws_sns_notification.api_key_detected.handle_api_key_detected",
    priority=60,  # High priority for security-related notifications
    enabled=True,
)
