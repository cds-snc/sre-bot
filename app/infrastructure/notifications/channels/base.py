"""Notification channel abstract base class.

All channel implementations (Chat, Email, SMS) must implement this interface.
"""

from abc import ABC, abstractmethod
from typing import List
from infrastructure.notifications.models import (
    Notification,
    NotificationResult,
    Recipient,
)
from infrastructure.operations import OperationResult


class NotificationChannel(ABC):
    """Abstract base class for notification channels.

    Each channel handles delivery through a specific platform:
    - ChatChannel: Slack/Teams/Discord DMs
    - EmailChannel: Gmail/MS365 email
    - SMSChannel: GC Notify SMS

    Platform abstraction enables swapping implementations without
    changing dispatcher or feature code.

    Example Implementation:
        @dataclass
        class ChatChannel(NotificationChannel):

            @property
            def channel_name(self) -> str:
                return "chat"

            def send(self, notification: Notification) -> List[NotificationResult]:
                results = []
                for recipient in notification.recipients:
                    # Send DM via Slack
                    result = self._send_dm(recipient, notification.message)
                    results.append(result)
                return results
    """

    @property
    @abstractmethod
    def channel_name(self) -> str:
        """Channel identifier (chat, email, sms).

        Returns:
            Channel name string for routing and logging
        """
        pass

    @abstractmethod
    def send(self, notification: Notification) -> List[NotificationResult]:
        """Send notification to all recipients.

        Must handle errors gracefully and return NotificationResult
        with FAILED status rather than raising exceptions.

        Args:
            notification: Notification to send

        Returns:
            List of NotificationResult (one per recipient)

        Example:
            results = channel.send(notification)
            success_count = sum(1 for r in results if r.is_success)
            logger.info(f"Sent {success_count}/{len(results)} notifications")
        """
        pass

    @abstractmethod
    def resolve_recipient(self, recipient: Recipient) -> OperationResult:
        """Resolve recipient email to platform-specific ID.

        Examples:
        - ChatChannel: Email → Slack user ID via users.lookupByEmail
        - EmailChannel: Email is native format, return as-is
        - SMSChannel: Email → phone number via directory lookup

        Args:
            recipient: Recipient with email address

        Returns:
            OperationResult with platform ID in data field
            - Success: OperationResult(status=SUCCESS, data={"user_id": "U123"})
            - Not Found: OperationResult(status=PERMANENT_ERROR, error_code="USER_NOT_FOUND")

        Example:
            result = channel.resolve_recipient(recipient)
            if result.is_success:
                user_id = result.data.get("user_id")
                # Use user_id for sending
        """
        pass

    @abstractmethod
    def health_check(self) -> OperationResult:
        """Check channel health (API connectivity, credentials).

        Returns:
            OperationResult indicating channel health
            - Success: API reachable, credentials valid
            - Failure: API unreachable or credentials invalid

        Example:
            result = channel.health_check()
            if not result.is_success:
                logger.error(f"Channel unhealthy: {result.message}")
        """
        pass
