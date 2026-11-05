"""Unit tests for looking up when an incident conversation started in Slack.

The reader runs over a ``MagicMock(spec=WebClient)`` and is given the incident's
conversation reference. The answer is an ``OperationResult``: the creation time
(or ``None`` when Slack gives none) on success, a classified result when
``conversations.info`` fails, and an exception for a code the Slack table does
not name.
"""

from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock

import pytest
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from contracts.operations.codes import ErrorCode
from contracts.operations.status import OperationStatus
from contracts.workplace import WorkplaceSystem
from features.incident.core.adapters.slack import SlackIncidentTranscriptReader
from features.incident.core.domain import ConversationReference

pytestmark = pytest.mark.unit

_CONVERSATION = ConversationReference(system=WorkplaceSystem.SLACK, tenant="T0SLACK", vendor_id="C123")


def _client(channel: dict[str, Any] | None) -> MagicMock:
    """Return a fake Web client whose conversations.info answers with ``channel``."""
    client = MagicMock(spec=WebClient)
    client.conversations_info.return_value = {"ok": True, "channel": channel}
    return client


def test_creation_time_comes_back_as_an_aware_utc_datetime() -> None:
    """The channel's ``created`` epoch seconds become a timezone-aware UTC datetime."""
    client = _client({"created": 1_700_000_000})

    started = SlackIncidentTranscriptReader(client).conversation_started_at(_CONVERSATION)

    assert started.is_success
    assert started.data == datetime(2023, 11, 14, 22, 13, 20, tzinfo=UTC)
    assert started.data is not None and started.data.tzinfo is UTC
    client.conversations_info.assert_called_once_with(channel="C123")


@pytest.mark.parametrize("channel", [{}, {"name": "incident-1"}, None, {"created": "not-a-time"}])
def test_conversation_without_a_usable_creation_time_gives_none(channel: dict[str, Any] | None) -> None:
    """With no readable creation time the reader says so, and the caller applies its own window."""
    started = SlackIncidentTranscriptReader(_client(channel)).conversation_started_at(_CONVERSATION)

    assert started.is_success
    assert started.data is None


def test_lookup_failure_is_the_classified_result() -> None:
    """A failed conversations.info call (a missing scope, for one) is a classified result, not an exception."""
    client = _client({})
    client.conversations_info.side_effect = SlackApiError("boom", {"ok": False, "error": "missing_scope"})

    started = SlackIncidentTranscriptReader(client).conversation_started_at(_CONVERSATION)

    assert started.status is OperationStatus.UNAUTHORIZED
    assert started.error_code == "missing_scope"


def test_an_unknown_slack_code_propagates() -> None:
    client = _client({})
    client.conversations_info.side_effect = SlackApiError("boom", {"ok": False, "error": "invalid_arguments"})

    with pytest.raises(SlackApiError):
        SlackIncidentTranscriptReader(client).conversation_started_at(_CONVERSATION)


def test_a_reference_of_another_system_is_unsupported_without_a_call() -> None:
    client = _client({"created": 1_700_000_000})
    google = ConversationReference(system=WorkplaceSystem.GOOGLE, tenant="C0GOOGLE", vendor_id="spaces/AAA")

    started = SlackIncidentTranscriptReader(client).conversation_started_at(google)

    assert started.status is OperationStatus.PERMANENT_ERROR
    assert started.error_code == ErrorCode.UNSUPPORTED_OPERATION
    client.conversations_info.assert_not_called()
