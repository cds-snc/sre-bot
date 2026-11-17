"""SlackIncidentConversation.join: the Slack calls behind the parity suite's join rules.

Runs the adapter over the ``stub_slack`` Web clients. The adapter reads
``conversations.info`` first, so a channel the bot is already in (private ones
included, which Slack would refuse to join) makes no join call; a channel it left
is joined once; an archived channel or a private one it cannot join is refused as
not writable. Assertions are on the stub's recorded calls and the result.
"""

from collections.abc import Callable
from typing import Any

import pytest

from contracts.operations.codes import ErrorCode
from contracts.operations.status import OperationStatus
from contracts.workplace import WorkplaceSystem
from features.incident.core.adapters.in_memory import InMemoryIncidentConversation
from features.incident.core.adapters.slack import SlackIncidentConversation
from features.incident.core.api import ConversationReference

pytestmark = pytest.mark.unit

TENANT = "T0SLACK"


def _reference(vendor_id: str) -> ConversationReference:
    return ConversationReference(system=WorkplaceSystem.SLACK, tenant=TENANT, vendor_id=vendor_id)


def _adapter(stub_slack: Callable[..., Any], **flags: bool) -> tuple[Any, SlackIncidentConversation]:
    stub = stub_slack({"C0CHAN": {"is_archived": False, "is_member": False, **flags}})
    return stub, SlackIncidentConversation(stub.reads, stub.writes, tenant=TENANT)


@pytest.mark.parametrize("private", [False, True])
async def test_a_member_makes_no_join_call(stub_slack: Callable[..., Any], private: bool) -> None:
    stub, adapter = _adapter(stub_slack, is_member=True, is_private=private)

    joined = await adapter.join(_reference("C0CHAN"))

    assert joined.is_success
    stub.writes.conversations_join.assert_not_called()


async def test_a_channel_the_bot_left_is_joined_once(stub_slack: Callable[..., Any]) -> None:
    stub, adapter = _adapter(stub_slack)

    joined = await adapter.join(_reference("C0CHAN"))

    assert joined.is_success
    stub.writes.conversations_join.assert_awaited_once_with(channel="C0CHAN")


async def test_an_archived_channel_is_refused_without_a_join_call(stub_slack: Callable[..., Any]) -> None:
    stub, adapter = _adapter(stub_slack, is_archived=True)

    joined = await adapter.join(_reference("C0CHAN"))

    assert (joined.status, joined.error_code) == (OperationStatus.PERMANENT_ERROR, ErrorCode.CONVERSATION_NOT_WRITABLE)
    stub.writes.conversations_join.assert_not_called()


async def test_a_private_channel_the_bot_left_is_refused_as_not_writable(stub_slack: Callable[..., Any]) -> None:
    _, adapter = _adapter(stub_slack, is_private=True)

    joined = await adapter.join(_reference("C0CHAN"))

    assert (joined.status, joined.error_code) == (OperationStatus.PERMANENT_ERROR, ErrorCode.CONVERSATION_NOT_WRITABLE)


async def test_the_fake_refuses_a_private_channel_the_bot_left_and_records_joins() -> None:
    fake = InMemoryIncidentConversation(tenant=TENANT, non_member_ids=["C0LEFT"], private_non_member_ids=["C0PRIVATE"])

    refused = await fake.join(_reference("C0PRIVATE"))
    joined = await fake.join(_reference("C0LEFT"))

    assert refused.error_code == ErrorCode.CONVERSATION_NOT_WRITABLE
    assert joined.is_success
    assert fake.joined == [_reference("C0LEFT")]
