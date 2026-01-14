"""Slack client facade.

Wraps the Slack SDK (slack_sdk.WebClient) with OperationResult-based APIs
for consistent error handling across the platform.
"""

import structlog
from typing import Any, Dict, List, Optional
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from infrastructure.operations import OperationResult

logger = structlog.get_logger()


class SlackClientFacade:
    """Facade for Slack SDK client with standardized OperationResult returns.

    Wraps slack_sdk.WebClient methods to provide consistent error handling
    and response formatting across the platform infrastructure.

    Args:
        token: Slack bot token for API authentication

    Example:
        >>> from infrastructure.platforms.clients import SlackClientFacade
        >>> client = SlackClientFacade(token="xoxb-...")
        >>> result = client.post_message(channel="C123", text="Hello")
        >>> if result.is_success:
        ...     print(f"Message sent: {result.data['ts']}")
    """

    def __init__(self, token: str):
        """Initialize Slack client with bot token.

        Args:
            token: Slack bot token (starts with xoxb-)
        """
        self._client = WebClient(token=token)
        self._log = logger.bind(component="slack_client_facade")

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
            channel: Channel ID to post to (e.g., "C1234567890")
            text: Plain text message (required if blocks not provided)
            blocks: List of Block Kit blocks for rich formatting
            thread_ts: Optional parent message timestamp for threading
            **kwargs: Additional arguments passed to chat.postMessage

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

            # Check if error is retryable
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
        """Update an existing Slack message.

        Args:
            channel: Channel ID where message exists
            ts: Timestamp of message to update
            text: New plain text content
            blocks: New Block Kit blocks
            **kwargs: Additional arguments passed to chat.update

        Returns:
            OperationResult with updated message data
        """
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

    def list_conversations(
        self,
        types: str = "public_channel",
        exclude_archived: bool = True,
        limit: int = 100,
    ) -> OperationResult:
        """List Slack conversations (channels, DMs, etc.).

        Args:
            types: Comma-separated list of conversation types
                   (public_channel, private_channel, mpim, im)
            exclude_archived: Whether to exclude archived channels
            limit: Maximum number of results per page (1-1000)

        Returns:
            OperationResult with list of channels and response_metadata
        """
        log = self._log.bind(types=types, exclude_archived=exclude_archived)

        try:
            response = self._client.conversations_list(
                types=types, exclude_archived=exclude_archived, limit=limit
            )

            if not response.get("ok"):
                error = response.get("error", "unknown_error")
                log.warning("slack_conversations_list_failed", error=error)
                return OperationResult.permanent_error(
                    message=f"Slack API error: {error}",
                    error_code=f"SLACK_{error.upper()}",
                )

            channels: list[Any] = response.get("channels", [])
            log.info("slack_conversations_listed", count=len(channels))
            return OperationResult.success(
                data={
                    "channels": channels,
                    "response_metadata": response.get("response_metadata", {}),
                },
                message=f"Retrieved {len(channels)} channels",
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
                message=f"Unexpected error listing conversations: {str(e)}",
                error_code="SLACK_CLIENT_ERROR",
            )

    def get_user_info(self, user_id: str) -> OperationResult:
        """Get information about a Slack user.

        Args:
            user_id: Slack user ID (e.g., "U1234567890")

        Returns:
            OperationResult with user information
        """
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

    def open_view(self, trigger_id: str, view: Dict[str, Any]) -> OperationResult:
        """Open a modal view in Slack.

        Args:
            trigger_id: Trigger ID from interaction payload
            view: View definition (Block Kit modal)

        Returns:
            OperationResult with view data including view.id
        """
        log = self._log.bind(trigger_id=trigger_id[:10])

        try:
            response = self._client.views_open(trigger_id=trigger_id, view=view)

            if not response.get("ok"):
                error = response.get("error", "unknown_error")
                log.warning("slack_view_open_failed", error=error)
                return OperationResult.permanent_error(
                    message=f"Slack API error: {error}",
                    error_code=f"SLACK_{error.upper()}",
                )

            view_data: Dict[str, Any] = response.get("view", {})
            view_id = view_data.get("id") if isinstance(view_data, dict) else None
            log.info("slack_view_opened", view_id=view_id)
            return OperationResult.success(
                data=response.data, message="View opened successfully"
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
                message=f"Unexpected error opening view: {str(e)}",
                error_code="SLACK_CLIENT_ERROR",
            )

    @property
    def raw_client(self) -> WebClient:
        """Access underlying Slack WebClient for advanced use cases.

        Returns:
            slack_sdk.WebClient instance

        Warning:
            Direct client access bypasses OperationResult wrapping.
            Use only when facade methods are insufficient.
        """
        return self._client
