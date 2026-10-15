"""Behavior tests for the TimelineEntry record and its source-message reference.

Plain value tests. An entry belongs to a named incident, has its own id and a
timezone-aware time. A captured entry points at the message it came from by
system, tenant, conversation and message id, so a re-capture can derive the
same key.
"""

import dataclasses
from datetime import UTC, datetime

import pytest

from contracts.workplace import WorkplaceSystem
from features.incident.core.api import MessageReference, TimelineEntry

pytestmark = pytest.mark.unit

AT = datetime(2026, 10, 15, 14, 0, tzinfo=UTC)
MESSAGE = MessageReference(
    system=WorkplaceSystem.SLACK, tenant="T0TENANT", conversation_id="C0INCIDENT", message_id="1760536800.000100"
)


def _entry(**overrides: object) -> TimelineEntry:
    fields: dict[str, object] = {
        "incident_id": "7f0c3a52-3d0e-4d55-9a4e-6f1f2b9c0a11",
        "entry_id": "0f8b6c5e-2b1a-5d2f-9e7c-3a4b5c6d7e8f",
        "posted_at": AT,
        "author": "U0AUTHOR",
        "text": "Rolled back the deploy.",
    }
    fields.update(overrides)
    return TimelineEntry(**fields)  # type: ignore[arg-type]


def test_a_manual_entry_has_no_source_message() -> None:
    """An entry typed by a responder has no message to point at."""
    assert _entry().source_message is None


def test_a_captured_entry_keeps_its_source_message() -> None:
    """The four parts of the source message survive on the record."""
    entry = _entry(source_message=MESSAGE)

    assert entry.source_message == MESSAGE


def test_the_entry_is_frozen() -> None:
    """The entry is an immutable value."""
    with pytest.raises(dataclasses.FrozenInstanceError):
        _entry().text = "edited"  # type: ignore[misc]


def test_a_naive_posted_at_is_rejected() -> None:
    """A time without a zone is ambiguous and would break the time-ordered key."""
    with pytest.raises(ValueError, match="posted_at"):
        _entry(posted_at=datetime(2026, 10, 15, 14, 0))


@pytest.mark.parametrize("field", ["incident_id", "entry_id"])
def test_a_blank_id_is_rejected(field: str) -> None:
    """An entry always belongs to an incident and has its own id."""
    with pytest.raises(ValueError, match=field):
        _entry(**{field: ""})


@pytest.mark.parametrize("field", ["tenant", "conversation_id", "message_id"])
def test_a_source_message_needs_every_part(field: str) -> None:
    """Without all four parts the capture key could collide across tenants or conversations."""
    fields = {"system": WorkplaceSystem.SLACK, "tenant": "T0", "conversation_id": "C0", "message_id": "1.0", field: ""}

    with pytest.raises(ValueError, match=field):
        MessageReference(**fields)  # type: ignore[arg-type]


def test_a_source_message_system_must_be_a_member() -> None:
    """The system is validated strictly where it is chosen."""
    with pytest.raises(ValueError, match="system"):
        MessageReference(system="slack", tenant="T0", conversation_id="C0", message_id="1.0")  # type: ignore[arg-type]
