"""Test helpers that sign SNS messages the way AWS does.

A module-scoped RSA key and a self-signed certificate stand in for AWS's signing certificate;
``signed_message`` builds a message of a given type and signs its canonical string with
SignatureVersion 1 (SHA1) or 2 (SHA256). ``StaticCertificates`` is the certificate port serving
that PEM, so tests never fetch.
"""

import base64
import json
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from typing import Any

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.x509.oid import NameOID

from capabilities.webhooks.domain.sns import NOTIFICATION_SIGNED_FIELDS, SUBSCRIPTION_SIGNED_FIELDS, canonical_string
from capabilities.webhooks.interfaces import SnsCertificates
from contracts.operations import OperationResult

CERT_URL = "https://sns.ca-central-1.amazonaws.com/SimpleNotificationService-0000.pem"
SUBSCRIBE_URL = "https://sns.ca-central-1.amazonaws.com/?Action=ConfirmSubscription&TopicArn=t&Token=abc"
TOPIC = "arn:aws:sns:ca-central-1:123456789012:budgets"
SENT_AT = datetime(2026, 11, 27, 12, 0, tzinfo=UTC)


@lru_cache(maxsize=1)
def signing_key() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@lru_cache(maxsize=1)
def certificate_pem() -> bytes:
    key = signing_key()
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "sns.amazonaws.com")])
    certificate = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(1)
        .not_valid_before(SENT_AT - timedelta(days=30))
        .not_valid_after(SENT_AT + timedelta(days=365))
        .sign(key, hashes.SHA256())
    )
    return certificate.public_bytes(serialization.Encoding.PEM)


def signed_message(
    message_type: str = "Notification",
    *,
    version: str = "2",
    message: str = '{"AlarmName": "cpu-high"}',
    topic: str = TOPIC,
    sent_at: datetime = SENT_AT,
    **overrides: Any,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "Type": message_type,
        "MessageId": "6f2b-4c1a-9d8e",
        "TopicArn": topic,
        "Message": message,
        "Timestamp": sent_at.isoformat().replace("+00:00", "Z"),
        "SignatureVersion": version,
        "SigningCertURL": CERT_URL,
    }
    if message_type == "Notification":
        body["Subject"] = "ALARM"
        fields = NOTIFICATION_SIGNED_FIELDS
    else:
        body["Token"] = "abc"
        body["SubscribeURL"] = SUBSCRIBE_URL
        fields = SUBSCRIPTION_SIGNED_FIELDS
    body.update({name: value for name, value in overrides.items() if name != "Signature"})
    digest = hashes.SHA1() if version == "1" else hashes.SHA256()  # noqa: S303 - SNS SignatureVersion 1 is SHA1
    signature = signing_key().sign(canonical_string(body, fields), padding.PKCS1v15(), digest)
    body["Signature"] = overrides.get("Signature", base64.b64encode(signature).decode())
    return body


def encoded(body: dict[str, Any]) -> bytes:
    return json.dumps(body).encode()


class StaticCertificates(SnsCertificates):
    """Serves the test certificate, or a given failure, and counts fetches."""

    def __init__(self, result: OperationResult[bytes] | None = None) -> None:
        self.result = result
        self.fetched: list[str] = []

    async def certificate(self, url: str) -> OperationResult[bytes]:
        self.fetched.append(url)
        return self.result if self.result is not None else OperationResult.success(data=certificate_pem())
