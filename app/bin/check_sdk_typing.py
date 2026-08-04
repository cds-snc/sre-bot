#!/usr/bin/env python3
"""Freeze-baseline guardrail for SDK typing anti-patterns.

Scans every .py file under app/integrations/ for retired SDK anti-patterns and
compares the result against the checked-in baseline
(app/bin/baselines/sdk_typing_antipatterns.txt). Files already in the baseline
are grandfathered; any file containing an anti-pattern that is NOT in the baseline
is a net-new violation and fails the check. Baseline entries that no longer
contain anti-patterns are reported as stale (safe to remove) but never fail the
check — the baseline only ratchets down.

Anti-patterns detected:
  - execute_aws_api_call / execute_google_api_call string-dispatch
    (both definitions and call sites)
  - __doc__-based parameter discovery (docstring scraping)

Usage:
    python3 bin/check_sdk_typing.py

Retirement: delete this script and its baseline once the baseline is empty
(see decisions/sdk-typing.md "migration complete" criteria).
"""

import re
import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parent.parent
INTEGRATIONS_ROOT = APP_ROOT / "integrations"
BASELINE_PATH = Path(__file__).resolve().parent / "baselines" / "sdk_typing_antipatterns.txt"
EXCLUDED_DIR_NAMES = {"__pycache__", ".mypy_cache", ".pytest_cache", ".venv"}

_ANTIPATTERN_RE = re.compile(
    r"\bexecute_aws_api_call\b"
    r"|\bexecute_google_api_call\b"
    r"|(?<!\w)__doc__\b",
)


def iter_python_files(root: Path):
    """Yield every .py file under root, skipping cache/venv directories."""
    for path in sorted(root.rglob("*.py")):
        if any(part in EXCLUDED_DIR_NAMES for part in path.parts):
            continue
        yield path


def contains_antipattern(path: Path) -> bool:
    """Return True if the file contains any of the tracked anti-patterns."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return False
    return bool(_ANTIPATTERN_RE.search(text))


def find_current_violations() -> set[str]:
    """Return app-relative paths of every file in integrations/ with an anti-pattern."""
    violations: set[str] = set()
    for path in iter_python_files(INTEGRATIONS_ROOT):
        if contains_antipattern(path):
            violations.add(path.relative_to(APP_ROOT).as_posix())
    return violations


def load_baseline() -> set[str]:
    """Return the set of baselined (grandfathered) file paths, ignoring comments/blank lines."""
    if not BASELINE_PATH.exists():
        return set()
    lines = BASELINE_PATH.read_text(encoding="utf-8").splitlines()
    return {line.strip() for line in lines if line.strip() and not line.strip().startswith("#")}


def main() -> int:
    current = find_current_violations()
    baseline = load_baseline()
    net_new = sorted(current - baseline)
    stale = sorted(baseline - current)

    if stale:
        print("INFO: baseline entries with no remaining anti-patterns (safe to remove):")
        for entry in stale:
            print(f"  - {entry}")

    if net_new:
        print("FAIL: files contain SDK typing anti-patterns but are not in the baseline:")
        for entry in net_new:
            print(f"  - {entry}")
        print(f"\nBaseline: {BASELINE_PATH.relative_to(APP_ROOT.parent)}")
        print(
            "Baselines only ratchet down (decisions/sdk-typing.md coexistence rule); "
            "migrate the consumer off execute_*_api_call / __doc__ scraping instead of widening the baseline."
        )
        return 1

    print(f"OK: no net-new SDK anti-patterns ({len(current)} baselined file(s) remain).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
