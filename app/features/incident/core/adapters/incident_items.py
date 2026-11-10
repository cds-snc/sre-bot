"""Write an ``Incident`` as an end-state incident item, read one back, and format its stored times.

Pure: no store and no I/O. Stored attributes are named after the record fields
(decisions/incident-management.md, The incident record); each resource
reference is one map ``{system, tenant, vendor_id, url}`` and the source alert
a message map ``{system, tenant, conversation_id, message_id, url}``, the url
omitted when unset. Items without ``record_version``
are not end-state items and never reach this parser. The record-version
constants and the open-index bucket value are defined here, so the store and
the per-item upgrade plan share them without importing each other.

A required value that cannot be read (id, title, status, declared_by,
declared_at, security_incident) makes the item a classified
``INCIDENT_RECORD_UNREADABLE`` result. An optional value that cannot be read is
dropped (not recorded, not assigned, not rated or no reference) and logged with
the incident id and field; the incident stays readable.
"""

from collections.abc import Mapping
from dataclasses import fields
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import structlog

from contracts.operations.codes import ErrorCode
from contracts.operations.result import OperationResult
from contracts.operations.status import OperationStatus
from contracts.workplace import WorkplaceSystem
from features.incident.common.vocabulary import IncidentStatus, Severity
from features.incident.core.domain import (
    ConversationReference,
    ExternalCaseReference,
    Incident,
    MessageReference,
    PostmortemMeetingReference,
    ReportReference,
    ResourceReference,
    VideoCallReference,
)

logger = structlog.get_logger()

# The end-state shape without a binding. No current writer stamps it; the legacy upgrade raises such items to RECORD_VERSION.
END_STATE_VERSION = 1
# The end-state shape with its binding: what every writer and the legacy upgrade stamp on an item.
RECORD_VERSION = 2
# open_bucket value while an incident is open; the writers remove it on Closed.
OPEN_BUCKET = "OPEN"

_UNREADABLE_MESSAGE = "A stored incident record could not be read."


class _RequiredValueError(Exception):
    """A required attribute is missing or cannot be read."""

    def __init__(self, field: str, value: object) -> None:
        super().__init__(field)
        self.field = field
        self.value = value


def parse_incident_item(item: Mapping[str, Any]) -> OperationResult[Incident]:
    """Return the incident an end-state item holds, or ``INCIDENT_RECORD_UNREADABLE``."""
    incident_id = item.get("id")

    def text(field: str) -> str | None:
        return _optional_text(item, field, incident_id)

    def time(field: str) -> datetime | None:
        return _optional_time(item, field, incident_id)

    def reference[R: ResourceReference](field: str, kind: type[R]) -> R | None:
        return read_reference(item, field, kind, incident_id)

    try:
        incident = Incident(
            id=_required_text(item, "id"),
            title=_required_text(item, "title"),
            status=_required_status(item),
            declared_by=_required_text(item, "declared_by"),
            declared_at=_required_time(item),
            security_incident=_required_bool(item, "security_incident"),
            product=text("product"),
            severity=_optional_severity(item, incident_id),
            detected_at=time("detected_at"),
            impact_started_at=time("impact_started_at"),
            impact_ended_at=time("impact_ended_at"),
            incident_commander=text("incident_commander"),
            operations_lead=text("operations_lead"),
            communications_lead=text("communications_lead"),
            policy_lead=text("policy_lead"),
            postmortem_owner=text("postmortem_owner"),
            conversation=reference("conversation", ConversationReference),
            report=reference("report", ReportReference),
            video_call=reference("video_call", VideoCallReference),
            postmortem_meeting=reference("postmortem_meeting", PostmortemMeetingReference),
            external_case=reference("external_case", ExternalCaseReference),
            source_alert=read_message_reference(item, "source_alert", incident_id),
        )
    except _RequiredValueError as exc:
        log_fields: dict[str, object] = {"incident_id": incident_id, "field": exc.field}
        if exc.field == "status":
            log_fields["value"] = exc.value
        logger.warning("incident_record_unreadable", **log_fields)
        return incident_record_unreadable()
    return OperationResult.success(data=incident)


def read_reference[R: ResourceReference](item: Mapping[str, Any], field: str, kind: type[R], incident_id: object) -> R | None:
    """Return the reference map stored under ``field`` as ``kind``, or ``None`` when absent or unreadable."""
    stored = item.get(field)
    if stored is None:
        return None
    try:
        if not isinstance(stored, Mapping):
            raise TypeError("not a map")
        url = stored.get("url")
        if url is not None and not isinstance(url, str):
            raise TypeError("url is not text")
        return kind(
            system=WorkplaceSystem(_text(stored.get("system"))),
            tenant=_text(stored.get("tenant")),
            vendor_id=_text(stored.get("vendor_id")),
            url=url,
        )
    except TypeError, ValueError:
        # Never log the map: its url may carry a vendor link.
        logger.warning("incident_field_unreadable", incident_id=incident_id, field=field)
        return None


def read_message_reference(item: Mapping[str, Any], field: str, incident_id: object) -> MessageReference | None:
    """Return the message map stored under ``field``, or ``None`` when absent or unreadable."""
    stored = item.get(field)
    if stored is None:
        return None
    try:
        if not isinstance(stored, Mapping):
            raise TypeError("not a map")
        url = stored.get("url")
        if url is not None and not isinstance(url, str):
            raise TypeError("url is not text")
        return MessageReference(
            system=WorkplaceSystem(_text(stored.get("system"))),
            tenant=_text(stored.get("tenant")),
            conversation_id=_text(stored.get("conversation_id")),
            message_id=_text(stored.get("message_id")),
            url=url,
        )
    except TypeError, ValueError:
        # Never log the map: its url may carry a vendor link.
        logger.warning("incident_field_unreadable", incident_id=incident_id, field=field)
        return None


def incident_item(incident: Incident) -> dict[str, Any]:
    """Return the end-state item for ``incident``, as ``create`` puts it.

    Writes only the record's own names, an optional field only when set, plus
    ``channel_id`` (the by_channel lookup copy), ``record_version`` and, while
    the incident is open, ``open_bucket`` with ``opened_at`` (the declared time).

    Raises:
        ValueError: the incident has no conversation, so no lookup copy can be written.
    """
    if incident.conversation is None:
        raise ValueError("an incident record needs its conversation")
    item: dict[str, Any] = {"record_version": RECORD_VERSION, "channel_id": incident.conversation.vendor_id}
    for field in fields(incident):
        value = getattr(incident, field.name)
        if value is not None:
            item[field.name] = _stored_value(value)
    if incident.status.is_open:
        item["open_bucket"] = OPEN_BUCKET
        item["opened_at"] = format_stored_time(incident.declared_at)
    return item


def reference_item(reference: ResourceReference) -> dict[str, str]:
    """Return the stored map of a resource reference; the url only when set."""
    stored = {"system": reference.system.value, "tenant": reference.tenant, "vendor_id": reference.vendor_id}
    if reference.url is not None:
        stored["url"] = reference.url
    return stored


def message_reference_item(reference: MessageReference) -> dict[str, str]:
    """Return the stored map of a message reference; the url only when set."""
    stored = {
        "system": reference.system.value,
        "tenant": reference.tenant,
        "conversation_id": reference.conversation_id,
        "message_id": reference.message_id,
    }
    if reference.url is not None:
        stored["url"] = reference.url
    return stored


def _stored_value(value: object) -> object:
    """Return the stored form of one record field value."""
    match value:
        case ResourceReference():
            return reference_item(value)
        case MessageReference():
            return message_reference_item(value)
        case datetime():
            return format_stored_time(value)
        case Severity():
            return int(value)
        case IncidentStatus():
            return value.value
        case _:
            return value


def format_stored_time(value: datetime) -> str:
    """Return the stored form of a time: fixed-width ISO-8601 in UTC with its +00:00 offset.

    Microseconds are always written, so stored times sort as text in time order.
    A naive time raises ``ValueError``: storing it would assume the host timezone.
    """
    if value.utcoffset() is None:
        raise ValueError("a stored time must be timezone-aware")
    return value.astimezone(UTC).isoformat(timespec="microseconds")


def incident_record_unreadable[T]() -> OperationResult[T]:
    """Return the classified result for a stored incident item that cannot be read."""
    return OperationResult.error(
        OperationStatus.PERMANENT_ERROR, message=_UNREADABLE_MESSAGE, error_code=ErrorCode.INCIDENT_RECORD_UNREADABLE
    )


def _text(value: object) -> str:
    if not isinstance(value, str):
        raise TypeError("not text")
    return value


def _required_text(item: Mapping[str, Any], field: str) -> str:
    value = item.get(field)
    if not isinstance(value, str) or not value.strip():
        raise _RequiredValueError(field, value)
    return value


def _required_status(item: Mapping[str, Any]) -> IncidentStatus:
    value = item.get("status")
    if not isinstance(value, str) or value not in IncidentStatus:
        raise _RequiredValueError("status", value)
    return IncidentStatus(value)


def _required_time(item: Mapping[str, Any]) -> datetime:
    value = _parse_time(item.get("declared_at"))
    if value is None:
        raise _RequiredValueError("declared_at", item.get("declared_at"))
    return value


def _required_bool(item: Mapping[str, Any], field: str) -> bool:
    value = item.get(field)
    if not isinstance(value, bool):
        raise _RequiredValueError(field, value)
    return value


def _optional_text(item: Mapping[str, Any], field: str, incident_id: object) -> str | None:
    value = item.get(field)
    if value is None:
        return None
    if not isinstance(value, str):
        _log_unreadable(incident_id, field, value)
        return None
    return value if value.strip() else None


def _optional_severity(item: Mapping[str, Any], incident_id: object) -> Severity | None:
    value = item.get("severity")
    if value is None:
        return None
    if isinstance(value, (int, Decimal)) and not isinstance(value, bool) and value == int(value) and 0 <= value <= 4:
        return Severity(int(value))
    _log_unreadable(incident_id, "severity", value)
    return None


def _optional_time(item: Mapping[str, Any], field: str, incident_id: object) -> datetime | None:
    value = item.get(field)
    if value is None:
        return None
    parsed = _parse_time(value)
    if parsed is None:
        _log_unreadable(incident_id, field, value)
    return parsed


def _parse_time(value: object) -> datetime | None:
    """Return an aware time from an ISO-8601 string; ``None`` for anything else, naive times included."""
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.utcoffset() is not None else None


def _log_unreadable(incident_id: object, field: str, value: object) -> None:
    logger.warning("incident_field_unreadable", incident_id=incident_id, field=field, value=value)
