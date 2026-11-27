"""Unit tests for the aws_sns protocol: signature versions, refusals and the decoded document.

Messages are signed with a test key whose self-signed certificate the static certificate port
serves, so verification runs the real RSA check. Each refusal asserts the rejection reason the
route maps to its status (403 for unauthentic, 400 for undecodable, 503 for unavailable).
"""

from datetime import timedelta

import pytest

from capabilities.webhooks.domain.inbox import ItemKind, ProtocolDelivery, Rejection, RejectReason
from capabilities.webhooks.domain.kinds import AuthTier, Owner, WebhookInstance
from capabilities.webhooks.entrypoints.http_aws_sns import AwsSnsProtocol
from capabilities.webhooks.settings import get_webhooks_settings
from contracts.operations import OperationResult
from tests.unit.capabilities.webhooks.sns_signing import (
    CERT_URL,
    SENT_AT,
    SUBSCRIBE_URL,
    TOPIC,
    StaticCertificates,
    encoded,
    signed_message,
)

pytestmark = pytest.mark.unit


def _instance(topic_arns: tuple[str, ...] = ()) -> WebhookInstance:
    return WebhookInstance(
        instance_ref="ref-1",
        name="budgets",
        owner=Owner("sre", "sre@example.com"),
        auth_tier=AuthTier.LEGACY,
        protocol="aws_sns",
        sender_kinds=("budget-alert",),
        topic_arns=topic_arns,
    )


def _protocol(certificates: StaticCertificates | None = None, *, now=SENT_AT + timedelta(minutes=1)) -> AwsSnsProtocol:
    return AwsSnsProtocol(certificates or StaticCertificates(), get_webhooks_settings(), clock=lambda: now)


@pytest.mark.parametrize("version", ["1", "2"])
async def test_signature_versions_1_and_2_verify(version: str) -> None:
    decoded = await _protocol().decode(encoded(signed_message(version=version)), {}, _instance())

    assert isinstance(decoded, ProtocolDelivery)
    assert (decoded.delivery_id, decoded.kind) == ("6f2b-4c1a-9d8e", ItemKind.EVENT)


async def test_the_document_holds_the_signed_fields_with_the_message_parsed() -> None:
    decoded = await _protocol().decode(encoded(signed_message()), {}, _instance())

    assert isinstance(decoded, ProtocolDelivery)
    assert decoded.document == {
        "Type": "Notification",
        "MessageId": "6f2b-4c1a-9d8e",
        "TopicArn": TOPIC,
        "Subject": "ALARM",
        "Timestamp": "2026-11-27T12:00:00Z",
        "Message": {"AlarmName": "cpu-high"},
    }


async def test_a_text_message_stays_text() -> None:
    decoded = await _protocol().decode(encoded(signed_message(message="plain words")), {}, _instance())

    assert isinstance(decoded, ProtocolDelivery) and isinstance(decoded.document, dict)
    assert decoded.document["Message"] == "plain words"


@pytest.mark.parametrize(
    "body",
    [
        pytest.param({**signed_message(), "Message": "tampered"}, id="tampered-message"),
        pytest.param(signed_message(Signature="bm90IGEgc2lnbmF0dXJl"), id="bad-signature"),
        pytest.param(signed_message(Signature="***"), id="signature-not-base64"),
        pytest.param(signed_message(version="3"), id="unknown-version"),
        pytest.param(signed_message(SigningCertURL="https://evil.example.com/cert.pem"), id="cert-off-host"),
        pytest.param(signed_message(SigningCertURL="http://sns.ca-central-1.amazonaws.com/c.pem"), id="cert-not-https"),
        pytest.param(
            signed_message(SigningCertURL="https://sns.ca-central-1.amazonaws.com.evil.io/c.pem"), id="cert-suffix-host"
        ),
        pytest.param(signed_message(sent_at=SENT_AT - timedelta(days=2)), id="older-than-the-replay-bound"),
    ],
)
async def test_an_unauthentic_message_is_refused_and_never_fetches_off_host(body: dict) -> None:
    certificates = StaticCertificates()

    decoded = await _protocol(certificates).decode(encoded(body), {}, _instance())

    assert decoded == Rejection(RejectReason.UNAUTHENTIC)
    assert set(certificates.fetched) <= {CERT_URL}


async def test_a_topic_outside_the_allowlist_is_refused() -> None:
    body = signed_message(topic="arn:aws:sns:ca-central-1:999999999999:other")

    decoded = await _protocol().decode(encoded(body), {}, _instance(topic_arns=(TOPIC,)))

    assert decoded == Rejection(RejectReason.UNAUTHENTIC)


async def test_an_empty_allowlist_accepts_any_verified_topic_until_backfilled() -> None:
    decoded = await _protocol().decode(encoded(signed_message()), {}, _instance())

    assert isinstance(decoded, ProtocolDelivery)


@pytest.mark.parametrize(
    "raw",
    [
        pytest.param(b"not json", id="not-json"),
        pytest.param(b"[]", id="not-an-object"),
        pytest.param(encoded({**signed_message(), "Type": "Surprise"}), id="unknown-type"),
        pytest.param(encoded({k: v for k, v in signed_message().items() if k != "MessageId"}), id="missing-field"),
        pytest.param(b'{"Type": "Notification", "Type": "Notification"}', id="duplicate-member"),
    ],
)
async def test_a_body_that_fails_the_sns_decode_is_undecodable(raw: bytes) -> None:
    assert await _protocol().decode(raw, {}, _instance()) == Rejection(RejectReason.UNDECODABLE)


async def test_a_message_type_header_that_disagrees_with_the_body_is_undecodable() -> None:
    decoded = await _protocol().decode(
        encoded(signed_message()), {"x-amz-sns-message-type": "SubscriptionConfirmation"}, _instance()
    )

    assert decoded == Rejection(RejectReason.UNDECODABLE)


async def test_a_certificate_that_could_not_be_fetched_is_unavailable_so_sns_retries() -> None:
    certificates = StaticCertificates(OperationResult.transient_error("timeout"))

    assert await _protocol(certificates).decode(encoded(signed_message()), {}, _instance()) == Rejection(RejectReason.UNAVAILABLE)


async def test_a_subscription_confirmation_carries_its_sns_subscribe_url() -> None:
    decoded = await _protocol().decode(encoded(signed_message("SubscriptionConfirmation")), {}, _instance())

    assert isinstance(decoded, ProtocolDelivery)
    assert (decoded.kind, decoded.subscribe_url) == (ItemKind.SUBSCRIPTION_CONFIRMATION, SUBSCRIBE_URL)
    assert isinstance(decoded.document, dict) and "Token" not in decoded.document


async def test_a_signed_subscribe_url_off_an_sns_host_is_refused() -> None:
    body = signed_message("SubscriptionConfirmation", SubscribeURL="https://evil.example.com/confirm")

    assert await _protocol().decode(encoded(body), {}, _instance()) == Rejection(RejectReason.UNDECODABLE)


async def test_an_unsubscribe_confirmation_decodes_to_its_kind() -> None:
    decoded = await _protocol().decode(encoded(signed_message("UnsubscribeConfirmation")), {}, _instance())

    assert isinstance(decoded, ProtocolDelivery) and decoded.kind is ItemKind.UNSUBSCRIBE_CONFIRMATION
