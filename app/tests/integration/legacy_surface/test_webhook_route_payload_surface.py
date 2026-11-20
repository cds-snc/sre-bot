"""Pins what ``POST /hook/{webhook_id}`` posts to Slack for each payload family, through the production ASGI app.

The webhook record store, the Slack Web API (including the email lookup) and Sentinel are
faked at their external edges. Sender-supplied content the route forwards (text, blocks,
attachments, the alert buttons' ids and values) is asserted exactly, apart from the documented
mention and address-link rewrites; layout the bot builds (the Upptime and access-request
messages) is asserted by identifying facts. ``test_legacy_only_webhook_*`` tests pin behaviour
the webhooks rebuild ends and are deleted by the task named in each docstring.
"""

from typing import Any

import pytest
from slack_sdk.errors import SlackApiError

from contracts.configuration import host_info
from tests.integration.legacy_surface.conftest import WEBHOOK_CHANNEL, WEBHOOK_ID, WebhookSurface

pytestmark = pytest.mark.integration

SENDER_BLOCKS = [
    {"type": "header", "text": {"type": "plain_text", "text": "Deploy finished"}},
    {"type": "section", "text": {"type": "mrkdwn", "text": "*checkout* is live in `production`"}},
]


def button_attachment(post: dict[str, Any]) -> dict[str, Any]:
    """The incident-button attachment the route appended: the last attachment of ``post``."""
    attachment: dict[str, Any] = post["attachments"][-1]
    assert attachment["callback_id"] == "handle_incident_action_buttons"
    return attachment


def section_texts(post: dict[str, Any]) -> list[str]:
    """The mrkdwn and plain text of every block of ``post``, header text included."""
    return [block["text"]["text"] for block in post["blocks"] if "text" in block]


def test_webhook_route_generic_slack_message_is_forwarded_to_the_record_channel(webhook_surface: WebhookSurface) -> None:
    """A Slack-shaped body is posted unchanged, to the record's channel whatever channel the sender names."""
    webhook_surface.records.seed(hook_type="info")

    response = webhook_surface.post(
        {
            "channel": "C0SOMEWHEREELSE",
            "text": "Deploy finished",
            "blocks": SENDER_BLOCKS,
            "username": "deploy-bot",
            "icon_emoji": ":rocket:",
            "unfurl_links": False,
        }
    )

    assert response.status_code == 200
    [post] = webhook_surface.all_posts
    assert post["channel"] == WEBHOOK_CHANNEL
    assert post["text"] == "Deploy finished"
    assert post["blocks"] == SENDER_BLOCKS
    assert post["username"] == "deploy-bot"
    assert post["icon_emoji"] == ":rocket:"
    assert post["unfurl_links"] is False


def test_legacy_only_webhook_unknown_key_drops_a_slack_message_to_plain_text(webhook_surface: WebhookSurface) -> None:
    """A body with a key the Slack message model does not know falls back to the plain-text family.

    The text is posted and the unknown key never reaches Slack. Ended by TASK-37.2, where the
    webhook record declares its source and the body is parsed as that source.
    """
    webhook_surface.records.seed(hook_type="info")

    response = webhook_surface.post({"text": "just the text", "colour": "red"})

    assert response.status_code == 200
    [post] = webhook_surface.all_posts
    assert post["text"] == "just the text"
    assert "colour" not in post


@pytest.mark.parametrize("hook_type", ["info", "standard", "runbook"])
def test_webhook_route_non_alert_hook_types_post_without_buttons(webhook_surface: WebhookSurface, hook_type: str) -> None:
    """Only alert webhooks get incident buttons: any other hook type leaves the attachments as sent."""
    webhook_surface.records.seed(hook_type=hook_type)

    webhook_surface.post({"text": "Deploy finished", "blocks": SENDER_BLOCKS})

    [post] = webhook_surface.all_posts
    assert post["attachments"] == []


@pytest.mark.parametrize("hook_type", ["alert", None], ids=["alert", "hook-type-not-defined"])
def test_webhook_route_alert_hook_types_append_the_incident_buttons(
    webhook_surface: WebhookSurface, hook_type: str | None
) -> None:
    """A webhook of type alert, or one with no type recorded, gets the incident buttons appended."""
    webhook_surface.records.seed(hook_type=hook_type)

    webhook_surface.post({"text": "Deploy finished", "blocks": SENDER_BLOCKS})

    [post] = webhook_surface.all_posts
    assert button_attachment(post)["actions"]


def test_webhook_route_alert_buttons_carry_the_incident_action_contract(webhook_surface: WebhookSurface) -> None:
    """The posted alert's buttons keep the ids and values the Slack interaction handler reads back.

    The attachment's ``callback_id`` is an id on a message already posted, so buttons
    in old alerts keep working across the rebuild: ``handle_incident_action_buttons``
    (a legacy alias of the transport contract in decisions/transport-slack.md; a rename
    is a named change of kind (b), decisions/migration.md step 4). ``call-incident`` carries
    the alert text and ``ignore-incident`` the webhook id. Button labels and colour are
    wording and are not asserted.
    """
    webhook_surface.records.seed(hook_type="alert")

    webhook_surface.post({"text": "Checkout error rate above threshold"})

    [post] = webhook_surface.all_posts
    attachment = button_attachment(post)
    assert [(action["name"], action["type"], action["value"]) for action in attachment["actions"]] == [
        ("call-incident", "button", "Checkout error rate above threshold"),
        ("ignore-incident", "button", WEBHOOK_ID),
    ]


@pytest.mark.parametrize(
    ("sent_attachments", "forwarded_before_buttons"),
    [
        (None, []),
        ([{"text": "runbook", "color": "#36a64f"}], [{"text": "runbook", "color": "#36a64f"}]),
        ("a plain attachment", ["a plain attachment"]),
    ],
    ids=["absent", "list", "string"],
)
def test_webhook_route_alert_buttons_follow_the_attachments_the_sender_gave(
    webhook_surface: WebhookSurface, sent_attachments: Any, forwarded_before_buttons: list[Any]
) -> None:
    """The buttons are appended after the sender's attachments, whether given as a list, a string or not at all."""
    webhook_surface.records.seed(hook_type="alert")
    body: dict[str, Any] = {"text": "Deploy finished", "blocks": SENDER_BLOCKS}
    if sent_attachments is not None:
        body["attachments"] = sent_attachments

    webhook_surface.post(body)

    [post] = webhook_surface.all_posts
    assert post["attachments"][:-1] == forwarded_before_buttons
    assert button_attachment(post)["actions"]


def test_webhook_route_resolvable_emails_become_mentions_in_text_and_blocks(webhook_surface: WebhookSurface) -> None:
    """An email Slack can resolve is replaced by the user's mention; an unknown one is left as the sender wrote it."""
    webhook_surface.records.seed(hook_type="info")

    def lookup(email: str) -> dict[str, Any]:
        if email != "alice@example.com":
            raise SlackApiError("users_not_found", {"ok": False, "error": "users_not_found"})
        return {"ok": True, "user": {"id": "U0ALICE"}}

    webhook_surface.slack.replies["users_lookupByEmail"] = lookup

    webhook_surface.post(
        {
            "text": "Assigned to alice@example.com, cc bob@example.com",
            "blocks": [{"type": "section", "text": {"type": "mrkdwn", "text": "Owner: alice@example.com"}}],
        }
    )

    [post] = webhook_surface.all_posts
    assert post["text"] == "Assigned to <@U0ALICE>, cc bob@example.com"
    assert post["blocks"] == [{"type": "section", "text": {"type": "mrkdwn", "text": "Owner: <@U0ALICE>"}}]


def test_webhook_route_ip_addresses_become_geolocate_links_in_text_and_blocks(webhook_surface: WebhookSurface) -> None:
    """An IP address in the text or blocks is linked to the bot's geolocate page, under the host's public base URL."""
    webhook_surface.records.seed(hook_type="info")
    base_url = host_info().public_base_url.rstrip("/")

    webhook_surface.post(
        {
            "text": "Login blocked from 198.51.100.4",
            "blocks": [{"type": "section", "text": {"type": "mrkdwn", "text": "source 203.0.113.9 and 2001:db8::1"}}],
        }
    )

    [post] = webhook_surface.all_posts
    assert post["text"] == f"Login blocked from <{base_url}/geolocate/198.51.100.4|198.51.100.4>"
    assert post["blocks"][0]["text"]["text"] == (
        f"source <{base_url}/geolocate/203.0.113.9|203.0.113.9> and <{base_url}/geolocate/2001%3Adb8%3A%3A1|2001:db8::1>"
    )


def test_webhook_route_plain_text_is_posted_as_sent(webhook_surface: WebhookSurface) -> None:
    """A body that is only ``{"text": ...}`` is posted to the record's channel with the text unchanged."""
    webhook_surface.records.seed(hook_type="info")

    response = webhook_surface.post({"text": "backup completed in 4 minutes"})

    assert response.status_code == 200
    [post] = webhook_surface.all_posts
    assert post["channel"] == WEBHOOK_CHANNEL
    assert post["text"] == "backup completed in 4 minutes"


def test_webhook_route_access_request_is_posted_with_its_details(webhook_surface: WebhookSurface) -> None:
    """An access request is posted as a message that names the account, the reason and the window."""
    webhook_surface.records.seed(hook_type="info")

    response = webhook_surface.post(
        {
            "account": "prod-payments",
            "reason": "rotate the signing key",
            "startDate": "2026-11-20T10:00:00",
            "endDate": "2026-11-20T12:00:00",
        }
    )

    assert response.status_code == 200
    [post] = webhook_surface.all_posts
    assert post["channel"] == WEBHOOK_CHANNEL
    for fact in ("prod-payments", "rotate the signing key", "2026", "10", "12"):
        assert fact in post["text"]


@pytest.mark.parametrize(
    ("status_text", "headline_fact"),
    [
        (":large_red_square: Checkout (https://checkout.example.test) is down", "Down"),
        (":large_green_square: Checkout (https://checkout.example.test) is back up", "Recovered"),
        (":large_yellow_square: Checkout (https://checkout.example.test) is experiencing degraded performance", "Degraded"),
    ],
    ids=["down", "recovered", "degraded"],
)
def test_webhook_route_upptime_status_text_is_posted_as_a_status_message(
    webhook_surface: WebhookSurface, status_text: str, headline_fact: str
) -> None:
    """Upptime status text is posted as a message with a status headline and the sender's text unchanged."""
    webhook_surface.records.seed(hook_type="info")

    response = webhook_surface.post({"text": status_text})

    assert response.status_code == 200
    [post] = webhook_surface.all_posts
    assert post["channel"] == WEBHOOK_CHANNEL
    assert status_text in section_texts(post)
    headers = [block["text"]["text"] for block in post["blocks"] if block["type"] == "header"]
    assert len(headers) == 1
    assert headline_fact in headers[0]


def test_legacy_only_webhook_payload_family_is_guessed_by_score(webhook_surface: WebhookSurface) -> None:
    """The family of a body is guessed by scoring it against each model, so one extra key changes what is posted.

    Upptime text alone is read as plain text and gets the status layout; the same text with a
    ``username`` field scores as a Slack message and is forwarded as written. Ended by TASK-37.2,
    where the webhook record declares its source and the body is parsed as that source.
    """
    webhook_surface.records.seed(hook_type="info")
    status_text = ":large_red_square: Checkout is down"

    webhook_surface.post({"text": status_text})
    webhook_surface.post({"text": status_text, "username": "monitor"})

    as_plain_text, as_slack_message = webhook_surface.all_posts
    assert as_plain_text["blocks"] != []
    assert as_slack_message["text"] == status_text
    assert as_slack_message["blocks"] == []
