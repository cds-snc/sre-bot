from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from core.config import settings
from core.logging import get_module_logger

OPS_CHANNEL_ID = settings.sre_ops.SRE_OPS_CHANNEL_ID

logger = get_module_logger()


def log_ops_message(client: WebClient, message: str):
    """Provides a standardized way to log operational messages to a specific Slack channel configured in the settings.
    Failure to log the message will not raise an exception, but will be logged in the application logs to avoid disrupting the main application flow.

    Args:
        client (WebClient): An instance of the Slack WebClient to interact with the Slack API.
        message (str): The message to be logged to the operations channel.

    Returns:
        None
    """
    if not OPS_CHANNEL_ID:
        logger.warning("ops_channel_id_not_configured")
        return
    channel_id = OPS_CHANNEL_ID
    logger.info("ops_message_logged", message=message)
    try:
        client.conversations_join(channel=channel_id)
        client.chat_postMessage(channel=channel_id, text=message, as_user=True)
    except SlackApiError as e:
        logger.error("ops_message_failed", message=message, error=str(e))
