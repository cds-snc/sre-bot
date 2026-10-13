"""Tests for the form shown after Save draft, start and Review in the status-updates modal.

``save_status_update_form`` stores the typed values and returns the form to
show: the saved draft, or the stored draft overlaid with the typed values and
``kept`` set when nothing was saved. A stale sequence and an unreadable stored
draft are errors. ``start_status_update_form`` and ``open_status_update_form``
return the started or pending draft's form, each with the AI-availability flag.

The save, start, read and availability calls are replaced on the form module by
recording stubs, so each test pins how the module combines their results; the
calls themselves have their own tests.
"""

from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

import pytest

from contracts.operations import OperationResult
from contracts.operations.codes import ErrorCode
from features.incident.core.api import StatusUpdate, StatusUpdateStage, StatusUpdateState, StatusUpdateText
from features.incident.scribe import status_update_form
from features.incident.scribe.domain import StatusUpdateDraftOutcome, StatusUpdateEdit, StatusUpdateOutcomeKind
from features.incident.scribe.status_update_form import (
    open_status_update_form,
    save_status_update_form,
    start_status_update_form,
)

pytestmark = pytest.mark.unit

_NOW = datetime(2026, 10, 9, 15, 0, tzinfo=UTC)


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
_SAVED = replace(_STORED, sequence=5, stage=_EDIT.stage, en=_EDIT.en, fr=_EDIT.fr)


class _Calls:
    """Recording stubs for the calls the form module makes."""

    def __init__(self, *, saved: OperationResult[StatusUpdate], read: OperationResult[StatusUpdate]) -> None:
        self.saved = saved
        self.read = read
        self.saves: list[dict[str, Any]] = []
        self.reads: list[tuple[str, int]] = []

    def save(self, conversation_id: str, sequence: int, **kwargs: Any) -> OperationResult[StatusUpdate]:
        self.saves.append({"conversation_id": conversation_id, "sequence": sequence, **kwargs})
        return self.saved

    async def get_draft(self, incident_id: str, sequence: int) -> OperationResult[StatusUpdate]:
        self.reads.append((incident_id, sequence))
        return self.read


def _install(monkeypatch: pytest.MonkeyPatch, calls: _Calls, *, ai: bool = True) -> None:
    monkeypatch.setattr(status_update_form, "save_status_update_draft", calls.save)
    monkeypatch.setattr(status_update_form, "get_draft_for_review", calls.get_draft)
    monkeypatch.setattr(status_update_form, "text_generation_available", lambda: ai)


async def test_a_save_returns_the_saved_draft_without_reading_the_stored_one(monkeypatch: pytest.MonkeyPatch) -> None:
    """The saved draft fills the form, nothing is kept, and the stored draft is not read."""
    calls = _Calls(saved=OperationResult.success(data=_SAVED), read=OperationResult.success(data=_STORED))
    _install(monkeypatch, calls, ai=False)

    result = await save_status_update_form("C1", "inc-1", 4, edit=_EDIT, author="U2")

    assert result.is_success and result.data is not None
    assert (result.data.update, result.data.kept, result.data.ai_available) == (_SAVED, False, False)
    assert calls.saves == [{"conversation_id": "C1", "sequence": 4, "edit": _EDIT, "author": "U2"}]
    assert calls.reads == []


async def test_a_stale_sequence_is_an_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """A conflicting save is returned as the conflict error, so the handler shows the conflict view."""
    conflict = OperationResult.permanent_error(message="stale", error_code=ErrorCode.STATUS_UPDATE_CONFLICT)
    calls = _Calls(saved=conflict, read=OperationResult.success(data=_STORED))
    _install(monkeypatch, calls)

    result = await save_status_update_form("C1", "inc-1", 4, edit=_EDIT, author="U2")

    assert not result.is_success
    assert result.error_code == ErrorCode.STATUS_UPDATE_CONFLICT
    assert calls.reads == []


async def test_a_failed_save_keeps_the_stored_draft_overlaid_with_the_typed_values(monkeypatch: pytest.MonkeyPatch) -> None:
    """A non-conflict failure re-reads the stored draft and overlays the typed stage and fields, with the code."""
    failed = OperationResult.transient_error(message="throttled", error_code=ErrorCode.RATE_LIMITED)
    calls = _Calls(saved=failed, read=OperationResult.success(data=_STORED))
    _install(monkeypatch, calls)

    result = await save_status_update_form("C1", "inc-1", 4, edit=_EDIT, author="U2")

    assert result.is_success and result.data is not None
    assert result.data.update == replace(_STORED, stage=_EDIT.stage, en=_EDIT.en, fr=_EDIT.fr)
    assert (result.data.kept, result.data.failure_code) == (True, ErrorCode.RATE_LIMITED)
    assert calls.reads == [("inc-1", 4)]


async def test_a_form_without_a_stage_keeps_the_stored_draft_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    """With no readable stage nothing is saved, and the stored draft is shown as it is."""
    calls = _Calls(saved=OperationResult.success(data=_SAVED), read=OperationResult.success(data=_STORED))
    _install(monkeypatch, calls)

    result = await save_status_update_form("C1", "inc-1", 4, edit=None, author="U2")

    assert result.is_success and result.data is not None
    assert (result.data.update, result.data.kept) == (_STORED, True)
    assert result.data.failure_code == ErrorCode.STATUS_UPDATE_FIELDS_INVALID
    assert calls.saves == []


async def test_an_unreadable_stored_draft_after_a_failed_save_is_an_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """When the kept draft cannot be read back, the read's error is returned."""
    failed = OperationResult.transient_error(message="throttled", error_code=ErrorCode.RATE_LIMITED)
    unreadable = OperationResult.permanent_error(message="gone", error_code=ErrorCode.STATUS_UPDATE_CONFLICT)
    _install(monkeypatch, _Calls(saved=failed, read=unreadable))

    result = await save_status_update_form("C1", "inc-1", 4, edit=_EDIT, author="U2")

    assert not result.is_success
    assert result.error_code == ErrorCode.STATUS_UPDATE_CONFLICT


async def test_open_returns_the_pending_draft_with_the_ai_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    """Review shows the pending draft as stored, and whether Draft with AI is offered."""
    _install(
        monkeypatch, _Calls(saved=OperationResult.success(data=_SAVED), read=OperationResult.success(data=_STORED)), ai=False
    )

    result = await open_status_update_form("inc-1", 4)

    assert result.is_success and result.data is not None
    assert (result.data.update, result.data.ai_available, result.data.kept) == (_STORED, False, False)


async def test_open_passes_on_a_read_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """A draft that is no longer pending is returned as the read's conflict error."""
    conflict = OperationResult.permanent_error(message="stale", error_code=ErrorCode.STATUS_UPDATE_CONFLICT)
    _install(monkeypatch, _Calls(saved=OperationResult.success(data=_SAVED), read=conflict))

    result = await open_status_update_form("inc-1", 4)

    assert result.error_code == ErrorCode.STATUS_UPDATE_CONFLICT


def test_start_returns_the_started_draft_with_its_kind(monkeypatch: pytest.MonkeyPatch) -> None:
    """New update shows the started draft, how it came to be, and the AI flag."""
    outcome = StatusUpdateDraftOutcome(update=_STORED, kind=StatusUpdateOutcomeKind.MANUAL)
    monkeypatch.setattr(status_update_form, "start_status_update_draft", lambda *_, **__: OperationResult.success(data=outcome))
    monkeypatch.setattr(status_update_form, "text_generation_available", lambda: True)

    result = start_status_update_form("C1", author="U2")

    assert result.is_success and result.data is not None
    assert (result.data.update, result.data.kind, result.data.ai_available) == (_STORED, StatusUpdateOutcomeKind.MANUAL, True)


def test_start_passes_on_its_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """A start that fails returns the same classified error."""
    failed = OperationResult.permanent_error(message="no incident", error_code=ErrorCode.NOT_FOUND)
    monkeypatch.setattr(status_update_form, "start_status_update_draft", lambda *_, **__: failed)

    result = start_status_update_form("C1", author="U2")

    assert (result.is_success, result.error_code) == (False, ErrorCode.NOT_FOUND)
