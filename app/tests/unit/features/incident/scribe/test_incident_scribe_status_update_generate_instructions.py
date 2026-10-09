"""Tests for filling a pending status update with AI from a responder's instructions in the scribe service.

``generate_status_update_draft`` is called with non-blank instructions, which
always make one model call with the redraft prompt; the helper returns the
stored draft so assertions read the record directly. The service runs against the in-memory status-update store and stubs for the
incident lookup, the transcript reader, the security flag reader and the text
generator, with a fixed ``now``, so each test controls which records exist,
which messages are read and what the model answers. Assertions compare the
exact model call (instructions, input and token cap), the exact stored records
and the exact result codes, because an instructed fill must make one model
call, add one new draft and leave every earlier record as it was.
"""

import hashlib
import json
from collections.abc import Sequence
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from structlog.testing import capture_logs

from contracts.operations import OperationResult, OperationStatus
from contracts.operations.codes import ErrorCode
from features.incident.core.adapters.in_memory import InMemoryStatusUpdateStore
from features.incident.core.api import (
    IncidentSecurityFlag,
    StatusUpdate,
    StatusUpdateOrigin,
    StatusUpdateStage,
    StatusUpdateState,
    StatusUpdateText,
    TranscriptMessage,
)
from features.incident.scribe.domain import NoNewInformationWording, StatusUpdateEdit, StatusUpdateOutcomeKind
from features.incident.scribe.status_update import DRAFT_UNPARSEABLE_CODE, generate_status_update_draft
from features.incident.scribe.status_update_prompt import build_redraft_input, build_redraft_instructions

pytestmark = pytest.mark.unit

_NOW = datetime(2026, 10, 7, 15, 0, tzinfo=UTC)
_INCIDENT = "inc-uuid-1"
_CHANNEL = "C123"
_REDRAFTER = "U0REDRAFTER"
_GUIDANCE = "do not name the vendor"
_FIELDS = ("affected_service", "impact", "current_action", "workaround")
_WORDING = NoNewInformationWording(en="No new information.", fr="Aucune nouvelle information.")


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
) -> StatusUpdate:
    return StatusUpdate(
        incident_id=_INCIDENT,
        sequence=sequence,
        state=state,
        stage=stage,
        en=_text("en", f" #{sequence}"),
        fr=_text("fr", f" #{sequence}"),
        next_update_at=_at(cutoff_minutes_ago) + timedelta(minutes=30),
        author="U0",
        transcript_cutoff=_at(cutoff_minutes_ago),
        transcript_fingerprint=f"v1:sha256:prior{sequence}",
        created_at=_at(cutoff_minutes_ago),
    )


_APPROVED = _record(1, StatusUpdateState.APPROVED, cutoff_minutes_ago=90)
_PENDING = _record(2, StatusUpdateState.DRAFT, cutoff_minutes_ago=40)
_CURRENT = StatusUpdateEdit(stage=StatusUpdateStage.IDENTIFIED, en=_text("en", " edited"), fr=_text("fr", " edited"))


def _model_answer(stage: str = "identified", **overrides: Any) -> str:
    answer: dict[str, Any] = {"stage": stage}
    for language in ("en", "fr"):
        for field in _FIELDS:
            answer[f"{language}_{field}"] = f"{language} {field} redrafted"
    answer.update(overrides)
    return json.dumps(answer)


def _redrafted_text(language: str) -> StatusUpdateText:
    return StatusUpdateText(**{field: f"{language} {field} redrafted" for field in _FIELDS})


def _fingerprint(*lines: tuple[datetime, str]) -> str:
    """The provenance digest a draft records: each person's message time and text, one per line."""
    content = "\n".join(f"{posted_at.isoformat()}\t{text}" for posted_at, text in lines)
    return f"v1:sha256:{hashlib.sha256(content.encode()).hexdigest()}"


class _StubLookup:
    def __init__(self, result: OperationResult[str] | None = None) -> None:
        self._result = result or OperationResult.success(data=_INCIDENT)
        self.calls: list[str] = []

    def find_incident_for_conversation(self, conversation_id: str) -> OperationResult[str]:
        self.calls.append(conversation_id)
        return self._result


class _StubSecurityReader:
    def __init__(self, result: OperationResult[IncidentSecurityFlag] | None = None) -> None:
        self._result = result or OperationResult.success(data=IncidentSecurityFlag.NO)
        self.calls: list[str] = []

    def read_security_flag(self, incident_id: str) -> OperationResult[IncidentSecurityFlag]:
        self.calls.append(incident_id)
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


class _StubGenerator:
    def __init__(self, result: OperationResult[str] | None = None, events: list[str] | None = None) -> None:
        self._result = result or OperationResult.success(data=_model_answer())
        self._events = events
        self.calls: list[dict[str, Any]] = []

    async def summarize(
        self,
        transcript: str,
        *,
        instructions: str | None = None,
        max_output_tokens: int | None = None,
    ) -> OperationResult[str]:
        if self._events is not None:
            self._events.append("model")
        self.calls.append({"transcript": transcript, "instructions": instructions, "max_output_tokens": max_output_tokens})
        return self._result


class _RacingStore(InMemoryStatusUpdateStore):
    """Store where another writer's draft takes the sequence just before our append lands."""

    def __init__(self) -> None:
        super().__init__()
        self.winner: StatusUpdate | None = None

    def append(self, update: StatusUpdate) -> OperationResult[StatusUpdate]:
        if self.winner is None and update.sequence > _PENDING.sequence:
            self.winner = replace(update, author="U-other", en=_text("en", " other"))
            super().append(self.winner)
        return super().append(update)


class _FailingListStore(InMemoryStatusUpdateStore):
    def list_for_incident(self, incident_id: str) -> OperationResult[Sequence[StatusUpdate]]:
        return OperationResult.transient_error(message="throttled", error_code=ErrorCode.RATE_LIMITED, retry_after=3)


class _FailingAppendStore(InMemoryStatusUpdateStore):
    def append(self, update: StatusUpdate) -> OperationResult[StatusUpdate]:
        if update.sequence > _PENDING.sequence:
            return OperationResult.transient_error(message="throttled", error_code=ErrorCode.RATE_LIMITED, retry_after=5)
        return super().append(update)


def _store[S: InMemoryStatusUpdateStore](store: S, *records: StatusUpdate) -> S:
    for record in records:
        store.append(record)
    return store


def _stored(store: InMemoryStatusUpdateStore) -> tuple[StatusUpdate, ...]:
    result = store.list_for_incident(_INCIDENT)
    assert result.data is not None
    return tuple(result.data)


async def _redraft(
    *,
    store: InMemoryStatusUpdateStore,
    sequence: int = _PENDING.sequence,
    instructions: str = _GUIDANCE,
    current: StatusUpdateEdit = _CURRENT,
    reader: _StubReader | None = None,
    generator: _StubGenerator | None = None,
    lookup: _StubLookup | None = None,
    security_reader: _StubSecurityReader | None = None,
    security_confirmed: bool = False,
    on_started: Any = None,
) -> OperationResult[StatusUpdate]:
    """Fill with instructions and return the stored draft, or the refusal with its classification."""
    result = await generate_status_update_draft(
        _CHANNEL,
        sequence,
        current=current,
        author=_REDRAFTER,
        wording=_WORDING,
        instructions=instructions,
        security_confirmed=security_confirmed,
        on_started=on_started,
        lookup=lookup or _StubLookup(),
        reader=reader or _StubReader(),
        store=store,
        generator=generator or _StubGenerator(),
        security_reader=security_reader or _StubSecurityReader(),
        now=_NOW,
    )
    if result.is_success and result.data is not None:
        assert result.data.kind is StatusUpdateOutcomeKind.DRAFTED
        return OperationResult.success(data=result.data.update)
    return OperationResult.error(
        result.status, message=result.message or "", error_code=result.error_code, retry_after=result.retry_after
    )


class TestRedraft:
    @pytest.mark.asyncio
    async def test_one_model_call_gets_the_guidance_the_current_draft_and_the_whole_window(self) -> None:
        """The model gets the redraft instructions, the reviewer's current values and every message, bots included."""
        store = _store(InMemoryStatusUpdateStore(), _APPROVED, _PENDING)
        reader = _StubReader([_human("rolled back", 50), _bot("RESOLVED: 5xx", 20), _human("vendor confirmed", 10)])
        generator = _StubGenerator()

        await _redraft(store=store, reader=reader, generator=generator)

        assert generator.calls == [
            {
                "transcript": build_redraft_input(
                    _CURRENT, "Ada: rolled back\nAlertmanager: RESOLVED: 5xx\nAda: vendor confirmed"
                ),
                "instructions": build_redraft_instructions(_GUIDANCE),
                "max_output_tokens": 2000,
            }
        ]

    @pytest.mark.asyncio
    async def test_the_redraft_is_stored_as_the_next_draft_authored_by_the_redrafter(self) -> None:
        """The new record is a DRAFT at the next sequence with the model's fields and the people's provenance."""
        store = _store(InMemoryStatusUpdateStore(), _APPROVED, _PENDING)
        reader = _StubReader([_human("rolled back", 50), _bot("RESOLVED: 5xx", 20), _human("vendor confirmed", 10)])

        result = await _redraft(store=store, reader=reader)

        expected = StatusUpdate(
            incident_id=_INCIDENT,
            sequence=3,
            state=StatusUpdateState.DRAFT,
            stage=StatusUpdateStage.IDENTIFIED,
            en=_redrafted_text("en"),
            fr=_redrafted_text("fr"),
            next_update_at=_NOW + timedelta(minutes=30),
            author=_REDRAFTER,
            transcript_cutoff=_at(10),
            transcript_fingerprint=_fingerprint((_at(50), "rolled back"), (_at(10), "vendor confirmed")),
            created_at=_NOW,
            origin=StatusUpdateOrigin.MODEL_INSTRUCTED,
        )
        assert (result.status, result.data) == (OperationStatus.SUCCESS, expected)
        assert _stored(store) == (expected, _PENDING, _APPROVED)

    @pytest.mark.asyncio
    async def test_the_window_is_reread_from_the_latest_approved_cutoff(self) -> None:
        """The pending draft does not narrow the window, so the redraft reads what the first draft read and later messages."""
        store = _store(InMemoryStatusUpdateStore(), _APPROVED, _PENDING)
        reader = _StubReader([_human("later", 5)])

        await _redraft(store=store, reader=reader)

        assert reader.reads == [{"conversation_id": _CHANNEL, "since": _at(90), "limit": 1000, "exclude": True}]

    @pytest.mark.asyncio
    async def test_without_an_approved_update_the_window_opens_at_the_conversation_start(self) -> None:
        """A first draft being redrafted is read from when the conversation started."""
        store = _store(InMemoryStatusUpdateStore(), _record(1, StatusUpdateState.DRAFT, cutoff_minutes_ago=40))
        reader = _StubReader([_human("hello", 50)], started_at=_at(600))

        result = await _redraft(store=store, sequence=1, reader=reader)

        assert reader.reads == [{"conversation_id": _CHANNEL, "since": _at(600), "limit": 1000, "exclude": True}]
        assert result.data is not None
        assert (result.data.sequence, result.data.state) == (2, StatusUpdateState.DRAFT)

    @pytest.mark.asyncio
    async def test_the_guidance_is_trimmed_before_it_reaches_the_model(self) -> None:
        """Surrounding whitespace in the reviewer's guidance is dropped from the instructions."""
        store = _store(InMemoryStatusUpdateStore(), _APPROVED, _PENDING)
        generator = _StubGenerator()

        await _redraft(store=store, instructions=f"  \n{_GUIDANCE} \n", reader=_StubReader([_human("x", 5)]), generator=generator)

        assert [call["instructions"] for call in generator.calls] == [build_redraft_instructions(_GUIDANCE)]

    @pytest.mark.asyncio
    async def test_overlong_guidance_is_capped_before_it_reaches_the_model(self) -> None:
        """Guidance longer than the cap is cut to the first 500 characters."""
        store = _store(InMemoryStatusUpdateStore(), _APPROVED, _PENDING)
        generator = _StubGenerator()

        await _redraft(store=store, instructions="v" * 650, reader=_StubReader([_human("x", 5)]), generator=generator)

        assert [call["instructions"] for call in generator.calls] == [build_redraft_instructions("v" * 500)]

    @pytest.mark.asyncio
    async def test_on_started_is_called_once_just_before_the_model_call(self) -> None:
        """The caller can show the redrafting state only when a model call follows."""
        events: list[str] = []
        store = _store(InMemoryStatusUpdateStore(), _APPROVED, _PENDING)

        await _redraft(
            store=store,
            reader=_StubReader([_human("x", 5)]),
            generator=_StubGenerator(events=events),
            on_started=lambda: events.append("started"),
        )

        assert events == ["started", "model"]

    @pytest.mark.asyncio
    async def test_a_resolved_redraft_has_no_next_update_beyond_its_creation(self) -> None:
        """Resolved means no further update is due, so the next update time is the creation time."""
        store = _store(InMemoryStatusUpdateStore(), _APPROVED, _PENDING)

        result = await _redraft(
            store=store,
            reader=_StubReader([_human("all clear", 5)]),
            generator=_StubGenerator(OperationResult.success(data=_model_answer("resolved"))),
        )

        assert result.data is not None
        assert (result.data.stage, result.data.next_update_at) == (StatusUpdateStage.RESOLVED, _NOW)


class TestNoNewPeople:
    @pytest.mark.parametrize(
        "messages",
        [[], [_bot("ALARM again", 5)]],
        ids=["empty-transcript", "bots-only"],
    )
    @pytest.mark.asyncio
    async def test_a_window_without_people_still_redrafts_and_keeps_the_previous_provenance(
        self, messages: list[TranscriptMessage]
    ) -> None:
        """Instructions alone justify a redraft; with no person's message read, cutoff and fingerprint stay the previous draft's."""
        store = _store(InMemoryStatusUpdateStore(), _APPROVED, _PENDING)
        generator = _StubGenerator()

        result = await _redraft(store=store, reader=_StubReader(messages), generator=generator)

        assert len(generator.calls) == 1
        assert result.data is not None
        assert (result.data.sequence, result.data.state, result.data.author) == (3, StatusUpdateState.DRAFT, _REDRAFTER)
        assert (result.data.transcript_cutoff, result.data.transcript_fingerprint) == (
            _PENDING.transcript_cutoff,
            _PENDING.transcript_fingerprint,
        )
        assert _stored(store) == (result.data, _PENDING, _APPROVED)

    @pytest.mark.asyncio
    async def test_a_carried_forward_draft_is_redrafted_with_an_empty_transcript_input(self) -> None:
        """A draft carried forward with nothing new is still revised: the model gets the draft and an empty transcript."""
        carried = _record(2, StatusUpdateState.DRAFT, cutoff_minutes_ago=90)
        store = _store(InMemoryStatusUpdateStore(), _APPROVED, carried)
        generator = _StubGenerator()

        result = await _redraft(store=store, reader=_StubReader([]), generator=generator)

        assert [call["transcript"] for call in generator.calls] == [build_redraft_input(_CURRENT, "")]
        assert result.data is not None
        assert (result.data.transcript_cutoff, result.data.transcript_fingerprint) == (
            carried.transcript_cutoff,
            carried.transcript_fingerprint,
        )


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
    async def test_a_redrafted_stage_never_goes_behind_the_latest_approved_stage(
        self, approved: StatusUpdateStage, drafted: str, expected: StatusUpdateStage
    ) -> None:
        """Guidance cannot move the public stage backwards: code applies the floor after the model answers."""
        store = _store(
            InMemoryStatusUpdateStore(),
            _record(1, StatusUpdateState.APPROVED, stage=approved, cutoff_minutes_ago=90),
            _PENDING,
        )

        result = await _redraft(
            store=store,
            reader=_StubReader([_human("update", 5)]),
            generator=_StubGenerator(OperationResult.success(data=_model_answer(drafted))),
        )

        assert result.data is not None
        assert result.data.stage is expected

    @pytest.mark.asyncio
    async def test_the_pending_draft_stage_does_not_set_the_floor(self) -> None:
        """Only an approved stage constrains the redraft; the draft being replaced was never public."""
        store = _store(
            InMemoryStatusUpdateStore(),
            _record(1, StatusUpdateState.APPROVED, stage=StatusUpdateStage.INVESTIGATING, cutoff_minutes_ago=90),
            _record(2, StatusUpdateState.DRAFT, stage=StatusUpdateStage.RESOLVED, cutoff_minutes_ago=40),
        )

        result = await _redraft(store=store, reader=_StubReader([_human("not fixed after all", 5)]))

        assert result.data is not None
        assert result.data.stage is StatusUpdateStage.IDENTIFIED


class TestRejectedBeforeAnyWork:
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
        """Outside an incident nothing is read, redrafted or stored."""
        store = _store(InMemoryStatusUpdateStore(), _APPROVED, _PENDING)
        reader = _StubReader([_human("x", 5)])
        generator = _StubGenerator()

        result = await _redraft(store=store, reader=reader, generator=generator, lookup=_StubLookup(refusal))

        assert (result.status, result.error_code) == (refusal.status, refusal.error_code)
        assert (reader.reads, generator.calls) == ([], [])
        assert _stored(store) == (_PENDING, _APPROVED)

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
    @pytest.mark.asyncio
    async def test_a_target_that_is_not_the_latest_draft_is_a_conflict_with_no_read_or_model_call(
        self, records: tuple[StatusUpdate, ...], sequence: int
    ) -> None:
        """Only the pending draft the reviewer sees can be redrafted; anything else changed under them."""
        store = _store(InMemoryStatusUpdateStore(), *records)
        before = _stored(store)
        reader = _StubReader([_human("x", 5)])
        generator = _StubGenerator()

        result = await _redraft(store=store, sequence=sequence, reader=reader, generator=generator)

        assert (result.status, result.error_code) == (OperationStatus.PERMANENT_ERROR, ErrorCode.STATUS_UPDATE_CONFLICT)
        assert (reader.reads, generator.calls) == ([], [])
        assert _stored(store) == before

    @pytest.mark.asyncio
    async def test_a_store_read_failure_passes_through_before_the_transcript_is_read(self) -> None:
        """Without the incident's records nothing can be checked, so the store's error is returned."""
        reader = _StubReader([_human("x", 5)])
        generator = _StubGenerator()

        result = await _redraft(store=_FailingListStore(), reader=reader, generator=generator)

        assert (result.status, result.error_code, result.retry_after) == (
            OperationStatus.TRANSIENT_ERROR,
            ErrorCode.RATE_LIMITED,
            3,
        )
        assert (reader.reads, generator.calls) == ([], [])


class TestFailuresKeepThePreviousDraft:
    @pytest.mark.asyncio
    async def test_a_model_failure_passes_through_and_stores_nothing(self) -> None:
        """The generator's classified error, retry hint included, reaches the caller; the pending draft stays latest."""
        store = _store(InMemoryStatusUpdateStore(), _APPROVED, _PENDING)
        failure: OperationResult[str] = OperationResult.transient_error(
            message="rate limited", error_code=ErrorCode.RATE_LIMITED, retry_after=7
        )

        result = await _redraft(store=store, reader=_StubReader([_human("x", 5)]), generator=_StubGenerator(failure))

        assert (result.status, result.error_code, result.retry_after) == (
            OperationStatus.TRANSIENT_ERROR,
            ErrorCode.RATE_LIMITED,
            7,
        )
        assert _stored(store) == (_PENDING, _APPROVED)

    @pytest.mark.parametrize(
        "raw",
        [
            _model_answer("degraded"),
            json.dumps({key: value for key, value in json.loads(_model_answer()).items() if key != "fr_workaround"}),
            _model_answer(en_impact="   "),
            '{"stage": "identified"',
            "I would rather not.",
        ],
        ids=["unknown-stage", "missing-key", "blank-field", "truncated", "prose"],
    )
    @pytest.mark.asyncio
    async def test_unparseable_output_is_refused_with_the_strict_parser_and_stores_nothing(self, raw: str) -> None:
        """The redraft is parsed as strictly as the first draft: any bad field rejects the whole answer."""
        store = _store(InMemoryStatusUpdateStore(), _APPROVED, _PENDING)

        result = await _redraft(
            store=store,
            reader=_StubReader([_human("x", 5)]),
            generator=_StubGenerator(OperationResult.success(data=raw)),
        )

        assert (result.status, result.error_code) == (OperationStatus.PERMANENT_ERROR, DRAFT_UNPARSEABLE_CODE)
        assert _stored(store) == (_PENDING, _APPROVED)

    @pytest.mark.asyncio
    async def test_a_store_write_failure_passes_through(self) -> None:
        """A failed append returns the store's classified error and leaves the previous records as they were."""
        store = _store(_FailingAppendStore(), _APPROVED, _PENDING)

        result = await _redraft(store=store, reader=_StubReader([_human("x", 5)]))

        assert (result.status, result.error_code, result.retry_after) == (
            OperationStatus.TRANSIENT_ERROR,
            ErrorCode.RATE_LIMITED,
            5,
        )
        assert _stored(store) == (_PENDING, _APPROVED)

    @pytest.mark.asyncio
    async def test_an_append_conflict_is_returned_without_adopting_the_winner(self) -> None:
        """When another writer took the next sequence, the redraft reports the conflict rather than showing their draft."""
        store = _store(_RacingStore(), _APPROVED, _PENDING)

        result = await _redraft(store=store, reader=_StubReader([_human("x", 5)]))

        assert (result.status, result.error_code, result.data) == (
            OperationStatus.PERMANENT_ERROR,
            ErrorCode.STATUS_UPDATE_CONFLICT,
            None,
        )
        assert _stored(store) == (store.winner, _PENDING, _APPROVED)


class TestSecurityGate:
    @pytest.mark.parametrize(
        "flag_result",
        [
            OperationResult.success(data=IncidentSecurityFlag.YES),
            OperationResult.success(data=IncidentSecurityFlag.UNKNOWN),
            OperationResult.transient_error(message="store error", error_code=ErrorCode.RATE_LIMITED),
        ],
        ids=["yes", "unknown", "unreadable"],
    )
    @pytest.mark.asyncio
    async def test_a_security_unknown_or_unreadable_flag_refuses_before_the_model(
        self, flag_result: OperationResult[IncidentSecurityFlag]
    ) -> None:
        """Without confirmation, a redraft that may expose a security incident never reaches the model or the store."""
        store = _store(InMemoryStatusUpdateStore(), _APPROVED, _PENDING)
        generator = _StubGenerator()
        security_reader = _StubSecurityReader(flag_result)
        started: list[str] = []

        result = await _redraft(
            store=store,
            reader=_StubReader([_human("x", 5)]),
            generator=generator,
            security_reader=security_reader,
            on_started=lambda: started.append("started"),
        )

        assert (result.status, result.error_code) == (
            OperationStatus.PERMANENT_ERROR,
            ErrorCode.SECURITY_CONFIRMATION_REQUIRED,
        )
        assert security_reader.calls == [_INCIDENT]
        assert (generator.calls, started) == ([], [])
        assert _stored(store) == (_PENDING, _APPROVED)

    @pytest.mark.asyncio
    async def test_a_non_security_incident_redrafts_after_reading_the_flag_once(self) -> None:
        """A flag that says no lets the redraft through without confirmation."""
        store = _store(InMemoryStatusUpdateStore(), _APPROVED, _PENDING)
        generator = _StubGenerator()
        security_reader = _StubSecurityReader(OperationResult.success(data=IncidentSecurityFlag.NO))

        result = await _redraft(
            store=store, reader=_StubReader([_human("x", 5)]), generator=generator, security_reader=security_reader
        )

        assert result.is_success
        assert security_reader.calls == [_INCIDENT]
        assert len(generator.calls) == 1

    @pytest.mark.parametrize("flag", [IncidentSecurityFlag.YES, IncidentSecurityFlag.UNKNOWN])
    @pytest.mark.asyncio
    async def test_confirmation_skips_the_flag_and_redrafts(self, flag: IncidentSecurityFlag) -> None:
        """The responder's confirmation is explicit consent, so the flag is not read and one model call is made."""
        store = _store(InMemoryStatusUpdateStore(), _APPROVED, _PENDING)
        generator = _StubGenerator()
        security_reader = _StubSecurityReader(OperationResult.success(data=flag))

        result = await _redraft(
            store=store,
            reader=_StubReader([_human("x", 5)]),
            generator=generator,
            security_reader=security_reader,
            security_confirmed=True,
        )

        assert result.data is not None
        assert (result.data.sequence, result.data.state) == (3, StatusUpdateState.DRAFT)
        assert security_reader.calls == []
        assert len(generator.calls) == 1


class TestLogging:
    @pytest.mark.asyncio
    async def test_logs_never_carry_the_guidance_or_the_transcript_text(self) -> None:
        """The reviewer's guidance and the conversation stay out of logs; only their size may be recorded."""
        store = _store(InMemoryStatusUpdateStore(), _APPROVED, _PENDING)

        with capture_logs() as logs:
            await _redraft(
                store=store,
                instructions="never mention Acme Payments Ltd",
                reader=_StubReader([_human("customer SIN 123-456-789", 5)]),
            )

        assert logs != []
        assert [entry for entry in logs if "Acme Payments" in str(entry)] == []
        assert [entry for entry in logs if "123-456-789" in str(entry)] == []
