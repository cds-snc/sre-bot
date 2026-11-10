"""Tests for starting an incident status update by hand in the comms service.

The service runs against the in-memory status-update store, an in-memory
incident store holding the incident on the channel, and a stub transcript
reader, with a fixed ``now``, so each test controls exactly which records exist
and which messages are read, and asserts what was stored. The reader records the
conversation reference it was given (the record's) and can return a classified
failure, which the service reads as an empty window. Starting takes no text
generator and never reads the security flag, so no model call or security read
can happen.
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
from features.incident.comms.service.draft import start_status_update_draft
from features.incident.core.adapters.in_memory import InMemoryIncidentStore, InMemoryStatusUpdateStore
from features.incident.core.api import (
    ConversationReference,
    StatusUpdate,
    StatusUpdateOrigin,
    StatusUpdateStage,
    StatusUpdateState,
    StatusUpdateText,
    TranscriptMessage,
)
from tests.factories.incident import incident_on, incident_store_with, slack_conversation

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


class _StubReader:
    def __init__(
        self,
        messages: Sequence[TranscriptMessage] = (),
        *,
        started_at: datetime | None = _at(600),
        read_fails: bool = False,
        start_fails: bool = False,
    ) -> None:
        self._messages = list(messages)
        self._started_at = started_at
        self._read_fails = read_fails
        self._start_fails = start_fails
        self.reads: list[dict[str, Any]] = []

    def conversation_started_at(self, conversation: ConversationReference) -> OperationResult[datetime | None]:
        if self._start_fails:
            return OperationResult.transient_error(message="ratelimited", error_code="ratelimited")
        return OperationResult.success(self._started_at)

    def read_transcript(
        self,
        conversation: ConversationReference,
        *,
        since: datetime,
        limit: int,
        exclude_own_and_system_messages: bool = False,
    ) -> OperationResult[Sequence[TranscriptMessage]]:
        self.reads.append(
            {"conversation": conversation, "since": since, "limit": limit, "exclude": exclude_own_and_system_messages}
        )
        if self._read_fails:
            return OperationResult.transient_error(message="ratelimited", error_code="ratelimited")
        return OperationResult.success(self._messages)


class _RacingStore(InMemoryStatusUpdateStore):
    """Store where another writer takes the sequence just before our append lands."""

    def __init__(self, winner_state: StatusUpdateState) -> None:
        super().__init__()
        self._winner_state = winner_state
        self.winner: StatusUpdate | None = None

    async def append(self, update: StatusUpdate) -> OperationResult[StatusUpdate]:
        if self.winner is None:
            self.winner = replace(update, author="U-other", state=self._winner_state)
            await super().append(self.winner)
        return await super().append(update)


class _FailingListStore(InMemoryStatusUpdateStore):
    async def list_for_incident(self, incident_id: str) -> OperationResult[Sequence[StatusUpdate]]:
        return OperationResult.transient_error(message="throttled", error_code=ErrorCode.RATE_LIMITED, retry_after=3)


async def _store(*records: StatusUpdate) -> InMemoryStatusUpdateStore:
    store = InMemoryStatusUpdateStore()
    for record in records:
        await store.append(record)
    return store


async def _stored(store: InMemoryStatusUpdateStore) -> tuple[StatusUpdate, ...]:
    result = await store.list_for_incident(_INCIDENT)
    assert result.data is not None
    return tuple(result.data)


async def _start(
    *,
    store: InMemoryStatusUpdateStore | None = None,
    reader: _StubReader | None = None,
    incidents: InMemoryIncidentStore | None = None,
) -> OperationResult[StatusUpdateDraftOutcome]:
    return await start_status_update_draft(
        incidents if incidents is not None else incident_store_with(incident_on(_CHANNEL, _INCIDENT)),
        slack_conversation(_CHANNEL),
        author="U123",
        reader=reader or _StubReader(),
        store=store if store is not None else InMemoryStatusUpdateStore(),
        now=_NOW,
    )


class TestStartByHand:
    async def test_the_approved_update_is_stored_as_a_hand_draft_by_the_responder(self) -> None:
        """Starting copies the latest approved stage and fields into the next draft, written by hand."""
        prior = _record(1, StatusUpdateState.APPROVED, stage=StatusUpdateStage.MONITORING, cutoff_minutes_ago=60)
        store = await _store(prior)

        result = await _start(store=store, reader=_StubReader([_human("still slow", 10)]))

        assert result.is_success and result.data is not None
        assert result.data.kind is StatusUpdateOutcomeKind.MANUAL
        update = result.data.update
        assert (update.sequence, update.state, update.stage) == (2, StatusUpdateState.DRAFT, StatusUpdateStage.MONITORING)
        assert (update.en, update.fr) == (prior.en, prior.fr)
        assert (update.author, update.origin, update.created_at) == ("U123", StatusUpdateOrigin.HAND, _NOW)
        assert update.transcript_cutoff == _at(10)
        assert update.next_update_at == _NOW + timedelta(minutes=30)
        assert (await _stored(store))[0] == update

    async def test_the_first_update_starts_blank_at_investigating(self) -> None:
        """With no approved update to copy, every field is blank and the stage is the first one."""
        result = await _start(reader=_StubReader([_human("seeing 500s", 5)]))

        assert result.data is not None
        update = result.data.update
        assert (update.sequence, update.stage, update.en, update.fr) == (1, StatusUpdateStage.INVESTIGATING, _BLANK, _BLANK)

    async def test_with_nothing_new_the_approved_update_is_still_copied_by_hand(self) -> None:
        """Nothing new is no reason to carry forward: the responder asked to write, so the draft is the approved text, by hand."""
        prior = _record(1, StatusUpdateState.APPROVED, cutoff_minutes_ago=40)
        store = await _store(prior)

        result = await _start(store=store, reader=_StubReader([_human("old", 40), _bot("ALARM again", 5)]))

        assert result.data is not None and result.data.kind is StatusUpdateOutcomeKind.MANUAL
        update = result.data.update
        assert (update.sequence, update.en, update.fr, update.origin) == (2, prior.en, prior.fr, StatusUpdateOrigin.HAND)

    async def test_without_people_after_an_approved_update_the_provenance_is_the_approved_one(self) -> None:
        """Bot posts are not what anyone read, so the new draft keeps the approved update's cutoff and fingerprint."""
        prior = _record(1, StatusUpdateState.APPROVED, cutoff_minutes_ago=40)

        result = await _start(store=await _store(prior), reader=_StubReader([_bot("ALARM again", 5)]))

        assert result.data is not None
        update = result.data.update
        assert (update.transcript_cutoff, update.transcript_fingerprint) == (
            prior.transcript_cutoff,
            prior.transcript_fingerprint,
        )

    async def test_a_resolved_prefill_has_no_next_update_beyond_its_creation(self) -> None:
        """Resolved means no further update is due, so the next update time is the creation time."""
        prior = _record(1, StatusUpdateState.APPROVED, stage=StatusUpdateStage.RESOLVED, cutoff_minutes_ago=40)

        result = await _start(store=await _store(prior), reader=_StubReader([_human("all clear", 5)]))

        assert result.data is not None
        assert (result.data.update.stage, result.data.update.next_update_at) == (StatusUpdateStage.RESOLVED, _NOW)

    async def test_no_update_and_no_human_message_refuses_with_empty_history(self) -> None:
        """A first draft needs a person's message to date it from; nothing is stored."""
        store = InMemoryStatusUpdateStore()

        result = await _start(store=store, reader=_StubReader([_bot("ALARM", 5)]))

        assert (result.status, result.error_code) == (OperationStatus.PERMANENT_ERROR, ErrorCode.EMPTY_HISTORY)
        assert await _stored(store) == ()


class TestPendingDraft:
    async def test_a_pending_draft_is_returned_as_is_without_reading_the_conversation(self) -> None:
        """Another responder already started: their draft is opened for editing and nothing is read or stored."""
        pending = _record(2, StatusUpdateState.DRAFT, cutoff_minutes_ago=20)
        store = await _store(_record(1, StatusUpdateState.APPROVED, cutoff_minutes_ago=60), pending)
        reader = _StubReader([_human("new fact", 5)])

        result = await _start(store=store, reader=reader)

        assert result.data == StatusUpdateDraftOutcome(update=pending, kind=StatusUpdateOutcomeKind.PENDING)
        assert reader.reads == []
        assert len(await _stored(store)) == 2


class TestWindow:
    async def test_the_first_update_reads_from_the_conversation_start_without_own_or_system_posts(self) -> None:
        """With no approved update the window opens when the conversation did, capped at the history limit."""
        reader = _StubReader([_human("hello", 5)], started_at=_at(600))

        await _start(reader=reader)

        assert reader.reads == [{"conversation": slack_conversation(_CHANNEL), "since": _at(600), "limit": 1000, "exclude": True}]

    async def test_the_records_conversation_is_read(self) -> None:
        """The conversation read is the incident record's reference (its stored link tells it from the command's)."""
        recorded = replace(slack_conversation(_CHANNEL), url="https://example.slack.com/archives/C0INCIDENT")
        reader = _StubReader([_human("hello", 5)])

        await _start(
            reader=reader, incidents=incident_store_with(replace(incident_on(_CHANNEL, _INCIDENT), conversation=recorded))
        )

        assert reader.reads[0]["conversation"] == recorded

    async def test_a_failed_start_lookup_falls_back_to_the_default_window(self) -> None:
        """A classified failure of the start lookup is treated like an unknown start."""
        reader = _StubReader([_human("hello", 5)], start_fails=True)

        await _start(reader=reader)

        assert reader.reads[0]["since"] == _NOW - timedelta(hours=24)

    async def test_a_failed_read_is_an_empty_window(self) -> None:
        """A classified read failure keeps today's outcome: no conversation from people to date the update from."""
        result = await _start(reader=_StubReader(read_fails=True))

        assert result.status is OperationStatus.PERMANENT_ERROR
        assert result.error_code == ErrorCode.EMPTY_HISTORY

    async def test_an_unknown_conversation_start_falls_back_to_the_default_window(self) -> None:
        """When the platform cannot say when the conversation started, the last 24 hours are read."""
        reader = _StubReader([_human("hello", 5)], started_at=None)

        await _start(reader=reader)

        assert reader.reads[0]["since"] == _NOW - timedelta(hours=24)

    async def test_the_window_opens_at_the_latest_approved_cutoff(self) -> None:
        """The draft is dated from what people posted since the public last heard from the incident."""
        reader = _StubReader([_human("new", 5)])

        await _start(store=await _store(_record(1, StatusUpdateState.APPROVED, cutoff_minutes_ago=90)), reader=reader)

        assert reader.reads[0]["since"] == _at(90)

    async def test_the_fingerprint_follows_the_human_messages_read(self) -> None:
        """Same human messages give the same fingerprint; different ones give a different fingerprint."""
        first = await _start(reader=_StubReader([_human("a", 20)]))
        same = await _start(reader=_StubReader([_human("a", 20), _bot("noise", 15)]))
        other = await _start(reader=_StubReader([_human("b", 20)]))

        assert first.data and same.data and other.data
        assert first.data.update.transcript_fingerprint == same.data.update.transcript_fingerprint
        assert first.data.update.transcript_fingerprint != other.data.update.transcript_fingerprint


class TestConcurrentStarts:
    async def test_a_draft_that_wins_the_sequence_is_returned_as_pending(self) -> None:
        """Two responders starting at once open the same draft rather than an error."""
        store = _RacingStore(StatusUpdateState.DRAFT)

        result = await _start(store=store, reader=_StubReader([_human("hi", 5)]))

        assert result.is_success and result.data is not None
        assert result.data == StatusUpdateDraftOutcome(update=store.winner, kind=StatusUpdateOutcomeKind.PENDING)  # type: ignore[arg-type]
        assert await _stored(store) == (store.winner,)

    async def test_any_other_conflict_is_refused(self) -> None:
        """When the winning record is no longer a draft there is nothing pending to open, so the conflict is reported."""
        store = _RacingStore(StatusUpdateState.APPROVED)

        result = await _start(store=store, reader=_StubReader([_human("hi", 5)]))

        assert (result.status, result.error_code) == (OperationStatus.PERMANENT_ERROR, ErrorCode.STATUS_UPDATE_CONFLICT)


class TestFailures:
    @pytest.mark.parametrize(
        ("incidents", "refusal"),
        [
            (incident_store_with(), (OperationStatus.NOT_FOUND, ErrorCode.NOT_AN_INCIDENT)),
            (
                incident_store_with(incident_on(_CHANNEL, _INCIDENT), incident_on(_CHANNEL, "inc-uuid-2")),
                (OperationStatus.PERMANENT_ERROR, ErrorCode.AMBIGUOUS_INCIDENT_CONVERSATION),
            ),
        ],
        ids=["not-an-incident", "ambiguous"],
    )
    async def test_an_incident_refusal_passes_through_before_anything_is_read(
        self, incidents: InMemoryIncidentStore, refusal: tuple[OperationStatus, ErrorCode]
    ) -> None:
        """Outside an incident, or with two incidents on the channel, nothing is read or stored."""
        store = InMemoryStatusUpdateStore()
        reader = _StubReader([_human("hi", 5)])

        result = await _start(store=store, reader=reader, incidents=incidents)

        assert (result.status, result.error_code) == refusal
        assert reader.reads == [] and await _stored(store) == ()

    async def test_a_store_read_failure_passes_through_before_the_transcript_is_read(self) -> None:
        """Without the prior updates nothing can be decided, so the store's error is returned."""
        reader = _StubReader([_human("hi", 5)])

        result = await _start(store=_FailingListStore(), reader=reader)

        assert (result.status, result.retry_after) == (OperationStatus.TRANSIENT_ERROR, 3)
        assert reader.reads == []


class TestLogging:
    async def test_a_full_history_page_is_logged_as_possibly_truncated(self) -> None:
        """Reading exactly the history limit may have cut off older messages, which is surfaced, not hidden."""
        messages = [_human(f"m{i}", 500 - i // 10) for i in range(1000)]

        with capture_logs() as logs:
            await _start(reader=_StubReader(messages))

        assert any(entry["event"] == "incident_status_update_history_truncated" for entry in logs)

    async def test_logs_name_the_outcome_and_never_carry_transcript_text(self) -> None:
        """Logs identify the incident, sequence and outcome; conversation content stays out of them."""
        with capture_logs() as logs:
            await _start(reader=_StubReader([_human("customer SIN 123-456-789", 5)]))

        started = [entry for entry in logs if entry["event"] == "incident_status_update_manual"]
        assert started and started[0]["incident_id"] == _INCIDENT and started[0]["sequence"] == 1
        assert started[0]["operation"] == "start_status_update_draft"
        assert all("123-456-789" not in str(entry) for entry in logs)
