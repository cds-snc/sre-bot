"""Slack SDK client wrapper."""

from typing import Any, Dict, List, Optional

import structlog
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from infrastructure.operations import OperationResult

logger = structlog.get_logger()


class SlackClient:
    """Wraps Slack SDK WebClient with OperationResult-based APIs."""

    def __init__(self, token: str):
        """Initialize with bot token.

        Args:
            token: Slack bot token (starts with xoxb-)
        """
        self._client = WebClient(token=token)
        self._log = logger.bind(component="slack_client")

    def post_message(
        self,
        channel: str,
        text: Optional[str] = None,
        blocks: Optional[List[Dict[str, Any]]] = None,
        thread_ts: Optional[str] = None,
        **kwargs,
    ) -> OperationResult:
        """Post a message to a Slack channel.

        Args:
            channel: Channel ID to post to
            text: Plain text message
            blocks: Block Kit blocks for rich formatting
            thread_ts: Optional parent message timestamp for threading
            **kwargs: Additional arguments for chat.postMessage

        Returns:
            OperationResult with message data including 'ts' (timestamp)
        """
        log = self._log.bind(channel=channel, has_blocks=blocks is not None)

        try:
            response = self._client.chat_postMessage(
                channel=channel, text=text, blocks=blocks, thread_ts=thread_ts, **kwargs
            )

            if not response.get("ok"):
                error = response.get("error", "unknown_error")
                log.warning("slack_message_failed", error=error)
                return OperationResult.permanent_error(
                    message=f"Slack API error: {error}",
                    error_code=f"SLACK_{error.upper()}",
                )

            log.info("slack_message_posted", ts=response.get("ts"))
            return OperationResult.success(
                data=response.data, message="Message posted successfully"
            )

        except SlackApiError as e:
            log.exception("slack_api_error", error=str(e))

            if e.response.status_code in [429, 500, 502, 503, 504]:
                retry_after = int(e.response.headers.get("Retry-After", 60))
                return OperationResult.transient_error(
                    message=f"Slack API transient error: {e.response['error']}",
                    error_code=f"SLACK_{e.response['error'].upper()}",
                    retry_after=retry_after,
                )

            return OperationResult.permanent_error(
                message=f"Slack API error: {e.response['error']}",
                error_code=f"SLACK_{e.response['error'].upper()}",
            )

        except Exception as e:
            log.exception("slack_client_error", error=str(e))
            return OperationResult.permanent_error(
                message=f"Unexpected error posting message: {str(e)}",
                error_code="SLACK_CLIENT_ERROR",
            )

    def update_message(
        self,
        channel: str,
        ts: str,
        text: Optional[str] = None,
        blocks: Optional[List[Dict[str, Any]]] = None,
        **kwargs,
    ) -> OperationResult:
        """Update an existing Slack message."""
        log = self._log.bind(channel=channel, ts=ts)

        try:
            response = self._client.chat_update(
                channel=channel, ts=ts, text=text, blocks=blocks, **kwargs
            )

            if not response.get("ok"):
                error = response.get("error", "unknown_error")
                log.warning("slack_update_failed", error=error)
                return OperationResult.permanent_error(
                    message=f"Slack API error: {error}",
                    error_code=f"SLACK_{error.upper()}",
                )

            log.info("slack_message_updated")
            return OperationResult.success(
                data=response.data, message="Message updated successfully"
            )

        except SlackApiError as e:
            log.exception("slack_api_error", error=str(e))

            if e.response.status_code in [429, 500, 502, 503, 504]:
                retry_after = int(e.response.headers.get("Retry-After", 60))
                return OperationResult.transient_error(
                    message=f"Slack API transient error: {e.response['error']}",
                    error_code=f"SLACK_{e.response['error'].upper()}",
                    retry_after=retry_after,
                )

            return OperationResult.permanent_error(
                message=f"Slack API error: {e.response['error']}",
                error_code=f"SLACK_{e.response['error'].upper()}",
            )

        except Exception as e:
            log.exception("slack_client_error", error=str(e))
            return OperationResult.permanent_error(
                message=f"Unexpected error updating message: {str(e)}",
                error_code="SLACK_CLIENT_ERROR",
            )

    def get_user_info(self, user_id: str) -> OperationResult:
        """Get information about a Slack user."""
        log = self._log.bind(user_id=user_id)

        try:
            response = self._client.users_info(user=user_id)

            if not response.get("ok"):
                error = response.get("error", "unknown_error")
                log.warning("slack_user_info_failed", error=error)
                return OperationResult.permanent_error(
                    message=f"Slack API error: {error}",
                    error_code=f"SLACK_{error.upper()}",
                )

            log.info("slack_user_info_retrieved")
            return OperationResult.success(
                data=response.get("user"), message="User info retrieved successfully"
            )

        except SlackApiError as e:
            log.exception("slack_api_error", error=str(e))

            if e.response.status_code in [429, 500, 502, 503, 504]:
                retry_after = int(e.response.headers.get("Retry-After", 60))
                return OperationResult.transient_error(
                    message=f"Slack API transient error: {e.response['error']}",
                    error_code=f"SLACK_{e.response['error'].upper()}",
                    retry_after=retry_after,
                )

            return OperationResult.permanent_error(
                message=f"Slack API error: {e.response['error']}",
                error_code=f"SLACK_{e.response['error'].upper()}",
            )

        except Exception as e:
            log.exception("slack_client_error", error=str(e))
            return OperationResult.permanent_error(
                message=f"Unexpected error getting user info: {str(e)}",
                error_code="SLACK_CLIENT_ERROR",
            )

    @property
    def raw_client(self) -> WebClient:
        """Access underlying Slack WebClient for advanced use cases."""
        return self._client


__all__ = ["SlackClient"]
