"""Unit tests for the translation resource spec in contracts.i18n.

The spec is built directly through the contracts import and its construction
rules are asserted on the resulting values or the raised ``ValueError``. An AST
scan of the package source proves the contract imports only the standard
library, so it stays a leaf that every layer may depend on.
"""

import ast
import dataclasses
import sys
from pathlib import Path

import pytest

import contracts.i18n
from contracts.i18n.resources import I18nResourceSpec

pytestmark = pytest.mark.unit


def test_spec_defaults_to_a_required_yaml_resource_in_the_default_domain() -> None:
    spec = I18nResourceSpec(owner="packages.test", path="/test/locales")

    assert spec.owner == "packages.test"
    assert spec.path == "/test/locales"
    assert spec.required is True
    assert spec.format == "yaml"
    assert spec.domain == "default"


def test_spec_keeps_explicit_values() -> None:
    spec = I18nResourceSpec(
        owner="packages.test",
        path="/test/locales",
        required=False,
        format="json",
        domain="test",
    )

    assert spec.required is False
    assert spec.format == "json"
    assert spec.domain == "test"


def test_spec_is_immutable() -> None:
    spec = I18nResourceSpec(owner="packages.test", path="/test/locales")

    with pytest.raises(dataclasses.FrozenInstanceError):
        spec.path = "/elsewhere"  # type: ignore[misc]


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"owner": "", "path": "/test/locales"}, "owner must not be empty"),
        ({"owner": "packages.test", "path": ""}, "path must not be empty"),
        (
            {"owner": "packages.test", "path": "/test/locales", "format": "toml"},
            "format must be 'yaml' or 'json'",
        ),
    ],
)
def test_spec_rejects_invalid_values(kwargs: dict[str, str], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        I18nResourceSpec(**kwargs)


def test_contracts_i18n_imports_only_the_standard_library() -> None:
    package_dir = Path(contracts.i18n.__file__).parent
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
                f"{source.name}: {module}" for module in modules if module.split(".")[0] not in sys.stdlib_module_names
            )

    assert offenders == []
