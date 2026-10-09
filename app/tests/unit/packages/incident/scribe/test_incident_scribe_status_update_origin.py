"""Tests for the origin the scribe service records on every draft it appends.

``draft_status_update`` and ``redraft_status_update`` run against the
in-memory store and stubs for the lookup, the transcript reader, the security
flag reader and the text generator, with a fixed ``now``. Each test drives one
path and asserts only the stored record's origin, since the record's other
fields are pinned by the drafting and redrafting tests.
"""

import json
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from contracts.operations import OperationResult
from packages.incident.core.adapters.in_memory import InMemoryStatusUpdateStore
from packages.incident.core.api import (
    IncidentSecurityFlag,
    StatusUpdate,
    StatusUpdateOrigin,
    StatusUpdateStage,
    StatusUpdateState,
    StatusUpdateText,
    TranscriptMessage,
)
from packages.incident.scribe.domain import NoNewInformationWording, StatusUpdateEdit
from packages.incident.scribe.status_update import draft_status_update, redraft_status_update

pytestmark = pytest.mark.unit

_NOW = datetime(2026, 10, 7, 15, 0, tzinfo=UTC)
_INCIDENT = "inc-uuid-1"
_CHANNEL = "C123"
_FIELDS = ("affected_service", "impact", "current_action", "workaround")
_WORDING = NoNewInformationWording(en="No new information.", fr="Aucune nouvelle information.")


def _text(language: str) -> StatusUpdateText:
    return StatusUpdateText(**{field: f"{language} {field}" for field in _FIELDS})


def _record(sequence: int, state: StatusUpdateState) -> StatusUpdate:
    at = _NOW - timedelta(minutes=90)
    return StatusUpdate(
        incident_id=_INCIDENT,
        sequence=sequence,
        state=state,
        stage=StatusUpdateStage.IDENTIFIED,
        en=_text("en"),
        fr=_text("fr"),
        next_update_at=at,
        author="U0",
        transcript_cutoff=at,
        transcript_fingerprint="v1:sha256:prior",
        created_at=at,
    )


_APPROVED = _record(1, StatusUpdateState.APPROVED)
_NEW_MESSAGE = TranscriptMessage(author="Ada", text="rolled back", posted_at=_NOW - timedelta(minutes=5))


def _model_answer() -> str:
    answer = {"stage": "identified"} | {
        f"{lang}_{field}": f"{lang} {field} drafted" for lang in ("en", "fr") for field in _FIELDS
    }
    return json.dumps(answer)


class _StubLookup:
    def find_incident_for_conversation(self, conversation_id: str) -> OperationResult[str]:
        return OperationResult.success(data=_INCIDENT)


class _StubSecurityReader:
    def read_security_flag(self, incident_id: str) -> OperationResult[IncidentSecurityFlag]:
        return OperationResult.success(data=IncidentSecurityFlag.NO)


class _StubReader:
    def __init__(self, messages: Sequence[TranscriptMessage]) -> None:
        self._messages = list(messages)

    def conversation_started_at(self, conversation_id: str) -> datetime | None:
        return _NOW - timedelta(hours=10)

    def read_transcript(
        self,
        conversation_id: str,
        *,
        since: datetime,
        limit: int,
        exclude_own_and_system_messages: bool = False,
    ) -> Sequence[TranscriptMessage]:
        return self._messages


class _StubGenerator:
    async def summarize(
        self,
        transcript: str,
        *,
        instructions: str | None = None,
        max_output_tokens: int | None = None,
    ) -> OperationResult[str]:
        return OperationResult.success(data=_model_answer())


def _store(*records: StatusUpdate) -> InMemoryStatusUpdateStore:
    store = InMemoryStatusUpdateStore()
    for record in records:
        store.append(record)
    return store


def _stubs(messages: Sequence[TranscriptMessage]) -> dict[str, Any]:
    return {
        "lookup": _StubLookup(),
        "reader": _StubReader(messages),
        "generator": _StubGenerator(),
        "security_reader": _StubSecurityReader(),
        "now": _NOW,
    }


@pytest.mark.parametrize(
    ("messages", "manual", "origin"),
    [
        ([_NEW_MESSAGE], False, StatusUpdateOrigin.MODEL),
        ([_NEW_MESSAGE], True, StatusUpdateOrigin.HAND),
        ([], False, StatusUpdateOrigin.CARRIED_FORWARD),
    ],
    ids=["drafted", "manual", "carried-forward"],
)
@pytest.mark.asyncio
async def test_draft_records_how_its_text_came_to_be(
    messages: list[TranscriptMessage], manual: bool, origin: StatusUpdateOrigin
) -> None:
    """A model draft is MODEL, a hand-started one HAND, and a repeat with nothing new CARRIED_FORWARD."""
    store = _store(_APPROVED)

    result = await draft_status_update(
        _CHANNEL, author="U0DRAFTER", wording=_WORDING, manual=manual, store=store, **_stubs(messages)
    )

    assert result.data is not None
    assert result.data.update.origin is origin
    assert store.latest(_INCIDENT).data == result.data.update


@pytest.mark.asyncio
async def test_a_failed_model_call_falls_back_to_a_hand_draft() -> None:
    """The manual fallback holds the prefill for the responder to write, so it is HAND."""

    class _FailingGenerator(_StubGenerator):
        async def summarize(
            self,
            transcript: str,
            *,
            instructions: str | None = None,
            max_output_tokens: int | None = None,
        ) -> OperationResult[str]:
            return OperationResult.permanent_error(message="off", error_code="TEXT_GENERATION_UNAVAILABLE")

    store = _store(_APPROVED)

    result = await draft_status_update(
        _CHANNEL,
        author="U0DRAFTER",
        wording=_WORDING,
        store=store,
        **(_stubs([_NEW_MESSAGE]) | {"generator": _FailingGenerator()}),
    )

    assert result.data is not None
    assert result.data.update.origin is StatusUpdateOrigin.HAND


@pytest.mark.asyncio
async def test_redraft_from_instructions_is_model_instructed() -> None:
    """A reviewer's guidance steered the model, which the origin keeps apart from a plain model draft."""
    store = _store(_APPROVED, _record(2, StatusUpdateState.DRAFT))
    current = StatusUpdateEdit(stage=StatusUpdateStage.IDENTIFIED, en=_text("en"), fr=_text("fr"))

    result = await redraft_status_update(
        _CHANNEL, 2, instructions="shorter", current=current, author="U0REDRAFTER", store=store, **_stubs([_NEW_MESSAGE])
    )

    assert result.data is not None
    assert result.data.origin is StatusUpdateOrigin.MODEL_INSTRUCTED
