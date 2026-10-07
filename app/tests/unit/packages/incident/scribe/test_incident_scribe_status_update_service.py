"""Tests for drafting an incident status update in the scribe service.

The service runs against the in-memory status-update store and stubs for the
incident lookup, the transcript reader and the text generator, with a fixed
``now``, so each test controls exactly which records exist, which messages are
read and what the model answers, and asserts what was stored and whether the
model was called.
"""

import json
from collections.abc import Sequence
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from structlog.testing import capture_logs

from contracts.operations import OperationResult, OperationStatus
from contracts.operations.codes import ErrorCode
from packages.incident.core.adapters.in_memory import InMemoryStatusUpdateStore
from packages.incident.core.api import (
    IncidentSecurityFlag,
    StatusUpdate,
    StatusUpdateStage,
    StatusUpdateState,
    StatusUpdateText,
    TranscriptMessage,
)
from packages.incident.scribe.domain import NoNewInformationWording, StatusUpdateDraftOutcome, StatusUpdateOutcomeKind
from packages.incident.scribe.status_update import DRAFT_UNPARSEABLE_CODE, draft_status_update

pytestmark = pytest.mark.unit

_NOW = datetime(2026, 10, 7, 15, 0, tzinfo=UTC)
_INCIDENT = "inc-uuid-1"
_CHANNEL = "C123"
_WORDING = NoNewInformationWording(en="No new information.", fr="Aucune nouvelle information.")
_FIELDS = ("affected_service", "impact", "current_action", "workaround")


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


def _model_answer(stage: str = "identified") -> str:
    answer: dict[str, str] = {"stage": stage}
    for language in ("en", "fr"):
        for field in _FIELDS:
            answer[f"{language}_{field}"] = f"{language} {field} drafted"
    return json.dumps(answer)


class _StubLookup:
    def __init__(self, result: OperationResult[str] | None = None) -> None:
        self._result = result or OperationResult.success(data=_INCIDENT)
        self.calls: list[str] = []

    def find_incident_for_conversation(self, conversation_id: str) -> OperationResult[str]:
        self.calls.append(conversation_id)
        return self._result


class _StubSecurityReader:
    def __init__(self, flag: IncidentSecurityFlag = IncidentSecurityFlag.NO) -> None:
        self._flag = flag

    def read_security_flag(self, incident_id: str) -> OperationResult[IncidentSecurityFlag]:
        return OperationResult.success(data=self._flag)


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


class _StubGenerator:
    def __init__(self, result: OperationResult[str] | None = None) -> None:
        self._result = result or OperationResult.success(data=_model_answer())
        self.calls: list[dict[str, Any]] = []

    async def summarize(
        self,
        transcript: str,
        *,
        instructions: str | None = None,
        max_output_tokens: int | None = None,
    ) -> OperationResult[str]:
        self.calls.append({"transcript": transcript, "instructions": instructions, "max_output_tokens": max_output_tokens})
        return self._result


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


async def _draft(
    *,
    store: InMemoryStatusUpdateStore | None = None,
    reader: _StubReader | None = None,
    generator: _StubGenerator | None = None,
    lookup: _StubLookup | None = None,
    on_started: Any = None,
    security_reader: Any = None,
    security_confirmed: bool = False,
) -> OperationResult[StatusUpdateDraftOutcome]:
    return await draft_status_update(
        _CHANNEL,
        author="U123",
        wording=_WORDING,
        on_started=on_started,
        lookup=lookup or _StubLookup(),
        reader=reader or _StubReader(),
        store=store if store is not None else InMemoryStatusUpdateStore(),
        generator=generator or _StubGenerator(),
        security_reader=security_reader or _StubSecurityReader(),
        security_confirmed=security_confirmed,
        now=_NOW,
    )


class TestDraftFromNewActivity:
    @pytest.mark.asyncio
    async def test_new_human_activity_makes_one_model_call_and_stores_a_complete_draft(self) -> None:
        """With no prior update, the conversation is drafted once and kept as draft #1 with its provenance."""
        store = InMemoryStatusUpdateStore()
        reader = _StubReader([_human("seeing 500s", 20), _human("rolled back", 10, author="Bob")])
        generator = _StubGenerator()

        result = await _draft(store=store, reader=reader, generator=generator)

        assert result.is_success and result.data is not None
        assert result.data.kind is StatusUpdateOutcomeKind.DRAFTED
        update = result.data.update
        assert len(generator.calls) == 1
        assert (update.incident_id, update.sequence, update.state) == (_INCIDENT, 1, StatusUpdateState.DRAFT)
        assert update.stage is StatusUpdateStage.IDENTIFIED
        assert update.en == StatusUpdateText(**{field: f"en {field} drafted" for field in _FIELDS})
        assert update.fr == StatusUpdateText(**{field: f"fr {field} drafted" for field in _FIELDS})
        assert update.author == "U123"
        assert update.transcript_cutoff == _at(10)
        assert update.transcript_fingerprint.startswith("v1:sha256:")
        assert update.created_at == _NOW
        assert update.next_update_at == _NOW + timedelta(minutes=30)
        assert _stored(store) == (update,)

    @pytest.mark.asyncio
    async def test_the_model_gets_the_whole_window_with_bot_context_the_prompt_and_the_token_cap(self) -> None:
        """Bot posts are context for the model even though they never count as new activity."""
        reader = _StubReader([_bot("ALARM: 5xx", 30), _human("on it", 20)])
        generator = _StubGenerator()

        await _draft(reader=reader, generator=generator)

        call = generator.calls[0]
        assert call["transcript"] == "Alertmanager: ALARM: 5xx\nAda: on it"
        assert call["instructions"] and "en_affected_service" in call["instructions"]
        assert call["max_output_tokens"] == 2000

    @pytest.mark.asyncio
    async def test_the_fingerprint_follows_the_human_messages_read(self) -> None:
        """Same human messages give the same fingerprint; different ones give a different fingerprint."""
        first = await _draft(reader=_StubReader([_human("a", 20)]))
        same = await _draft(reader=_StubReader([_human("a", 20), _bot("noise", 15)]))
        other = await _draft(reader=_StubReader([_human("b", 20)]))

        assert first.data and same.data and other.data
        assert first.data.update.transcript_fingerprint == same.data.update.transcript_fingerprint
        assert first.data.update.transcript_fingerprint != other.data.update.transcript_fingerprint

    @pytest.mark.asyncio
    async def test_the_first_update_reads_from_the_conversation_start_without_own_or_system_posts(self) -> None:
        """With no approved update the window opens when the conversation did, capped at the history limit."""
        reader = _StubReader([_human("hello", 5)], started_at=_at(600))

        await _draft(reader=reader)

        assert reader.reads == [{"conversation_id": _CHANNEL, "since": _at(600), "limit": 1000, "exclude": True}]

    @pytest.mark.asyncio
    async def test_an_unknown_conversation_start_falls_back_to_the_default_window(self) -> None:
        """When the platform cannot say when the conversation started, the last 24 hours are read."""
        reader = _StubReader([_human("hello", 5)], started_at=None)

        await _draft(reader=reader)

        assert reader.reads[0]["since"] == _NOW - timedelta(hours=24)

    @pytest.mark.asyncio
    async def test_the_window_opens_at_the_latest_approved_cutoff_so_a_pending_draft_is_recovered(self) -> None:
        """A newer draft that was never approved does not narrow what the model reads."""
        store = _store(
            _record(1, StatusUpdateState.APPROVED, cutoff_minutes_ago=90),
            _record(2, StatusUpdateState.DRAFT, cutoff_minutes_ago=40),
        )
        reader = _StubReader([_human("new", 5)])

        result = await _draft(store=store, reader=reader)

        assert reader.reads[0]["since"] == _at(90)
        assert result.data is not None and result.data.update.sequence == 3

    @pytest.mark.asyncio
    async def test_on_started_is_called_once_just_before_the_model_call(self) -> None:
        """The caller can tell the responder drafting has begun only when a model call follows."""
        events: list[str] = []
        generator = _StubGenerator()
        original = generator.summarize

        async def recording_summarize(transcript: str, **kwargs: Any) -> OperationResult[str]:
            events.append("model")
            return await original(transcript, **kwargs)

        generator.summarize = recording_summarize  # type: ignore[method-assign]

        await _draft(reader=_StubReader([_human("hi", 5)]), generator=generator, on_started=lambda: events.append("started"))

        assert events == ["started", "model"]

    @pytest.mark.asyncio
    async def test_a_resolved_draft_has_no_next_update_beyond_its_creation(self) -> None:
        """Resolved means no further update is due, so the next update time is the creation time."""
        result = await _draft(
            reader=_StubReader([_human("all clear", 5)]),
            generator=_StubGenerator(OperationResult.success(data=_model_answer("resolved"))),
        )

        assert result.data is not None
        assert result.data.update.stage is StatusUpdateStage.RESOLVED
        assert result.data.update.next_update_at == _NOW


class TestNothingNew:
    @pytest.mark.asyncio
    async def test_no_new_human_message_carries_the_approved_update_forward_without_a_model_call(self) -> None:
        """Code decides nothing is new: the prior fields stay and the current action says there is no new information."""
        prior = _record(1, StatusUpdateState.APPROVED, stage=StatusUpdateStage.MONITORING, cutoff_minutes_ago=40)
        store = _store(prior)
        generator = _StubGenerator()
        started: list[str] = []

        result = await _draft(
            store=store,
            reader=_StubReader([_human("old", 40)]),
            generator=generator,
            on_started=lambda: started.append("x"),
        )

        assert result.is_success and result.data is not None
        assert result.data.kind is StatusUpdateOutcomeKind.CARRIED_FORWARD
        update = result.data.update
        assert generator.calls == [] and started == []
        assert (update.sequence, update.state, update.stage) == (2, StatusUpdateState.DRAFT, StatusUpdateStage.MONITORING)
        assert update.en == replace(prior.en, current_action=_WORDING.en)
        assert update.fr == replace(prior.fr, current_action=_WORDING.fr)
        assert update.next_update_at == _NOW + timedelta(minutes=30)
        assert (update.transcript_cutoff, update.transcript_fingerprint) == (
            prior.transcript_cutoff,
            prior.transcript_fingerprint,
        )
        assert (update.author, update.created_at) == ("U123", _NOW)
        assert _stored(store)[0] == update

    @pytest.mark.asyncio
    async def test_a_message_exactly_at_the_cutoff_is_not_new(self) -> None:
        """The cutoff message was already read by the prior update."""
        store = _store(_record(1, StatusUpdateState.PUBLISHED, cutoff_minutes_ago=30))
        generator = _StubGenerator()

        result = await _draft(store=store, reader=_StubReader([_human("same", 30)]), generator=generator)

        assert result.data is not None and result.data.kind is StatusUpdateOutcomeKind.CARRIED_FORWARD
        assert generator.calls == []

    @pytest.mark.asyncio
    async def test_bot_posts_after_the_cutoff_are_not_new_activity(self) -> None:
        """Only people moving the incident forward justify a new draft; alerts repeating do not."""
        store = _store(_record(1, StatusUpdateState.APPROVED, cutoff_minutes_ago=30))
        generator = _StubGenerator()

        result = await _draft(store=store, reader=_StubReader([_bot("ALARM again", 5)]), generator=generator)

        assert result.data is not None and result.data.kind is StatusUpdateOutcomeKind.CARRIED_FORWARD
        assert generator.calls == []

    @pytest.mark.asyncio
    async def test_running_twice_with_nothing_new_returns_the_same_pending_draft_and_stores_nothing(self) -> None:
        """A pending draft is returned as is, so repeated runs neither call the model nor add records."""
        pending = _record(2, StatusUpdateState.DRAFT, cutoff_minutes_ago=20)
        store = _store(_record(1, StatusUpdateState.APPROVED, cutoff_minutes_ago=60), pending)
        generator = _StubGenerator()
        reader = _StubReader([_human("covered", 20)])

        first = await _draft(store=store, reader=reader, generator=generator)
        second = await _draft(store=store, reader=reader, generator=generator)

        for result in (first, second):
            assert result.data == StatusUpdateDraftOutcome(update=pending, kind=StatusUpdateOutcomeKind.PENDING)
        assert generator.calls == []
        assert len(_stored(store)) == 2

    @pytest.mark.asyncio
    async def test_new_activity_after_a_pending_draft_drafts_again_at_the_next_sequence(self) -> None:
        """The store cannot replace a draft, so fresher activity becomes the next draft."""
        store = _store(_record(1, StatusUpdateState.DRAFT, cutoff_minutes_ago=30))
        generator = _StubGenerator()

        result = await _draft(store=store, reader=_StubReader([_human("new fact", 5)]), generator=generator)

        assert result.data is not None
        assert (result.data.kind, result.data.update.sequence) == (StatusUpdateOutcomeKind.DRAFTED, 2)
        assert len(generator.calls) == 1

    @pytest.mark.asyncio
    async def test_no_update_and_no_human_message_refuses_with_empty_history(self) -> None:
        """There is nothing to draft from and nothing to carry forward."""
        store = InMemoryStatusUpdateStore()
        generator = _StubGenerator()

        result = await _draft(store=store, reader=_StubReader([_bot("ALARM", 5)]), generator=generator)

        assert (result.status, result.error_code) == (OperationStatus.PERMANENT_ERROR, ErrorCode.EMPTY_HISTORY)
        assert generator.calls == [] and _stored(store) == ()


class TestStageFloor:
    @pytest.mark.parametrize(
        ("approved", "drafted", "expected"),
        [
            (StatusUpdateStage.MONITORING, "identified", StatusUpdateStage.MONITORING),
            (StatusUpdateStage.MONITORING, "monitoring", StatusUpdateStage.MONITORING),
            (StatusUpdateStage.IDENTIFIED, "monitoring", StatusUpdateStage.MONITORING),
        ],
        ids=["earlier-is-raised", "equal-stays", "later-stays"],
    )
    @pytest.mark.asyncio
    async def test_a_drafted_stage_never_goes_behind_the_latest_approved_stage(
        self, approved: StatusUpdateStage, drafted: str, expected: StatusUpdateStage
    ) -> None:
        """Stages only move forward for the public."""
        store = _store(_record(1, StatusUpdateState.APPROVED, stage=approved, cutoff_minutes_ago=30))

        result = await _draft(
            store=store,
            reader=_StubReader([_human("update", 5)]),
            generator=_StubGenerator(OperationResult.success(data=_model_answer(drafted))),
        )

        assert result.data is not None and result.data.update.stage is expected

    @pytest.mark.asyncio
    async def test_an_unapproved_draft_does_not_set_the_floor(self) -> None:
        """Only what the public saw constrains the stage; a pending draft's stage was never approved."""
        store = _store(
            _record(1, StatusUpdateState.APPROVED, stage=StatusUpdateStage.INVESTIGATING, cutoff_minutes_ago=60),
            _record(2, StatusUpdateState.DRAFT, stage=StatusUpdateStage.RESOLVED, cutoff_minutes_ago=30),
        )

        result = await _draft(store=store, reader=_StubReader([_human("not fixed after all", 5)]))

        assert result.data is not None and result.data.update.stage is StatusUpdateStage.IDENTIFIED


class TestConcurrentDrafts:
    @pytest.mark.asyncio
    async def test_a_draft_that_wins_the_sequence_is_returned_as_pending(self) -> None:
        """Two responders drafting at once see the same draft rather than an error."""
        store = _RacingStore(StatusUpdateState.DRAFT)

        result = await _draft(store=store, reader=_StubReader([_human("hi", 5)]))

        assert result.is_success and result.data is not None
        assert result.data == StatusUpdateDraftOutcome(update=store.winner, kind=StatusUpdateOutcomeKind.PENDING)  # type: ignore[arg-type]
        assert _stored(store) == (store.winner,)

    @pytest.mark.asyncio
    async def test_any_other_conflict_is_refused(self) -> None:
        """When the winning record is no longer a draft there is nothing pending to show, so the conflict is reported."""
        store = _RacingStore(StatusUpdateState.APPROVED)

        result = await _draft(store=store, reader=_StubReader([_human("hi", 5)]))

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
    @pytest.mark.asyncio
    async def test_a_lookup_refusal_passes_through_before_anything_is_read(self, refusal: OperationResult[str]) -> None:
        """Outside an incident nothing is read, drafted or stored."""
        store = InMemoryStatusUpdateStore()
        reader = _StubReader([_human("hi", 5)])
        generator = _StubGenerator()

        result = await _draft(store=store, reader=reader, generator=generator, lookup=_StubLookup(refusal))

        assert (result.status, result.error_code) == (refusal.status, refusal.error_code)
        assert reader.reads == [] and generator.calls == [] and _stored(store) == ()

    @pytest.mark.asyncio
    async def test_a_model_failure_passes_through_and_stores_nothing(self) -> None:
        """The generator's classified error, retry hint included, reaches the caller."""
        store = InMemoryStatusUpdateStore()
        failure: OperationResult[str] = OperationResult.transient_error(
            message="rate limited", error_code="RATE_LIMITED", retry_after=7
        )

        result = await _draft(store=store, reader=_StubReader([_human("hi", 5)]), generator=_StubGenerator(failure))

        assert (result.status, result.error_code, result.retry_after) == (OperationStatus.TRANSIENT_ERROR, "RATE_LIMITED", 7)
        assert _stored(store) == ()

    @pytest.mark.asyncio
    async def test_unparseable_model_output_is_refused_and_stores_nothing(self) -> None:
        """A partial or malformed answer never becomes a draft."""
        store = InMemoryStatusUpdateStore()

        result = await _draft(
            store=store,
            reader=_StubReader([_human("hi", 5)]),
            generator=_StubGenerator(OperationResult.success(data='{"stage": "identified"')),
        )

        assert (result.status, result.error_code) == (OperationStatus.PERMANENT_ERROR, DRAFT_UNPARSEABLE_CODE)
        assert _stored(store) == ()

    @pytest.mark.asyncio
    async def test_a_store_read_failure_passes_through_before_the_transcript_is_read(self) -> None:
        """Without the prior updates nothing can be decided, so the store's error is returned."""
        reader = _StubReader([_human("hi", 5)])

        result = await _draft(store=_FailingListStore(), reader=reader)

        assert (result.status, result.retry_after) == (OperationStatus.TRANSIENT_ERROR, 3)
        assert reader.reads == []


class TestLogging:
    @pytest.mark.asyncio
    async def test_a_full_history_page_is_logged_as_possibly_truncated(self) -> None:
        """Reading exactly the history limit may have cut off older messages, which is surfaced, not hidden."""
        messages = [_human(f"m{i}", 500 - i // 10) for i in range(1000)]

        with capture_logs() as logs:
            await _draft(reader=_StubReader(messages))

        assert any(entry["event"] == "incident_status_update_history_truncated" for entry in logs)

    @pytest.mark.asyncio
    async def test_logs_name_the_outcome_and_never_carry_transcript_text(self) -> None:
        """Logs identify the incident, sequence and outcome; conversation content stays out of them."""
        with capture_logs() as logs:
            await _draft(reader=_StubReader([_human("customer SIN 123-456-789", 5)]))

        drafted = [entry for entry in logs if entry["event"] == "incident_status_update_drafted"]
        assert drafted and drafted[0]["incident_id"] == _INCIDENT and drafted[0]["sequence"] == 1
        assert all("123-456-789" not in str(entry) for entry in logs)
