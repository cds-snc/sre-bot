"""Groups membership event consumers.

This module contains event handlers for group membership changes.
Notifications use centralized infrastructure services for i18n,
idempotency, and delivery.
"""

from typing import Optional
from infrastructure.events import register_event_handler, Event
from infrastructure.notifications import (
    NotificationDispatcher,
    Notification,
    Recipient,
    NotificationPriority,
)
from infrastructure.i18n import Translator, LocaleResolver, TranslationKey
from infrastructure.idempotency import IdempotencyKeyBuilder
from infrastructure.observability import get_module_logger

logger = get_module_logger()


class GroupNotificationHandler:
    """Handles group membership notifications using centralized infrastructure.

    Uses NotificationDispatcher for delivery (idempotency, circuit breakers, fallback),
    Translator for i18n message formatting, LocaleResolver for user locale detection,
    and IdempotencyKeyBuilder for consistent key generation.
    """

    def __init__(
        self,
        dispatcher: NotificationDispatcher,
        translator: Translator,
        locale_resolver: LocaleResolver,
        key_builder: IdempotencyKeyBuilder,
    ):
        """Initialize handler with injected dependencies."""
        self.dispatcher = dispatcher
        self.translator = translator
        self.locale_resolver = locale_resolver
        self.key_builder = key_builder

    def handle_member_added(self, event: Event) -> None:
        """Handle member added event."""
        self._send_notifications(event, action="added")

    def handle_member_removed(self, event: Event) -> None:
        """Handle member removed event."""
        self._send_notifications(event, action="removed")

    def _send_notifications(self, event: Event, action: str) -> None:
        """Send notifications for membership changes.

        Args:
            event: Domain event containing membership change details
            action: "added" or "removed"
        """
        event_dict = event.to_dict()
        metadata = event_dict.get("metadata", {})
        req = metadata.get("request", {})
        orch = metadata.get("orchestration", {})
        correlation_id = event_dict.get("correlation_id", "")

        requestor_email = req.get("requestor") or req.get("requestor_email")
        member_email = req.get("member_email")
        group_id = req.get("group_id")
        provider = req.get("provider") or orch.get("provider", "unknown")
        action_type = orch.get("action", "")

        if not requestor_email:
            logger.debug(
                "skipping_notification_no_requestor",
                event_type=event_dict.get("event_type"),
            )
            return

        requester_locale = self.locale_resolver.default_locale

        notifications_to_send = []

        requester_message = self.translator.translate_message(
            key=TranslationKey(
                namespace="groups.notifications",
                message_key=f"member_{action}_to_requester",
            ),
            locale=requester_locale,
            variables={
                "member_email": member_email,
                "group_id": group_id,
            },
        )

        subject = self.translator.translate_message(
            key=TranslationKey(
                namespace="groups.notifications",
                message_key="subject",
            ),
            locale=requester_locale,
            variables={"provider": provider.upper()},
        )

        notifications_to_send.append(
            {
                "recipient": requestor_email,
                "message": requester_message,
                "subject": subject,
                "locale": requester_locale,
            }
        )

        if member_email and member_email != requestor_email:
            member_locale = self.locale_resolver.default_locale

            member_message = self.translator.translate_message(
                key=TranslationKey(
                    namespace="groups.notifications",
                    message_key=f"member_{action}_to_member",
                ),
                locale=member_locale,
                variables={
                    "group_id": group_id,
                    "requestor": requestor_email,
                },
            )

            member_subject = self.translator.translate_message(
                key=TranslationKey(
                    namespace="groups.notifications",
                    message_key="subject",
                ),
                locale=member_locale,
                variables={"provider": provider.upper()},
            )

            notifications_to_send.append(
                {
                    "recipient": member_email,
                    "message": member_message,
                    "subject": member_subject,
                    "locale": member_locale,
                }
            )

        for notif_info in notifications_to_send:
            # Idempotency key includes correlation_id to scope deduplication to this
            # specific operation.
            idempotency_key = self.key_builder.build(
                operation="send_notification",
                correlation_id=correlation_id,
                recipient=notif_info["recipient"],
            )

            notification = Notification(
                subject=notif_info["subject"],
                message=notif_info["message"],
                recipients=[Recipient(email=notif_info["recipient"])],
                channels=["chat"],
                priority=NotificationPriority.NORMAL,
                idempotency_key=idempotency_key,
                metadata={
                    "group_id": group_id,
                    "member_email": member_email,
                    "requestor": requestor_email,
                    "action": action_type,
                    "provider": provider,
                    "event_type": event_dict.get("event_type"),
                    "locale": str(notif_info["locale"]),
                },
            )

            results = self.dispatcher.send(notification)

            success = any(r.is_success for r in results)
            logger.info(
                "group_notification_sent",
                recipient=notif_info["recipient"],
                success=success,
                locale=str(notif_info["locale"]),
                idempotency_key=idempotency_key,
            )


_notification_handler: Optional[GroupNotificationHandler] = None


def get_notification_handler() -> GroupNotificationHandler:
    """Get or create notification handler with proper dependencies.

    Factory function following the pattern of infrastructure.idempotency.factory.get_cache().
    Creates singleton handler with all required infrastructure dependencies.

    Returns:
        GroupNotificationHandler instance with configured dependencies
    """
    global _notification_handler

    if _notification_handler is not None:
        return _notification_handler

    from infrastructure.notifications import NotificationDispatcher
    from infrastructure.notifications.channels.chat import ChatChannel
    from infrastructure.idempotency.factory import get_cache
    from infrastructure.i18n import YAMLTranslationLoader
    from pathlib import Path

    dispatcher = NotificationDispatcher(
        channels={"chat": ChatChannel()},
        fallback_order=["chat"],
        idempotency_cache=get_cache(),
        idempotency_ttl_seconds=3600,
    )

    loader = YAMLTranslationLoader(translations_dir=Path("locales"), use_cache=False)
    translator = Translator(loader=loader)
    translator.load_all()

    locale_resolver = LocaleResolver()
    key_builder = IdempotencyKeyBuilder(namespace="groups_notifications")

    _notification_handler = GroupNotificationHandler(
        dispatcher=dispatcher,
        translator=translator,
        locale_resolver=locale_resolver,
        key_builder=key_builder,
    )

    logger.info("initialized_group_notification_handler")
    return _notification_handler


def reset_notification_handler() -> None:
    """Reset notification handler singleton (for testing only)."""
    global _notification_handler
    _notification_handler = None


@register_event_handler("group.member.added")
def handle_member_added(payload: Event) -> None:
    """Handle member added event."""
    handler = get_notification_handler()
    handler.handle_member_added(payload)


@register_event_handler("group.member.removed")
def handle_member_removed(payload: Event) -> None:
    """Handle member removed event."""
    handler = get_notification_handler()
    handler.handle_member_removed(payload)


@register_event_handler("group.listed")
def handle_group_listed(payload: Event) -> None:
    """Handle group listed event (no notifications needed)."""
    pass
