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
    python3 -m bin.check_sdk_typing

Retirement: delete this script and its baseline once the baseline is empty
(see decisions/sdk-typing.md "migration complete" criteria).
"""

import re
import sys
from pathlib import Path

from bin.freeze_guard import iter_python_files, load_baseline, report

APP_ROOT = Path(__file__).resolve().parent.parent
INTEGRATIONS_ROOT = APP_ROOT / "integrations"
BASELINE_PATH = Path(__file__).resolve().parent / "baselines" / "sdk_typing_antipatterns.txt"

_ANTIPATTERN_RE = re.compile(
    r"\bexecute_aws_api_call\b"
    r"|\bexecute_google_api_call\b"
    r"|(?<!\w)__doc__\b",
)


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


def main() -> int:
    return report(
        current=find_current_violations(),
        baseline=load_baseline(BASELINE_PATH),
        baseline_path=BASELINE_PATH,
        app_root=APP_ROOT,
        stale_label="baseline entries with no remaining anti-patterns (safe to remove)",
        fail_label="files contain SDK typing anti-patterns but are not in the baseline",
        remediation=(
            "Baselines only ratchet down (decisions/sdk-typing.md coexistence rule); "
            "migrate the consumer off execute_*_api_call / __doc__ scraping instead of widening the baseline."
        ),
        ok_template="no net-new SDK anti-patterns ({count} baselined file(s) remain).",
    )


if __name__ == "__main__":
    sys.exit(main())
