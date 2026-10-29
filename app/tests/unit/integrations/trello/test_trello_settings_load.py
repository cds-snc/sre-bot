"""Unit tests for loading the Trello vendor slice.

Each test installs a base and a local file from tmp_path (``install_trello_files``) with every
Trello variable removed and the .env file disabled (the autouse isolation fixture), so it
observes only the values it writes and sets. The SDK fixes Trello's host, so the tenant entry is
its credentials, read only from TRELLO__TENANT__APP_KEY and TRELLO__TENANT__TOKEN; the ATIP
board (a non-public value) only from TRELLO__ATIP_BOARD.
"""

from pathlib import Path

import pytest

from contracts.configuration import ConfigurationSlice
from integrations.trello.settings import TrelloSettings, get_trello_settings
from tests.unit.integrations.trello.conftest import install_trello_files

pytestmark = pytest.mark.unit


def test_trello_settings_is_a_slice_on_the_trello_table() -> None:
    """The slice reads [trello] with the TRELLO__ prefix and rejects unknown keys."""
    config = TrelloSettings.model_config

    assert issubclass(TrelloSettings, ConfigurationSlice)
    assert config.get("toml_table_header") == ("trello",)
    assert config.get("env_prefix") == "TRELLO__"
    assert config.get("extra") == "forbid"


@pytest.mark.parametrize("field", list(TrelloSettings.model_fields))
def test_trello_settings_fields_have_no_alias(field: str) -> None:
    info = TrelloSettings.model_fields[field]

    assert (info.alias, info.validation_alias) == (None, None)


def test_nothing_set_is_trello_not_configured(tmp_path: Path) -> None:
    install_trello_files(tmp_path)

    settings = TrelloSettings()

    assert settings.tenant is None
    assert settings.atip_board == ""


def test_the_tenant_variables_configure_trello(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    install_trello_files(tmp_path)
    monkeypatch.setenv("TRELLO__TENANT__APP_KEY", "trello-key-0001")
    monkeypatch.setenv("TRELLO__TENANT__TOKEN", "trello-token-0001")
    monkeypatch.setenv("TRELLO__ATIP_BOARD", "board-0001")

    settings = TrelloSettings()

    assert settings.tenant is not None
    assert settings.tenant.app_key.get_secret_value() == "trello-key-0001"
    assert settings.tenant.token.get_secret_value() == "trello-token-0001"
    assert settings.atip_board == "board-0001"


def test_the_values_never_appear_in_repr_str_or_dump(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The credentials are masked wherever the slice is rendered; the board is left out of repr and str."""
    install_trello_files(tmp_path)
    monkeypatch.setenv("TRELLO__TENANT__APP_KEY", "trello-key-render")
    monkeypatch.setenv("TRELLO__TENANT__TOKEN", "trello-token-render")
    monkeypatch.setenv("TRELLO__ATIP_BOARD", "board-render")

    settings = TrelloSettings()

    for rendered in (repr(settings), str(settings), repr(settings.model_dump())):
        assert "trello-key-render" not in rendered
        assert "trello-token-render" not in rendered
    assert "board-render" not in repr(settings) + str(settings)


def test_empty_values_count_as_unset(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    install_trello_files(tmp_path)
    for name in ("TRELLO__TENANT__APP_KEY", "TRELLO__TENANT__TOKEN", "TRELLO__ATIP_BOARD"):
        monkeypatch.setenv(name, "")

    assert TrelloSettings().tenant is None


def test_get_trello_settings_is_cached(tmp_path: Path) -> None:
    install_trello_files(tmp_path)

    assert get_trello_settings() is get_trello_settings()
