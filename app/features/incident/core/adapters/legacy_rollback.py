"""Rollback guard for the legacy incident modules: read an upgraded item, translate a legacy write.

Pure, no I/O. The legacy readers build their ``Incident`` from ``legacy_view``,
which prefers the end-state attributes of an item at ``RECORD_VERSION`` or above
and falls back to the legacy ones. The legacy field writer asks ``translated_update``
what to write on such an item: only the end-state attribute, never both names.
This lets a reverted reader cutover keep working on items the rebuilt writers
upgraded. Only ``modules.incident`` imports it; no end-state reader or core module may.
"""
# TODO(TASK-145.7.10): remove with the legacy model

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, TypeIs

from features.incident.common.vocabulary import IncidentStatus, Severity
from features.incident.core.adapters.incident_items import OPEN_BUCKET, RECORD_VERSION, format_stored_time

_TIMES = {"detection_time": "detected_at", "start_impact_time": "impact_started_at", "end_impact_time": "impact_ended_at"}
_REFERENCE_URLS = {"report_url": "report", "meet_url": "video_call"}
_STATUSES = {status.casefold(): status for status in IncidentStatus}
_OPEN_INDEX = ("open_bucket", "opened_at")


class UntranslatableValueError(ValueError):
    """A legacy field value that has no end-state form."""


@dataclass(frozen=True)
class TranslatedUpdate:
    """The end-state attributes one legacy field write sets and removes.

    Attributes:
        sets: Attribute to DynamoDB attribute value, set unconditionally.
        removes: Attributes removed.
        sets_if_absent: Attribute to DynamoDB attribute value, set only where the item has none.
    """

    sets: Mapping[str, dict[str, Any]]
    removes: tuple[str, ...] = ()
    sets_if_absent: Mapping[str, dict[str, Any]] = field(default_factory=dict)

    def expression(self) -> tuple[str, dict[str, str], dict[str, dict[str, Any]]]:
        """Return the UpdateExpression with its attribute names and values."""
        assignments = [f"#{name} = :{name}" for name in self.sets]
        assignments += [f"#{name} = if_not_exists(#{name}, :{name})" for name in self.sets_if_absent]
        parts = [f"SET {', '.join(assignments)}"] if assignments else []
        if self.removes:
            parts.append(f"REMOVE {', '.join(f'#{name}' for name in self.removes)}")
        attributes = [*self.sets, *self.sets_if_absent, *self.removes]
        values = {f":{name}": value for name, value in {**self.sets, **self.sets_if_absent}.items()}
        return " ".join(parts), {f"#{name}": name for name in attributes}, values


def legacy_view(item: Mapping[str, Any]) -> dict[str, Any]:
    """Return ``item`` with its legacy attributes filled from the end-state ones, for the legacy ``Incident``.

    The end-state attribute wins when present and readable; the legacy one is the fallback.
    Extra end-state attributes stay in the result: the caller validates with ``extra="ignore"``.
    """
    view = dict(item)
    severity = item.get("severity")
    if _is_level(severity):
        view["severity"] = f"sev-{int(severity)}"
    for legacy, stored in _TIMES.items():
        parsed = _parse_stored_time(item.get(stored))
        if parsed is not None:
            view[legacy] = str(parsed.timestamp())
    title = item.get("title")
    if isinstance(title, str) and title:
        view["name"] = title
    for legacy, reference in _REFERENCE_URLS.items():
        stored_reference = item.get(reference)
        url = stored_reference.get("url") if isinstance(stored_reference, Mapping) else None
        if isinstance(url, str) and url:
            view[legacy] = url
    return view


def translated_update(field: str, value: str, *, marker: int | None, now: datetime) -> TranslatedUpdate | None:
    """Return the end-state write for a legacy field on an item at ``marker``, or ``None`` to write the legacy attribute.

    ``None`` for an item without the marker or a field that has no end-state counterpart.
    Raises ``UntranslatableValueError`` for a value the end-state shape cannot hold.
    """
    if marker is None or marker < RECORD_VERSION:
        return None
    if field == "severity":
        return _severity_update(value)
    if field in _TIMES:
        return TranslatedUpdate({_TIMES[field]: {"S": _epoch_to_stored(value)}})
    if field == "status":
        return _status_update(value, now)
    return None


def _is_level(value: object) -> TypeIs[int | Decimal]:
    return isinstance(value, int | Decimal) and not isinstance(value, bool) and value == int(value) and value in set(Severity)


def _parse_stored_time(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed.astimezone(UTC) if parsed.utcoffset() is not None else None


def _epoch_to_stored(value: str) -> str:
    try:
        return format_stored_time(datetime.fromtimestamp(float(value), UTC))
    except ValueError, OverflowError, OSError:
        raise UntranslatableValueError("time") from None


def _severity_update(value: str) -> TranslatedUpdate:
    text = "".join(value.split()).casefold()
    if text in ("", "none"):
        return TranslatedUpdate({}, removes=("severity",))
    if len(text) == 5 and text.startswith("sev-") and text[4] in "01234":
        return TranslatedUpdate({"severity": {"N": text[4]}})
    raise UntranslatableValueError("severity")


def _status_update(value: str, now: datetime) -> TranslatedUpdate:
    status = _STATUSES.get(value.strip().casefold())
    if status is None:
        raise UntranslatableValueError("status")
    sets: dict[str, dict[str, Any]] = {"status": {"S": status.value}}
    if not status.is_open:
        return TranslatedUpdate(sets, removes=_OPEN_INDEX)
    sets["open_bucket"] = {"S": OPEN_BUCKET}
    return TranslatedUpdate(sets, sets_if_absent={"opened_at": {"S": format_stored_time(now)}})
