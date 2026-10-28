"""Tests for the hosting tables in the checked-in configuration files.

Each environment's files are read with the real loader and the hosting slices are built on
them. [directory] holds require_startup_warmup alone; no file has a [drive] or [spreadsheets]
table or a provider key, because the vendor is the Google adapter and never a setting. [audit]
and [coordination] hold the table names terraform creates and today's TTLs, and every
environment keeps them.
"""

import tomllib
from collections.abc import Iterator

import pytest

from contracts.configuration import install_configuration_files
from infrastructure.audit.settings import AuditSettings
from infrastructure.coordination.settings import ConditionalWriteSettings
from infrastructure.directory.settings import DirectorySettings
from server.configuration.loader import CONFIG_DIR, load_configuration_files

pytestmark = pytest.mark.unit

_ENVIRONMENTS = ("production", "local", "ci")


@pytest.fixture(autouse=True)
def _no_dotenv(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Build the slice from the files only, never a developer's .env or Codespaces variables."""
    for settings_class in (DirectorySettings, AuditSettings, ConditionalWriteSettings):
        monkeypatch.setitem(settings_class.model_config, "env_file", None)
    for name in (
        "DIRECTORY__REQUIRE_STARTUP_WARMUP",
        "AUDIT__TABLE_NAME",
        "COORDINATION__TABLE_NAME",
        "COORDINATION__RECORD_TTL_SECONDS",
        "COORDINATION__IN_PROGRESS_TTL_SECONDS",
    ):
        monkeypatch.delenv(name, raising=False)
    yield


@pytest.mark.parametrize("environment", _ENVIRONMENTS)
def test_each_environment_builds_the_directory_slice_without_warmup(environment: str) -> None:
    install_configuration_files(load_configuration_files(environment))

    assert DirectorySettings().require_startup_warmup is False


def test_directory_table_holds_only_require_startup_warmup() -> None:
    base = tomllib.loads((CONFIG_DIR / "base.toml").read_text(encoding="utf-8"))

    assert base["directory"] == {"require_startup_warmup": False}


@pytest.mark.parametrize("name", ["base", *_ENVIRONMENTS])
def test_no_file_has_a_drive_or_spreadsheets_table_or_a_provider_key(name: str) -> None:
    path = CONFIG_DIR / f"{name}.toml"
    data = tomllib.loads(path.read_text(encoding="utf-8")) if path.exists() else {}

    assert "drive" not in data
    assert "spreadsheets" not in data
    assert "provider" not in data.get("directory", {})


def test_audit_and_coordination_tables_hold_the_terraform_names_and_ttls() -> None:
    base = tomllib.loads((CONFIG_DIR / "base.toml").read_text(encoding="utf-8"))

    assert base["audit"] == {"table_name": "sre_bot_audit_trail"}
    assert base["coordination"] == {
        "table_name": "sre_bot_idempotency",
        "record_ttl_seconds": 3600,
        "in_progress_ttl_seconds": 300,
    }


@pytest.mark.parametrize("environment", _ENVIRONMENTS)
def test_each_environment_builds_the_audit_and_coordination_slices(environment: str) -> None:
    install_configuration_files(load_configuration_files(environment))

    assert AuditSettings().table_name == "sre_bot_audit_trail"
    assert ConditionalWriteSettings().table_name == "sre_bot_idempotency"
