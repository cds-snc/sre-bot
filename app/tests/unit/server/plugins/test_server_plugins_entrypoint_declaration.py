"""Unit tests that every feature plugin is declared as a pyproject entry point.

An AST scan (no imports) finds every module under ``packages/`` and ``features/``
that defines a
``@hookimpl`` function and compares it with the entry points declared in
``pyproject.toml`` under the ``PLUGIN_NAMESPACE`` group, in both directions: a
package with hookimpls but no entry-point line would silently never load. The
installed distribution metadata is compared with ``pyproject.toml`` so a stale
environment is reported with the fix. A source scan guards that no filesystem
discovery or direct first-party registration returns to production code.
"""

import ast
import tomllib
from importlib.metadata import entry_points
from pathlib import Path

import pytest

import server.plugins
from contracts.plugins.namespace import PLUGIN_NAMESPACE

pytestmark = pytest.mark.unit

APP_ROOT = Path(server.plugins.__file__).resolve().parents[2]
PLUGIN_ROOTS = (APP_ROOT / "packages", APP_ROOT / "features")
SKIPPED_TOP_LEVEL = {"tests", ".venv"}
NEVER_ENTRY_POINTS = {"access", "access.common", "incident", "incident.core", "aws_platform"}


def _declared_entry_points() -> dict[str, str]:
    pyproject = tomllib.loads((APP_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return dict(pyproject["project"]["entry-points"][PLUGIN_NAMESPACE])


def _is_hookimpl(decorator: ast.expr) -> bool:
    target = decorator.func if isinstance(decorator, ast.Call) else decorator
    if isinstance(target, ast.Name):
        return target.id == "hookimpl"
    return isinstance(target, ast.Attribute) and target.attr == "hookimpl"


def _files_with_hookimpls() -> list[Path]:
    found = []
    for source in sorted(source for root in PLUGIN_ROOTS for source in root.rglob("*.py")):
        tree = ast.parse(source.read_text(encoding="utf-8"))
        functions = (node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef))
        if any(_is_hookimpl(decorator) for function in functions for decorator in function.decorator_list):
            found.append(source)
    return found


def _plugin_root(path: Path) -> Path:
    return next(root for root in PLUGIN_ROOTS if path.is_relative_to(root))


def _plugin_name(init_file: Path) -> str:
    return ".".join(init_file.parent.relative_to(_plugin_root(init_file)).parts)


def test_pyproject_declares_only_the_plugin_namespace_group() -> None:
    pyproject = tomllib.loads((APP_ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert list(pyproject["project"]["entry-points"]) == [PLUGIN_NAMESPACE]


def test_hookimpls_are_defined_only_in_package_init_modules() -> None:
    files = _files_with_hookimpls()

    assert files, "the scan found no hookimpl at all; PLUGIN_ROOTS is wrong"
    assert [path.relative_to(APP_ROOT).as_posix() for path in files if path.name != "__init__.py"] == []


def test_every_package_with_hookimpls_has_a_matching_entry_point_and_no_other() -> None:
    with_hookimpls = {_plugin_name(path) for path in _files_with_hookimpls() if path.name == "__init__.py"}

    assert set(_declared_entry_points()) == with_hookimpls


def test_entry_points_target_the_package_named_by_their_dotted_name() -> None:
    """Each entry point targets ``<root>.<name>`` where root is ``packages`` or ``features``."""
    declared = _declared_entry_points()
    roots = {target.partition(".")[0] for target in declared.values()}

    assert roots <= {root.name for root in PLUGIN_ROOTS}
    assert {name: f"{declared[name].partition('.')[0]}.{name}" for name in declared} == declared


def test_umbrellas_shared_kernels_and_namespaces_are_never_entry_points() -> None:
    assert NEVER_ENTRY_POINTS & set(_declared_entry_points()) == set()


def test_installed_metadata_matches_pyproject_entry_points() -> None:
    installed = {ep.name: ep.value for ep in entry_points(group=PLUGIN_NAMESPACE)}

    assert installed == _declared_entry_points(), "installed entry points are stale; run `uv sync`"


def test_production_code_has_no_filesystem_discovery_or_direct_plugin_registration() -> None:
    forbidden = ("pkgutil", "walk_packages", "pm.register(", ".register(module")
    offenders = sorted(
        f"{source.relative_to(APP_ROOT).as_posix()}: {token}"
        for source in APP_ROOT.rglob("*.py")
        if source.relative_to(APP_ROOT).parts[0] not in SKIPPED_TOP_LEVEL
        for token in forbidden
        if token in source.read_text(encoding="utf-8")
    )

    assert offenders == []
