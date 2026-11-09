#!/usr/bin/env python3
"""Package-shape guard for app/features/ and app/capabilities/.

decisions/feature-packages.md fixes one package shape for every feature,
capability and umbrella subdomain, and plugin-architecture.md and plugins.md
name the CI checks that enforce it. This guard is those checks.

Every top-level directory under features/ or capabilities/ is a package. It is
an umbrella when no entry point names it (or its plugin module) and it holds a
child directory outside the layout table's directories; otherwise it is a flat
package. A settings-only package without an entry point is therefore flat, and
a flat plugin with a stray directory still fails on that directory's name.

Rules, each reported as one key:
  - a flat package, an umbrella subdomain and an umbrella core/ hold only names
    from the layout table (``<path>``); service and domain may each be a module
    or a package; api.py and hookspecs.py only in a capability, api.py also in
    core/; plugin.py only where an entry point names it
    (``<path>:plugin-unnamed``);
  - an umbrella's __init__.py holds nothing but whitespace
    (``<path>:umbrella-init``) and its root holds only __init__.py, README.md
    and its subdomain, core and common directories (``<path>``);
  - core/ has no entrypoints/ (``<core>:core-entrypoints``), no hookimpl in any
    module (``<core>:core-hookimpl``) and no entry point
    (``<core>:core-entry-point``);
  - common/ holds no adapters/, store.py or providers.py (``<path>``);
  - a package whose __init__.py or plugin.py defines a hookimpl is named by an
    entry point (``<path>:no-entry-point``);
  - an entry point into features/ or capabilities/ is named ``<package>`` for a
    flat package and ``<umbrella>.<subdomain>`` for a subdomain
    (``<name>:entry-point-name``);
  - a capability's README.md has a ``## Classification`` section whose first
    line is ``generic`` or ``supporting``, and a ``## Feature consumers``
    section listing ``- features.<feature>[.<subdomain>]`` bullets that each
    resolve to a directory under features/
    (``<path>:readme-missing|readme-classification|readme-consumers``).

The names come from bin/package_layout.toml, the machine copy of the layout
table, through bin/package_layout.py: one source for this guard and the
generator.

Known violations are grandfathered in bin/baselines/package_shape.txt, each
group naming the task that removes it. A violation not in the baseline fails;
a baselined one that is gone is reported stale and never fails (the baseline
only ratchets down, decisions/migration.md coexistence rule 3). The layout
table grows only by amending feature-packages.md, never by widening the
baseline.

Usage:
    python3 -m bin.check_package_shape
"""

import ast
import sys
import tomllib
from pathlib import Path

from bin.freeze_guard import EXCLUDED_DIR_NAMES, load_baseline, report
from bin.package_layout import Kind, layout
from contracts.plugins.namespace import PLUGIN_NAMESPACE

APP_ROOT = Path(__file__).resolve().parent.parent
FEATURES_ROOT = APP_ROOT / layout().roots.features
CAPABILITIES_ROOT = APP_ROOT / layout().roots.capabilities
BASELINE_PATH = Path(__file__).resolve().parent / "baselines" / "package_shape.txt"
PYPROJECT_PATH = APP_ROOT / "pyproject.toml"

CORE = "core"
COMMON = "common"
PLUGIN_MODULE = "plugin"


def _relative(path: Path) -> str:
    return path.relative_to(APP_ROOT).as_posix()


def _module(path: Path) -> str:
    return ".".join(path.relative_to(APP_ROOT).parts)


def _children(directory: Path) -> list[Path]:
    return sorted(child for child in directory.iterdir() if child.name not in EXCLUDED_DIR_NAMES)


def load_entry_points() -> dict[str, str]:
    """Return the host group's entry points as name -> target module (any ``:attr`` dropped)."""
    if not PYPROJECT_PATH.exists():
        return {}
    project = tomllib.loads(PYPROJECT_PATH.read_text(encoding="utf-8")).get("project", {})
    group: dict[str, str] = project.get("entry-points", {}).get(PLUGIN_NAMESPACE, {})
    return {name: target.split(":", 1)[0] for name, target in group.items()}


def _package_module(target: str) -> str:
    """The package an entry point registers: its target, without a trailing plugin module."""
    head, _, last = target.rpartition(".")
    return head if last == PLUGIN_MODULE and head else target


def _is_named(package: Path, targets: set[str]) -> bool:
    module = _module(package)
    return module in targets or f"{module}.{PLUGIN_MODULE}" in targets


def _defines_hookimpl(path: Path) -> bool:
    """Return True if a module decorates anything with ``hookimpl`` (bare, called or as an attribute)."""
    if not path.is_file():
        return False
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        for decorator in node.decorator_list:
            target = decorator.func if isinstance(decorator, ast.Call) else decorator
            name = target.attr if isinstance(target, ast.Attribute) else getattr(target, "id", None)
            if name == "hookimpl":
                return True
    return False


def _kind(name: str) -> Kind:
    return layout().kinds[name]


def _is_umbrella(package: Path, targets: set[str]) -> bool:
    if _is_named(package, targets):
        return False
    return any(child.is_dir() and child.name not in _kind("feature").allowed_dirs for child in _children(package))


def _check_names(package: Path, kind: Kind) -> set[str]:
    violations: set[str] = set()
    for child in _children(package):
        allowed = kind.allowed_dirs if child.is_dir() else kind.allowed_files
        if child.name not in allowed:
            violations.add(_relative(child))
    return violations


def _check_plugin_package(package: Path, kind: Kind, targets: set[str]) -> set[str]:
    """A flat package or an umbrella subdomain: table names, plugin.py, and hookimpls imply an entry point."""
    violations = _check_names(package, kind)
    plugin = package / f"{PLUGIN_MODULE}.py"
    if plugin.is_file() and f"{_module(package)}.{PLUGIN_MODULE}" not in targets:
        violations.add(f"{_relative(plugin)}:plugin-unnamed")
    if (_defines_hookimpl(package / "__init__.py") or _defines_hookimpl(plugin)) and not _is_named(package, targets):
        violations.add(f"{_relative(package)}:no-entry-point")
    return violations


def _check_core(core: Path, targets: set[str]) -> set[str]:
    violations = _check_names(core, _kind(CORE))
    key = _relative(core)
    if (core / "entrypoints").is_dir():
        violations = {v for v in violations if v != f"{key}/entrypoints"}
        violations.add(f"{key}:core-entrypoints")
    if any(_defines_hookimpl(path) for path in sorted(core.rglob("*.py"))):
        violations.add(f"{key}:core-hookimpl")
    module = _module(core)
    if any(_package_module(t) == module or _package_module(t).startswith(f"{module}.") for t in targets):
        violations.add(f"{key}:core-entry-point")
    return violations


def _check_common(common: Path) -> set[str]:
    """common/ holds none of its kind's forbidden names, and only its declared ones unless the kind is open."""
    kind = _kind(COMMON)
    violations = {_relative(child) for child in _children(common) if child.name in kind.forbidden_names}
    return violations if kind.open else violations | _check_names(common, kind)


def _check_umbrella(umbrella: Path, subdomain: Kind, targets: set[str]) -> set[str]:
    violations: set[str] = set()
    init = umbrella / "__init__.py"
    if init.is_file() and init.read_text(encoding="utf-8").strip():
        violations.add(f"{_relative(init)}:umbrella-init")
    for child in _children(umbrella):
        if child.is_file():
            if child.name not in _kind("umbrella").allowed_files:
                violations.add(_relative(child))
        elif child.name == CORE:
            violations |= _check_core(child, targets)
        elif child.name == COMMON:
            violations |= _check_common(child)
        elif child.name in _kind("feature").allowed_dirs:
            violations.add(_relative(child))
        else:
            violations |= _check_plugin_package(child, subdomain, targets)
    return violations


def _section(lines: list[str], heading: str) -> list[str] | None:
    """The non-blank lines under a ``## `` heading, up to the next one; None when the heading is absent."""
    if heading not in lines:
        return None
    body: list[str] = []
    for line in lines[lines.index(heading) + 1 :]:
        if line.startswith("## "):
            break
        if line.strip():
            body.append(line.strip())
    return body


def _check_readme(capability: Path) -> set[str]:
    key = _relative(capability)
    readme = capability / "README.md"
    if not readme.is_file():
        return {f"{key}:readme-missing"}
    lines = [line.rstrip() for line in readme.read_text(encoding="utf-8").splitlines()]
    violations: set[str] = set()

    rules = layout()
    classification = _section(lines, rules.classification_heading)
    if not classification or classification[0] not in rules.classifications:
        violations.add(f"{key}:readme-classification")

    consumers = [line.removeprefix("- ") for line in _section(lines, rules.consumers_heading) or [] if line.startswith("- ")]
    resolved = [
        consumer
        for consumer in consumers
        if consumer.startswith("features.") and (APP_ROOT.joinpath(*consumer.split("."))).is_dir()
    ]
    if not consumers or len(resolved) != len(consumers):
        violations.add(f"{key}:readme-consumers")
    return violations


def _check_entry_point_names(entry_points: dict[str, str]) -> set[str]:
    violations: set[str] = set()
    roots = {_module(FEATURES_ROOT), _module(CAPABILITIES_ROOT)}
    for name, target in sorted(entry_points.items()):
        root, _, rest = _package_module(target).partition(".")
        if root not in roots or not rest:
            continue
        if name != rest:
            violations.add(f"{name}:entry-point-name")
    return violations


def find_violations() -> set[str]:
    """Return every package-shape violation under features/ and capabilities/."""
    entry_points = load_entry_points()
    targets = set(entry_points.values())
    violations = _check_entry_point_names(entry_points)
    # A capability umbrella's subdomains take the capability shape, as its flat packages do.
    for root, flat, member in (
        (FEATURES_ROOT, _kind("feature"), _kind("subdomain")),
        (CAPABILITIES_ROOT, _kind("capability"), _kind("capability")),
    ):
        if not root.is_dir():
            continue
        for package in _children(root):
            if not package.is_dir():
                continue
            if _is_umbrella(package, targets):
                violations |= _check_umbrella(package, member, targets)
            else:
                violations |= _check_plugin_package(package, flat, targets)
            if root == CAPABILITIES_ROOT:
                violations |= _check_readme(package)
    return violations


def main() -> int:
    return report(
        current=find_violations(),
        baseline=load_baseline(BASELINE_PATH),
        baseline_path=BASELINE_PATH,
        app_root=APP_ROOT,
        stale_label="baseline entries that no longer violate the package shape (safe to remove)",
        fail_label="packages under features/ or capabilities/ break the package shape and are not in the baseline",
        remediation=(
            "Use a name from the layout table in decisions/feature-packages.md (amend that record to add a name); "
            "baselines only ratchet down (decisions/migration.md coexistence rule 3)."
        ),
        ok_template="no net-new package-shape violations ({count} baselined violation(s) remain).",
    )


if __name__ == "__main__":
    sys.exit(main())
