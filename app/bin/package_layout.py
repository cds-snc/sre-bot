"""Load the package-layout manifest, the machine copy of feature-packages.md's layout table.

bin/package_layout.toml declares each package kind (feature, subdomain,
capability, core, common, umbrella) with its required, optional and forbidden
entries, plus the capability README rules and the reserved subdomain names,
and for the generator (bin/new_package.py) each kind's templates and the
option flags that add an optional entry. This module reads it with tomllib into frozen dataclasses and refuses a
malformed manifest, naming the key at fault, so a bad edit fails every tool
that reads it instead of silently widening a check.

Usage:
    from bin.package_layout import layout
    layout().kinds["capability"].allowed_files
"""

import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

LAYOUT_PATH = Path(__file__).resolve().parent / "package_layout.toml"

REQUIRED_TOP_LEVEL_KEYS = frozenset({"roots", "reserved_subdomains", "grows_into_package", "capability_readme", "kinds"})
TOP_LEVEL_KEYS = REQUIRED_TOP_LEVEL_KEYS | {"options"}
ROOT_KEYS = frozenset({"features", "capabilities"})
README_KEYS = frozenset({"classification_heading", "consumers_heading", "classifications"})
KIND_KEYS = frozenset({"extends", "required", "optional", "exclude", "forbidden", "open", "templates"})
OPTION_KEYS = frozenset({"entry", "needs"})
DIRECTORY_MARK = "/"


class LayoutError(Exception):
    """The manifest is malformed; the message names the key at fault."""


@dataclass(frozen=True)
class Kind:
    """One package kind: the entries it must hold, may hold, or must not hold."""

    name: str
    required: frozenset[str]
    optional: frozenset[str]
    forbidden: frozenset[str]
    open: bool
    grows_into_package: frozenset[str]
    templates: Mapping[str, str]
    """Entry -> template file in bin/package_templates/ ('' writes an empty file); a directory's renders its __init__.py."""

    @property
    def declared(self) -> frozenset[str]:
        """Required and optional entries as written in the manifest (a directory keeps its '/')."""
        return self.required | self.optional

    @property
    def allowed_files(self) -> frozenset[str]:
        return frozenset(name for name in self.declared if not name.endswith(DIRECTORY_MARK))

    @property
    def allowed_dirs(self) -> frozenset[str]:
        """Directories, plus a package for each allowed module that may grow into one."""
        directories = {name.removesuffix(DIRECTORY_MARK) for name in self.declared if name.endswith(DIRECTORY_MARK)}
        grown = {name.removesuffix(".py") for name in self.allowed_files & self.grows_into_package}
        return frozenset(directories | grown)

    @property
    def forbidden_names(self) -> frozenset[str]:
        """Forbidden entries by bare name, file or directory alike."""
        return frozenset(name.removesuffix(DIRECTORY_MARK) for name in self.forbidden)


@dataclass(frozen=True)
class Option:
    """A generator flag (--<name>) that adds one optional entry, when the entries it needs are there."""

    name: str
    entry: str
    needs: frozenset[str]


@dataclass(frozen=True)
class Roots:
    """The top-level directories, under app/, that hold packages."""

    features: str
    capabilities: str


@dataclass(frozen=True)
class Layout:
    """The whole manifest."""

    roots: Roots
    kinds: Mapping[str, Kind]
    reserved_subdomains: frozenset[str]
    classification_heading: str
    consumers_heading: str
    classifications: tuple[str, ...]
    options: Mapping[str, Option]

    def options_of(self, kind: str) -> tuple[Option, ...]:
        """The options a kind takes, in manifest order: those whose entry the kind lists as optional."""
        optional = self.kinds[kind].optional
        return tuple(option for option in self.options.values() if option.entry in optional)

    @property
    def declared_names(self) -> frozenset[str]:
        """Every entry any kind declares, as written: the names of the layout table."""
        return frozenset().union(*(kind.declared for kind in self.kinds.values()))


def _check_keys(table: Mapping[str, Any], allowed: frozenset[str], where: str) -> None:
    unknown = sorted(set(table) - allowed)
    if unknown:
        raise LayoutError(f"{where}: unknown key(s) {', '.join(unknown)}; allowed: {', '.join(sorted(allowed))}")


def _strings(value: Any, where: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        raise LayoutError(f"{where} must be a list of non-empty strings")
    return value


def _names(value: Any, where: str) -> frozenset[str]:
    names = _strings(value, where)
    for name in names:
        if DIRECTORY_MARK in name.removesuffix(DIRECTORY_MARK):
            raise LayoutError(f"{where}: '{name}' is a path; an entry is one file or one directory ending in '/'")
    return frozenset(names)


def _kind(name: str, kinds: Mapping[str, Any], grows: frozenset[str], seen: tuple[str, ...] = ()) -> Kind:
    where = f"kinds.{name}"
    if name in seen:
        raise LayoutError(f"{where}: extends forms a cycle ({' -> '.join((*seen, name))})")
    table = kinds[name]
    if not isinstance(table, dict):
        raise LayoutError(f"{where} must be a table")
    _check_keys(table, KIND_KEYS, where)

    required: frozenset[str] = frozenset()
    optional: frozenset[str] = frozenset()
    templates: dict[str, str] = {}
    if "extends" in table:
        base_name = table["extends"]
        if base_name not in kinds:
            raise LayoutError(f"{where}.extends: no kind '{base_name}'")
        base = _kind(base_name, kinds, grows, (*seen, name))
        required, optional, templates = base.required, base.optional, dict(base.templates)
    # Exclude drops inherited entries before the kind's own are added, so an entry can move from required to optional.
    exclude = _names(table.get("exclude", []), f"{where}.exclude")
    absent = sorted(exclude - required - optional)
    if absent:
        raise LayoutError(f"{where}.exclude: {', '.join(absent)} is not an entry of this kind")
    required, optional = required - exclude, optional - exclude
    required |= _names(table.get("required", []), f"{where}.required")
    optional |= _names(table.get("optional", []), f"{where}.optional")

    both = sorted(required & optional)
    if both:
        raise LayoutError(f"{where}: {', '.join(both)} is both required and optional")
    is_open = table.get("open", False)
    if not isinstance(is_open, bool):
        raise LayoutError(f"{where}.open must be true or false")
    forbidden = _names(table.get("forbidden", []), f"{where}.forbidden")
    templates = {entry: template for entry, template in templates.items() if entry in required | optional}
    templates |= _templates(table.get("templates", {}), required | optional, f"{where}.templates")
    return Kind(name, required, optional, forbidden, is_open, grows, templates)


def _templates(value: Any, declared: frozenset[str], where: str) -> dict[str, str]:
    if not isinstance(value, dict) or not all(isinstance(template, str) for template in value.values()):
        raise LayoutError(f"{where} must be a table of entry = template file name")
    undeclared = sorted(set(value) - declared)
    if undeclared:
        raise LayoutError(f"{where}: {', '.join(undeclared)} is not an entry of this kind")
    return dict(value)


def _options(value: Any, declared: frozenset[str]) -> dict[str, Option]:
    if not isinstance(value, dict):
        raise LayoutError("options must be a table of option tables")
    options: dict[str, Option] = {}
    for name, table in value.items():
        where = f"options.{name}"
        if not isinstance(table, dict):
            raise LayoutError(f"{where} must be a table")
        _check_keys(table, OPTION_KEYS, where)
        entry = table.get("entry")
        if entry not in declared:
            raise LayoutError(f"{where}.entry: '{entry}' is not an entry any kind declares")
        needs = _names(table.get("needs", []), f"{where}.needs")
        unknown = sorted(needs - declared)
        if unknown:
            raise LayoutError(f"{where}.needs: {', '.join(unknown)} is not an entry any kind declares")
        options[name] = Option(name, entry, needs)
    return options


def load_layout(path: Path) -> Layout:
    """Read and validate the manifest at ``path``; raise ``LayoutError`` naming the key at fault."""
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as error:
        raise LayoutError(f"{path.name}: {error}") from error
    _check_keys(data, TOP_LEVEL_KEYS, path.name)
    for key in sorted(REQUIRED_TOP_LEVEL_KEYS):
        if key not in data:
            raise LayoutError(f"{path.name}: missing {key}")

    roots = data["roots"]
    _check_keys(roots, ROOT_KEYS, "roots")
    if set(roots) != ROOT_KEYS or not all(isinstance(value, str) and value for value in roots.values()):
        raise LayoutError(f"roots must name {' and '.join(sorted(ROOT_KEYS))}")

    readme = data["capability_readme"]
    _check_keys(readme, README_KEYS, "capability_readme")
    classifications = _strings(readme.get("classifications"), "capability_readme.classifications")
    if not classifications:
        raise LayoutError("capability_readme.classifications must name at least one classification")
    headings = {key: readme.get(key) for key in ("classification_heading", "consumers_heading")}
    for key, heading in headings.items():
        if not isinstance(heading, str) or not heading.startswith("## "):
            raise LayoutError(f"capability_readme.{key} must be a '## ' heading")

    grows = _names(data["grows_into_package"], "grows_into_package")
    kinds = data["kinds"]
    if not isinstance(kinds, dict) or not kinds:
        raise LayoutError("kinds must declare at least one kind")
    parsed = {name: _kind(name, kinds, grows) for name in kinds}
    declared = frozenset().union(*(kind.declared for kind in parsed.values()))
    return Layout(
        roots=Roots(features=roots["features"], capabilities=roots["capabilities"]),
        kinds=parsed,
        reserved_subdomains=_names(data["reserved_subdomains"], "reserved_subdomains"),
        classification_heading=str(headings["classification_heading"]),
        consumers_heading=str(headings["consumers_heading"]),
        classifications=tuple(classifications),
        options=_options(data.get("options", {}), declared),
    )


@cache
def layout() -> Layout:
    """The repository's manifest, loaded once."""
    return load_layout(LAYOUT_PATH)
