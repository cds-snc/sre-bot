"""Unit tests for the import surface of the coordination contract.

The package root is the stable import path for the conditional-write store
types, so its ``__all__`` is compared with the full public name set. An AST
scan of the package source proves the contract imports only the standard
library and other ``contracts`` modules, so it can ship without the DynamoDB
backend.
"""

import ast
import sys
from pathlib import Path

import pytest

import contracts.coordination

pytestmark = pytest.mark.unit

PUBLIC_NAMES = {"ConditionalWriteStore", "ClaimResult", "ClaimOutcome"}


def test_package_root_exports_the_whole_coordination_surface() -> None:
    assert set(contracts.coordination.__all__) == PUBLIC_NAMES
    assert all(hasattr(contracts.coordination, name) for name in PUBLIC_NAMES)


def test_contracts_coordination_imports_only_stdlib_and_contracts() -> None:
    package_dir = Path(contracts.coordination.__file__).parent
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
            offenders.extend(
                f"{source.name}: {module}"
                for module in modules
                if (root := module.split(".")[0]) not in sys.stdlib_module_names and root != "contracts"
            )

    assert offenders == []
