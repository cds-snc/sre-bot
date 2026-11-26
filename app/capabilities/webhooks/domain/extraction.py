"""Field extraction with RFC 9535 singular JSONPath queries, in strict mode.

A singular query has only name and index segments, so each path selects at most one value
and costs time linear in its length (decisions/webhooks.md, the linear-processing rule).
Every value is type-checked and capped; text is neutralised (``values.neutralise_text``) and
links are validated https URLs (``values.normalise_https_url``).
"""

import math
from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
from types import MappingProxyType

from jsonpath import JSONPath, JSONPathEnvironment
from jsonpath.exceptions import JSONPathError

from capabilities.webhooks.domain.events import FieldValue, JsonDocument, Scalar
from capabilities.webhooks.domain.kinds import FieldSpec, FieldType, SenderKind
from capabilities.webhooks.domain.limits import WebhookLimits
from capabilities.webhooks.domain.values import neutralise_text, normalise_https_url, truncate


@dataclass(frozen=True)
class ExtractionMiss:
    """A required field the payload does not provide, or provides with the wrong type."""

    kind_id: str
    field: str
    reason: str


@lru_cache(maxsize=1)
def _environment() -> JSONPathEnvironment:
    return JSONPathEnvironment(strict=True)


def compile_path(text: str) -> JSONPath:
    """Compile an RFC 9535 singular query; raise ValueError for any other query."""
    try:
        path = _environment().compile(text)
    except JSONPathError as error:
        raise ValueError(f"invalid JSONPath {text!r}: {error}") from None
    if not isinstance(path, JSONPath) or not path.singular_query():
        raise ValueError(f"{text!r} is not a singular query: use name and index segments only")
    return path


def extract(kind: SenderKind, document: JsonDocument, limits: WebhookLimits) -> Mapping[str, FieldValue] | ExtractionMiss:
    """Return the kind's fields from ``document``, or the first required field that is missing.

    An optional field that is missing or mistyped is None.
    """
    values: dict[str, FieldValue] = {}
    for spec in kind.fields:
        found = spec.path.match(document)
        value = None if found is None else _convert(spec, found.obj, limits)
        if value is None and spec.required:
            reason = "missing" if found is None else f"not a valid {spec.type}"
            return ExtractionMiss(kind.id, spec.name, reason)
        values[spec.name] = value
    return MappingProxyType(values)


def _convert(spec: FieldSpec, raw: object, limits: WebhookLimits) -> FieldValue:
    match spec.type:
        case FieldType.STRING:
            return _text(raw, limits)
        case FieldType.INTEGER:
            return raw if isinstance(raw, int) and not isinstance(raw, bool) else None
        case FieldType.NUMBER:
            if isinstance(raw, bool) or not isinstance(raw, int | float):
                return None
            return raw if not isinstance(raw, float) or math.isfinite(raw) else None
        case FieldType.BOOLEAN:
            return raw if isinstance(raw, bool) else None
        case FieldType.STRING_LIST:
            if not isinstance(raw, list):
                return None
            items = (_text(element, limits) for element in raw[: limits.max_list_items])
            return tuple(item for item in items if item is not None)
        case FieldType.URL:
            if not isinstance(raw, str):
                return None
            return normalise_https_url(raw, max_chars=limits.max_url_chars, allowed_hosts=spec.allowed_hosts)
    return None


def _text(raw: object, limits: WebhookLimits) -> Scalar | None:
    """A string, or a number shown as text; never a boolean, a list or an object."""
    if isinstance(raw, bool) or not isinstance(raw, str | int | float):
        return None
    if isinstance(raw, float) and not math.isfinite(raw):
        return None
    # Neutralise a bounded prefix only: removed characters can shorten it, so take twice the cap.
    text = str(raw)[: 2 * limits.max_field_value_chars]
    return truncate(neutralise_text(text), limits.max_field_value_chars)
