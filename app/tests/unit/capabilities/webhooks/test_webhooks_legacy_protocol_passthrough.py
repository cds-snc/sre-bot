"""Unit tests for the legacy_slack_json protocol and the passthrough-hardening fingerprint.

The protocol decodes bytes into a delivery; assertions check the delivery id (local, or keyed
by an Idempotency-Key), the refusals, and the fingerprint, which names fields and never values.
"""

import json

import pytest

from capabilities.webhooks.domain.inbox import ProtocolDelivery, Rejection, RejectReason
from capabilities.webhooks.domain.kinds import AuthTier, Owner, WebhookInstance
from capabilities.webhooks.domain.passthrough import hardening_fingerprint
from capabilities.webhooks.entrypoints.http_legacy_slack_json import LegacySlackJsonProtocol
from capabilities.webhooks.settings import get_webhooks_settings

pytestmark = pytest.mark.unit

INSTANCE = WebhookInstance(
    instance_ref="ref-2",
    name="deploys",
    owner=Owner("sre", "sre@example.com"),
    auth_tier=AuthTier.LEGACY,
    protocol="legacy_slack_json",
    sender_kinds=(),
)


async def _decode(body: object, headers: dict[str, str] | None = None) -> ProtocolDelivery | Rejection:
    raw = body if isinstance(body, bytes) else json.dumps(body).encode()
    return await LegacySlackJsonProtocol(get_webhooks_settings()).decode(raw, headers or {}, INSTANCE)


async def test_without_a_key_each_delivery_gets_its_own_local_id() -> None:
    first = await _decode({"text": "deployed"})
    second = await _decode({"text": "deployed"})

    assert isinstance(first, ProtocolDelivery) and isinstance(second, ProtocolDelivery)
    assert first.delivery_id.startswith("local:") and first.delivery_id != second.delivery_id


async def test_an_idempotency_key_makes_redeliveries_share_their_id() -> None:
    first = await _decode({"text": "deployed"}, {"idempotency-key": "deploy-42"})
    second = await _decode({"text": "again"}, {"idempotency-key": "deploy-42"})

    assert isinstance(first, ProtocolDelivery) and isinstance(second, ProtocolDelivery)
    assert first.delivery_id == second.delivery_id == "idem:deploy-42"


@pytest.mark.parametrize("key", ["", "has space", "x" * 256, "naïve"])
async def test_a_malformed_idempotency_key_is_refused(key: str) -> None:
    assert await _decode({"text": "x"}, {"idempotency-key": key}) == Rejection(RejectReason.UNDECODABLE)


@pytest.mark.parametrize("body", [b"[1, 2]", b'"text"', b"{", b'{"text": "a", "text": "b"}'])
async def test_a_body_that_is_not_a_strict_json_object_is_refused(body: bytes) -> None:
    assert await _decode(body) == Rejection(RejectReason.UNDECODABLE)


def test_the_fingerprint_names_the_hardening_fields_and_never_their_values() -> None:
    message = {
        "text": "hi",
        "username": "Totally the CEO",
        "thread_ts": "1.2",
        "link_names": True,
        "blocks": [
            {"type": "actions", "block_id": "b1", "elements": [{"type": "button", "action_id": "incident.call", "value": "x"}]},
            {"type": "section", "accessory": {"type": "button", "url": "https://example.com", "action_id": "link"}},
        ],
        "attachments": [{"callback_id": "legacy_cb"}],
    }

    fingerprint = hardening_fingerprint(message)

    assert fingerprint == (
        "action_id",
        "block_id",
        "callback_id",
        "interactive_without_url",
        "link_names",
        "thread_ts",
        "username",
    )
    assert not {"Totally the CEO", "incident.call", "legacy_cb"} & set(fingerprint)


async def test_a_plain_message_has_an_empty_fingerprint() -> None:
    delivery = await _decode({"text": "hello", "channel": "C-PAYLOAD"})

    assert isinstance(delivery, ProtocolDelivery) and delivery.fingerprint == ()
