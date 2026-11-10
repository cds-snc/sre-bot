"""Convert an ``IncidentBinding`` to and from its stored bindings-table item.

Pure: no store and no I/O. Stored attributes are named after the binding fields;
the sort key ``binding_key`` is ``<kind>#<system>#<tenant>#<vendor_id>`` and
``conversation_id`` (equal to ``vendor_id``) is stored only for chat kinds, which
keeps the ``by_conversation`` index sparse (decisions/incident-management.md,
Bindings and Stored form).

``parse_binding_item`` separates two refusals the lookup treats differently: a
kind this build does not declare (``UnknownBindingKindError``, skipped and
logged, never routed) and an item of a known kind that cannot be read
(``UnreadableBindingItemError``, which fails the lookup closed).
"""

from collections.abc import Mapping
from datetime import datetime
from typing import Any

from contracts.workplace import WorkplaceSystem
from features.incident.core.adapters.incident_items import format_stored_time
from features.incident.core.domain import BindingKind, IncidentBinding

PARTITION_ATTRIBUTE = "incident_id"
SORT_ATTRIBUTE = "binding_key"
CONVERSATION_ATTRIBUTE = "conversation_id"


class UnknownBindingKindError(Exception):
    """A stored binding names a kind this build does not declare."""

    def __init__(self, incident_id: object, kind: object) -> None:
        super().__init__(f"unknown binding kind {kind!r}")
        self.incident_id = incident_id
        self.kind = kind


class UnreadableBindingItemError(Exception):
    """A stored binding of a known kind has a missing or ill-typed value, or a key that differs from its fields."""

    def __init__(self, incident_id: object, field: str) -> None:
        super().__init__(f"unreadable binding field {field}")
        self.incident_id = incident_id
        self.field = field


def binding_key(kind: BindingKind, system: WorkplaceSystem, tenant: str, vendor_id: str) -> str:
    """Return the sort key of a binding: ``<kind>#<system>#<tenant>#<vendor_id>``."""
    return f"{kind.value}#{system.value}#{tenant}#{vendor_id}"


def binding_item(binding: IncidentBinding) -> dict[str, Any]:
    """Return the stored item of ``binding``; ``url`` and ``archived_at`` are absent when unset."""
    item: dict[str, Any] = {
        PARTITION_ATTRIBUTE: binding.incident_id,
        SORT_ATTRIBUTE: binding_key(binding.kind, binding.system, binding.tenant, binding.vendor_id),
        "kind": binding.kind.value,
        "system": binding.system.value,
        "tenant": binding.tenant,
        "vendor_id": binding.vendor_id,
        "primary": binding.primary,
        "bound_by": binding.bound_by,
        "bound_at": format_stored_time(binding.bound_at),
    }
    if binding.kind is BindingKind.CHAT_CONVERSATION:
        item[CONVERSATION_ATTRIBUTE] = binding.vendor_id
    if binding.url is not None:
        item["url"] = binding.url
    if binding.archived_at is not None:
        item["archived_at"] = format_stored_time(binding.archived_at)
    return item


def parse_binding_item(item: Mapping[str, Any]) -> IncidentBinding:
    """Return the binding a stored item holds.

    Raises:
        UnknownBindingKindError: ``kind`` is not a declared ``BindingKind``.
        UnreadableBindingItemError: a value is missing or ill-typed, or the stored key differs from the fields.
    """
    incident_id = item.get(PARTITION_ATTRIBUTE)
    stored_kind = item.get("kind")
    if not isinstance(stored_kind, str):
        raise UnreadableBindingItemError(incident_id, "kind")
    try:
        kind = BindingKind(stored_kind)
    except ValueError:
        raise UnknownBindingKindError(incident_id, stored_kind) from None
    system = _system(item, incident_id)
    tenant, vendor_id = _text(item, "tenant", incident_id), _text(item, "vendor_id", incident_id)
    primary = item.get("primary")
    if not isinstance(primary, bool):
        raise UnreadableBindingItemError(incident_id, "primary")
    url = item.get("url")
    if url is not None and not isinstance(url, str):
        raise UnreadableBindingItemError(incident_id, "url")
    archived = item.get("archived_at")
    try:
        binding = IncidentBinding(
            incident_id=_text(item, PARTITION_ATTRIBUTE, incident_id),
            kind=kind,
            system=system,
            tenant=tenant,
            vendor_id=vendor_id,
            primary=primary,
            bound_by=_text(item, "bound_by", incident_id),
            bound_at=_time(item.get("bound_at"), "bound_at", incident_id),
            url=url,
            archived_at=None if archived is None else _time(archived, "archived_at", incident_id),
        )
    except ValueError:
        raise UnreadableBindingItemError(incident_id, "value") from None
    if item.get(SORT_ATTRIBUTE) != binding_key(kind, system, tenant, vendor_id):
        raise UnreadableBindingItemError(incident_id, SORT_ATTRIBUTE)
    return binding


def _text(item: Mapping[str, Any], field: str, incident_id: object) -> str:
    value = item.get(field)
    if not isinstance(value, str) or not value.strip():
        raise UnreadableBindingItemError(incident_id, field)
    return value


def _system(item: Mapping[str, Any], incident_id: object) -> WorkplaceSystem:
    try:
        return WorkplaceSystem(_text(item, "system", incident_id))
    except ValueError:
        raise UnreadableBindingItemError(incident_id, "system") from None


def _time(value: object, field: str, incident_id: object) -> datetime:
    if not isinstance(value, str):
        raise UnreadableBindingItemError(incident_id, field)
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        raise UnreadableBindingItemError(incident_id, field) from None
    if parsed.utcoffset() is None:
        raise UnreadableBindingItemError(incident_id, field)
    return parsed
