"""Upgrade a legacy incident item to the end-state item shape.

The one legacy mapping (decisions/incident-management.md, Migration): the store
applies it on read to items without ``record_version`` and the legacy upgrade
job (TASK-145.5.7) writes its result. The upgraded item is read by the
end-state parser unchanged. Deleted with the legacy module once the upgrade
job reports nothing pending.

Pure and never raising: no store, no settings (the configured tenant per
workplace system is passed in) and no guessing. A required value that cannot be
matched makes the whole item an ``UnreadableLegacyItem`` naming the incident
id, the legacy attribute and its stored value. An optional value that cannot be
matched is dropped and logged with the incident id and attribute, never a link.

The upgraded item holds the record's attributes only: the writers and the
upgrade job add ``record_version`` and the open index attributes, and
``channel_id`` stays on the stored item as the by_channel key.
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import urlsplit

import structlog

from contracts.workplace import WorkplaceSystem
from features.incident.common.vocabulary import IncidentStatus
from features.incident.core.adapters.incident_items import format_stored_time

logger = structlog.get_logger()

_STATUSES = {status.casefold(): status for status in IncidentStatus}
_SEVERITY = re.compile(r"sev-([0-4])")
_REPORT_DOCUMENT_ID = re.compile(r"/document/d/([A-Za-z0-9_-]+)")
_MEET_HOST = "meet.google.com"
_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)
# Legacy optional times, by their record field.
_TIMES = {"detection_time": "detected_at", "start_impact_time": "impact_started_at", "end_impact_time": "impact_ended_at"}
_ROLES = ("incident_commander", "operations_lead")


@dataclass(frozen=True)
class UpgradedItem:
    """A legacy item in the end-state item shape, ready for the end-state parser."""

    item: dict[str, Any]


@dataclass(frozen=True)
class UnreadableLegacyItem:
    """A legacy item with a required value the mapping cannot match; fixed by hand.

    Attributes:
        incident_id: The stored ``id`` of the item, whatever its type.
        field: The legacy attribute that cannot be matched.
        value: Its stored value.
    """

    incident_id: object
    field: str
    value: object


class _Unreadable(Exception):
    def __init__(self, field: str, value: object) -> None:
        super().__init__(field)
        self.field = field
        self.value = value


def upgrade_legacy_item(item: Mapping[str, Any], tenants: Mapping[WorkplaceSystem, str]) -> UpgradedItem | UnreadableLegacyItem:
    """Return the end-state form of a legacy item, or why it cannot be read.

    ``tenants`` is the configured tenant per workplace system; a reference whose
    system has none makes the item unreadable rather than losing the reference.
    """
    incident_id = item.get("id")
    try:
        upgraded: dict[str, Any] = {
            "id": _required_text(item, "id"),
            "title": _required_text(item, "name"),
            "status": _required_status(item),
            "declared_by": _required_text(item, "user_id"),
            "declared_at": _required_time(item),
            "security_incident": _security_flag(item),
        }
        optional = {
            "product": _product(item, incident_id),
            "severity": _severity(item, incident_id),
            **{field: _optional_time(item, legacy, incident_id) for legacy, field in _TIMES.items()},
            **{role: _role(item, role) for role in _ROLES},
            "conversation": _conversation(item, tenants),
            "report": _report(item, tenants, incident_id),
            "video_call": _video_call(item, tenants, incident_id),
        }
    except _Unreadable as exc:
        return UnreadableLegacyItem(incident_id=incident_id, field=exc.field, value=exc.value)
    upgraded.update((field, value) for field, value in optional.items() if value is not None)
    return UpgradedItem(item=upgraded)


def _blank(value: object) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _unknown(value: object) -> bool:
    return _blank(value) or (isinstance(value, str) and value.strip().casefold() == "unknown")


def _dropped(incident_id: object, field: str, **context: object) -> None:
    logger.warning("incident_legacy_field_dropped", incident_id=incident_id, field=field, **context)


def _required_text(item: Mapping[str, Any], field: str) -> str:
    value = item.get(field)
    if not isinstance(value, str) or not value.strip():
        raise _Unreadable(field, value)
    return value


def _required_status(item: Mapping[str, Any]) -> str:
    value = item.get("status")
    status = _STATUSES.get(value.strip().casefold()) if isinstance(value, str) else None
    if status is None:
        raise _Unreadable("status", value)
    return status.value


def _required_time(item: Mapping[str, Any]) -> str:
    value = item.get("created_at")
    parsed = _read_time(value)
    if parsed is None:
        raise _Unreadable("created_at", value)
    return format_stored_time(parsed)


def _security_flag(item: Mapping[str, Any]) -> bool:
    # Only stored since 2026-10-07; an item declared before then was not flagged.
    value = item.get("security_incident")
    if value is None:
        return False
    if not isinstance(value, bool):
        raise _Unreadable("security_incident", value)
    return value


def _read_time(value: object) -> datetime | None:
    """Return the instant of epoch seconds or ISO-8601 with an offset; ``None`` otherwise, naive text included."""
    if isinstance(value, bool):
        return None
    if isinstance(value, str):
        try:
            seconds = Decimal(value.strip())
        except InvalidOperation:
            try:
                parsed = datetime.fromisoformat(value.strip())
            except ValueError:
                return None
            return parsed.astimezone(UTC) if parsed.utcoffset() is not None else None
    elif isinstance(value, int | Decimal):
        seconds = Decimal(value)
    else:
        return None
    try:
        return _EPOCH + timedelta(microseconds=int((seconds * 1_000_000).to_integral_value()))
    except ValueError, ArithmeticError:
        return None


def _optional_time(item: Mapping[str, Any], legacy: str, incident_id: object) -> str | None:
    value = item.get(legacy)
    if _unknown(value):
        return None
    parsed = _read_time(value)
    if parsed is None:
        _dropped(incident_id, legacy)
        return None
    return format_stored_time(parsed)


def _product(item: Mapping[str, Any], incident_id: object) -> str | None:
    teams = item.get("teams")
    if teams is None:
        return None
    if not isinstance(teams, list):
        _dropped(incident_id, "teams")
        return None
    first = teams[0] if teams else None
    if _unknown(first):
        return None
    if not isinstance(first, str):
        _dropped(incident_id, "teams")
        return None
    return first.strip()


def _severity(item: Mapping[str, Any], incident_id: object) -> int | None:
    value = item.get("severity")
    if _blank(value) or (isinstance(value, str) and value.strip().casefold() == "none"):
        return None
    match = _SEVERITY.fullmatch("".join(value.split()).casefold()) if isinstance(value, str) else None
    if match is None:
        _dropped(incident_id, "severity", value=value)
        return None
    return int(match.group(1))


def _role(item: Mapping[str, Any], role: str) -> str | None:
    # A non-text role passes through for the end-state parser to drop and log.
    value = item.get(role)
    return None if _blank(value) else value


def _reference(
    system: WorkplaceSystem, tenants: Mapping[WorkplaceSystem, str], field: str, vendor_id: str, url: str | None
) -> dict[str, str]:
    tenant = tenants.get(system)
    if not tenant:
        raise _Unreadable(field, url or vendor_id)
    reference = {"system": system.value, "tenant": tenant, "vendor_id": vendor_id}
    if url is not None:
        reference["url"] = url
    return reference


def _conversation(item: Mapping[str, Any], tenants: Mapping[WorkplaceSystem, str]) -> dict[str, str] | None:
    channel_id = item.get("channel_id")
    if _blank(channel_id):
        return None
    if not isinstance(channel_id, str):
        raise _Unreadable("channel_id", channel_id)
    return _reference(WorkplaceSystem.SLACK, tenants, "channel_id", channel_id.strip(), None)


def _report(item: Mapping[str, Any], tenants: Mapping[WorkplaceSystem, str], incident_id: object) -> dict[str, str] | None:
    url = item.get("report_url")
    if _blank(url):
        return None
    match = _REPORT_DOCUMENT_ID.search(url) if isinstance(url, str) else None
    if match is None:
        _dropped(incident_id, "report_url")
        return None
    return _reference(WorkplaceSystem.GOOGLE, tenants, "report_url", match.group(1), url)


def _video_call(item: Mapping[str, Any], tenants: Mapping[WorkplaceSystem, str], incident_id: object) -> dict[str, str] | None:
    url = item.get("meet_url")
    if _blank(url) or (isinstance(url, str) and url.strip().upper() == "TBC"):
        return None
    code = _meet_code(url) if isinstance(url, str) else None
    if code is None:
        _dropped(incident_id, "meet_url")
        return None
    return _reference(WorkplaceSystem.GOOGLE, tenants, "meet_url", code, url)


def _meet_code(url: str) -> str | None:
    try:
        parts = urlsplit(url.strip())
    except ValueError:
        return None
    code = parts.path.strip("/").rsplit("/", 1)[-1]
    return code if parts.hostname == _MEET_HOST and code else None
