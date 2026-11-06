"""Behavior tests for the package generator's pyproject.toml and base.toml edits.

Each edit is built from the real files' text (read, never written), applied with
``render``, and asserted on the re-parsed result, so the tests follow whatever
the repository's contracts and enablement tables hold today. Comment lines are
compared as text because keeping them is the reason the generator edits through
tomlkit instead of rewriting the file. ``verify`` is exercised directly with a
hand-tampered result to prove a stray change is rejected before anything is
written.
"""

import tomllib
from pathlib import Path
from typing import Any

import pytest

from bin import package_toml
from bin.package_toml import TomlEditError

APP_ROOT = Path(__file__).resolve().parents[3]
PYPROJECT = (APP_ROOT / "pyproject.toml").read_text(encoding="utf-8")
BASE = (APP_ROOT / "config" / "base.toml").read_text(encoding="utf-8")


def _comments(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip().startswith("#")]


def _contract(data: dict[str, Any], contract_id: str) -> dict[str, Any]:
    contracts: list[dict[str, Any]] = data["tool"]["importlinter"]["contracts"]
    return next(contract for contract in contracts if contract.get("id") == contract_id)


def _render_pyproject(edits: list[package_toml.Edit]) -> dict[str, Any]:
    new_text = package_toml.render(PYPROJECT, edits)
    assert _comments(new_text) == _comments(PYPROJECT)
    return tomllib.loads(new_text)


def test_an_entry_point_and_its_protected_module_are_added_together() -> None:
    data = tomllib.loads(PYPROJECT)
    edits = package_toml.entry_point(data, "shop", "features.shop") + package_toml.protected_plugin(data, "features.shop")

    result = _render_pyproject(edits)

    assert result["project"]["entry-points"]["sre_bot"]["shop"] == "features.shop"
    assert "features.shop" in _contract(result, "protected-plugins")["protected_modules"]


def test_a_dotted_entry_point_name_is_written_as_one_quoted_key() -> None:
    edits = package_toml.entry_point(tomllib.loads(PYPROJECT), "incident.triage", "features.incident.triage")

    result = _render_pyproject(edits)

    assert result["project"]["entry-points"]["sre_bot"]["incident.triage"] == "features.incident.triage"


def test_an_existing_entry_point_name_bound_to_another_module_is_refused() -> None:
    with pytest.raises(TomlEditError, match="rant"):
        package_toml.entry_point(tomllib.loads(PYPROJECT), "rant", "features.rant")


def test_a_new_feature_joins_the_feature_independence_contract() -> None:
    result = _render_pyproject(package_toml.independent_feature(tomllib.loads(PYPROJECT), "features.shop"))

    assert "features.shop" in _contract(result, "feature-independence")["modules"]


def test_a_new_umbrella_gets_an_exhaustive_layers_contract_over_its_container() -> None:
    result = _render_pyproject(package_toml.umbrella_contract(tomllib.loads(PYPROJECT), "shop"))

    contract = _contract(result, "shop-umbrella")
    assert contract["type"] == "layers"
    assert contract["containers"] == ["features.shop"]
    assert contract["layers"] == []
    assert contract["exhaustive"] is True


def test_umbrella_members_keep_the_subdomains_over_core_over_common_order() -> None:
    text = package_toml.render(PYPROJECT, package_toml.umbrella_contract(tomllib.loads(PYPROJECT), "shop"))
    for member, kind in (("common", "common"), ("orders", "subdomain"), ("core", "core"), ("cart", "subdomain")):
        text = package_toml.render(text, package_toml.umbrella_member(tomllib.loads(text), "shop", member, kind))

    assert _contract(tomllib.loads(text), "shop-umbrella")["layers"] == ["cart | orders", "core", "common"]


def test_a_subdomain_joins_an_existing_umbrella_sibling_line_in_sorted_order() -> None:
    result = _render_pyproject(package_toml.umbrella_member(tomllib.loads(PYPROJECT), "incident", "triage", "subdomain"))

    layers = _contract(result, "incident-umbrella")["layers"]
    siblings = layers[0].split(" | ")
    assert "triage" in siblings
    assert siblings == sorted(siblings)
    assert layers[1:] == ["core", "common"]


def test_an_umbrella_member_without_an_umbrella_contract_is_refused() -> None:
    with pytest.raises(TomlEditError, match="features.shop"):
        package_toml.umbrella_member(tomllib.loads(PYPROJECT), "shop", "cart", "subdomain")


def test_the_capabilities_bootstrap_adds_the_root_package_wheel_package_and_guarded_sources() -> None:
    result = _render_pyproject(package_toml.capabilities_root(tomllib.loads(PYPROJECT)))

    assert "capabilities" in result["tool"]["importlinter"]["root_packages"]
    wheel_packages = result["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"]
    assert "capabilities" in wheel_packages
    assert wheel_packages == sorted(wheel_packages)
    assert "capabilities" in _contract(result, "no-host-imports")["source_modules"]
    assert "capabilities" in _contract(result, "integrations-via-adapters")["source_modules"]
    assert "capabilities" in _contract(result, "no-legacy-imports")["source_modules"]
    assert "capabilities" in _contract(result, "no-provider-imports")["source_modules"]
    assert "capabilities.**.entrypoints.slack" in _contract(result, "slack-bolt-in-entrypoints")["allowed_importers"]
    assert "(capabilities)" in _contract(result, "layers")["layers"]


@pytest.mark.parametrize(
    "build",
    [
        lambda data: package_toml.entry_point(data, "shop", "features.shop"),
        lambda data: package_toml.protected_plugin(data, "features.shop"),
        lambda data: package_toml.independent_feature(data, "features.shop"),
        lambda data: package_toml.umbrella_contract(data, "shop"),
        package_toml.capabilities_root,
    ],
)
def test_each_pyproject_edit_is_a_no_op_once_applied(build: Any) -> None:
    once = package_toml.render(PYPROJECT, build(tomllib.loads(PYPROJECT)))

    assert build(tomllib.loads(once)) == []


def test_an_enablement_key_is_set_true_in_the_chosen_area_table() -> None:
    new_text = package_toml.render(BASE, package_toml.enablement_key(tomllib.loads(BASE), "workplace_utilities", "shop"))

    assert _comments(new_text) == _comments(BASE)
    assert tomllib.loads(new_text)["plugins"]["workplace_utilities"]["shop"] is True


def test_an_enablement_key_for_an_unknown_area_is_refused_naming_the_areas() -> None:
    with pytest.raises(TomlEditError, match="incident_response"):
        package_toml.enablement_key(tomllib.loads(BASE), "marketing", "shop")


def test_a_settings_table_is_added_once() -> None:
    new_text = package_toml.render(BASE, package_toml.settings_table(tomllib.loads(BASE), "shop"))

    assert tomllib.loads(new_text)["shop"] == {}
    assert package_toml.settings_table(tomllib.loads(new_text), "shop") == []


def test_plugin_areas_are_read_from_the_enablement_tables() -> None:
    assert set(package_toml.plugin_areas(tomllib.loads(BASE))) >= {
        "incident_response",
        "cloud_operations",
        "platform_access",
        "workplace_utilities",
    }


def test_verify_rejects_a_result_that_differs_from_the_intended_edits() -> None:
    edits = package_toml.independent_feature(tomllib.loads(PYPROJECT), "features.shop")
    tampered = package_toml.render(PYPROJECT, edits).replace('name = "sre-bot"', 'name = "other"', 1)

    with pytest.raises(TomlEditError, match="differs"):
        package_toml.verify(PYPROJECT, tampered, edits)


def test_renaming_an_entry_point_and_its_contract_strings_keeps_comments_and_other_contracts() -> None:
    def rename(text: str) -> str:
        return text.replace("features.incident.scribe", "features.incident.notes")

    data = tomllib.loads(PYPROJECT)
    edits = package_toml.rename_entry_point(data, "incident.scribe", "incident.notes", "features.incident.notes")
    edits += package_toml.rename_in_contracts(data, rename, keep=frozenset({"feature-independence"}))

    result = _render_pyproject(edits)

    group = result["project"]["entry-points"]["sre_bot"]
    assert "incident.scribe" not in group
    assert group["incident.notes"] == "features.incident.notes"
    assert "features.incident.notes" in _contract(result, "protected-plugins")["protected_modules"]
    assert "features.incident.notes.service -> integrations.openai" in _contract(result, "integrations-via-adapters")["ignore_imports"]
    assert _contract(result, "feature-independence") == _contract(data, "feature-independence")


def test_renaming_an_enablement_key_keeps_its_value_area_and_the_comments() -> None:
    edits = package_toml.rename_enablement_key(tomllib.loads(BASE), "geolocate", "geo.lookup")

    new_text = package_toml.render(BASE, edits)

    assert _comments(new_text) == _comments(BASE)
    keys = tomllib.loads(new_text)["plugins"]["workplace_utilities"]
    assert "geolocate" not in keys
    assert keys["geo.lookup"] is True
    assert package_toml.rename_enablement_key(tomllib.loads(BASE), "absent", "other") == []
