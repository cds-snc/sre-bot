"""Unit tests for the Slack poster's output encoding (decisions/webhooks.md 9, OWASP).

Stub strategy: the poster posts through a recording stand-in for the Slack Web API client;
the assertions read the blocks and text it was given. They pin what a channel reader sees:
mention, broadcast and link syntax in any payload-derived field arrives escaped (inert),
mrkdwn carrying payload text has ``verbatim`` set, links come only from the validated URL,
and a cut never leaves half an entity or half a token.
"""

import pytest

from capabilities.webhooks.adapters.slack import SECTION_TEXT_CHARS, escape_mrkdwn, fit
from capabilities.webhooks.domain.events import Link
from capabilities.webhooks.domain.extensions import EventAction
from capabilities.webhooks.domain.kinds import Destination
from capabilities.webhooks.domain.messages import ChannelMessage, FallbackMessage
from contracts.languages import MultilingualText
from contracts.workplace import WorkplaceSystem
from tests.unit.capabilities.webhooks.slack_client_fake import TENANT, FakeSlackClient, delivery_poster

pytestmark = pytest.mark.unit

DESTINATION = Destination(system=WorkplaceSystem.SLACK, tenant=TENANT, conversation_id="C123")
HOSTILE = "<!channel> <@U123> <https://evil.example|click> & <!here>"


def _text(value: str) -> MultilingualText:
    return MultilingualText((("en-US", value), ("fr-FR", value)))


def _assert_inert(text: str) -> None:
    for raw in ("<!channel>", "<@U123>", "<https://evil.example|click>", "<!here>"):
        assert raw not in text
    assert "&lt;!channel&gt;" in text and "&amp;" in text


async def test_every_payload_field_renders_inert() -> None:
    """Title, summary, details and link labels each carry the hostile text and none of it is live."""
    client = FakeSlackClient()
    message = ChannelMessage(
        title=_text(HOSTILE),
        summary=_text(HOSTILE),
        details=HOSTILE,
        links=(Link(url="https://console.example/x", label=_text(HOSTILE)),),
    )

    await delivery_poster(client).post(DESTINATION, message)

    for text in client.section_texts():
        _assert_inert(text)
    _assert_inert(client.posts[-1]["text"])


async def test_the_fallback_header_source_and_body_render_inert() -> None:
    client = FakeSlackClient()

    await delivery_poster(client).post(DESTINATION, FallbackMessage(header=_text("Header"), source=HOSTILE, body=HOSTILE))

    for text in client.section_texts():
        _assert_inert(text)


async def test_mrkdwn_with_payload_text_is_verbatim_and_unfurling_is_off() -> None:
    """Slack neither auto-links payload text nor fetches a payload URL to preview it."""
    client = FakeSlackClient()

    await delivery_poster(client).post(DESTINATION, ChannelMessage(title=_text("t"), summary=_text("s"), details="d"))

    texts = [block["text"] for block in client.posts[-1]["blocks"] if block["type"] == "section"]
    assert texts and all(text["type"] == "mrkdwn" and text["verbatim"] is True for text in texts)
    assert (client.posts[-1]["unfurl_links"], client.posts[-1]["unfurl_media"]) == (False, False)


async def test_a_link_is_built_from_the_validated_url_with_an_escaped_label() -> None:
    client = FakeSlackClient()
    link = Link(url="https://console.example/a%7Cb", label=_text("Open <now>"))

    await delivery_poster(client).post(DESTINATION, ChannelMessage(title=_text("t"), summary=_text("s"), links=(link,)))

    assert "<https://console.example/a%7Cb|Open &lt;now&gt;>" in client.section_texts()[0]


async def test_a_url_holding_a_link_delimiter_is_dropped() -> None:
    """Defence in depth: W2 re-encodes URLs, and the poster still refuses one that could break out."""
    client = FakeSlackClient()
    link = Link(url="https://x.example/a|<!channel>", label=_text("Open"))

    await delivery_poster(client).post(DESTINATION, ChannelMessage(title=_text("t"), summary=_text("s"), links=(link,)))

    assert "x.example" not in client.section_texts()[0]


async def test_button_labels_are_plain_text() -> None:
    """Code-owned wording is the only plain_text: it carries no payload value."""
    client = FakeSlackClient()
    action = EventAction(action_id="incident.response.call", value="inst-1:item-1", label=_text("Call"))

    await delivery_poster(client).post(DESTINATION, ChannelMessage(title=_text("t"), summary=_text("s"), actions=(action,)))

    [actions] = [block for block in client.posts[-1]["blocks"] if block["type"] == "actions"]
    assert actions["elements"][0]["text"] == {"type": "plain_text", "text": "Call / Call"}


def test_escaping_handles_the_ampersand_first() -> None:
    """``<`` becomes ``&lt;``, not ``&amp;lt;``."""
    assert escape_mrkdwn("a & <b>") == "a &amp; &lt;b&gt;"


@pytest.mark.parametrize("budget", range(1, 12))
def test_a_cut_never_splits_an_entity(budget: int) -> None:
    """Whatever the budget, the result is a prefix of whole escaped characters plus the ellipsis."""
    text = fit(["&&&&&&"], budget)

    assert len(text) <= budget
    assert text.removesuffix("…").replace("&amp;", "") == ""


def test_the_limit_is_measured_on_the_escaped_text() -> None:
    """Text that fits raw but not escaped is cut."""
    text = fit(["<" * SECTION_TEXT_CHARS], SECTION_TEXT_CHARS)

    assert len(text) <= SECTION_TEXT_CHARS
    assert text.endswith("…")


def test_text_within_the_budget_is_not_cut() -> None:
    assert fit(["a&b"], 7) == "a&amp;b"
