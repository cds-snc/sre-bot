"""Tests for the security confirmation gate in filling a status-update draft with AI.

When generate_status_update_draft needs a model call for a YES or UNKNOWN
incident, the gate refuses with SECURITY_CONFIRMATION_REQUIRED before the call,
unless security_confirmed=True. Read failures also refuse with the same code. A
stale sequence and the carried-forward branch never read the flag. Refusal logs
do not carry incident text. The service runs against the in-memory store holding
one pending draft, with stubbed lookup, reader, generator and flag reader.
"""

import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from structlog.testing import capture_logs

from contracts.operations import OperationResult, OperationStatus
from contracts.operations.codes import ErrorCode
from packages.incident.core.adapters.in_memory import InMemoryStatusUpdateStore
from packages.incident.core.api import (
    IncidentSecurityFlag,
    StatusUpdate,
    StatusUpdateStage,
    StatusUpdateState,
    StatusUpdateText,
    TranscriptMessage,
)
from packages.incident.scribe.domain import NoNewInformationWording, StatusUpdateDraftOutcome, StatusUpdateEdit
from packages.incident.scribe.status_update import generate_status_update_draft

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


class _StubLookup:
    def __init__(self, result: OperationResult[str] | None = None) -> None:
        self._result = result or OperationResult.success(data=_INCIDENT)

    def find_incident_for_conversation(self, conversation_id: str) -> OperationResult[str]:
        return self._result


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


class _StubSecurityReader:
    def __init__(self, flag: IncidentSecurityFlag) -> None:
        self._flag = flag
        self.calls: list[str] = []

    def read_security_flag(self, incident_id: str) -> OperationResult[IncidentSecurityFlag]:
        self.calls.append(incident_id)
        return OperationResult.success(data=self._flag)


class _FailingSecurityReader:
    def __init__(self, error_code: str = "STORE_ERROR", status: OperationStatus = OperationStatus.TRANSIENT_ERROR) -> None:
        self._error_code = error_code
        self._status = status
        self.calls: list[str] = []

    def read_security_flag(self, incident_id: str) -> OperationResult[IncidentSecurityFlag]:
        self.calls.append(incident_id)
        if self._status == OperationStatus.TRANSIENT_ERROR:
            return OperationResult.transient_error(message="store error", error_code=self._error_code)
        else:
            return OperationResult.permanent_error(message="not found", error_code=self._error_code)


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
    lookup: _StubLookup | None = None,
    security_reader: _StubSecurityReader | _FailingSecurityReader | None = None,
    security_confirmed: bool = False,
) -> OperationResult[StatusUpdateDraftOutcome]:
    store = store if store is not None else _pending_store()
    latest = store.latest(_INCIDENT).data
    return await generate_status_update_draft(
        _CHANNEL,
        sequence if sequence is not None else (latest.sequence if latest else 1),
        current=_CURRENT,
        author="U123",
        wording=_WORDING,
        on_started=None,
        lookup=lookup or _StubLookup(),
        reader=reader or _StubReader(),
        store=store,
        generator=generator or _StubGenerator(),
        security_reader=security_reader,
        security_confirmed=security_confirmed,
        now=_NOW,
    )


class TestSecurityGateRefusesYes:
    @pytest.mark.asyncio
    async def test_refuses_yes_incident_with_security_confirmation_required(self) -> None:
        """A YES incident with security_confirmed=False refuses before any model call."""
        store = _pending_store()
        security_reader = _StubSecurityReader(IncidentSecurityFlag.YES)
        generator = _StubGenerator()

        result = await _draft(store=store, security_reader=security_reader, generator=generator)

        assert not result.is_success
        assert result.error_code == ErrorCode.SECURITY_CONFIRMATION_REQUIRED
        assert generator.calls == []
        # The pending draft is still the only record
        listed = store.list_for_incident(_INCIDENT)
        assert listed.data == (_PENDING,)

    @pytest.mark.asyncio
    async def test_refuses_yes_with_no_on_started_call(self) -> None:
        """When refusing a YES incident, on_started is never called."""
        on_started_called = False

        def mock_on_started() -> None:
            nonlocal on_started_called
            on_started_called = True

        security_reader = _StubSecurityReader(IncidentSecurityFlag.YES)
        reader = _StubReader([_human("activity", 20)])

        await generate_status_update_draft(
            _CHANNEL,
            _PENDING.sequence,
            current=_CURRENT,
            author="U123",
            wording=_WORDING,
            on_started=mock_on_started,
            lookup=_StubLookup(),
            reader=reader,
            store=_pending_store(),
            generator=_StubGenerator(),
            security_reader=security_reader,
            security_confirmed=False,
            now=_NOW,
        )

        assert not on_started_called


class TestSecurityGateRefusesUnknown:
    @pytest.mark.asyncio
    async def test_refuses_unknown_incident_with_security_confirmation_required(self) -> None:
        """An UNKNOWN incident with security_confirmed=False refuses before any model call."""
        store = _pending_store()
        security_reader = _StubSecurityReader(IncidentSecurityFlag.UNKNOWN)
        generator = _StubGenerator()

        result = await _draft(store=store, security_reader=security_reader, generator=generator)

        assert not result.is_success
        assert result.error_code == ErrorCode.SECURITY_CONFIRMATION_REQUIRED


class TestSecurityGateAllowsNo:
    @pytest.mark.asyncio
    async def test_no_incident_proceeds_without_confirmation(self) -> None:
        """A NO incident proceeds through the gate without security_confirmed."""
        store = _pending_store()
        security_reader = _StubSecurityReader(IncidentSecurityFlag.NO)

        result = await _draft(store=store, security_reader=security_reader)

        # Should succeed, not refuse at the gate
        assert result.is_success or result.error_code != ErrorCode.SECURITY_CONFIRMATION_REQUIRED


class TestSecurityGateWithConfirmed:
    @pytest.mark.asyncio
    async def test_yes_incident_proceeds_when_security_confirmed(self) -> None:
        """A YES incident with security_confirmed=True proceeds past the gate."""
        store = _pending_store()
        security_reader = _StubSecurityReader(IncidentSecurityFlag.YES)

        result = await _draft(store=store, security_reader=security_reader, security_confirmed=True)

        # Should not refuse at the gate (may fail later, but not with SECURITY_CONFIRMATION_REQUIRED)
        assert result.error_code != ErrorCode.SECURITY_CONFIRMATION_REQUIRED

    @pytest.mark.asyncio
    async def test_confirmed_does_not_call_security_reader(self) -> None:
        """When security_confirmed=True, the reader is not consulted."""
        security_reader = _FailingSecurityReader()

        await _draft(security_reader=security_reader, security_confirmed=True)

        # Reader should not be called when confirmed
        assert len(security_reader.calls) == 0


class TestSecurityGateRefusesReadFailure:
    @pytest.mark.asyncio
    async def test_refuses_on_store_error_with_security_confirmation_required(self) -> None:
        """A store error from the security reader refuses with SECURITY_CONFIRMATION_REQUIRED."""
        security_reader = _FailingSecurityReader(error_code="STORE_ERROR")

        result = await _draft(security_reader=security_reader)

        assert not result.is_success
        assert result.error_code == ErrorCode.SECURITY_CONFIRMATION_REQUIRED

    @pytest.mark.asyncio
    async def test_refuses_on_not_found_with_security_confirmation_required(self) -> None:
        """A NOT_FOUND error from the reader refuses with SECURITY_CONFIRMATION_REQUIRED."""
        security_reader = _FailingSecurityReader(error_code=ErrorCode.NOT_FOUND, status=OperationStatus.PERMANENT_ERROR)

        result = await _draft(security_reader=security_reader)

        assert not result.is_success
        assert result.error_code == ErrorCode.SECURITY_CONFIRMATION_REQUIRED


class TestSecurityGateBypassedByStaleSequence:
    @pytest.mark.asyncio
    async def test_a_stale_sequence_is_refused_before_the_flag_is_read(self) -> None:
        """A form opened on an older draft is a conflict; nothing about the incident is read."""
        security_reader = _FailingSecurityReader()

        result = await _draft(sequence=_PENDING.sequence + 1, security_reader=security_reader)

        assert result.error_code == ErrorCode.STATUS_UPDATE_CONFLICT
        assert len(security_reader.calls) == 0


class TestSecurityGateBypassedByCarriedForward:
    @pytest.mark.asyncio
    async def test_carried_forward_branch_does_not_check_reader(self) -> None:
        """CARRIED_FORWARD branch returns carried-forward without consulting the reader."""
        # No new activity and no instructions, so will go into carried-forward branch
        store = _pending_store(_record(1, StatusUpdateState.APPROVED), replace(_PENDING, sequence=2))
        reader = _StubReader([_human("before the approval", 90)])  # No new messages after the cutoff
        security_reader = _FailingSecurityReader()

        result = await _draft(store=store, reader=reader, security_reader=security_reader)

        # Should return carried-forward without checking reader
        assert result.is_success
        # Reader should not have been called
        assert len(security_reader.calls) == 0


class TestSecurityGateLogging:
    @pytest.mark.asyncio
    async def test_refusal_logs_do_not_carry_incident_text(self) -> None:
        """A refusal is logged with the incident id but never the conversation's message text.

        The stub transcript holds a distinctive message; every captured log value
        is checked for it, so a log that dumped the transcript would fail.
        """
        security_reader = _StubSecurityReader(IncidentSecurityFlag.YES)
        secret_text = "customer database credentials leaked"

        with capture_logs() as cap_logs:
            await _draft(reader=_StubReader([_human(secret_text, 20)]), security_reader=security_reader)

        refusal_logs = [log for log in cap_logs if log.get("error_code") == ErrorCode.SECURITY_CONFIRMATION_REQUIRED]
        assert refusal_logs
        for log in refusal_logs:
            assert log.get("incident_id") == _INCIDENT
            assert all(secret_text not in str(value) for value in log.values())
