"""Unit tests for how the Slack poster lays out a message in several languages.

Stub strategy: a recording stand-in for the Slack Web API client. The core hands the poster
wording already in the destination's languages and order (decisions/languages.md); the
assertions pin that Slack shows one section per language in that order, the sender's
details once, and the action labels in every language.
"""

import pytest

from capabilities.webhooks.domain.events import Link
from capabilities.webhooks.domain.extensions import EventAction
from capabilities.webhooks.domain.kinds import Destination
from capabilities.webhooks.domain.messages import ChannelMessage
from contracts.languages import MultilingualText
from contracts.workplace import WorkplaceSystem
from tests.unit.capabilities.webhooks.slack_client_fake import TENANT, FakeSlackClient, delivery_poster

pytestmark = pytest.mark.unit

DESTINATION = Destination(system=WorkplaceSystem.SLACK, tenant=TENANT, conversation_id="C123")


def _message(order: tuple[str, str]) -> ChannelMessage:
    wording = {
        "en-US": ("Budget exceeded", "Spent 120", "Open the console", "Call incident"),
        "fr-FR": ("Budget dépassé", "Dépensé 120", "Ouvrir la console", "Déclarer un incident"),
    }

    def text(index: int) -> MultilingualText:
        return MultilingualText(tuple((language, wording[language][index]) for language in order))

    return ChannelMessage(
        title=text(0),
        summary=text(1),
        details="Actual spend is over the budget.",
        links=(Link(url="https://console.example/billing", label=text(2)),),
        actions=(EventAction(action_id="incident.response.call", value="inst-1:item-1", label=text(3)),),
    )


@pytest.mark.parametrize("order", [("en-US", "fr-FR"), ("fr-FR", "en-US")])
async def test_one_section_per_language_in_the_destinations_order(order: tuple[str, str]) -> None:
    """The policy order decides which language reads first."""
    client = FakeSlackClient()

    await delivery_poster(client).post(DESTINATION, _message(order))

    sections = client.section_texts()
    first_title = "*Budget exceeded*" if order[0] == "en-US" else "*Budget dépassé*"
    assert sections[0].startswith(first_title)
    assert "Ouvrir la console" in sections[0 if order[0] == "fr-FR" else 1]


async def test_each_language_section_holds_its_own_wording_only() -> None:
    client = FakeSlackClient()

    await delivery_poster(client).post(DESTINATION, _message(("en-US", "fr-FR")))

    english, french = client.section_texts()[:2]
    assert "Spent 120" in english and "Dépensé" not in english
    assert "<https://console.example/billing|Open the console>" in english
    assert "Dépensé 120" in french and "<https://console.example/billing|Ouvrir la console>" in french


async def test_the_senders_details_appear_once() -> None:
    """Forwarded text keeps its source language and is not repeated per language."""
    client = FakeSlackClient()

    await delivery_poster(client).post(DESTINATION, _message(("en-US", "fr-FR")))

    assert sum("Actual spend is over the budget." in text for text in client.section_texts()) == 1
    assert client.posts[-1]["text"].count("Actual spend is over the budget.") == 1


async def test_action_labels_carry_every_language() -> None:
    client = FakeSlackClient()

    await delivery_poster(client).post(DESTINATION, _message(("fr-FR", "en-US")))

    [actions] = [block for block in client.posts[-1]["blocks"] if block["type"] == "actions"]
    assert actions["elements"][0]["text"]["text"] == "Déclarer un incident / Call incident"


async def test_the_notification_text_carries_the_wording_for_screen_readers() -> None:
    """Slack reads the top-level text aloud and shows it in notifications, so it holds the content."""
    client = FakeSlackClient()

    await delivery_poster(client).post(DESTINATION, _message(("en-US", "fr-FR")))

    text = client.posts[-1]["text"]
    assert text.index("Budget exceeded") < text.index("Budget dépassé")
