"""Unit tests for the [talent] slice: the hiring folder and template ids, non-public values.

Settings are built from the checked-in configuration files the test run installs and
from the environment with monkeypatch; nothing is stubbed. Each id is declared empty in
base.toml, held by no environment file, read only from TALENT__<FIELD>, and kept out of
the repr; an unknown key fails naming it.
"""

import tomllib
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest

from contracts.configuration import ConfigurationError, install_configuration_files, uninstall_configuration_files
from features.talent.settings import TalentSettings, get_talent_settings
from server.configuration.loader import CONFIG_DIR

pytestmark = pytest.mark.unit

_FIELDS = (
    "internal_folder_id",
    "templates_folder_id",
    "scoring_guide_template_id",
    "core_values_interview_notes_id",
    "technical_interview_notes_id",
    "intake_form_template_id",
    "phone_screen_template_id",
    "recruitment_feedback_template_id",
    "panelist_guidebook_template_id",
)


@dataclass(frozen=True)
class _Files:
    environment: str
    paths: tuple[Path, ...]


@pytest.fixture(autouse=True)
def _isolated(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setitem(TalentSettings.model_config, "env_file", None)
    get_talent_settings.cache_clear()
    yield
    get_talent_settings.cache_clear()


def test_base_declares_every_id_empty() -> None:
    base = tomllib.loads((CONFIG_DIR / "base.toml").read_text(encoding="utf-8"))

    assert base["talent"] == dict.fromkeys(_FIELDS, "")


@pytest.mark.parametrize("environment", ["ci", "local", "production"])
def test_no_environment_file_holds_an_id(environment: str) -> None:
    values = tomllib.loads((CONFIG_DIR / f"{environment}.toml").read_text(encoding="utf-8"))

    assert "talent" not in values


@pytest.mark.parametrize("field", _FIELDS)
def test_an_id_is_empty_by_default_and_read_from_the_environment(monkeypatch: pytest.MonkeyPatch, field: str) -> None:
    """An empty id does not fail the slice; the legacy reader fails at first use instead."""
    assert getattr(TalentSettings(), field) == ""

    monkeypatch.setenv(f"TALENT__{field.upper()}", "id-from-env")

    assert getattr(TalentSettings(), field) == "id-from-env"


def test_an_id_never_appears_in_the_repr(monkeypatch: pytest.MonkeyPatch) -> None:
    for field in _FIELDS:
        monkeypatch.setenv(f"TALENT__{field.upper()}", f"value-of-{field}")

    rendered = repr(TalentSettings())

    assert not [field for field in _FIELDS if f"value-of-{field}" in rendered]


def test_an_unknown_key_in_the_table_fails_naming_it(tmp_path: Path) -> None:
    base = tmp_path / "base.toml"
    environment = tmp_path / "ci.toml"
    base.write_text('[talent]\nunknown_id = "x"\n')
    environment.write_text("")
    install_configuration_files(_Files("ci", (base, environment)))

    with pytest.raises(ConfigurationError, match="unknown_id"):
        TalentSettings()


def test_building_before_install_raises() -> None:
    uninstall_configuration_files()

    with pytest.raises(ConfigurationError):
        TalentSettings()


def test_the_provider_returns_one_cached_instance() -> None:
    assert get_talent_settings() is get_talent_settings()
