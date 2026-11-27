"""The webhooks capability's extension point: event consumers by type, handlers by id.

A feature implements these hooks in its plugin module; the host calls them once, in the
extension-point phase, and the capability validates every contributed value before it
serves (decisions/plugins.md, decisions/webhooks.md 5a).
"""

from collections.abc import Sequence

from capabilities.webhooks.domain.extensions import EventConsumer, EventHandler
from contracts.plugins.namespace import hookspec


class WebhooksSpecs:
    """Hooks a feature implements to consume webhook events."""

    @hookspec
    def register_webhook_consumers(self) -> Sequence[EventConsumer]:
        """Return the consumers this plugin contributes, each naming its event types."""
        raise NotImplementedError

    @hookspec
    def register_webhook_handlers(self) -> Sequence[EventHandler]:
        """Return the handlers this plugin contributes, each with the dotted id sender kinds name."""
        raise NotImplementedError
