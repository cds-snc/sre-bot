"""Tests for reading or toggling an approved status update and rendering it as copy-ready text in one call.

``read_published`` returns the approved record at a sequence with its text;
``set_published_and_render`` marks it published or not first. A failed read or
toggle is passed on without rendering; a rendering failure is returned as the
publisher classified it.

Records live in the core's ``InMemoryStatusUpdateStore`` through the real read
and toggle (replaced on the module with the store bound); a recording publisher
stands in for the copy-ready adapter.
"""

from dataclasses import replace
from datetime import UTC, datetime
from functools import partial

import pytest

from contracts.operations import OperationResult
from contracts.operations.codes import ErrorCode
from features.incident.comms import history
from features.incident.comms.comms_profile import ProfileLabels
from features.incident.comms.domain import CopyReadyText, PublishedRecord
from features.incident.comms.entrypoints.slack_views import build_profile_labels
from features.incident.comms.history import (
    get_approved_update,
    read_published,
    set_published,
    set_published_and_render,
)
from features.incident.core.adapters.in_memory import InMemoryStatusUpdateStore
from features.incident.core.api import StatusUpdate, StatusUpdateStage, StatusUpdateState, StatusUpdateText

pytestmark = pytest.mark.unit

_NOW = datetime(2026, 10, 9, 15, 0, tzinfo=UTC)
_TEXT = StatusUpdateText(affected_service="service", impact="impact", current_action="action", workaround="none")
_APPROVED = StatusUpdate(
    incident_id="inc-1",
    sequence=1,
    state=StatusUpdateState.APPROVED,
    stage=StatusUpdateStage.IDENTIFIED,
    en=_TEXT,
    fr=_TEXT,
    next_update_at=_NOW,
    author="U1",
    transcript_cutoff=_NOW,
    transcript_fingerprint="v1:sha256:abc",
    created_at=_NOW,
    approver="U9",
    approved_at=_NOW,
)
_DRAFT = replace(_APPROVED, sequence=2, state=StatusUpdateState.DRAFT, approver=None, approved_at=None)
_COPY = CopyReadyText(en="EN text", fr="FR text")
_LABELS = {"labels_en": build_profile_labels("en-US"), "labels_fr": build_profile_labels("fr-FR")}


class _RecordingPublisher:
    """Publisher that records each record it renders and returns a fixed result."""

    def __init__(self, result: OperationResult[CopyReadyText]) -> None:
        self.result = result
        self.rendered: list[StatusUpdate] = []

    async def publish(
        self, update: StatusUpdate, *, labels_en: ProfileLabels, labels_fr: ProfileLabels
    ) -> OperationResult[CopyReadyText]:
        self.rendered.append(update)
        return self.result


@pytest.fixture
def store(monkeypatch: pytest.MonkeyPatch) -> InMemoryStatusUpdateStore:
    status_updates = InMemoryStatusUpdateStore()
    status_updates.append(_APPROVED)
    status_updates.append(_DRAFT)
    monkeypatch.setattr(history, "get_approved_update", partial(get_approved_update, store=status_updates))
    monkeypatch.setattr(history, "set_published", partial(set_published, now=_NOW, store=status_updates))
    return status_updates


async def test_read_returns_the_record_with_its_text(store: InMemoryStatusUpdateStore) -> None:
    """The approved record and its rendered text come back together."""
    publisher = _RecordingPublisher(OperationResult.success(data=_COPY))

    result = await read_published("inc-1", 1, publisher=publisher, **_LABELS)

    assert (result.is_success, result.data) == (True, PublishedRecord(update=_APPROVED, text=_COPY))
    assert publisher.rendered == [_APPROVED]


async def test_read_of_a_draft_renders_nothing(store: InMemoryStatusUpdateStore) -> None:
    """A draft at the sequence is refused as not approved, and nothing is rendered."""
    publisher = _RecordingPublisher(OperationResult.success(data=_COPY))

    result = await read_published("inc-1", 2, publisher=publisher, **_LABELS)

    assert result.error_code == ErrorCode.STATUS_UPDATE_NOT_APPROVED
    assert publisher.rendered == []


async def test_read_passes_on_a_rendering_failure(store: InMemoryStatusUpdateStore) -> None:
    """The publisher's error is what the caller sees."""
    failed = OperationResult.transient_error(message="busy", error_code=ErrorCode.RATE_LIMITED)

    result = await read_published("inc-1", 1, publisher=_RecordingPublisher(failed), **_LABELS)

    assert result.error_code == ErrorCode.RATE_LIMITED


async def test_toggle_renders_the_stored_published_record(store: InMemoryStatusUpdateStore) -> None:
    """Marking published stores the transition, and the published record is what gets rendered."""
    publisher = _RecordingPublisher(OperationResult.success(data=_COPY))

    result = await set_published_and_render("inc-1", 1, published=True, actor="U7", publisher=publisher, **_LABELS)

    published = replace(_APPROVED, state=StatusUpdateState.PUBLISHED, published_at=_NOW, published_by="U7")
    assert (result.is_success, result.data) == (True, PublishedRecord(update=published, text=_COPY))
    assert publisher.rendered == [published]


async def test_toggle_of_a_missing_sequence_renders_nothing(store: InMemoryStatusUpdateStore) -> None:
    """A sequence the incident does not have is a conflict, and nothing is rendered."""
    publisher = _RecordingPublisher(OperationResult.success(data=_COPY))

    result = await set_published_and_render("inc-1", 9, published=True, actor="U7", publisher=publisher, **_LABELS)

    assert result.error_code == ErrorCode.STATUS_UPDATE_CONFLICT
    assert publisher.rendered == []


async def test_toggle_passes_on_a_rendering_failure(store: InMemoryStatusUpdateStore) -> None:
    """The toggle is stored, and the publisher's error is what the caller sees."""
    failed = OperationResult.permanent_error(message="draft", error_code=ErrorCode.STATUS_UPDATE_NOT_APPROVED)

    result = await set_published_and_render(
        "inc-1", 1, published=True, actor="U7", publisher=_RecordingPublisher(failed), **_LABELS
    )

    assert result.error_code == ErrorCode.STATUS_UPDATE_NOT_APPROVED
    stored = store.list_for_incident("inc-1").data
    assert stored is not None and any(update.state is StatusUpdateState.PUBLISHED for update in stored)
