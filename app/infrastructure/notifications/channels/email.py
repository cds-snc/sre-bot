"""Email channel implementation using Google Workspace Gmail."""

from typing import List

import structlog
from infrastructure.notifications.channels.base import NotificationChannel
from infrastructure.notifications.models import (
    Notification,
    NotificationResult,
    NotificationStatus,
    Recipient,
)
from infrastructure.operations import OperationResult
from infrastructure.resilience.circuit_breaker import CircuitBreaker
from infrastructure.services.providers import get_settings
from integrations.google_workspace import gmail_next

logger = structlog.get_logger()
settings = get_settings()


class EmailChannel(NotificationChannel):
    """Email notification channel using Gmail API.

    Sends emails via Google Workspace Gmail API.
    Supports sending from configured service account or user delegation.
    """

    def __init__(self):
        """Initialize Gmail email channel."""
        self._circuit_breaker = CircuitBreaker(
            name="gmail_email_channel",
            failure_threshold=5,
            timeout_seconds=60,
        )
        self._sender_email = settings.google_workspace.GOOGLE_DELEGATED_ADMIN_EMAIL
        logger.info(
            "initialized_email_channel",
            backend="gmail",
            sender=self._sender_email,
        )

    @property
    def channel_name(self) -> str:
        """Channel identifier."""
        return "email"

    def send(self, notification: Notification) -> List[NotificationResult]:
        """Send email notification to all recipients.

        Args:
            notification: Notification to send.

        Returns:
            List of NotificationResult, one per recipient.
        """
        results = []

        for recipient in notification.recipients:
            # Resolve recipient (email validation)
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

            recipient_email = resolve_result.data.get("email")

            # Send email via circuit breaker
            send_result = self._circuit_breaker.call(
                self._send_gmail,
                subject=notification.subject or "Notification",
                message=notification.message,
                recipient=recipient_email,
                sender=self._sender_email,
            )

            if send_result.is_success:
                results.append(
                    NotificationResult(
                        notification=notification,
                        channel=self.channel_name,
                        status=NotificationStatus.SENT,
                        message=f"Sent email to {recipient_email}",
                        external_id=send_result.data.get("message_id"),
                    )
                )
                logger.info(
                    "gmail_sent",
                    recipient=recipient_email,
                    subject=notification.subject,
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
                    "gmail_failed",
                    recipient=recipient_email,
                    error=send_result.message,
                )

        return results

    def resolve_recipient(self, recipient: Recipient) -> OperationResult:
        """Validate recipient email address.

        Email is already validated by Pydantic EmailStr in Recipient model.
        This method primarily ensures email field is present.

        Args:
            recipient: Recipient to resolve.

        Returns:
            OperationResult with email in data field.
        """
        if not recipient.email:
            return OperationResult.permanent_error(
                message="Email address required",
                error_code="MISSING_EMAIL",
            )

        # Email format already validated by Pydantic EmailStr (RFC 5322)
        return OperationResult.success(
            message="Email validated",
            data={"email": recipient.email},
        )

    def health_check(self) -> OperationResult:
        """Check Gmail API connectivity.

        Returns:
            OperationResult indicating channel health.
        """
        # Use gmail_next to list labels as a health check
        result = gmail_next.list_messages(
            max_results=1,
            delegated_user_email=self._sender_email,
        )

        # gmail_next already returns OperationResult with proper error handling
        if result.is_success:
            return OperationResult.success(
                message="Gmail API healthy",
                data={"sender": self._sender_email},
            )

        # Propagate the error from gmail_next
        return result

    def _send_gmail(
        self, subject: str, message: str, recipient: str, sender: str
    ) -> OperationResult:
        """Send email via Gmail API.

        Args:
            subject: Email subject.
            message: Email body.
            recipient: Recipient email address.
            sender: Sender email address.

        Returns:
            OperationResult with message ID in data field.
        """
        # Use gmail_next module which already returns OperationResult
        result = gmail_next.send_email(
            subject=subject,
            body=message,
            sender=sender,
            recipient=recipient,
            delegated_user_email=sender,
        )

        # If successful, extract message ID for external_id tracking
        if result.is_success and result.data and "id" in result.data:
            return OperationResult.success(
                message="Email sent via Gmail",
                data={"message_id": result.data["id"]},
            )

        # Propagate the error from gmail_next
        return result
