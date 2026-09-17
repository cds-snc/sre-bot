#!/usr/bin/env python3
"""Freeze-baseline guardrail for the packages/aws_platform transition seam.

packages/aws_platform is a provisional namespace holding adapters for legacy AWS
callers until TASK-88 moves them into the feature packages that own them. It is
a seam, not a destination: every file that reaches into it is one more caller to
move when the package is dissolved. This guard freezes the set of files allowed
to do so.

Scanned: every .py file under app/. Excluded: app/tests/ (tests import the seam
by design, and baselining them would never ratchet down), packages/aws_platform/
itself (a self-import is not a new dependent) and this script (its own constants
name the seam). app/pyproject.toml is checked separately for entry points.

A file counts as a consumer when it names the seam through any of:
  - an absolute import, e.g. ``import packages.aws_platform.adapters.dynamodb``
  - an import from inside it, e.g. ``from packages.aws_platform.adapters import dynamodb``
  - the seam as an imported name, e.g. ``from packages import aws_platform``
  - a relative import resolving to it, e.g. ``from .. import aws_platform``
  - a string constant naming it, which covers importlib.import_module targets,
    mock.patch targets and entry-point strings
  - a project entry-point or console script naming it (reported as "pyproject.toml")
Docstrings are exempt, so prose about the migration does not pin a file into the
baseline. A file that will not parse raises rather than being skipped: silently
ignoring a broken file is how a real consumer goes unnoticed.

Files already in the baseline are grandfathered. A consumer that is NOT in the
baseline is net-new and fails the check. Baseline entries that no longer
reference the seam are reported as stale (safe to remove) and never fail: the
baseline only ratchets down (decisions/migration.md coexistence rule 3).

Known blind spot, recorded so a green check is not mistaken for proof that
nothing loads the seam: server/lifespan.py calls auto_discover_plugins with
base_paths ["packages", "modules"], which walks the whole packages/ tree and
imports every sub-package. packages.aws_platform is therefore imported at
startup with no literal reference anywhere, and no AST or string scan can see
it. This guard bounds net-new NAMED dependents, which is what TASK-88 has to
migrate.

Usage:
    python3 -m bin.check_aws_platform_seam

Retirement: TASK-88 deletes this script, its baseline, the make target and the
CI step when packages/aws_platform is dissolved.
"""

import ast
import sys
import tomllib
from pathlib import Path

from bin.freeze_guard import iter_python_files, load_baseline, report

APP_ROOT = Path(__file__).resolve().parent.parent
SEAM_MODULE = "packages.aws_platform"
SEAM_TREE = APP_ROOT / "packages" / "aws_platform"
TESTS_TREE = APP_ROOT / "tests"
SELF_PATH = Path(__file__).resolve()
BASELINE_PATH = Path(__file__).resolve().parent / "baselines" / "aws_platform_seam_consumers.txt"
PYPROJECT_PATH = APP_ROOT / "pyproject.toml"

PYPROJECT_ENTRY = "pyproject.toml"


def _names_seam(dotted: str) -> bool:
    """Return True if a dotted name is the seam or lives inside it.

    The boundary check is what keeps a package such as ``packages.aws_platformer``
    out of the results; a plain prefix test would report it as a consumer.
    """
    return dotted == SEAM_MODULE or dotted.startswith(f"{SEAM_MODULE}.")


def _package_parts(path: Path) -> tuple[str, ...]:
    """Return the app-relative package parts of the file's own directory."""
    return path.resolve().relative_to(APP_ROOT).parts[:-1]


def _import_from_base(node: ast.ImportFrom, path: Path) -> str:
    """Resolve an ImportFrom to the absolute dotted package it imports from.

    ``level`` 0 is already absolute. A relative import is resolved against the
    file's own package: one dot is the current package, each further dot drops
    one more part.
    """
    if node.level == 0:
        return node.module or ""
    parts = _package_parts(path)
    kept = parts[: len(parts) - (node.level - 1)]
    if node.module:
        kept = (*kept, node.module)
    return ".".join(kept)


def _docstring_node_ids(tree: ast.Module) -> set[int]:
    """Return the ids of every docstring Constant, so prose is not a reference."""
    ids: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Module | ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            continue
        body = node.body
        if (
            body
            and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)
        ):
            ids.add(id(body[0].value))
    return ids


def references_seam(path: Path) -> bool:
    """Return True if the file names the seam in any detected form.

    A SyntaxError propagates: a file that will not parse is reported loudly
    rather than passed over as clean.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    docstring_ids = _docstring_node_ids(tree)

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(_names_seam(alias.name) for alias in node.names):
                return True
        elif isinstance(node, ast.ImportFrom):
            base = _import_from_base(node, path)
            if _names_seam(base):
                return True
            if any(_names_seam(f"{base}.{alias.name}" if base else alias.name) for alias in node.names):
                return True
        elif (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and id(node) not in docstring_ids
            and _names_seam(node.value)
        ):
            return True
    return False


def pyproject_references_seam() -> bool:
    """Return True if a project entry point or console script loads the seam."""
    if not PYPROJECT_PATH.exists():
        return False
    project = tomllib.loads(PYPROJECT_PATH.read_text(encoding="utf-8")).get("project", {})

    targets: list[str] = list(project.get("scripts", {}).values())
    for group in project.get("entry-points", {}).values():
        targets.extend(group.values())

    return any(_names_seam(target.split(":", 1)[0]) for target in targets)


def find_current_consumers() -> set[str]:
    """Return app-relative paths of every in-scope file that references the seam."""
    consumers: set[str] = set()
    for path in iter_python_files(APP_ROOT):
        if path == SELF_PATH or path.is_relative_to(TESTS_TREE) or path.is_relative_to(SEAM_TREE):
            continue
        if references_seam(path):
            consumers.add(path.relative_to(APP_ROOT).as_posix())

    if pyproject_references_seam():
        consumers.add(PYPROJECT_ENTRY)
    return consumers


def main() -> int:
    return report(
        current=find_current_consumers(),
        baseline=load_baseline(BASELINE_PATH),
        baseline_path=BASELINE_PATH,
        app_root=APP_ROOT,
        stale_label="baseline entries no longer importing packages.aws_platform (safe to remove)",
        fail_label="production files reference the packages.aws_platform transition seam but are not in the baseline",
        remediation=(
            "Baselines only ratchet down (decisions/migration.md coexistence rule 3); "
            "use the owning feature package or infrastructure capability instead of widening the seam (TASK-88)."
        ),
        ok_template="no net-new packages.aws_platform consumers ({count} baselined consumer(s) remain).",
    )


if __name__ == "__main__":
    sys.exit(main())
