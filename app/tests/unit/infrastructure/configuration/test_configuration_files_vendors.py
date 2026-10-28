"""Tests for the Notify, Trello, Opsgenie and MaxMind tables in the checked-in configuration files.

Each environment's files are read with the real loader and each slice is built on them, with
its credentials set where the environment names an entry (a secret is never in a file) and
blanked otherwise. production.toml names the Notify and Opsgenie API hosts and the MaxMind
database; local.toml the Opsgenie host (development has a key) and the MaxMind database; ci.toml
no entry, so the test run has the four vendors not configured. Trello's entry is its credentials,
so no file names it. The raw files are also searched for a credential or the ATIP board.
"""

import tomllib
from collections.abc import Iterator

import pytest

from contracts.configuration import install_configuration_files
from integrations.maxmind.settings import MaxMindSettings
from integrations.notify.settings import NotifySettings
from integrations.opsgenie.settings import OpsGenieSettings
from integrations.trello.settings import TrelloSettings
from server.configuration.loader import CONFIG_DIR, load_configuration_files

pytestmark = pytest.mark.unit

_SLICES = (NotifySettings, TrelloSettings, OpsGenieSettings, MaxMindSettings)
_SECRETS = (
    "NOTIFY__SRE_USER_NAME",
    "NOTIFY__SRE_CLIENT_SECRET",
    "OPSGENIE__INTEGRATIONS_KEY",
    "TRELLO__TENANT__APP_KEY",
    "TRELLO__TENANT__TOKEN",
    "TRELLO__ATIP_BOARD",
)
# The tenant entries each environment file names; base.toml names none.
_ENTRIES = {
    "production": {"notify", "opsgenie", "maxmind"},
    "local": {"opsgenie", "maxmind"},
    "ci": set(),
}


@pytest.fixture(autouse=True)
def _no_dotenv(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Build the slices from the files only, never a developer's .env or Codespaces secrets."""
    for slice_class in _SLICES:
        monkeypatch.setitem(slice_class.model_config, "env_file", None)
    for name in _SECRETS:
        monkeypatch.setenv(name, "")
    yield


@pytest.mark.parametrize("environment", list(_ENTRIES))
def test_each_environment_names_its_entries(environment: str, monkeypatch: pytest.MonkeyPatch) -> None:
    install_configuration_files(load_configuration_files(environment))
    entries = _ENTRIES[environment]
    if "notify" in entries:
        monkeypatch.setenv("NOTIFY__SRE_USER_NAME", "files-user")
        monkeypatch.setenv("NOTIFY__SRE_CLIENT_SECRET", "files-secret")
    if "opsgenie" in entries:
        monkeypatch.setenv("OPSGENIE__INTEGRATIONS_KEY", "files-key")

    configured = {
        name
        for name, settings in (
            ("notify", NotifySettings()),
            ("trello", TrelloSettings()),
            ("opsgenie", OpsGenieSettings()),
            ("maxmind", MaxMindSettings()),
        )
        if settings.tenant is not None
    }

    assert configured == entries


def test_production_reaches_the_us_opsgenie_host_and_the_image_database() -> None:
    install_configuration_files(load_configuration_files("production"))
    files = tomllib.loads((CONFIG_DIR / "production.toml").read_text(encoding="utf-8"))

    assert files["opsgenie"]["tenant"] == {"api_url": "https://api.opsgenie.com"}
    assert files["maxmind"]["tenant"] == {"database_path": "./geodb/GeoLite2-City.mmdb"}
    assert files["notify"]["tenant"]["api_url"].startswith("https://")


def test_base_names_no_entry() -> None:
    files = tomllib.loads((CONFIG_DIR / "base.toml").read_text(encoding="utf-8"))

    assert files["notify"] == {"timeout_seconds": 60.0}
    assert files["opsgenie"] == {"timeout_seconds": 30.0}
    assert files["trello"] == {}
    assert files["maxmind"] == {}


@pytest.mark.parametrize("name", ["base.toml", "local.toml", "ci.toml", "production.toml"])
def test_no_file_holds_a_credential_or_the_board(name: str) -> None:
    files = tomllib.loads((CONFIG_DIR / name).read_text(encoding="utf-8"))
    tables = {table: files.get(table, {}) for table in ("notify", "trello", "opsgenie", "maxmind")}

    assert tables["trello"] == {} or "tenant" not in tables["trello"]
    assert "atip_board" not in tables["trello"]
    for table in tables.values():
        keys = set(table) | set(table.get("tenant", {}))
        assert not keys & {"sre_user_name", "sre_client_secret", "integrations_key", "app_key", "token"}
