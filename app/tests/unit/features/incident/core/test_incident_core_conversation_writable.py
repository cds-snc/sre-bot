"""conversation_is_writable: the check callers apply before writing to an incident's conversation.

Runs over the in-memory IncidentConversation, which the parity suite holds to the
Slack adapter's rules. An incident without a conversation (``None``) is not
writable and no call is made, asserted through the fake's call log.
"""

import pytest

from contracts.workplace import WorkplaceSystem
from features.incident.core.adapters.in_memory import InMemoryIncidentConversation
from features.incident.core.api import ConversationReference, conversation_is_writable

pytestmark = pytest.mark.unit

TENANT = "T0SLACK"


def _reference(vendor_id: str) -> ConversationReference:
    return ConversationReference(system=WorkplaceSystem.SLACK, tenant=TENANT, vendor_id=vendor_id)


@pytest.fixture
def fake() -> InMemoryIncidentConversation:
    return InMemoryIncidentConversation(
        tenant=TENANT, open_ids=["C0OPEN"], archived_ids=["C0ARCHIVED"], non_member_ids=["C0LEFT"]
    )


@pytest.mark.parametrize(("vendor_id", "writable"), [("C0OPEN", True), ("C0ARCHIVED", False), ("C0LEFT", False)])
async def test_the_answer_is_the_conversations(fake: InMemoryIncidentConversation, vendor_id: str, writable: bool) -> None:
    result = await conversation_is_writable(fake, _reference(vendor_id))

    assert result.is_success
    assert result.data is writable


async def test_no_conversation_is_not_writable_without_a_call(fake: InMemoryIncidentConversation) -> None:
    result = await conversation_is_writable(fake, None)

    assert result.is_success
    assert result.data is False
    assert fake.checked == []


async def test_a_failed_check_is_returned_as_classified(fake: InMemoryIncidentConversation) -> None:
    result = await conversation_is_writable(fake, _reference("C0GONE"))

    assert not result.is_success
    assert result.error_code == "channel_not_found"
