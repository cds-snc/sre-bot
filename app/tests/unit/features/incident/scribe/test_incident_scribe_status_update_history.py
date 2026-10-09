"""Tests for reading one approved status update of an incident by its sequence.

``get_approved_update`` returns the incident's record at a sequence when it is
approved or published. A draft at that sequence is refused as not approved and
a missing sequence as a conflict, so the modal can say the list is stale. Store
errors keep their classification.

Records live in the core's ``InMemoryStatusUpdateStore``; a failing stub stands
in for a throttled store. The returned record is compared whole, so nothing
about it may change on the way out.
"""

from collections.abc import Sequence
from dataclasses import replace
from datetime import UTC, datetime

import pytest

from contracts.operations import OperationResult, OperationStatus
from contracts.operations.codes import ErrorCode
from features.incident.core.adapters.in_memory import InMemoryStatusUpdateStore
from features.incident.core.api import StatusUpdate, StatusUpdateStage, StatusUpdateState, StatusUpdateText
from features.incident.scribe.status_update_history import get_approved_update

pytestmark = pytest.mark.unit

_INCIDENT = "inc-uuid-1"
_NOW = datetime(2026, 10, 7, 15, 0, tzinfo=UTC)


def _text(language: str) -> StatusUpdateText:
    return StatusUpdateText(
        affected_service=f"{language} service",
        impact=f"{language} impact",
        current_action=f"{language} action",
        workaround=f"{language} workaround",
    )


_DRAFT_1 = StatusUpdate(
    incident_id=_INCIDENT,
    sequence=1,
    state=StatusUpdateState.DRAFT,
    stage=StatusUpdateStage.INVESTIGATING,
    en=_text("en"),
    fr=_text("fr"),
    next_update_at=_NOW,
    author="U123",
    transcript_cutoff=_NOW,
    transcript_fingerprint="v1:sha256:abc123",
    created_at=_NOW,
)
_PUBLISHED_1 = replace(_DRAFT_1, state=StatusUpdateState.PUBLISHED, approver="U0APPROVER", approved_at=_NOW, published_at=_NOW)
_APPROVED_2 = replace(
    _DRAFT_1,
    sequence=2,
    state=StatusUpdateState.APPROVED,
    stage=StatusUpdateStage.IDENTIFIED,
    approver="U0OTHER",
    approved_at=_NOW,
)
_DRAFT_3 = replace(_DRAFT_1, sequence=3, stage=StatusUpdateStage.MONITORING)


class _FailingStore:
    """Store whose list read fails with a throttling error."""

    def list_for_incident(self, incident_id: str) -> OperationResult[Sequence[StatusUpdate]]:
        return OperationResult.transient_error(message="throttled", error_code=ErrorCode.RATE_LIMITED, retry_after=3)


def _store(*updates: StatusUpdate) -> InMemoryStatusUpdateStore:
    store = InMemoryStatusUpdateStore()
    for update in updates:
        store.append(update)
    return store


async def test_returns_an_approved_update() -> None:
    """An approved record at the sequence is returned unchanged, though a newer draft exists."""
    result = await get_approved_update(_INCIDENT, 2, store=_store(_PUBLISHED_1, _APPROVED_2, _DRAFT_3))

    assert (result.status, result.data) == (OperationStatus.SUCCESS, _APPROVED_2)


async def test_returns_a_published_update() -> None:
    """A published record at an older sequence is returned unchanged."""
    result = await get_approved_update(_INCIDENT, 1, store=_store(_PUBLISHED_1, _APPROVED_2, _DRAFT_3))

    assert (result.status, result.data) == (OperationStatus.SUCCESS, _PUBLISHED_1)


async def test_draft_is_not_approved() -> None:
    """A draft at the sequence is refused as not approved."""
    result = await get_approved_update(_INCIDENT, 3, store=_store(_PUBLISHED_1, _APPROVED_2, _DRAFT_3))

    assert (result.status, result.error_code) == (OperationStatus.PERMANENT_ERROR, ErrorCode.STATUS_UPDATE_NOT_APPROVED)


async def test_missing_sequence_is_a_conflict() -> None:
    """A sequence the incident does not have is refused as a conflict."""
    result = await get_approved_update(_INCIDENT, 9, store=_store(_PUBLISHED_1, _APPROVED_2))

    assert (result.status, result.error_code) == (OperationStatus.PERMANENT_ERROR, ErrorCode.STATUS_UPDATE_CONFLICT)


async def test_other_incident_is_a_conflict() -> None:
    """A sequence held only by another incident is refused as a conflict for this one."""
    result = await get_approved_update("inc-uuid-other", 2, store=_store(_PUBLISHED_1, _APPROVED_2))

    assert (result.status, result.error_code) == (OperationStatus.PERMANENT_ERROR, ErrorCode.STATUS_UPDATE_CONFLICT)


async def test_store_error_keeps_its_classification() -> None:
    """A failed list read is returned with its status, code and retry hint."""
    result = await get_approved_update(_INCIDENT, 1, store=_FailingStore())  # type: ignore[arg-type]

    assert (result.status, result.error_code, result.retry_after) == (
        OperationStatus.TRANSIENT_ERROR,
        ErrorCode.RATE_LIMITED,
        3,
    )
