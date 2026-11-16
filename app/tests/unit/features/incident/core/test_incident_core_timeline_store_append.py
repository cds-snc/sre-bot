"""Behavior tests for TimelineStore.append: one item per entry under its incident, idempotent on its key.

The item layout is read back from InMemoryRecordStore under the real store;
the replay case runs on the real store and on the in-memory fake, which must
agree; a backend failure comes from a MagicMock RecordStore.
"""

from collections.abc import Callable
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from contracts.operations.result import OperationResult
from contracts.operations.status import OperationStatus
from contracts.records import RecordStore
from contracts.workplace import WorkplaceSystem
from features.incident.common.settings import get_incident_core_settings
from features.incident.common.vocabulary import Severity
from features.incident.core.adapters.in_memory import InMemoryTimelineStore
from features.incident.core.adapters.timeline_items import entry_key
from features.incident.core.domain import MessageReference, SeverityChange, TimelineEntry, TimelineEntryKind
from features.incident.core.store import RecordTimelineStore, TimelineStore, timeline_table
from infrastructure.records.in_memory import InMemoryRecordStore

pytestmark = pytest.mark.unit

INCIDENT_ID = "inc-1"
AT = datetime(2026, 10, 15, 14, 0, tzinfo=UTC)
MESSAGE = MessageReference(
    system=WorkplaceSystem.SLACK,
    tenant="T0SLACK",
    conversation_id="C0INCIDENT",
    message_id="1760536800.000100",
    url="https://s/p1",
)
CAPTURED = TimelineEntry(
    incident_id=INCIDENT_ID, entry_id="e-1", posted_at=AT, author="U0AUTHOR", text="Rolled back", source_message=MESSAGE
)
SEVERITY = TimelineEntry(
    incident_id=INCIDENT_ID,
    entry_id="e-2",
    posted_at=AT,
    author="U0EDITOR",
    text="",
    kind=TimelineEntryKind.SEVERITY_CHANGED,
    severity_change=SeverityChange(previous=Severity.SEV3, current=Severity.SEV1),
)


def _table_name() -> str:
    return get_incident_core_settings().timeline_table


def _real(records: RecordStore | None = None) -> RecordTimelineStore:
    return RecordTimelineStore(records or InMemoryRecordStore(), timeline_table(_table_name()))


STORES: dict[str, Callable[[], TimelineStore]] = {"real": _real, "fake": InMemoryTimelineStore}


def test_the_table_is_keyed_by_incident_and_entry_key() -> None:
    """The declaration matches terraform: partition incident_id, sort entry_key."""
    table = timeline_table("t")

    assert (table.key.partition, table.key.sort) == ("incident_id", "entry_key")


def test_a_captured_entry_is_stored_with_its_key_and_source_message() -> None:
    """The key sorts by time; the message map keeps its four ids and the url hint."""
    records = InMemoryRecordStore()

    assert _real(records).append(CAPTURED).is_success

    stored = records.get(timeline_table(_table_name()), {"incident_id": INCIDENT_ID, "entry_key": entry_key(AT, "e-1")}).data
    assert stored == {
        "incident_id": INCIDENT_ID,
        "entry_key": "2026-10-15T14:00:00.000000+00:00#e-1",
        "entry_id": "e-1",
        "kind": "message",
        "posted_at": "2026-10-15T14:00:00.000000+00:00",
        "author": "U0AUTHOR",
        "text": "Rolled back",
        "source_message": {
            "system": "slack",
            "tenant": "T0SLACK",
            "conversation_id": "C0INCIDENT",
            "message_id": "1760536800.000100",
            "url": "https://s/p1",
        },
    }


def test_a_severity_entry_is_stored_as_structured_levels_without_text() -> None:
    """Previous and current are stored as their numbers; there is no text to store."""
    records = InMemoryRecordStore()

    assert _real(records).append(SEVERITY).is_success

    stored = records.get(timeline_table(_table_name()), {"incident_id": INCIDENT_ID, "entry_key": entry_key(AT, "e-2")}).data
    assert stored is not None
    assert (stored["kind"], stored["severity_previous"], stored["severity_current"]) == ("severity_changed", 3, 1)
    assert "text" not in stored


@pytest.mark.parametrize("name", sorted(STORES))
def test_appending_the_same_entry_again_is_a_replay_that_succeeds(name: str) -> None:
    """The second append finds the key taken and writes nothing; the caller sees success."""
    timeline = STORES[name]()
    assert timeline.append(CAPTURED).is_success

    result = timeline.append(CAPTURED)

    assert result.is_success
    assert result.data == CAPTURED


def test_the_fake_lists_an_incidents_entries_in_key_order() -> None:
    """The fake keeps one entry per key, ordered as the table's sort key orders them."""
    timeline = InMemoryTimelineStore()
    later = TimelineEntry(incident_id=INCIDENT_ID, entry_id="e-0", posted_at=AT.replace(hour=15), author="U0", text="Later")
    assert timeline.append(later).is_success
    assert timeline.append(CAPTURED).is_success
    assert timeline.append(CAPTURED).is_success

    assert timeline.entries(INCIDENT_ID) == (CAPTURED, later)


def test_a_store_failure_is_classified_with_a_generic_message() -> None:
    """The backend's status, code and retry hint are kept; its message is not."""
    records = MagicMock(spec=RecordStore)
    records.put_if_not_exists.return_value = OperationResult.error(
        OperationStatus.TRANSIENT_ERROR, message="throttled: arn:aws:...", error_code="Throttling", retry_after=3
    )

    result = _real(records).append(CAPTURED)

    assert (result.status, result.error_code, result.retry_after) == (OperationStatus.TRANSIENT_ERROR, "Throttling", 3)
    assert result.message == "The incident timeline store is unavailable."
