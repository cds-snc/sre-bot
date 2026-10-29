"""Unit tests for the configuration summary builder in server.configuration.summary.

The builder is a pure function of built slices, so the tests declare small
slices here, install a base file into tmp_path and build them; no host loader
runs and no log pipeline is involved. Assertions read the per-slice sections the
summary would log and its config_hash. Canary values stand in for credentials and
non-public identifiers: a credential must never appear in any section or in the
hash input, and a non-public value only as its last four characters.
"""

import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel, SecretBytes, SecretStr
from pydantic_settings import SettingsConfigDict

from contracts.configuration import (
    ConfigurationSlice,
    built_slices,
    env_only,
    install_configuration_files,
    installed_configuration_files,
)
from server.configuration.summary import summarize

pytestmark = pytest.mark.unit

CREDENTIAL = "xoxb-canary-credential-0001"
NON_PUBLIC = "1AbCdEfGhIjKlMnOpQrStUvWxYz"


class _Mode(StrEnum):
    FAST = "fast"


class _Entry(BaseModel):
    audience: str = ""
    private_id: str = env_only("A non-public id.", "local", default="")


class _DemoSettings(ConfigurationSlice):
    model_config = SettingsConfigDict(toml_table_header=("demo",), env_prefix="DEMO__", env_file=None)

    unauthorized_errors: int = 3
    mode: _Mode = _Mode.FAST
    names: tuple[str, ...] = ("a", "b")
    entries: list[_Entry] = []
    tenant: _Entry | None = None
    credential: SecretStr = env_only("A credential.", "local", default=SecretStr(""))
    blob: SecretBytes | None = env_only("A binary credential.", "local", default=None)
    folder_id: str = env_only("A non-public id.", "local", default="")
    short_id: str = env_only("A short non-public id.", "local", default="")
    ratio: float = float("nan")
    limits: dict[str, int] = {}


class _OtherSettings(ConfigurationSlice):
    model_config = SettingsConfigDict(toml_table_header=("other",), env_prefix="OTHER__", env_file=None)

    level: str = "INFO"


@dataclass(frozen=True)
class _Files:
    environment: str
    paths: tuple[Path, ...]


@pytest.fixture(autouse=True)
def _installed(tmp_path: Path) -> None:
    base = tmp_path / "base.toml"
    base.write_text("[demo]\n[other]\n", encoding="utf-8")
    install_configuration_files(_Files(environment="ci", paths=(base,)))


def _demo(**values: Any) -> dict[str, Any]:
    _DemoSettings(**values)
    return summarize(built_slices()).sections()["demo"]


def test_every_built_slice_is_present_without_a_hand_kept_list() -> None:
    """A slice class declared in the test and built appears; the builder names no slice."""
    _DemoSettings()
    _OtherSettings()

    tables = {entry.table for entry in summarize(built_slices()).entries}

    assert tables == {"demo", "other"}


def test_a_slice_is_one_section_keyed_by_its_table() -> None:
    """Shown fields sit under values, keyed by field name, and the table is not repeated per field."""
    section = _demo()

    assert section["values"]["unauthorized_errors"] == 3
    assert "slice" not in section


def test_a_list_of_plain_values_stays_one_value_and_models_get_dotted_names() -> None:
    """Enums show their value; a list of plain values is one value; nested models recurse into dotted names."""
    values = _demo(entries=[{"audience": "aud-1", "private_id": NON_PUBLIC}])["values"]

    assert values["mode"] == "fast"
    assert values["names"] == ["a", "b"]
    assert values["entries.0.audience"] == "aud-1"
    assert values["tenant"] is None


def test_a_credential_shows_state_only_and_is_never_read() -> None:
    """A SecretStr or SecretBytes value yields set/unset by truthiness, with no value and no tail."""
    section = _demo(credential=SecretStr(CREDENTIAL), blob=SecretBytes(b"abcdefghijklmnop"))

    assert {"credential", "blob"} <= set(section["set"])
    assert "credential" not in section["values"]
    assert "credential" not in section.get("partial", {})


def test_an_empty_or_absent_credential_is_unset() -> None:
    """Empty means unset for a SecretStr, and an absent optional one is unset too."""
    section = _demo()

    assert {"credential", "blob"} <= set(section["unset"])


def test_a_long_non_public_value_shows_state_and_its_last_four_characters() -> None:
    """An env_only plain str of twelve or more characters carries only its tail."""
    section = _demo(folder_id=NON_PUBLIC)

    assert section["partial"]["folder_id"] == NON_PUBLIC[-4:]
    assert "folder_id" not in section.get("set", [])


def test_a_short_non_public_value_shows_state_only() -> None:
    """Under twelve characters the tail would be a large part of the value, so none is shown."""
    section = _demo(short_id="abc123")

    assert "short_id" in section["set"]
    assert "short_id" not in section.get("partial", {})


def test_a_non_public_value_inside_a_nested_entry_is_withheld() -> None:
    """env_only metadata on a nested model field withholds that leaf, with the dotted name."""
    section = _demo(entries=[{"private_id": NON_PUBLIC}])

    assert section["partial"]["entries.0.private_id"] == NON_PUBLIC[-4:]


def test_the_serialised_summary_holds_no_credential_and_no_full_non_public_value() -> None:
    """Nothing in the sections or the hash input carries more than the tail."""
    _DemoSettings(credential=SecretStr(CREDENTIAL), folder_id=NON_PUBLIC)

    summary = summarize(built_slices())
    rendered = json.dumps(summary.sections()) + summary.config_hash

    assert CREDENTIAL not in rendered
    assert NON_PUBLIC not in rendered
    assert NON_PUBLIC[-4:] in rendered


def test_an_odd_value_does_not_raise_and_stays_json_serialisable() -> None:
    """A non-finite float and an empty mapping are summarised without error."""
    values = _demo()["values"]

    assert values["ratio"] == "nan"
    assert values["limits"] == {}
    json.dumps(summarize(built_slices()).sections(), allow_nan=False)


def test_the_hash_is_stable_and_ignores_slice_build_order() -> None:
    """The same shown values hash the same however the slices were built."""
    _DemoSettings()
    _OtherSettings()
    first = summarize(built_slices()).config_hash
    install_configuration_files(installed_configuration_files())
    _OtherSettings()
    _DemoSettings()

    assert summarize(built_slices()).config_hash == first


def test_the_hash_changes_with_a_shown_value() -> None:
    """A different non-secret value changes the hash, so drift between replicas shows."""
    _DemoSettings(unauthorized_errors=3)
    before = summarize(built_slices()).config_hash
    _DemoSettings(unauthorized_errors=4)

    assert summarize(built_slices()).config_hash != before


def test_the_hash_ignores_credentials_and_non_public_values() -> None:
    """Withheld values, tails included, never feed the hash."""
    _DemoSettings(credential=SecretStr("first-credential-value"), folder_id="first-non-public-0001")
    before = summarize(built_slices()).config_hash
    _DemoSettings(credential=SecretStr("other-credential-value"), folder_id="other-non-public-9999")

    assert summarize(built_slices()).config_hash == before


def test_an_empty_summary_has_a_hash() -> None:
    """Nothing built is a valid summary, not an error."""
    summary = summarize(())

    assert summary.entries == ()
    assert len(summary.config_hash) == 64
