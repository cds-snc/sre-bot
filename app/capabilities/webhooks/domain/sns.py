"""Amazon SNS rules that need no I/O: which URLs the bot may call, and what a signature covers.

The bot calls SNS only at ``https://sns.<region>.amazonaws.com``: a ``SigningCertURL`` (a
``.pem`` path) or a ``SubscribeURL``. A URL is parsed, never matched with a regular
expression, and refused when anything is ambiguous: another scheme, userinfo, a port, a
fragment, or a host outside that shape (decisions/security.md Webhooks; OWASP SSRF
Prevention). The canonical string is the one AWS signs, per message type
(docs.aws.amazon.com/sns/latest/dg/sns-verify-signature-of-message.html).
"""

from collections.abc import Mapping
from urllib.parse import urlsplit

_REGION_CHARACTERS = frozenset("abcdefghijklmnopqrstuvwxyz0123456789-")
_MAX_REGION_CHARS = 32
NOTIFICATION_SIGNED_FIELDS = ("Message", "MessageId", "Subject", "Timestamp", "TopicArn", "Type")
SUBSCRIPTION_SIGNED_FIELDS = ("Message", "MessageId", "SubscribeURL", "Timestamp", "Token", "TopicArn", "Type")


def _is_region(label: str) -> bool:
    return (
        0 < len(label) <= _MAX_REGION_CHARS
        and label[0].isalpha()
        and label[-1] != "-"
        and all(character in _REGION_CHARACTERS for character in label)
    )


def is_sns_host_url(url: str, *, pem_path: bool = False) -> bool:
    """True when ``url`` is https on ``sns.<region>.amazonaws.com`` with nothing ambiguous.

    Args:
        url: The URL a message names.
        pem_path: Also require a ``.pem`` path and no query (a signing certificate).
    """
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError:
        return False
    if parts.scheme != "https" or parts.username is not None or parts.password is not None or port is not None:
        return False
    if parts.fragment or any(character.isspace() for character in url):
        return False
    labels = (parts.hostname or "").split(".")
    if len(labels) != 4 or labels[0] != "sns" or labels[2:] != ["amazonaws", "com"] or not _is_region(labels[1]):
        return False
    if parts.netloc.lower() != parts.hostname:
        return False
    if pem_path:
        return parts.path.endswith(".pem") and not parts.query
    return True


def canonical_string(message: Mapping[str, str], fields: tuple[str, ...]) -> bytes:
    """The bytes SNS signed: each present field's name and value, one per line, in AWS's order."""
    lines: list[str] = []
    for name in fields:
        value = message.get(name)
        if value is None:
            continue
        lines += [name, value]
    return ("\n".join(lines) + "\n").encode("utf-8")
