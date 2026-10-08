"""Tests for marking an approved status update as published or not published.

``set_published`` moves one record between approved and published with a single
store transition conditioned on the state it read. Publishing records the time
and the person; marking it not published clears both. A request whose target
state is already stored is success with no write, a draft is refused as not
approved and a missing sequence is a conflict. When the conditional write loses
a race the record is read once more: if it now sits in the requested state the
request is success, otherwise it is a conflict. Other store errors keep their
classification.

Records live in the core's ``InMemoryStatusUpdateStore``, wrapped by a
recording store that logs every read and write so the tests can prove the
transition is the only write and count re-reads. Races are staged inside the
wrapper's ``transition``: the competing write lands on the real in-memory store
first, so the conflict returned is the real store's ``OperationResult``. A fixed
``now`` makes the stored publication time exact, and every record is compared
whole.
"""

from collections.abc import Sequence
from dataclasses import replace
from datetime import UTC, datetime

import pytest

from contracts.operations import OperationResult, OperationStatus
from contracts.operations.codes import ErrorCode
from packages.incident.core.adapters.in_memory import InMemoryStatusUpdateStore
from packages.incident.core.api import StatusUpdate, StatusUpdateStage, StatusUpdateState, StatusUpdateText
from packages.incident.scribe.status_update_history import set_published

pytestmark = pytest.mark.unit

_INCIDENT = "inc-uuid-1"
_ACTOR = "U0ACTOR"
_OTHER = "U0OTHER"
_NOW = datetime(2026, 10, 7, 15, 0, tzinfo=UTC)
_APPROVED_AT = datetime(2026, 10, 7, 14, 0, tzinfo=UTC)
_EARLIER_PUBLISH = datetime(2026, 10, 7, 14, 30, tzinfo=UTC)


def _text(language: str) -> StatusUpdateText:
    return StatusUpdateText(
        affected_service=f"{language} service",
        impact=f"{language} impact",
        current_action=f"{language} action",
        workaround=f"{language} workaround",
    )


_DRAFT = StatusUpdate(
    incident_id=_INCIDENT,
    sequence=1,
    state=StatusUpdateState.DRAFT,
    stage=StatusUpdateStage.IDENTIFIED,
    en=_text("en"),
    fr=_text("fr"),
    next_update_at=_NOW,
    author="U0AUTHOR",
    transcript_cutoff=_APPROVED_AT,
    transcript_fingerprint="v1:sha256:abc123",
    created_at=_APPROVED_AT,
)
_APPROVED = replace(_DRAFT, state=StatusUpdateState.APPROVED, approver="U0APPROVER", approved_at=_APPROVED_AT)


def _published(publisher: str = _OTHER, at: datetime = _EARLIER_PUBLISH) -> StatusUpdate:
    """The approved record as stored once ``publisher`` marked it published at ``at``."""
    return replace(_APPROVED, state=StatusUpdateState.PUBLISHED, published_at=at, published_by=publisher)


class _RecordingStore:
    """In-memory store wrapper that logs every call and can stage a competing write.

    ``calls`` names each store method in call order. ``transitions`` keeps the
    record and expected state of each transition. ``race`` is written to the
    inner store (from its current state) just before the first transition is
    attempted, as a concurrent writer would. ``transition_result`` replaces the
    transition's answer without touching the inner store.
    """

    def __init__(self, *updates: StatusUpdate) -> None:
        self._inner = InMemoryStatusUpdateStore()
        for update in updates:
            self._inner.append(update)
        self.calls: list[str] = []
        self.transitions: list[tuple[StatusUpdate, StatusUpdateState]] = []
        self.race: tuple[StatusUpdate, StatusUpdateState] | None = None
        self.transition_result: OperationResult[StatusUpdate] | None = None
        self.list_result: OperationResult[Sequence[StatusUpdate]] | None = None

    def append(self, update: StatusUpdate) -> OperationResult[StatusUpdate]:
        self.calls.append("append")
        return self._inner.append(update)

    def transition(self, update: StatusUpdate, *, expected_state: StatusUpdateState) -> OperationResult[StatusUpdate]:
        self.calls.append("transition")
        self.transitions.append((update, expected_state))
        if self.race is not None:
            winner, winner_expected = self.race
            self.race = None
            self._inner.transition(winner, expected_state=winner_expected)
        if self.transition_result is not None:
            return self.transition_result
        return self._inner.transition(update, expected_state=expected_state)

    def latest(self, incident_id: str) -> OperationResult[StatusUpdate | None]:
        self.calls.append("latest")
        return self._inner.latest(incident_id)

    def list_for_incident(self, incident_id: str) -> OperationResult[Sequence[StatusUpdate]]:
        self.calls.append("list_for_incident")
        if self.list_result is not None:
            return self.list_result
        return self._inner.list_for_incident(incident_id)

    def stored(self, sequence: int = 1) -> StatusUpdate | None:
        """The record held by the inner store at ``sequence``, read without logging a call."""
        listed = self._inner.list_for_incident(_INCIDENT).data or ()
        return next((update for update in listed if update.sequence == sequence), None)

    def writes(self) -> list[str]:
        return [name for name in self.calls if name in {"append", "transition"}]


class TestPublish:
    async def test_records_the_actor_and_the_time(self) -> None:
        """Publishing an approved update stores it as published at ``now`` by the actor and returns that record."""
        store = _RecordingStore(_APPROVED)

        result = await set_published(_INCIDENT, 1, published=True, actor=_ACTOR, now=_NOW, store=store)

        expected = _published(publisher=_ACTOR, at=_NOW)
        assert result.is_success
        assert result.data == expected
        assert store.stored() == expected

    async def test_is_one_transition_from_approved(self) -> None:
        """The only write is one transition of the published record, conditioned on the approved state read."""
        store = _RecordingStore(_APPROVED)

        await set_published(_INCIDENT, 1, published=True, actor=_ACTOR, now=_NOW, store=store)

        assert store.writes() == ["transition"]
        assert store.transitions == [(_published(publisher=_ACTOR, at=_NOW), StatusUpdateState.APPROVED)]

    async def test_repeat_is_success_without_a_write(self) -> None:
        """A publish of an update that is already published returns the stored record and writes nothing."""
        stored = _published()
        store = _RecordingStore(stored)

        result = await set_published(_INCIDENT, 1, published=True, actor=_ACTOR, now=_NOW, store=store)

        assert result.is_success
        assert result.data == stored
        assert store.writes() == []
        assert store.stored() == stored

    async def test_now_defaults_to_the_current_time(self) -> None:
        """Without ``now`` the publication time is the current, timezone-aware time."""
        store = _RecordingStore(_APPROVED)
        before = datetime.now(UTC)

        result = await set_published(_INCIDENT, 1, published=True, actor=_ACTOR, store=store)

        after = datetime.now(UTC)
        assert result.data is not None
        assert result.data.published_at is not None
        assert before <= result.data.published_at <= after


class TestMarkNotPublished:
    async def test_clears_the_publication_time_and_person(self) -> None:
        """Undo stores the update as approved again, with neither published_at nor published_by."""
        store = _RecordingStore(_published())

        result = await set_published(_INCIDENT, 1, published=False, actor=_ACTOR, now=_NOW, store=store)

        assert result.is_success
        assert result.data == _APPROVED
        assert store.stored() == _APPROVED

    async def test_is_one_transition_from_published(self) -> None:
        """The only write is one transition of the approved record, conditioned on the published state read."""
        store = _RecordingStore(_published())

        await set_published(_INCIDENT, 1, published=False, actor=_ACTOR, now=_NOW, store=store)

        assert store.writes() == ["transition"]
        assert store.transitions == [(_APPROVED, StatusUpdateState.PUBLISHED)]

    async def test_repeat_is_success_without_a_write(self) -> None:
        """Marking an update that is already not published returns the stored record and writes nothing."""
        store = _RecordingStore(_APPROVED)

        result = await set_published(_INCIDENT, 1, published=False, actor=_ACTOR, now=_NOW, store=store)

        assert result.is_success
        assert result.data == _APPROVED
        assert store.writes() == []


class TestRefusals:
    @pytest.mark.parametrize("published", [True, False], ids=["publish", "undo"])
    async def test_a_draft_is_refused_as_not_approved(self, published: bool) -> None:
        """A draft has no copy-ready text to publish; the request is refused and nothing is written."""
        store = _RecordingStore(_DRAFT)

        result = await set_published(_INCIDENT, 1, published=published, actor=_ACTOR, now=_NOW, store=store)

        assert result.status is OperationStatus.PERMANENT_ERROR
        assert result.error_code == ErrorCode.STATUS_UPDATE_NOT_APPROVED
        assert store.writes() == []
        assert store.stored() == _DRAFT

    @pytest.mark.parametrize("published", [True, False], ids=["publish", "undo"])
    async def test_a_missing_sequence_is_a_conflict(self, published: bool) -> None:
        """A sequence the incident does not have means the view is stale; nothing is written or created."""
        store = _RecordingStore(_APPROVED)

        result = await set_published(_INCIDENT, 9, published=published, actor=_ACTOR, now=_NOW, store=store)

        assert result.status is OperationStatus.PERMANENT_ERROR
        assert result.error_code == ErrorCode.STATUS_UPDATE_CONFLICT
        assert store.writes() == []
        assert store.stored(9) is None


class TestLostRace:
    async def test_another_publish_that_landed_first_is_success(self) -> None:
        """Someone else published between the read and the write; the one re-read finds the target state and succeeds.

        The returned record is the winner's, so the view shows who actually
        marked it published, and the transition is not retried.
        """
        winner = _published(publisher=_OTHER, at=_EARLIER_PUBLISH)
        store = _RecordingStore(_APPROVED)
        store.race = (winner, StatusUpdateState.APPROVED)

        result = await set_published(_INCIDENT, 1, published=True, actor=_ACTOR, now=_NOW, store=store)

        assert result.is_success
        assert result.data == winner
        assert store.writes() == ["transition"]
        assert store.stored() == winner

    async def test_another_undo_that_landed_first_is_success(self) -> None:
        """Someone else marked it not published first; the stored record is the one requested, so the undo succeeds."""
        store = _RecordingStore(_published())
        store.race = (_APPROVED, StatusUpdateState.PUBLISHED)

        result = await set_published(_INCIDENT, 1, published=False, actor=_ACTOR, now=_NOW, store=store)

        assert result.is_success
        assert result.data == _APPROVED
        assert store.writes() == ["transition"]

    async def test_a_lost_write_whose_record_is_not_in_the_target_state_is_a_conflict(self) -> None:
        """The store reports a conflict and the re-read still shows approved, so the publish is refused, not retried."""
        store = _RecordingStore(_APPROVED)
        store.transition_result = OperationResult.permanent_error(
            message="The status update was changed or taken by another writer.",
            error_code=ErrorCode.STATUS_UPDATE_CONFLICT,
        )

        result = await set_published(_INCIDENT, 1, published=True, actor=_ACTOR, now=_NOW, store=store)

        assert result.status is OperationStatus.PERMANENT_ERROR
        assert result.error_code == ErrorCode.STATUS_UPDATE_CONFLICT
        assert store.writes() == ["transition"]
        assert store.stored() == _APPROVED

    async def test_a_lost_write_rereads_exactly_once(self) -> None:
        """One read before the write and one re-read after the conflict; no retry loop."""
        store = _RecordingStore(_APPROVED)
        store.transition_result = OperationResult.permanent_error(
            message="The status update was changed or taken by another writer.",
            error_code=ErrorCode.STATUS_UPDATE_CONFLICT,
        )

        await set_published(_INCIDENT, 1, published=True, actor=_ACTOR, now=_NOW, store=store)

        assert store.calls == ["list_for_incident", "transition", "list_for_incident"]


class TestStoreErrors:
    async def test_a_failed_read_keeps_its_classification(self) -> None:
        """A throttled list read is returned with its status, code and retry hint, and nothing is written."""
        store = _RecordingStore(_APPROVED)
        store.list_result = OperationResult.transient_error(message="throttled", error_code=ErrorCode.RATE_LIMITED, retry_after=3)

        result = await set_published(_INCIDENT, 1, published=True, actor=_ACTOR, now=_NOW, store=store)

        assert (result.status, result.error_code, result.retry_after) == (
            OperationStatus.TRANSIENT_ERROR,
            ErrorCode.RATE_LIMITED,
            3,
        )
        assert store.writes() == []

    async def test_a_failed_write_keeps_its_classification_without_a_reread(self) -> None:
        """A throttled transition is returned as is; only a conflict earns the re-read."""
        store = _RecordingStore(_APPROVED)
        store.transition_result = OperationResult.transient_error(
            message="throttled", error_code=ErrorCode.RATE_LIMITED, retry_after=3
        )

        result = await set_published(_INCIDENT, 1, published=True, actor=_ACTOR, now=_NOW, store=store)

        assert (result.status, result.error_code, result.retry_after) == (
            OperationStatus.TRANSIENT_ERROR,
            ErrorCode.RATE_LIMITED,
            3,
        )
        assert store.calls == ["list_for_incident", "transition"]
