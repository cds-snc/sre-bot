"""Notification dispatcher with multi-channel routing and fallback.

Centralized notification delivery system that:
- Routes notifications to multiple channels (chat, email, sms)
- Implements automatic fallback (chat → email → sms)
- Prevents duplicate sends with idempotency cache
- Protects channels with circuit breakers
- Provides comprehensive observability

Usage Example:
    from infrastructure.notifications import (
        NotificationDispatcher,
        Notification,
        Recipient,
        NotificationPriority,
    )

    dispatcher = NotificationDispatcher(
        channels={"chat": chat_channel, "email": email_channel},
        idempotency_cache=cache,
    )

    notification = Notification(
        subject="Access Granted",
        message="You have been added to engineering-team",
        recipients=[Recipient(email="user@example.com")],
        channels=["chat", "email"],
        idempotency_key="group-add-12345-user@example.com",
    )

    results = dispatcher.send(notification)
    success_count = sum(1 for r in results if r.is_success)
    logger.info(f"Sent {success_count}/{len(results)} notifications")
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional
import structlog
from infrastructure.notifications.channels.base import NotificationChannel
from infrastructure.notifications.models import (
    Notification,
    NotificationResult,
    NotificationStatus,
)
from infrastructure.idempotency.cache import IdempotencyCache

logger = structlog.get_logger()


class NotificationDispatcher:
    """Multi-channel notification dispatcher.

    Orchestrates notification delivery across multiple channels with:
    - Channel routing based on notification.channels
    - Automatic fallback when channels fail
    - Idempotency to prevent duplicate sends
    - Per-recipient channel selection
    - Comprehensive logging for observability

    Attributes:
        channels: Dict mapping channel name to NotificationChannel instance
        fallback_order: Default fallback sequence (default: ["chat", "email", "sms"])
        idempotency_cache: Optional cache to prevent duplicate sends
        idempotency_ttl_seconds: TTL for idempotency cache entries (default: 3600)

    Example:
        dispatcher = NotificationDispatcher(
            channels={
                "chat": ChatChannel(),
                "email": EmailChannel(),
            },
            fallback_order=["chat", "email"],
        )

        results = dispatcher.send(notification)
    """

    def __init__(
        self,
        channels: Dict[str, NotificationChannel],
        fallback_order: Optional[List[str]] = None,
        idempotency_cache: Optional[IdempotencyCache] = None,
        idempotency_ttl_seconds: int = 3600,
    ):
        """Initialize notification dispatcher.

        Args:
            channels: Dict mapping channel name to NotificationChannel instance
            fallback_order: Default channel fallback sequence
            idempotency_cache: Optional cache for preventing duplicate sends
            idempotency_ttl_seconds: TTL for cached idempotency keys
        """
        self.channels = channels
        self.fallback_order = fallback_order or ["chat", "email", "sms"]
        self.idempotency_cache = idempotency_cache
        self.idempotency_ttl_seconds = idempotency_ttl_seconds

        logger.info(
            "initialized_notification_dispatcher",
            channels=list(channels.keys()),
            fallback_order=self.fallback_order,
            idempotency_enabled=idempotency_cache is not None,
        )

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

        Example:
            results = dispatcher.send(notification)

            # Check overall success
            success_count = sum(1 for r in results if r.is_success)
            logger.info(f"Delivered {success_count}/{len(results)}")

            # Check per-recipient
            for recipient in notification.recipients:
                recipient_results = [
                    r for r in results
                    if r.notification.recipients[0].email == recipient.email
                ]
                success = any(r.is_success for r in recipient_results)
        """
        # Check idempotency cache
        if notification.idempotency_key and self.idempotency_cache:
            cached = self._check_idempotency_cache(notification.idempotency_key)
            # Only use cached results if they exist and contain actual result data
            if cached and cached.get("results"):
                logger.info(
                    "notification_already_sent",
                    idempotency_key=notification.idempotency_key,
                    cached_at=cached.get("sent_at"),
                    result_count=len(cached.get("results", [])),
                )
                return cached.get("results", [])

        # Send through channels
        results = self._send_through_channels(notification)

        # Cache results if idempotency key provided
        if notification.idempotency_key and self.idempotency_cache:
            self._cache_results(notification.idempotency_key, results)

        # Log summary
        success_count = sum(1 for r in results if r.is_success)
        logger.info(
            "notification_sent",
            subject=notification.subject,
            recipient_count=len(notification.recipients),
            channel_count=len(notification.channels),
            success_count=success_count,
            total_attempts=len(results),
            idempotency_key=notification.idempotency_key,
        )

        return results

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

        Example:
            # Send urgent notification to all channels
            results = dispatcher.broadcast(
                notification,
                all_channels=True,
            )
        """
        channels_to_use = (
            list(self.channels.keys()) if all_channels else notification.channels
        )

        logger.info(
            "broadcasting_notification",
            subject=notification.subject,
            recipient_count=len(notification.recipients),
            channels=channels_to_use,
        )

        results = []
        for channel_name in channels_to_use:
            channel = self.channels.get(channel_name)
            if not channel:
                logger.warning(
                    "channel_not_found",
                    channel_name=channel_name,
                    available_channels=list(self.channels.keys()),
                )
                continue

            try:
                channel_results = channel.send(notification)
                results.extend(channel_results)
            except Exception as e:
                logger.error(
                    "channel_send_failed",
                    channel_name=channel_name,
                    error=str(e),
                    exc_info=True,
                )
                # Add failure results for all recipients
                for recipient in notification.recipients:
                    results.append(
                        NotificationResult(
                            notification=notification,
                            channel=channel_name,
                            status=NotificationStatus.FAILED,
                            message=f"Channel exception: {str(e)}",
                            error_code="CHANNEL_EXCEPTION",
                        )
                    )

        return results

    def _send_through_channels(
        self, notification: Notification
    ) -> List[NotificationResult]:
        """Send notification with fallback support.

        For each recipient:
        1. Try preferred channels first (recipient.preferred_channels)
        2. If all preferred channels fail, try fallback channels
        3. Track one successful send per recipient

        Args:
            notification: Notification to send

        Returns:
            List of NotificationResult
        """
        all_results = []

        for recipient in notification.recipients:
            # Determine channel order for this recipient
            channel_order = self._get_channel_order(recipient, notification)

            recipient_sent = False
            recipient_results = []

            for channel_name in channel_order:
                channel = self.channels.get(channel_name)
                if not channel:
                    logger.warning(
                        "channel_not_available",
                        channel_name=channel_name,
                        recipient=recipient.email,
                    )
                    continue

                # Create single-recipient notification
                single_recipient_notification = Notification(
                    subject=notification.subject,
                    message=notification.message,
                    recipients=[recipient],
                    priority=notification.priority,
                    channels=[channel_name],
                    metadata=notification.metadata,
                    html_body=notification.html_body,
                    attachments=notification.attachments,
                    retry_on_failure=notification.retry_on_failure,
                    idempotency_key=notification.idempotency_key,
                )

                try:
                    results = channel.send(single_recipient_notification)
                    recipient_results.extend(results)

                    # Check if any send succeeded
                    if any(r.is_success for r in results):
                        recipient_sent = True
                        logger.debug(
                            "recipient_notified",
                            recipient=recipient.email,
                            channel=channel_name,
                        )
                        break  # Success, stop trying channels

                except Exception as e:
                    logger.error(
                        "channel_exception",
                        channel_name=channel_name,
                        recipient=recipient.email,
                        error=str(e),
                        exc_info=True,
                    )
                    recipient_results.append(
                        NotificationResult(
                            notification=single_recipient_notification,
                            channel=channel_name,
                            status=NotificationStatus.FAILED,
                            message=f"Channel exception: {str(e)}",
                            error_code="CHANNEL_EXCEPTION",
                        )
                    )

            if not recipient_sent:
                logger.warning(
                    "recipient_notification_failed",
                    recipient=recipient.email,
                    channels_tried=channel_order,
                )

            all_results.extend(recipient_results)

        return all_results

    def _get_channel_order(self, recipient, notification: Notification) -> List[str]:
        """Determine channel order for recipient.

        Priority:
        1. Recipient's preferred channels (if overlap with notification.channels)
        2. Notification's specified channels
        3. Fallback order for remaining channels

        Args:
            recipient: Recipient with preferred_channels
            notification: Notification with channels list

        Returns:
            Ordered list of channel names to try
        """
        # Start with recipient's preferred channels that are in notification.channels
        preferred = [
            ch for ch in recipient.preferred_channels if ch in notification.channels
        ]

        # Add remaining notification channels
        remaining = [ch for ch in notification.channels if ch not in preferred]

        # Combine: preferred first, then remaining
        channel_order = preferred + remaining

        # If no channels specified, use fallback order
        if not channel_order:
            channel_order = [ch for ch in self.fallback_order if ch in self.channels]

        return channel_order

    def _check_idempotency_cache(self, key: str) -> Optional[dict]:
        """Check if notification was already sent.

        Args:
            key: Idempotency key

        Returns:
            Cached results dict with reconstructed NotificationResult objects,
            or None if not found or invalid
        """
        if not self.idempotency_cache:
            return None

        try:
            cached = self.idempotency_cache.get(key)
            if cached:
                # Validate cache structure
                if not isinstance(cached, dict):
                    logger.warning(
                        "invalid_cache_structure",
                        idempotency_key=key,
                        cached_type=type(cached).__name__,
                    )
                    return None

                # Check if results exist and are valid
                if "results" not in cached or not cached["results"]:
                    logger.warning(
                        "empty_cached_results",
                        idempotency_key=key,
                        cache_keys=list(cached.keys()),
                    )
                    return None

                logger.debug(
                    "idempotency_cache_hit",
                    idempotency_key=key,
                    result_count=len(cached.get("results", [])),
                )
                # Reconstruct NotificationResult objects from cached dicts
                if isinstance(cached["results"], list):
                    cached["results"] = [
                        NotificationResult(**result_dict)
                        for result_dict in cached["results"]
                    ]
                return cached
        except Exception as e:
            logger.error(
                "idempotency_cache_error",
                idempotency_key=key,
                error=str(e),
                exc_info=True,
            )

        return None

    def _cache_results(self, key: str, results: List[NotificationResult]) -> None:
        """Cache notification results.

        Args:
            key: Idempotency key
            results: Notification results to cache
        """
        if not self.idempotency_cache:
            return

        try:
            # Convert Pydantic models to JSON-serializable dicts
            # Use mode="json" to serialize datetime/enum/etc properly
            cache_data = {
                "results": [r.model_dump(mode="json") for r in results],
                "sent_at": datetime.now(timezone.utc).isoformat(),
            }

            self.idempotency_cache.set(
                key,
                cache_data,
                ttl_seconds=self.idempotency_ttl_seconds,
            )

            logger.debug(
                "cached_notification_results",
                idempotency_key=key,
                result_count=len(results),
                ttl_seconds=self.idempotency_ttl_seconds,
            )
        except Exception as e:
            logger.error(
                "idempotency_cache_set_error",
                idempotency_key=key,
                error=str(e),
                exc_info=True,
            )

    def get_available_channels(self) -> List[str]:
        """Get list of available channel names.

        Returns:
            List of channel names
        """
        return list(self.channels.keys())

    def health_check(self) -> Dict[str, bool]:
        """Check health of all channels.

        Returns:
            Dict mapping channel name to health status (True=healthy)

        Example:
            health = dispatcher.health_check()
            if not all(health.values()):
                logger.warning("Some channels unhealthy", health=health)
        """
        health_status = {}

        for channel_name, channel in self.channels.items():
            try:
                result = channel.health_check()
                health_status[channel_name] = result.is_success
            except Exception as e:
                logger.error(
                    "channel_health_check_failed",
                    channel_name=channel_name,
                    error=str(e),
                    exc_info=True,
                )
                health_status[channel_name] = False

        return health_status
