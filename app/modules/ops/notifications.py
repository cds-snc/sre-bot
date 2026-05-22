from slack_sdk.errors import SlackApiError
from structlog import get_logger

from core.config import settings
from integrations.slack.client import SlackClientManager

OPS_CHANNEL_ID = settings.sre_ops.SRE_OPS_CHANNEL_ID

logger = get_logger()


def log_ops_message(message: str):
    """
    Log an operational message to the configured Slack channel and application logs.
    Follows the canonical logging schema and conventions per the logging ADR.

    Args:
        message (str): The message to be logged to the operations channel.
    """
    log = logger.bind(ops_message=message)
    client = SlackClientManager.get_client()
    if not client:
        log.error(
            "slack_client_not_initialized",
        )
        return
    if not OPS_CHANNEL_ID:
        log.warning(
            "ops_channel_id_not_configured",
        )
        return
    channel_id = OPS_CHANNEL_ID
    log.info(
        "ops_message_log_attempted",
        channel_id=channel_id,
    )
    try:
        client.conversations_join(channel=channel_id)
        client.chat_postMessage(channel=channel_id, text=message, as_user=True)
        log.info(
            "ops_message_logged",
            channel_id=channel_id,
        )
    except SlackApiError as e:
        log.error(
            "ops_message_failed",
            channel_id=channel_id,
            error=str(e),
        )
