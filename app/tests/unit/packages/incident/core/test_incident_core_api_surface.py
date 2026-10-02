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
from contracts.plugins.namespace import PLUGIN_NAMESPACE
from packages.incident.core import api
from packages.incident.core.adapters import slack as slack_adapter

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _clear_provider_cache() -> Iterator[None]:
    """Keep the cached reader from leaking between tests."""
    api.get_incident_transcript_reader.cache_clear()
    yield
    api.get_incident_transcript_reader.cache_clear()


def test_api_exports_exactly_the_three_public_names() -> None:
    """Subdomains reach core through these names only; a new export is a deliberate change."""
    assert sorted(api.__all__) == ["IncidentTranscriptReader", "TranscriptMessage", "get_incident_transcript_reader"]
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


def test_core_is_not_a_plugin() -> None:
    """Core has no inbound handlers and registers nothing: no entrypoints directory and no hookimpl in its package module."""
    package_dir = Path(core.__file__).parent

    assert not (package_dir / "entrypoints").exists()
    assert not (package_dir / "platforms").exists()
    assert [name for name, value in vars(core).items() if hasattr(value, f"{PLUGIN_NAMESPACE}_impl")] == []
