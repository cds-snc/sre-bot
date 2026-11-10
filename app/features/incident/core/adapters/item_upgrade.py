"""The per-item upgrade plan from a stored incident item to the current record version.

Pure: no store and no I/O. ``plan_item_upgrade`` is the one plan shared by the
legacy upgrade job and by any store-side upgrade-on-write: it says which
guarded changes raise an item to ``RECORD_VERSION``, which guard holds them
back from a concurrent writer, and which binding the item gets. The verified
tenant check stays the batch job's; this plan only uses the configured tenants.

An item without ``record_version`` is a legacy item and goes through the shared
legacy bridge. An item at ``END_STATE_VERSION`` already has the end-state shape
and only lacks its binding. An item at ``RECORD_VERSION`` or above is left
alone (``None``). The binding is the primary chat binding of the item's
conversation, bound by the item's declarer at its declared time, so a rerun
builds the identical item (decisions/incident-management.md, Migration).
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from contracts.records import ExpectedValue, RecordChange, SetAttribute
from contracts.workplace import WorkplaceSystem
from features.incident.common.vocabulary import IncidentStatus
from features.incident.core.adapters.incident_items import (
    END_STATE_VERSION,
    OPEN_BUCKET,
    RECORD_VERSION,
    read_reference,
)
from features.incident.core.adapters.legacy_items import UnreadableLegacyItem, upgrade_legacy_item
from features.incident.core.domain import BindingKind, ConversationReference, IncidentBinding

# Every scalar the bridge reads, guarded at its read value so a write never lands on a changed item.
_READ_ATTRIBUTES = (
    "status",
    "name",
    "user_id",
    "created_at",
    "security_incident",
    "channel_id",
    "report_url",
    "meet_url",
    "severity",
    "detection_time",
    "start_impact_time",
    "end_impact_time",
    "incident_commander",
    "operations_lead",
)

# What the plan reads of an item already in the end-state shape, guarded at its read value.
_END_STATE_GUARDED = ("channel_id", "status", "declared_at")


@dataclass(frozen=True)
class ItemUpgrade:
    """The guarded write that raises one item to ``RECORD_VERSION``, and its binding.

    Attributes:
        incident_id: The item's id.
        from_version: ``None`` for a legacy item, ``END_STATE_VERSION`` for an end-state item without a binding.
        binding: The primary conversation binding to put first; ``None`` only for a Closed item without a conversation.
        changes: The attributes to set, the version marker last.
        expected: The read value of every guarded attribute (``None`` for an absent one).
        dropped: The legacy attributes whose optional value could not be matched.
    """

    incident_id: str
    from_version: int | None
    binding: IncidentBinding | None
    changes: tuple[RecordChange, ...]
    expected: dict[str, ExpectedValue]
    dropped: tuple[str, ...] = ()


@dataclass(frozen=True)
class UnboundOpenItem:
    """An open item without a conversation: no binding can be built, so it is fixed by hand.

    Attributes:
        incident_id: The stored ``id`` of the item, whatever its type.
    """

    incident_id: object


class _UnguardableError(Exception):
    def __init__(self, field: str) -> None:
        super().__init__(field)
        self.field = field


def plan_item_upgrade(
    item: Mapping[str, Any], tenants: Mapping[WorkplaceSystem, str]
) -> ItemUpgrade | UnreadableLegacyItem | UnboundOpenItem | None:
    """Return the plan that raises ``item`` to ``RECORD_VERSION``, why it cannot be planned, or ``None`` when nothing is to do.

    ``None`` means the item is at ``RECORD_VERSION`` or above (a higher version is left alone).
    ``tenants`` is the configured tenant per workplace system, as the legacy bridge gets it.
    An unreadable result never carries a stored value except an unmatched status.
    """
    stored_version = item.get("record_version")
    if stored_version is None:
        return _plan_legacy(item, tenants)
    try:
        if isinstance(stored_version, bool):
            raise _UnguardableError("record_version")
        version = _guard_value("record_version", stored_version)
    except _UnguardableError:
        return UnreadableLegacyItem(incident_id=item.get("id"), field="record_version", value=None)
    if not isinstance(version, int) or version < END_STATE_VERSION:
        return UnreadableLegacyItem(incident_id=item.get("id"), field="record_version", value=None)
    if version >= RECORD_VERSION:
        return None
    return _plan_raise(item, version)


def _plan_legacy(
    item: Mapping[str, Any], tenants: Mapping[WorkplaceSystem, str]
) -> ItemUpgrade | UnreadableLegacyItem | UnboundOpenItem:
    upgraded = upgrade_legacy_item(item, tenants)
    if isinstance(upgraded, UnreadableLegacyItem):
        return upgraded
    incident_id = upgraded.item["id"]
    values = {attribute: value for attribute, value in upgraded.item.items() if attribute != "id"}
    closed = values["status"] == IncidentStatus.CLOSED.value
    if not closed:
        values["open_bucket"] = OPEN_BUCKET
        values["opened_at"] = values["declared_at"]
    values["record_version"] = RECORD_VERSION
    try:
        expected = {attribute: _guard_value(attribute, item.get(attribute)) for attribute in (*_READ_ATTRIBUTES, *values)}
    except _UnguardableError as exc:
        return UnreadableLegacyItem(incident_id=incident_id, field=exc.field, value=None)
    binding = _binding_for(upgraded.item)
    if isinstance(binding, UnreadableLegacyItem):
        return binding
    if binding is None and not closed:
        return UnboundOpenItem(incident_id)
    changes = tuple(SetAttribute(attribute, value) for attribute, value in values.items())
    return ItemUpgrade(incident_id, None, binding, changes, expected, upgraded.dropped)


def _plan_raise(item: Mapping[str, Any], version: int) -> ItemUpgrade | UnreadableLegacyItem | UnboundOpenItem:
    incident_id = item.get("id")
    status = item.get("status")
    if not isinstance(incident_id, str) or not incident_id.strip():
        return UnreadableLegacyItem(incident_id=incident_id, field="id", value=None)
    if status not in {member.value for member in IncidentStatus}:
        return UnreadableLegacyItem(incident_id=incident_id, field="status", value=status)
    binding = _binding_for(item)
    if isinstance(binding, UnreadableLegacyItem):
        return binding
    if binding is None and status != IncidentStatus.CLOSED.value:
        return UnboundOpenItem(incident_id)
    try:
        expected = {attribute: _guard_value(attribute, item.get(attribute)) for attribute in _END_STATE_GUARDED}
    except _UnguardableError as exc:
        return UnreadableLegacyItem(incident_id=incident_id, field=exc.field, value=None)
    expected["record_version"] = version
    return ItemUpgrade(incident_id, version, binding, (SetAttribute("record_version", RECORD_VERSION),), expected)


def _binding_for(item: Mapping[str, Any]) -> IncidentBinding | UnreadableLegacyItem | None:
    """Return the primary chat binding of an end-state item's conversation; ``None`` when it has no conversation."""
    incident_id = item.get("id")
    if item.get("conversation") is None:
        return None
    reference = read_reference(item, "conversation", ConversationReference, incident_id)
    if reference is None:
        return UnreadableLegacyItem(incident_id=incident_id, field="conversation", value=None)
    declared_by = item.get("declared_by")
    declared_at = item.get("declared_at")
    if not isinstance(declared_by, str):
        return UnreadableLegacyItem(incident_id=incident_id, field="declared_by", value=None)
    try:
        bound_at = datetime.fromisoformat(declared_at) if isinstance(declared_at, str) else None
    except ValueError:
        bound_at = None
    if bound_at is None:
        return UnreadableLegacyItem(incident_id=incident_id, field="declared_at", value=None)
    try:
        return IncidentBinding(
            incident_id=str(incident_id),
            kind=BindingKind.CHAT_CONVERSATION,
            system=reference.system,
            tenant=reference.tenant,
            vendor_id=reference.vendor_id,
            primary=True,
            bound_by=declared_by,
            bound_at=bound_at,
            url=reference.url,
        )
    except ValueError, TypeError:
        return UnreadableLegacyItem(incident_id=incident_id, field="conversation", value=None)


def _guard_value(attribute: str, value: object) -> ExpectedValue:
    """Return ``value`` as an equality guard: text, bool, int and None as read, an integral Decimal as int."""
    if value is None or isinstance(value, str | bool | int):
        return value
    if isinstance(value, Decimal) and value.is_finite() and value == value.to_integral_value():
        return int(value)
    raise _UnguardableError(attribute)
