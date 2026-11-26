"""The sender-kind template engine: python-liquid, plain text, strict names, every limit set.

Templates are organisation content, reviewed like code; payload values reach them only as
data (``fields``), never as template text. The environment has no loader, raises on an
undefined name (``StrictUndefined``), sets every resource limit from the [webhooks] settings,
and keeps only the tags and filters plain-text wording needs: ``include``, ``render``,
``assign``, ``capture`` and the other state tags fail at parse, and filters that decode,
mark up or run a regular expression over a value are absent (decisions/webhooks.md Engines).
Output is plain text, never markup; the platform adapter escapes it.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache

from liquid import Environment, ResourceLimits, StrictUndefined, Template
from liquid.exceptions import LiquidError

from capabilities.webhooks.domain.events import Alert, AlertStatus, FieldValue, Link, Notification, Severity
from capabilities.webhooks.domain.kinds import AlertSpec, LocalizedTemplate, SenderKind
from capabilities.webhooks.domain.limits import WebhookLimits
from capabilities.webhooks.domain.values import truncate
from contracts.languages import MultilingualText

KEPT_TAGS = frozenset({"#", "break", "case", "continue", "doc", "echo", "for", "if", "raw", "unless"})
KEPT_FILTERS = frozenset(
    {
        "abs",
        "append",
        "at_least",
        "at_most",
        "capitalize",
        "ceil",
        "compact",
        "date",
        "default",
        "divided_by",
        "downcase",
        "first",
        "floor",
        "join",
        "last",
        "lstrip",
        "minus",
        "modulo",
        "plus",
        "prepend",
        "remove",
        "remove_first",
        "remove_last",
        "replace",
        "replace_first",
        "replace_last",
        "reverse",
        "round",
        "rstrip",
        "size",
        "slice",
        "sort",
        "sort_natural",
        "strip",
        "strip_newlines",
        "times",
        "truncate",
        "truncatewords",
        "uniq",
        "upcase",
    }
)

# The template data model: the kind's fields, the instance's name and the received time.
FIELDS = "fields"
INSTANCE = "instance"
INSTANCE_NAME = "name"
RECEIVED_AT = "received_at"


class _ContentEnvironment(Environment):
    """A Liquid environment with only the plain-text tags and filters."""

    def setup_tags_and_filters(self, *, extra: bool = False) -> None:
        super().setup_tags_and_filters(extra=extra)
        for name in set(self.tags) - KEPT_TAGS:
            del self.tags[name]
        for name in set(self.filters) - KEPT_FILTERS:
            del self.filters[name]


@lru_cache(maxsize=4)
def template_environment(limits: WebhookLimits) -> Environment:
    """Return the shared environment for ``limits``; built on first use, never at import."""
    return _ContentEnvironment(
        undefined=StrictUndefined,
        autoescape=False,
        resource_limits=ResourceLimits(
            max_loop_iterations=limits.max_loop_iterations,
            max_render_size=limits.max_render_chars,
            max_context_depth=limits.max_context_depth,
        ),
    )


def parse_template(source: str, limits: WebhookLimits, *, field_names: frozenset[str], allow_fields: bool = True) -> Template:
    """Parse ``source`` and check every name it reads; raise ValueError naming the problem.

    A template may read ``fields.<an extracted field>`` (unless ``allow_fields`` is false),
    ``instance.name`` and ``received_at``; nothing else.
    """
    if len(source) > limits.max_template_chars:
        raise ValueError(f"template exceeds {limits.max_template_chars} characters")
    try:
        template = template_environment(limits).parse(source)
    except LiquidError as error:
        raise ValueError(f"invalid template: {error.args[0] if error.args else error}") from None
    unknown = sorted(set(template.filter_names()) - KEPT_FILTERS)
    if unknown:
        raise ValueError(f"template uses filters this engine does not provide: {', '.join(unknown)}")
    for segments in template.global_variable_segments():
        root, rest = segments[0], segments[1:]
        if root == FIELDS and allow_fields and rest and rest[0] in field_names:
            continue
        if root == INSTANCE and tuple(rest) == (INSTANCE_NAME,):
            continue
        if root == RECEIVED_AT and not rest:
            continue
        name = ".".join(str(segment) for segment in segments)
        raise ValueError(f"template reads {name!r}, which is not an extracted field, instance.name or received_at")
    return template


@dataclass(frozen=True)
class RenderFailure(Exception):
    """A template failed at render time; the delivery gets the fallback rendering."""

    kind_id: str
    field: str
    reason: str


def render(
    kind: SenderKind,
    fields: Mapping[str, FieldValue],
    *,
    instance_name: str,
    received_at: datetime,
    languages: Sequence[str],
    limits: WebhookLimits,
) -> Alert | Notification:
    """Render the kind's templates over ``fields`` in ``languages``, in that order.

    Raises:
        RenderFailure: A template raised, a language is missing, or an alert value is not one
            of its closed set.
    """
    if kind.title is None or kind.summary is None:
        raise RenderFailure(kind.id, "title", "the kind has no templates")
    data = {
        FIELDS: {name: list(value) if isinstance(value, tuple) else value for name, value in fields.items()},
        INSTANCE: {INSTANCE_NAME: instance_name},
        RECEIVED_AT: received_at.isoformat(),
    }
    title = _localized(kind, "title", kind.title, data, languages)
    title = MultilingualText(tuple((language, truncate(text, limits.max_title_chars)) for language, text in title.parts))
    summary = _localized(kind, "summary", kind.summary, data, languages)
    details = _single(kind, "details", kind.details, data) if kind.details is not None else None
    links = tuple(
        Link(url=url, label=_localized(kind, f"links.{link.field}", link.label, data, languages))
        for link in kind.links
        if isinstance(url := fields.get(link.field), str)
    )
    attributes = dict(fields)
    if kind.alert is None:
        return Notification(title=title, summary=summary, details=details or None, links=links, attributes=attributes)
    status, severity, dedup_key = _alert_values(kind, kind.alert, data, limits)
    return Alert(
        title=title,
        summary=summary,
        status=status,
        severity=severity,
        dedup_key=dedup_key,
        details=details or None,
        links=links,
        attributes=attributes,
    )


def _localized(
    kind: SenderKind, field: str, template: LocalizedTemplate, data: Mapping[str, object], languages: Sequence[str]
) -> MultilingualText:
    parts: list[tuple[str, str]] = []
    for language in languages:
        source = template.templates.get(language)
        if source is None:
            raise RenderFailure(kind.id, field, f"no {language} template")
        parts.append((language, _single(kind, field, source, data)))
    return MultilingualText(tuple(parts))


def _single(kind: SenderKind, field: str, template: Template, data: Mapping[str, object]) -> str:
    try:
        return template.render(data).strip()
    except LiquidError as error:
        raise RenderFailure(kind.id, field, type(error).__name__) from None


def _alert_values(
    kind: SenderKind, spec: AlertSpec, data: Mapping[str, object], limits: WebhookLimits
) -> tuple[AlertStatus, Severity | None, str | None]:
    status = AlertStatus.FIRING
    if spec.status is not None:
        rendered = _single(kind, "alert.status", spec.status, data)
        if rendered not in AlertStatus:
            raise RenderFailure(kind.id, "alert.status", f"{rendered!r} is not a status")
        status = AlertStatus(rendered)
    severity = None
    if spec.severity is not None and (rendered := _single(kind, "alert.severity", spec.severity, data)):
        if rendered not in Severity:
            raise RenderFailure(kind.id, "alert.severity", f"{rendered!r} is not a severity")
        severity = Severity(rendered)
    dedup_key = None
    if spec.dedup_key is not None:
        dedup_key = truncate(_single(kind, "alert.dedup_key", spec.dedup_key, data), limits.max_field_value_chars) or None
    return status, severity, dedup_key
