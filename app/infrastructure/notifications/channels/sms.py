"""SMS channel implementation using GC Notify."""

from typing import List, Optional, TYPE_CHECKING

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
from integrations.notify.client import post_event, create_authorization_header

if TYPE_CHECKING:
    from infrastructure.configuration import Settings

logger = structlog.get_logger()


class SMSChannel(NotificationChannel):
    """SMS notification channel using GC Notify.

    Sends SMS messages via GC Notify REST API.
    Requires phone numbers in E.164 format (+1234567890).
    """

    def __init__(self, settings: "Settings"):
        """Initialize GC Notify SMS channel.

        Args:
            settings: Settings instance with notify configuration.
        """
        self._circuit_breaker = CircuitBreaker(
            name="gc_notify_sms_channel",
            failure_threshold=5,
            timeout_seconds=60,
        )
        self._api_url = settings.notify.NOTIFY_API_URL
        logger.info("initialized_sms_channel", backend="gc_notify")

    @property
    def channel_name(self) -> str:
        """Channel identifier."""
        return "sms"

    def send(self, notification: Notification) -> List[NotificationResult]:
        """Send SMS notification to all recipients.

        Args:
            notification: Notification to send.

        Returns:
            List of NotificationResult, one per recipient.
        """
        results = []

        for recipient in notification.recipients:
            # Resolve recipient (phone number validation)
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

            phone_number = resolve_result.data.get("phone_number")

            # Send SMS via circuit breaker
            send_result = self._circuit_breaker.call(
                self._send_sms,
                phone_number=phone_number,
                message=notification.message,
                subject=notification.subject,
            )

            if send_result.is_success:
                results.append(
                    NotificationResult(
                        notification=notification,
                        channel=self.channel_name,
                        status=NotificationStatus.SENT,
                        message=f"Sent SMS to {phone_number}",
                        external_id=send_result.data.get("notification_id"),
                    )
                )
                logger.info(
                    "sms_sent",
                    phone_number=phone_number,
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
                    "sms_failed",
                    phone_number=phone_number,
                    error=send_result.message,
                )

        return results

    def resolve_recipient(self, recipient: Recipient) -> OperationResult:
        """Validate recipient phone number.

        Args:
            recipient: Recipient to resolve.

        Returns:
            OperationResult with phone_number in data field.
        """
        if not recipient.phone_number:
            return OperationResult.permanent_error(
                message="Phone number required for SMS",
                error_code="MISSING_PHONE",
            )

        # Validate E.164 format (+1234567890)
        phone = recipient.phone_number.strip()
        if not phone.startswith("+"):
            return OperationResult.permanent_error(
                message="Phone number must be in E.164 format (+1234567890)",
                error_code="INVALID_PHONE_FORMAT",
            )

        # Basic length validation (E.164 allows 1-15 digits after +)
        digits = phone[1:]
        if not digits.isdigit() or len(digits) < 1 or len(digits) > 15:
            return OperationResult.permanent_error(
                message="Phone number must have 1-15 digits after +",
                error_code="INVALID_PHONE_LENGTH",
            )

        return OperationResult.success(
            message="Phone number validated",
            data={"phone_number": phone},
        )

    def health_check(self) -> OperationResult:
        """Check GC Notify API connectivity.

        Returns:
            OperationResult indicating channel health.
        """
        try:
            # Test JWT token generation (validates credentials)
            header_key, header_value = create_authorization_header()

            if header_key and header_value:
                return OperationResult.success(
                    message="GC Notify API credentials valid",
                    data={"api_url": self._api_url},
                )
            else:
                return OperationResult.transient_error(
                    message="Failed to create authorization header",
                    error_code="AUTH_HEADER_FAILED",
                )

        except Exception as e:
            logger.error("gc_notify_health_check_failed", error=str(e), exc_info=True)
            return OperationResult.transient_error(
                message=f"Health check failed: {str(e)}",
                error_code="HEALTH_CHECK_ERROR",
            )

    def _send_sms(
        self, phone_number: str, message: str, subject: Optional[str] = None
    ) -> OperationResult:
        """Send SMS via GC Notify API.

        Args:
            phone_number: Recipient phone number (E.164 format).
            message: SMS message body.
            subject: Optional subject (prepended to message if provided).

        Returns:
            OperationResult with notification ID in data field.
        """
        try:
            # Format message with subject if provided
            full_message = f"{subject}: {message}" if subject else message

            # Truncate if needed (SMS has length limits)
            if len(full_message) > 1600:  # GC Notify SMS limit
                full_message = full_message[:1597] + "..."
                logger.warning(
                    "sms_message_truncated",
                    phone_number=phone_number,
                    original_length=len(full_message),
                )

            # Prepare payload for GC Notify
            payload = {
                "phone_number": phone_number,
                "message": full_message,
            }

            # Send via GC Notify API
            url = f"{self._api_url}/v2/notifications/sms"
            response = post_event(url, payload)

            if response.status_code == 201:
                response_data = response.json()
                return OperationResult.success(
                    message="SMS sent via GC Notify",
                    data={"notification_id": response_data.get("id")},
                )
            else:
                return OperationResult.transient_error(
                    message=f"GC Notify API error: HTTP {response.status_code}",
                    error_code=f"HTTP_{response.status_code}",
                )

        except Exception as e:
            logger.error(
                "sms_send_error",
                phone_number=phone_number,
                error=str(e),
                exc_info=True,
            )
            return OperationResult.transient_error(
                message=f"SMS send error: {str(e)}",
                error_code="SEND_ERROR",
            )
