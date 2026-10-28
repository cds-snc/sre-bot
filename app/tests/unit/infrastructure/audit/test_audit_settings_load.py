"""Unit tests for loading the audit slice from the [audit] table and the provider wiring.

Each test installs a base and a local file from tmp_path with every AUDIT variable removed and the
.env file disabled (the autouse isolation fixture), so it observes only the values it writes and
sets. table_name is the slice's only key; the retired AUDIT_TABLE_NAME is never read, and an
unknown key fails the load naming it. The provider-built service runs over the in-memory record
store, so its write is observed in the configured table.
"""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest

from contracts.configuration import ConfigurationError, ConfigurationSlice, install_configuration_files
from contracts.records import RecordQuery
from infrastructure.audit import service as audit_service
from infrastructure.audit.models import AuditEvent
from infrastructure.audit.settings import AuditSettings, get_audit_settings
from infrastructure.records.in_memory import InMemoryRecordStore
from server.configuration.loader import CONFIG_DIR, TomlConfigurationFiles

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _audit_env_isolation(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Remove AUDIT variables, disable the .env file and clear the cached providers."""
    monkeypatch.setitem(AuditSettings.model_config, "env_file", None)
    for key in tuple(os.environ):
        if key.upper().startswith("AUDIT_"):
            monkeypatch.delenv(key, raising=False)
    get_audit_settings.cache_clear()
    audit_service.get_audit_trail_service.cache_clear()
    yield
    get_audit_settings.cache_clear()
    audit_service.get_audit_trail_service.cache_clear()


def _install(tmp_path: Path, base: str = "[audit]\n", environment: str = "") -> None:
    (tmp_path / "base.toml").write_text(base, encoding="utf-8")
    (tmp_path / "local.toml").write_text(environment, encoding="utf-8")
    install_configuration_files(
        TomlConfigurationFiles(environment="local", paths=(tmp_path / "base.toml", tmp_path / "local.toml"))
    )


def test_audit_settings_is_a_slice_on_the_audit_table() -> None:
    """The slice reads [audit] with the AUDIT__ prefix and rejects unknown keys."""
    config = AuditSettings.model_config

    assert issubclass(AuditSettings, ConfigurationSlice)
    assert config.get("toml_table_header") == ("audit",)
    assert config.get("env_prefix") == "AUDIT__"
    assert config.get("extra") == "forbid"


def test_table_name_is_the_only_key() -> None:
    assert tuple(AuditSettings.model_fields) == ("table_name",)


def test_the_default_is_the_terraform_table(tmp_path: Path) -> None:
    _install(tmp_path)

    assert AuditSettings().table_name == "sre_bot_audit_trail"


def test_the_checked_in_base_file_sets_the_default() -> None:
    install_configuration_files(TomlConfigurationFiles(environment="ci", paths=(CONFIG_DIR / "base.toml",)))

    assert AuditSettings().table_name == "sre_bot_audit_trail"


def test_a_file_sets_the_table_name(tmp_path: Path) -> None:
    _install(tmp_path, environment='[audit]\ntable_name = "audit_elsewhere"\n')

    assert AuditSettings().table_name == "audit_elsewhere"


def test_the_prefixed_environment_name_overrides_the_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _install(tmp_path, base='[audit]\ntable_name = "from_file"\n')
    monkeypatch.setenv("AUDIT__TABLE_NAME", "from_env")

    assert AuditSettings().table_name == "from_env"


@pytest.mark.parametrize("key", ["audit_table_name", "table"])
def test_an_unknown_key_in_a_file_fails_the_load_naming_it(tmp_path: Path, key: str) -> None:
    """The former field name is an unknown key too, so a stale file cannot set it silently."""
    _install(tmp_path, base=f'[audit]\n{key} = "x"\n')

    with pytest.raises(ConfigurationError, match=key):
        AuditSettings()


def test_the_retired_flat_name_is_not_read(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _install(tmp_path)
    monkeypatch.setenv("AUDIT_TABLE_NAME", "retired")

    assert AuditSettings().table_name == "sre_bot_audit_trail"


def test_the_provider_is_cached() -> None:
    assert get_audit_settings() is get_audit_settings()


def test_provider_built_service_writes_to_configured_table(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = InMemoryRecordStore()
    _install(tmp_path, environment='[audit]\ntable_name = "audit_elsewhere"\n')
    monkeypatch.setattr(audit_service, "get_record_store", lambda: store)

    audit_service.get_audit_trail_service().write_audit_event(
        AuditEvent(
            correlation_id="c1",
            timestamp="2026-01-01T00:00:00+00:00",
            action="group_member_added",
            user_email="alice@example.com",
            result="success",
            resource_id="eng@example.com",
        )
    )

    written = store.query(audit_service.audit_table("audit_elsewhere"), RecordQuery(partition="eng@example.com"))
    assert [item["correlation_id"] for item in written.data] == ["c1"]
