"""Tests for starting an incident status update by hand in the comms service.

The service runs against the in-memory status-update store and stubs for the
incident lookup and the transcript reader, with a fixed ``now``, so each test
controls exactly which records exist and which messages are read, and asserts
what was stored. Starting takes no text generator and no security reader, so no
model call or security read can happen.
"""

from collections.abc import Sequence
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from structlog.testing import capture_logs

from contracts.operations import OperationResult, OperationStatus
from contracts.operations.codes import ErrorCode
from features.incident.comms.domain import StatusUpdateDraftOutcome, StatusUpdateOutcomeKind
from features.incident.comms.service import start_status_update_draft
from features.incident.core.adapters.in_memory import InMemoryStatusUpdateStore
from features.incident.core.api import (
    StatusUpdate,
    StatusUpdateOrigin,
    StatusUpdateStage,
    StatusUpdateState,
    StatusUpdateText,
    TranscriptMessage,
)

pytestmark = pytest.mark.unit

_NOW = datetime(2026, 10, 7, 15, 0, tzinfo=UTC)
_INCIDENT = "inc-uuid-1"
_CHANNEL = "C123"
_FIELDS = ("affected_service", "impact", "current_action", "workaround")
_BLANK = StatusUpdateText(affected_service="", impact="", current_action="", workaround="")


def _at(minutes: int) -> datetime:
    """A time ``minutes`` before ``_NOW``."""
    return _NOW - timedelta(minutes=minutes)


def _human(text: str, minutes_ago: int, author: str = "Ada") -> TranscriptMessage:
    return TranscriptMessage(author=author, text=text, posted_at=_at(minutes_ago))


def _bot(text: str, minutes_ago: int) -> TranscriptMessage:
    return TranscriptMessage(author="Alertmanager", text=text, posted_at=_at(minutes_ago), is_bot=True)


def _text(language: str, tag: str = "") -> StatusUpdateText:
    return StatusUpdateText(**{field: f"{language} {field}{tag}" for field in _FIELDS})


def _record(
    sequence: int,
    state: StatusUpdateState,
    *,
    stage: StatusUpdateStage = StatusUpdateStage.IDENTIFIED,
    cutoff_minutes_ago: int = 60,
    author: str = "U0",
) -> StatusUpdate:
    return StatusUpdate(
        incident_id=_INCIDENT,
        sequence=sequence,
        state=state,
        stage=stage,
        en=_text("en", f" #{sequence}"),
        fr=_text("fr", f" #{sequence}"),
        next_update_at=_at(cutoff_minutes_ago) + timedelta(minutes=30),
        author=author,
        transcript_cutoff=_at(cutoff_minutes_ago),
        transcript_fingerprint=f"v1:sha256:prior{sequence}",
        created_at=_at(cutoff_minutes_ago),
    )


class _StubLookup:
    def __init__(self, result: OperationResult[str] | None = None) -> None:
        self._result = result or OperationResult.success(data=_INCIDENT)
        self.calls: list[str] = []

    def find_incident_for_conversation(self, conversation_id: str) -> OperationResult[str]:
        self.calls.append(conversation_id)
        return self._result


class _StubReader:
    def __init__(self, messages: Sequence[TranscriptMessage] = (), *, started_at: datetime | None = _at(600)) -> None:
        self._messages = list(messages)
        self._started_at = started_at
        self.reads: list[dict[str, Any]] = []

    def conversation_started_at(self, conversation_id: str) -> datetime | None:
        return self._started_at

    def read_transcript(
        self,
        conversation_id: str,
        *,
        since: datetime,
        limit: int,
        exclude_own_and_system_messages: bool = False,
    ) -> Sequence[TranscriptMessage]:
        self.reads.append(
            {"conversation_id": conversation_id, "since": since, "limit": limit, "exclude": exclude_own_and_system_messages}
        )
        return self._messages


class _RacingStore(InMemoryStatusUpdateStore):
    """Store where another writer takes the sequence just before our append lands."""

    def __init__(self, winner_state: StatusUpdateState) -> None:
        super().__init__()
        self._winner_state = winner_state
        self.winner: StatusUpdate | None = None

    def append(self, update: StatusUpdate) -> OperationResult[StatusUpdate]:
        if self.winner is None:
            self.winner = replace(update, author="U-other", state=self._winner_state)
            super().append(self.winner)
        return super().append(update)


class _FailingListStore(InMemoryStatusUpdateStore):
    def list_for_incident(self, incident_id: str) -> OperationResult[Sequence[StatusUpdate]]:
        return OperationResult.transient_error(message="throttled", error_code=ErrorCode.RATE_LIMITED, retry_after=3)


def _store(*records: StatusUpdate) -> InMemoryStatusUpdateStore:
    store = InMemoryStatusUpdateStore()
    for record in records:
        store.append(record)
    return store


def _stored(store: InMemoryStatusUpdateStore) -> tuple[StatusUpdate, ...]:
    result = store.list_for_incident(_INCIDENT)
    assert result.data is not None
    return tuple(result.data)


def _start(
    *,
    store: InMemoryStatusUpdateStore | None = None,
    reader: _StubReader | None = None,
    lookup: _StubLookup | None = None,
) -> OperationResult[StatusUpdateDraftOutcome]:
    return start_status_update_draft(
        _CHANNEL,
        author="U123",
        lookup=lookup or _StubLookup(),
        reader=reader or _StubReader(),
        store=store if store is not None else InMemoryStatusUpdateStore(),
        now=_NOW,
    )


class TestStartByHand:
    def test_the_approved_update_is_stored_as_a_hand_draft_by_the_responder(self) -> None:
        """Starting copies the latest approved stage and fields into the next draft, written by hand."""
        prior = _record(1, StatusUpdateState.APPROVED, stage=StatusUpdateStage.MONITORING, cutoff_minutes_ago=60)
        store = _store(prior)

        result = _start(store=store, reader=_StubReader([_human("still slow", 10)]))

        assert result.is_success and result.data is not None
        assert result.data.kind is StatusUpdateOutcomeKind.MANUAL
        update = result.data.update
        assert (update.sequence, update.state, update.stage) == (2, StatusUpdateState.DRAFT, StatusUpdateStage.MONITORING)
        assert (update.en, update.fr) == (prior.en, prior.fr)
        assert (update.author, update.origin, update.created_at) == ("U123", StatusUpdateOrigin.HAND, _NOW)
        assert update.transcript_cutoff == _at(10)
        assert update.next_update_at == _NOW + timedelta(minutes=30)
        assert _stored(store)[0] == update

    def test_the_first_update_starts_blank_at_investigating(self) -> None:
        """With no approved update to copy, every field is blank and the stage is the first one."""
        result = _start(reader=_StubReader([_human("seeing 500s", 5)]))

        assert result.data is not None
        update = result.data.update
        assert (update.sequence, update.stage, update.en, update.fr) == (1, StatusUpdateStage.INVESTIGATING, _BLANK, _BLANK)

    def test_with_nothing_new_the_approved_update_is_still_copied_by_hand(self) -> None:
        """Nothing new is no reason to carry forward: the responder asked to write, so the draft is the approved text, by hand."""
        prior = _record(1, StatusUpdateState.APPROVED, cutoff_minutes_ago=40)
        store = _store(prior)

        result = _start(store=store, reader=_StubReader([_human("old", 40), _bot("ALARM again", 5)]))

        assert result.data is not None and result.data.kind is StatusUpdateOutcomeKind.MANUAL
        update = result.data.update
        assert (update.sequence, update.en, update.fr, update.origin) == (2, prior.en, prior.fr, StatusUpdateOrigin.HAND)

    def test_without_people_after_an_approved_update_the_provenance_is_the_approved_one(self) -> None:
        """Bot posts are not what anyone read, so the new draft keeps the approved update's cutoff and fingerprint."""
        prior = _record(1, StatusUpdateState.APPROVED, cutoff_minutes_ago=40)

        result = _start(store=_store(prior), reader=_StubReader([_bot("ALARM again", 5)]))

        assert result.data is not None
        update = result.data.update
        assert (update.transcript_cutoff, update.transcript_fingerprint) == (
            prior.transcript_cutoff,
            prior.transcript_fingerprint,
        )

    def test_a_resolved_prefill_has_no_next_update_beyond_its_creation(self) -> None:
        """Resolved means no further update is due, so the next update time is the creation time."""
        prior = _record(1, StatusUpdateState.APPROVED, stage=StatusUpdateStage.RESOLVED, cutoff_minutes_ago=40)

        result = _start(store=_store(prior), reader=_StubReader([_human("all clear", 5)]))

        assert result.data is not None
        assert (result.data.update.stage, result.data.update.next_update_at) == (StatusUpdateStage.RESOLVED, _NOW)

    def test_no_update_and_no_human_message_refuses_with_empty_history(self) -> None:
        """A first draft needs a person's message to date it from; nothing is stored."""
        store = InMemoryStatusUpdateStore()

        result = _start(store=store, reader=_StubReader([_bot("ALARM", 5)]))

        assert (result.status, result.error_code) == (OperationStatus.PERMANENT_ERROR, ErrorCode.EMPTY_HISTORY)
        assert _stored(store) == ()


class TestPendingDraft:
    def test_a_pending_draft_is_returned_as_is_without_reading_the_conversation(self) -> None:
        """Another responder already started: their draft is opened for editing and nothing is read or stored."""
        pending = _record(2, StatusUpdateState.DRAFT, cutoff_minutes_ago=20)
        store = _store(_record(1, StatusUpdateState.APPROVED, cutoff_minutes_ago=60), pending)
        reader = _StubReader([_human("new fact", 5)])

        result = _start(store=store, reader=reader)

        assert result.data == StatusUpdateDraftOutcome(update=pending, kind=StatusUpdateOutcomeKind.PENDING)
        assert reader.reads == []
        assert len(_stored(store)) == 2


class TestWindow:
    def test_the_first_update_reads_from_the_conversation_start_without_own_or_system_posts(self) -> None:
        """With no approved update the window opens when the conversation did, capped at the history limit."""
        reader = _StubReader([_human("hello", 5)], started_at=_at(600))

        _start(reader=reader)

        assert reader.reads == [{"conversation_id": _CHANNEL, "since": _at(600), "limit": 1000, "exclude": True}]

    def test_an_unknown_conversation_start_falls_back_to_the_default_window(self) -> None:
        """When the platform cannot say when the conversation started, the last 24 hours are read."""
        reader = _StubReader([_human("hello", 5)], started_at=None)

        _start(reader=reader)

        assert reader.reads[0]["since"] == _NOW - timedelta(hours=24)

    def test_the_window_opens_at_the_latest_approved_cutoff(self) -> None:
        """The draft is dated from what people posted since the public last heard from the incident."""
        reader = _StubReader([_human("new", 5)])

        _start(store=_store(_record(1, StatusUpdateState.APPROVED, cutoff_minutes_ago=90)), reader=reader)

        assert reader.reads[0]["since"] == _at(90)

    def test_the_fingerprint_follows_the_human_messages_read(self) -> None:
        """Same human messages give the same fingerprint; different ones give a different fingerprint."""
        first = _start(reader=_StubReader([_human("a", 20)]))
        same = _start(reader=_StubReader([_human("a", 20), _bot("noise", 15)]))
        other = _start(reader=_StubReader([_human("b", 20)]))

        assert first.data and same.data and other.data
        assert first.data.update.transcript_fingerprint == same.data.update.transcript_fingerprint
        assert first.data.update.transcript_fingerprint != other.data.update.transcript_fingerprint


class TestConcurrentStarts:
    def test_a_draft_that_wins_the_sequence_is_returned_as_pending(self) -> None:
        """Two responders starting at once open the same draft rather than an error."""
        store = _RacingStore(StatusUpdateState.DRAFT)

        result = _start(store=store, reader=_StubReader([_human("hi", 5)]))

        assert result.is_success and result.data is not None
        assert result.data == StatusUpdateDraftOutcome(update=store.winner, kind=StatusUpdateOutcomeKind.PENDING)  # type: ignore[arg-type]
        assert _stored(store) == (store.winner,)

    def test_any_other_conflict_is_refused(self) -> None:
        """When the winning record is no longer a draft there is nothing pending to open, so the conflict is reported."""
        store = _RacingStore(StatusUpdateState.APPROVED)

        result = _start(store=store, reader=_StubReader([_human("hi", 5)]))

        assert (result.status, result.error_code) == (OperationStatus.PERMANENT_ERROR, ErrorCode.STATUS_UPDATE_CONFLICT)


class TestFailures:
    @pytest.mark.parametrize(
        "refusal",
        [
            OperationResult.error(OperationStatus.NOT_FOUND, message="no incident", error_code=ErrorCode.NOT_AN_INCIDENT),
            OperationResult.permanent_error(message="two incidents", error_code=ErrorCode.AMBIGUOUS_INCIDENT_CONVERSATION),
        ],
        ids=["not-an-incident", "ambiguous"],
    )
    def test_a_lookup_refusal_passes_through_before_anything_is_read(self, refusal: OperationResult[str]) -> None:
        """Outside an incident nothing is read or stored."""
        store = InMemoryStatusUpdateStore()
        reader = _StubReader([_human("hi", 5)])

        result = _start(store=store, reader=reader, lookup=_StubLookup(refusal))

        assert (result.status, result.error_code) == (refusal.status, refusal.error_code)
        assert reader.reads == [] and _stored(store) == ()

    def test_a_store_read_failure_passes_through_before_the_transcript_is_read(self) -> None:
        """Without the prior updates nothing can be decided, so the store's error is returned."""
        reader = _StubReader([_human("hi", 5)])

        result = _start(store=_FailingListStore(), reader=reader)

        assert (result.status, result.retry_after) == (OperationStatus.TRANSIENT_ERROR, 3)
        assert reader.reads == []


class TestLogging:
    def test_a_full_history_page_is_logged_as_possibly_truncated(self) -> None:
        """Reading exactly the history limit may have cut off older messages, which is surfaced, not hidden."""
        messages = [_human(f"m{i}", 500 - i // 10) for i in range(1000)]

        with capture_logs() as logs:
            _start(reader=_StubReader(messages))

        assert any(entry["event"] == "incident_status_update_history_truncated" for entry in logs)

    def test_logs_name_the_outcome_and_never_carry_transcript_text(self) -> None:
        """Logs identify the incident, sequence and outcome; conversation content stays out of them."""
        with capture_logs() as logs:
            _start(reader=_StubReader([_human("customer SIN 123-456-789", 5)]))

        started = [entry for entry in logs if entry["event"] == "incident_status_update_manual"]
        assert started and started[0]["incident_id"] == _INCIDENT and started[0]["sequence"] == 1
        assert started[0]["operation"] == "start_status_update_draft"
        assert all("123-456-789" not in str(entry) for entry in logs)
