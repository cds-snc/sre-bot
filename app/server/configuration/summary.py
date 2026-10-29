"""The configuration summary: what startup reports about the slices that validated.

Generated from the built slices, never from a hand-kept list (decisions/configuration.md,
Startup reports configuration, never a secret). Each slice is logged as its own event, so
no event outgrows the Fargate runtime's 16 KB line buffer or Logs Insights' 200 extracted
fields, and each section groups the slice's fields as Spring Boot's configprops groups
properties by prefix: shown fields under
"values" (dotted names for nested models and list entries that hold models; a list of
plain values stays one value), withheld fields named under "set" or "unset", and
non-public fields with a tail under "partial". A withheld field's name is a list member,
never a dict key, so the log pipeline's key-name redaction cannot hide its state. A shown
field whose name matches a redaction pattern is masked by that pipeline, which fails safe.

A field is withheld when it was declared env_only (a credential or a non-public value)
or when its value is a SecretStr or SecretBytes. A SecretStr or SecretBytes value is never
read: only whether it is empty. A non-public plain str of twelve or more characters also
carries its last four characters. The config_hash covers the shown values only, so a
withheld value, its tail included, is never hashed.
"""

import hashlib
import json
import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, SecretBytes, SecretStr

from contracts.configuration import ConfigurationSlice, is_env_only, slice_table

# A tail is shown only when it leaves most of the value unseen.
TAIL_LENGTH = 4
TAIL_MIN_LENGTH = 12


@dataclass(frozen=True)
class SummaryEntry:
    """One field of one slice: its value, or for a withheld field its state and maybe a tail."""

    table: str
    name: str
    value: object = None
    state: Literal["set", "unset"] | None = None
    tail: str | None = None


@dataclass(frozen=True)
class ConfigurationSummary:
    """The entries of a set of slices and the SHA-256 of the shown ones."""

    config_hash: str
    entries: tuple[SummaryEntry, ...]

    def sections(self) -> dict[str, dict[str, Any]]:
        """Return one section per slice table, in entry order, as the summary event carries them."""
        sections: dict[str, dict[str, Any]] = {}
        for entry in self.entries:
            section = sections.setdefault(entry.table, {})
            if entry.state is None:
                section.setdefault("values", {})[entry.name] = entry.value
            elif entry.tail is not None:
                section.setdefault("partial", {})[entry.name] = entry.tail
            else:
                section.setdefault(entry.state, []).append(entry.name)
        return sections

    def slice_events(self) -> list[dict[str, Any]]:
        """Return one event body per slice table: the table, the hash of its shown values, then its section."""
        return [
            {"slice": table, "config_hash": _hash([entry for entry in self.entries if entry.table == table]), **section}
            for table, section in self.sections().items()
        ]


def summarize(slices: Iterable[ConfigurationSlice]) -> ConfigurationSummary:
    """Summarise the slices in the order given, hashing the shown values only."""
    entries: list[SummaryEntry] = []
    for built in slices:
        table = slice_table(built)
        for field_name, field in type(built).model_fields.items():
            _walk(table, field_name, getattr(built, field_name), is_env_only(field), entries)
    return ConfigurationSummary(config_hash=_hash(entries), entries=tuple(entries))


def _walk(table: str, name: str, value: object, withheld: bool, entries: list[SummaryEntry]) -> None:
    match value:
        case SecretStr() | SecretBytes():
            entries.append(SummaryEntry(table, name, state="set" if len(value) else "unset"))
        case BaseModel():
            for field_name, field in type(value).model_fields.items():
                _walk(table, f"{name}.{field_name}", getattr(value, field_name), withheld or is_env_only(field), entries)
        case Mapping() if _holds_structure(value.values()):
            for field_name in sorted(value, key=str):
                _walk(table, f"{name}.{field_name}", value[field_name], withheld, entries)
        case list() | tuple() | set() | frozenset() if _holds_structure(value):
            members = sorted(value, key=str) if isinstance(value, set | frozenset) else value
            for position, member in enumerate(members):
                _walk(table, f"{name}.{position}", member, withheld, entries)
        case _ if withheld:
            entries.append(_withheld_entry(table, name, value))
        case _:
            entries.append(SummaryEntry(table, name, _plain(value)))


def _holds_structure(members: Iterable[object]) -> bool:
    """A container is walked only when it holds a model or a secret; otherwise it is one value."""
    return any(isinstance(member, BaseModel | SecretStr | SecretBytes) for member in members)


def _withheld_entry(table: str, name: str, value: object) -> SummaryEntry:
    state: Literal["set", "unset"] = "set" if _is_set(value) else "unset"
    if isinstance(value, str) and len(value) >= TAIL_MIN_LENGTH:
        return SummaryEntry(table, name, state=state, tail=value[-TAIL_LENGTH:])
    return SummaryEntry(table, name, state=state)


def _is_set(value: object) -> bool:
    try:
        return bool(value)
    except Exception:
        return value is not None


def _plain(value: object) -> object:
    """Reduce a shown value to what JSON carries, so building the summary never raises on an odd type."""
    match value:
        case None | bool() | int() | str():
            return value
        case float():
            return value if math.isfinite(value) else str(value)
        case Enum():
            return _plain(value.value)
        case Mapping():
            return {str(member): _plain(value[member]) for member in sorted(value, key=str)}
        case set() | frozenset():
            return [_plain(member) for member in sorted(value, key=str)]
        case list() | tuple():
            return [_plain(member) for member in value]
        case _:
            return str(value)


def _hash(entries: list[SummaryEntry]) -> str:
    shown: list[list[Any]] = [
        [entry.table, entry.name, entry.value]
        for entry in sorted(entries, key=lambda entry: (entry.table, entry.name))
        if entry.state is None
    ]
    canonical = json.dumps(shown, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
