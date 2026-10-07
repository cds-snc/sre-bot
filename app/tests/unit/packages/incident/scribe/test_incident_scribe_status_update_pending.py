"""Tests for retrieving the pending status update draft.

get_pending_status_update looks up the conversation's incident, reads the pending
draft when it exists, returns None otherwise, and classifies errors.
"""

from collections.abc import Sequence
from datetime import UTC, datetime

import pytest

from contracts.operations import OperationResult, OperationStatus
from contracts.operations.codes import ErrorCode
from packages.incident.core.adapters.in_memory import InMemoryStatusUpdateStore
from packages.incident.core.api import StatusUpdate, StatusUpdateStage, StatusUpdateState, StatusUpdateText
from packages.incident.scribe.status_update import get_pending_status_update

pytestmark = pytest.mark.unit

_INCIDENT = "inc-uuid-1"
_CHANNEL = "C123"
_NOW = datetime(2026, 10, 7, 15, 0, tzinfo=UTC)


def _text(language: str) -> StatusUpdateText:
    return StatusUpdateText(
        affected_service=f"{language} service",
        impact=f"{language} impact",
        current_action=f"{language} action",
        workaround=f"{language} workaround",
    )


def _update(sequence: int, state: StatusUpdateState, stage: StatusUpdateStage = StatusUpdateStage.IDENTIFIED) -> StatusUpdate:
    return StatusUpdate(
        incident_id=_INCIDENT,
        sequence=sequence,
        state=state,
        stage=stage,
        en=_text("en"),
        fr=_text("fr"),
        next_update_at=_NOW,
        author="U123",
        transcript_cutoff=_NOW,
        transcript_fingerprint="v1:sha256:abc123",
        created_at=_NOW,
    )


class _StubLookup:
    def __init__(self, result: OperationResult[str] | None = None) -> None:
        self._result = result or OperationResult.success(data=_INCIDENT)

    def find_incident_for_conversation(self, conversation_id: str) -> OperationResult[str]:
        return self._result


def _store(*updates: StatusUpdate) -> InMemoryStatusUpdateStore:
    store = InMemoryStatusUpdateStore()
    for update in updates:
        store.append(update)
    return store


def test_returns_the_latest_draft_when_it_exists():
    """When the incident has a draft, it is returned regardless of approved updates."""
    store = _store(
        _update(1, StatusUpdateState.APPROVED),
        _update(2, StatusUpdateState.DRAFT),
    )
    lookup = _StubLookup()

    result = get_pending_status_update(_CHANNEL, lookup=lookup, store=store)

    assert result.is_success
    assert result.data is not None
    assert result.data.sequence == 2
    assert result.data.state == StatusUpdateState.DRAFT


def test_returns_none_when_latest_is_approved():
    """When there is no draft, None is returned."""
    store = _store(
        _update(1, StatusUpdateState.APPROVED),
        _update(2, StatusUpdateState.APPROVED),
    )
    lookup = _StubLookup()

    result = get_pending_status_update(_CHANNEL, lookup=lookup, store=store)

    assert result.is_success
    assert result.data is None


def test_returns_none_when_no_updates_exist():
    """When the incident has no updates at all, None is returned."""
    store = InMemoryStatusUpdateStore()
    lookup = _StubLookup()

    result = get_pending_status_update(_CHANNEL, lookup=lookup, store=store)

    assert result.is_success
    assert result.data is None


def test_returns_not_an_incident_when_lookup_fails_with_not_found():
    """A conversation with no incident returns NOT_FOUND with NOT_AN_INCIDENT."""
    lookup = _StubLookup(
        OperationResult.error(
            OperationStatus.NOT_FOUND,
            message="no incident",
            error_code=ErrorCode.NOT_AN_INCIDENT,
        )
    )
    store = _store()

    result = get_pending_status_update(_CHANNEL, lookup=lookup, store=store)

    assert result.status == OperationStatus.NOT_FOUND
    assert result.error_code == ErrorCode.NOT_AN_INCIDENT


def test_returns_ambiguous_when_lookup_fails_with_ambiguous():
    """A conversation that maps to multiple incidents returns PERMANENT_ERROR with AMBIGUOUS_INCIDENT_CONVERSATION."""
    lookup = _StubLookup(
        OperationResult.permanent_error(
            message="multiple incidents",
            error_code=ErrorCode.AMBIGUOUS_INCIDENT_CONVERSATION,
        )
    )
    store = _store()

    result = get_pending_status_update(_CHANNEL, lookup=lookup, store=store)

    assert result.status == OperationStatus.PERMANENT_ERROR
    assert result.error_code == ErrorCode.AMBIGUOUS_INCIDENT_CONVERSATION


def test_returns_store_error_when_list_fails():
    """A store failure is returned to the caller."""
    lookup = _StubLookup()

    class _FailingStore:
        def list_for_incident(self, incident_id: str) -> OperationResult[Sequence[StatusUpdate]]:
            return OperationResult.transient_error(
                message="throttled",
                error_code=ErrorCode.RATE_LIMITED,
                retry_after=3,
            )

    store = _FailingStore()  # type: ignore[assignment]

    result = get_pending_status_update(_CHANNEL, lookup=lookup, store=store)

    assert result.status == OperationStatus.TRANSIENT_ERROR
    assert result.error_code == ErrorCode.RATE_LIMITED
    assert result.retry_after == 3
