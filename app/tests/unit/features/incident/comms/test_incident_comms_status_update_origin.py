"""Tests for the origin the comms service records on every draft it appends.

``start_status_update_draft`` and ``generate_status_update_draft`` run against
the in-memory status-update store, an in-memory incident store holding one
non-security incident on the channel, and stubs for the transcript reader and
the text generator, with a fixed ``now``. Each test
drives one path and asserts only the stored record's origin, since the record's
other fields are pinned by the start and generate tests.
"""

import json
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from contracts.operations import OperationResult
from features.incident.comms.domain import NoNewInformationWording, StatusUpdateEdit
from features.incident.comms.service import generate_status_update_draft, start_status_update_draft
from features.incident.core.adapters.in_memory import InMemoryStatusUpdateStore
from features.incident.core.api import (
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


_CONVERSATION = slack_conversation(_CHANNEL)


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
        "reader": _StubReader(messages),
        "generator": _StubGenerator(),
        "now": _NOW,
    }


_PENDING = _record(2, StatusUpdateState.DRAFT)
_CURRENT = StatusUpdateEdit(stage=StatusUpdateStage.IDENTIFIED, en=_text("en"), fr=_text("fr"))


@pytest.mark.parametrize("messages", [[_NEW_MESSAGE], []], ids=["new-activity", "nothing-new"])
def test_starting_by_hand_is_hand(messages: list[TranscriptMessage]) -> None:
    """A responder chose to write, so the started draft is HAND whatever the conversation holds."""
    store = _store(_APPROVED)

    result = start_status_update_draft(
        incident_store_with(incident_on(_CHANNEL, _INCIDENT)),
        _CONVERSATION,
        author="U0WRITER",
        store=store,
        reader=_StubReader(messages),
        now=_NOW,
    )

    assert result.data is not None
    assert result.data.update.origin is StatusUpdateOrigin.HAND
    assert store.latest(_INCIDENT).data == result.data.update


@pytest.mark.parametrize(
    ("messages", "instructions", "origin"),
    [
        ([_NEW_MESSAGE], "", StatusUpdateOrigin.MODEL),
        ([_NEW_MESSAGE], "shorter", StatusUpdateOrigin.MODEL_INSTRUCTED),
        ([], "", StatusUpdateOrigin.CARRIED_FORWARD),
    ],
    ids=["drafted", "instructed", "carried-forward"],
)
@pytest.mark.asyncio
async def test_draft_with_ai_records_how_its_text_came_to_be(
    messages: list[TranscriptMessage], instructions: str, origin: StatusUpdateOrigin
) -> None:
    """A model fill is MODEL, a fill steered by guidance MODEL_INSTRUCTED, and a repeat with nothing new CARRIED_FORWARD."""
    store = _store(_APPROVED, _PENDING)

    result = await generate_status_update_draft(
        incident_store_with(incident_on(_CHANNEL, _INCIDENT)),
        _CONVERSATION,
        _PENDING.sequence,
        current=_CURRENT,
        author="U0FILLER",
        wording=_WORDING,
        instructions=instructions,
        store=store,
        **_stubs(messages),
    )

    assert result.data is not None
    assert result.data.update.origin is origin
    assert store.latest(_INCIDENT).data == result.data.update
