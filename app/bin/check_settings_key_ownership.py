#!/usr/bin/env python3
"""Guardrail: every settings key has exactly one owning slice.

decisions/configuration.md "Checks" asks for these, all enforced here:
  - key-ownership:  no environment variable is read by two settings classes,
                    and no configuration-file table is named by two slices;
  - unowned-table:  every table in ``config/*.toml`` is named by a slice's
                    ``toml_table_header``;
  - missing-table:  every table a slice names is in ``config/base.toml``;
  - env-naming:     a ``ConfigurationSlice`` reads only ``<TABLE>__`` names or a
                    platform-provided name (``ENVIRONMENT``, ``GIT_SHA``,
                    ``FORWARDED_ALLOW_IPS``);
  - sdk-namespace:  no ``ConfigurationSlice`` reads an ``AWS_*``, ``UVICORN_*`` or
                    ``OTEL_*`` name, which the SDK or runtime reads itself;
  - vendor-enabled: no ``<VENDOR>_ENABLED`` key in ``integrations/`` (a vendor
                    client is enabled by its tenant entry);
  - environ-read:   no ``os.environ`` / ``os.getenv`` read outside a settings
                    class (``bin/`` developer scripts and tests excepted).

decisions/plugins.md and reliability.md "Checks" add, for ``server/lifespan.py``
and the ``server/plugins/``, ``packages/``, ``features/`` and ``jobs/`` trees:
  - plugin-switch:    no flat settings class (not a ``ConfigurationSlice``)
                      declares an ``enabled`` field, or a ``<NAME>_ENABLED``
                      field without an ``env_prefix``: a plugin or the scheduler
                      runs on a configuration-file key;
  - environment-gate: no comparison against the environment name
                      (``environment``, ``ENVIRONMENT``, ``os.environ["ENVIRONMENT"]``);
                      ``server/configuration/`` and legacy ``modules/`` are outside these trees.

The naming rules apply to slices on the configuration files only; a slice
still on flat environment names keeps them until TASK-111 moves it.

Everything is read from source with ``ast``, never imported, so modules with
import-time side effects are safe to scan and a settings class nested inside
another class is still seen. Names are derived the way pydantic-settings
derives them: an alias (``alias``, ``validation_alias`` or each string of an
``AliasChoices``) is read as written, without ``env_prefix``; a field without
one is read as ``env_prefix`` plus the field name; ``populate_by_name`` also
reads the field name; a nested model field also reads each sub-field joined by
``env_nested_delimiter``. Keys are compared case-insensitively, because
pydantic-settings matches case-insensitively by default, always on Windows and
for aliases. An alias the script cannot read as a literal string fails the
check instead of being skipped.

Each key is recorded as a ``Claim`` of (source kind, key, owner), and
``find_collisions`` groups claims by source kind and key, so environment names
and configuration-file tables share one ownership rule.

There is deliberately no baseline: the tree is clean, so any violation is new.

Usage:
    python3 -m bin.check_settings_key_ownership
"""

import ast
import re
import sys
import tomllib
from collections import defaultdict
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from pathlib import Path

from bin.freeze_guard import EXCLUDED_DIR_NAMES, iter_python_files

APP_ROOT = Path(__file__).resolve().parent.parent

# Test doubles redeclare real keys on purpose; only shipped code is judged.
SCANNED_EXCLUSIONS = EXCLUDED_DIR_NAMES | {"tests"}

# Developer scripts read their own environment; they are not app code.
ENVIRON_EXEMPT_ROOTS = frozenset({"bin"})

# Where a plugin or the scheduler is decided to run: judged by plugin-switch and environment-gate.
RUN_SWITCH_FILES = frozenset({"server/lifespan.py"})
RUN_SWITCH_ROOTS = ("server/plugins/", "packages/", "features/", "jobs/")
ENVIRONMENT_NAME = "environment"

# Names the platform sets for the app; they keep their bare names.
PLATFORM_NAMES = frozenset({"ENVIRONMENT", "GIT_SHA", "FORWARDED_ALLOW_IPS"})

# Names an SDK or runtime reads itself; AWS__ (a table prefix) is not one of them.
SDK_NAMESPACE = re.compile(r"(AWS|UVICORN|OTEL)_[^_]")

ENV_SOURCE = "env"
TABLE_SOURCE = "config-table"
CONFIG_DIR_NAME = "config"
SETTINGS_ROOT = ("pydantic_settings", "BaseSettings")
MODEL_ROOT = ("pydantic", "BaseModel")
CONFIGURATION_SLICE_ROOT = ("contracts.configuration", "ConfigurationSlice")
ENVIRON_NAMES = frozenset({"environ", "environb", "getenv", "getenvb"})
CONFIG_KEYS = frozenset(
    {"env_prefix", "env_nested_delimiter", "env_nested_max_split", "populate_by_name", "validate_by_name", "toml_table_header"}
)
MAX_NESTING = 5


@dataclass(frozen=True)
class Claim:
    """One key a settings class reads from one source, folded to lower case."""

    source_kind: str
    key: str
    owner: str


@dataclass(frozen=True)
class Collision:
    """A key read by more than one owner within one source."""

    source_kind: str
    key: str
    owners: tuple[str, ...]


@dataclass(frozen=True)
class Violation:
    """A broken rule, located by owner, key or path:line."""

    rule: str
    location: str
    message: str


@dataclass
class _Module:
    name: str
    path: str
    tree: ast.Module
    imports: dict[str, tuple[str, str]] = field(default_factory=dict)
    module_aliases: dict[str, str] = field(default_factory=dict)
    top_classes: dict[str, ast.ClassDef] = field(default_factory=dict)


@dataclass(frozen=True)
class _Class:
    module: _Module
    qualname: str
    node: ast.ClassDef

    @property
    def owner(self) -> str:
        return f"{self.module.name}:{self.qualname}"


class _Unreadable(Exception):
    """A settings declaration the script cannot turn into variable names."""


def _module_name(relative: Path) -> str:
    parts = list(relative.with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _resolve_from(module: _Module, node: ast.ImportFrom) -> str:
    """Return the absolute module an ``ImportFrom`` names, resolving relative levels."""
    if node.level == 0:
        return node.module or ""
    package = module.name.split(".")
    if not module.path.endswith("__init__.py"):
        package = package[:-1]
    base = package[: len(package) - (node.level - 1)]
    return ".".join([*base, node.module] if node.module else base)


def _iter_classes(module: _Module) -> Iterator[_Class]:
    """Yield every class in a module, nested ones included, with its qualified name."""

    def walk(node: ast.AST, prefix: str) -> Iterator[_Class]:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.ClassDef):
                qualname = f"{prefix}{child.name}"
                yield _Class(module, qualname, child)
                yield from walk(child, f"{qualname}.")
            elif isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef):
                yield from walk(child, f"{prefix}{child.name}.<locals>.")
            else:
                yield from walk(child, prefix)

    yield from walk(module.tree, "")


class _Tree:
    """A parsed source tree with base-class resolution across its modules."""

    def __init__(self, root: Path) -> None:
        self.modules: dict[str, _Module] = {}
        for path in iter_python_files(root, SCANNED_EXCLUSIONS):
            relative = path.relative_to(root)
            module = _Module(
                name=_module_name(relative),
                path=relative.as_posix(),
                tree=ast.parse(path.read_text(encoding="utf-8"), filename=str(path)),
            )
            for node in ast.walk(module.tree):
                if isinstance(node, ast.ImportFrom):
                    source = _resolve_from(module, node)
                    for alias in node.names:
                        module.imports[alias.asname or alias.name] = (source, alias.name)
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        module.module_aliases[alias.asname or alias.name] = alias.name
            module.top_classes = {node.name: node for node in module.tree.body if isinstance(node, ast.ClassDef)}
            self.modules[module.name] = module
        self.classes = [cls for module in self.modules.values() for cls in _iter_classes(module)]
        self._kinds: dict[tuple[str, str], str | None] = {}

    def lookup(self, key: tuple[str, str], seen: frozenset[tuple[str, str]] = frozenset()) -> _Class | None:
        """Return the class a (module, name) key points to, following re-exports."""
        module = self.modules.get(key[0])
        if module is None or key in seen:
            return None
        node = module.top_classes.get(key[1])
        if node is not None:
            return _Class(module, node.name, node)
        if key[1] in module.imports:
            return self.lookup(module.imports[key[1]], seen | {key})
        return None

    def base_keys(self, cls: _Class) -> list[tuple[str, str]]:
        """Return the (module, name) key of each base class, as far as source shows it."""
        keys = []
        for base in cls.node.bases:
            if isinstance(base, ast.Name):
                if base.id in cls.module.top_classes:
                    keys.append((cls.module.name, base.id))
                elif base.id in cls.module.imports:
                    keys.append(cls.module.imports[base.id])
            elif isinstance(base, ast.Attribute) and isinstance(base.value, ast.Name):
                keys.append((cls.module.module_aliases.get(base.value.id, base.value.id), base.attr))
        return keys

    def bases(self, cls: _Class) -> list[_Class]:
        return [base for key in self.base_keys(cls) if (base := self.lookup(key)) is not None]

    def kind(self, cls: _Class) -> str | None:
        """Return "settings", "model" or None for a class, from its base chain."""
        memo = (cls.module.name, cls.qualname)
        if memo in self._kinds:
            return self._kinds[memo]
        self._kinds[memo] = None
        kinds: set[str | None] = set()
        for key in self.base_keys(cls):
            if key == SETTINGS_ROOT:
                kinds.add("settings")
            elif key == MODEL_ROOT:
                kinds.add("model")
            elif (base := self.lookup(key)) is not None:
                kinds.add(self.kind(base))
        result = "settings" if "settings" in kinds else "model" if "model" in kinds else None
        self._kinds[memo] = result
        return result

    def settings_classes(self) -> list[_Class]:
        return [cls for cls in self.classes if self.kind(cls) == "settings"]

    def derives_from(self, cls: _Class, root: tuple[str, str], seen: frozenset[str] = frozenset()) -> bool:
        """Return True when a class's base chain reaches the (module, name) root."""
        for key in self.base_keys(cls):
            base = self.lookup(key)
            if key == root or (base is not None and (base.module.name, base.qualname) == root):
                return True
            if base is not None and base.owner not in seen and self.derives_from(base, root, seen | {cls.owner}):
                return True
        return False

    def model_for(self, module: _Module, annotation: ast.expr | None) -> _Class | None:
        """Return the pydantic model an annotation names (``X``, ``X | None``, ``Optional[X]``)."""
        if annotation is None:
            return None
        if isinstance(annotation, ast.BinOp):
            return self.model_for(module, annotation.left) or self.model_for(module, annotation.right)
        if isinstance(annotation, ast.Subscript):
            return self.model_for(module, annotation.slice)
        if isinstance(annotation, ast.Name):
            key = (module.name, annotation.id) if annotation.id in module.top_classes else module.imports.get(annotation.id)
            target = self.lookup(key) if key else None
            if target is not None and self.kind(target) in {"model", "settings"}:
                return target
        return None


def _model_config_value(cls: _Class) -> ast.expr | None:
    """Return the expression a class assigns to ``model_config``, if it assigns one."""
    for statement in cls.node.body:
        if isinstance(statement, ast.Assign) and len(statement.targets) == 1:
            target, value = statement.targets[0], statement.value
        elif isinstance(statement, ast.AnnAssign) and statement.value is not None:
            target, value = statement.target, statement.value
        else:
            continue
        if isinstance(target, ast.Name) and target.id == "model_config":
            return value
    return None


def _literal_config(cls: _Class) -> dict[str, object]:
    """Return the name-relevant keys of a class's own ``model_config``."""
    value = _model_config_value(cls)
    if value is None:
        return {}
    pairs: list[tuple[str | None, ast.expr]]
    if isinstance(value, ast.Call) and not value.args:
        pairs = [(keyword.arg, keyword.value) for keyword in value.keywords]
    elif isinstance(value, ast.Dict):
        pairs = [
            (key.value if isinstance(key, ast.Constant) and isinstance(key.value, str) else None, item)
            for key, item in zip(value.keys, value.values, strict=True)
        ]
    else:
        raise _Unreadable("model_config is not a literal SettingsConfigDict(...) or dict")
    config: dict[str, object] = {}
    for name, item in pairs:
        if name is None:
            raise _Unreadable("model_config unpacks another mapping")
        if name == "toml_table_header":
            if not (
                isinstance(item, ast.Tuple)
                and all(isinstance(part, ast.Constant) and isinstance(part.value, str) for part in item.elts)
            ):
                raise _Unreadable("model_config toml_table_header is not a literal tuple of strings")
            config[name] = tuple(part.value for part in item.elts if isinstance(part, ast.Constant))
        elif name in CONFIG_KEYS:
            if not isinstance(item, ast.Constant):
                raise _Unreadable(f"model_config {name} is not a literal")
            config[name] = item.value
    return config


def _config(tree: _Tree, cls: _Class, seen: frozenset[str] = frozenset()) -> dict[str, object]:
    """Return a class's config merged over its bases' configs, as pydantic merges them."""
    merged: dict[str, object] = {}
    for base in reversed(tree.bases(cls)):
        if base.owner not in seen:
            merged.update(_config(tree, base, seen | {cls.owner}))
    merged.update(_literal_config(cls))
    return merged


def _is_class_var(annotation: ast.expr) -> bool:
    node = annotation.value if isinstance(annotation, ast.Subscript) else annotation
    return (isinstance(node, ast.Name) and node.id == "ClassVar") or (isinstance(node, ast.Attribute) and node.attr == "ClassVar")


def _field_call(statement: ast.AnnAssign) -> ast.Call | None:
    """Return the ``Field(...)`` call declaring a field, as a default or in ``Annotated``."""
    candidates: list[ast.expr] = [statement.value] if statement.value is not None else []
    annotation = statement.annotation
    if isinstance(annotation, ast.Subscript) and isinstance(annotation.slice, ast.Tuple):
        candidates.extend(annotation.slice.elts[1:])
    for candidate in candidates:
        if isinstance(candidate, ast.Call):
            func = candidate.func
            if (isinstance(func, ast.Name) and func.id == "Field") or (isinstance(func, ast.Attribute) and func.attr == "Field"):
                return candidate
    return None


def _declared_fields(cls: _Class) -> Iterator[tuple[str, ast.AnnAssign]]:
    """Yield each pydantic field a class declares itself (inherited ones are its base's)."""
    for statement in cls.node.body:
        if not (isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name)):
            continue
        name = statement.target.id
        if name.startswith("_") or name == "model_config" or _is_class_var(statement.annotation):
            continue
        yield name, statement


def _alias_names(value: ast.expr) -> list[str]:
    """Return the variable names an alias expression reads, or raise when it is not literal."""
    if isinstance(value, ast.Constant) and isinstance(value.value, str):
        return [value.value]
    if isinstance(value, ast.Call):
        func = value.func
        func_name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else ""
        if func_name == "AliasChoices" and not value.keywords:
            names = []
            for choice in value.args:
                if not (isinstance(choice, ast.Constant) and isinstance(choice.value, str)):
                    raise _Unreadable("an AliasChoices entry is not a literal string (AliasPath has no variable name)")
                names.append(choice.value)
            return names
        if func_name == "AliasPath":
            raise _Unreadable("AliasPath has no environment variable name")
    raise _Unreadable(f"alias {ast.unparse(value)} is not a literal string")


def _field_names(statement: ast.AnnAssign, name: str, prefix: str, by_name: bool) -> list[str]:
    """Return the environment names one field reads, before nesting."""
    call = _field_call(statement)
    keywords = {keyword.arg: keyword.value for keyword in call.keywords} if call else {}
    alias = keywords.get("validation_alias") or keywords.get("alias")
    names = _alias_names(alias) if alias is not None else []
    if alias is None or by_name:
        names.append(prefix + name)
    return names


def _sub_field_names(tree: _Tree, model: _Class, delimiter: str, depth: int, seen: frozenset[str]) -> list[str]:
    """Return the delimited sub-field names of a nested model, its bases' fields included."""
    names: list[str] = []
    for owner in [*reversed(tree.bases(model)), model]:
        if tree.kind(owner) is None or owner.owner in seen:
            continue
        for name, statement in _declared_fields(owner):
            call = _field_call(statement)
            alias = next((keyword.value for keyword in call.keywords if keyword.arg == "alias"), None) if call else None
            sub = alias.value if isinstance(alias, ast.Constant) and isinstance(alias.value, str) else name
            names.append(sub)
            nested = tree.model_for(owner.module, statement.annotation)
            if nested is not None and depth > 1:
                deeper = _sub_field_names(tree, nested, delimiter, depth - 1, seen | {model.owner})
                names.extend(f"{sub}{delimiter}{name}" for name in deeper)
    return names


def _class_claims(tree: _Tree, cls: _Class) -> list[Claim]:
    config = _config(tree, cls)
    prefix = str(config.get("env_prefix") or "")
    by_name = bool(config.get("populate_by_name") or config.get("validate_by_name"))
    delimiter = config.get("env_nested_delimiter")
    max_split = config.get("env_nested_max_split")
    depth = int(max_split) if isinstance(max_split, int) and max_split > 0 else MAX_NESTING
    keys: list[str] = []
    for name, statement in _declared_fields(cls):
        names = _field_names(statement, name, prefix, by_name)
        keys.extend(names)
        model = tree.model_for(cls.module, statement.annotation)
        if model is not None and isinstance(delimiter, str) and delimiter:
            subs = _sub_field_names(tree, model, delimiter, depth, frozenset({cls.owner}))
            keys.extend(f"{top}{delimiter}{sub}" for top in names for sub in subs)
    claims = [Claim(source_kind=ENV_SOURCE, key=key.lower(), owner=cls.owner) for key in dict.fromkeys(keys)]
    header = config.get("toml_table_header")
    if isinstance(header, tuple) and header:
        if len(header) != 1:
            raise _Unreadable("toml_table_header must name exactly one table")
        claims.append(Claim(source_kind=TABLE_SOURCE, key=str(header[0]).lower(), owner=cls.owner))
    return claims


def _collect(tree: _Tree) -> tuple[list[Claim], list[Violation]]:
    claims: list[Claim] = []
    errors: list[Violation] = []
    for cls in tree.settings_classes():
        try:
            claims.extend(_class_claims(tree, cls))
        except _Unreadable as exc:
            errors.append(
                Violation(
                    rule="unreadable-alias",
                    location=cls.owner,
                    message=f"{cls.owner}: {exc}; declare the variable name as a literal string",
                )
            )
    return claims, errors


def collect_claims(root: Path) -> tuple[list[Claim], list[Violation]]:
    """Return every key and table the settings classes under root claim, and any unreadable declaration."""
    return _collect(_Tree(root))


def collect_env_claims(root: Path) -> tuple[list[Claim], list[Violation]]:
    """Return every environment key the settings classes under root read, and any unreadable declaration."""
    claims, errors = collect_claims(root)
    return [claim for claim in claims if claim.source_kind == ENV_SOURCE], errors


def find_collisions(claims: Iterable[Claim]) -> list[Collision]:
    """Return each (source kind, key) claimed by more than one owner."""
    owners: dict[tuple[str, str], set[str]] = defaultdict(set)
    for claim in claims:
        owners[(claim.source_kind, claim.key)].add(claim.owner)
    return [
        Collision(source_kind=source_kind, key=key, owners=tuple(sorted(names)))
        for (source_kind, key), names in sorted(owners.items())
        if len(names) > 1
    ]


def find_vendor_switches(claims: Iterable[Claim]) -> list[Violation]:
    """Return each ``<VENDOR>_ENABLED`` key a vendor client slice reads."""
    violations = []
    for claim in claims:
        if claim.source_kind != ENV_SOURCE:
            continue
        key = claim.key.upper()
        in_integrations = claim.owner.split(".", 1)[0] == "integrations"
        if in_integrations and (key == "ENABLED" or key.endswith("_ENABLED")):
            violations.append(
                Violation(
                    rule="vendor-enabled",
                    location=claim.owner,
                    message=f"{claim.owner} reads {key}: a vendor client is enabled by its tenant entry, never a <VENDOR>_ENABLED key",
                )
            )
    return violations


def _is_environ_read(module: _Module, node: ast.AST) -> bool:
    """Return True for ``os.environ`` / ``os.getenv`` access and ``from os import environ``."""
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
        return module.module_aliases.get(node.value.id) == "os" and node.attr in ENVIRON_NAMES
    if isinstance(node, ast.ImportFrom):
        return node.module == "os" and any(alias.name in ENVIRON_NAMES for alias in node.names)
    return False


def _iter_environ_reads(module: _Module, node: ast.AST, settings_nodes: set[int], inside: bool) -> Iterator[int]:
    """Yield the line of each environment read outside a settings class body."""
    for child in ast.iter_child_nodes(node):
        child_inside = inside or id(child) in settings_nodes
        if not child_inside and isinstance(child, ast.expr | ast.stmt) and _is_environ_read(module, child):
            yield child.lineno
        yield from _iter_environ_reads(module, child, settings_nodes, child_inside)


def _environ_reads(tree: _Tree) -> list[Violation]:
    settings_nodes = {id(cls.node) for cls in tree.settings_classes()}
    violations = []
    for module in sorted(tree.modules.values(), key=lambda item: item.path):
        if module.path.split("/", 1)[0] in ENVIRON_EXEMPT_ROOTS:
            continue
        for line in sorted(_iter_environ_reads(module, module.tree, settings_nodes, False)):
            location = f"{module.path}:{line}"
            message = f"{location} reads the environment outside a settings class; read it through the owning settings slice"
            violations.append(Violation(rule="environ-read", location=location, message=message))
    return violations


def _decides_runs(path: str) -> bool:
    """Return True for a module where a plugin or the scheduler is decided to run."""
    return path in RUN_SWITCH_FILES or path.startswith(RUN_SWITCH_ROOTS)


def _plugin_switches(tree: _Tree) -> list[Violation]:
    """Return each flat ``enabled`` switch a settings class in a run-deciding tree declares."""
    violations = []
    for cls in tree.settings_classes():
        if not _decides_runs(cls.module.path) or tree.derives_from(cls, CONFIGURATION_SLICE_ROOT):
            continue
        try:
            prefixed = bool(_config(tree, cls).get("env_prefix"))
        except _Unreadable:
            continue  # reported as unreadable-alias
        for name, _ in _declared_fields(cls):
            folded = name.lower()
            if folded == "enabled" or (not prefixed and folded.endswith("_enabled")):
                message = (
                    f"{cls.owner} declares {name}: a plugin or the scheduler runs on a configuration-file key"
                    " ([plugins.<area>] or [scheduler] enabled), never a flat environment switch"
                )
                violations.append(Violation(rule="plugin-switch", location=cls.owner, message=message))
    return violations


def _names_environment(node: ast.expr) -> bool:
    """Return True for an expression that reads the environment name."""
    if isinstance(node, ast.Name):
        return node.id.lower() == ENVIRONMENT_NAME
    if isinstance(node, ast.Attribute):
        return node.attr.lower() == ENVIRONMENT_NAME
    if isinstance(node, ast.Subscript):
        key = node.slice
        return isinstance(key, ast.Constant) and isinstance(key.value, str) and key.value.lower() == ENVIRONMENT_NAME
    if isinstance(node, ast.Call):
        return any(
            isinstance(arg, ast.Constant) and isinstance(arg.value, str) and arg.value.lower() == ENVIRONMENT_NAME
            for arg in node.args
        )
    return False


def _environment_gates(tree: _Tree) -> list[Violation]:
    """Return each comparison against the environment name in a run-deciding module."""
    violations = []
    for module in sorted(tree.modules.values(), key=lambda item: item.path):
        if not _decides_runs(module.path):
            continue
        lines = {
            node.lineno
            for node in ast.walk(module.tree)
            if isinstance(node, ast.Compare) and any(_names_environment(side) for side in (node.left, *node.comparators))
        }
        for line in sorted(lines):
            location = f"{module.path}:{line}"
            message = (
                f"{location} compares the environment name; whether a plugin or the scheduler runs is a"
                " configuration-file key, set per environment in that environment's file"
            )
            violations.append(Violation(rule="environment-gate", location=location, message=message))
    return violations


def _collision_violation(collision: Collision) -> Violation:
    owners = ", ".join(collision.owners)
    if collision.source_kind == TABLE_SOURCE:
        message = f"table [{collision.key}] is named by {owners}; one table has exactly one owning slice"
        return Violation(rule="key-ownership", location=f"[{collision.key}]", message=message)
    message = f"{collision.source_kind} key {collision.key.upper()} is read by {owners}; one key has exactly one owning slice"
    return Violation(rule="key-ownership", location=collision.key.upper(), message=message)


def _read_tables(path: Path, root: Path) -> tuple[set[str], list[Violation]]:
    """Return the top-level tables of one configuration file, or the parse failure."""
    location = path.relative_to(root).as_posix()
    try:
        return set(tomllib.loads(path.read_text(encoding="utf-8"))), []
    except tomllib.TOMLDecodeError as exc:
        return set(), [Violation(rule="invalid-config", location=location, message=f"{location}: invalid TOML: {exc}")]


def _table_violations(root: Path, claims: Iterable[Claim]) -> list[Violation]:
    """Return each table no slice owns and each slice table the base file lacks."""
    table_claims = sorted(
        (claim for claim in claims if claim.source_kind == TABLE_SOURCE), key=lambda claim: (claim.key, claim.owner)
    )
    owned = {claim.key for claim in table_claims}
    config_dir = root / CONFIG_DIR_NAME
    violations: list[Violation] = []
    base_tables: set[str] = set()
    for path in sorted(config_dir.glob("*.toml")):
        tables, errors = _read_tables(path, root)
        violations.extend(errors)
        if path.name == "base.toml":
            base_tables = tables
        location = path.relative_to(root).as_posix()
        for table in sorted(tables - owned):
            message = (
                f"{location}: [{table}] is named by no settings slice; name it in one slice's toml_table_header or remove it"
            )
            violations.append(Violation(rule="unowned-table", location=f"{location}:[{table}]", message=message))
    for claim in table_claims:
        if claim.key not in base_tables:
            message = f"{claim.owner} reads [{claim.key}], which {CONFIG_DIR_NAME}/base.toml lacks; the base file holds every slice's table"
            violations.append(Violation(rule="missing-table", location=claim.owner, message=message))
    return violations


def _naming_violations(tree: _Tree, claims: Iterable[Claim]) -> list[Violation]:
    """Return each name a configuration slice reads outside its table, the platform names aside."""
    slices = {cls.owner for cls in tree.settings_classes() if tree.derives_from(cls, CONFIGURATION_SLICE_ROOT)}
    tables = {claim.owner: claim.key for claim in claims if claim.source_kind == TABLE_SOURCE and claim.owner in slices}
    violations = []
    for claim in claims:
        table = tables.get(claim.owner)
        if claim.source_kind != ENV_SOURCE or table is None:
            continue
        key = claim.key.upper()
        if SDK_NAMESPACE.match(key):
            message = f"{claim.owner} reads {key}: the SDK or runtime reads this name itself, so no slice declares it"
            violations.append(Violation(rule="sdk-namespace", location=claim.owner, message=message))
        elif key not in PLATFORM_NAMES and not key.startswith(f"{table.upper()}__"):
            message = f"{claim.owner} reads {key}: a slice on the configuration files reads {table.upper()}__<FIELD> names only, with no per-field alias"
            violations.append(Violation(rule="env-naming", location=claim.owner, message=message))
    return violations


def find_violations(root: Path) -> list[Violation]:
    """Return every broken rule for the source tree under root."""
    tree = _Tree(root)
    claims, errors = _collect(tree)
    collisions = [_collision_violation(collision) for collision in find_collisions(claims)]
    return [
        *errors,
        *collisions,
        *_table_violations(root, claims),
        *_naming_violations(tree, claims),
        *find_vendor_switches(claims),
        *_environ_reads(tree),
        *_plugin_switches(tree),
        *_environment_gates(tree),
    ]


def main() -> int:
    violations = find_violations(APP_ROOT)

    if violations:
        print("FAIL: settings keys break decisions/configuration.md's ownership checks:")
        for violation in violations:
            print(f"  - [{violation.rule}] {violation.message}")
        print(
            "\nEach environment variable and each configuration-file table has exactly one\n"
            "owning settings slice, a slice on the files reads only its own <TABLE>__ names,\n"
            "a vendor client is enabled by its tenant entry, a plugin or the scheduler runs on a\n"
            "configuration-file key, and only settings classes read the environment. Move the key\n"
            "or table to its one owner, or read it through that slice."
        )
        return 1

    print(
        "OK: every settings key and configuration table has one owner, slices on the files read only their own names,"
        " no vendor, plugin or environment run switch exists, and only settings classes read the environment."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
