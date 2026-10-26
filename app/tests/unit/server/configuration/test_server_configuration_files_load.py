"""Unit tests for the configuration-file loader in server.configuration.

Each test writes base.toml and ci.toml into tmp_path and calls
load_configuration_files with that directory, so no app/config file is read.
pydantic-settings alone skips a missing file, reports malformed TOML without
the file name, crashes on a non-table value and ignores an upper-case key; the
loader turns each into a ConfigurationError whose message names the file (and
the table and key where there is one), which the assertions check.
"""

from pathlib import Path

import pytest

from contracts.configuration import ConfigurationError
from server.configuration import load_configuration_files

pytestmark = pytest.mark.unit


def _write(directory: Path, base: str | None, environment: str | None) -> None:
    if base is not None:
        (directory / "base.toml").write_text(base, encoding="utf-8")
    if environment is not None:
        (directory / "ci.toml").write_text(environment, encoding="utf-8")


def test_valid_files_load_base_first_then_the_environment_file(tmp_path: Path) -> None:
    """The file list is the base file followed by the one named after ENVIRONMENT."""
    _write(tmp_path, '[logging]\nlog_level = "INFO"\n', "")

    files = load_configuration_files("ci", tmp_path)

    assert files.environment == "ci"
    assert files.paths == (tmp_path / "base.toml", tmp_path / "ci.toml")


@pytest.mark.parametrize(("base", "environment", "missing"), [(None, "", "base.toml"), ("", None, "ci.toml")])
def test_missing_file_fails_naming_it(tmp_path: Path, base: str | None, environment: str | None, missing: str) -> None:
    """Both files must exist; the error names the absent one."""
    _write(tmp_path, base, environment)

    with pytest.raises(ConfigurationError, match=missing):
        load_configuration_files("ci", tmp_path)


def test_malformed_toml_fails_naming_file_and_line(tmp_path: Path) -> None:
    """A parse error names the file and keeps tomllib's line and column."""
    _write(tmp_path, "", "[logging\n")

    with pytest.raises(ConfigurationError) as raised:
        load_configuration_files("ci", tmp_path)

    assert str(tmp_path / "ci.toml") in str(raised.value)
    assert "line 1" in str(raised.value)


def test_top_level_value_that_is_not_a_table_fails_naming_file_and_key(tmp_path: Path) -> None:
    """Every top-level entry is a slice's table; a bare value fails."""
    _write(tmp_path, "logging = 3\n", "")

    with pytest.raises(ConfigurationError) as raised:
        load_configuration_files("ci", tmp_path)

    assert str(tmp_path / "base.toml") in str(raised.value)
    assert "logging" in str(raised.value)


@pytest.mark.parametrize("document", ['[logging]\nLOG_LEVEL = "DEBUG"\n', '[Logging]\nlog_level = "DEBUG"\n'])
def test_key_that_is_not_lower_snake_case_fails_naming_file_table_and_key(tmp_path: Path, document: str) -> None:
    """pydantic-settings silently ignores an upper-case key, so the loader rejects it."""
    _write(tmp_path, "", document)

    with pytest.raises(ConfigurationError) as raised:
        load_configuration_files("ci", tmp_path)

    message = str(raised.value)
    assert str(tmp_path / "ci.toml") in message
    assert "LOG_LEVEL" in message or "Logging" in message


def test_nested_table_keys_are_checked(tmp_path: Path) -> None:
    """The lower-case rule applies inside nested tables, which is where tenant entries live."""
    _write(tmp_path, '[slack.tenant]\nTeam_Id = "T1"\n', "")

    with pytest.raises(ConfigurationError, match=r"\[slack\.tenant\] Team_Id"):
        load_configuration_files("ci", tmp_path)


def test_a_quoted_dotted_key_of_lower_snake_case_segments_loads(tmp_path: Path) -> None:
    """Plugin enablement keys are entry-point names, such as "incident.comms"; each segment is lower snake_case."""
    _write(tmp_path, '[plugins.incident_response]\n"incident.comms" = true\noncall_sync = true\n', "")

    load_configuration_files("ci", tmp_path)


@pytest.mark.parametrize(
    "key", ['"Incident.comms"', '"incident.Comms"', '"incident..comms"', '"incident.comms."', '"incident.1comms"']
)
def test_a_dotted_key_with_a_segment_that_is_not_lower_snake_case_fails_naming_it(tmp_path: Path, key: str) -> None:
    _write(tmp_path, f"[plugins.incident_response]\n{key} = true\n", "")

    with pytest.raises(ConfigurationError, match=r"\[plugins\.incident_response\]"):
        load_configuration_files("ci", tmp_path)
