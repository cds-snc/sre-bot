#!/usr/bin/env python3
"""Freeze-baseline guardrail for deprecated `infrastructure.clients` imports.

Scans every .py file under app/ (this script's parent directory) for imports of the
deprecated `infrastructure.clients` package and compares the result against the
checked-in baseline (app/bin/baselines/deprecated_infra_client_imports.txt). Files
already in the baseline are grandfathered; any file importing the deprecated package
that is NOT in the baseline is a net-new violation and fails the check. Baseline
entries that no longer import the deprecated package are reported as stale (safe to
remove) but never fail the check - the baseline only ratchets down.

Usage:
    python3 bin/check_deprecated_infra_client_imports.py

Retirement: delete this script and its baseline once the baseline is empty
(see decisions/migration.md "Done means" criteria).
"""

import ast
import sys
from pathlib import Path

DEPRECATED_MODULE = "infrastructure.clients"
APP_ROOT = Path(__file__).resolve().parent.parent
DEPRECATED_TREE = APP_ROOT / "infrastructure" / "clients"
BASELINE_PATH = Path(__file__).resolve().parent / "baselines" / "deprecated_infra_client_imports.txt"
EXCLUDED_DIR_NAMES = {"__pycache__", ".mypy_cache", ".pytest_cache", ".venv"}


def iter_python_files(root: Path):
    """Yield every .py file under root, skipping cache/venv directories."""
    for path in sorted(root.rglob("*.py")):
        if any(part in EXCLUDED_DIR_NAMES for part in path.parts):
            continue
        yield path


def imports_deprecated_module(path: Path) -> bool:
    """Return True if the file has an import statement naming the deprecated module."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError:
        return False

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == DEPRECATED_MODULE or alias.name.startswith(DEPRECATED_MODULE + "."):
                    return True
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module == DEPRECATED_MODULE or module.startswith(DEPRECATED_MODULE + "."):
                return True
    return False


def find_current_consumers() -> set[str]:
    """Return app-relative paths of every file (outside the deprecated tree itself) that imports it."""
    consumers: set[str] = set()
    for path in iter_python_files(APP_ROOT):
        if path == DEPRECATED_TREE or DEPRECATED_TREE in path.parents:
            continue  # internal self-imports of the deprecated tree are not new dependents
        if imports_deprecated_module(path):
            consumers.add(path.relative_to(APP_ROOT).as_posix())
    return consumers


def load_baseline() -> set[str]:
    """Return the set of baselined (grandfathered) consumer paths, ignoring comments/blank lines."""
    if not BASELINE_PATH.exists():
        return set()
    lines = BASELINE_PATH.read_text(encoding="utf-8").splitlines()
    return {line.strip() for line in lines if line.strip() and not line.strip().startswith("#")}


def main() -> int:
    current = find_current_consumers()
    baseline = load_baseline()
    net_new = sorted(current - baseline)
    stale = sorted(baseline - current)

    if stale:
        print("INFO: baseline entries no longer importing infrastructure.clients (safe to remove):")
        for entry in stale:
            print(f"  - {entry}")

    if net_new:
        print("FAIL: files import the deprecated infrastructure.clients tree but are not in the baseline:")
        for entry in net_new:
            print(f"  - {entry}")
        print(f"\nBaseline: {BASELINE_PATH.relative_to(APP_ROOT.parent)}")
        print(
            "Baselines only ratchet down (decisions/migration.md coexistence rule 3); "
            "migrate the consumer to app/integrations/ instead of widening the baseline."
        )
        return 1

    print(f"OK: no net-new infrastructure.clients imports ({len(current)} baselined consumer(s) remain).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
