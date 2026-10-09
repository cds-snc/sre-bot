"""Tests for saving a responder's status-update draft in the scribe service.

The service runs against the in-memory status-update store and a stub incident
lookup, with a fixed ``now``. No transcript reader, security reader or text
generator is involved, because saving never reads the conversation or calls a
model. Assertions compare the exact stored records and result codes, because a
save must add one new draft (or none on a replay) and leave every earlier
record as it was.
"""

from collections.abc import Sequence
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from structlog.testing import capture_logs

from contracts.operations import OperationResult, OperationStatus
from contracts.operations.codes import ErrorCode
from features.incident.core.adapters.in_memory import InMemoryStatusUpdateStore
from features.incident.core.api import (
    StatusUpdate,
    StatusUpdateOrigin,
    StatusUpdateStage,
    StatusUpdateState,
    StatusUpdateText,
)
from features.incident.scribe.domain import StatusUpdateEdit
from features.incident.scribe.status_update import save_status_update_draft

pytestmark = pytest.mark.unit

_NOW = datetime(2026, 10, 7, 15, 0, tzinfo=UTC)
_INCIDENT = "inc-uuid-1"
_CHANNEL = "C123"
_SAVER = "U0SAVER"
_FIELDS = ("affected_service", "impact", "current_action", "workaround")


def _at(minutes: int) -> datetime:
    """A time ``minutes`` before ``_NOW``."""
    return _NOW - timedelta(minutes=minutes)


def _text(language: str, tag: str = "") -> StatusUpdateText:
    return StatusUpdateText(**{field: f"{language} {field}{tag}" for field in _FIELDS})


def _record(
    sequence: int,
    state: StatusUpdateState,
    *,
    stage: StatusUpdateStage = StatusUpdateStage.IDENTIFIED,
    minutes_ago: int = 60,
) -> StatusUpdate:
    return StatusUpdate(
        incident_id=_INCIDENT,
        sequence=sequence,
        state=state,
        stage=stage,
        en=_text("en", f" #{sequence}"),
        fr=_text("fr", f" #{sequence}"),
        next_update_at=_at(minutes_ago) + timedelta(minutes=30),
        author="U0",
        transcript_cutoff=_at(minutes_ago),
        transcript_fingerprint=f"v1:sha256:prior{sequence}",
        created_at=_at(minutes_ago),
        origin=StatusUpdateOrigin.MODEL,
    )


_APPROVED = _record(1, StatusUpdateState.APPROVED, minutes_ago=90)
_PENDING = _record(2, StatusUpdateState.DRAFT, minutes_ago=40)
_EDIT = StatusUpdateEdit(stage=StatusUpdateStage.IDENTIFIED, en=_text("en", " edited"), fr=_text("fr", " edited"))


class _StubLookup:
    def __init__(self, result: OperationResult[str] | None = None) -> None:
        self._result = result or OperationResult.success(data=_INCIDENT)

    def find_incident_for_conversation(self, conversation_id: str) -> OperationResult[str]:
        return self._result


class _RacingStore(InMemoryStatusUpdateStore):
    """Store where another writer's record takes the sequence just before our append lands."""

    def __init__(self, state: StatusUpdateState = StatusUpdateState.DRAFT) -> None:
        super().__init__()
        self._state = state
        self.winner: StatusUpdate | None = None

    def append(self, update: StatusUpdate) -> OperationResult[StatusUpdate]:
        if self.winner is None and update.sequence > _PENDING.sequence:
            self.winner = replace(update, author="U-other", en=_text("en", " other"), state=self._state)
            super().append(self.winner)
        return super().append(update)


class _FailingListStore(InMemoryStatusUpdateStore):
    def list_for_incident(self, incident_id: str) -> OperationResult[Sequence[StatusUpdate]]:
        return OperationResult.transient_error(message="throttled", error_code=ErrorCode.RATE_LIMITED, retry_after=3)


class _CountingStore(InMemoryStatusUpdateStore):
    def __init__(self) -> None:
        super().__init__()
        self.appends = 0

    def append(self, update: StatusUpdate) -> OperationResult[StatusUpdate]:
        self.appends += 1
        return super().append(update)


def _store[S: InMemoryStatusUpdateStore](store: S, *records: StatusUpdate) -> S:
    for record in records:
        store.append(record)
    return store


def _stored(store: InMemoryStatusUpdateStore) -> tuple[StatusUpdate, ...]:
    result = store.list_for_incident(_INCIDENT)
    assert result.data is not None
    return tuple(result.data)


def _save(
    *,
    store: InMemoryStatusUpdateStore,
    sequence: int = _PENDING.sequence,
    edit: StatusUpdateEdit = _EDIT,
    author: str = _SAVER,
    lookup: _StubLookup | None = None,
    now: datetime = _NOW,
) -> OperationResult[StatusUpdate]:
    return save_status_update_draft(
        _CHANNEL,
        sequence,
        edit=edit,
        author=author,
        lookup=lookup or _StubLookup(),
        store=store,
        now=now,
    )


class TestSave:
    def test_the_edit_is_stored_as_the_next_draft_written_by_hand(self) -> None:
        """The new record carries the responder's fields, origin HAND and the pending draft's provenance."""
        store = _store(InMemoryStatusUpdateStore(), _APPROVED, _PENDING)

        result = _save(store=store)

        expected = replace(
            _PENDING,
            sequence=3,
            en=_EDIT.en,
            fr=_EDIT.fr,
            author=_SAVER,
            created_at=_NOW,
            origin=StatusUpdateOrigin.HAND,
        )
        assert (result.status, result.data) == (OperationStatus.SUCCESS, expected)
        assert _stored(store) == (expected, _PENDING, _APPROVED)

    def test_partial_fields_are_saved_as_they_are(self) -> None:
        """A draft may be unfinished: blank fields are stored, not refused; approval checks completeness."""
        store = _store(InMemoryStatusUpdateStore(), _APPROVED, _PENDING)
        blank = StatusUpdateText(affected_service="GC Notify", impact="", current_action="", workaround="")
        edit = StatusUpdateEdit(stage=StatusUpdateStage.IDENTIFIED, en=blank, fr=blank)

        result = _save(store=store, edit=edit)

        assert result.data is not None
        assert (result.data.en, result.data.fr) == (blank, blank)

    def test_a_stage_behind_the_approved_stage_is_saved_as_written(self) -> None:
        """Saving applies no stage floor; the responder's stage is kept for approval to judge."""
        store = _store(InMemoryStatusUpdateStore(), _APPROVED, _PENDING)

        result = _save(store=store, edit=replace(_EDIT, stage=StatusUpdateStage.INVESTIGATING))

        assert result.data is not None
        assert result.data.stage is StatusUpdateStage.INVESTIGATING

    def test_a_changed_stage_recomputes_when_the_next_update_is_due(self) -> None:
        """A new stage restarts the update clock from now; a resolved stage has nothing further due."""
        store = _store(InMemoryStatusUpdateStore(), _APPROVED, _PENDING)

        monitoring = _save(store=store, edit=replace(_EDIT, stage=StatusUpdateStage.MONITORING))
        assert monitoring.data is not None
        resolved = _save(store=store, sequence=3, edit=replace(_EDIT, stage=StatusUpdateStage.RESOLVED))

        assert monitoring.data.next_update_at == _NOW + timedelta(minutes=30)
        assert resolved.data is not None
        assert resolved.data.next_update_at == _NOW

    def test_an_unchanged_stage_keeps_the_pending_next_update_time(self) -> None:
        """Editing wording does not move the promised next update."""
        store = _store(InMemoryStatusUpdateStore(), _APPROVED, _PENDING)

        result = _save(store=store)

        assert result.data is not None
        assert result.data.next_update_at == _PENDING.next_update_at

    def test_the_first_draft_of_an_incident_can_be_saved(self) -> None:
        """Without an approved update, the pending first draft is the base."""
        first = _record(1, StatusUpdateState.DRAFT, minutes_ago=40)
        store = _store(InMemoryStatusUpdateStore(), first)

        result = _save(store=store, sequence=1)

        assert result.data is not None
        assert (result.data.sequence, result.data.origin) == (2, StatusUpdateOrigin.HAND)

    def test_logs_never_carry_the_saved_text(self) -> None:
        """The responder's wording stays out of logs; the saved sequence is recorded."""
        store = _store(InMemoryStatusUpdateStore(), _APPROVED, _PENDING)
        secret = StatusUpdateText(affected_service="Acme Payments Ltd", impact="", current_action="", workaround="")

        with capture_logs() as logs:
            _save(store=store, edit=replace(_EDIT, en=secret))

        assert [entry["event"] for entry in logs] == ["incident_status_update_saved"]
        assert logs[0]["sequence"] == 3
        assert [entry for entry in logs if "Acme Payments" in str(entry)] == []


class TestReplay:
    def test_an_identical_repeat_by_the_same_author_returns_the_stored_draft_without_a_write(self) -> None:
        """A double submit of the same save stores one record; the second call returns it."""
        store = _store(_CountingStore(), _APPROVED, _PENDING)
        first = _save(store=store)
        appends = store.appends

        second = _save(store=store, now=_NOW + timedelta(seconds=2))

        assert (second.status, second.data) == (OperationStatus.SUCCESS, first.data)
        assert store.appends == appends
        assert len(_stored(store)) == 3

    def test_saving_the_unchanged_pending_draft_by_its_author_writes_nothing(self) -> None:
        """Saving what is already the pending draft is a no-op that returns it."""
        store = _store(_CountingStore(), _APPROVED, _PENDING)
        appends = store.appends
        unchanged = StatusUpdateEdit(stage=_PENDING.stage, en=_PENDING.en, fr=_PENDING.fr)

        result = _save(store=store, edit=unchanged, author=_PENDING.author)

        assert result.data == _PENDING
        assert store.appends == appends

    def test_the_same_edit_by_another_author_after_a_save_is_a_conflict(self) -> None:
        """Only the saver's own repeat is a replay; anyone else is looking at a stale draft."""
        store = _store(InMemoryStatusUpdateStore(), _APPROVED, _PENDING)
        _save(store=store)

        result = _save(store=store, author="U-other")

        assert (result.status, result.error_code) == (OperationStatus.PERMANENT_ERROR, ErrorCode.STATUS_UPDATE_CONFLICT)
        assert len(_stored(store)) == 3


class TestConflicts:
    @pytest.mark.parametrize(
        ("records", "sequence"),
        [
            ((_APPROVED, _PENDING), 1),
            ((_APPROVED, _PENDING), 3),
            ((_APPROVED, replace(_PENDING, state=StatusUpdateState.APPROVED)), 2),
            ((_APPROVED, replace(_PENDING, state=StatusUpdateState.PUBLISHED)), 2),
            ((), 1),
        ],
        ids=["older-sequence", "newer-sequence", "latest-approved", "latest-published", "no-records"],
    )
    def test_a_target_that_is_not_the_pending_draft_is_a_conflict_with_no_write(
        self, records: tuple[StatusUpdate, ...], sequence: int
    ) -> None:
        """Only the pending draft the responder sees can be saved over; anything else changed under them."""
        store = _store(InMemoryStatusUpdateStore(), *records)
        before = _stored(store)

        result = _save(store=store, sequence=sequence)

        assert (result.status, result.error_code) == (OperationStatus.PERMANENT_ERROR, ErrorCode.STATUS_UPDATE_CONFLICT)
        assert _stored(store) == before

    def test_an_append_conflict_with_a_newer_draft_returns_that_draft(self) -> None:
        """When another writer's draft took the sequence, it is what the responder now sees."""
        store = _store(_RacingStore(), _APPROVED, _PENDING)

        result = _save(store=store)

        assert (result.status, result.data) == (OperationStatus.SUCCESS, store.winner)

    def test_an_append_conflict_with_a_non_draft_is_a_conflict(self) -> None:
        """A record that is no longer a draft cannot be adopted as the saved draft."""
        store = _store(_RacingStore(StatusUpdateState.APPROVED), _APPROVED, _PENDING)

        result = _save(store=store)

        assert (result.status, result.error_code) == (OperationStatus.PERMANENT_ERROR, ErrorCode.STATUS_UPDATE_CONFLICT)


class TestPassThrough:
    def test_a_store_read_failure_passes_through(self) -> None:
        """Without the incident's records nothing can be checked, so the store's error is returned."""
        result = _save(store=_FailingListStore())

        assert (result.status, result.error_code, result.retry_after) == (
            OperationStatus.TRANSIENT_ERROR,
            ErrorCode.RATE_LIMITED,
            3,
        )

    def test_a_lookup_refusal_passes_through_with_no_write(self) -> None:
        """Outside an incident nothing is saved."""
        store = _store(InMemoryStatusUpdateStore(), _APPROVED, _PENDING)
        refusal: OperationResult[str] = OperationResult.error(
            OperationStatus.NOT_FOUND, message="no incident", error_code=ErrorCode.NOT_AN_INCIDENT
        )

        result = _save(store=store, lookup=_StubLookup(refusal))

        assert (result.status, result.error_code) == (OperationStatus.NOT_FOUND, ErrorCode.NOT_AN_INCIDENT)
        assert _stored(store) == (_PENDING, _APPROVED)
