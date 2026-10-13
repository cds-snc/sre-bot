"""Tests for approving an incident status update in the comms service.

Approval stores the APPROVED state with approver, approved_at and edited en/fr/stage.
Validation checks all 8 fields are non-blank before any write. Stale sequence, a
non-draft target or a stage below the latest non-draft record's stage are refused.
A repeated identical approval succeeds; a different concurrent approval is a conflict.
next_update_at is kept on the same stage and recomputed only when the stage changes.
"""

from datetime import UTC, datetime

import pytest

from contracts.operations import OperationResult, OperationStatus
from contracts.operations.codes import ErrorCode
from features.incident.comms.approval import (
    approve_status_update,
    get_draft_for_review,
)
from features.incident.comms.domain import StatusUpdateEdit
from features.incident.core.adapters.in_memory import InMemoryStatusUpdateStore
from features.incident.core.api import (
    StatusUpdate,
    StatusUpdateStage,
    StatusUpdateState,
    StatusUpdateText,
)

pytestmark = pytest.mark.unit

_NOW = datetime(2026, 10, 7, 15, 0, tzinfo=UTC)
_INCIDENT = "inc-uuid-1"


def _text(language: str, tag: str = "") -> StatusUpdateText:
    fields = ("affected_service", "impact", "current_action", "workaround")
    return StatusUpdateText(**{field: f"{language} {field}{tag}" for field in fields})


def _record(
    sequence: int,
    state: StatusUpdateState,
    *,
    stage: StatusUpdateStage = StatusUpdateStage.IDENTIFIED,
    approver: str = "U0",
    next_update_at: datetime | None = None,
) -> StatusUpdate:
    return StatusUpdate(
        incident_id=_INCIDENT,
        sequence=sequence,
        state=state,
        stage=stage,
        en=_text("en", f" #{sequence}"),
        fr=_text("fr", f" #{sequence}"),
        next_update_at=next_update_at or _NOW,
        author="U-author",
        approver=approver if state in (StatusUpdateState.APPROVED, StatusUpdateState.PUBLISHED) else None,
        approved_at=_NOW if state in (StatusUpdateState.APPROVED, StatusUpdateState.PUBLISHED) else None,
        published_at=_NOW if state is StatusUpdateState.PUBLISHED else None,
        transcript_cutoff=_NOW,
        transcript_fingerprint="v1:sha256:test",
        created_at=_NOW,
    )


def _store(*records: StatusUpdate) -> InMemoryStatusUpdateStore:
    store = InMemoryStatusUpdateStore()
    for record in records:
        store.append(record)
    return store


class TestBlankFields:
    """Tests for StatusUpdateEdit.blank_fields: a pure method checking field blankness."""

    def test_all_fields_present_returns_empty_tuple(self) -> None:
        """When all 8 fields are non-blank, validation succeeds."""

        edit = StatusUpdateEdit(
            stage=StatusUpdateStage.IDENTIFIED,
            en=_text("en"),
            fr=_text("fr"),
        )

        result = edit.blank_fields()

        assert result == ()

    @pytest.mark.parametrize(
        "blank_field,expected_names",
        [
            ("en_affected_service", ("en.affected_service",)),
            ("en_impact", ("en.impact",)),
            ("en_current_action", ("en.current_action",)),
            ("en_workaround", ("en.workaround",)),
            ("fr_affected_service", ("fr.affected_service",)),
            ("fr_impact", ("fr.impact",)),
            ("fr_current_action", ("fr.current_action",)),
            ("fr_workaround", ("fr.workaround",)),
        ],
        ids=[
            "en-affected-service",
            "en-impact",
            "en-current-action",
            "en-workaround",
            "fr-affected-service",
            "fr-impact",
            "fr-current-action",
            "fr-workaround",
        ],
    )
    def test_blank_field_names_all_8_fields(self, blank_field: str, expected_names: tuple[str]) -> None:
        """Blank fields in either language are named in the result."""

        lang, field_name = blank_field.split("_", 1)
        en_dict = {"affected_service": "x", "impact": "x", "current_action": "x", "workaround": "x"}
        fr_dict = en_dict.copy()
        if lang == "en":
            en_dict[field_name] = ""
        else:
            fr_dict[field_name] = ""

        edit = StatusUpdateEdit(
            stage=StatusUpdateStage.IDENTIFIED,
            en=StatusUpdateText(**en_dict),
            fr=StatusUpdateText(**fr_dict),
        )

        result = edit.blank_fields()

        assert result == expected_names

    def test_whitespace_only_field_treated_as_blank(self) -> None:
        """Whitespace-only field is treated as blank after trimming."""

        edit = StatusUpdateEdit(
            stage=StatusUpdateStage.IDENTIFIED,
            en=StatusUpdateText(
                affected_service="  \t  ",
                impact="valid",
                current_action="valid",
                workaround="valid",
            ),
            fr=_text("fr"),
        )

        result = edit.blank_fields()

        assert result == ("en.affected_service",)

    def test_multiple_blank_fields_returns_all_names_in_order(self) -> None:
        """Multiple blank fields are all named in the result."""

        edit = StatusUpdateEdit(
            stage=StatusUpdateStage.IDENTIFIED,
            en=StatusUpdateText(
                affected_service="",
                impact="valid",
                current_action="",
                workaround="valid",
            ),
            fr=StatusUpdateText(
                affected_service="valid",
                impact="valid",
                current_action="valid",
                workaround="",
            ),
        )

        result = edit.blank_fields()

        assert result == ("en.affected_service", "en.current_action", "fr.workaround")


class TestGetDraftForReview:
    """Tests for get_draft_for_review: returns a DRAFT at the given sequence."""

    @pytest.mark.asyncio
    async def test_returns_draft_at_sequence(self) -> None:
        """When the latest record at the sequence is a draft, it is returned."""

        draft = _record(1, StatusUpdateState.DRAFT)
        store = _store(draft)

        result = await get_draft_for_review(_INCIDENT, 1, store=store)

        assert result.is_success
        assert result.data == draft

    @pytest.mark.asyncio
    async def test_refuses_non_draft_target(self) -> None:
        """An approved record at the sequence is not a pending draft."""

        store = _store(_record(1, StatusUpdateState.APPROVED))

        result = await get_draft_for_review(_INCIDENT, 1, store=store)

        assert result.status == OperationStatus.PERMANENT_ERROR
        assert result.error_code == ErrorCode.STATUS_UPDATE_CONFLICT

    @pytest.mark.asyncio
    async def test_refuses_stale_sequence(self) -> None:
        """If the latest record is newer than the given sequence, the request is stale."""

        store = _store(
            _record(1, StatusUpdateState.APPROVED),
            _record(2, StatusUpdateState.DRAFT),
        )

        result = await get_draft_for_review(_INCIDENT, 1, store=store)

        assert result.status == OperationStatus.PERMANENT_ERROR
        assert result.error_code == ErrorCode.STATUS_UPDATE_CONFLICT

    @pytest.mark.asyncio
    async def test_store_list_error_propagates(self) -> None:
        """A store read failure is returned."""

        class FailingStore(InMemoryStatusUpdateStore):
            def list_for_incident(self, incident_id: str):
                return OperationResult.transient_error(message="throttled", error_code=ErrorCode.RATE_LIMITED)

        result = await get_draft_for_review(_INCIDENT, 1, store=FailingStore())

        assert result.status == OperationStatus.TRANSIENT_ERROR
        assert result.error_code == ErrorCode.RATE_LIMITED


class TestApproveStatusUpdate:
    """Tests for approve_status_update: validation, conflicts, stages, next_update_at."""

    @pytest.mark.asyncio
    async def test_stores_approved_with_approver_and_fields(self) -> None:
        """Approval stores the record as APPROVED with approver, approved_at, and edited fields."""

        draft = _record(1, StatusUpdateState.DRAFT)
        store = _store(draft)
        edit = StatusUpdateEdit(
            stage=StatusUpdateStage.MONITORING,
            en=StatusUpdateText(
                affected_service="New Service",
                impact="New Impact",
                current_action="New Action",
                workaround="New Workaround",
            ),
            fr=StatusUpdateText(
                affected_service="Nouveau Service",
                impact="Nouvel Impact",
                current_action="Nouvelle Action",
                workaround="Nouvelle Solution",
            ),
        )

        result = await approve_status_update(_INCIDENT, 1, approver="U-approver", edit=edit, store=store, now=_NOW)

        assert result.is_success
        assert result.data is not None
        approved = result.data
        assert approved.state == StatusUpdateState.APPROVED
        assert approved.approver == "U-approver"
        assert approved.approved_at == _NOW
        assert approved.published_at is None
        assert approved.en.affected_service == "New Service"
        assert approved.fr.impact == "Nouvel Impact"
        assert approved.stage == StatusUpdateStage.MONITORING

    @pytest.mark.asyncio
    async def test_blank_field_validation_before_any_write(self) -> None:
        """Blank field validation happens before any store read or write."""

        class CountingStore(InMemoryStatusUpdateStore):
            def __init__(self):
                super().__init__()
                self.list_calls = 0
                self.transition_calls = 0

            def list_for_incident(self, incident_id: str):
                self.list_calls += 1
                return super().list_for_incident(incident_id)

            def transition(self, update, *, expected_state):
                self.transition_calls += 1
                return super().transition(update, expected_state=expected_state)

        draft = _record(1, StatusUpdateState.DRAFT)
        store = CountingStore()
        store.append(draft)
        edit = StatusUpdateEdit(
            stage=StatusUpdateStage.IDENTIFIED,
            en=StatusUpdateText(
                affected_service="",
                impact="valid",
                current_action="valid",
                workaround="valid",
            ),
            fr=_text("fr"),
        )

        result = await approve_status_update(_INCIDENT, 1, approver="U-approver", edit=edit, store=store, now=_NOW)

        assert result.status == OperationStatus.PERMANENT_ERROR
        assert result.error_code == ErrorCode.STATUS_UPDATE_FIELDS_INVALID
        assert store.list_calls == 0
        assert store.transition_calls == 0
        assert "en.affected_service" in (result.message or "")

    @pytest.mark.asyncio
    async def test_stale_sequence_refused(self) -> None:
        """If the latest record has a newer sequence, the approval is stale."""

        store = _store(
            _record(1, StatusUpdateState.APPROVED),
            _record(2, StatusUpdateState.DRAFT),
        )
        edit = StatusUpdateEdit(
            stage=StatusUpdateStage.IDENTIFIED,
            en=_text("en"),
            fr=_text("fr"),
        )

        result = await approve_status_update(_INCIDENT, 1, approver="U-approver", edit=edit, store=store, now=_NOW)

        assert result.status == OperationStatus.PERMANENT_ERROR
        assert result.error_code == ErrorCode.STATUS_UPDATE_CONFLICT

    @pytest.mark.asyncio
    async def test_non_draft_target_refused(self) -> None:
        """An approved record at the sequence cannot be re-approved."""

        store = _store(_record(1, StatusUpdateState.APPROVED))
        edit = StatusUpdateEdit(
            stage=StatusUpdateStage.IDENTIFIED,
            en=_text("en"),
            fr=_text("fr"),
        )

        result = await approve_status_update(_INCIDENT, 1, approver="U-approver", edit=edit, store=store, now=_NOW)

        assert result.status == OperationStatus.PERMANENT_ERROR
        assert result.error_code == ErrorCode.STATUS_UPDATE_CONFLICT

    @pytest.mark.asyncio
    async def test_identical_approval_succeeds(self) -> None:
        """Approving the same record again with identical fields succeeds with the stored record."""

        stored = _record(1, StatusUpdateState.APPROVED, approver="U-approver")
        store = _store(stored)
        edit = StatusUpdateEdit(
            stage=stored.stage,
            en=stored.en,
            fr=stored.fr,
        )

        result = await approve_status_update(_INCIDENT, 1, approver="U-approver", edit=edit, store=store, now=_NOW)

        assert result.is_success
        assert result.data == stored

    @pytest.mark.asyncio
    async def test_different_concurrent_approval_conflict(self) -> None:
        """If another writer approved with different fields, the conflict is returned."""

        class RacingStore(InMemoryStatusUpdateStore):
            def __init__(self):
                super().__init__()
                self.transition_called = False

            def transition(self, update, *, expected_state):
                if not self.transition_called:
                    self.transition_called = True
                    winner = _record(1, StatusUpdateState.APPROVED, approver="U-other")
                    self.append(winner)
                    return OperationResult.permanent_error(message="conflict", error_code=ErrorCode.STATUS_UPDATE_CONFLICT)
                return super().transition(update, expected_state=expected_state)

        draft = _record(1, StatusUpdateState.DRAFT)
        store = RacingStore()
        store.append(draft)
        edit = StatusUpdateEdit(
            stage=StatusUpdateStage.IDENTIFIED,
            en=_text("en"),
            fr=_text("fr"),
        )

        result = await approve_status_update(_INCIDENT, 1, approver="U-approver", edit=edit, store=store, now=_NOW)

        assert result.status == OperationStatus.PERMANENT_ERROR
        assert result.error_code == ErrorCode.STATUS_UPDATE_CONFLICT

    @pytest.mark.asyncio
    async def test_stage_below_floor_refused(self) -> None:
        """A stage below the latest non-draft record's stage is refused."""

        store = _store(_record(1, StatusUpdateState.APPROVED, stage=StatusUpdateStage.MONITORING))
        draft = _record(2, StatusUpdateState.DRAFT, stage=StatusUpdateStage.IDENTIFIED)
        store.append(draft)
        edit = StatusUpdateEdit(
            stage=StatusUpdateStage.IDENTIFIED,
            en=_text("en"),
            fr=_text("fr"),
        )

        result = await approve_status_update(_INCIDENT, 2, approver="U-approver", edit=edit, store=store, now=_NOW)

        assert result.status == OperationStatus.PERMANENT_ERROR
        assert result.error_code == ErrorCode.STATUS_UPDATE_STAGE_BELOW_FLOOR

    @pytest.mark.asyncio
    async def test_equal_stage_accepted(self) -> None:
        """A stage equal to the latest non-draft record's stage is accepted."""

        store = _store(_record(1, StatusUpdateState.APPROVED, stage=StatusUpdateStage.MONITORING))
        draft = _record(2, StatusUpdateState.DRAFT, stage=StatusUpdateStage.MONITORING)
        store.append(draft)
        edit = StatusUpdateEdit(
            stage=StatusUpdateStage.MONITORING,
            en=_text("en"),
            fr=_text("fr"),
        )

        result = await approve_status_update(_INCIDENT, 2, approver="U-approver", edit=edit, store=store, now=_NOW)

        assert result.is_success

    @pytest.mark.asyncio
    async def test_next_update_at_kept_on_same_stage(self) -> None:
        """When the stage does not change, next_update_at is kept from the draft."""

        old_next = datetime(2026, 10, 8, 15, 0, tzinfo=UTC)
        draft = _record(1, StatusUpdateState.DRAFT, stage=StatusUpdateStage.MONITORING, next_update_at=old_next)
        store = _store(draft)
        edit = StatusUpdateEdit(
            stage=StatusUpdateStage.MONITORING,
            en=_text("en"),
            fr=_text("fr"),
        )

        result = await approve_status_update(_INCIDENT, 1, approver="U-approver", edit=edit, store=store, now=_NOW)

        assert result.is_success
        assert result.data is not None
        assert result.data.next_update_at == old_next

    @pytest.mark.asyncio
    async def test_next_update_at_recomputed_on_stage_change(self) -> None:
        """When the stage changes, next_update_at is recomputed."""

        draft = _record(1, StatusUpdateState.DRAFT, stage=StatusUpdateStage.IDENTIFIED, next_update_at=_NOW)
        store = _store(draft)
        edit = StatusUpdateEdit(
            stage=StatusUpdateStage.MONITORING,
            en=_text("en"),
            fr=_text("fr"),
        )

        result = await approve_status_update(_INCIDENT, 1, approver="U-approver", edit=edit, store=store, now=_NOW)

        assert result.is_success
        assert result.data is not None
        assert result.data.next_update_at != _NOW

    @pytest.mark.asyncio
    async def test_next_update_at_recomputed_for_resolved(self) -> None:
        """When the stage is RESOLVED, next_update_at is the current time."""

        draft = _record(1, StatusUpdateState.DRAFT, stage=StatusUpdateStage.MONITORING)
        store = _store(draft)
        edit = StatusUpdateEdit(
            stage=StatusUpdateStage.RESOLVED,
            en=_text("en"),
            fr=_text("fr"),
        )

        result = await approve_status_update(_INCIDENT, 1, approver="U-approver", edit=edit, store=store, now=_NOW)

        assert result.is_success
        assert result.data is not None
        assert result.data.next_update_at == _NOW

    @pytest.mark.asyncio
    async def test_store_list_error_propagates(self) -> None:
        """A store list error is returned."""

        class FailingStore(InMemoryStatusUpdateStore):
            def list_for_incident(self, incident_id: str):
                return OperationResult.transient_error(message="throttled", error_code=ErrorCode.RATE_LIMITED)

        edit = StatusUpdateEdit(
            stage=StatusUpdateStage.IDENTIFIED,
            en=_text("en"),
            fr=_text("fr"),
        )

        result = await approve_status_update(_INCIDENT, 1, approver="U-approver", edit=edit, store=FailingStore(), now=_NOW)

        assert result.status == OperationStatus.TRANSIENT_ERROR
        assert result.error_code == ErrorCode.RATE_LIMITED

    @pytest.mark.asyncio
    async def test_store_transition_error_propagates(self) -> None:
        """A store transition error is returned."""

        class FailingStore(InMemoryStatusUpdateStore):
            def transition(self, update, *, expected_state):
                return OperationResult.transient_error(message="throttled", error_code=ErrorCode.RATE_LIMITED)

        draft = _record(1, StatusUpdateState.DRAFT)
        store = FailingStore()
        store.append(draft)
        edit = StatusUpdateEdit(
            stage=StatusUpdateStage.IDENTIFIED,
            en=_text("en"),
            fr=_text("fr"),
        )

        result = await approve_status_update(_INCIDENT, 1, approver="U-approver", edit=edit, store=store, now=_NOW)

        assert result.status == OperationStatus.TRANSIENT_ERROR
        assert result.error_code == ErrorCode.RATE_LIMITED
