"""Behavior tests for the in-memory StatusUpdateStore.

The fake is what subdomain tests inject in place of the DynamoDB adapter, so it
is held to the same observable rules: a conditional append that tolerates its
own replay, newest-first reads, and state changes that refuse once the stored
state has moved on.
"""

import dataclasses
from datetime import UTC, datetime

import pytest

from features.incident.core.adapters.in_memory import InMemoryStatusUpdateStore
from features.incident.core.api import (
    StatusUpdate,
    StatusUpdateOrigin,
    StatusUpdateStage,
    StatusUpdateState,
    StatusUpdateStore,
    StatusUpdateText,
)

pytestmark = pytest.mark.unit

INCIDENT_ID = "7f0c3a52-3d0e-4d55-9a4e-6f1f2b9c0a11"
OTHER_INCIDENT_ID = "1b2c3d4e-5f60-4718-8293-a4b5c6d7e8f9"
AT = datetime(2026, 10, 7, 14, 0, tzinfo=UTC)
TEXT = StatusUpdateText(
    affected_service="GC Notify", impact="Emails are delayed.", current_action="Restarting workers.", workaround=""
)


def _draft(sequence: int = 1, incident_id: str = INCIDENT_ID) -> StatusUpdate:
    return StatusUpdate(
        incident_id=incident_id,
        sequence=sequence,
        state=StatusUpdateState.DRAFT,
        stage=StatusUpdateStage.INVESTIGATING,
        en=TEXT,
        fr=TEXT,
        next_update_at=AT,
        author="U0AUTHOR",
        transcript_cutoff=AT,
        transcript_fingerprint=f"fp-{sequence}",
        created_at=AT,
    )


def _approved(draft: StatusUpdate, approver: str = "U0APPROVER") -> StatusUpdate:
    return dataclasses.replace(draft, state=StatusUpdateState.APPROVED, approver=approver, approved_at=AT)


def test_the_fake_satisfies_the_store_interface() -> None:
    """Subdomain tests can inject it wherever core's provider would supply the adapter."""
    assert isinstance(InMemoryStatusUpdateStore(), StatusUpdateStore)


def test_appended_updates_list_newest_first_per_incident() -> None:
    """Updates of other incidents never appear; the latest is the highest sequence."""
    store = InMemoryStatusUpdateStore()
    store.append(_draft(1))
    store.append(_draft(2))
    store.append(_draft(1, incident_id=OTHER_INCIDENT_ID))

    listed = store.list_for_incident(INCIDENT_ID)
    latest = store.latest(INCIDENT_ID)

    assert [update.sequence for update in listed.data or ()] == [2, 1]
    assert latest.data == _draft(2)


def test_latest_without_updates_is_success_with_nothing() -> None:
    """An incident with no update yet answers success and no record."""
    result = InMemoryStatusUpdateStore().latest(INCIDENT_ID)

    assert result.is_success
    assert result.data is None


def test_appending_the_same_record_twice_is_success_and_stores_one() -> None:
    """A replay of an identical append is tolerated, as the adapter tolerates an SDK retry."""
    store = InMemoryStatusUpdateStore()
    store.append(_draft(1))

    assert store.append(_draft(1)).is_success
    assert len(store.list_for_incident(INCIDENT_ID).data or ()) == 1


def test_appending_a_different_record_at_a_taken_sequence_is_a_conflict() -> None:
    """The first writer keeps the sequence; the second is refused with the conflict code."""
    store = InMemoryStatusUpdateStore()
    store.append(_draft(1))

    result = store.append(dataclasses.replace(_draft(1), author="U0OTHER"))

    assert result.error_code == "STATUS_UPDATE_CONFLICT"
    assert store.latest(INCIDENT_ID).data == _draft(1)


def test_transition_from_the_expected_state_replaces_the_record() -> None:
    """Approval stores the approver; a repeat of the same approval is success."""
    store = InMemoryStatusUpdateStore()
    store.append(_draft(1))
    approved = _approved(_draft(1))

    assert store.transition(approved, expected_state=StatusUpdateState.DRAFT).is_success
    assert store.transition(approved, expected_state=StatusUpdateState.DRAFT).is_success
    assert store.latest(INCIDENT_ID).data == approved


def test_transition_after_the_state_moved_on_is_a_conflict() -> None:
    """A second, different approval of the same draft is refused and the first stays stored."""
    store = InMemoryStatusUpdateStore()
    store.append(_draft(1))
    first = _approved(_draft(1))
    store.transition(first, expected_state=StatusUpdateState.DRAFT)

    result = store.transition(_approved(_draft(1), approver="U0OTHER"), expected_state=StatusUpdateState.DRAFT)

    assert result.error_code == "STATUS_UPDATE_CONFLICT"
    assert store.latest(INCIDENT_ID).data == first


def test_transition_of_a_missing_record_is_a_conflict() -> None:
    """Nothing is created by a state change."""
    store = InMemoryStatusUpdateStore()

    result = store.transition(_approved(_draft(1)), expected_state=StatusUpdateState.DRAFT)

    assert result.error_code == "STATUS_UPDATE_CONFLICT"
    assert store.latest(INCIDENT_ID).data is None


def test_an_illegal_transition_raises() -> None:
    """Skipping approval or going back to draft is a programmer error, as in the adapter."""
    store = InMemoryStatusUpdateStore()
    store.append(_draft(1))

    with pytest.raises(ValueError, match="transition"):
        store.transition(
            dataclasses.replace(_draft(1), state=StatusUpdateState.PUBLISHED), expected_state=StatusUpdateState.DRAFT
        )


def _published(approved: StatusUpdate, publisher: str = "U0PUBLISHER") -> StatusUpdate:
    return dataclasses.replace(approved, state=StatusUpdateState.PUBLISHED, published_at=AT, published_by=publisher)


def test_a_published_record_can_be_marked_not_published() -> None:
    """Undo moves a published record back to approved from the expected published state, clearing the publication."""
    store = InMemoryStatusUpdateStore()
    store.append(_draft(1))
    approved = _approved(_draft(1))
    store.transition(approved, expected_state=StatusUpdateState.DRAFT)
    store.transition(_published(approved), expected_state=StatusUpdateState.APPROVED)

    result = store.transition(approved, expected_state=StatusUpdateState.PUBLISHED)

    assert result.is_success
    assert store.latest(INCIDENT_ID).data == approved


def test_undo_after_the_record_was_already_unpublished_by_someone_else_is_a_conflict() -> None:
    """The undo is conditioned on the stored state being published; a record back at approved with other data refuses it."""
    store = InMemoryStatusUpdateStore()
    store.append(_draft(1))
    approved = _approved(_draft(1))
    store.transition(approved, expected_state=StatusUpdateState.DRAFT)

    result = store.transition(dataclasses.replace(approved, approver="U0OTHER"), expected_state=StatusUpdateState.PUBLISHED)

    assert result.error_code == "STATUS_UPDATE_CONFLICT"
    assert store.latest(INCIDENT_ID).data == approved


def test_a_published_record_still_cannot_go_back_to_draft() -> None:
    """Only the undo to approved is allowed from published; a move to draft is a programmer error."""
    store = InMemoryStatusUpdateStore()
    store.append(_draft(1))
    approved = _approved(_draft(1))
    store.transition(approved, expected_state=StatusUpdateState.DRAFT)
    store.transition(_published(approved), expected_state=StatusUpdateState.APPROVED)

    with pytest.raises(ValueError, match="transition"):
        store.transition(_draft(1), expected_state=StatusUpdateState.PUBLISHED)


@pytest.mark.parametrize("origin", [None, *StatusUpdateOrigin])
def test_a_record_reads_back_with_its_origin(origin: StatusUpdateOrigin | None) -> None:
    """The fake keeps the origin as the adapter does, absent included."""
    store = InMemoryStatusUpdateStore()
    store.append(dataclasses.replace(_draft(1), origin=origin))

    latest = store.latest(INCIDENT_ID).data
    assert latest is not None
    assert latest.origin is origin
