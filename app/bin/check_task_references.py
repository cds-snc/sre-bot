#!/usr/bin/env python3
"""Freeze-baseline guardrail for task ids in Python comments, docstrings and strings.

Code describes what it does. A backlog task id belongs in code only as a removal
or change marker, ``TODO(TASK-<id>)``, naming the task that deletes or changes the
lines it sits on (decisions/migration.md coexistence rule 7): that task finds its
markers with a search and removes them. Any other mention (where code came from,
which task added it, which future task will own a behaviour) goes stale the day
that task ships, and git history and the task already hold it.

Scanned: every .py file under app/, tests included (testing standards already ask
test docstrings for no task ids). Excluded: this script and its own test, whose
fixtures must spell task ids out. Task ids in TOML owner comments (import-linter
ignore lists, freeze baselines) are governed by coexistence rule 3 and are not
scanned.

An entry is ``<app-relative path>:<task id>`` for each task id a file mentions
outside a ``TODO(TASK-<id>)`` marker. Code identifiers cannot hold the hyphen of a
task id, so a text scan finds exactly the comments, docstrings and strings.

Files and ids already in the baseline are grandfathered. A new entry fails the
check. Entries no longer found are reported as stale (safe to remove) and never
fail: the baseline only ratchets down (decisions/migration.md coexistence rule 3).

Usage:
    python3 -m bin.check_task_references
    python3 -m bin.check_task_references --print-entries   # seed or inspect the baseline
"""

import re
import sys
from pathlib import Path

from bin.freeze_guard import iter_python_files, load_baseline, report

APP_ROOT = Path(__file__).resolve().parent.parent
BASELINE_PATH = Path(__file__).resolve().parent / "baselines" / "task_references.txt"
EXCLUDED_FILES = frozenset(
    {
        Path(__file__).resolve(),
        APP_ROOT / "tests" / "unit" / "bin" / "test_bin_task_references_check.py",
    }
)

TASK_ID = re.compile(r"TASK-\d+(?:\.\d+)*")
MARKER = re.compile(r"TODO\((TASK-\d+(?:\.\d+)*)\)")


def bare_task_ids(text: str) -> set[str]:
    """Return the task ids ``text`` mentions outside a ``TODO(TASK-<id>)`` marker."""
    marked = {match.start(1) for match in MARKER.finditer(text)}
    return {match.group() for match in TASK_ID.finditer(text) if match.start() not in marked}


def current_entries(app_root: Path, excluded: frozenset[Path] = EXCLUDED_FILES) -> set[str]:
    """Return ``<path>:<task id>`` for every bare task id in the .py files under ``app_root``."""
    entries: set[str] = set()
    for path in iter_python_files(app_root):
        if path.resolve() in excluded:
            continue
        relative = path.relative_to(app_root).as_posix()
        entries |= {f"{relative}:{task_id}" for task_id in bare_task_ids(path.read_text(encoding="utf-8"))}
    return entries


def main(argv: list[str]) -> int:
    """Run the guard; ``--print-entries`` prints the current entries instead."""
    current = current_entries(APP_ROOT)
    if "--print-entries" in argv:
        for entry in sorted(current):
            print(entry)
        return 0
    return report(
        current=current,
        baseline=load_baseline(BASELINE_PATH),
        baseline_path=BASELINE_PATH,
        app_root=APP_ROOT,
        stale_label="baseline entries no longer found (safe to remove)",
        fail_label="files mention a task id outside a TODO(TASK-<id>) marker and are not in the baseline",
        remediation=(
            "Describe what the code does instead. A task id belongs in code only as TODO(TASK-<id>) naming the task "
            "that removes or changes those lines (decisions/migration.md coexistence rule 7); never widen the baseline."
        ),
        ok_template="no net-new task ids outside TODO markers ({count} baselined mention(s) remain).",
    )


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
