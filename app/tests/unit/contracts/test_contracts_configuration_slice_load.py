"""Unit tests for the settings-slice base in contracts.configuration.

Each test writes a base and an environment file into tmp_path, installs them
through install_configuration_files and builds a small slice declared here, so
only the contract is exercised: no server loader, no app/config files. The
.env file is disabled on the test slice so the developer's environment never
leaks in. Assertions read the built values or the ConfigurationError message,
which must name the file, the table and the key a maintainer has to fix.
"""

from dataclasses import dataclass
from pathlib import Path

import pytest
from pydantic_settings import SettingsConfigDict

from contracts.configuration import (
    ConfigurationError,
    ConfigurationSlice,
    install_configuration_files,
    uninstall_configuration_files,
)

pytestmark = pytest.mark.unit


class _ToolSettings(ConfigurationSlice):
    model_config = SettingsConfigDict(toml_table_header=("tool",), env_prefix="TOOL__", env_file=None)

    level: str = "INFO"
    names: tuple[str, ...] = ()
    retries: int = 3


@dataclass(frozen=True)
class _Files:
    environment: str
    paths: tuple[Path, ...]


def _install(tmp_path: Path, base: str, environment: str = "") -> tuple[Path, Path]:
    base_path = tmp_path / "base.toml"
    environment_path = tmp_path / "ci.toml"
    base_path.write_text(base, encoding="utf-8")
    environment_path.write_text(environment, encoding="utf-8")
    install_configuration_files(_Files(environment="ci", paths=(base_path, environment_path)))
    return base_path, environment_path


def test_environment_file_overrides_base_key_by_key(tmp_path: Path) -> None:
    """The environment file replaces only the keys it sets; the base file keeps the others."""
    _install(tmp_path, '[tool]\nlevel = "INFO"\nnames = ["a"]\n', '[tool]\nlevel = "DEBUG"\n')

    settings = _ToolSettings()

    assert settings.level == "DEBUG"
    assert settings.names == ("a",)


def test_environment_variable_overrides_file_value(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An upper-case <TABLE>__<FIELD> variable beats both files."""
    _install(tmp_path, '[tool]\nlevel = "INFO"\n', '[tool]\nlevel = "DEBUG"\n')
    monkeypatch.setenv("TOOL__LEVEL", "WARNING")

    assert _ToolSettings().level == "WARNING"


def test_file_value_overrides_code_default(tmp_path: Path) -> None:
    """A key in the base file beats the field default; an unset key keeps its default."""
    _install(tmp_path, "[tool]\nretries = 5\n")

    settings = _ToolSettings()

    assert settings.retries == 5
    assert settings.level == "INFO"


def test_dotenv_keys_of_other_slices_are_ignored_and_own_keys_read(tmp_path: Path) -> None:
    """extra=forbid guards the slice's table; the shared .env file holds every slice's names."""
    _install(tmp_path, '[tool]\nlevel = "INFO"\n')
    dotenv = tmp_path / ".env"
    dotenv.write_text("SLACK_BOT_TOKEN=xoxb-other-slice\nTOOL__LEVEL=ERROR\n", encoding="utf-8")

    assert _ToolSettings(_env_file=dotenv).level == "ERROR"


def test_slice_built_before_files_are_installed_fails_naming_the_slice() -> None:
    """With nothing installed, building a slice fails instead of silently using defaults."""
    uninstall_configuration_files()

    with pytest.raises(ConfigurationError, match="_ToolSettings"):
        _ToolSettings()


def test_unknown_key_fails_naming_file_table_and_key(tmp_path: Path) -> None:
    """A misspelled key in the environment file names that file, the table and the key."""
    _, environment_path = _install(tmp_path, '[tool]\nlevel = "INFO"\n', '[tool]\nlevle = "DEBUG"\n')

    with pytest.raises(ConfigurationError) as raised:
        _ToolSettings()

    message = str(raised.value)
    assert str(environment_path) in message
    assert "[tool]" in message
    assert "levle" in message


def test_bad_type_in_file_fails_naming_file_table_and_key(tmp_path: Path) -> None:
    """A wrongly typed value names the file that set it, the table and the key."""
    base_path, _ = _install(tmp_path, '[tool]\nretries = "many"\n')

    with pytest.raises(ConfigurationError) as raised:
        _ToolSettings()

    message = str(raised.value)
    assert str(base_path) in message
    assert "[tool]" in message
    assert "retries" in message


def test_table_missing_from_base_file_fails_naming_base_and_table(tmp_path: Path) -> None:
    """The base file holds every slice's table; a missing one fails instead of a bare KeyError."""
    base_path, _ = _install(tmp_path, "[other]\nx = 1\n", '[tool]\nlevel = "DEBUG"\n')

    with pytest.raises(ConfigurationError) as raised:
        _ToolSettings()

    assert str(base_path) in str(raised.value)
    assert "[tool]" in str(raised.value)


def test_slice_whose_prefix_does_not_match_its_table_is_rejected() -> None:
    """The environment prefix mirrors the table name, so a mismatch fails at class creation."""
    with pytest.raises(TypeError, match="TOOL__"):

        class _Mismatched(ConfigurationSlice):
            model_config = SettingsConfigDict(toml_table_header=("tool",), env_prefix="TOOLS__")


def test_slice_without_a_table_is_rejected() -> None:
    """Every slice names exactly one table."""
    with pytest.raises(TypeError, match="toml_table_header"):

        class _Tableless(ConfigurationSlice):
            model_config = SettingsConfigDict(env_prefix="TOOL__")
