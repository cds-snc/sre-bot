#!/usr/bin/env python3
"""Test-seam guard: tests of rebuilt code fake at Protocol seams, legacy pins on named seams.

decisions/testing.md has a test replace a collaborator at its Protocol seam (a
registered fake, ``dependency_overrides``, the provider-clearing fixture), never
by patching a module's internals. Every other freeze guard reads only the
package tree, so this one reads app/tests/ and keeps rebuilt code from picking
up the legacy habit. Two zones, each on its own freeze baseline:

  strict zone   tests/{unit,integration}/{features,capabilities}/
                A patch whose target lives in features/, capabilities/ or
                modules/ is a violation, keyed ``<file>::<target>``.
  legacy pins   tests/integration/legacy_surface/
                A pin test never patches such a target inline
                (``inline:<file>::<target>``). conftest.py may, but only inside
                a top-level fixture whose docstring says ``Owning rebuild task:
                TASK-<id>``; each such seam is keyed
                ``<fixture>::<target>  # TASK-<id>``, so a seam entry without its
                fixture's owner never matches. A patch anywhere else in
                conftest.py is ``unowned:<file>::<function>::<target>``.

A patch is found by its call (``monkeypatch.setattr``/``delattr`` and its
``context()`` aliases, ``patch``, ``patch.object``, ``patch.multiple``, as a
call or a decorator). Its target is resolved statically, never imported: string
targets fold module-level constants, f-strings and ``+``; object targets go
through the test file's imports; a test-local object is not a target. Because a
patch replaces the name where it is looked up, the dotted target is then walked
through the app tree to the binding's origin, and the origin decides:

  edge      outside features/, capabilities/ and modules/ (integrations,
            infrastructure, packages, the stdlib, third-party): allowed;
  seam      a public function of a providers.py or settings.py module: allowed
            (the provider substitution decisions/testing.md sanctions, until
            the service registry replaces provider functions);
  internal  anything else in the three roots, module-level variables such as
            ``logger`` included: a violation;
  ?target   a target in the three roots that cannot be walked: a violation, so
            nothing unresolved passes silently.

Baselines only ratchet down (decisions/migration.md coexistence rule 3); its
named expand-step exception lets a pin task's PR add the seam its plan names,
with the owner comment. A move PR re-keys its own entries, same count
(decisions/testing.md). ``--print-entries`` prints the current entries for
seeding and re-keying; it writes nothing.

Usage:
    python3 -m bin.check_test_seams [--print-entries]
"""

import ast
import re
import sys
from collections.abc import Iterator
from dataclasses import dataclass
from enum import Enum
from functools import cache
from pathlib import Path

from bin.freeze_guard import iter_python_files, report

APP_ROOT = Path(__file__).resolve().parent.parent
TESTS_ROOT = APP_ROOT / "tests"
STRICT_ZONES = tuple(TESTS_ROOT / kind / area for kind in ("unit", "integration") for area in ("features", "capabilities"))
LEGACY_ZONE = TESTS_ROOT / "integration" / "legacy_surface"
STRICT_BASELINE_PATH = Path(__file__).resolve().parent / "baselines" / "test_seams_strict.txt"
LEGACY_BASELINE_PATH = Path(__file__).resolve().parent / "baselines" / "test_seams_legacy.txt"

GUARDED_ROOTS = frozenset({"features", "capabilities", "modules"})
SEAM_MODULES = frozenset({"providers", "settings"})
PATCH_RECEIVERS = frozenset({"mock", "unittest.mock", "mocker"})
PATCH_OPTIONS = frozenset({"spec", "spec_set", "create", "autospec", "new_callable"})
OWNER_DOCSTRING = re.compile(r"Owning rebuild task:\s*(TASK-\d+(?:\.\d+)*)")
OWNER_COMMENT = re.compile(r"#.*?(TASK-\d+(?:\.\d+)*)")


class Origin(Enum):
    EDGE = "edge"
    SEAM = "seam"
    INTERNAL = "internal"
    UNRESOLVED = "unresolved"


@dataclass(frozen=True)
class Binding:
    """One top-level name of a module: ``kind`` is def, class, variable or import."""

    kind: str
    target: str = ""


# Walking the app tree.


def _module_file(parts: list[str]) -> Path | None:
    base = APP_ROOT.joinpath(*parts)
    for candidate in (base.with_suffix(".py"), base / "__init__.py"):
        if candidate.is_file():
            return candidate
    return None


def _top_level(body: list[ast.stmt]) -> Iterator[ast.stmt]:
    """Module-level statements, including those under if/try/with blocks."""
    for node in body:
        yield node
        if isinstance(node, (ast.If, ast.With)):
            yield from _top_level(node.body)
            yield from _top_level(getattr(node, "orelse", []))
        elif isinstance(node, (ast.Try, ast.TryStar)):
            for block in (node.body, node.orelse, node.finalbody, *(handler.body for handler in node.handlers)):
                yield from _top_level(block)


def _absolute(module: str, is_package: bool, node: ast.ImportFrom) -> str:
    if not node.level:
        return node.module or ""
    package = module.split(".") if is_package else module.split(".")[:-1]
    base = package[: len(package) - (node.level - 1)]
    return ".".join([*base, *([node.module] if node.module else [])])


@cache
def _bindings(path: Path, module: str) -> dict[str, Binding]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    bindings: dict[str, Binding] = {}
    for node in _top_level(tree.body):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            bindings[node.name] = Binding("def")
        elif isinstance(node, ast.ClassDef):
            bindings[node.name] = Binding("class")
        elif isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                for name in ast.walk(target):
                    if isinstance(name, ast.Name):
                        bindings[name.id] = Binding("variable")
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.asname:
                    bindings[alias.asname] = Binding("import", alias.name)
                else:
                    head = alias.name.split(".")[0]
                    bindings[head] = Binding("import", head)
        elif isinstance(node, ast.ImportFrom):
            source = _absolute(module, path.name == "__init__.py", node)
            for alias in node.names:
                if alias.name != "*":
                    bindings[alias.asname or alias.name] = Binding("import", f"{source}.{alias.name}")
    return bindings


def classify(dotted: str, seen: frozenset[str] = frozenset()) -> Origin:
    """Where the binding a dotted patch target names comes from."""
    parts = dotted.split(".")
    if parts[0] not in GUARDED_ROOTS:
        return Origin.EDGE
    if dotted in seen:
        return Origin.UNRESOLVED
    for split in range(len(parts), 0, -1):
        path = _module_file(parts[:split])
        if path is not None:
            break
    else:
        return Origin.UNRESOLVED
    if split == len(parts):
        return Origin.INTERNAL
    name, rest = parts[split], parts[split + 1 :]
    binding = _bindings(path, ".".join(parts[:split])).get(name)
    if binding is None:
        return Origin.UNRESOLVED
    if binding.kind == "import":
        return classify(".".join([binding.target, *rest]), seen | {dotted})
    if binding.kind == "def" and path.stem in SEAM_MODULES and not name.startswith("_"):
        return Origin.SEAM
    return Origin.INTERNAL


# Reading one test file.


@dataclass(frozen=True)
class TestFile:
    """The names a test file binds: imported modules and objects, and its string constants."""

    imports: dict[str, str]
    constants: dict[str, str]


def _fold(node: ast.expr | None, constants: dict[str, str]) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name):
        return constants.get(node.id)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left, right = _fold(node.left, constants), _fold(node.right, constants)
        return None if left is None or right is None else left + right
    if isinstance(node, ast.JoinedStr):
        folded = [
            _fold(part.value if isinstance(part, ast.FormattedValue) else part, constants)
            for part in node.values
            if not (isinstance(part, ast.FormattedValue) and (part.format_spec or part.conversion != -1))
        ]
        if len(folded) != len(node.values) or None in folded:
            return None
        return "".join(part for part in folded if part is not None)
    return None


def _read_test_file(path: Path, tree: ast.Module) -> TestFile:
    module = ".".join(path.relative_to(APP_ROOT).with_suffix("").parts)
    imports: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports[alias.asname or alias.name.split(".")[0]] = alias.name if alias.asname else alias.name.split(".")[0]
        elif isinstance(node, ast.ImportFrom):
            source = _absolute(module, path.name == "__init__.py", node)
            for alias in node.names:
                if alias.name != "*":
                    imports[alias.asname or alias.name] = f"{source}.{alias.name}"
    constants: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            folded = _fold(node.value, constants)
            if folded is not None:
                constants[node.targets[0].id] = folded
    return TestFile(imports=imports, constants=constants)


def _object_path(node: ast.expr, test_file: TestFile) -> str | None:
    """The dotted path an object expression names through the file's imports; None when test-local."""
    if isinstance(node, ast.Name):
        return test_file.imports.get(node.id)
    if isinstance(node, ast.Attribute):
        base = _object_path(node.value, test_file)
        return f"{base}.{node.attr}" if base else None
    return None


def _is_patch(func: ast.expr) -> bool:
    if isinstance(func, ast.Name):
        return func.id == "patch"
    return isinstance(func, ast.Attribute) and func.attr == "patch" and ast.unparse(func.value) in PATCH_RECEIVERS


def _raw_targets(call: ast.Call) -> Iterator[tuple[ast.expr | None, ast.expr | None]]:
    """(object, name) pairs a patch call replaces; object None means name is a dotted string."""
    func, args = call.func, call.args
    keywords = {keyword.arg: keyword.value for keyword in call.keywords if keyword.arg}
    if isinstance(func, ast.Attribute) and func.attr in {"setattr", "delattr"} and not _is_patch(func.value):
        string_form = 2 if func.attr == "setattr" else 1
        if len(args) == string_form:
            yield None, args[0]
        elif len(args) > string_form:
            yield args[0], args[1]
    elif _is_patch(func):
        target = args[0] if args else keywords.get("target")
        if target is not None:
            yield None, target
    elif isinstance(func, ast.Attribute) and _is_patch(func.value) and args:
        if func.attr == "object" and len(args) >= 2:
            yield args[0], args[1]
        elif func.attr == "multiple":
            for name in keywords.keys() - PATCH_OPTIONS:
                yield args[0], ast.Constant(value=name)


def _resolve(owner: ast.expr | None, name: ast.expr | None, test_file: TestFile) -> tuple[str, Origin] | None:
    """The patch target and its origin, or None when it is test-local."""
    attribute = _fold(name, test_file.constants)
    if owner is None:
        if attribute is None:
            raw = ast.unparse(name) if name is not None else ""
            return ("?" + raw, Origin.UNRESOLVED) if any(root in raw for root in GUARDED_ROOTS) else None
        return attribute, classify(attribute)
    base = _object_path(owner, test_file)
    if base is None:
        return None
    if attribute is None:
        if base.split(".")[0] not in GUARDED_ROOTS:
            return None
        return f"?{base}.<{ast.unparse(name) if name is not None else ''}>", Origin.UNRESOLVED
    target = f"{base}.{attribute}"
    return target, classify(target)


def internal_patches(nodes: ast.AST, test_file: TestFile) -> Iterator[str]:
    """Each violating patch target under ``nodes``: internal, or unresolved in a guarded root."""
    for call in ast.walk(nodes):
        if not isinstance(call, ast.Call):
            continue
        for owner, name in _raw_targets(call):
            resolved = _resolve(owner, name, test_file)
            if resolved is None or resolved[1] in {Origin.EDGE, Origin.SEAM}:
                continue
            target, origin = resolved
            yield f"?{target}" if origin is Origin.UNRESOLVED and not target.startswith("?") else target


# The two zones.


def _parse(path: Path) -> tuple[ast.Module, TestFile]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return tree, _read_test_file(path, tree)


def _relative(path: Path) -> str:
    return path.relative_to(APP_ROOT).as_posix()


def strict_entries() -> set[str]:
    """``<file>::<target>`` for each internal patch in a test of features/ or capabilities/."""
    entries: set[str] = set()
    for zone in STRICT_ZONES:
        if not zone.exists():
            continue
        for path in iter_python_files(zone):
            tree, test_file = _parse(path)
            entries.update(f"{_relative(path)}::{target}" for target in internal_patches(tree, test_file))
    return entries


def _fixture_owner(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str | None:
    is_fixture = any(
        ast.unparse(decorator.func if isinstance(decorator, ast.Call) else decorator) in {"pytest.fixture", "fixture"}
        for decorator in node.decorator_list
    )
    match = OWNER_DOCSTRING.search(ast.get_docstring(node) or "")
    return match.group(1) if is_fixture and match else None


def _conftest_entries(path: Path, tree: ast.Module, test_file: TestFile) -> Iterator[str]:
    relative = _relative(path)
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            owner = _fixture_owner(node)
            for target in internal_patches(node, test_file):
                yield f"{node.name}::{target}  # {owner}" if owner else f"unowned:{relative}::{node.name}::{target}"
        else:
            scope = node.name if isinstance(node, ast.ClassDef) else "<module>"
            for target in internal_patches(node, test_file):
                yield f"unowned:{relative}::{scope}::{target}"


def legacy_entries() -> set[str]:
    """Inline pin-test patches, owned conftest seams and unowned conftest patches."""
    entries: set[str] = set()
    if not LEGACY_ZONE.exists():
        return entries
    for path in iter_python_files(LEGACY_ZONE):
        tree, test_file = _parse(path)
        if path.name == "conftest.py":
            entries.update(_conftest_entries(path, tree, test_file))
        else:
            entries.update(f"inline:{_relative(path)}::{target}" for target in internal_patches(tree, test_file))
    return entries


def _normalize(line: str) -> str | None:
    """A baseline line as an entry: comments dropped, except a seam entry keeps its owner."""
    entry, _, comment = line.partition("#")
    entry = entry.strip()
    if not entry:
        return None
    if entry.startswith(("inline:", "unowned:")) or "/" in entry.split("::")[0]:
        return entry
    owner = OWNER_COMMENT.search("#" + comment) if comment else None
    return f"{entry}  # {owner.group(1)}" if owner else entry


def load_entries(path: Path) -> set[str]:
    if not path.exists():
        return set()
    lines = path.read_text(encoding="utf-8").splitlines()
    return {entry for line in lines if (entry := _normalize(line)) is not None}


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    strict, legacy = strict_entries(), legacy_entries()
    if "--print-entries" in args:
        for title, entries in (("strict", strict), ("legacy", legacy)):
            print(f"# {title} ({len(entries)})")
            print("\n".join(sorted(entries)))
        return 0
    strict_status = report(
        current=strict,
        baseline=load_entries(STRICT_BASELINE_PATH),
        baseline_path=STRICT_BASELINE_PATH,
        app_root=APP_ROOT,
        stale_label="strict-zone patches gone; safe to remove from the baseline",
        fail_label="tests of features/ or capabilities/ patch an internal target",
        remediation=(
            "Fake at the Protocol seam instead (decisions/testing.md): a registered in-memory fake, "
            "dependency_overrides or the provider-clearing fixture; or patch the edge (integrations/, "
            "infrastructure/, the stdlib). Do not add entries (decisions/migration.md rule 3); "
            "a move PR re-keys its own entries."
        ),
        ok_template="no net-new strict-zone patches ({count} baselined)",
    )
    legacy_status = report(
        current=legacy,
        baseline=load_entries(LEGACY_BASELINE_PATH),
        baseline_path=LEGACY_BASELINE_PATH,
        app_root=APP_ROOT,
        stale_label="legacy pin seams gone; safe to remove from the baseline",
        fail_label="legacy pins patch an internal target outside an owned seam fixture",
        remediation=(
            "Move the patch into a fixture in tests/integration/legacy_surface/conftest.py whose docstring "
            "says 'Owning rebuild task: TASK-<id>'. Only the pin task its plan names adds "
            "'<fixture>::<target>  # TASK-<id>' (decisions/migration.md rule 3, expand-step exception)."
        ),
        ok_template="no net-new legacy pin seams ({count} baselined)",
    )
    return max(strict_status, legacy_status)


if __name__ == "__main__":
    sys.exit(main())
