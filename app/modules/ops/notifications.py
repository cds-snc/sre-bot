from slack_sdk.errors import SlackApiError
from core.config import settings
from core.logging import get_module_logger
from integrations.slack.client import SlackClientManager

OPS_CHANNEL_ID = settings.sre_ops.SRE_OPS_CHANNEL_ID

logger = get_module_logger()


def log_ops_message(message: str):
    """Provides a standardized way to log operational messages to a specific Slack channel configured in the settings.
    Failure to log the message will not raise an exception, but will be logged in the application logs to avoid disrupting the main application flow.

    Args:
        message (str): The message to be logged to the operations channel.

    Returns:
        None
    """
    client = SlackClientManager.get_client()
    if not client:
        logger.error("slack_client_not_initialized")
        return
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
