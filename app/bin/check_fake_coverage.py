#!/usr/bin/env python3
"""Freeze-baseline guardrail for the in-memory fake contract.

decisions/cloud-portability.md (contract 4) requires every hosting contract and
every externally facing capability api.py Protocol to have an in-memory fake
exercised by tests. This script reads the package tree (never app/tests/) and
decides which Protocols are covered by a structural rule — the driven-port line —
rather than by an exclusion list:

  contracts      a Protocol under app/contracts/ is a hosting contract when a
                 class under app/infrastructure/ explicitly subclasses it.
                 Registrars and extension points are implemented by the host,
                 so they fall out by rule; they are printed as not covered.
  capability     a Protocol in app/capabilities/<name>/api.py faces an external
                 system when a class under that capability's adapters/
                 explicitly subclasses it.
  infrastructure a Protocol still defined under app/infrastructure/ is a hosting
                 contract not yet moved to app/contracts/, covered by location.

app/features/, app/packages/, app/integrations/ and capability adapters/ are
never read for Protocol definitions, so feature Path B adapters are out by rule.

A covered Protocol has a fake when a class in an in_memory.py module under
app/infrastructure/ or app/capabilities/ explicitly subclasses it. Explicit
subclassing is what lets mypy prove the fake implements the Protocol; each
conformance suite's enrollment test proves the fake is exercised.

Entries are "<app-relative module>:<Protocol>". Net-new gaps fail; baseline
entries with no matching gap are reported as stale but never fail it — the
baseline (app/bin/baselines/fake_coverage.txt) only ratchets down. A trailing
"# TASK-<id>" on a baseline line names the task that closes the gap.

Usage:
    python3 -m bin.check_fake_coverage
"""

import ast
import sys
from collections.abc import Iterator
from pathlib import Path

from bin.freeze_guard import iter_python_files, load_baseline, report

APP_ROOT = Path(__file__).resolve().parent.parent
BASELINE_PATH = Path(__file__).resolve().parent / "baselines" / "fake_coverage.txt"
FAKE_MODULE_NAME = "in_memory.py"
CAPABILITY_API_MODULE_NAME = "api.py"
CAPABILITY_ADAPTERS_DIR = "adapters"
PROTOCOL_NAME = "Protocol"


def _base_name(node: ast.expr) -> str | None:
    """Return the class name a base expression refers to: Name, module.Name or Name[...]."""
    if isinstance(node, ast.Subscript):
        node = node.value
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _classes(path: Path) -> Iterator[tuple[str, set[str]]]:
    """Yield (class name, base names) for every class defined in the module.

    A SyntaxError propagates so an unparsable file fails the check loudly
    instead of being skipped.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            yield node.name, {name for base in node.bases if (name := _base_name(base)) is not None}


def _protocols(path: Path) -> list[str]:
    return [name for name, bases in _classes(path) if PROTOCOL_NAME in bases]


def _subclassed_names(paths: Iterator[Path]) -> set[str]:
    return {base for path in paths for _, bases in _classes(path) for base in bases}


def _app_relative(path: Path) -> str:
    return path.relative_to(APP_ROOT).as_posix()


def _contract_protocols() -> list[tuple[str, str]]:
    return [(_app_relative(path), name) for path in iter_python_files(APP_ROOT / "contracts") for name in _protocols(path)]


def _infrastructure_implementations() -> set[str]:
    infrastructure = iter_python_files(APP_ROOT / "infrastructure")
    return _subclassed_names(path for path in infrastructure if path.name != FAKE_MODULE_NAME)


def find_covered_protocols() -> set[str]:
    """Return "<module>:<Protocol>" for every Protocol the fake contract covers."""
    implemented = _infrastructure_implementations()
    covered = {f"{module}:{name}" for module, name in _contract_protocols() if name in implemented}

    for api in sorted((APP_ROOT / "capabilities").glob(f"*/{CAPABILITY_API_MODULE_NAME}")):
        adapters = _subclassed_names(iter_python_files(api.parent / CAPABILITY_ADAPTERS_DIR))
        covered |= {f"{_app_relative(api)}:{name}" for name in _protocols(api) if name in adapters}

    for path in iter_python_files(APP_ROOT / "infrastructure"):
        if path.name != FAKE_MODULE_NAME:
            covered |= {f"{_app_relative(path)}:{name}" for name in _protocols(path)}
    return covered


def find_fakes() -> set[str]:
    """Return the names of every Protocol a package in_memory.py class explicitly subclasses."""
    fake_modules = (
        path
        for root in ("infrastructure", "capabilities")
        for path in iter_python_files(APP_ROOT / root)
        if path.name == FAKE_MODULE_NAME
    )
    return _subclassed_names(fake_modules)


def find_current_violations() -> set[str]:
    """Return "<module>:<Protocol>" for every covered Protocol with no in-memory fake."""
    fakes = find_fakes()
    return {entry for entry in find_covered_protocols() if entry.rpartition(":")[2] not in fakes}


def find_uncovered_contracts() -> list[str]:
    """Return sorted contracts Protocols no infrastructure class implements (driving ports, extension points)."""
    implemented = _infrastructure_implementations()
    return sorted(f"{module}:{name}" for module, name in _contract_protocols() if name not in implemented)


def load_baseline_entries() -> set[str]:
    """Return the baselined gaps with each line's trailing "# TASK-<id>" owner comment removed."""
    return {entry.partition("#")[0].strip() for entry in load_baseline(BASELINE_PATH)}


def main() -> int:
    uncovered = find_uncovered_contracts()
    if uncovered:
        print("INFO: contracts Protocols with no infrastructure implementation (not hosting contracts, no fake required):")
        for entry in uncovered:
            print(f"  - {entry}")

    return report(
        current=find_current_violations(),
        baseline=load_baseline_entries(),
        baseline_path=BASELINE_PATH,
        app_root=APP_ROOT,
        stale_label="baseline entries whose Protocol now has a fake or is gone (safe to remove)",
        fail_label="covered Protocols with no in-memory fake not in the baseline",
        remediation=(
            "Add an in_memory.py module next to the implementation whose class explicitly subclasses the "
            "Protocol, and run it through the Protocol's conformance suite (decisions/cloud-portability.md) "
            "instead of widening the baseline."
        ),
        ok_template="every covered Protocol has an in-memory fake ({count} baselined gap(s) remain).",
    )


if __name__ == "__main__":
    sys.exit(main())
