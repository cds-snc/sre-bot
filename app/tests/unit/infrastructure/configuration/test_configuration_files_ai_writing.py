"""Tests for the [ai_writing] table in the checked-in configuration files.

Each environment's files are read with the real loader and the capability's slice is built on
them with the .env file disabled and AI_WRITING__MODEL removed. The model is the deploying
organisation's value: base.toml leaves it unset, and production.toml and local.toml set the model
they sent before it moved out of [openai.tenant]. The raw files are also searched for a model left
under the vendor's tenant entry.
"""

import tomllib
from collections.abc import Iterator

import pytest

from capabilities.ai_writing.settings import AIWritingSettings
from contracts.configuration import install_configuration_files
from server.configuration.loader import CONFIG_DIR, load_configuration_files

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _files_only(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setitem(AIWritingSettings.model_config, "env_file", None)
    monkeypatch.delenv("AI_WRITING__MODEL", raising=False)
    yield


def test_base_leaves_the_model_unset() -> None:
    assert tomllib.loads((CONFIG_DIR / "base.toml").read_text(encoding="utf-8"))["ai_writing"] == {"model": ""}


@pytest.mark.parametrize("environment", ["production", "local"])
def test_deployed_environments_set_the_model_they_sent_before(environment: str) -> None:
    install_configuration_files(load_configuration_files(environment))

    assert AIWritingSettings().model == "gpt-5.6-luna"


def test_ci_leaves_the_model_unset() -> None:
    install_configuration_files(load_configuration_files("ci"))

    assert AIWritingSettings().model == ""


@pytest.mark.parametrize("name", ["base.toml", "local.toml", "ci.toml", "production.toml"])
def test_no_file_names_a_model_under_the_vendor_tenant(name: str) -> None:
    table = tomllib.loads((CONFIG_DIR / name).read_text(encoding="utf-8")).get("openai", {})

    assert "model" not in table.get("tenant", {})
