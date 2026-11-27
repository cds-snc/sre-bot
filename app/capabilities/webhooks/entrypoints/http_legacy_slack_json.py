"""The ``legacy_slack_json`` wire protocol: a sender-built Slack message, passed through.

The legacy tier has no signature: the URL token is the secret (decisions/security.md, the
hardened secret-URL tier, time-boxed). The body must be a strict JSON object. The protocol has
no delivery id, so deliveries are not deduplicated (decisions/webhooks.md Consequences, the
written exception), except where the sender sends an ``Idempotency-Key`` header: printable
ASCII within a length cap, deduplicated under the instance's prefix. A malformed key is
refused rather than ignored. The delivery records the passthrough-hardening fields it
carries, by name only.
TODO(TASK-48): delete this protocol once the last instance leaves the legacy tier.
"""

from collections.abc import Mapping

from capabilities.webhooks.domain.events import local_event_id
from capabilities.webhooks.domain.inbox import ItemKind, ProtocolDelivery, Rejection, RejectReason
from capabilities.webhooks.domain.kinds import WebhookInstance
from capabilities.webhooks.domain.passthrough import hardening_fingerprint
from capabilities.webhooks.domain.strict_json import StrictJsonError, loads_strict
from capabilities.webhooks.settings import WebhooksSettings

PROTOCOL = "legacy_slack_json"
IDEMPOTENCY_KEY_HEADER = "idempotency-key"
IDEMPOTENCY_ID_PREFIX = "idem:"


def _valid_key(key: str, max_chars: int) -> bool:
    return 0 < len(key) <= max_chars and all(" " < character <= "~" for character in key)


class LegacySlackJsonProtocol:
    """Decodes legacy Slack-shaped deliveries."""

    name = PROTOCOL

    def __init__(self, settings: WebhooksSettings) -> None:
        self._settings = settings

    @property
    def content_types(self) -> tuple[str, ...]:
        """The media types a legacy delivery may declare."""
        return self._settings.legacy_slack_json_content_types

    @property
    def max_body_bytes(self) -> int:
        """The body cap."""
        return self._settings.legacy_slack_json_max_body_bytes

    async def decode(self, body: bytes, headers: Mapping[str, str], instance: WebhookInstance) -> ProtocolDelivery | Rejection:
        """Decode ``body`` as a Slack-shaped message for ``instance``."""
        try:
            message = loads_strict(body, max_depth=self._settings.max_json_depth)
        except StrictJsonError:
            return Rejection(RejectReason.UNDECODABLE)
        if not isinstance(message, dict):
            return Rejection(RejectReason.UNDECODABLE)
        key = headers.get(IDEMPOTENCY_KEY_HEADER)
        if key is None:
            delivery_id = local_event_id()
        elif _valid_key(key, self._settings.idempotency_key_max_chars):
            delivery_id = f"{IDEMPOTENCY_ID_PREFIX}{key}"
        else:
            return Rejection(RejectReason.UNDECODABLE)
        return ProtocolDelivery(
            delivery_id=delivery_id, kind=ItemKind.EVENT, document=message, fingerprint=hardening_fingerprint(message)
        )
