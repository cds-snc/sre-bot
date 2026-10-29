"""Behavior tests for the scheduler settings slice on the [scheduler] table.

The slice is built on installed configuration files, either a base file
written under tmp_path or the checked-in files, with SCHEDULER__ variables
removed and the developer's .env ignored, so only the files and the variables a
test sets decide the values. The checked-in files are pinned because a wrong
production value silently stops every scheduled job.
"""

from pathlib import Path

import pytest

from contracts.configuration import ConfigurationError, install_configuration_files
from jobs.settings import SchedulerSettings, get_scheduler_settings
from server.configuration import load_configuration_files

pytestmark = pytest.mark.unit

_BASE = """
[scheduler]
enabled = false
default_tier2_lease_ttl_seconds = 1800
"""


@pytest.fixture(autouse=True)
def _no_scheduler_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    for field in ("ENABLED", "DEFAULT_TIER2_LEASE_TTL_SECONDS"):
        monkeypatch.delenv(f"SCHEDULER__{field}", raising=False)
    monkeypatch.setitem(SchedulerSettings.model_config, "env_file", None)


def _install(tmp_path: Path, base: str) -> None:
    (tmp_path / "base.toml").write_text(base, encoding="utf-8")
    (tmp_path / "ci.toml").write_text("", encoding="utf-8")
    install_configuration_files(load_configuration_files("ci", tmp_path))


def test_the_scheduler_table_sets_the_switch_and_the_lease_ttl(tmp_path: Path) -> None:
    _install(tmp_path, _BASE)

    settings = SchedulerSettings()

    assert settings.enabled is False
    assert settings.default_tier2_lease_ttl_seconds == 1800


def test_an_environment_variable_switches_the_scheduler_on(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _install(tmp_path, _BASE)
    monkeypatch.setenv("SCHEDULER__ENABLED", "true")

    assert SchedulerSettings().enabled is True


def test_an_unknown_scheduler_key_fails_naming_it(tmp_path: Path) -> None:
    _install(tmp_path, _BASE + "jobs = 3\n")

    with pytest.raises(ConfigurationError, match="jobs"):
        SchedulerSettings()


@pytest.mark.parametrize(("environment", "enabled"), [("production", True), ("local", False), ("ci", False)])
def test_configuration_files_run_scheduled_jobs_in_production_only(environment: str, enabled: bool) -> None:
    install_configuration_files(load_configuration_files(environment))

    assert SchedulerSettings().enabled is enabled


def test_get_scheduler_settings_returns_one_instance() -> None:
    get_scheduler_settings.cache_clear()

    assert get_scheduler_settings() is get_scheduler_settings()
