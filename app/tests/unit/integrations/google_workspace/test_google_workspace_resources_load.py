"""Unit tests for loading GOOGLE_RESOURCES, the Google document and folder ids of the features.

Settings are built from monkeypatched environment variables with the .env file
disabled. The single JSON variable is keyed by domain, and each property reads
one id from it; a missing id reads as an empty string. The provider is a cached
singleton.
"""

import pytest
from pydantic import ValidationError
from pydantic_settings import SettingsError

from integrations.google_workspace.settings import GoogleResourcesConfig, get_google_resources_config

pytestmark = pytest.mark.unit


def test_provider_returns_one_cached_instance() -> None:
    """Every caller shares one parsed configuration."""
    get_google_resources_config.cache_clear()

    assert get_google_resources_config() is get_google_resources_config()


def test_config_reads_the_env_file_case_insensitively_and_ignores_unknown_keys() -> None:
    """The configuration reads the .env file, matches names in any case and ignores unknown keys."""
    config = GoogleResourcesConfig.model_config

    assert (config.get("env_file"), config.get("case_sensitive"), config.get("extra")) == (".env", False, "ignore")


def test_properties_read_their_ids_from_the_json_variable(monkeypatch: pytest.MonkeyPatch) -> None:
    """Each domain key maps to its property."""
    monkeypatch.setenv(
        "GOOGLE_RESOURCES",
        '{"inc": {"d": "drive", "t": "template"}, "tal": {"pan": "guidebook"}, "aws": {"s": "sheet"}, "cal": {"sre": "calendar"}}',
    )

    config = GoogleResourcesConfig(_env_file=None)  # type: ignore[call-arg]

    assert (
        config.incident_drive_id,
        config.incident_template_id,
        config.panelist_guidebook_template_id,
        config.spending_sheet_id,
        config.sre_calendar_id,
    ) == ("drive", "template", "guidebook", "sheet", "calendar")


def test_a_missing_id_reads_as_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    """Unset domains and keys read as an empty string rather than failing."""
    monkeypatch.setenv("GOOGLE_RESOURCES", '{"inc": {"d": "drive"}}')

    config = GoogleResourcesConfig(_env_file=None)  # type: ignore[call-arg]

    assert (config.incident_folder_id, config.spending_sheet_id) == ("", "")


def test_an_unset_variable_reads_every_id_as_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without GOOGLE_RESOURCES the configuration still builds."""
    monkeypatch.delenv("GOOGLE_RESOURCES", raising=False)

    assert GoogleResourcesConfig(_env_file=None).incident_drive_id == ""  # type: ignore[call-arg]


def test_a_mapping_passed_directly_is_kept() -> None:
    """Values given by name, not from the environment, are accepted as a mapping."""
    config = GoogleResourcesConfig.model_validate({"GOOGLE_RESOURCES": {"aws": {"s": "sheet"}}})

    assert config.spending_sheet_id == "sheet"


def test_a_quoted_json_string_passed_directly_is_unwrapped() -> None:
    """Outer quotes left by shell or parameter-store quoting are stripped before parsing."""
    config = GoogleResourcesConfig.model_validate({"GOOGLE_RESOURCES": '\'{"inc": {"h": "handbook"}}\''})

    assert config.incident_handbook_id == "handbook"


def test_a_json_list_fails_naming_the_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """A JSON value that is not an object is rejected at load."""
    monkeypatch.setenv("GOOGLE_RESOURCES", "[1, 2]")

    with pytest.raises(ValidationError, match="GOOGLE_RESOURCES"):
        GoogleResourcesConfig(_env_file=None)  # type: ignore[call-arg]


def test_malformed_json_fails_naming_the_field(monkeypatch: pytest.MonkeyPatch) -> None:
    """pydantic-settings decodes the variable before validation, so malformed JSON fails there naming the field."""
    monkeypatch.setenv("GOOGLE_RESOURCES", "not json")

    with pytest.raises(SettingsError, match='field "resources"'):
        GoogleResourcesConfig(_env_file=None)  # type: ignore[call-arg]
