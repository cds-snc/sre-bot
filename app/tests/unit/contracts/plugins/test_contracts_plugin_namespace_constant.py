"""Unit tests for the plugin namespace constant and markers in contracts.plugins.

The constant is compared with the installed project metadata, and a real pluggy
PluginManager built from it must bind a function decorated with the contracts
``hookimpl`` marker, which proves the markers and the manager share one
namespace. An AST scan of the package source proves the contract imports no
app code outside ``contracts``.
"""

import ast
from importlib.metadata import metadata
from pathlib import Path

import pluggy
import pytest
from structlog.stdlib import BoundLogger

import contracts.plugins
from contracts.plugins.hookspecs import FeatureLifecycleSpecs
from contracts.plugins.namespace import PLUGIN_NAMESPACE, hookimpl, hookspec

pytestmark = pytest.mark.unit


def test_namespace_is_the_project_name_in_entry_point_group_form() -> None:
    assert metadata("sre-bot")["Name"].replace("-", "_") == PLUGIN_NAMESPACE
    assert PLUGIN_NAMESPACE == "sre_bot"


def test_both_markers_carry_the_namespace() -> None:
    assert hookspec.project_name == PLUGIN_NAMESPACE
    assert hookimpl.project_name == PLUGIN_NAMESPACE


def test_plugin_manager_built_from_the_namespace_binds_a_hookimpl() -> None:
    observed: list[object] = []

    class Plugin:
        @hookimpl
        def startup_warmup(self, logger: BoundLogger) -> None:
            observed.append(logger)

    manager = pluggy.PluginManager(PLUGIN_NAMESPACE)
    manager.add_hookspecs(FeatureLifecycleSpecs)
    manager.register(Plugin())
    sentinel = object()

    manager.hook.startup_warmup(logger=sentinel)

    assert observed == [sentinel]


def test_contracts_plugins_imports_no_app_code_outside_contracts() -> None:
    package_dir = Path(contracts.plugins.__file__).parent
    app_root = package_dir.parents[1]
    app_modules = {path.stem for path in app_root.iterdir() if path.is_dir() or path.suffix == ".py"} - {"contracts"}
    offenders: list[str] = []
    for source in sorted(package_dir.glob("*.py")):
        tree = ast.parse(source.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                modules = [node.module or ""]
            else:
                continue
            offenders.extend(f"{source.name}: {module}" for module in modules if module.split(".")[0] in app_modules)

    assert "infrastructure" in app_modules
    assert offenders == []
