"""One behaviour suite for every IncidentConversation: the Slack adapter and the in-memory fake.

The adapter runs over stubbed async Web clients that answer as Slack does (the
``stub_slack`` fixture); the fake is seeded with the same conversations. Each
test runs against both, so a consumer tested on the fake sees the adapter's
observable rules: writes to an open conversation succeed, a post returns the
message's reference, an archived or non-member conversation is not writable
and refuses writes with ``CONVERSATION_NOT_WRITABLE``, an unknown one is not
found, and another system's reference is unsupported without a call. Joining
makes a conversation the bot left writable, joining one it is in succeeds, and
an archived one refuses the join as not writable. Both are
seeded with the same channel names, user groups and accounts: a new name creates a
channel the bot can write to, a taken name is ``CONVERSATION_NAME_TAKEN``,
``find_own`` finds only the bot's open channels by exact name, and
``account_ids_for`` answers the account ids of the emails it knows, skipping the others.
``members`` lists the conversation's human, active accounts in order (bots, app users,
Slackbot and deactivated accounts left out) and ``account_emails`` answers each asked
account's email, ``None`` for an account with no email or none at all; the Slack stub
answers ``conversations.members`` one id per page, so the adapter's paging is exercised.
"""

from collections.abc import Callable
from datetime import date
from typing import Any

import pytest

from contracts.languages import MultilingualText
from contracts.operations.codes import ErrorCode
from contracts.operations.status import OperationStatus
from contracts.workplace import WorkplaceSystem
from features.incident.core.adapters.in_memory import InMemoryIncidentConversation, SeededAccount
from features.incident.core.adapters.slack import SlackIncidentConversation, slack_channel_name
from features.incident.core.api import ConversationName, ConversationReference, IncidentConversation, MessageReference

pytestmark = pytest.mark.unit

TENANT = "T0SLACK"
OPEN = ConversationReference(system=WorkplaceSystem.SLACK, tenant=TENANT, vendor_id="C0OPEN")
ARCHIVED = ConversationReference(system=WorkplaceSystem.SLACK, tenant=TENANT, vendor_id="C0ARCHIVED")
LEFT = ConversationReference(system=WorkplaceSystem.SLACK, tenant=TENANT, vendor_id="C0LEFT")
UNKNOWN = ConversationReference(system=WorkplaceSystem.SLACK, tenant=TENANT, vendor_id="C0GONE")
GOOGLE = ConversationReference(system=WorkplaceSystem.GOOGLE, tenant="C0GOOGLE", vendor_id="spaces/AAA")

OPENED_ON = date(2026, 11, 10)
OPEN_NAME = ConversationName("open", OPENED_ON, production=True)
ARCHIVED_NAME = ConversationName("archived", OPENED_ON, production=True)
LEFT_NAME = ConversationName("left", OPENED_ON, production=True)
FOREIGN_NAME = ConversationName("squatted", OPENED_ON, production=True)
NEW_NAME = ConversationName("payments", OPENED_ON, production=True)
_NAMES = {
    slack_channel_name(OPEN_NAME): "C0OPEN",
    slack_channel_name(ARCHIVED_NAME): "C0ARCHIVED",
    slack_channel_name(LEFT_NAME): "C0LEFT",
}
_FOREIGN = [slack_channel_name(FOREIGN_NAME)]
_GROUPS = {"S0SEC": ["U1", "U2"]}
_ACCOUNTS = {"ada@example.org": "U0ADA", "bo@example.org": "U0BO"}
_MEMBERS = {"C0OPEN": ["U0ADA", "U0BOT", "U0BO", "U0GONE", "U0APP", "USLACKBOT", "U0NOMAIL"]}
_PEOPLE = {
    "U0ADA": SeededAccount(email="ada@example.org"),
    "U0BO": SeededAccount(email="bo@example.org"),
    "U0NOMAIL": SeededAccount(email=None),
    "U0BOT": SeededAccount(email=None, human=False),
    "U0APP": SeededAccount(email="app@example.org", human=False),
    "USLACKBOT": SeededAccount(email=None, human=False),
    "U0GONE": SeededAccount(email="gone@example.org", active=False),
}
# The same people as Slack's users.info answers them: a bot and an app user are flagged
# differently, and Slackbot carries no bot flag at all (only its id names it).
_SLACK_USERS: dict[str, dict[str, Any]] = {
    "U0ADA": {"profile": {"email": "ada@example.org"}},
    "U0BO": {"profile": {"email": "bo@example.org"}},
    "U0NOMAIL": {"profile": {}},
    "U0BOT": {"is_bot": True, "profile": {}},
    "U0APP": {"is_app_user": True, "profile": {"email": "app@example.org"}},
    "USLACKBOT": {"profile": {}},
    "U0GONE": {"deleted": True, "profile": {"email": "gone@example.org"}},
}
_CHANNELS = {
    "C0OPEN": {"is_archived": False, "is_member": True},
    "C0ARCHIVED": {"is_archived": True, "is_member": True},
    "C0LEFT": {"is_archived": False, "is_member": False},
}


@pytest.fixture(params=["slack", "in_memory"])
def conversations(request: pytest.FixtureRequest, stub_slack: Callable[..., Any]) -> IncidentConversation:
    if request.param == "slack":
        stub = stub_slack(
            {key: dict(value) for key, value in _CHANNELS.items()},
            names=_NAMES,
            foreign_names=_FOREIGN,
            groups=_GROUPS,
            accounts=_ACCOUNTS,
            members={key: list(value) for key, value in _MEMBERS.items()},
            users=_SLACK_USERS,
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
        accounts=_ACCOUNTS,
        members=_MEMBERS,
        people=_PEOPLE,
    )


def test_both_implement_the_protocol(conversations: IncidentConversation) -> None:
    assert isinstance(conversations, IncidentConversation)


async def test_post_to_an_open_conversation_returns_the_message_reference(conversations: IncidentConversation) -> None:
    posted = await conversations.post(OPEN, "Status: investigating")

    assert posted.is_success
    assert posted.data == MessageReference(
        system=WorkplaceSystem.SLACK, tenant=TENANT, conversation_id="C0OPEN", message_id="1700000000.000001"
    )


async def test_a_multilingual_post_to_an_open_conversation_returns_the_message_reference(
    conversations: IncidentConversation,
) -> None:
    posted = await conversations.post(OPEN, MultilingualText((("en-US", "Status"), ("fr-FR", "Statut"))))

    assert posted.is_success
    assert posted.data is not None
    assert posted.data.conversation_id == "C0OPEN"


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
        lambda c: c.purpose(GOOGLE),
        lambda c: c.set_topic(GOOGLE, "topic"),
        lambda c: c.create_canvas(GOOGLE, "# Canvas"),
        lambda c: c.group_members(GOOGLE, "S0SEC"),
        lambda c: c.join(GOOGLE),
        lambda c: c.account_ids_for(GOOGLE, ["ada@example.org"]),
        lambda c: c.members(GOOGLE),
        lambda c: c.account_emails(GOOGLE, ["U0ADA"]),
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
    created = await conversations.create(NEW_NAME, private=private)

    assert created.is_success
    assert created.data == NEW
    assert (await conversations.is_writable(NEW)).data is True
    assert (await conversations.post(NEW, "Incident declared")).is_success


@pytest.mark.parametrize("name", [OPEN_NAME, FOREIGN_NAME])
async def test_creating_under_a_taken_name_is_name_taken(conversations: IncidentConversation, name: ConversationName) -> None:
    created = await conversations.create(name, private=False)

    assert created.status is OperationStatus.PERMANENT_ERROR
    assert created.error_code == ErrorCode.CONVERSATION_NAME_TAKEN
    assert created.data is None


async def test_find_own_returns_the_bots_open_channel_of_that_exact_name(conversations: IncidentConversation) -> None:
    found = await conversations.find_own(OPEN_NAME)

    assert found.is_success
    assert found.data == OPEN


@pytest.mark.parametrize(
    "name",
    [
        FOREIGN_NAME,
        ARCHIVED_NAME,
        LEFT_NAME,
        ConversationName("ope", OPENED_ON, production=True),
        ConversationName("open", OPENED_ON, production=False),
        ConversationName("open", OPENED_ON, production=True, attempt=2),
    ],
)
async def test_find_own_returns_none_for_any_other_name(conversations: IncidentConversation, name: ConversationName) -> None:
    found = await conversations.find_own(name)

    assert found.is_success
    assert found.data is None


async def test_find_own_finds_a_channel_just_created(conversations: IncidentConversation) -> None:
    await conversations.create(NEW_NAME, private=False)

    assert (await conversations.find_own(NEW_NAME)).data == NEW


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


async def test_a_conversation_without_a_purpose_reads_an_empty_one(conversations: IncidentConversation) -> None:
    purpose = await conversations.purpose(OPEN)

    assert purpose.is_success
    assert purpose.data == ""


async def test_the_purpose_read_is_the_one_last_set(conversations: IncidentConversation) -> None:
    await conversations.set_purpose(OPEN, "Payments outage")

    assert (await conversations.purpose(OPEN)).data == "Payments outage"


async def test_the_purpose_of_an_unknown_conversation_is_not_found(conversations: IncidentConversation) -> None:
    purpose = await conversations.purpose(UNKNOWN)

    assert purpose.status is OperationStatus.NOT_FOUND
    assert purpose.error_code == "channel_not_found"


@pytest.mark.parametrize("conversation", [OPEN, LEFT])
async def test_joining_makes_the_conversation_writable(
    conversations: IncidentConversation, conversation: ConversationReference
) -> None:
    joined = await conversations.join(conversation)

    assert joined.is_success
    assert (await conversations.is_writable(conversation)).data is True


async def test_joining_an_archived_conversation_is_refused_as_not_writable(conversations: IncidentConversation) -> None:
    joined = await conversations.join(ARCHIVED)

    assert joined.status is OperationStatus.PERMANENT_ERROR
    assert joined.error_code == ErrorCode.CONVERSATION_NOT_WRITABLE


async def test_joining_an_unknown_conversation_is_not_found(conversations: IncidentConversation) -> None:
    joined = await conversations.join(UNKNOWN)

    assert joined.status is OperationStatus.NOT_FOUND
    assert joined.error_code == "channel_not_found"


async def test_account_ids_for_answers_known_emails_in_order_and_skips_unknown_ones(
    conversations: IncidentConversation,
) -> None:
    found = await conversations.account_ids_for(OPEN, ["bo@example.org", "nobody@example.org", "ada@example.org"])

    assert found.is_success
    assert found.data == ("U0BO", "U0ADA")


async def test_account_ids_for_no_emails_is_empty(conversations: IncidentConversation) -> None:
    found = await conversations.account_ids_for(OPEN, [])

    assert found.is_success
    assert found.data == ()


async def test_members_are_the_human_active_accounts_in_order(conversations: IncidentConversation) -> None:
    found = await conversations.members(OPEN)

    assert found.is_success
    assert found.data == ("U0ADA", "U0BO", "U0NOMAIL")


async def test_members_of_an_unknown_conversation_is_not_found(conversations: IncidentConversation) -> None:
    found = await conversations.members(UNKNOWN)

    assert found.status is OperationStatus.NOT_FOUND


async def test_account_emails_answers_each_asked_account_none_without_an_email(
    conversations: IncidentConversation,
) -> None:
    found = await conversations.account_emails(OPEN, ["U0BO", "U0NOMAIL", "U0NOBODY", "U0ADA"])

    assert found.is_success
    assert dict(found.data or {}) == {"U0BO": "bo@example.org", "U0NOMAIL": None, "U0NOBODY": None, "U0ADA": "ada@example.org"}


async def test_account_emails_of_no_accounts_is_empty(conversations: IncidentConversation) -> None:
    found = await conversations.account_emails(OPEN, [])

    assert found.is_success
    assert dict(found.data or {}) == {}
