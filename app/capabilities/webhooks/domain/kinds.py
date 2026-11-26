"""Sender kinds and webhook instances, as the frozen values the engines read.

A sender kind is provisioned content (decisions/webhooks.md Content rules): which deliveries
it matches, which fields it extracts and how the event is worded. A webhook instance is one
endpoint, managed content: its protocol, the ordered kinds it tries and where it posts.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType

from jsonpath import JSONPath
from liquid import Template

from capabilities.webhooks.domain.events import EventType, JsonDocument, Scalar


class ConditionOp(StrEnum):
    """The closed set of condition operators; content holds no regular expression."""

    EQUALS = "equals"
    IN = "in"
    EXISTS = "exists"
    STARTS_WITH = "starts_with"
    CONTAINS = "contains"


class GroupMode(StrEnum):
    """How a group combines its conditions."""

    ALL = "all"
    ANY = "any"


@dataclass(frozen=True)
class Condition:
    """One test of the decoded payload: a singular path, an operator and its operand."""

    path: JSONPath
    op: ConditionOp
    value: Scalar | tuple[Scalar, ...]


@dataclass(frozen=True)
class ConditionGroup:
    """Conditions combined with all or any, nested at most to the configured depth."""

    mode: GroupMode
    items: tuple[Condition | ConditionGroup, ...]


class FieldType(StrEnum):
    """The types an extracted field may have."""

    STRING = "string"
    INTEGER = "integer"
    NUMBER = "number"
    BOOLEAN = "boolean"
    STRING_LIST = "string_list"
    URL = "url"


@dataclass(frozen=True)
class FieldSpec:
    """One field the kind extracts: its name, singular path, type and whether it must be present."""

    name: str
    path: JSONPath
    type: FieldType
    required: bool = False
    allowed_hosts: frozenset[str] = frozenset()


@dataclass(frozen=True)
class LocalizedTemplate:
    """One template per supported language for the bot's wording."""

    templates: Mapping[str, Template]

    def __post_init__(self) -> None:
        object.__setattr__(self, "templates", MappingProxyType(dict(self.templates)))


@dataclass(frozen=True)
class LinkSpec:
    """A link built from a url field, under a fixed per-language label."""

    field: str
    label: LocalizedTemplate


@dataclass(frozen=True)
class AlertSpec:
    """Templates for an alert's status, severity and dedup key."""

    status: Template | None = None
    severity: Template | None = None
    dedup_key: Template | None = None


@dataclass(frozen=True)
class SenderKind:
    """Which event a delivery is and how to word it.

    A kind with ``suppress`` set matches and posts nothing; ``handler`` names a code
    handler a plugin registers; ``mentions`` turns email addresses in the text into
    mentions on platforms that have them.
    """

    id: str
    event_type: EventType
    match: ConditionGroup
    fields: tuple[FieldSpec, ...] = ()
    title: LocalizedTemplate | None = None
    summary: LocalizedTemplate | None = None
    details: Template | None = None
    links: tuple[LinkSpec, ...] = ()
    alert: AlertSpec | None = None
    handler: str | None = None
    suppress: bool = False
    mentions: bool = False


class AuthTier(StrEnum):
    """How an instance's deliveries are authenticated during the caller migration."""

    LEGACY = "legacy"
    MONITOR = "monitor"
    ENFORCE = "enforce"


@dataclass(frozen=True)
class Owner:
    """The team that owns an instance, and how to reach it."""

    team: str
    contact: str


@dataclass(frozen=True)
class Destination:
    """Where an instance posts, and whether triage consumers apply to its alerts."""

    channel: str
    triage: bool = False


@dataclass(frozen=True)
class WebhookInstance:
    """One endpoint: its protocol, the sender kinds it tries in order, and its destinations.

    ``instance_ref`` is the internal, non-secret id that logs, metrics and buttons carry;
    the URL token never appears here.
    """

    instance_ref: str
    name: str
    owner: Owner
    auth_tier: AuthTier
    protocol: str
    sender_kinds: tuple[str, ...]
    destinations: tuple[Destination, ...] = field(default=())


def resolve_kinds(
    instance: WebhookInstance, kinds: Mapping[str, SenderKind], *, max_kinds: int
) -> tuple[tuple[SenderKind, ...], tuple[str, ...]]:
    """Return the instance's kinds in its declared order, and the ids it names that are unknown.

    A stored instance is untrusted content: an unknown id, a repeated id or ids past
    ``max_kinds`` are reported, never raised (decisions/managed-content.md).
    """
    resolved: list[SenderKind] = []
    skipped: list[str] = []
    seen: set[str] = set()
    for kind_id in instance.sender_kinds:
        kind = kinds.get(kind_id)
        if kind is None or kind_id in seen or len(resolved) >= max_kinds:
            skipped.append(kind_id)
            continue
        seen.add(kind_id)
        resolved.append(kind)
    return tuple(resolved), tuple(skipped)


def first_match(kinds: Sequence[SenderKind], document: JsonDocument) -> SenderKind | None:
    """Return the first kind, in the given order, whose conditions hold for ``document``."""
    for kind in kinds:
        if _holds(kind.match, document):
            return kind
    return None


def _holds(item: Condition | ConditionGroup, document: JsonDocument) -> bool:
    if isinstance(item, ConditionGroup):
        results = (_holds(child, document) for child in item.items)
        return all(results) if item.mode is GroupMode.ALL else any(results)
    found = item.path.match(document)
    if item.op is ConditionOp.EXISTS:
        return (found is not None) is item.value
    if found is None:
        return False
    actual = found.obj
    match item.op:
        case ConditionOp.EQUALS:
            return _same(actual, item.value)
        case ConditionOp.IN:
            return isinstance(item.value, tuple) and any(_same(actual, option) for option in item.value)
        case ConditionOp.STARTS_WITH:
            return isinstance(actual, str) and isinstance(item.value, str) and actual.startswith(item.value)
        case ConditionOp.CONTAINS:
            if isinstance(actual, str):
                return isinstance(item.value, str) and item.value in actual
            return isinstance(actual, list) and any(_same(element, item.value) for element in actual)
    return False


def _same(actual: object, expected: object) -> bool:
    """Compare as JSON does: a boolean never equals a number."""
    if isinstance(actual, bool) or isinstance(expected, bool):
        return type(actual) is type(expected) and actual == expected
    return actual == expected
