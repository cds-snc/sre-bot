"""The [atip] slice: where the ATIP kickoff is announced, per environment file.

Local and ci announce in the SRE test channel, as the handler did when the channel was written
in code; production announces where the ATIP_ANNOUNCE_CHANNEL blob line pointed (deploy check
'features'). The retired flat name is unread, and an unknown key fails naming it.
"""

import tomllib
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest

from contracts.configuration import ConfigurationError, install_configuration_files, uninstall_configuration_files
from modules.atip.settings import AtipSettings
from server.configuration.loader import CONFIG_DIR, load_configuration_files

pytestmark = pytest.mark.unit


@dataclass(frozen=True)
class _Files:
    environment: str
    paths: tuple[Path, ...]


@pytest.fixture(autouse=True)
def _no_dotenv(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setitem(AtipSettings.model_config, "env_file", None)
    monkeypatch.delenv("ATIP__ANNOUNCE_CHANNEL_ID", raising=False)
    monkeypatch.delenv("ATIP_ANNOUNCE_CHANNEL", raising=False)
    yield


def test_base_declares_the_announce_channel_empty() -> None:
    base = tomllib.loads((CONFIG_DIR / "base.toml").read_text(encoding="utf-8"))

    assert base["atip"] == {"announce_channel_id": ""}


@pytest.mark.parametrize("environment", ["local", "ci"])
def test_local_and_ci_announce_in_the_test_channel(environment: str) -> None:
    install_configuration_files(load_configuration_files(environment))

    assert AtipSettings().announce_channel_id == "C033L7RGCT0"


def test_production_announces_where_the_blob_line_pointed() -> None:
    """Production's announce channel was the test channel both in code and in the blob line."""
    install_configuration_files(load_configuration_files("production"))

    assert AtipSettings().announce_channel_id == "C033L7RGCT0"


def test_prefixed_name_beats_the_file_and_the_flat_name_is_unread(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ATIP_ANNOUNCE_CHANNEL", "COLD")
    assert AtipSettings().announce_channel_id == "C033L7RGCT0"

    monkeypatch.setenv("ATIP__ANNOUNCE_CHANNEL_ID", "C0OVERRIDE")
    assert AtipSettings().announce_channel_id == "C0OVERRIDE"


def test_unknown_key_in_the_table_fails_naming_it(tmp_path: Path) -> None:
    base = tmp_path / "base.toml"
    environment = tmp_path / "ci.toml"
    base.write_text("[atip]\nannounce_channel = 1\n")
    environment.write_text("")
    install_configuration_files(_Files("ci", (base, environment)))

    with pytest.raises(ConfigurationError, match="announce_channel"):
        AtipSettings()


def test_building_before_install_raises() -> None:
    uninstall_configuration_files()

    with pytest.raises(ConfigurationError):
        AtipSettings()
