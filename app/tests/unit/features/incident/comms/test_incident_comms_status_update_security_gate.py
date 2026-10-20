"""Tests for the security confirmation gate in filling a status-update draft with AI.

When generate_status_update_draft needs a model call for a security incident,
the gate refuses with SECURITY_CONFIRMATION_REQUIRED before the call, unless
security_confirmed=True. A failed flag read also refuses with the same code. A
legacy item stored without the flag reads as not a security incident, so drafting
proceeds without confirmation. A stale sequence and the carried-forward branch
never read the flag. Refusal logs do not carry incident text. The service runs
against the in-memory status-update store holding one pending draft and an
incident store that counts flag reads, with stubbed transcript reader and
generator.
"""

import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from structlog.testing import capture_logs

from contracts.operations import OperationResult, OperationStatus
from contracts.operations.codes import ErrorCode
from contracts.workplace import WorkplaceSystem
from features.incident.comms.domain import NoNewInformationWording, StatusUpdateDraftOutcome, StatusUpdateEdit
from features.incident.comms.service import generate_status_update_draft
from features.incident.core.adapters.in_memory import InMemoryIncidentStore, InMemoryStatusUpdateStore
from features.incident.core.api import (
    IncidentStore,
    StatusUpdate,
    StatusUpdateStage,
    StatusUpdateState,
    StatusUpdateText,
    TranscriptMessage,
)
from features.incident.core.store import RecordIncidentStore, incidents_table
from infrastructure.records.in_memory import InMemoryRecordStore
from tests.factories.incident import SLACK_TENANT, incident_on, slack_conversation

pytestmark = pytest.mark.unit

_NOW = datetime(2026, 10, 7, 15, 0, tzinfo=UTC)
_INCIDENT = "inc-uuid-1"
_CHANNEL = "C123"
_WORDING = NoNewInformationWording(en="No new information.", fr="Aucune nouvelle information.")
_FIELDS = ("affected_service", "impact", "current_action", "workaround")


def _at(minutes: int) -> datetime:
    """A time ``minutes`` before ``_NOW``."""
    return _NOW - timedelta(minutes=minutes)


def _human(text: str, minutes_ago: int, author: str = "Ada") -> TranscriptMessage:
    return TranscriptMessage(author=author, text=text, posted_at=_at(minutes_ago))


def _text(language: str, tag: str = "") -> StatusUpdateText:
    return StatusUpdateText(**{field: f"{language} {field}{tag}" for field in _FIELDS})


def _record(
    sequence: int,
    state: StatusUpdateState,
    *,
    stage: StatusUpdateStage = StatusUpdateStage.IDENTIFIED,
) -> StatusUpdate:
    return StatusUpdate(
        incident_id=_INCIDENT,
        sequence=sequence,
        state=state,
        stage=stage,
        en=_text("en", f" #{sequence}"),
        fr=_text("fr", f" #{sequence}"),
        next_update_at=_at(60) + timedelta(minutes=30),
        author="U0",
        transcript_cutoff=_at(60),
        transcript_fingerprint=f"v1:sha256:prior{sequence}",
        created_at=_at(60),
    )


class _StubReader:
    def __init__(self, messages: list[TranscriptMessage] | None = None) -> None:
        self._messages = messages or [_human("activity", 20)]

    def conversation_started_at(self, conversation_id: str) -> datetime | None:
        return _at(600)

    def read_transcript(
        self,
        conversation_id: str,
        *,
        since: datetime,
        limit: int,
        exclude_own_and_system_messages: bool = False,
    ) -> list[TranscriptMessage]:
        return self._messages


class _StubGenerator:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def summarize(
        self,
        transcript: str,
        *,
        instructions: str | None = None,
        max_output_tokens: int | None = None,
    ) -> OperationResult[str]:
        self.calls.append(transcript)
        answer = {
            "stage": "identified",
            "en_affected_service": "en service",
            "en_impact": "en impact",
            "en_current_action": "en action",
            "en_workaround": "en workaround",
            "fr_affected_service": "fr service",
            "fr_impact": "fr impact",
            "fr_current_action": "fr action",
            "fr_workaround": "fr workaround",
        }
        return OperationResult.success(data=json.dumps(answer))


class _CountingIncidents(InMemoryIncidentStore):
    """Holds the one incident on the channel and counts security flag reads; ``failure`` fails each read."""

    def __init__(self, *, security_incident: bool = False, failure: OperationResult[bool] | None = None) -> None:
        super().__init__()
        self.seed(incident_on(_CHANNEL, _INCIDENT, security_incident=security_incident))
        self._failure = failure
        self.calls: list[str] = []

    def read_security_flag(self, incident_id: str) -> OperationResult[bool]:
        self.calls.append(incident_id)
        return self._failure if self._failure is not None else super().read_security_flag(incident_id)


def _legacy_item_store(**overrides: Any) -> IncidentStore:
    """The real store over one legacy item on the channel, stored without security_incident."""
    item: dict[str, Any] = {
        "id": _INCIDENT,
        "channel_id": _CHANNEL,
        "name": "Legacy incident",
        "user_id": "U0DECLARER",
        "status": "Open",
        "created_at": "1760536800.0",
    }
    item.update(overrides)
    records = InMemoryRecordStore()
    table = incidents_table("incidents")
    assert records.put(table, item).is_success
    return RecordIncidentStore(records, table, {WorkplaceSystem.SLACK: SLACK_TENANT})


_PENDING = _record(1, StatusUpdateState.DRAFT)
_CURRENT = StatusUpdateEdit(stage=_PENDING.stage, en=_PENDING.en, fr=_PENDING.fr)


def _pending_store(*records: StatusUpdate) -> InMemoryStatusUpdateStore:
    """A store holding ``records``, or only ``_PENDING`` when none are given."""
    store = InMemoryStatusUpdateStore()
    for record in records or (_PENDING,):
        store.append(record)
    return store


async def _draft(
    *,
    store: InMemoryStatusUpdateStore | None = None,
    sequence: int | None = None,
    reader: _StubReader | None = None,
    generator: _StubGenerator | None = None,
    incidents: IncidentStore | None = None,
    security_confirmed: bool = False,
) -> OperationResult[StatusUpdateDraftOutcome]:
    store = store if store is not None else _pending_store()
    latest = store.latest(_INCIDENT).data
    return await generate_status_update_draft(
        incidents if incidents is not None else _CountingIncidents(),
        slack_conversation(_CHANNEL),
        sequence if sequence is not None else (latest.sequence if latest else 1),
        current=_CURRENT,
        author="U123",
        wording=_WORDING,
        on_started=None,
        reader=reader or _StubReader(),
        store=store,
        generator=generator or _StubGenerator(),
        security_confirmed=security_confirmed,
        now=_NOW,
    )


class TestSecurityGateRefusesASecurityIncident:
    @pytest.mark.asyncio
    async def test_refuses_a_security_incident_with_security_confirmation_required(self) -> None:
        """A security incident with security_confirmed=False refuses before any model call."""
        store = _pending_store()
        generator = _StubGenerator()

        result = await _draft(store=store, incidents=_CountingIncidents(security_incident=True), generator=generator)

        assert not result.is_success
        assert result.error_code == ErrorCode.SECURITY_CONFIRMATION_REQUIRED
        assert generator.calls == []
        # The pending draft is still the only record
        listed = store.list_for_incident(_INCIDENT)
        assert listed.data == (_PENDING,)

    @pytest.mark.asyncio
    async def test_refuses_a_security_incident_with_no_on_started_call(self) -> None:
        """When refusing a security incident, on_started is never called."""
        on_started_called = False

        def mock_on_started() -> None:
            nonlocal on_started_called
            on_started_called = True

        await generate_status_update_draft(
            _CountingIncidents(security_incident=True),
            slack_conversation(_CHANNEL),
            _PENDING.sequence,
            current=_CURRENT,
            author="U123",
            wording=_WORDING,
            on_started=mock_on_started,
            reader=_StubReader([_human("activity", 20)]),
            store=_pending_store(),
            generator=_StubGenerator(),
            security_confirmed=False,
            now=_NOW,
        )

        assert not on_started_called


class TestSecurityGateAllowsANonSecurityIncident:
    @pytest.mark.asyncio
    async def test_a_non_security_incident_is_drafted_without_confirmation(self) -> None:
        """A false flag passes the gate: the model is called once and the draft is stored."""
        generator = _StubGenerator()
        incidents = _CountingIncidents(security_incident=False)

        result = await _draft(incidents=incidents, generator=generator)

        assert result.is_success
        assert len(generator.calls) == 1
        assert incidents.calls == [_INCIDENT]

    @pytest.mark.asyncio
    async def test_a_legacy_incident_without_a_stored_flag_is_drafted_without_confirmation(self) -> None:
        """A legacy item stored before the flag existed reads as false, so the gate does not fire."""
        generator = _StubGenerator()

        result = await _draft(incidents=_legacy_item_store(), generator=generator)

        assert result.is_success
        assert len(generator.calls) == 1

    @pytest.mark.asyncio
    async def test_a_legacy_incident_stored_as_a_security_incident_is_refused(self) -> None:
        """A legacy item with security_incident true still needs the responder's confirmation."""
        result = await _draft(incidents=_legacy_item_store(security_incident=True))

        assert result.error_code == ErrorCode.SECURITY_CONFIRMATION_REQUIRED


class TestSecurityGateWithConfirmed:
    @pytest.mark.asyncio
    async def test_a_security_incident_proceeds_when_security_confirmed(self) -> None:
        """A security incident with security_confirmed=True is drafted."""
        generator = _StubGenerator()

        result = await _draft(incidents=_CountingIncidents(security_incident=True), generator=generator, security_confirmed=True)

        assert result.is_success
        assert len(generator.calls) == 1

    @pytest.mark.asyncio
    async def test_confirmed_does_not_read_the_flag(self) -> None:
        """When security_confirmed=True, the flag is not read."""
        incidents = _CountingIncidents()

        await _draft(incidents=incidents, security_confirmed=True)

        assert incidents.calls == []


class TestSecurityGateRefusesReadFailure:
    @pytest.mark.asyncio
    async def test_refuses_on_store_error_with_security_confirmation_required(self) -> None:
        """A store error reading the flag refuses with SECURITY_CONFIRMATION_REQUIRED, never as false."""
        failure: OperationResult[bool] = OperationResult.transient_error(message="store error", error_code="STORE_ERROR")
        generator = _StubGenerator()

        result = await _draft(incidents=_CountingIncidents(failure=failure), generator=generator)

        assert not result.is_success
        assert result.error_code == ErrorCode.SECURITY_CONFIRMATION_REQUIRED
        assert generator.calls == []

    @pytest.mark.asyncio
    async def test_refuses_on_not_found_with_security_confirmation_required(self) -> None:
        """A NOT_FOUND read refuses with SECURITY_CONFIRMATION_REQUIRED."""
        failure: OperationResult[bool] = OperationResult.error(
            OperationStatus.NOT_FOUND, message="not found", error_code=ErrorCode.NOT_AN_INCIDENT
        )

        result = await _draft(incidents=_CountingIncidents(failure=failure))

        assert not result.is_success
        assert result.error_code == ErrorCode.SECURITY_CONFIRMATION_REQUIRED


class TestSecurityGateBypassedByStaleSequence:
    @pytest.mark.asyncio
    async def test_a_stale_sequence_is_refused_before_the_flag_is_read(self) -> None:
        """A form opened on an older draft is a conflict; the flag is not read."""
        incidents = _CountingIncidents()

        result = await _draft(sequence=_PENDING.sequence + 1, incidents=incidents)

        assert result.error_code == ErrorCode.STATUS_UPDATE_CONFLICT
        assert incidents.calls == []


class TestSecurityGateBypassedByCarriedForward:
    @pytest.mark.asyncio
    async def test_carried_forward_branch_does_not_read_the_flag(self) -> None:
        """With nothing new and no instructions the fields are carried forward without reading the flag."""
        store = _pending_store(_record(1, StatusUpdateState.APPROVED), replace(_PENDING, sequence=2))
        reader = _StubReader([_human("before the approval", 90)])
        incidents = _CountingIncidents(security_incident=True)

        result = await _draft(store=store, reader=reader, incidents=incidents)

        assert result.is_success
        assert incidents.calls == []


class TestSecurityGateLogging:
    @pytest.mark.asyncio
    async def test_refusal_logs_do_not_carry_incident_text(self) -> None:
        """A refusal is logged with the incident id but never the conversation's message text.

        The stub transcript holds a distinctive message; every captured log value
        is checked for it, so a log that dumped the transcript would fail.
        """
        secret_text = "customer database credentials leaked"

        with capture_logs() as cap_logs:
            await _draft(reader=_StubReader([_human(secret_text, 20)]), incidents=_CountingIncidents(security_incident=True))

        refusal_logs = [log for log in cap_logs if log.get("error_code") == ErrorCode.SECURITY_CONFIRMATION_REQUIRED]
        assert refusal_logs
        for log in refusal_logs:
            assert log.get("incident_id") == _INCIDENT
            assert all(secret_text not in str(value) for value in log.values())
