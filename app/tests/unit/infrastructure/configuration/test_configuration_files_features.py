"""Tests for the SRE ops and AWS ops tables in the checked-in configuration files.

Each environment's files are read with the real loader and the two feature slices are built
on them. base.toml declares every key empty; production.toml holds the Slack id and the AWS
admin group production ran on; local and ci hold none, because local shares the production
Slack workspace. Field names stay upper case until each package move, and a lower snake_case
key fills them through the slices' case-insensitive matching.
"""

import tomllib
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest

from contracts.configuration import ConfigurationError, install_configuration_files, uninstall_configuration_files
from infrastructure.configuration.features.aws_ops import AWSFeatureSettings
from infrastructure.configuration.features.sre_ops import SreOpsSettings
from server.configuration.loader import CONFIG_DIR, load_configuration_files

pytestmark = pytest.mark.unit

_SLICES = (SreOpsSettings, AWSFeatureSettings)
_FLAT_NAMES = (
    "SRE_OPS_CHANNEL_ID",
    "AWS_ADMIN_GROUPS",
    "AWS_OPS_GROUP_NAME",
)
_PREFIXED_NAMES = (
    "SRE_OPS__SRE_OPS_CHANNEL_ID",
    "CLOUD_OPERATIONS__AWS_ADMIN_GROUPS",
)


@dataclass(frozen=True)
class _Files:
    environment: str
    paths: tuple[Path, ...]


@pytest.fixture(autouse=True)
def _no_dotenv(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Build the slices from the files only, never a developer's .env or Codespaces variables."""
    for settings_class in _SLICES:
        monkeypatch.setitem(settings_class.model_config, "env_file", None)
    for name in (*_FLAT_NAMES, *_PREFIXED_NAMES):
        monkeypatch.delenv(name, raising=False)
    yield


def _table(environment: str, name: str) -> dict:
    path = CONFIG_DIR / f"{environment}.toml"
    return tomllib.loads(path.read_text(encoding="utf-8")).get(name, {}) if path.exists() else {}


def test_base_declares_each_feature_table_empty() -> None:
    assert _table("base", "sre_ops") == {"sre_ops_channel_id": ""}
    assert _table("base", "cloud_operations") == {"aws_admin_groups": []}


def test_production_resolves_the_values_production_ran_on() -> None:
    """The id is the blob line's value (deploy check 'features'); the admin group was the code default."""
    install_configuration_files(load_configuration_files("production"))

    assert SreOpsSettings().SRE_OPS_CHANNEL_ID == "C0388M21LKZ"
    assert AWSFeatureSettings().AWS_ADMIN_GROUPS == ["sre-ifs@cds-snc.ca"]


@pytest.mark.parametrize("environment", ["local", "ci"])
def test_local_and_ci_configure_no_feature_value(environment: str) -> None:
    """No production channel, group or admin address is a default where developers run the bot."""
    install_configuration_files(load_configuration_files(environment))

    assert SreOpsSettings().SRE_OPS_CHANNEL_ID == ""
    assert AWSFeatureSettings().AWS_ADMIN_GROUPS == []


@pytest.mark.parametrize("name", ["base", "production", "local", "ci"])
def test_no_file_has_a_groups_table(name: str) -> None:
    assert _table(name, "groups") == {}


def test_prefixed_environment_variables_beat_the_files(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SRE_OPS__SRE_OPS_CHANNEL_ID", "C0OPS")
    monkeypatch.setenv("CLOUD_OPERATIONS__AWS_ADMIN_GROUPS", '["admins@example.com"]')

    assert SreOpsSettings().SRE_OPS_CHANNEL_ID == "C0OPS"
    assert AWSFeatureSettings().AWS_ADMIN_GROUPS == ["admins@example.com"]


def test_former_flat_names_are_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in _FLAT_NAMES:
        monkeypatch.setenv(name, '["old@example.com"]' if name == "AWS_ADMIN_GROUPS" else "COLD")

    assert SreOpsSettings().SRE_OPS_CHANNEL_ID == ""
    assert AWSFeatureSettings().AWS_ADMIN_GROUPS == []


@pytest.mark.parametrize(
    ("table", "settings_class"),
    [("sre_ops", SreOpsSettings), ("cloud_operations", AWSFeatureSettings)],
)
def test_unknown_key_in_the_table_fails_naming_it(tmp_path: Path, table: str, settings_class: type) -> None:
    base = tmp_path / "base.toml"
    environment = tmp_path / "ci.toml"
    base.write_text(f"[{table}]\nnot_a_key = 1\n")
    environment.write_text("")
    install_configuration_files(_Files("ci", (base, environment)))

    with pytest.raises(ConfigurationError, match="not_a_key"):
        settings_class()


@pytest.mark.parametrize("settings_class", _SLICES)
def test_building_before_install_raises(settings_class: type) -> None:
    """A slice built before the configuration phase fails closed, which is why readers build at use."""
    uninstall_configuration_files()

    with pytest.raises(ConfigurationError):
        settings_class()
