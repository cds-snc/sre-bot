"""Chat channel implementation using Slack."""

from typing import List, Optional, TYPE_CHECKING
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

import structlog
from infrastructure.notifications.channels.base import NotificationChannel
from infrastructure.notifications.models import (
    Notification,
    NotificationResult,
    NotificationStatus,
    Recipient,
)
from infrastructure.operations import OperationResult
from integrations.slack.client import SlackClientManager

if TYPE_CHECKING:
    from infrastructure.resilience.circuit_breaker import CircuitBreaker

logger = structlog.get_logger()


class ChatChannel(NotificationChannel):
    """Slack chat notification channel.

    Sends direct messages via Slack using the Web API.
    Supports recipient resolution by email or Slack user ID.
    """

    def __init__(self, circuit_breaker: Optional["CircuitBreaker"] = None):
        """Initialize Slack chat channel.

        Args:
            circuit_breaker: Optional circuit breaker for fault tolerance.
                           If not provided, creates a default one.
        """
        self._client_manager = SlackClientManager()

        if circuit_breaker is None:
            # Import only if needed (for backward compatibility)
            from infrastructure.resilience.circuit_breaker import CircuitBreaker

            circuit_breaker = CircuitBreaker(
                name="slack_chat_channel",
                failure_threshold=5,
                timeout_seconds=60,
            )

        self._circuit_breaker = circuit_breaker
        logger.info("initialized_chat_channel", backend="slack")

    @property
    def channel_name(self) -> str:
        """Channel identifier."""
        return "chat"

    def send(self, notification: Notification) -> List[NotificationResult]:
        """Send chat notification to all recipients.

        Args:
            notification: Notification to send.

        Returns:
            List of NotificationResult, one per recipient.
        """
        results = []
        client = self._client_manager.get_client()

        for recipient in notification.recipients:
            # Resolve recipient to Slack user ID
            resolve_result = self.resolve_recipient(recipient)
            if not resolve_result.is_success:
                results.append(
                    NotificationResult(
                        notification=notification,
                        channel=self.channel_name,
                        status=NotificationStatus.FAILED,
                        message=f"Failed to resolve recipient: {resolve_result.message}",
                        error_code="RECIPIENT_RESOLUTION_FAILED",
                    )
                )
                continue

            slack_user_id = resolve_result.data.get("slack_user_id")

            # Send DM via circuit breaker
            send_result = self._circuit_breaker.call(
                self._send_slack_dm,
                client=client,
                user_id=slack_user_id,
                message=notification.message,
                subject=notification.subject,
            )

            if send_result.is_success:
                results.append(
                    NotificationResult(
                        notification=notification,
                        channel=self.channel_name,
                        status=NotificationStatus.SENT,
                        message=f"Sent Slack DM to {recipient.email}",
                        external_id=send_result.data.get("ts"),
                    )
                )
                logger.info(
                    "slack_dm_sent",
                    recipient=recipient.email,
                    slack_user_id=slack_user_id,
                    priority=notification.priority.value,
                )
            else:
                results.append(
                    NotificationResult(
                        notification=notification,
                        channel=self.channel_name,
                        status=NotificationStatus.FAILED,
                        message=send_result.message,
                        error_code=send_result.error_code,
                    )
                )
                logger.error(
                    "slack_dm_failed",
                    recipient=recipient.email,
                    error=send_result.message,
                )

        return results

    def resolve_recipient(self, recipient: Recipient) -> OperationResult:
        """Resolve recipient to Slack user ID.

        Args:
            recipient: Recipient to resolve.

        Returns:
            OperationResult with slack_user_id in data field.
        """
        try:
            client = self._client_manager.get_client()

            # If Slack user ID already provided, validate and return
            if recipient.slack_user_id:
                try:
                    user_info = client.users_info(user=recipient.slack_user_id)
                    if user_info["ok"]:
                        return OperationResult.success(
                            message="Slack user ID validated",
                            data={"slack_user_id": recipient.slack_user_id},
                        )
                except SlackApiError as e:
                    logger.warning(
                        "slack_user_id_validation_failed",
                        user_id=recipient.slack_user_id,
                        error=str(e),
                    )

            # Look up user by email
            if recipient.email:
                try:
                    lookup = client.users_lookupByEmail(email=recipient.email)
                    if lookup["ok"] and lookup.get("user"):
                        slack_user_id = lookup["user"]["id"]
                        return OperationResult.success(
                            message=f"Resolved {recipient.email} to Slack user",
                            data={"slack_user_id": slack_user_id},
                        )
                except SlackApiError as e:
                    return OperationResult.permanent_error(
                        message=f"Slack user lookup failed: {e.response['error']}",
                        error_code=e.response["error"],
                    )

            return OperationResult.permanent_error(
                message="No email or Slack user ID provided",
                error_code="MISSING_IDENTIFIER",
            )

        except Exception as e:
            logger.error(
                "recipient_resolution_error",
                recipient=recipient.email,
                error=str(e),
                exc_info=True,
            )
            return OperationResult.transient_error(
                message=f"Resolution error: {str(e)}",
                error_code="RESOLUTION_ERROR",
            )

    def health_check(self) -> OperationResult:
        """Check Slack API connectivity.

        Returns:
            OperationResult indicating channel health.
        """
        try:
            client = self._client_manager.get_client()
            auth_test = client.auth_test()

            if auth_test["ok"]:
                return OperationResult.success(
                    message="Slack API healthy",
                    data={
                        "team": auth_test.get("team"),
                        "user": auth_test.get("user"),
                    },
                )
            else:
                return OperationResult.permanent_error(
                    message="Slack auth test failed",
                    error_code=auth_test.get("error") or "AUTH_FAILED",
                )

        except Exception as e:
            logger.error("slack_health_check_failed", error=str(e), exc_info=True)
            return OperationResult.transient_error(
                message=f"Health check failed: {str(e)}",
                error_code="HEALTH_CHECK_ERROR",
            )

    def _send_slack_dm(
        self, client: WebClient, user_id: str, message: str, subject: str
    ) -> OperationResult:
        """Send Slack DM to user.

        Args:
            client: Slack WebClient instance.
            user_id: Slack user ID.
            message: Message body.
            subject: Subject line (prepended to message).

        Returns:
            OperationResult with message timestamp in data field.
        """
        try:
            # Open DM conversation
            conversation = client.conversations_open(users=[user_id])
            if not conversation["ok"]:
                return OperationResult.transient_error(
                    message=f"Failed to open conversation: {conversation.get('error')}",
                    error_code=conversation.get("error"),
                )

            channel_id = conversation["channel"]["id"]

            # Format message with subject
            full_message = f"*{subject}*\n\n{message}"

            # Send message
            response = client.chat_postMessage(
                channel=channel_id,
                text=full_message,
            )

            if response["ok"]:
                return OperationResult.success(
                    message="Slack DM sent",
                    data={"ts": response["ts"], "channel": channel_id},
                )
            else:
                return OperationResult.transient_error(
                    message=f"Failed to send message: {response.get('error')}",
                    error_code=response.get("error"),
                )

        except SlackApiError as e:
            logger.error(
                "slack_dm_send_error",
                user_id=user_id,
                error=e.response["error"],
                exc_info=True,
            )
            return OperationResult.transient_error(
                message=f"Slack API error: {e.response['error']}",
                error_code=e.response["error"],
            )
        except Exception as e:
            logger.error(
                "slack_dm_send_unexpected_error",
                user_id=user_id,
                error=str(e),
                exc_info=True,
            )
            return OperationResult.transient_error(
                message=f"Unexpected error: {str(e)}",
                error_code="UNEXPECTED_ERROR",
            )
