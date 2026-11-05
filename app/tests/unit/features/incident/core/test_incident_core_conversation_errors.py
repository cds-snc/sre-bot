"""Classified failures of SlackIncidentConversation.

Slack's error codes are classified through the Slack vendor table: the codes for
a conversation the bot cannot write to become ``CONVERSATION_NOT_WRITABLE``, the
other catalogued codes keep their class and Slack code (with the rate-limit
retry hint), and a code the table does not name propagates instead of being
guessed at. Each failure logs ``incident_conversation_<operation>_failed`` with
the Slack code, asserted through structlog's capture.
"""

from collections.abc import Callable
from typing import Any

import pytest
from slack_sdk.errors import SlackApiError
from structlog.testing import capture_logs

from contracts.operations.codes import ErrorCode
from contracts.operations.status import OperationStatus
from contracts.workplace import WorkplaceSystem
from features.incident.core.adapters.slack import SlackIncidentConversation
from features.incident.core.api import ConversationReference

pytestmark = pytest.mark.unit

OPEN = ConversationReference(system=WorkplaceSystem.SLACK, tenant="T0SLACK", vendor_id="C0OPEN")


@pytest.mark.parametrize("code", ["is_archived", "not_in_channel", "restricted_action", "restricted_action_read_only_channel"])
async def test_a_post_refused_by_the_conversation_is_not_writable(stub_slack: Callable[..., Any], code: str) -> None:
    stub = stub_slack(fail_with=code)

    with capture_logs() as logs:
        posted = await SlackIncidentConversation(stub.reads, stub.writes).post(OPEN, "text")

    assert posted.status is OperationStatus.PERMANENT_ERROR
    assert posted.error_code == ErrorCode.CONVERSATION_NOT_WRITABLE
    assert code in (posted.message or "")
    assert any(e["event"] == "incident_conversation_post_failed" and e["slack_error"] == code for e in logs)


async def test_a_rate_limited_write_is_transient_with_the_retry_hint(stub_slack: Callable[..., Any]) -> None:
    stub = stub_slack(fail_with="ratelimited")

    result = await SlackIncidentConversation(stub.reads, stub.writes).set_purpose(OPEN, "purpose")

    assert result.status is OperationStatus.TRANSIENT_ERROR
    assert result.error_code == "ratelimited"
    assert result.retry_after == 30


async def test_a_missing_scope_on_the_check_is_unauthorized(stub_slack: Callable[..., Any]) -> None:
    stub = stub_slack(fail_with="missing_scope")

    result = await SlackIncidentConversation(stub.reads, stub.writes).is_writable(OPEN)

    assert result.status is OperationStatus.UNAUTHORIZED
    assert result.error_code == "missing_scope"


async def test_an_unknown_slack_code_propagates(stub_slack: Callable[..., Any]) -> None:
    stub = stub_slack(fail_with="invalid_blocks")

    with pytest.raises(SlackApiError):
        await SlackIncidentConversation(stub.reads, stub.writes).post(OPEN, "text")


async def test_a_non_slack_exception_propagates(stub_slack: Callable[..., Any]) -> None:
    stub = stub_slack()
    stub.writes.conversations_archive.side_effect = TimeoutError("socket")

    with pytest.raises(TimeoutError):
        await SlackIncidentConversation(stub.reads, stub.writes).archive(OPEN)
