"""``update_fields``: the record first, then the notice in the record's conversation.

Runs over the core in-memory fakes (incident store with its timeline, conversation),
which the core parity suites hold to the adapters' rules; a test-local subclass fails
one port or records the call order. Assertions read the fakes back in domain terms
(the stored fields, the timeline entries, the channel's posts) and the channel stage
the service returns, since the entry point renders its private lines from it.

The record is the commit point (decisions/incident-management.md): a refused command
check or a failed record write posts nothing; a failed or skipped notice is reported
and never rolls the record back.
"""

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from contracts.operations.codes import ErrorCode
from contracts.operations.result import OperationResult
from features.incident.common.vocabulary import Severity
from features.incident.core.adapters.in_memory import InMemoryIncidentConversation, InMemoryIncidentStore
from features.incident.core.api import ConversationReference, Incident, IncidentChanges, MessageReference
from features.incident.response.service.fields import FieldsChange, update_fields
from features.incident.response.service.status import StageOutcome
from tests.factories.incident import incident_on, slack_conversation

pytestmark = pytest.mark.unit

CHANNEL_ID = "C0INCIDENT"
INCIDENT_ID = "inc-1"
USER_ID = "U0INVOKER"
AT = datetime(2026, 11, 17, 15, 0, tzinfo=UTC)
NOTICE = "<@U0INVOKER> has updated the field severity to sev-1"


def _store(incident: Incident | None = None) -> InMemoryIncidentStore:
    store = InMemoryIncidentStore()
    store.seed(incident or replace(incident_on(CHANNEL_ID, INCIDENT_ID), severity=Severity.SEV2))
    return store


async def _update(
    store: InMemoryIncidentStore,
    conversations: InMemoryIncidentConversation,
    changes: IncidentChanges,
    *,
    channel_id: str = CHANNEL_ID,
) -> OperationResult[FieldsChange]:
    return await update_fields(store, conversations, slack_conversation(channel_id), changes, by=USER_ID, at=AT, notice=NOTICE)


def _changed(result: OperationResult[FieldsChange]) -> FieldsChange:
    assert result.is_success and result.data is not None, result
    return result.data


async def _stored(store: InMemoryIncidentStore) -> Incident:
    found = await store.get(INCIDENT_ID)
    assert found.data is not None
    return found.data


def _posts(conversations: InMemoryIncidentConversation) -> tuple[str, ...]:
    return tuple(conversations.posts_in(slack_conversation(CHANNEL_ID)))


async def test_a_field_update_writes_the_record_then_tells_the_channel() -> None:
    store = _store()
    conversations = InMemoryIncidentConversation(open_ids=[CHANNEL_ID])

    change = _changed(await _update(store, conversations, IncidentChanges(severity=Severity.SEV1)))

    assert (await _stored(store)).severity is Severity.SEV1
    assert change.incident.severity is Severity.SEV1
    assert change.channel.outcome is StageOutcome.DONE
    assert _posts(conversations) == (NOTICE,)


async def test_a_severity_change_appends_its_timeline_entry() -> None:
    store = _store()

    _changed(await _update(store, InMemoryIncidentConversation(open_ids=[CHANNEL_ID]), IncidentChanges(severity=Severity.SEV1)))

    [entry] = store.timeline.entries(INCIDENT_ID)
    assert (entry.posted_at, entry.author) == (AT, USER_ID)


async def test_times_and_the_security_flag_are_written_and_cleared() -> None:
    store = _store()
    conversations = InMemoryIncidentConversation(open_ids=[CHANNEL_ID])
    detected = datetime(2026, 10, 1, 13, 30, tzinfo=UTC)

    _changed(await _update(store, conversations, IncidentChanges(detected_at=detected, security_incident=True)))
    _changed(await _update(store, conversations, IncidentChanges(severity=None)))

    stored = await _stored(store)
    assert (stored.detected_at, stored.security_incident, stored.severity) == (detected, True, None)
    assert store.timeline.entries(INCIDENT_ID) != ()


async def test_the_record_is_written_before_the_notice() -> None:
    calls: list[str] = []

    class Store(InMemoryIncidentStore):
        async def update_fields(
            self, incident_id: str, changes: IncidentChanges, *, by: str, at: datetime
        ) -> OperationResult[Incident]:
            calls.append("record")
            return await super().update_fields(incident_id, changes, by=by, at=at)

    class Conversation(InMemoryIncidentConversation):
        async def post(self, conversation: ConversationReference, text: str, *, blocks=()) -> OperationResult[MessageReference]:  # type: ignore[no-untyped-def]
            calls.append("channel")
            return await super().post(conversation, text, blocks=blocks)

    store = Store()
    store.seed(incident_on(CHANNEL_ID, INCIDENT_ID))

    _changed(await _update(store, Conversation(open_ids=[CHANNEL_ID]), IncidentChanges(security_incident=True)))

    assert calls == ["record", "channel"]


async def test_a_conversation_of_no_incident_is_refused_and_nothing_is_written_or_posted() -> None:
    store = _store()
    conversations = InMemoryIncidentConversation(open_ids=[CHANNEL_ID, "C0OTHER"])

    result = await _update(store, conversations, IncidentChanges(severity=Severity.SEV1), channel_id="C0OTHER")

    assert result.error_code == ErrorCode.NOT_AN_INCIDENT
    assert (await _stored(store)).severity is Severity.SEV2
    assert _posts(conversations) == ()


async def test_a_failed_record_write_posts_nothing() -> None:
    class Store(InMemoryIncidentStore):
        async def update_fields(
            self, incident_id: str, changes: IncidentChanges, *, by: str, at: datetime
        ) -> OperationResult[Incident]:
            return OperationResult.permanent_error("conflict", ErrorCode.INCIDENT_RECORD_CONFLICT)

    store = Store()
    store.seed(incident_on(CHANNEL_ID, INCIDENT_ID))
    conversations = InMemoryIncidentConversation(open_ids=[CHANNEL_ID])

    result = await _update(store, conversations, IncidentChanges(severity=Severity.SEV1))

    assert result.error_code == ErrorCode.INCIDENT_RECORD_CONFLICT
    assert _posts(conversations) == ()


async def test_an_unwritable_conversation_skips_the_notice_and_keeps_the_record() -> None:
    store = _store()
    conversations = InMemoryIncidentConversation(archived_ids=[CHANNEL_ID])

    change = _changed(await _update(store, conversations, IncidentChanges(severity=Severity.SEV1)))

    assert (change.channel.outcome, change.channel.reason) == (StageOutcome.SKIPPED, "not_writable")
    assert (await _stored(store)).severity is Severity.SEV1


async def test_a_failed_notice_is_reported_and_the_record_is_kept() -> None:
    class Conversation(InMemoryIncidentConversation):
        async def post(self, conversation: ConversationReference, text: str, *, blocks=()) -> OperationResult[MessageReference]:  # type: ignore[no-untyped-def]
            return OperationResult.transient_error("slack down")

    store = _store()

    change = _changed(await _update(store, Conversation(open_ids=[CHANNEL_ID]), IncidentChanges(severity=Severity.SEV1)))

    assert change.channel.outcome is StageOutcome.FAILED
    assert (await _stored(store)).severity is Severity.SEV1


async def test_repeating_a_value_writes_no_change_and_posts_the_notice_again() -> None:
    """A replay changes no stored value and reruns the notice, as the legacy update announced every submission."""
    store = _store()
    conversations = InMemoryIncidentConversation(open_ids=[CHANNEL_ID])
    _changed(await _update(store, conversations, IncidentChanges(severity=Severity.SEV1)))

    change = _changed(await _update(store, conversations, IncidentChanges(severity=Severity.SEV1)))

    assert change.incident.severity is Severity.SEV1
    assert len(store.timeline.entries(INCIDENT_ID)) == 1
    assert _posts(conversations) == (NOTICE, NOTICE)


async def test_a_naive_time_is_a_programming_error() -> None:
    with pytest.raises(ValueError):
        await update_fields(
            _store(),
            InMemoryIncidentConversation(open_ids=[CHANNEL_ID]),
            slack_conversation(CHANNEL_ID),
            IncidentChanges(security_incident=True),
            by=USER_ID,
            at=datetime(2026, 11, 17, 15, 0),  # noqa: DTZ001 -- the naive time under test
            notice=NOTICE,
        )
