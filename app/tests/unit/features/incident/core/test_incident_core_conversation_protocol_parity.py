"""One behaviour suite for every IncidentConversation: the Slack adapter and the in-memory fake.

The adapter runs over stubbed async Web clients that answer as Slack does (the
``stub_slack`` fixture); the fake is seeded with the same conversations. Each
test runs against both, so a consumer tested on the fake sees the adapter's
observable rules: writes to an open conversation succeed, a post returns the
message's reference, an archived or non-member conversation is not writable
and refuses writes with ``CONVERSATION_NOT_WRITABLE``, an unknown one is not
found, and another system's reference is unsupported without a call. Both are
seeded with the same channel names and user groups: a new name creates a
channel the bot can write to, a taken name is ``CONVERSATION_NAME_TAKEN``, and
``find_own`` finds only the bot's open channels by exact name.
"""

from collections.abc import Callable
from typing import Any

import pytest

from contracts.operations.codes import ErrorCode
from contracts.operations.status import OperationStatus
from contracts.workplace import WorkplaceSystem
from features.incident.core.adapters.in_memory import InMemoryIncidentConversation
from features.incident.core.adapters.slack import SlackIncidentConversation
from features.incident.core.api import ConversationReference, IncidentConversation, MessageReference

pytestmark = pytest.mark.unit

TENANT = "T0SLACK"
OPEN = ConversationReference(system=WorkplaceSystem.SLACK, tenant=TENANT, vendor_id="C0OPEN")
ARCHIVED = ConversationReference(system=WorkplaceSystem.SLACK, tenant=TENANT, vendor_id="C0ARCHIVED")
LEFT = ConversationReference(system=WorkplaceSystem.SLACK, tenant=TENANT, vendor_id="C0LEFT")
UNKNOWN = ConversationReference(system=WorkplaceSystem.SLACK, tenant=TENANT, vendor_id="C0GONE")
GOOGLE = ConversationReference(system=WorkplaceSystem.GOOGLE, tenant="C0GOOGLE", vendor_id="spaces/AAA")

_NAMES = {"incident-open": "C0OPEN", "incident-archived": "C0ARCHIVED", "incident-left": "C0LEFT"}
_FOREIGN = ["general"]
_GROUPS = {"S0SEC": ["U1", "U2"]}
_CHANNELS = {
    "C0OPEN": {"is_archived": False, "is_member": True},
    "C0ARCHIVED": {"is_archived": True, "is_member": True},
    "C0LEFT": {"is_archived": False, "is_member": False},
}


@pytest.fixture(params=["slack", "in_memory"])
def conversations(request: pytest.FixtureRequest, stub_slack: Callable[..., Any]) -> IncidentConversation:
    if request.param == "slack":
        stub = stub_slack(
            {key: dict(value) for key, value in _CHANNELS.items()}, names=_NAMES, foreign_names=_FOREIGN, groups=_GROUPS
        )
        return SlackIncidentConversation(stub.reads, stub.writes, tenant=TENANT)
    return InMemoryIncidentConversation(
        tenant=TENANT,
        open_ids=["C0OPEN"],
        archived_ids=["C0ARCHIVED"],
        non_member_ids=["C0LEFT"],
        names=_NAMES,
        foreign_names=_FOREIGN,
        groups=_GROUPS,
    )


def test_both_implement_the_protocol(conversations: IncidentConversation) -> None:
    assert isinstance(conversations, IncidentConversation)


async def test_post_to_an_open_conversation_returns_the_message_reference(conversations: IncidentConversation) -> None:
    posted = await conversations.post(OPEN, "Status: investigating")

    assert posted.is_success
    assert posted.data == MessageReference(
        system=WorkplaceSystem.SLACK, tenant=TENANT, conversation_id="C0OPEN", message_id="1700000000.000001"
    )


async def test_each_write_to_an_open_conversation_succeeds(conversations: IncidentConversation) -> None:
    results = [
        await conversations.set_purpose(OPEN, "Payments outage"),
        await conversations.add_bookmark(OPEN, "Incident report", "https://docs.example/d/1"),
        await conversations.invite(OPEN, ["U1", "U2"]),
        await conversations.archive(OPEN),
    ]

    assert all(result.is_success for result in results)


@pytest.mark.parametrize(("conversation", "writable"), [(OPEN, True), (ARCHIVED, False), (LEFT, False)])
async def test_writability(conversations: IncidentConversation, conversation: ConversationReference, writable: bool) -> None:
    result = await conversations.is_writable(conversation)

    assert result.is_success
    assert result.data is writable


async def test_an_archived_conversation_reads_as_not_writable_once_archived(conversations: IncidentConversation) -> None:
    assert (await conversations.archive(OPEN)).is_success

    assert (await conversations.is_writable(OPEN)).data is False


@pytest.mark.parametrize("conversation", [ARCHIVED, LEFT])
async def test_a_post_where_the_bot_cannot_write_is_refused_as_not_writable(
    conversations: IncidentConversation, conversation: ConversationReference
) -> None:
    posted = await conversations.post(conversation, "Status: investigating")

    assert posted.status is OperationStatus.PERMANENT_ERROR
    assert posted.error_code == ErrorCode.CONVERSATION_NOT_WRITABLE


async def test_an_unknown_conversation_is_not_found(conversations: IncidentConversation) -> None:
    result = await conversations.is_writable(UNKNOWN)

    assert result.status is OperationStatus.NOT_FOUND
    assert result.error_code == "channel_not_found"


async def test_archiving_twice_succeeds(conversations: IncidentConversation) -> None:
    assert (await conversations.archive(ARCHIVED)).is_success


async def test_inviting_nobody_succeeds(conversations: IncidentConversation) -> None:
    assert (await conversations.invite(OPEN, [])).is_success


@pytest.mark.parametrize(
    "call",
    [
        lambda c: c.post(GOOGLE, "text"),
        lambda c: c.set_purpose(GOOGLE, "purpose"),
        lambda c: c.add_bookmark(GOOGLE, "title", "https://example"),
        lambda c: c.invite(GOOGLE, ["U1"]),
        lambda c: c.archive(GOOGLE),
        lambda c: c.is_writable(GOOGLE),
        lambda c: c.set_topic(GOOGLE, "topic"),
        lambda c: c.create_canvas(GOOGLE, "# Canvas"),
        lambda c: c.group_members(GOOGLE, "S0SEC"),
    ],
)
async def test_another_systems_reference_is_unsupported(
    conversations: IncidentConversation, call: Callable[[IncidentConversation], Any]
) -> None:
    result = await call(conversations)

    assert result.status is OperationStatus.PERMANENT_ERROR
    assert result.error_code == ErrorCode.UNSUPPORTED_OPERATION


NEW = ConversationReference(system=WorkplaceSystem.SLACK, tenant=TENANT, vendor_id="C0NEW1")


@pytest.mark.parametrize("private", [False, True])
async def test_creating_under_a_new_name_returns_a_writable_conversation(
    conversations: IncidentConversation, private: bool
) -> None:
    created = await conversations.create("incident-2026-11-10-payments", private=private)

    assert created.is_success
    assert created.data == NEW
    assert (await conversations.is_writable(NEW)).data is True
    assert (await conversations.post(NEW, "Incident declared")).is_success


@pytest.mark.parametrize("name", ["incident-open", "general"])
async def test_creating_under_a_taken_name_is_name_taken(conversations: IncidentConversation, name: str) -> None:
    created = await conversations.create(name, private=False)

    assert created.status is OperationStatus.PERMANENT_ERROR
    assert created.error_code == ErrorCode.CONVERSATION_NAME_TAKEN
    assert created.data is None


async def test_find_own_returns_the_bots_open_channel_of_that_exact_name(conversations: IncidentConversation) -> None:
    found = await conversations.find_own("incident-open")

    assert found.is_success
    assert found.data == OPEN


@pytest.mark.parametrize("name", ["general", "incident-archived", "incident-left", "incident-ope", "missing"])
async def test_find_own_returns_none_for_any_other_name(conversations: IncidentConversation, name: str) -> None:
    found = await conversations.find_own(name)

    assert found.is_success
    assert found.data is None


async def test_find_own_finds_a_channel_just_created(conversations: IncidentConversation) -> None:
    await conversations.create("incident-2026-11-10-payments", private=False)

    assert (await conversations.find_own("incident-2026-11-10-payments")).data == NEW


async def test_topic_canvas_and_blocks_on_an_open_conversation_succeed(conversations: IncidentConversation) -> None:
    results = [
        await conversations.set_topic(OPEN, "Incident: payments"),
        await conversations.create_canvas(OPEN, "# Incident canvas"),
        await conversations.post(OPEN, "Next steps", blocks=[{"type": "section", "text": {"type": "mrkdwn", "text": "*Next*"}}]),
    ]

    assert all(result.is_success for result in results)


async def test_a_second_canvas_counts_as_created(conversations: IncidentConversation) -> None:
    assert (await conversations.create_canvas(OPEN, "# Incident canvas")).is_success

    assert (await conversations.create_canvas(OPEN, "# Incident canvas")).is_success


@pytest.mark.parametrize("conversation", [ARCHIVED, LEFT])
@pytest.mark.parametrize(
    "call",
    [lambda c, conversation: c.set_topic(conversation, "topic"), lambda c, conversation: c.create_canvas(conversation, "# C")],
)
async def test_topic_and_canvas_where_the_bot_cannot_write_are_refused_as_not_writable(
    conversations: IncidentConversation, conversation: ConversationReference, call: Callable[..., Any]
) -> None:
    result = await call(conversations, conversation)

    assert result.status is OperationStatus.PERMANENT_ERROR
    assert result.error_code == ErrorCode.CONVERSATION_NOT_WRITABLE


async def test_group_members_returns_the_groups_account_ids(conversations: IncidentConversation) -> None:
    members = await conversations.group_members(OPEN, "S0SEC")

    assert members.is_success
    assert members.data == ("U1", "U2")


async def test_an_unknown_group_is_not_found(conversations: IncidentConversation) -> None:
    members = await conversations.group_members(OPEN, "S0GONE")

    assert members.status is OperationStatus.NOT_FOUND
    assert members.error_code == "no_such_subteam"
