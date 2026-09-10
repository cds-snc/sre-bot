#!/usr/bin/env python3
"""Freeze-baseline guardrail for the vendor-package export contract.

Each vendor package under app/integrations/ exports exactly its client
factories, classify_<vendor>_error and settings (decisions/outbound-clients.md);
app/integrations/ holds construction plus classification and nothing else
(decisions/layers.md). This script enforces that with two rules and compares
the result against the checked-in baseline
(app/bin/baselines/vendor_package_contract.txt):

  module            every .py file under app/integrations/<vendor>/ is
                    __init__.py, client.py or settings.py directly in the vendor
                    directory; nested subpackages are violations, and
                    app/integrations/__init__.py is the only allowed top-level
                    module.
  operation-result  no code reference to OperationResult anywhere under
                    app/integrations/ (import, name or attribute access;
                    docstrings and comments do not count). Classification
                    returns OperationStatus tuples and never needs it.

Directories listed in NON_VENDOR_DIRS are not vendor packages: their modules are
printed as a warning, never fail the check and are never baselined. The
operation-result rule still applies to them.

Baseline entries are rule-qualified ("<rule>:<app-relative path>"). Net-new
violations fail the check; baseline entries with no matching violation are
reported as stale but never fail it — the baseline only ratchets down.

Usage:
    python3 bin/check_vendor_package_contract.py

Retirement: delete this script and its baseline once the baseline is empty.
"""

import ast
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Literal

APP_ROOT = Path(__file__).resolve().parent.parent
INTEGRATIONS_ROOT = APP_ROOT / "integrations"
BASELINE_PATH = Path(__file__).resolve().parent / "baselines" / "vendor_package_contract.txt"
EXCLUDED_DIR_NAMES = {"__pycache__", ".mypy_cache", ".pytest_cache", ".venv"}
ALLOWED_VENDOR_MODULES = frozenset({"__init__.py", "client.py", "settings.py"})
NON_VENDOR_DIRS = frozenset({"utils"})
RULE_MODULE = "module"
RULE_OPERATION_RESULT = "operation-result"
FORBIDDEN_NAME = "OperationResult"

type ModuleVerdict = Literal["ok", "violation", "warn"]


def iter_python_files(root: Path) -> Iterator[Path]:
    """Yield every .py file under root, skipping cache/venv directories."""
    for path in sorted(root.rglob("*.py")):
        if any(part in EXCLUDED_DIR_NAMES for part in path.relative_to(root).parts):
            continue
        yield path


def classify_module(path: Path) -> ModuleVerdict:
    """Classify a module's location under INTEGRATIONS_ROOT against the vendor-package layout."""
    parts = path.relative_to(INTEGRATIONS_ROOT).parts
    if len(parts) == 1:
        return "ok" if parts[0] == "__init__.py" else "violation"
    if parts[0] in NON_VENDOR_DIRS:
        return "warn"
    if len(parts) == 2 and parts[1] in ALLOWED_VENDOR_MODULES:
        return "ok"
    return "violation"


def references_operation_result(path: Path) -> bool:
    """Return True if the module references OperationResult in code.

    Docstrings are string constants and comments never reach the AST, so prose
    mentions do not match. A SyntaxError propagates so an unparsable file fails
    the check loudly instead of being skipped.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.alias) and FORBIDDEN_NAME in (node.name.rpartition(".")[2], node.asname):
            return True
        if isinstance(node, ast.Name) and node.id == FORBIDDEN_NAME:
            return True
        if isinstance(node, ast.Attribute) and node.attr == FORBIDDEN_NAME:
            return True
    return False


def _app_relative(path: Path) -> str:
    return path.relative_to(APP_ROOT).as_posix()


def find_current_violations() -> set[str]:
    """Return a rule-qualified "<rule>:<app-relative path>" entry for every violation in integrations/."""
    violations: set[str] = set()
    for path in iter_python_files(INTEGRATIONS_ROOT):
        if classify_module(path) == "violation":
            violations.add(f"{RULE_MODULE}:{_app_relative(path)}")
        if references_operation_result(path):
            violations.add(f"{RULE_OPERATION_RESULT}:{_app_relative(path)}")
    return violations


def find_warnings() -> list[str]:
    """Return sorted app-relative paths of modules inside non-vendor directories."""
    return [_app_relative(path) for path in iter_python_files(INTEGRATIONS_ROOT) if classify_module(path) == "warn"]


def load_baseline() -> set[str]:
    """Return the set of baselined (grandfathered) entries, ignoring comments/blank lines."""
    if not BASELINE_PATH.exists():
        return set()
    lines = BASELINE_PATH.read_text(encoding="utf-8").splitlines()
    return {line.strip() for line in lines if line.strip() and not line.strip().startswith("#")}


def main() -> int:
    warnings = find_warnings()
    current = find_current_violations()
    baseline = load_baseline()
    net_new = sorted(current - baseline)
    stale = sorted(baseline - current)

    if warnings:
        print("WARN: modules in non-vendor directories under integrations/ (not failing, never baselined):")
        for entry in warnings:
            print(f"  - {entry}")
        print("integrations/ holds vendor packages only; shared helpers belong with their consumer.")

    if stale:
        print("INFO: baseline entries with no remaining violation (safe to remove):")
        for entry in stale:
            print(f"  - {entry}")

    if net_new:
        print("FAIL: vendor-package contract violations not in the baseline:")
        for entry in net_new:
            print(f"  - {entry}")
        print(f"\nBaseline: {BASELINE_PATH.relative_to(APP_ROOT.parent)}")
        print(
            "Vendor packages export only client factories, classify_<vendor>_error and settings "
            "(decisions/outbound-clients.md); move the logic into an adapter or infrastructure "
            "capability instead of widening the baseline."
        )
        return 1

    print(f"OK: no net-new vendor-package contract violations ({len(current)} baselined entry(ies) remain).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
