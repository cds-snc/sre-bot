"""The status-update item layout: pure conversion between ``StatusUpdate`` and its stored item.

Each update is its own item under ``PK = INCIDENT#<incident id>`` and
``SK = UPDATE#<sequence, zero-padded to 6>``, so a newest-first query on the
partition lists an incident's updates and a one-item query reads the latest.
The keys and attribute names are permanent: they are the items the
provisioned table already holds. Times are UTC ISO-8601 strings; optional
attributes are absent when unset. ``RecordStatusUpdateStore`` in
``core/store.py`` reads and writes these items through the records contract.
"""

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from features.incident.core.domain import (
    StatusUpdate,
    StatusUpdateOrigin,
    StatusUpdateStage,
    StatusUpdateState,
    StatusUpdateText,
)

PARTITION_ATTRIBUTE = "PK"
SORT_ATTRIBUTE = "SK"
SORT_KEY_PREFIX = "UPDATE#"
# Written only when set; a transition that clears one removes the attribute.
OPTIONAL_ATTRIBUTES = ("approver", "approved_at", "published_at", "published_by", "origin")

_TEXT_FIELDS = ("affected_service", "impact", "current_action", "workaround")


class UnreadableStatusUpdateItemError(Exception):
    """A stored item that does not convert into a ``StatusUpdate``."""


def partition_key(incident_id: str) -> str:
    """Return the partition value holding every item of the incident."""
    return f"INCIDENT#{incident_id}"


def status_update_key(incident_id: str, sequence: int) -> dict[str, Any]:
    """Return the full key of the update at ``sequence``."""
    return {PARTITION_ATTRIBUTE: partition_key(incident_id), SORT_ATTRIBUTE: f"{SORT_KEY_PREFIX}{sequence:06d}"}


def status_update_item(update: StatusUpdate) -> dict[str, Any]:
    """Return the stored item of ``update``, keys included."""
    item: dict[str, Any] = {
        **status_update_key(update.incident_id, update.sequence),
        "incident_id": update.incident_id,
        "sequence": update.sequence,
        "state": update.state.value,
        "stage": update.stage.value,
        "en": _text_item(update.en),
        "fr": _text_item(update.fr),
        "next_update_at": _time_item(update.next_update_at),
        "author": update.author,
        "transcript_cutoff": _time_item(update.transcript_cutoff),
        "transcript_fingerprint": update.transcript_fingerprint,
        "created_at": _time_item(update.created_at),
    }
    optional: dict[str, Any] = {
        "approver": update.approver,
        "approved_at": _time_item(update.approved_at) if update.approved_at is not None else None,
        "published_at": _time_item(update.published_at) if update.published_at is not None else None,
        "published_by": update.published_by,
        "origin": update.origin.value if update.origin is not None else None,
    }
    item.update({name: value for name, value in optional.items() if value is not None})
    return item


def parse_status_update_item(item: Mapping[str, Any]) -> StatusUpdate:
    """Return the ``StatusUpdate`` stored as ``item``.

    Raises:
        UnreadableStatusUpdateItemError: An attribute is missing or holds a value of the wrong shape.
    """
    try:
        return StatusUpdate(
            incident_id=_text(item["incident_id"]),
            sequence=int(item["sequence"]),
            state=StatusUpdateState(item["state"]),
            stage=StatusUpdateStage(item["stage"]),
            en=_text_from_item(item["en"]),
            fr=_text_from_item(item["fr"]),
            next_update_at=datetime.fromisoformat(item["next_update_at"]),
            author=_text(item["author"]),
            transcript_cutoff=datetime.fromisoformat(item["transcript_cutoff"]),
            transcript_fingerprint=_text(item["transcript_fingerprint"]),
            created_at=datetime.fromisoformat(item["created_at"]),
            approver=_text(item["approver"]) if "approver" in item else None,
            approved_at=datetime.fromisoformat(item["approved_at"]) if "approved_at" in item else None,
            published_at=datetime.fromisoformat(item["published_at"]) if "published_at" in item else None,
            published_by=_text(item["published_by"]) if "published_by" in item else None,
            origin=StatusUpdateOrigin(item["origin"]) if "origin" in item else None,
        )
    except (KeyError, TypeError, ValueError, ArithmeticError) as exc:
        raise UnreadableStatusUpdateItemError(f"{type(exc).__name__}: {exc}") from exc


def _text_item(text: StatusUpdateText) -> dict[str, str]:
    return {name: getattr(text, name) for name in _TEXT_FIELDS}


def _time_item(value: datetime) -> str:
    return value.astimezone(UTC).isoformat()


def _text_from_item(value: Mapping[str, Any]) -> StatusUpdateText:
    return StatusUpdateText(**{name: _text(value[name]) for name in _TEXT_FIELDS})


def _text(value: Any) -> str:
    if not isinstance(value, str):
        raise TypeError(f"expected a string, got {type(value).__name__}")
    return value
