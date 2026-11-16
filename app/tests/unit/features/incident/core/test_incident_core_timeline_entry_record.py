"""Behavior tests for the TimelineEntry record, its kinds and its source-message reference.

Plain value tests. An entry belongs to a named incident, has its own id and a
timezone-aware time. A captured entry points at the message it came from by
system, tenant, conversation and message id, so a re-capture can derive the
same key. A message entry carries text; a severity_changed entry carries only
its structured change, rendered at read time.
"""

import dataclasses
from datetime import UTC, datetime

import pytest

from contracts.workplace import WorkplaceSystem
from features.incident.common.vocabulary import Severity
from features.incident.core.api import MessageReference, SeverityChange, TimelineEntry, TimelineEntryKind

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


def test_a_message_reference_url_is_an_optional_hint() -> None:
    """The link is kept when the vendor gave one and absent otherwise; the four ids identify the message."""
    linked = MessageReference(
        system=WorkplaceSystem.SLACK,
        tenant="T0TENANT",
        conversation_id="C0INCIDENT",
        message_id="1760536800.000100",
        url="https://slack.test/archives/C0INCIDENT/p1760536800000100",
    )

    assert MESSAGE.url is None
    assert linked.url == "https://slack.test/archives/C0INCIDENT/p1760536800000100"


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


def test_an_entry_is_a_message_by_default() -> None:
    """Existing captured and manual entries keep their shape: kind message, no structured payload."""
    entry = _entry()

    assert (entry.kind, entry.severity_change) == (TimelineEntryKind.MESSAGE, None)


def test_a_message_entry_needs_text() -> None:
    """A message is what a person wrote; an empty one would render as nothing."""
    with pytest.raises(ValueError, match="text"):
        _entry(text="  ")


def test_a_severity_entry_carries_the_change_and_no_text() -> None:
    """The change is structured data, rendered per locale at read time, never stored in one language."""
    change = SeverityChange(previous=Severity.SEV3, current=Severity.SEV1)

    entry = _entry(kind=TimelineEntryKind.SEVERITY_CHANGED, text="", severity_change=change)

    assert entry.severity_change == change


def test_a_severity_entry_without_its_change_is_rejected() -> None:
    """A system entry without its payload says nothing a reader could render."""
    with pytest.raises(ValueError, match="severity_change"):
        _entry(kind=TimelineEntryKind.SEVERITY_CHANGED, text="")


def test_a_severity_entry_with_text_is_rejected() -> None:
    """System entries hold no free text, so no language is baked into the record."""
    change = SeverityChange(previous=None, current=Severity.SEV2)

    with pytest.raises(ValueError, match="text"):
        _entry(kind=TimelineEntryKind.SEVERITY_CHANGED, text="Severity raised", severity_change=change)


def test_a_message_entry_with_a_severity_change_is_rejected() -> None:
    """The payload belongs to its kind only."""
    with pytest.raises(ValueError, match="severity_change"):
        _entry(severity_change=SeverityChange(previous=None, current=Severity.SEV2))


@pytest.mark.parametrize(
    ("previous", "current"),
    [(Severity.SEV2, Severity.SEV2), (None, None)],
    ids=["same-level", "both-unset"],
)
def test_a_severity_change_must_change_something(previous: Severity | None, current: Severity | None) -> None:
    """Writing the same severity is a replay, never a change."""
    with pytest.raises(ValueError, match="differ"):
        SeverityChange(previous=previous, current=current)


def test_a_severity_change_takes_members_only() -> None:
    """A bare int would store whatever the caller passed."""
    with pytest.raises(ValueError, match="current"):
        SeverityChange(previous=None, current=2)  # type: ignore[arg-type]
