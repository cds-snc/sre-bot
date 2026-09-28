"""Behavior of the import-linter configuration that enforces the plugin layers.

import-linter only analyses packages listed in ``root_packages`` and rejects a
listed package that does not exist, so a layer created later (contracts,
features, capabilities) is only checked once the PR that creates it also lists
it. These tests read the real ``pyproject.toml`` and repository: they fail when
such a directory appears without being listed, when a contract with seeded
ignores could go stale silently, or when the check is not wired into the
Makefile and CI, since a check nothing runs protects nothing.
"""

import re
import tomllib
from pathlib import Path
from typing import Any

APP_ROOT = Path(__file__).resolve().parents[3]
REPO_ROOT = APP_ROOT.parent


def _importlinter_config() -> dict[str, Any]:
    with (APP_ROOT / "pyproject.toml").open("rb") as handle:
        config: dict[str, Any] = tomllib.load(handle)["tool"]["importlinter"]
    return config


def _optional_top_level_layers(config: dict[str, Any]) -> set[str]:
    """Return the top-level layer names written as optional ``(name)`` in the layers contract."""
    layers_contract = next(contract for contract in config["contracts"] if contract["id"] == "layers")
    return {name for layer in layers_contract["layers"] for name in re.findall(r"\((\w+)\)", layer)}


def test_every_existing_optional_layer_is_a_root_package() -> None:
    """A layer directory that exists but is not a root package would be skipped by every contract."""
    config = _importlinter_config()
    unlisted = sorted(
        name
        for name in _optional_top_level_layers(config)
        if (APP_ROOT / name / "__init__.py").exists() and name not in config["root_packages"]
    )

    assert unlisted == [], f"add {unlisted} to [tool.importlinter] root_packages in app/pyproject.toml"


def test_contracts_with_seeded_ignores_fail_on_stale_entries() -> None:
    """The ignore lists only shrink if an entry that no longer matches an import is an error."""
    config = _importlinter_config()
    lenient = [
        contract["id"]
        for contract in config["contracts"]
        if contract.get("ignore_imports") and contract.get("unmatched_ignore_imports_alerting") != "error"
    ]

    assert lenient == []


def test_import_contract_check_runs_in_makefile_and_ci() -> None:
    """The contracts are enforced only if CI runs lint-imports through the Makefile target."""
    makefile = (APP_ROOT / "Makefile").read_text()
    workflow = (REPO_ROOT / ".github" / "workflows" / "ci_code.yml").read_text()

    assert "check-import-contracts:\n\tuv run lint-imports" in makefile
    assert "run: make check-import-contracts" in workflow
