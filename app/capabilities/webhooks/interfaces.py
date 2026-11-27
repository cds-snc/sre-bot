"""The ports the webhooks services depend on; adapters and stores implement them.

A destination's ``system`` picks the poster (decisions/webhooks.md 1: one adapter per
platform). The stores speak the domain model, never raw attribute shapes; the SNS port
fetches certificates and confirms subscriptions. Nothing here names a platform's types.
Every port is async: its adapter offloads any blocking call (decisions/outbound-clients.md).
"""

from datetime import datetime
from typing import Protocol

from capabilities.webhooks.domain.inbox import InboxItem
from capabilities.webhooks.domain.kinds import Destination, WebhookInstance
from capabilities.webhooks.domain.messages import OutboundMessage
from contracts.operations import OperationResult


class DeliveryPoster(Protocol):
    """Posts one delivery's messages; holds what is cached for that delivery only (mention lookups)."""

    async def post(self, destination: Destination, message: OutboundMessage) -> OperationResult[str]:
        """Post ``message`` to ``destination``; success carries the platform's message id.

        A transient failure carries the platform's ``retry_after``: the inbox retries the
        item, so the poster never waits or retries in process.
        """
        ...


class ChannelPoster(Protocol):
    """One platform's poster."""

    def for_delivery(self) -> DeliveryPoster:
        """Open a poster for one delivery, shared by its destinations on this platform."""
        ...


class WebhookStore(Protocol):
    """Reads instances; the control plane is their one writer."""

    async def by_url_id(self, webhook_id: str) -> OperationResult[WebhookInstance]:
        """The provisioned instance behind a URL token; NOT_FOUND when there is none.

        The token is used for this lookup only and never appears in the result.
        """
        ...

    async def by_ref(self, instance_ref: str) -> OperationResult[WebhookInstance]:
        """The provisioned instance with ``instance_ref``; NOT_FOUND when there is none."""
        ...


class InboxStore(Protocol):
    """The durable inbox. Writes are conditional: an insert only where no item has the key,
    and every change only while the item still has the state and owner the writer read."""

    async def insert(self, item: InboxItem) -> OperationResult[bool]:
        """Insert ``item``; True when it is new, False when its key already exists."""
        ...

    async def get(self, key: str) -> OperationResult[InboxItem]:
        """Read one item, strongly consistent; NOT_FOUND when there is none."""
        ...

    async def replace(self, current: InboxItem, new: InboxItem) -> OperationResult[InboxItem]:
        """Write ``new``'s changes over ``current``, guarded on ``current``'s state and owner.

        Success carries ``new``; success with no data means the guard was lost (another worker
        owns the item) and nothing was written.
        """
        ...

    async def due(self, now: datetime, limit: int) -> OperationResult[tuple[InboxItem, ...]]:
        """Up to ``limit`` items whose lease or retry is due, oldest first (may lag writes)."""
        ...


class SnsCertificates(Protocol):
    """Fetches SNS signing certificates, from an SNS host only."""

    async def certificate(self, url: str) -> OperationResult[bytes]:
        """The PEM certificate at ``url``; a transient failure means verification could not run."""
        ...


class SubscriptionConfirmer(Protocol):
    """Confirms an SNS subscription from its inbox item."""

    async def confirm(self, subscribe_url: str) -> OperationResult[None]:
        """Visit ``subscribe_url`` once, with no redirects."""
        ...
