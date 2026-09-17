#!/usr/bin/env python3
"""Guardrail: shipped code may only import what the production image installs.

A module imported at runtime from a dev-only distribution (type stubs, test
tooling) imports fine locally and in CI, where the dev dependency group is
installed, then raises ModuleNotFoundError on boot in production, where it is
not. Type-only imports must therefore sit inside an ``if TYPE_CHECKING:`` block,
which PEP 649's lazy annotations make free -- no string quoting, no
``from __future__ import annotations``.

The rule enforced here: every non-relative import in shipped code must resolve
to the standard library, to first-party code, or to a distribution in the
transitive closure of ``[project] dependencies``.

Everything is derived from pyproject.toml, so the check needs no editing when a
dependency, a shipped package or a first-party root is added:
  - shipped trees          <- [tool.hatch.build.targets.wheel] packages (+ main.py)
  - first-party roots      <- [tool.ruff.lint.isort] known-first-party
  - allowed distributions  <- [project] dependencies, resolved transitively
                              through installed metadata, honouring extras and
                              environment markers

There is deliberately no baseline: the tree is clean, so any violation is
net-new and is fixed by moving the import under ``if TYPE_CHECKING:``.

Usage:
    python3 bin/check_runtime_imports.py
"""

import ast
import sys
import tomllib
from collections.abc import Iterator
from importlib import metadata
from pathlib import Path

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

APP_ROOT = Path(__file__).resolve().parent.parent
PYPROJECT_PATH = APP_ROOT / "pyproject.toml"
EXCLUDED_DIR_NAMES = {"__pycache__", ".mypy_cache", ".pytest_cache", ".venv", "node_modules"}

# Shipped modules that are not declared anywhere but are always importable.
ALWAYS_AVAILABLE = {"__future__"}


def load_pyproject() -> dict:
    """Return the parsed pyproject.toml."""
    with PYPROJECT_PATH.open("rb") as handle:
        return tomllib.load(handle)


def shipped_roots(pyproject: dict) -> list[Path]:
    """Return the paths that end up in the wheel: every packaged tree, plus main.py."""
    packages = pyproject["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"]
    roots = [APP_ROOT / name for name in packages]
    main = APP_ROOT / "main.py"
    if main.exists():
        roots.append(main)
    return [path for path in roots if path.exists()]


def first_party_names(pyproject: dict) -> set[str]:
    """Return the first-party import roots, reusing ruff's isort configuration."""
    return set(pyproject["tool"]["ruff"]["lint"]["isort"]["known-first-party"])


def runtime_distributions(pyproject: dict) -> set[str]:
    """Return the canonical names of every distribution the production image installs.

    Walks ``[project] dependencies`` transitively through installed metadata.
    A requirement is followed only when its environment marker holds for the
    extras it was reached under, so an extra-gated dependency of a runtime
    package is not mistaken for a runtime dependency itself.
    """
    stack = [(canonicalize_name(req.name), frozenset(req.extras)) for req in map(Requirement, pyproject["project"]["dependencies"])]
    seen: set[tuple[str, frozenset[str]]] = set()
    while stack:
        entry = stack.pop()
        if entry in seen:
            continue
        seen.add(entry)
        name, extras = entry
        try:
            requires = metadata.requires(name) or []
        except metadata.PackageNotFoundError:
            # Not installed here; it cannot supply an importable module either.
            continue
        environments = [{"extra": extra} for extra in extras] or [{}]
        for raw in requires:
            req = Requirement(raw)
            if req.marker and not any(req.marker.evaluate(env) for env in environments):
                continue
            stack.append((canonicalize_name(req.name), frozenset(req.extras)))
    return {name for name, _ in seen}


def runtime_modules(distributions: set[str]) -> set[str]:
    """Return every top-level module name supplied by the given distributions."""
    modules = set()
    for module, providers in metadata.packages_distributions().items():
        if any(canonicalize_name(provider) in distributions for provider in providers):
            modules.add(module)
    return modules


def iter_python_files(root: Path) -> Iterator[Path]:
    """Yield every .py file under root (or root itself), skipping cache directories."""
    if root.is_file():
        yield root
        return
    for path in sorted(root.rglob("*.py")):
        if any(part in EXCLUDED_DIR_NAMES for part in path.parts):
            continue
        yield path


def _is_type_checking_test(test: ast.expr) -> bool:
    """Return True for `TYPE_CHECKING` and `typing.TYPE_CHECKING` guard conditions."""
    if isinstance(test, ast.Name):
        return test.id == "TYPE_CHECKING"
    if isinstance(test, ast.Attribute):
        return test.attr == "TYPE_CHECKING"
    return False


def iter_unguarded_imports(tree: ast.Module) -> Iterator[tuple[ast.stmt, str]]:
    """Yield (node, top-level module name) for each import evaluated at runtime.

    Imports nested inside an ``if TYPE_CHECKING:`` block are skipped, as are
    relative imports, which are first-party by construction.
    """

    def walk(node: ast.AST, guarded: bool) -> Iterator[tuple[ast.stmt, str]]:
        for child in ast.iter_child_nodes(node):
            child_guarded = guarded
            if isinstance(node, ast.If) and _is_type_checking_test(node.test) and child in node.body:
                child_guarded = True
            if not child_guarded:
                if isinstance(child, ast.Import):
                    for alias in child.names:
                        yield child, alias.name.split(".")[0]
                elif isinstance(child, ast.ImportFrom) and child.level == 0 and child.module:
                    yield child, child.module.split(".")[0]
            yield from walk(child, child_guarded)

    yield from walk(tree, False)


def find_violations(pyproject: dict) -> list[tuple[str, int, str]]:
    """Return (path, line, module) for every shipped import production cannot resolve."""
    allowed = (
        runtime_modules(runtime_distributions(pyproject)) | first_party_names(pyproject) | sys.stdlib_module_names | ALWAYS_AVAILABLE
    )
    violations = []
    for root in shipped_roots(pyproject):
        for path in iter_python_files(root):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node, module in iter_unguarded_imports(tree):
                if module not in allowed:
                    violations.append((path.relative_to(APP_ROOT).as_posix(), node.lineno, module))
    return sorted(violations)


def main() -> int:
    pyproject = load_pyproject()
    violations = find_violations(pyproject)

    if violations:
        print("FAIL: shipped code imports modules the production image does not install:")
        for path, line, module in violations:
            print(f"  - {path}:{line} imports {module!r}")
        print(
            "\nThese import cleanly here and in CI, where the dev dependency group is\n"
            "installed, and raise ModuleNotFoundError on boot in production.\n"
            "If the import exists only for type annotations, move it under\n"
            "`if TYPE_CHECKING:` -- PEP 649 keeps annotations lazy, so no quoting is\n"
            "needed. Otherwise promote the distribution into [project] dependencies."
        )
        return 1

    print("OK: every shipped import resolves to the standard library, first-party code, or a runtime dependency.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
