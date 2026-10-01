"""Unit test that pluggy is imported only by the contracts and the host plugin manager.

An AST scan walks every production source file under the app root (tests and
the virtual environment are skipped) and collects the files that import pluggy.
Only ``contracts/`` and ``server/plugins/`` may appear, so a feature can never
reach pluggy except through the contracts markers.
"""

import ast
from pathlib import Path

import pytest

import server.plugins

pytestmark = pytest.mark.unit

APP_ROOT = Path(server.plugins.__file__).resolve().parents[2]
SKIPPED_TOP_LEVEL = {"tests", ".venv"}
ALLOWED_PREFIXES = ("contracts/", "server/plugins/")


def _imports_pluggy(source: Path) -> bool:
    tree = ast.parse(source.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            modules = [node.module or ""]
        else:
            continue
        if any(module.split(".")[0] == "pluggy" for module in modules):
            return True
    return False


def test_pluggy_is_imported_only_in_contracts_and_server_plugins() -> None:
    importers = sorted(
        source.relative_to(APP_ROOT).as_posix()
        for source in APP_ROOT.rglob("*.py")
        if source.relative_to(APP_ROOT).parts[0] not in SKIPPED_TOP_LEVEL and _imports_pluggy(source)
    )

    assert importers, "the scan found no pluggy import at all; APP_ROOT is wrong"
    assert [path for path in importers if not path.startswith(ALLOWED_PREFIXES)] == []
