"""Write a ``TimelineEntry`` as a timeline item, and derive its key and system entry ids.

Pure: no store and no I/O. An item sits under its incident (partition
``incident_id``) at ``entry_key`` = ``'<posted_at>#<entry_id>'``, so entries sort
by time and two entries posted at the same instant stay distinct. A system
entry stores its structured payload (``severity_previous`` / ``severity_current``
as levels, absent when unrated) and no text: it is rendered per locale when read.
Ids of system entries are uuid5 values in ``TIMELINE_NAMESPACE``, derived from the
change and its time, so a retry of the same change derives the same id.
"""

from datetime import datetime
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from features.incident.core.adapters.incident_items import format_stored_time, message_reference_item
from features.incident.core.domain import SeverityChange, TimelineEntry, TimelineEntryKind

PARTITION_ATTRIBUTE = "incident_id"
SORT_ATTRIBUTE = "entry_key"

# Fixed for good: changing it changes every derived id, so retries would no longer match.
TIMELINE_NAMESPACE = uuid5(NAMESPACE_URL, "urn:sre-bot:incident:timeline")


def entry_key(posted_at: datetime, entry_id: str) -> str:
    """Return the sort key of an entry: its stored time, then its id."""
    return f"{format_stored_time(posted_at)}#{entry_id}"


def severity_entry_id(incident_id: str, change: SeverityChange, at: datetime) -> str:
    """Return the id of the entry recording ``change`` at ``at``: the same change at the same time is the same entry."""
    levels = ["none" if level is None else str(int(level)) for level in (change.previous, change.current)]
    name = "|".join([incident_id, TimelineEntryKind.SEVERITY_CHANGED.value, *levels, format_stored_time(at)])
    return str(uuid5(TIMELINE_NAMESPACE, name))


def timeline_entry_item(entry: TimelineEntry) -> dict[str, Any]:
    """Return the stored item of ``entry``; optional attributes only when set."""
    item: dict[str, Any] = {
        PARTITION_ATTRIBUTE: entry.incident_id,
        SORT_ATTRIBUTE: entry_key(entry.posted_at, entry.entry_id),
        "entry_id": entry.entry_id,
        "kind": entry.kind.value,
        "posted_at": format_stored_time(entry.posted_at),
        "author": entry.author,
    }
    if entry.text:
        item["text"] = entry.text
    if entry.source_message is not None:
        item["source_message"] = message_reference_item(entry.source_message)
    if entry.severity_change is not None:
        for name, level in (
            ("severity_previous", entry.severity_change.previous),
            ("severity_current", entry.severity_change.current),
        ):
            if level is not None:
                item[name] = int(level)
    return item
