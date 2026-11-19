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
lease_hold_margin_seconds = 5
"""


@pytest.fixture(autouse=True)
def _no_scheduler_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    for field in ("ENABLED", "DEFAULT_TIER2_LEASE_TTL_SECONDS", "LEASE_HOLD_MARGIN_SECONDS"):
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


def test_the_scheduler_table_sets_the_lease_hold_margin(tmp_path: Path) -> None:
    _install(tmp_path, _BASE.replace("lease_hold_margin_seconds = 5", "lease_hold_margin_seconds = 12"))

    assert SchedulerSettings().lease_hold_margin_seconds == 12


def test_a_negative_lease_hold_margin_is_rejected(tmp_path: Path) -> None:
    _install(tmp_path, _BASE.replace("lease_hold_margin_seconds = 5", "lease_hold_margin_seconds = -1"))

    with pytest.raises(ConfigurationError, match="lease_hold_margin_seconds"):
        SchedulerSettings()


@pytest.mark.parametrize("environment", ["production", "local", "ci"])
def test_configuration_files_hold_a_lease_until_five_seconds_before_the_next_tick(environment: str) -> None:
    """The checked-in margin is pinned: the hold derived from it must stay under the interval."""
    install_configuration_files(load_configuration_files(environment))

    assert SchedulerSettings().lease_hold_margin_seconds == 5


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
