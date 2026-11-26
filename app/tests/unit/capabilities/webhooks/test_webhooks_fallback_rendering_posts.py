"""Unit tests for the fallback rendering of an unmatched delivery or a render failure.

The core words the header through the ``Translator`` contract in the destination's
languages; the Slack poster escapes and fits the decoded message under it. Stub strategy: a
dictionary-backed translator and a recording stand-in for the Slack Web API client.
"""

import pytest

from capabilities.webhooks.adapters.slack import SECTION_TEXT_CHARS
from capabilities.webhooks.domain.kinds import Destination
from capabilities.webhooks.domain.messages import fallback_body
from capabilities.webhooks.service import FALLBACK_HEADER_KEY, fallback_message
from contracts.workplace import WorkplaceSystem
from tests.unit.capabilities.webhooks.slack_client_fake import TENANT, FakeSlackClient, delivery_poster

pytestmark = pytest.mark.unit

DESTINATION = Destination(system=WorkplaceSystem.SLACK, tenant=TENANT, conversation_id="C123")
WORDING = {"en-US": "Webhook message the bot could not format", "fr-FR": "Message de webhook non mis en forme"}


class _Translator:
    def translate(self, key: str, language: str, /, **variables: str) -> str:
        assert key == FALLBACK_HEADER_KEY
        return WORDING[language]


async def test_the_header_is_in_each_language_over_the_escaped_body() -> None:
    message = fallback_message(
        _Translator(), ("fr-FR", "en-US"), source="Billing <prod>", decoded={"text": "<!channel> down"}, limit=3000
    )
    client = FakeSlackClient()

    await delivery_poster(client).post(DESTINATION, message)

    header, body = client.section_texts()
    assert header == "*Message de webhook non mis en forme*\n*Webhook message the bot could not format*\nBilling &lt;prod&gt;"
    assert body == '{"text":"&lt;!channel&gt; down"}'


async def test_a_long_body_is_cut_to_the_section_limit_after_escaping() -> None:
    message = fallback_message(_Translator(), ("en-US",), source="Billing", decoded={"text": "<" * 5000}, limit=5000)
    client = FakeSlackClient()

    await delivery_poster(client).post(DESTINATION, message)

    body = client.section_texts()[1]
    assert len(body) <= SECTION_TEXT_CHARS and body.endswith("…")


def test_the_body_is_neutralised_compact_json_cut_to_the_limit() -> None:
    """Bidirectional controls never reach the channel, and the text stops at the limit."""
    assert fallback_body({"a": "x‮y"}, 100) == '{"a":"xy"}'
    assert len(fallback_body({"a": "x" * 50}, 10)) == 10
