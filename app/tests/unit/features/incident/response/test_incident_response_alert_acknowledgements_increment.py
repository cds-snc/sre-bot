"""``RecordStoreAlertAcknowledgements``: one increment of the webhook's ``acknowledged_count`` per call.

Runs over the in-memory record store, held to the DynamoDB store by the records
contract suite. Assertions read the stored item back: an absent count starts at 0,
each call adds one, a missing webhook is ``NOT_FOUND`` with nothing created, and a
store failure is returned with its status, never raised.
"""

import pytest

from contracts.operations import OperationResult, OperationStatus
from features.incident.response.adapters.alert_acknowledgements import WEBHOOKS_TABLE, RecordStoreAlertAcknowledgements
from infrastructure.records.in_memory import InMemoryRecordStore

pytestmark = pytest.mark.unit


class DownStore(InMemoryRecordStore):
    def update(self, *args: object, **kwargs: object) -> OperationResult:
        return OperationResult.transient_error("throttled", retry_after=1.0)


async def test_each_call_adds_one_from_an_absent_count() -> None:
    records = InMemoryRecordStore()
    records.put(WEBHOOKS_TABLE, {"id": "hook-1"})
    counter = RecordStoreAlertAcknowledgements(records)

    first = await counter.increment("hook-1")
    await counter.increment("hook-1")

    assert first.is_success
    assert records.get(WEBHOOKS_TABLE, {"id": "hook-1"}).data == {"id": "hook-1", "acknowledged_count": 2}


async def test_a_missing_webhook_is_not_found_and_creates_nothing() -> None:
    records = InMemoryRecordStore()

    result = await RecordStoreAlertAcknowledgements(records).increment("hook-gone")

    assert result.status is OperationStatus.NOT_FOUND
    assert records.get(WEBHOOKS_TABLE, {"id": "hook-gone"}).data is None


async def test_a_store_failure_is_returned_with_its_status() -> None:
    result = await RecordStoreAlertAcknowledgements(DownStore()).increment("hook-1")

    assert (result.status, result.retry_after) == (OperationStatus.TRANSIENT_ERROR, 1.0)
