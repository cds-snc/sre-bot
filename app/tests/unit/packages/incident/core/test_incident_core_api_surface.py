"""Unit tests for the public surface of the incident core package."""

import dataclasses
import inspect
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from slack_sdk import WebClient

import packages.incident.core as core
from contracts.operations.result import OperationResult
from contracts.plugins.namespace import PLUGIN_NAMESPACE
from packages.incident.core import api
from packages.incident.core.adapters import legacy_incidents as legacy_incidents_adapter
from packages.incident.core.adapters import slack as slack_adapter

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _clear_provider_cache() -> Iterator[None]:
    """Keep the cached reader and lookup from leaking between tests."""
    api.get_incident_transcript_reader.cache_clear()
    api.get_incident_lookup.cache_clear()
    yield
    api.get_incident_transcript_reader.cache_clear()
    api.get_incident_lookup.cache_clear()


def test_api_exports_exactly_the_public_names() -> None:
    """Subdomains reach core through these names only; a new export is a deliberate change."""
    assert sorted(api.__all__) == [
        "IncidentLookup",
        "IncidentTranscriptReader",
        "TranscriptMessage",
        "find_incident_for_conversation",
        "get_incident_lookup",
        "get_incident_transcript_reader",
    ]
    assert all(hasattr(api, name) for name in api.__all__)


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

    assert {name: p.annotation for name, p in started.parameters.items() if name != "self"} == {"conversation_id": str}
    assert started.return_annotation == datetime | None
    assert {name: p.annotation for name, p in read.parameters.items() if name != "self"} == {
        "conversation_id": str,
        "since": datetime,
        "limit": int,
        "exclude_own_and_system_messages": bool,
    }
    assert read.parameters["exclude_own_and_system_messages"].default is False
    assert "TranscriptMessage" in str(read.return_annotation)


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
    reader.conversation_started_at("C123")
    client.conversations_info.assert_called_once_with(channel="C123")


def test_lookup_signature_carries_only_a_conversation_id_and_an_operation_result() -> None:
    """No table, item or SDK shape crosses the lookup interface, so the store can replace the adapter behind it."""
    find = inspect.signature(api.IncidentLookup.find_incident_for_conversation)

    assert {name: p.annotation for name, p in find.parameters.items() if name != "self"} == {"conversation_id": str}
    assert find.return_annotation == OperationResult[str]


def test_lookup_provider_returns_one_cached_lookup_built_by_the_legacy_adapter(monkeypatch: pytest.MonkeyPatch) -> None:
    """The provider builds the interim legacy-table lookup once and hands out that same instance."""
    built = MagicMock(spec=legacy_incidents_adapter.LegacyIncidentTableLookup)
    builder = MagicMock(return_value=built)
    monkeypatch.setattr(api, "build_legacy_incident_lookup", builder)

    lookup = api.get_incident_lookup()

    assert lookup is built
    assert api.get_incident_lookup() is built
    builder.assert_called_once_with()


def test_find_incident_for_conversation_returns_the_provided_lookup_result(monkeypatch: pytest.MonkeyPatch) -> None:
    """The module function is the command check every command calls; it answers with the provided lookup's result."""
    expected = OperationResult.success(data="7f0c3a52-3d0e-4d55-9a4e-6f1f2b9c0a11")

    class FakeLookup:
        def __init__(self) -> None:
            self.asked: list[str] = []

        def find_incident_for_conversation(self, conversation_id: str) -> OperationResult[str]:
            self.asked.append(conversation_id)
            return expected

    fake = FakeLookup()
    assert isinstance(fake, api.IncidentLookup)
    monkeypatch.setattr(api, "get_incident_lookup", lambda: fake)

    assert api.find_incident_for_conversation("C0INCIDENT") is expected
    assert fake.asked == ["C0INCIDENT"]


def test_core_is_not_a_plugin() -> None:
    """Core has no inbound handlers and registers nothing: no entrypoints directory and no hookimpl in its package module."""
    package_dir = Path(core.__file__).parent

    assert not (package_dir / "entrypoints").exists()
    assert not (package_dir / "platforms").exists()
    assert [name for name, value in vars(core).items() if hasattr(value, f"{PLUGIN_NAMESPACE}_impl")] == []
