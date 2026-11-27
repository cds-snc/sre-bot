"""``AlertAcknowledgements`` over the record store's webhooks table, the counter the alert's ignore button raises.

TODO(TASK-37.6.2): the webhooks feature's own acknowledgement port replaces this
adapter and its table declaration. Until then it adds one to the item's
``acknowledged_count`` (an absent count is 0) and never creates an item: a
webhook deleted since the alert was posted is ``NOT_FOUND``. The increment is
not replay-safe, so a retried write may count twice; the count is approximate.
"""

import asyncio

from contracts.operations import OperationResult
from contracts.records import IncrementAttribute, KeySchema, RecordStore, RecordTable

WEBHOOKS_TABLE = RecordTable(name="webhooks", key=KeySchema(partition="id"))
ACKNOWLEDGED_COUNT = "acknowledged_count"


class RecordStoreAlertAcknowledgements:
    """Raise a webhook's acknowledged count through ``RecordStore.update``, off the event loop."""

    def __init__(self, records: RecordStore) -> None:
        self._records = records

    async def increment(self, webhook_id: str) -> OperationResult[None]:
        """Add one to ``webhook_id``'s acknowledged count; the store's failure is returned, never raised."""
        updated = await asyncio.to_thread(
            self._records.update, WEBHOOKS_TABLE, {"id": webhook_id}, [IncrementAttribute(ACKNOWLEDGED_COUNT, 1)]
        )
        if updated.is_success:
            return OperationResult.success()
        return OperationResult.error(
            status=updated.status,
            message=updated.message or "The acknowledgement could not be counted",
            error_code=updated.error_code,
            retry_after=updated.retry_after,
        )
