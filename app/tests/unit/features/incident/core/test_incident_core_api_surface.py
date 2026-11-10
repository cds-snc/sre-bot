"""Unit tests for the public surface of the incident core package."""

import dataclasses
import inspect
from collections.abc import Iterator, Sequence
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from slack_sdk import WebClient

import features.incident.core as core
from contracts.operations.result import OperationResult
from contracts.plugins.namespace import PLUGIN_NAMESPACE
from features.incident.common import vocabulary
from features.incident.core import api
from features.incident.core.adapters import slack as slack_adapter
from features.incident.core.adapters.in_memory import InMemoryIncidentStore
from features.incident.core.domain import ResourceReference
from tests.factories.incident import incident_on, slack_conversation

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _clear_provider_cache() -> Iterator[None]:
    """Keep the cached reader and conversation from leaking between tests."""
    api.get_incident_transcript_reader.cache_clear()
    api.get_incident_conversation.cache_clear()
    yield
    api.get_incident_transcript_reader.cache_clear()
    api.get_incident_conversation.cache_clear()


def test_api_exports_exactly_the_public_names() -> None:
    """Subdomains reach core through these names only; a new export is a deliberate change."""
    assert sorted(api.__all__) == [
        "BindingKind",
        "ConversationReference",
        "DocumentField",
        "DocumentSection",
        "DraftWriteResult",
        "ExternalCaseReference",
        "Incident",
        "IncidentBinding",
        "IncidentConversation",
        "IncidentReport",
        "IncidentStore",
        "IncidentTranscriptReader",
        "LegacyUpgrade",
        "MessageReference",
        "PostmortemMeetingReference",
        "ReferenceKind",
        "ReportReference",
        "SectionDraft",
        "StatusUpdate",
        "StatusUpdateOrigin",
        "StatusUpdateStage",
        "StatusUpdateState",
        "StatusUpdateStore",
        "StatusUpdateText",
        "TimelineEntry",
        "TranscriptMessage",
        "UpgradeReport",
        "VideoCallReference",
        "build_incident_store",
        "build_legacy_upgrade",
        "build_status_update_store",
        "conversation_is_writable",
        "find_incident_for_conversation",
        "get_incident_conversation",
        "get_incident_report",
        "get_incident_transcript_reader",
        "translate",
    ]
    assert all(hasattr(api, name) for name in api.__all__)


def test_status_update_stage_is_the_common_vocabulary_type() -> None:
    """The stage is defined once, in common/; core re-exports that same class."""
    assert api.StatusUpdateStage is vocabulary.StatusUpdateStage


def test_transcript_message_is_frozen_with_an_optional_time() -> None:
    """The message is an immutable value: author and text, and a time only when the platform gave one."""
    message = api.TranscriptMessage(author="Alice", text="hi")

    assert message.posted_at is None
    assert api.TranscriptMessage(author="Alice", text="hi", posted_at=datetime(2026, 1, 1, tzinfo=UTC)).posted_at is not None
    with pytest.raises(dataclasses.FrozenInstanceError):
        message.text = "edited"  # type: ignore[misc]


def test_interface_signatures_carry_only_plain_and_domain_types() -> None:
    """No platform payload, SDK type or platform time format crosses the interface."""
    started = inspect.signature(api.IncidentTranscriptReader.conversation_started_at)
    read = inspect.signature(api.IncidentTranscriptReader.read_transcript)

    assert {name: p.annotation for name, p in started.parameters.items() if name != "self"} == {
        "conversation": api.ConversationReference
    }
    assert started.return_annotation == OperationResult[datetime | None]
    assert {name: p.annotation for name, p in read.parameters.items() if name != "self"} == {
        "conversation": api.ConversationReference,
        "since": datetime,
        "limit": int,
        "exclude_own_and_system_messages": bool,
    }
    assert read.parameters["exclude_own_and_system_messages"].default is False
    assert read.return_annotation == OperationResult[Sequence[api.TranscriptMessage]]


def test_conversation_interface_is_async_on_the_reference_with_operation_results() -> None:
    """Every IncidentConversation method is a coroutine taking the conversation reference; none creates one."""
    methods = {
        name: getattr(api.IncidentConversation, name)
        for name in ("post", "set_purpose", "add_bookmark", "invite", "archive", "is_writable")
    }

    assert not hasattr(api.IncidentConversation, "create")
    for method in methods.values():
        signature = inspect.signature(method)
        assert inspect.iscoroutinefunction(method)
        assert signature.parameters["conversation"].annotation is api.ConversationReference
    assert inspect.signature(methods["post"]).return_annotation == OperationResult[api.MessageReference]
    assert inspect.signature(methods["is_writable"]).return_annotation == OperationResult[bool]
    assert inspect.signature(methods["invite"]).parameters["account_ids"].annotation == Sequence[str]
    assert inspect.signature(api.conversation_is_writable).parameters["conversation"].annotation == (
        api.ConversationReference | None
    )


def test_provider_returns_one_cached_reader_built_on_the_slack_web_client(monkeypatch: pytest.MonkeyPatch) -> None:
    """The provider hands out a single reader that satisfies the interface and calls the shared client factory's client."""
    client = MagicMock(spec=WebClient)
    client.conversations_info.return_value = {"ok": True, "channel": {"created": 1}}
    factory = MagicMock(return_value=client)
    monkeypatch.setattr(slack_adapter, "get_slack_web_client", factory)

    reader = api.get_incident_transcript_reader()

    assert isinstance(reader, api.IncidentTranscriptReader)
    assert api.get_incident_transcript_reader() is reader
    factory.assert_called_once_with()
    reader.conversation_started_at(slack_conversation("C123"))
    client.conversations_info.assert_called_once_with(channel="C123")


def test_conversation_provider_reads_on_the_shared_client_and_writes_on_the_write_handle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One cached IncidentConversation, built once on the async read client and the rate-limit-only write handle."""
    reads, writes = MagicMock(name="reads"), MagicMock(name="writes")
    read_factory, write_factory = MagicMock(return_value=reads), MagicMock(return_value=writes)
    monkeypatch.setattr(slack_adapter, "get_async_slack_web_client", read_factory)
    monkeypatch.setattr(slack_adapter, "get_async_slack_write_client", write_factory)

    conversations = api.get_incident_conversation()

    assert isinstance(conversations, api.IncidentConversation)
    assert api.get_incident_conversation() is conversations
    read_factory.assert_called_once_with()
    write_factory.assert_called_once_with()


def test_find_incident_for_conversation_answers_with_the_store_for_the_reference() -> None:
    """The command check every command calls asks the given store for the conversation reference it was handed."""
    incident = incident_on("C0INCIDENT", "7f0c3a52-3d0e-4d55-9a4e-6f1f2b9c0a11")
    asked: list[api.ConversationReference] = []

    class _RecordingStore(InMemoryIncidentStore):
        def find_by_conversation(self, conversation: api.ConversationReference) -> OperationResult[api.Incident]:
            asked.append(conversation)
            return super().find_by_conversation(conversation)

    store = _RecordingStore()
    store.seed(incident)

    result = api.find_incident_for_conversation(store, slack_conversation("C0INCIDENT"))

    assert result.data == incident
    assert asked == [slack_conversation("C0INCIDENT")]


def test_status_update_store_signatures_carry_only_domain_types_and_operation_results() -> None:
    """No table, key or SDK shape crosses the store interface, so the storage contract can serve it later."""
    store = api.StatusUpdateStore

    def params(method: object) -> dict[str, object]:
        return {name: p.annotation for name, p in inspect.signature(method).parameters.items() if name != "self"}  # type: ignore[arg-type]

    assert params(store.append) == {"update": api.StatusUpdate}
    assert params(store.latest) == {"incident_id": str}
    assert params(store.list_for_incident) == {"incident_id": str}
    assert params(store.transition) == {"update": api.StatusUpdate, "expected_state": api.StatusUpdateState}
    assert inspect.signature(store.append).return_annotation == OperationResult[api.StatusUpdate]
    assert inspect.signature(store.latest).return_annotation == OperationResult[api.StatusUpdate | None]
    assert inspect.signature(store.list_for_incident).return_annotation == OperationResult[Sequence[api.StatusUpdate]]
    assert inspect.signature(store.transition).return_annotation == OperationResult[api.StatusUpdate]


def test_incident_store_signatures_carry_only_domain_types_and_operation_results() -> None:
    """No table, item or SDK shape crosses the store interface; its only writes are create, attach_conversation and set_reference."""
    store = api.IncidentStore

    def params(method: object) -> dict[str, object]:
        return {name: p.annotation for name, p in inspect.signature(method).parameters.items() if name != "self"}  # type: ignore[arg-type]

    assert params(store.get) == {"incident_id": str}
    assert params(store.find_by_conversation) == {"conversation": api.ConversationReference}
    assert params(store.list_open) == {}
    assert params(store.read_security_flag) == {"incident_id": str}
    assert inspect.signature(store.get).return_annotation == OperationResult[api.Incident]
    assert inspect.signature(store.find_by_conversation).return_annotation == OperationResult[api.Incident]
    assert inspect.signature(store.list_open).return_annotation == OperationResult[Sequence[api.Incident]]
    assert inspect.signature(store.read_security_flag).return_annotation == OperationResult[bool]
    assert params(store.create) == {"incident": api.Incident}
    assert params(store.attach_conversation) == {"incident_id": str, "binding": api.IncidentBinding}
    assert params(store.set_reference) == {
        "incident_id": str,
        "kind": api.ReferenceKind,
        "reference": ResourceReference,
    }
    assert inspect.signature(store.create).return_annotation == OperationResult[api.Incident]
    assert inspect.signature(store.attach_conversation).return_annotation == OperationResult[api.Incident]
    assert inspect.signature(store.set_reference).return_annotation == OperationResult[api.Incident]
    assert sorted(name for name in vars(store) if not name.startswith("_")) == [
        "attach_conversation",
        "create",
        "find_by_conversation",
        "get",
        "list_open",
        "read_security_flag",
        "set_reference",
    ]


def test_core_is_not_a_plugin() -> None:
    """Core has no inbound handlers and registers nothing: no entrypoints directory and no hookimpl in its package module."""
    package_dir = Path(core.__file__).parent

    assert not (package_dir / "entrypoints").exists()
    assert not (package_dir / "platforms").exists()
    assert [name for name, value in vars(core).items() if hasattr(value, f"{PLUGIN_NAMESPACE}_impl")] == []
