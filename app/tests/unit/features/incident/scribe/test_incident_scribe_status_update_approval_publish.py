"""Tests for approving a status update and rendering it as copy-ready text in one call.

``approve_and_publish`` approves the pending draft, then renders the approved
record through the ``StatusPagePublisher``. A refused approval is returned with
its code and nothing is rendered; a rendering failure is returned as the
publisher classified it.

Records live in the core's ``InMemoryStatusUpdateStore`` through the real
``approve_status_update`` (replaced on the module with its store bound); a
recording publisher stands in for the copy-ready adapter, so the tests see
exactly which record reached it and with which labels.
"""

from dataclasses import replace
from datetime import UTC, datetime
from functools import partial

import pytest

from contracts.operations import OperationResult
from contracts.operations.codes import ErrorCode
from features.incident.core.adapters.in_memory import InMemoryStatusUpdateStore
from features.incident.core.api import StatusUpdate, StatusUpdateStage, StatusUpdateState, StatusUpdateText
from features.incident.scribe import status_update_approval
from features.incident.scribe.comms_profile import ProfileLabels
from features.incident.scribe.domain import CopyReadyText, StatusUpdateEdit
from features.incident.scribe.entrypoints.slack_views import build_profile_labels
from features.incident.scribe.status_update_approval import approve_and_publish, approve_status_update

pytestmark = pytest.mark.unit

_NOW = datetime(2026, 10, 9, 15, 0, tzinfo=UTC)
_TEXT = StatusUpdateText(affected_service="service", impact="impact", current_action="action", workaround="none")
_DRAFT = StatusUpdate(
    incident_id="inc-1",
    sequence=1,
    state=StatusUpdateState.DRAFT,
    stage=StatusUpdateStage.INVESTIGATING,
    en=_TEXT,
    fr=_TEXT,
    next_update_at=_NOW,
    author="U1",
    transcript_cutoff=_NOW,
    transcript_fingerprint="v1:sha256:abc",
    created_at=_NOW,
)
_EDIT = StatusUpdateEdit(stage=StatusUpdateStage.INVESTIGATING, en=_TEXT, fr=_TEXT)
_COPY = CopyReadyText(en="EN text", fr="FR text")


class _RecordingPublisher:
    """Publisher that records each record and labels it renders, and returns a fixed result."""

    def __init__(self, result: OperationResult[CopyReadyText]) -> None:
        self.result = result
        self.calls: list[tuple[StatusUpdate, ProfileLabels, ProfileLabels]] = []

    async def publish(
        self, update: StatusUpdate, *, labels_en: ProfileLabels, labels_fr: ProfileLabels
    ) -> OperationResult[CopyReadyText]:
        self.calls.append((update, labels_en, labels_fr))
        return self.result


@pytest.fixture
def store(monkeypatch: pytest.MonkeyPatch) -> InMemoryStatusUpdateStore:
    status_updates = InMemoryStatusUpdateStore()
    status_updates.append(_DRAFT)
    monkeypatch.setattr(
        status_update_approval, "approve_status_update", partial(approve_status_update, store=status_updates, now=_NOW)
    )
    return status_updates


async def _approve(publisher: _RecordingPublisher, edit: StatusUpdateEdit = _EDIT) -> OperationResult[CopyReadyText]:
    return await approve_and_publish(
        "inc-1",
        1,
        approver="U9",
        edit=edit,
        labels_en=build_profile_labels("en-US"),
        labels_fr=build_profile_labels("fr-FR"),
        publisher=publisher,
    )


async def test_an_approval_renders_the_approved_record(store: InMemoryStatusUpdateStore) -> None:
    """The approved record, with its approver, reaches the publisher with both languages' labels; its text is returned."""
    publisher = _RecordingPublisher(OperationResult.success(data=_COPY))

    result = await _approve(publisher)

    assert (result.is_success, result.data) == (True, _COPY)
    approved = replace(_DRAFT, state=StatusUpdateState.APPROVED, approver="U9", approved_at=_NOW)
    assert publisher.calls == [(approved, build_profile_labels("en-US"), build_profile_labels("fr-FR"))]


async def test_a_refused_approval_renders_nothing(store: InMemoryStatusUpdateStore) -> None:
    """Blank fields refuse the approval with their code, and the publisher is never called."""
    publisher = _RecordingPublisher(OperationResult.success(data=_COPY))

    result = await _approve(publisher, edit=replace(_EDIT, en=replace(_TEXT, impact="  ")))

    assert result.error_code == ErrorCode.STATUS_UPDATE_FIELDS_INVALID
    assert publisher.calls == []


async def test_a_stale_approval_renders_nothing(store: InMemoryStatusUpdateStore) -> None:
    """A newer record makes the approval a conflict, and nothing is rendered."""
    store.append(replace(_DRAFT, sequence=2))
    publisher = _RecordingPublisher(OperationResult.success(data=_COPY))

    result = await _approve(publisher)

    assert result.error_code == ErrorCode.STATUS_UPDATE_CONFLICT
    assert publisher.calls == []


async def test_a_rendering_failure_is_returned_as_classified(store: InMemoryStatusUpdateStore) -> None:
    """The approval is stored, and the publisher's error is what the caller sees."""
    failed = OperationResult.permanent_error(message="draft", error_code=ErrorCode.STATUS_UPDATE_NOT_APPROVED)
    publisher = _RecordingPublisher(failed)

    result = await _approve(publisher)

    assert result.error_code == ErrorCode.STATUS_UPDATE_NOT_APPROVED
    latest = store.latest("inc-1").data
    assert latest is not None and latest.state is StatusUpdateState.APPROVED
