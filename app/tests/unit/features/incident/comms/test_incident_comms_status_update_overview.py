"""Tests for reading an incident's status-update overview: the pending draft and the approved updates.

``get_status_update_overview`` resolves the conversation to its incident with
one incident-store read, lists the incident's records once, and returns the latest record as
the pending draft when it is a draft, beside every approved or published record
newest first.

The store is the core's ``InMemoryStatusUpdateStore`` behind a counting wrapper
and the incident store is an ``InMemoryIncidentStore`` holding one incident on
the channel that counts conversation reads, so each test asserts the exact overview and,
where it matters, the exact number of reads. Error results are compared on
status, error code and retry hint, the classification callers branch on.
"""

from collections.abc import Sequence
from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta
from typing import Self

import pytest

from contracts.operations import OperationResult, OperationStatus
from contracts.operations.codes import ErrorCode
from features.incident.comms.domain import StatusUpdateOverview
from features.incident.comms.service.history import get_status_update_overview
from features.incident.core.adapters.in_memory import InMemoryIncidentStore, InMemoryStatusUpdateStore
from features.incident.core.api import (
    ConversationReference,
    Incident,
    StatusUpdate,
    StatusUpdateStage,
    StatusUpdateState,
    StatusUpdateText,
)
from tests.factories.incident import incident_on, slack_conversation

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


_CONVERSATION = slack_conversation(_CHANNEL)


class _CountingIncidents(InMemoryIncidentStore):
    """Holds the one incident on the channel and counts conversation reads; ``result`` replaces each answer."""

    def __init__(self, result: OperationResult[Incident] | None = None) -> None:
        super().__init__()
        self.seed(incident_on(_CHANNEL, _INCIDENT))
        self._result = result
        self.calls: list[ConversationReference] = []

    async def find_by_conversation(self, conversation: ConversationReference) -> OperationResult[Incident]:
        self.calls.append(conversation)
        return self._result if self._result is not None else await super().find_by_conversation(conversation)


class _CountingStore:
    """In-memory store wrapper that records every list read."""

    def __init__(self) -> None:
        self._inner = InMemoryStatusUpdateStore()
        self.list_calls: list[str] = []

    @classmethod
    async def seeded(cls, *updates: StatusUpdate) -> Self:
        """A store holding ``updates``, seeded without recording a list read."""
        store = cls()
        for update in updates:
            await store._inner.append(update)
        return store

    async def append(self, update: StatusUpdate) -> OperationResult[StatusUpdate]:
        raise AssertionError("the overview must not append")

    async def transition(self, update: StatusUpdate, *, expected_state: StatusUpdateState) -> OperationResult[StatusUpdate]:
        raise AssertionError("the overview must not transition")

    async def latest(self, incident_id: str) -> OperationResult[StatusUpdate | None]:
        raise AssertionError("the overview reads the list once, not the latest")

    async def list_for_incident(self, incident_id: str) -> OperationResult[Sequence[StatusUpdate]]:
        self.list_calls.append(incident_id)
        return await self._inner.list_for_incident(incident_id)


class _FailingStore:
    """Store whose list read fails with a throttling error."""

    async def list_for_incident(self, incident_id: str) -> OperationResult[Sequence[StatusUpdate]]:
        return OperationResult.transient_error(message="throttled", error_code=ErrorCode.RATE_LIMITED, retry_after=3)


class TestOverview:
    async def test_pending_draft_beside_approved_and_published_newest_first(self) -> None:
        """A latest draft is the pending one; approved and published records follow newest first."""
        store = await _CountingStore.seeded(
            _update(1, StatusUpdateState.PUBLISHED),
            _update(2, StatusUpdateState.APPROVED),
            _update(3, StatusUpdateState.DRAFT),
        )

        result = await get_status_update_overview(_CountingIncidents(), _CONVERSATION, store=store)

        assert result.status == OperationStatus.SUCCESS
        assert result.data == StatusUpdateOverview(
            pending=_update(3, StatusUpdateState.DRAFT),
            approved=(_update(2, StatusUpdateState.APPROVED), _update(1, StatusUpdateState.PUBLISHED)),
        )

    async def test_no_pending_when_latest_is_approved(self) -> None:
        """With an approved latest record nothing is pending and every record is listed as approved."""
        store = await _CountingStore.seeded(_update(1, StatusUpdateState.APPROVED), _update(2, StatusUpdateState.APPROVED))

        result = await get_status_update_overview(_CountingIncidents(), _CONVERSATION, store=store)

        assert result.data == StatusUpdateOverview(
            pending=None,
            approved=(_update(2, StatusUpdateState.APPROVED), _update(1, StatusUpdateState.APPROVED)),
        )

    async def test_pending_draft_with_no_approved_updates(self) -> None:
        """A lone draft is pending and the approved tuple is empty."""
        store = await _CountingStore.seeded(_update(1, StatusUpdateState.DRAFT))

        result = await get_status_update_overview(_CountingIncidents(), _CONVERSATION, store=store)

        assert result.data == StatusUpdateOverview(pending=_update(1, StatusUpdateState.DRAFT), approved=())

    async def test_published_records_count_as_approved(self) -> None:
        """Published records are listed with the approved ones, keeping their published state."""
        store = await _CountingStore.seeded(_update(1, StatusUpdateState.PUBLISHED), _update(2, StatusUpdateState.PUBLISHED))

        result = await get_status_update_overview(_CountingIncidents(), _CONVERSATION, store=store)

        assert result.data == StatusUpdateOverview(
            pending=None,
            approved=(_update(2, StatusUpdateState.PUBLISHED), _update(1, StatusUpdateState.PUBLISHED)),
        )

    async def test_empty_incident(self) -> None:
        """An incident with no records has no pending draft and no approved updates."""
        result = await get_status_update_overview(_CountingIncidents(), _CONVERSATION, store=await _CountingStore.seeded())

        assert result.status == OperationStatus.SUCCESS
        assert result.data == StatusUpdateOverview(pending=None, approved=())

    async def test_one_incident_read_and_one_list(self) -> None:
        """The conversation is resolved once and the resolved incident's records are listed once."""
        incidents = _CountingIncidents()
        store = await _CountingStore.seeded(_update(1, StatusUpdateState.APPROVED), _update(2, StatusUpdateState.DRAFT))

        await get_status_update_overview(incidents, _CONVERSATION, store=store)

        assert incidents.calls == [_CONVERSATION]
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
    async def test_incident_refusal_is_returned_without_listing(self, refusal: OperationResult[Incident]) -> None:
        """An incident-store refusal is returned with its status and code, and the store is never read."""
        store = await _CountingStore.seeded()

        result = await get_status_update_overview(_CountingIncidents(refusal), _CONVERSATION, store=store)

        assert (result.status, result.error_code) == (refusal.status, refusal.error_code)
        assert store.list_calls == []

    async def test_store_error_is_returned_with_its_classification(self) -> None:
        """A failed list read is returned with its status, code and retry hint."""
        result = await get_status_update_overview(_CountingIncidents(), _CONVERSATION, store=_FailingStore())  # type: ignore[arg-type]

        assert (result.status, result.error_code, result.retry_after) == (
            OperationStatus.TRANSIENT_ERROR,
            ErrorCode.RATE_LIMITED,
            3,
        )
