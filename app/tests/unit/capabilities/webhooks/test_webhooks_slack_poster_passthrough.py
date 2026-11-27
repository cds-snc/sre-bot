"""Unit tests for posting a legacy passthrough message through the Slack poster.

The poster runs over the recording Slack client fake; assertions read the recorded
``chat_postMessage`` arguments, which prove what reached Slack.
"""

import pytest

from capabilities.webhooks.domain.kinds import Destination
from capabilities.webhooks.domain.messages import PassthroughMessage
from contracts.workplace import WorkplaceSystem
from tests.unit.capabilities.webhooks.slack_client_fake import TENANT, FakeSlackClient, poster

pytestmark = pytest.mark.unit

DESTINATION = Destination(WorkplaceSystem.SLACK, TENANT, "C-DEST")


async def test_the_destination_decides_the_conversation_and_payload_keys_outside_the_allowlist_are_dropped() -> None:
    client = FakeSlackClient()
    message = PassthroughMessage(
        {"channel": "C-PAYLOAD", "token": "xoxb-stolen", "as_user": True, "text": "deployed", "blocks": [{"type": "divider"}]}
    )

    result = await poster(client).for_delivery().post(DESTINATION, message)

    assert result.is_success
    assert client.posts == [{"channel": "C-DEST", "text": "deployed", "blocks": [{"type": "divider"}]}]


async def test_the_hardening_fields_are_forwarded_until_hardening_is_enforced() -> None:
    client = FakeSlackClient()

    await (
        poster(client).for_delivery().post(DESTINATION, PassthroughMessage({"text": "x", "username": "bot", "thread_ts": "1.2"}))
    )

    assert client.posts[0]["username"] == "bot" and client.posts[0]["thread_ts"] == "1.2"
