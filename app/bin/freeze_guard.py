"""Shared plumbing for the freeze-baseline guardrails under app/bin/.

A freeze-baseline guard scans a tree for one kind of violation, compares the
result against a checked-in baseline and fails only on entries the baseline does
not already grandfather. Baselines only ratchet down (decisions/migration.md
coexistence rule 3): entries disappear as code is migrated, and a stale entry is
reported as safe to remove rather than treated as an error.

Three pieces are the same in every such guard and live here:

    iter_python_files   the scan itself
    load_baseline       reading the checked-in baseline file
    report              the stale/net-new verdict, its output and its exit code

Each guard keeps its own detection rules, its own module-level path constants
and its own wording, and passes both into these helpers. Nothing here reads a
module constant or a global, so a test can point a guard at a throwaway tree by
monkeypatching that guard's constants alone.

Consumers: check_sdk_typing.py and check_vendor_package_contract.py use all
three. check_runtime_imports.py uses the walker only -- it deliberately has no
baseline, because the tree it guards is clean and any violation is net-new.

Usage: imported by the guards, never run on its own.
"""

from collections.abc import Iterable, Iterator
from pathlib import Path

EXCLUDED_DIR_NAMES = frozenset({"__pycache__", ".mypy_cache", ".pytest_cache", ".venv", "node_modules"})


def iter_python_files(root: Path, excluded: Iterable[str] = EXCLUDED_DIR_NAMES) -> Iterator[Path]:
    """Yield every .py file under root, sorted, skipping excluded directories.

    A root that is a file yields just that file, which is what lets a caller
    scan a shipped root such as main.py alongside package directories.

    Exclusions are matched on the parts *relative to root*, never on the
    absolute path: matching absolutely skips every file whenever the checkout
    itself sits under a directory named like one of the exclusions, which
    silently turns the guard into a no-op that reports a clean tree because it
    scanned nothing.
    """
    if root.is_file():
        yield root
        return
    excluded_names = frozenset(excluded)
    for path in sorted(root.rglob("*.py")):
        if any(part in excluded_names for part in path.relative_to(root).parts):
            continue
        yield path


def load_baseline(baseline_path: Path) -> set[str]:
    """Return the baselined (grandfathered) entries, ignoring blank lines and # comments.

    A missing file is an empty set rather than an error, so a new guard can be
    run against no baseline at all to seed its first one from its own output.
    """
    if not baseline_path.exists():
        return set()
    lines = baseline_path.read_text(encoding="utf-8").splitlines()
    return {line.strip() for line in lines if line.strip() and not line.strip().startswith("#")}


def report(
    *,
    current: set[str],
    baseline: set[str],
    baseline_path: Path,
    app_root: Path,
    stale_label: str,
    fail_label: str,
    remediation: str,
    ok_template: str,
) -> int:
    """Print the stale/net-new verdict for one guard and return its exit code.

    Stale entries (baselined, no longer violating) are reported and never fail:
    the baseline only ratchets down. Net-new entries fail, and the failure names
    the baseline file and what to do instead, because widening the baseline is
    the one fix that must not be the obvious one.

    The four message arguments carry the guard's own wording. ``ok_template`` is
    formatted with ``count``, the number of violations still baselined, and so
    must not contain any other brace.
    """
    net_new = sorted(current - baseline)
    stale = sorted(baseline - current)

    if stale:
        print(f"INFO: {stale_label}:")
        for entry in stale:
            print(f"  - {entry}")

    if net_new:
        print(f"FAIL: {fail_label}:")
        for entry in net_new:
            print(f"  - {entry}")
        print(f"\nBaseline: {baseline_path.relative_to(app_root.parent)}")
        print(remediation)
        return 1

    print(f"OK: {ok_template.format(count=len(current))}")
    return 0
