"""Tests for the form shown after Draft with AI in the status-updates modal.

``fill_status_update_form`` fills the draft with AI from the typed values and
returns the form to show: the new draft with its kind, or, on a refusal or
failure, the stored draft overlaid with the typed values, ``kept`` set and the
refusal's code. The stored draft is read only when it is the model's base (no
readable stage) or a kept draft needs it. A stale sequence or an unreadable
stored draft is an error.

The fill and read calls are replaced on the form module by recording stubs, so
each test pins how the module combines their results; the fill itself has its
own tests.
"""

from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

import pytest

from contracts.operations import OperationResult
from contracts.operations.codes import ErrorCode
from features.incident.comms import form
from features.incident.comms.domain import (
    NoNewInformationWording,
    StatusUpdateDraftOutcome,
    StatusUpdateEdit,
    StatusUpdateOutcomeKind,
)
from features.incident.comms.form import fill_status_update_form
from features.incident.comms.service import DRAFT_UNPARSEABLE_CODE
from features.incident.core.api import StatusUpdate, StatusUpdateStage, StatusUpdateState, StatusUpdateText

pytestmark = pytest.mark.unit

_NOW = datetime(2026, 10, 9, 15, 0, tzinfo=UTC)
_WORDING = NoNewInformationWording(en="No new information.", fr="Aucune nouvelle information.")


def _text(language: str, marker: str = "stored") -> StatusUpdateText:
    return StatusUpdateText(
        affected_service=f"{language} {marker} service",
        impact=f"{language} {marker} impact",
        current_action=f"{language} {marker} action",
        workaround=f"{language} {marker} workaround",
    )


_STORED = StatusUpdate(
    incident_id="inc-1",
    sequence=4,
    state=StatusUpdateState.DRAFT,
    stage=StatusUpdateStage.INVESTIGATING,
    en=_text("en"),
    fr=_text("fr"),
    next_update_at=_NOW,
    author="U1",
    transcript_cutoff=_NOW,
    transcript_fingerprint="v1:sha256:abc",
    created_at=_NOW,
)
_EDIT = StatusUpdateEdit(stage=StatusUpdateStage.IDENTIFIED, en=_text("en", "typed"), fr=_text("fr", "typed"))
_FILLED = replace(_STORED, sequence=5, en=_text("en", "model"), fr=_text("fr", "model"))


class _Calls:
    """Recording stubs for the fill and the stored-draft read."""

    def __init__(self, filled: OperationResult[StatusUpdateDraftOutcome], read: OperationResult[StatusUpdate]) -> None:
        self.filled = filled
        self.read = read
        self.fills: list[dict[str, Any]] = []
        self.reads = 0

    async def fill(self, conversation_id: str, sequence: int, **kwargs: Any) -> OperationResult[StatusUpdateDraftOutcome]:
        self.fills.append({"conversation_id": conversation_id, "sequence": sequence, **kwargs})
        return self.filled

    async def get_draft(self, incident_id: str, sequence: int) -> OperationResult[StatusUpdate]:
        self.reads += 1
        return self.read


def _install(
    monkeypatch: pytest.MonkeyPatch,
    filled: OperationResult[StatusUpdateDraftOutcome],
    read: OperationResult[StatusUpdate] | None = None,
) -> _Calls:
    calls = _Calls(filled, read or OperationResult.success(data=_STORED))
    monkeypatch.setattr(form, "generate_status_update_draft", calls.fill)
    monkeypatch.setattr(form, "get_draft_for_review", calls.get_draft)
    return calls


async def _fill(edit: StatusUpdateEdit | None = _EDIT) -> OperationResult[Any]:
    return await fill_status_update_form(
        "C1", "inc-1", 4, edit=edit, author="U2", wording=_WORDING, instructions="be brief", security_confirmed=True
    )


@pytest.mark.parametrize("kind", [StatusUpdateOutcomeKind.DRAFTED, StatusUpdateOutcomeKind.CARRIED_FORWARD])
async def test_a_fill_returns_the_new_draft_and_its_kind(monkeypatch: pytest.MonkeyPatch, kind: StatusUpdateOutcomeKind) -> None:
    """The new draft fills the form with its kind and AI offered; the typed values were the model's base."""
    calls = _install(monkeypatch, OperationResult.success(data=StatusUpdateDraftOutcome(update=_FILLED, kind=kind)))

    result = await _fill()

    assert result.is_success and result.data is not None
    assert (result.data.update, result.data.kind, result.data.kept, result.data.ai_available) == (_FILLED, kind, False, True)
    assert calls.fills[0]["current"] == _EDIT
    assert (calls.fills[0]["instructions"], calls.fills[0]["security_confirmed"]) == ("be brief", True)
    assert calls.reads == 0


@pytest.mark.parametrize(
    ("code", "ai_available"),
    [
        (ErrorCode.SECURITY_CONFIRMATION_REQUIRED, True),
        (ErrorCode.EMPTY_HISTORY, True),
        (DRAFT_UNPARSEABLE_CODE, True),
        (ErrorCode.RATE_LIMITED, True),
        (ErrorCode.TEXT_GENERATION_UNAVAILABLE, False),
    ],
)
async def test_a_refusal_keeps_the_stored_draft_overlaid_with_the_typed_values(
    monkeypatch: pytest.MonkeyPatch, code: str, ai_available: bool
) -> None:
    """A refusal or failure keeps the stored draft with the typed values and the code; AI stays offered unless unavailable."""
    calls = _install(monkeypatch, OperationResult.permanent_error(message="refused", error_code=code))

    result = await _fill()

    assert result.is_success and result.data is not None
    assert result.data.update == replace(_STORED, stage=_EDIT.stage, en=_EDIT.en, fr=_EDIT.fr)
    assert (result.data.kept, result.data.failure_code, result.data.ai_available) == (True, code, ai_available)
    assert calls.reads == 1


async def test_a_stale_sequence_is_an_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """A conflicting fill is returned as the conflict error without reading the stored draft."""
    conflict = OperationResult.permanent_error(message="stale", error_code=ErrorCode.STATUS_UPDATE_CONFLICT)
    calls = _install(monkeypatch, conflict)

    result = await _fill()

    assert result.error_code == ErrorCode.STATUS_UPDATE_CONFLICT
    assert calls.reads == 0


async def test_without_a_stage_the_stored_draft_is_the_model_base(monkeypatch: pytest.MonkeyPatch) -> None:
    """With no readable stage the stored draft is read once, handed to the model, and kept as is on a refusal."""
    refused = OperationResult.permanent_error(message="refused", error_code=ErrorCode.EMPTY_HISTORY)
    calls = _install(monkeypatch, refused)

    result = await _fill(edit=None)

    assert calls.fills[0]["current"] == StatusUpdateEdit(stage=_STORED.stage, en=_STORED.en, fr=_STORED.fr)
    assert calls.reads == 1
    assert result.data is not None and result.data.update == _STORED


async def test_an_unreadable_base_is_an_error_without_a_fill(monkeypatch: pytest.MonkeyPatch) -> None:
    """When the stored draft that would be the model's base cannot be read, nothing is filled."""
    unreadable = OperationResult.permanent_error(message="stale", error_code=ErrorCode.STATUS_UPDATE_CONFLICT)
    calls = _install(monkeypatch, OperationResult.success(data=None), read=unreadable)

    result = await _fill(edit=None)

    assert result.error_code == ErrorCode.STATUS_UPDATE_CONFLICT
    assert calls.fills == []


async def test_an_unreadable_kept_draft_is_an_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """When a refusal's kept draft cannot be read back, the read's error is returned."""
    refused = OperationResult.permanent_error(message="refused", error_code=ErrorCode.EMPTY_HISTORY)
    unreadable = OperationResult.transient_error(message="throttled", error_code=ErrorCode.RATE_LIMITED)
    _install(monkeypatch, refused, read=unreadable)

    result = await _fill()

    assert result.error_code == ErrorCode.RATE_LIMITED
