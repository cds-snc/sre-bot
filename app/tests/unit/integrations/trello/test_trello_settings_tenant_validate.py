"""Unit tests for the Trello tenant entry's boot rules.

Each test installs files from tmp_path with every Trello variable removed (the autouse
isolation fixture) and builds the slice directly. Trello is never half configured: either
tenant variable needs the other, and the ATIP board needs the tenant. Each failure names the
variable at fault, and no failure text carries a value.
"""

from pathlib import Path

import pytest

from contracts.configuration import ConfigurationError
from integrations.trello.settings import TrelloSettings
from tests.unit.integrations.trello.conftest import install_trello_files

pytestmark = pytest.mark.unit

_TENANT = ("TRELLO__TENANT__APP_KEY", "TRELLO__TENANT__TOKEN")


@pytest.mark.parametrize("present", _TENANT)
def test_one_tenant_variable_without_the_other_fails_naming_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, present: str
) -> None:
    install_trello_files(tmp_path)
    monkeypatch.setenv(present, "trello-validate-0001")
    missing = next(name for name in _TENANT if name != present)

    with pytest.raises(ConfigurationError, match=missing) as raised:
        TrelloSettings()

    assert "trello-validate-0001" not in str(raised.value)


def test_the_board_without_a_tenant_fails_naming_it(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    install_trello_files(tmp_path)
    monkeypatch.setenv("TRELLO__ATIP_BOARD", "board-validate-0001")

    with pytest.raises(ConfigurationError, match="TRELLO__ATIP_BOARD") as raised:
        TrelloSettings()

    assert "board-validate-0001" not in str(raised.value)


@pytest.mark.parametrize(
    ("files", "env", "key"),
    [
        ('[trello]\natip_boards = "x"\n', {}, "atip_boards"),
        ("", {"TRELLO__TENANT__SECRET": "x"}, "secret"),
    ],
)
def test_an_unknown_key_fails_naming_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, files: str, env: dict[str, str], key: str
) -> None:
    install_trello_files(tmp_path, environment=files)
    monkeypatch.setenv("TRELLO__TENANT__APP_KEY", "trello-validate-0002")
    monkeypatch.setenv("TRELLO__TENANT__TOKEN", "trello-validate-0003")
    for name, value in env.items():
        monkeypatch.setenv(name, value)

    with pytest.raises(ConfigurationError, match=key):
        TrelloSettings()
