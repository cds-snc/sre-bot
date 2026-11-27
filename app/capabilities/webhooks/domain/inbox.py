"""The durable inbox: one item per delivery, its states and its transitions (pure).

A delivery is persisted before it is acknowledged; the item's own conditional insert is the
delivery idempotency (decisions/webhooks.md 3 Pipeline, reliability.md). An item is written
already ``processing`` under the inserting worker's owner token, so the hot path makes one
write before it answers. Every later transition is a guarded update on the state and owner
the writer read, so the inline attempt and the sweeper never both own an item. An item
records each finished target (a post, a consumer, a handler), so a retry repeats none of
them. Retries back off exponentially with full jitter (AWS Builders' Library, "Timeouts,
retries and backoff with jitter").
"""

import math
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import datetime
from enum import StrEnum

from capabilities.webhooks.domain.events import JsonDocument
from capabilities.webhooks.domain.kinds import Destination

ITEM_KEY_PREFIX = "webhooks"


class ItemKind(StrEnum):
    """What the processor does with an item."""

    EVENT = "event"
    SUBSCRIPTION_CONFIRMATION = "subscription_confirmation"
    UNSUBSCRIBE_CONFIRMATION = "unsubscribe_confirmation"


class ItemState(StrEnum):
    """An item's state. ``processing`` holds a lease until ``due_at``; the last three are terminal."""

    PROCESSING = "processing"
    RETRY = "retry"
    DONE = "done"
    RENDER_FAILED = "render_failed"
    DEAD = "dead"


DUE_STATES = frozenset({ItemState.PROCESSING, ItemState.RETRY})


class RejectReason(StrEnum):
    """Why a protocol refused a delivery; the HTTP entrypoint maps each to its status."""

    UNDECODABLE = "undecodable"
    UNAUTHENTIC = "unauthentic"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class Rejection:
    """A delivery a protocol refused; nothing is persisted."""

    reason: RejectReason


@dataclass(frozen=True)
class ProtocolDelivery:
    """What a protocol hands the inbox: the delivery id, what to do, and the decoded envelope.

    ``document`` is what sender kinds match and the fallback shows; it never holds raw
    headers. ``fingerprint`` names the passthrough-hardening fields present, never their values.
    """

    delivery_id: str
    kind: ItemKind
    document: JsonDocument
    fingerprint: tuple[str, ...] = ()
    subscribe_url: str | None = None


@dataclass(frozen=True)
class InboxItem:
    """One delivery in the inbox.

    Attributes:
        key: ``webhooks:<instance_ref>:<delivery id>``, the dedupe key.
        owner: The token of the worker that holds the item, or None.
        due_at: Epoch seconds when the lease ends or the retry is due; None once terminal.
        attempts: Processing attempts started, the inline one included.
        done_targets: Targets that finished, skipped by a retry.
    """

    key: str
    instance_ref: str
    delivery_id: str
    protocol: str
    kind: ItemKind
    envelope: JsonDocument
    received_at: datetime
    expires_at: int
    state: ItemState
    owner: str | None
    due_at: int | None
    attempts: int
    done_targets: frozenset[str] = field(default=frozenset())
    fingerprint: tuple[str, ...] = ()
    subscribe_url: str | None = None
    last_error: str | None = None


def item_key(instance_ref: str, delivery_id: str) -> str:
    """The dedupe key of a delivery: the instance's internal reference, never the URL token."""
    return f"{ITEM_KEY_PREFIX}:{instance_ref}:{delivery_id}"


def new_item(
    instance_ref: str,
    protocol: str,
    delivery: ProtocolDelivery,
    *,
    now: datetime,
    owner: str,
    lease_seconds: int,
    ttl_seconds: int,
) -> InboxItem:
    """The item a delivery is inserted as: already processing under ``owner``, its first attempt."""
    epoch = int(now.timestamp())
    return InboxItem(
        key=item_key(instance_ref, delivery.delivery_id),
        instance_ref=instance_ref,
        delivery_id=delivery.delivery_id,
        protocol=protocol,
        kind=delivery.kind,
        envelope=delivery.document,
        received_at=now,
        expires_at=epoch + ttl_seconds,
        state=ItemState.PROCESSING,
        owner=owner,
        due_at=epoch + lease_seconds,
        attempts=1,
        fingerprint=delivery.fingerprint,
        subscribe_url=delivery.subscribe_url,
    )


def claimable(item: InboxItem, now: datetime) -> bool:
    """True when a retry is due or a processing lease has run out."""
    return item.state in DUE_STATES and item.due_at is not None and item.due_at <= now.timestamp()


def claimed(item: InboxItem, *, owner: str, now: datetime, lease_seconds: int) -> InboxItem:
    """The item taken by ``owner`` for one more attempt."""
    return replace(
        item, state=ItemState.PROCESSING, owner=owner, due_at=int(now.timestamp()) + lease_seconds, attempts=item.attempts + 1
    )


def with_target_done(item: InboxItem, target: str) -> InboxItem:
    """The item with ``target`` recorded as finished."""
    return replace(item, done_targets=item.done_targets | {target})


def finished(item: InboxItem, state: ItemState, *, error: str | None = None) -> InboxItem:
    """The item in a terminal state, out of the due index and owned by no one."""
    if state in DUE_STATES:
        raise ValueError(f"{state} is not a terminal state")
    return replace(item, state=state, owner=None, due_at=None, last_error=error)


def retry_scheduled(item: InboxItem, *, retry_at: int, error: str) -> InboxItem:
    """The item waiting for its next attempt at ``retry_at``."""
    return replace(item, state=ItemState.RETRY, owner=None, due_at=retry_at, last_error=error)


def next_retry_at(
    now: datetime,
    *,
    attempts: int,
    retry_after: float | None,
    base_seconds: int,
    max_seconds: int,
    random: Callable[[], float],
) -> int:
    """When the next attempt is due: full-jitter exponential backoff, never before ``retry_after``.

    The delay is uniform in ``[0, min(max, base * 2 ** (attempts - 1))]``; a platform's
    ``retry_after`` (a 429) is a floor, capped at ``max_seconds``.
    """
    ceiling = min(max_seconds, base_seconds * (1 << max(attempts - 1, 0)))
    delay = ceiling * random()
    if retry_after is not None:
        delay = max(delay, min(retry_after, max_seconds))
    return math.ceil(now.timestamp() + delay)


def post_target(destination: Destination) -> str:
    """The progress key of a post to ``destination``."""
    return f"post:{destination.system}:{destination.tenant}:{destination.conversation_id}"


def consume_target(plugin: str) -> str:
    """The progress key of a consumer's ``consume``."""
    return f"consume:{plugin}"


def handler_target(handler_id: str) -> str:
    """The progress key of a kind's handler."""
    return f"handler:{handler_id}"
