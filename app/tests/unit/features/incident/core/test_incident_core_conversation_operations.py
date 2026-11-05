"""Slack-specific behaviour of SlackIncidentConversation's writes.

The adapter runs over the ``stub_slack`` async Web clients; the assertions read
the calls Slack received, because the request shape (text only, link bookmarks,
one invite call for every account) is the adapter's own contract with Slack.
Every write goes through the write handle and the writability check through
the read client, so a write is never replayed by the SDK after a server error.
"""

from collections.abc import Callable
from typing import Any

import pytest

from contracts.workplace import WorkplaceSystem
from features.incident.core.adapters.slack import SlackIncidentConversation
from features.incident.core.api import ConversationReference

pytestmark = pytest.mark.unit

OPEN = ConversationReference(system=WorkplaceSystem.SLACK, tenant="T0SLACK", vendor_id="C0OPEN")


@pytest.fixture
def stub(stub_slack: Callable[..., Any]) -> Any:
    return stub_slack()


@pytest.fixture
def adapter(stub: Any) -> SlackIncidentConversation:
    return SlackIncidentConversation(stub.reads, stub.writes)


async def test_post_sends_plain_text_on_the_write_handle(stub: Any, adapter: SlackIncidentConversation) -> None:
    await adapter.post(OPEN, "Status: investigating")

    stub.writes.chat_postMessage.assert_awaited_once_with(channel="C0OPEN", text="Status: investigating")
    stub.reads.chat_postMessage.assert_not_called()


async def test_set_purpose_bookmark_and_archive_name_the_channel(stub: Any, adapter: SlackIncidentConversation) -> None:
    await adapter.set_purpose(OPEN, "Payments outage")
    await adapter.add_bookmark(OPEN, "Incident report", "https://docs.example/d/1")
    await adapter.archive(OPEN)

    stub.writes.conversations_setPurpose.assert_awaited_once_with(channel="C0OPEN", purpose="Payments outage")
    stub.writes.bookmarks_add.assert_awaited_once_with(
        channel_id="C0OPEN", title="Incident report", type="link", link="https://docs.example/d/1"
    )
    stub.writes.conversations_archive.assert_awaited_once_with(channel="C0OPEN")


async def test_invite_sends_every_account_in_one_call(stub: Any, adapter: SlackIncidentConversation) -> None:
    """One call for every account; force lets the others in when one is already a member."""

    await adapter.invite(OPEN, ["U1", "U2"])

    stub.writes.conversations_invite.assert_awaited_once_with(channel="C0OPEN", users=["U1", "U2"], force=True)


async def test_inviting_nobody_makes_no_call(stub: Any, adapter: SlackIncidentConversation) -> None:
    assert (await adapter.invite(OPEN, [])).is_success

    stub.writes.conversations_invite.assert_not_called()


@pytest.mark.parametrize("code", ["already_in_channel", "cant_invite_self"])
async def test_an_invite_slack_reports_as_already_done_succeeds(stub: Any, adapter: SlackIncidentConversation, code: str) -> None:
    stub.writes.conversations_invite.side_effect = stub.error(code)

    assert (await adapter.invite(OPEN, ["U1"])).is_success


async def test_writability_reads_conversation_info_without_joining(stub: Any, adapter: SlackIncidentConversation) -> None:
    await adapter.is_writable(OPEN)

    stub.reads.conversations_info.assert_awaited_once_with(channel="C0OPEN")
    stub.reads.conversations_join.assert_not_called()
    stub.writes.conversations_join.assert_not_called()


async def test_another_systems_reference_makes_no_call(stub: Any, adapter: SlackIncidentConversation) -> None:
    google = ConversationReference(system=WorkplaceSystem.GOOGLE, tenant="C0GOOGLE", vendor_id="spaces/AAA")

    await adapter.post(google, "text")
    await adapter.is_writable(google)

    stub.writes.chat_postMessage.assert_not_called()
    stub.reads.conversations_info.assert_not_called()
