"""Unit tests for looking up when an incident conversation started in Slack."""

from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock

import pytest
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from features.incident.core.adapters.slack import SlackIncidentTranscriptReader

pytestmark = pytest.mark.unit


def _client(channel: dict[str, Any] | None) -> MagicMock:
    """Return a fake Web client whose conversations.info answers with ``channel``."""
    client = MagicMock(spec=WebClient)
    client.conversations_info.return_value = {"ok": True, "channel": channel}
    return client


def test_creation_time_comes_back_as_an_aware_utc_datetime() -> None:
    """The channel's ``created`` epoch seconds become a timezone-aware UTC datetime."""
    client = _client({"created": 1_700_000_000})

    started = SlackIncidentTranscriptReader(client).conversation_started_at("C123")

    assert started == datetime(2023, 11, 14, 22, 13, 20, tzinfo=UTC)
    assert started is not None and started.tzinfo is UTC
    client.conversations_info.assert_called_once_with(channel="C123")


@pytest.mark.parametrize("channel", [{}, {"name": "incident-1"}, None, {"created": "not-a-time"}])
def test_conversation_without_a_usable_creation_time_gives_none(channel: dict[str, Any] | None) -> None:
    """With no readable creation time the reader says so, and the caller applies its own window."""
    assert SlackIncidentTranscriptReader(_client(channel)).conversation_started_at("C123") is None


def test_lookup_failure_gives_none() -> None:
    """A failed conversations.info call (a missing scope, for one) degrades to None instead of raising."""
    client = _client({})
    client.conversations_info.side_effect = SlackApiError("boom", {"ok": False, "error": "missing_scope"})

    assert SlackIncidentTranscriptReader(client).conversation_started_at("C123") is None
