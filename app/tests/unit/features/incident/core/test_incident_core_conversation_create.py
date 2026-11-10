"""The Slack IncidentConversation's create, find_own, canvas and block posts, at the Web client edge.

The adapter runs over the ``stub_slack`` clients, which answer as Slack does.
The tests assert what reaches Slack (which client, which arguments) and how
each answer is classified: create makes exactly one non-replayed call on the
write handle and reports a taken name quietly, as an expected outcome the
caller iterates on; find_own reads the bot's own conversations page by page.
"""

from collections.abc import Callable
from typing import Any

import pytest
from structlog.testing import capture_logs

from contracts.operations.codes import ErrorCode
from contracts.operations.status import OperationStatus
from contracts.workplace import WorkplaceSystem
from features.incident.core.adapters.slack import SlackIncidentConversation
from features.incident.core.api import ConversationReference

pytestmark = pytest.mark.unit

TENANT = "T0SLACK"
OPEN = ConversationReference(system=WorkplaceSystem.SLACK, tenant=TENANT, vendor_id="C0OPEN")


def _adapter(stub: Any, *, tenant: str | None = TENANT) -> SlackIncidentConversation:
    return SlackIncidentConversation(stub.reads, stub.writes, tenant=tenant)


async def test_create_sends_only_the_name_for_a_public_channel_on_the_write_handle(stub_slack: Callable[..., Any]) -> None:
    stub = stub_slack()

    created = await _adapter(stub).create("incident-2026-11-10-payments", private=False)

    assert created.is_success
    stub.writes.conversations_create.assert_awaited_once_with(name="incident-2026-11-10-payments")
    stub.reads.conversations_create.assert_not_called()


async def test_create_asks_for_a_private_channel_when_private(stub_slack: Callable[..., Any]) -> None:
    stub = stub_slack()

    await _adapter(stub).create("incident-2026-11-10-breach", private=True)

    stub.writes.conversations_create.assert_awaited_once_with(name="incident-2026-11-10-breach", is_private=True)


async def test_a_taken_name_is_reported_quietly_after_one_call(stub_slack: Callable[..., Any]) -> None:
    stub = stub_slack(foreign_names=["incident-2026-11-10-payments"])

    with capture_logs() as logs:
        created = await _adapter(stub).create("incident-2026-11-10-payments", private=False)

    assert created.status is OperationStatus.PERMANENT_ERROR
    assert created.error_code == ErrorCode.CONVERSATION_NAME_TAKEN
    assert stub.writes.conversations_create.await_count == 1
    stub.reads.users_conversations.assert_not_called()
    assert [log["log_level"] for log in logs] == ["info"]
    assert logs[0]["event"] == "incident_conversation_name_taken"


async def test_a_workspace_refusing_channel_creation_is_not_writable(stub_slack: Callable[..., Any]) -> None:
    created = await _adapter(stub_slack(fail_with="restricted_action")).create("incident-x", private=False)

    assert created.status is OperationStatus.PERMANENT_ERROR
    assert created.error_code == ErrorCode.CONVERSATION_NOT_WRITABLE


async def test_a_rate_limited_create_is_transient_with_its_retry_after(stub_slack: Callable[..., Any]) -> None:
    created = await _adapter(stub_slack(fail_with="ratelimited")).create("incident-x", private=False)

    assert created.status is OperationStatus.TRANSIENT_ERROR
    assert created.retry_after is not None


@pytest.mark.parametrize("call", [lambda a: a.create("incident-x", private=False), lambda a: a.find_own("incident-x")])
async def test_without_a_slack_tenant_create_and_find_own_are_not_configured_without_a_call(
    stub_slack: Callable[..., Any], call: Callable[[SlackIncidentConversation], Any]
) -> None:
    stub = stub_slack()

    result = await call(_adapter(stub, tenant=None))

    assert result.status is OperationStatus.PERMANENT_ERROR
    assert result.error_code == ErrorCode.CONFIG_NOT_CONFIGURED
    stub.writes.conversations_create.assert_not_called()
    stub.reads.users_conversations.assert_not_called()


async def test_find_own_reads_every_page_of_the_bots_open_conversations(stub_slack: Callable[..., Any]) -> None:
    channels = {f"C0{n}": {"is_archived": False, "is_member": True} for n in range(3)}
    stub = stub_slack(channels, names={"incident-a": "C00", "incident-b": "C01", "incident-c": "C02"}, page_size=1)

    found = await _adapter(stub).find_own("incident-c")

    assert found.data == ConversationReference(system=WorkplaceSystem.SLACK, tenant=TENANT, vendor_id="C02")
    assert stub.reads.users_conversations.await_count == 3
    first = stub.reads.users_conversations.await_args_list[0].kwargs
    assert first["types"] == "public_channel,private_channel"
    assert first["exclude_archived"] is True


async def test_a_failed_lookup_is_classified(stub_slack: Callable[..., Any]) -> None:
    found = await _adapter(stub_slack(fail_with="ratelimited")).find_own("incident-x")

    assert found.status is OperationStatus.TRANSIENT_ERROR


async def test_a_post_with_blocks_sends_them_with_the_text_fallback(stub_slack: Callable[..., Any]) -> None:
    stub = stub_slack()
    blocks = [{"type": "section", "text": {"type": "mrkdwn", "text": "*Next steps*"}}]

    await _adapter(stub).post(OPEN, "Next steps", blocks=blocks)

    stub.writes.chat_postMessage.assert_awaited_once_with(channel="C0OPEN", text="Next steps", blocks=blocks)


async def test_a_post_without_blocks_sends_no_blocks(stub_slack: Callable[..., Any]) -> None:
    stub = stub_slack()

    await _adapter(stub).post(OPEN, "Status: investigating")

    stub.writes.chat_postMessage.assert_awaited_once_with(channel="C0OPEN", text="Status: investigating")


async def test_a_canvas_is_created_from_markdown_on_the_write_handle(stub_slack: Callable[..., Any]) -> None:
    stub = stub_slack()

    await _adapter(stub).create_canvas(OPEN, "# Incident canvas")

    stub.writes.conversations_canvases_create.assert_awaited_once_with(
        channel_id="C0OPEN", document_content={"type": "markdown", "markdown": "# Incident canvas"}
    )


async def test_group_members_reads_on_the_read_client(stub_slack: Callable[..., Any]) -> None:
    stub = stub_slack(groups={"S0SEC": ["U1"]})

    await _adapter(stub).group_members(OPEN, "S0SEC")

    stub.reads.usergroups_users_list.assert_awaited_once_with(usergroup="S0SEC")
    stub.writes.usergroups_users_list.assert_not_called()
