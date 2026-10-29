"""Unit tests for the record of built slices in contracts.configuration.

Each test installs a base file into tmp_path and builds small slices declared
here. The record is process-wide state, so every installation starts it afresh:
the assertions read built_slices() after building, after a failed build and
after a second installation. The .env file is disabled on the test slices so the
developer's environment never leaks in.
"""

from dataclasses import dataclass
from pathlib import Path

import pytest
from pydantic_settings import SettingsConfigDict

from contracts.configuration import (
    ConfigurationError,
    ConfigurationSlice,
    built_slices,
    env_only,
    install_configuration_files,
    is_env_only,
    uninstall_configuration_files,
)

pytestmark = pytest.mark.unit


class _AlphaSettings(ConfigurationSlice):
    model_config = SettingsConfigDict(toml_table_header=("alpha",), env_prefix="ALPHA__", env_file=None)

    level: str = "INFO"
    count: int = 1


class _BetaSettings(ConfigurationSlice):
    model_config = SettingsConfigDict(toml_table_header=("beta",), env_prefix="BETA__", env_file=None)

    level: str = "INFO"
    hidden: str = env_only("A non-public value.", "local", default="")


@dataclass(frozen=True)
class _Files:
    environment: str
    paths: tuple[Path, ...]


def _install(tmp_path: Path, base: str = "[alpha]\n[beta]\n") -> None:
    base_path = tmp_path / "base.toml"
    base_path.write_text(base, encoding="utf-8")
    install_configuration_files(_Files(environment="ci", paths=(base_path,)))


def test_a_built_slice_is_recorded_with_its_values(tmp_path: Path) -> None:
    """The record holds the built instance itself, so the summary reads the validated values."""
    _install(tmp_path)

    alpha = _AlphaSettings(count=4)

    assert built_slices() == (alpha,)


def test_records_are_sorted_by_table(tmp_path: Path) -> None:
    """The order does not depend on the build order, so the summary and its hash are stable."""
    _install(tmp_path)

    beta = _BetaSettings()
    alpha = _AlphaSettings()

    assert built_slices() == (alpha, beta)


def test_a_slice_that_fails_to_build_is_not_recorded(tmp_path: Path) -> None:
    """Only a slice that validated is reported; a failed build leaves the record as it was."""
    _install(tmp_path)

    with pytest.raises(ConfigurationError):
        _AlphaSettings(count="not a number")  # type: ignore[arg-type]

    assert built_slices() == ()


def test_installing_files_starts_a_fresh_record(tmp_path: Path) -> None:
    """A later installation forgets what the previous one built, since those values read other files."""
    _install(tmp_path)
    _AlphaSettings()

    _install(tmp_path)

    assert built_slices() == ()


def test_a_second_build_of_a_class_replaces_its_record(tmp_path: Path) -> None:
    """One entry per slice class, holding the latest build."""
    _install(tmp_path)
    _AlphaSettings(count=1)

    latest = _AlphaSettings(count=2)

    assert built_slices() == (latest,)


def test_built_slices_is_empty_when_files_were_uninstalled(tmp_path: Path) -> None:
    """Uninstalling the files clears the record along with them."""
    _install(tmp_path)
    _AlphaSettings()

    uninstall_configuration_files()

    assert built_slices() == ()


def test_is_env_only_reads_the_field_metadata() -> None:
    """The helper is true for a field declared with env_only and false for a plain field."""
    assert is_env_only(_BetaSettings.model_fields["hidden"]) is True
    assert is_env_only(_BetaSettings.model_fields["level"]) is False
