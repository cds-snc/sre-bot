"""The ``aws_sns`` wire protocol: verify, delivery id and decode, on the raw body.

Every message type is verified before anything reads it (decisions/security.md Webhooks):
SignatureVersion 1 (RSA with SHA1) and 2 (RSA with SHA256) are accepted and the version is
logged; the signing certificate comes from an SNS host only; a message older than the replay
bound is refused, so a captured message never outlives its dedupe key (OWASP Webhook Security:
a signed timestamp with tolerance plus event-id dedupe); a topic outside the instance's
allowlist is refused. Each refusal is ``UNAUTHENTIC``, which the route answers 403 with a
generic body. A certificate that could not be fetched is ``UNAVAILABLE`` (503), so SNS retries.

The decoded document holds the signed fields only, with ``Message`` parsed when it is a strict
JSON object, so sender kinds match ``$.Message.<field>`` (decisions/webhooks.md 2).
"""

import base64
import binascii
from collections.abc import Callable, Mapping
from datetime import datetime, timedelta
from typing import Any

import structlog
from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from pydantic import ValidationError

from capabilities.webhooks.domain.events import JsonDocument
from capabilities.webhooks.domain.inbox import ItemKind, ProtocolDelivery, Rejection, RejectReason
from capabilities.webhooks.domain.kinds import WebhookInstance
from capabilities.webhooks.domain.sns import (
    NOTIFICATION_SIGNED_FIELDS,
    SUBSCRIPTION_SIGNED_FIELDS,
    canonical_string,
    is_sns_host_url,
)
from capabilities.webhooks.domain.strict_json import StrictJsonError, loads_strict
from capabilities.webhooks.interfaces import SnsCertificates
from capabilities.webhooks.schemas import (
    SNS_MESSAGE,
    SnsMessage,
    SnsNotification,
    SnsSubscriptionConfirmation,
)
from capabilities.webhooks.settings import WebhooksSettings
from contracts.operations import OperationStatus

logger = structlog.get_logger()

PROTOCOL = "aws_sns"
MESSAGE_TYPE_HEADER = "x-amz-sns-message-type"
_HASHES: dict[str, Callable[[], hashes.HashAlgorithm]] = {"1": hashes.SHA1, "2": hashes.SHA256}
_DOCUMENT_FIELDS = ("Type", "MessageId", "TopicArn", "Subject", "Timestamp", "Message")


def _undecodable() -> Rejection:
    return Rejection(RejectReason.UNDECODABLE)


def _unauthentic(instance: WebhookInstance, reason: str) -> Rejection:
    logger.warning("webhook_sns_rejected", instance_ref=instance.instance_ref, reason=reason)
    return Rejection(RejectReason.UNAUTHENTIC)


def _signed_fields(message: SnsMessage) -> dict[str, str]:
    return {name: value for name, value in message.model_dump().items() if isinstance(value, str)}


def _signature_valid(message: SnsMessage, certificate_pem: bytes, now: datetime) -> bool:
    fields = NOTIFICATION_SIGNED_FIELDS if isinstance(message, SnsNotification) else SUBSCRIPTION_SIGNED_FIELDS
    try:
        certificate = x509.load_pem_x509_certificate(certificate_pem)
        key = certificate.public_key()
        if not isinstance(key, rsa.RSAPublicKey):
            return False
        if not certificate.not_valid_before_utc <= now <= certificate.not_valid_after_utc:
            return False
        key.verify(
            base64.b64decode(message.Signature, validate=True),
            canonical_string(_signed_fields(message), fields),
            padding.PKCS1v15(),
            _HASHES[message.SignatureVersion](),
        )
    except InvalidSignature, ValueError, TypeError, binascii.Error:
        return False
    return True


def _document(message: SnsMessage, max_depth: int) -> JsonDocument:
    fields = _signed_fields(message)
    document: dict[str, Any] = {name: fields[name] for name in _DOCUMENT_FIELDS if name in fields}
    try:
        parsed = loads_strict(message.Message, max_depth=max_depth)
    except StrictJsonError:
        parsed = None
    if isinstance(parsed, dict):
        document["Message"] = parsed
    return document


class AwsSnsProtocol:
    """Verifies and decodes SNS HTTP deliveries."""

    name = PROTOCOL

    def __init__(self, certificates: SnsCertificates, settings: WebhooksSettings, *, clock: Callable[[], datetime]) -> None:
        self._certificates = certificates
        self._settings = settings
        self._clock = clock

    @property
    def content_types(self) -> tuple[str, ...]:
        """The media types an SNS delivery may declare."""
        return self._settings.aws_sns_content_types

    @property
    def max_body_bytes(self) -> int:
        """The body cap."""
        return self._settings.aws_sns_max_body_bytes

    async def decode(self, body: bytes, headers: Mapping[str, str], instance: WebhookInstance) -> ProtocolDelivery | Rejection:
        """Verify ``body`` as an SNS message for ``instance`` and decode it."""
        try:
            parsed = loads_strict(body, max_depth=self._settings.max_json_depth)
            message: SnsMessage = SNS_MESSAGE.validate_python(parsed)
        except StrictJsonError, ValidationError:
            return _undecodable()
        declared = headers.get(MESSAGE_TYPE_HEADER)
        if declared is not None and declared != message.Type:
            return _undecodable()
        if message.SignatureVersion not in _HASHES:
            return _unauthentic(instance, "signature_version")
        if not is_sns_host_url(message.SigningCertURL, pem_path=True):
            return _unauthentic(instance, "certificate_url")
        now = self._clock()
        try:
            sent_at = datetime.fromisoformat(message.Timestamp)
        except ValueError:
            return _undecodable()
        if sent_at.tzinfo is None:
            return _undecodable()
        if now - sent_at > timedelta(seconds=self._settings.sns_max_message_age_seconds):
            return _unauthentic(instance, "too_old")
        fetched = await self._certificates.certificate(message.SigningCertURL)
        if fetched.status is OperationStatus.TRANSIENT_ERROR:
            return Rejection(RejectReason.UNAVAILABLE)
        if not fetched.is_success or fetched.data is None:
            return _unauthentic(instance, "certificate")
        if not _signature_valid(message, fetched.data, now):
            return _unauthentic(instance, "signature")
        if instance.topic_arns and message.TopicArn not in instance.topic_arns:
            return _unauthentic(instance, "topic")
        logger.info(
            "webhook_sns_verified",
            instance_ref=instance.instance_ref,
            signature_version=message.SignatureVersion,
            type=message.Type,
        )
        document = _document(message, self._settings.max_json_depth)
        if isinstance(message, SnsNotification):
            return ProtocolDelivery(delivery_id=message.MessageId, kind=ItemKind.EVENT, document=document)
        if not is_sns_host_url(message.SubscribeURL):
            return _undecodable()
        kind = (
            ItemKind.SUBSCRIPTION_CONFIRMATION
            if isinstance(message, SnsSubscriptionConfirmation)
            else ItemKind.UNSUBSCRIBE_CONFIRMATION
        )
        return ProtocolDelivery(delivery_id=message.MessageId, kind=kind, document=document, subscribe_url=message.SubscribeURL)
