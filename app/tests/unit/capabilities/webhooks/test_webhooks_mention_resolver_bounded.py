"""Unit tests for turning email addresses in a sender's text into Slack mentions.

Stub strategy: a recording stand-in for the Slack Web API client answers lookups from a
table (a miss is ``users_not_found``); structlog's ``capture_logs`` records the events. The
assertions pin the lookup bound: at most the configured number of lookups per
delivery, cached across its destinations, hits and misses alike, and no address logged.
"""

import pytest
from structlog.testing import capture_logs

from capabilities.webhooks.domain.kinds import Destination
from capabilities.webhooks.domain.messages import ChannelMessage
from contracts.languages import MultilingualText
from contracts.workplace import WorkplaceSystem
from tests.unit.capabilities.webhooks.slack_client_fake import TENANT, FakeSlackClient, delivery_poster, poster

pytestmark = pytest.mark.unit

ONE = Destination(system=WorkplaceSystem.SLACK, tenant=TENANT, conversation_id="C1")
TWO = Destination(system=WorkplaceSystem.SLACK, tenant=TENANT, conversation_id="C2")


def _message(details: str, *, mentions: bool = True) -> ChannelMessage:
    text = MultilingualText((("en-US", "Owner: ana@example.com"),))
    return ChannelMessage(title=text, summary=text, details=details, mentions=mentions)


async def test_a_resolved_address_becomes_a_mention_and_a_miss_stays_escaped_text() -> None:
    """The domain matches in any case; the local part is case-sensitive (RFC 5321), so it must match as written."""
    client = FakeSlackClient({"ana@example.com": "U0ANA"})

    await delivery_poster(client).post(ONE, _message("cc (bob@example.com), ana@EXAMPLE.com."))

    summary, details = client.section_texts()
    assert "Owner: <@U0ANA>" in summary
    assert "cc (bob@example.com), <@U0ANA>." in details


async def test_lookups_stop_at_the_cap() -> None:
    client = FakeSlackClient()
    addresses = " ".join(f"user{n}@example.com" for n in range(30))

    await delivery_poster(client, lookups_per_message=3).post(ONE, _message(addresses))

    assert len(client.lookups) == 3


async def test_the_cache_spans_the_deliverys_destinations_including_misses() -> None:
    """A second destination of the same delivery looks nothing up again."""
    client = FakeSlackClient({"ana@example.com": "U0ANA"})
    poster = delivery_poster(client)

    await poster.post(ONE, _message("bob@example.com"))
    await poster.post(TWO, _message("bob@example.com"))

    assert sorted(client.lookups) == ["ana@example.com", "bob@example.com"]
    assert "<@U0ANA>" in client.section_texts()[0]


async def test_a_new_delivery_starts_a_new_cache() -> None:
    client = FakeSlackClient({"ana@example.com": "U0ANA"})
    channel_poster = poster(client)
    await channel_poster.for_delivery().post(ONE, _message(""))
    await channel_poster.for_delivery().post(ONE, _message(""))

    assert client.lookups == ["ana@example.com", "ana@example.com"]


async def test_a_kind_without_mentions_looks_nothing_up() -> None:
    client = FakeSlackClient({"ana@example.com": "U0ANA"})

    await delivery_poster(client).post(ONE, _message("ana@example.com", mentions=False))

    assert client.lookups == []
    assert "<@" not in "".join(client.section_texts())


async def test_a_user_id_outside_slacks_shape_is_not_inserted() -> None:
    """Only a token the adapter can vouch for becomes live mrkdwn."""
    client = FakeSlackClient({"ana@example.com": "U0ANA><!channel"})

    await delivery_poster(client).post(ONE, _message(""))

    assert "<!channel" not in "".join(client.section_texts())


async def test_no_address_is_logged() -> None:
    client = FakeSlackClient({"ana@example.com": "U0ANA"})

    with capture_logs() as events:
        await delivery_poster(client).post(ONE, _message("bob@example.com"))

    assert "example.com" not in repr(events)
    assert [event for event in events if event["event"] == "webhook_mentions_resolved"][0]["looked_up"] == 2
