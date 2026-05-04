"""Notification service for dependency injection.

Provides a class-based interface to the notification system for easier DI and testing.
Channel construction and circuit breaker wiring belong in providers.py (ADR-0076 S3).
"""

from typing import Dict, List, Optional, TYPE_CHECKING

from infrastructure.notifications.dispatcher import NotificationDispatcher
from infrastructure.notifications.models import Notification, NotificationResult

if TYPE_CHECKING:
    from infrastructure.notifications.channels.base import NotificationChannel
    from infrastructure.idempotency.service import IdempotencyService


class NotificationService:
    """Class-based notification service.

    Wraps the NotificationDispatcher with a service interface to support
    dependency injection and easier testing with mocks.

    Channel instances (ChatChannel, EmailChannel, SMSChannel) and circuit
    breakers are constructed in providers.py and injected here via the
    ``channels`` parameter (ADR-0076 S3 — composition root pattern).

    Usage:
        # Via dependency injection
        from infrastructure.services import NotificationServiceDep

        @router.post("/notify")
        def send_notification(
            notification_service: NotificationServiceDep,
            notification: Notification
        ):
            results = notification_service.send(notification)
            success_count = sum(1 for r in results if r.is_success)
            return {"sent": success_count, "total": len(results)}
    """

    def __init__(
        self,
        channels: Dict[str, "NotificationChannel"],
        idempotency_service: Optional["IdempotencyService"] = None,
        dispatcher: Optional[NotificationDispatcher] = None,
    ):
        """Initialize notification service.

        Args:
            channels: Pre-built channel instances keyed by channel name.
                      Constructed and wired by providers.py.
            idempotency_service: Optional IdempotencyService for preventing duplicates.
            dispatcher: Optional pre-configured NotificationDispatcher instance.
                       If not provided, one is created from ``channels``.
        """
        if dispatcher is None:
            idempotency_cache = None
            if idempotency_service is not None:
                idempotency_cache = idempotency_service.cache

            dispatcher = NotificationDispatcher(
                channels=channels,
                fallback_order=["chat", "email", "sms"],
                idempotency_cache=idempotency_cache,
                idempotency_ttl_seconds=3600,
            )

        self._dispatcher = dispatcher

    def send(self, notification: Notification) -> List[NotificationResult]:
        """Send notification through appropriate channels.

        Process:
        1. Check idempotency cache if key provided
        2. Determine channels to use (notification.channels or fallback_order)
        3. For each recipient:
           a. Try preferred channels first
           b. Fall back to other channels on failure
           c. Track results per recipient per channel
        4. Cache results if idempotency key provided
        5. Return all results

        Args:
            notification: Notification to send

        Returns:
            List of NotificationResult (one per recipient per channel attempted)
        """
        return self._dispatcher.send(notification)

    def broadcast(
        self,
        notification: Notification,
        all_channels: bool = False,
    ) -> List[NotificationResult]:
        """Send notification through multiple channels simultaneously.

        Unlike send(), which tries channels in fallback order,
        broadcast() sends to all channels at once. Useful for
        high-priority notifications where redundancy is desired.

        Args:
            notification: Notification to broadcast
            all_channels: If True, use all available channels instead of
                         notification.channels (default: False)

        Returns:
            List of NotificationResult from all channels
        """
        return self._dispatcher.broadcast(notification, all_channels)

    def register_channel(
        self, channel_name: str, channel: "NotificationChannel"
    ) -> None:
        """Register a new notification channel.

        Allows dynamic channel registration after service initialization.

        Args:
            channel_name: Name of the channel (e.g., "chat", "email", "sms")
            channel: NotificationChannel implementation
        """
        self._dispatcher.channels[channel_name] = channel

    def get_channel(self, channel_name: str) -> Optional["NotificationChannel"]:
        """Get a registered channel by name.

        Args:
            channel_name: Name of the channel to retrieve

        Returns:
            NotificationChannel instance or None if not found
        """
        return self._dispatcher.channels.get(channel_name)

    def list_channels(self) -> List[str]:
        """List all registered channel names.

        Returns:
            List of channel names currently available
        """
        return list(self._dispatcher.channels.keys())

    @property
    def dispatcher(self) -> NotificationDispatcher:
        """Access underlying NotificationDispatcher instance.

        Provided for advanced use cases that need direct access
        to the NotificationDispatcher API.

        Returns:
            The underlying NotificationDispatcher instance
        """
        return self._dispatcher
