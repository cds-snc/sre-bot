"""Unit tests for loading the AI writing capability's slice from the [ai_writing] table.

Each test installs a base and a local file from tmp_path (``install_openai_files``) with every
OPENAI_* and AI_WRITING_* variable removed and the .env files disabled (the package conftest), so
it observes only the values it writes and sets.
"""

from pathlib import Path

import pytest

from capabilities.ai_writing.settings import AIWritingSettings, get_ai_writing_settings
from contracts.configuration import ConfigurationError, ConfigurationSlice
from tests.unit.capabilities.ai_writing.conftest import install_openai_files

pytestmark = pytest.mark.unit


def test_the_slice_reads_the_ai_writing_table() -> None:
    config = AIWritingSettings.model_config

    assert issubclass(AIWritingSettings, ConfigurationSlice)
    assert (config.get("toml_table_header"), config.get("env_prefix"), config.get("extra")) == (
        ("ai_writing",),
        "AI_WRITING__",
        "forbid",
    )


def test_the_model_is_unset_by_default(tmp_path: Path) -> None:
    """The model is the organisation's value, so the framework sets none."""
    install_openai_files(tmp_path, base="[ai_writing]\n")

    assert AIWritingSettings().model == ""


def test_the_model_comes_from_the_environment_file(tmp_path: Path) -> None:
    install_openai_files(tmp_path, base='[ai_writing]\nmodel = ""\n', environment='[ai_writing]\nmodel = "gpt-test"\n')

    assert AIWritingSettings().model == "gpt-test"


def test_the_environment_overrides_the_model(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    install_openai_files(tmp_path, base="[ai_writing]\n", environment='[ai_writing]\nmodel = "gpt-test"\n')
    monkeypatch.setenv("AI_WRITING__MODEL", "gpt-override")

    assert AIWritingSettings().model == "gpt-override"


def test_an_unknown_key_fails_naming_it(tmp_path: Path) -> None:
    install_openai_files(tmp_path, base="[ai_writing]\nmax_output_tokens = 3000\n")

    with pytest.raises(ConfigurationError, match="max_output_tokens"):
        AIWritingSettings()


def test_get_ai_writing_settings_is_cached(tmp_path: Path) -> None:
    install_openai_files(tmp_path, base="[ai_writing]\n")

    assert get_ai_writing_settings() is get_ai_writing_settings()
