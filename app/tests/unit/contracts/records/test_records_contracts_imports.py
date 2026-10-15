"""Unit tests for the import surface of the records contract.

The package root is the stable import path for every record-store type, so
its ``__all__`` is compared with the full public name set. An AST scan of the
package source proves the contract imports only the standard library and
other ``contracts`` modules, so it can ship without the DynamoDB backend.
"""

import ast
import sys
from pathlib import Path

import pytest

import contracts.records

pytestmark = pytest.mark.unit

PUBLIC_NAMES = {
    "RESERVED_ATTRIBUTE_PREFIX",
    "ExpectedValue",
    "IncrementAttribute",
    "KeySchema",
    "KeyValue",
    "RecordChange",
    "RecordIndex",
    "RecordQuery",
    "RecordStore",
    "RecordTable",
    "RemoveAttribute",
    "SetAttribute",
    "SortCondition",
    "SortOperator",
    "SortOrder",
    "resolve_query_key",
    "validate_record_item",
    "validate_record_update",
}


def test_package_root_exports_the_whole_records_surface() -> None:
    assert set(contracts.records.__all__) == PUBLIC_NAMES
    assert all(hasattr(contracts.records, name) for name in PUBLIC_NAMES)


def test_contracts_records_imports_only_stdlib_and_contracts() -> None:
    package_dir = Path(contracts.records.__file__).parent
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
