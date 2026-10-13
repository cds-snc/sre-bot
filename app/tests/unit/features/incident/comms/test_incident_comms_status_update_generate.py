"""Tests for filling a status-update draft with AI in the comms service.

The service runs against the in-memory status-update store and stubs for the
incident lookup, the transcript reader, the security flag reader and the text
generator, with a fixed ``now``, so each test controls which records exist,
which messages are read and what the model answers. Assertions compare the
exact model call, the exact stored records, the outcome kind and the result
codes, because a fill makes at most one model call, adds at most one new draft
and leaves every earlier record as it was.
"""

import json
from collections.abc import Sequence
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from contracts.operations import OperationResult, OperationStatus
from contracts.operations.codes import ErrorCode
from features.incident.comms.domain import (
    NoNewInformationWording,
    StatusUpdateDraftOutcome,
    StatusUpdateEdit,
    StatusUpdateOutcomeKind,
)
from features.incident.comms.prompt import INSTRUCTIONS, build_redraft_input, build_redraft_instructions
from features.incident.comms.service import DRAFT_UNPARSEABLE_CODE, generate_status_update_draft
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

pytestmark = pytest.mark.unit

_NOW = datetime(2026, 10, 7, 15, 0, tzinfo=UTC)
_INCIDENT = "inc-uuid-1"
_CHANNEL = "C123"
_FILLER = "U0FILLER"
_GUIDANCE = "do not name the vendor"
_FIELDS = ("affected_service", "impact", "current_action", "workaround")
_WORDING = NoNewInformationWording(en="No new information.", fr="Aucune nouvelle information.")


def _at(minutes: int) -> datetime:
    """A time ``minutes`` before ``_NOW``."""
    return _NOW - timedelta(minutes=minutes)


def _human(text: str, minutes_ago: int) -> TranscriptMessage:
    return TranscriptMessage(author="Ada", text=text, posted_at=_at(minutes_ago))


def _bot(text: str, minutes_ago: int) -> TranscriptMessage:
    return TranscriptMessage(author="Alertmanager", text=text, posted_at=_at(minutes_ago), is_bot=True)


def _text(language: str, tag: str = "") -> StatusUpdateText:
    return StatusUpdateText(**{field: f"{language} {field}{tag}" for field in _FIELDS})


def _record(sequence: int, state: StatusUpdateState, *, cutoff_minutes_ago: int = 60) -> StatusUpdate:
    return StatusUpdate(
        incident_id=_INCIDENT,
        sequence=sequence,
        state=state,
        stage=StatusUpdateStage.IDENTIFIED,
        en=_text("en", f" #{sequence}"),
        fr=_text("fr", f" #{sequence}"),
        next_update_at=_at(cutoff_minutes_ago) + timedelta(minutes=30),
        author="U0",
        transcript_cutoff=_at(cutoff_minutes_ago),
        transcript_fingerprint=f"v1:sha256:prior{sequence}",
        created_at=_at(cutoff_minutes_ago),
    )


_APPROVED = _record(1, StatusUpdateState.APPROVED, cutoff_minutes_ago=90)
# A hand-started draft repeats the approved update's provenance until something is drafted from the conversation.
_PENDING = replace(_record(2, StatusUpdateState.DRAFT, cutoff_minutes_ago=90), transcript_fingerprint="v1:sha256:prior1")
_CURRENT = StatusUpdateEdit(stage=StatusUpdateStage.IDENTIFIED, en=_text("en", " typed"), fr=_text("fr", " typed"))


def _model_answer(stage: str = "identified") -> str:
    answer: dict[str, Any] = {"stage": stage}
    for language in ("en", "fr"):
        for field in _FIELDS:
            answer[f"{language}_{field}"] = f"{language} {field} filled"
    return json.dumps(answer)


def _filled_text(language: str) -> StatusUpdateText:
    return StatusUpdateText(**{field: f"{language} {field} filled" for field in _FIELDS})


class _StubLookup:
    def find_incident_for_conversation(self, conversation_id: str) -> OperationResult[str]:
        return OperationResult.success(data=_INCIDENT)


class _StubSecurityReader:
    def __init__(self, result: OperationResult[IncidentSecurityFlag] | None = None) -> None:
        self._result = result or OperationResult.success(data=IncidentSecurityFlag.NO)
        self.calls: list[str] = []

    def read_security_flag(self, incident_id: str) -> OperationResult[IncidentSecurityFlag]:
        self.calls.append(incident_id)
        return self._result


class _StubReader:
    def __init__(self, messages: Sequence[TranscriptMessage] = ()) -> None:
        self._messages = list(messages)
        self.reads = 0

    def conversation_started_at(self, conversation_id: str) -> datetime | None:
        return _at(600)

    def read_transcript(
        self,
        conversation_id: str,
        *,
        since: datetime,
        limit: int,
        exclude_own_and_system_messages: bool = False,
    ) -> Sequence[TranscriptMessage]:
        self.reads += 1
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
        self.calls.append({"transcript": transcript, "instructions": instructions})
        return self._result


def _store(*records: StatusUpdate) -> InMemoryStatusUpdateStore:
    store = InMemoryStatusUpdateStore()
    for record in records:
        store.append(record)
    return store


def _stored(store: InMemoryStatusUpdateStore) -> tuple[StatusUpdate, ...]:
    result = store.list_for_incident(_INCIDENT)
    assert result.data is not None
    return tuple(result.data)


async def _generate(
    *,
    store: InMemoryStatusUpdateStore,
    sequence: int = _PENDING.sequence,
    instructions: str = "",
    reader: _StubReader | None = None,
    generator: _StubGenerator | None = None,
    security_reader: _StubSecurityReader | None = None,
    security_confirmed: bool = False,
) -> OperationResult[StatusUpdateDraftOutcome]:
    return await generate_status_update_draft(
        _CHANNEL,
        sequence,
        current=_CURRENT,
        author=_FILLER,
        wording=_WORDING,
        instructions=instructions,
        security_confirmed=security_confirmed,
        lookup=_StubLookup(),
        reader=reader or _StubReader(),
        store=store,
        generator=generator or _StubGenerator(),
        security_reader=security_reader or _StubSecurityReader(),
        now=_NOW,
    )


class TestNothingNew:
    @pytest.mark.parametrize("messages", [[], [_bot("ALARM again", 5)]], ids=["empty", "bots-only"])
    @pytest.mark.asyncio
    async def test_no_new_people_and_no_instructions_carries_the_typed_fields_forward_without_a_model_call(
        self, messages: list[TranscriptMessage]
    ) -> None:
        """Code decides nothing is new: the typed fields are kept, current action takes the wording, nothing is sent out."""
        store = _store(_APPROVED, _PENDING)
        generator = _StubGenerator()
        security_reader = _StubSecurityReader()

        result = await _generate(store=store, reader=_StubReader(messages), generator=generator, security_reader=security_reader)

        expected = replace(
            _PENDING,
            sequence=3,
            en=replace(_CURRENT.en, current_action=_WORDING.en),
            fr=replace(_CURRENT.fr, current_action=_WORDING.fr),
            next_update_at=_NOW + timedelta(minutes=30),
            author=_FILLER,
            created_at=_NOW,
            origin=StatusUpdateOrigin.CARRIED_FORWARD,
        )
        assert result.data == StatusUpdateDraftOutcome(update=expected, kind=StatusUpdateOutcomeKind.CARRIED_FORWARD)
        assert (generator.calls, security_reader.calls) == ([], [])
        assert _stored(store) == (expected, _PENDING, _APPROVED)

    @pytest.mark.asyncio
    async def test_a_message_at_the_approved_cutoff_is_not_new(self) -> None:
        """Only messages strictly after the approved update's cutoff count as new."""
        store = _store(_APPROVED, _PENDING)
        generator = _StubGenerator()

        result = await _generate(store=store, reader=_StubReader([_human("already covered", 90)]), generator=generator)

        assert result.data is not None
        assert result.data.kind is StatusUpdateOutcomeKind.CARRIED_FORWARD
        assert generator.calls == []

    @pytest.mark.asyncio
    async def test_no_approved_update_and_no_people_is_empty_history_without_a_model_call(self) -> None:
        """A first draft with nothing anyone said has nothing to fill from."""
        first = _record(1, StatusUpdateState.DRAFT)
        store = _store(first)
        generator = _StubGenerator()

        result = await _generate(store=store, sequence=1, reader=_StubReader([_bot("ALARM", 5)]), generator=generator)

        assert (result.status, result.error_code) == (OperationStatus.PERMANENT_ERROR, ErrorCode.EMPTY_HISTORY)
        assert generator.calls == []
        assert _stored(store) == (first,)


class TestModelCall:
    @pytest.mark.asyncio
    async def test_new_people_and_no_instructions_fill_from_the_base_prompt_over_the_typed_fields(self) -> None:
        """Blank instructions mean draft from the conversation: one call, the base rules, the typed fields as input."""
        store = _store(_APPROVED, _PENDING)
        generator = _StubGenerator()

        result = await _generate(store=store, reader=_StubReader([_human("rolled back", 10)]), generator=generator)

        assert generator.calls == [
            {"transcript": build_redraft_input(_CURRENT, "Ada: rolled back"), "instructions": INSTRUCTIONS}
        ]
        assert result.data is not None
        assert result.data.kind is StatusUpdateOutcomeKind.DRAFTED
        assert (result.data.update.sequence, result.data.update.origin) == (3, StatusUpdateOrigin.MODEL)
        assert (result.data.update.en, result.data.update.fr) == (_filled_text("en"), _filled_text("fr"))
        assert result.data.update.transcript_cutoff == _at(10)

    @pytest.mark.parametrize("messages", [[_human("rolled back", 10)], []], ids=["new-people", "nothing-new"])
    @pytest.mark.asyncio
    async def test_instructions_always_make_one_model_call_with_the_redraft_prompt(
        self, messages: list[TranscriptMessage]
    ) -> None:
        """Instructions are a request, so the model is called even when nothing new was said."""
        store = _store(_APPROVED, _PENDING)
        generator = _StubGenerator()

        result = await _generate(store=store, instructions=f"  {_GUIDANCE} ", reader=_StubReader(messages), generator=generator)

        assert [call["instructions"] for call in generator.calls] == [build_redraft_instructions(_GUIDANCE)]
        assert result.data is not None
        assert (result.data.kind, result.data.update.origin) == (
            StatusUpdateOutcomeKind.DRAFTED,
            StatusUpdateOrigin.MODEL_INSTRUCTED,
        )

    @pytest.mark.asyncio
    async def test_a_first_draft_with_people_is_filled_by_the_model(self) -> None:
        """Without an approved update every person's message is new."""
        store = _store(_record(1, StatusUpdateState.DRAFT, cutoff_minutes_ago=600))
        generator = _StubGenerator()

        result = await _generate(store=store, sequence=1, reader=_StubReader([_human("hello", 50)]), generator=generator)

        assert len(generator.calls) == 1
        assert result.data is not None
        assert (result.data.update.sequence, result.data.update.origin) == (2, StatusUpdateOrigin.MODEL)


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
    async def test_an_unconfirmed_security_incident_refuses_before_the_model(
        self, flag_result: OperationResult[IncidentSecurityFlag]
    ) -> None:
        """A model call that may expose a security incident needs the responder's confirmation first."""
        store = _store(_APPROVED, _PENDING)
        generator = _StubGenerator()

        result = await _generate(
            store=store,
            reader=_StubReader([_human("x", 5)]),
            generator=generator,
            security_reader=_StubSecurityReader(flag_result),
        )

        assert (result.status, result.error_code) == (
            OperationStatus.PERMANENT_ERROR,
            ErrorCode.SECURITY_CONFIRMATION_REQUIRED,
        )
        assert generator.calls == []
        assert _stored(store) == (_PENDING, _APPROVED)

    @pytest.mark.asyncio
    async def test_confirmation_skips_the_flag(self) -> None:
        """The responder's confirmation is explicit consent, so the flag is not read."""
        store = _store(_APPROVED, _PENDING)
        security_reader = _StubSecurityReader(OperationResult.success(data=IncidentSecurityFlag.YES))
        generator = _StubGenerator()

        result = await _generate(
            store=store,
            reader=_StubReader([_human("x", 5)]),
            generator=generator,
            security_reader=security_reader,
            security_confirmed=True,
        )

        assert result.is_success
        assert security_reader.calls == []
        assert len(generator.calls) == 1


class TestFailuresKeepThePendingDraft:
    @pytest.mark.asyncio
    async def test_a_model_failure_passes_through_and_stores_nothing(self) -> None:
        """The generator's classified error reaches the caller; the pending draft stays latest."""
        store = _store(_APPROVED, _PENDING)
        failure: OperationResult[str] = OperationResult.permanent_error(
            message="not configured", error_code="TEXT_GENERATION_UNAVAILABLE"
        )

        result = await _generate(store=store, reader=_StubReader([_human("x", 5)]), generator=_StubGenerator(failure))

        assert (result.status, result.error_code) == (OperationStatus.PERMANENT_ERROR, "TEXT_GENERATION_UNAVAILABLE")
        assert _stored(store) == (_PENDING, _APPROVED)

    @pytest.mark.asyncio
    async def test_an_unparseable_answer_is_refused_and_stores_nothing(self) -> None:
        """A partial or malformed answer never becomes a draft."""
        store = _store(_APPROVED, _PENDING)

        result = await _generate(
            store=store,
            reader=_StubReader([_human("x", 5)]),
            generator=_StubGenerator(OperationResult.success(data="I would rather not.")),
        )

        assert (result.status, result.error_code) == (OperationStatus.PERMANENT_ERROR, DRAFT_UNPARSEABLE_CODE)
        assert _stored(store) == (_PENDING, _APPROVED)

    @pytest.mark.parametrize("sequence", [1, 3], ids=["older", "newer"])
    @pytest.mark.asyncio
    async def test_a_stale_sequence_is_a_conflict_with_no_read_or_model_call(self, sequence: int) -> None:
        """Only the pending draft the responder sees can be filled; anything else changed under them."""
        store = _store(_APPROVED, _PENDING)
        reader = _StubReader([_human("x", 5)])
        generator = _StubGenerator()

        result = await _generate(store=store, sequence=sequence, reader=reader, generator=generator)

        assert (result.status, result.error_code) == (OperationStatus.PERMANENT_ERROR, ErrorCode.STATUS_UPDATE_CONFLICT)
        assert (reader.reads, generator.calls) == (0, [])
        assert _stored(store) == (_PENDING, _APPROVED)
