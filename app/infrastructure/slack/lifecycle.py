"""Slack lifecycle helpers used during FastAPI lifespan."""

from typing import Optional

from structlog.stdlib import BoundLogger

from infrastructure.operations import OperationResult
from infrastructure.slack.service import SlackBot


def initialize_slack_bot(slack_bot: SlackBot, logger: BoundLogger) -> OperationResult:
    """Initialize Slack transport and command handlers."""
    result = slack_bot.initialize_app()
    if result.is_success:
        logger.info("slack_bot_initialized")
    else:
        logger.warning(
            "slack_bot_initialization_failed",
            error_code=result.error_code,
            message=result.message,
        )
    return result


def start_slack_bot(slack_bot: SlackBot, logger: BoundLogger) -> OperationResult:
    """Start Slack transport runtime."""
    result = slack_bot.start()
    if result.is_success:
        logger.info("slack_bot_started")
    else:
        logger.warning(
            "slack_bot_start_failed",
            error_code=result.error_code,
            message=result.message,
        )
    return result


def stop_slack_bot(slack_bot: Optional[SlackBot], logger: BoundLogger) -> None:
    """Stop Slack transport runtime if it was started."""
    if slack_bot is None:
        return
    slack_bot.stop()
    logger.info("slack_bot_stopped")
