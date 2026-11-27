"""The ports the webhooks services depend on; adapters implement them per platform.

A destination's ``system`` picks the poster (decisions/webhooks.md 1: one adapter per
platform). Nothing here names a platform's types.
"""

from typing import Protocol

from capabilities.webhooks.domain.kinds import Destination
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
