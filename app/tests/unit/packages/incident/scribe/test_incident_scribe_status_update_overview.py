"""Tests for reading an incident's status-update overview: the pending draft and the approved updates.

``get_status_update_overview`` resolves the conversation to its incident with
one lookup, lists the incident's records once, and returns the latest record as
the pending draft when it is a draft, beside every approved or published record
newest first. ``get_pending_status_update`` returns the overview's pending
draft, so its results are unchanged.

The store is the core's ``InMemoryStatusUpdateStore`` behind a counting wrapper
and the lookup is a counting stub, so each test asserts the exact overview and,
where it matters, the exact number of reads. Error results are compared on
status, error code and retry hint, the classification callers branch on.
"""

from collections.abc import Sequence
from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta

import pytest

from contracts.operations import OperationResult, OperationStatus
from contracts.operations.codes import ErrorCode
from packages.incident.core.adapters.in_memory import InMemoryStatusUpdateStore
from packages.incident.core.api import StatusUpdate, StatusUpdateStage, StatusUpdateState, StatusUpdateText
from packages.incident.scribe.domain import StatusUpdateOverview
from packages.incident.scribe.status_update import get_pending_status_update, get_status_update_overview

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


def _update(sequence: int, state: StatusUpdateState) -> StatusUpdate:
    created = _NOW + timedelta(minutes=sequence)
    draft = StatusUpdate(
        incident_id=_INCIDENT,
        sequence=sequence,
        state=StatusUpdateState.DRAFT,
        stage=StatusUpdateStage.IDENTIFIED,
        en=_text("en"),
        fr=_text("fr"),
        next_update_at=created,
        author="U123",
        transcript_cutoff=created,
        transcript_fingerprint="v1:sha256:abc123",
        created_at=created,
    )
    if state is StatusUpdateState.DRAFT:
        return draft
    approved = replace(draft, state=StatusUpdateState.APPROVED, approver="U0APPROVER", approved_at=created)
    if state is StatusUpdateState.APPROVED:
        return approved
    return replace(approved, state=StatusUpdateState.PUBLISHED, published_at=created)


class _CountingLookup:
    """Lookup stub answering with one fixed result and counting its calls."""

    def __init__(self, result: OperationResult[str] | None = None) -> None:
        self._result = result or OperationResult.success(data=_INCIDENT)
        self.calls: list[str] = []

    def find_incident_for_conversation(self, conversation_id: str) -> OperationResult[str]:
        self.calls.append(conversation_id)
        return self._result


class _CountingStore:
    """In-memory store wrapper that records every list read."""

    def __init__(self, *updates: StatusUpdate) -> None:
        self._inner = InMemoryStatusUpdateStore()
        for update in updates:
            self._inner.append(update)
        self.list_calls: list[str] = []

    def append(self, update: StatusUpdate) -> OperationResult[StatusUpdate]:
        raise AssertionError("the overview must not append")

    def transition(self, update: StatusUpdate, *, expected_state: StatusUpdateState) -> OperationResult[StatusUpdate]:
        raise AssertionError("the overview must not transition")

    def latest(self, incident_id: str) -> OperationResult[StatusUpdate | None]:
        raise AssertionError("the overview reads the list once, not the latest")

    def list_for_incident(self, incident_id: str) -> OperationResult[Sequence[StatusUpdate]]:
        self.list_calls.append(incident_id)
        return self._inner.list_for_incident(incident_id)


class _FailingStore:
    """Store whose list read fails with a throttling error."""

    def list_for_incident(self, incident_id: str) -> OperationResult[Sequence[StatusUpdate]]:
        return OperationResult.transient_error(message="throttled", error_code=ErrorCode.RATE_LIMITED, retry_after=3)


class TestOverview:
    def test_pending_draft_beside_approved_and_published_newest_first(self) -> None:
        """A latest draft is the pending one; approved and published records follow newest first."""
        store = _CountingStore(
            _update(1, StatusUpdateState.PUBLISHED),
            _update(2, StatusUpdateState.APPROVED),
            _update(3, StatusUpdateState.DRAFT),
        )

        result = get_status_update_overview(_CHANNEL, lookup=_CountingLookup(), store=store)

        assert result.status == OperationStatus.SUCCESS
        assert result.data == StatusUpdateOverview(
            pending=_update(3, StatusUpdateState.DRAFT),
            approved=(_update(2, StatusUpdateState.APPROVED), _update(1, StatusUpdateState.PUBLISHED)),
        )

    def test_no_pending_when_latest_is_approved(self) -> None:
        """With an approved latest record nothing is pending and every record is listed as approved."""
        store = _CountingStore(_update(1, StatusUpdateState.APPROVED), _update(2, StatusUpdateState.APPROVED))

        result = get_status_update_overview(_CHANNEL, lookup=_CountingLookup(), store=store)

        assert result.data == StatusUpdateOverview(
            pending=None,
            approved=(_update(2, StatusUpdateState.APPROVED), _update(1, StatusUpdateState.APPROVED)),
        )

    def test_pending_draft_with_no_approved_updates(self) -> None:
        """A lone draft is pending and the approved tuple is empty."""
        store = _CountingStore(_update(1, StatusUpdateState.DRAFT))

        result = get_status_update_overview(_CHANNEL, lookup=_CountingLookup(), store=store)

        assert result.data == StatusUpdateOverview(pending=_update(1, StatusUpdateState.DRAFT), approved=())

    def test_published_records_count_as_approved(self) -> None:
        """Published records are listed with the approved ones, keeping their published state."""
        store = _CountingStore(_update(1, StatusUpdateState.PUBLISHED), _update(2, StatusUpdateState.PUBLISHED))

        result = get_status_update_overview(_CHANNEL, lookup=_CountingLookup(), store=store)

        assert result.data == StatusUpdateOverview(
            pending=None,
            approved=(_update(2, StatusUpdateState.PUBLISHED), _update(1, StatusUpdateState.PUBLISHED)),
        )

    def test_empty_incident(self) -> None:
        """An incident with no records has no pending draft and no approved updates."""
        result = get_status_update_overview(_CHANNEL, lookup=_CountingLookup(), store=_CountingStore())

        assert result.status == OperationStatus.SUCCESS
        assert result.data == StatusUpdateOverview(pending=None, approved=())

    def test_one_lookup_and_one_list(self) -> None:
        """The conversation is resolved once and the resolved incident's records are listed once."""
        lookup = _CountingLookup()
        store = _CountingStore(_update(1, StatusUpdateState.APPROVED), _update(2, StatusUpdateState.DRAFT))

        get_status_update_overview(_CHANNEL, lookup=lookup, store=store)

        assert lookup.calls == [_CHANNEL]
        assert store.list_calls == [_INCIDENT]

    def test_overview_is_frozen(self) -> None:
        """The overview is an immutable value."""
        overview = StatusUpdateOverview(pending=None, approved=())

        with pytest.raises(FrozenInstanceError):
            overview.pending = _update(1, StatusUpdateState.DRAFT)  # type: ignore[misc]


class TestOverviewErrors:
    @pytest.mark.parametrize(
        "refusal",
        [
            OperationResult.error(OperationStatus.NOT_FOUND, message="no incident", error_code=ErrorCode.NOT_AN_INCIDENT),
            OperationResult.permanent_error(message="multiple incidents", error_code=ErrorCode.AMBIGUOUS_INCIDENT_CONVERSATION),
        ],
        ids=["not-an-incident", "ambiguous"],
    )
    def test_lookup_refusal_is_returned_without_listing(self, refusal: OperationResult[str]) -> None:
        """A lookup refusal is returned with its status and code, and the store is never read."""
        store = _CountingStore()

        result = get_status_update_overview(_CHANNEL, lookup=_CountingLookup(refusal), store=store)

        assert (result.status, result.error_code) == (refusal.status, refusal.error_code)
        assert store.list_calls == []

    def test_store_error_is_returned_with_its_classification(self) -> None:
        """A failed list read is returned with its status, code and retry hint."""
        result = get_status_update_overview(_CHANNEL, lookup=_CountingLookup(), store=_FailingStore())  # type: ignore[arg-type]

        assert (result.status, result.error_code, result.retry_after) == (
            OperationStatus.TRANSIENT_ERROR,
            ErrorCode.RATE_LIMITED,
            3,
        )


class TestPendingDelegates:
    @pytest.mark.parametrize(
        "states",
        [
            (StatusUpdateState.APPROVED, StatusUpdateState.DRAFT),
            (StatusUpdateState.PUBLISHED, StatusUpdateState.APPROVED),
            (),
        ],
        ids=["latest-draft", "latest-approved", "empty"],
    )
    def test_pending_equals_the_overview_pending(self, states: tuple[StatusUpdateState, ...]) -> None:
        """The pending read returns exactly the overview's pending draft for the same records."""
        records = [_update(index, state) for index, state in enumerate(states, start=1)]

        pending = get_pending_status_update(_CHANNEL, lookup=_CountingLookup(), store=_CountingStore(*records))
        overview = get_status_update_overview(_CHANNEL, lookup=_CountingLookup(), store=_CountingStore(*records))

        assert overview.data is not None
        assert (pending.status, pending.data) == (OperationStatus.SUCCESS, overview.data.pending)

    def test_pending_read_lists_once(self) -> None:
        """The pending read still resolves once and lists once."""
        lookup = _CountingLookup()
        store = _CountingStore(_update(1, StatusUpdateState.DRAFT))

        get_pending_status_update(_CHANNEL, lookup=lookup, store=store)

        assert (lookup.calls, store.list_calls) == ([_CHANNEL], [_INCIDENT])

    def test_pending_read_keeps_the_store_error(self) -> None:
        """The pending read returns the store's classified error as before."""
        result = get_pending_status_update(_CHANNEL, lookup=_CountingLookup(), store=_FailingStore())  # type: ignore[arg-type]

        assert (result.status, result.error_code, result.retry_after) == (
            OperationStatus.TRANSIENT_ERROR,
            ErrorCode.RATE_LIMITED,
            3,
        )
