"""Tests for the Trello client used by the legacy ATIP command.

The client reads the Trello slice at use through ``get_trello_settings``, which each test
patches with a real ``TrelloSettings`` (``model_construct``, so no configuration files are
needed). The SDK is stubbed at ``TrelloApi``; no test reaches the network.
"""

from unittest.mock import MagicMock, patch

import pytest
from pydantic import SecretStr

from integrations import trello
from integrations.trello import TrelloNotConfiguredError
from integrations.trello.settings import TrelloSettings, TrelloTenant

_TENANT = TrelloTenant(app_key=SecretStr("app-key"), token=SecretStr("token"))


def _settings(tenant: TrelloTenant | None = _TENANT, board: str = "board-id") -> TrelloSettings:
    return TrelloSettings.model_construct(tenant=tenant, atip_board=board if tenant else "")


@pytest.fixture(autouse=True)
def _configured_trello():
    with patch("integrations.trello.client.get_trello_settings", return_value=_settings()):
        yield


@patch("integrations.trello.client.get_trello_client")
@patch("integrations.trello.client.get_atip_inbox_list_id_in_board")
def test_add_atip_card_to_trello(atip_inbox_list_id_in_board_mock, get_trello_client_mock):
    trello_mock = MagicMock()
    trello_mock.cards.new.return_value = "card"
    get_trello_client_mock.return_value = trello_mock
    atip_inbox_list_id_in_board_mock.return_value = "list_id"
    assert trello.add_atip_card_to_trello("title", "description", "due_date") == "card"
    trello_mock.cards.new.assert_called_with("title", idList="list_id", desc="description", due="due_date")


@patch("integrations.trello.client.get_trello_client")
def test_get_atip_inbox_list_id_in_board(get_trello_client_mock):
    trello_mock = MagicMock()
    trello_mock.boards.get_field.return_value = [
        {"name": "Inbox", "id": "inbox_list_id"},
        {"name": "Done", "id": "done_list_id"},
    ]
    get_trello_client_mock.return_value = trello_mock
    assert trello.get_atip_inbox_list_id_in_board() == "inbox_list_id"
    trello_mock.boards.get_field.assert_called_once_with("lists", "board-id")


@patch("integrations.trello.client.TrelloApi")
def test_get_trello_client_uses_the_tenant_credentials(trello_api_mock):
    assert trello.get_trello_client() == trello_api_mock.return_value
    trello_api_mock.assert_called_once_with("app-key")
    trello_api_mock.return_value.set_token.assert_called_once_with("token")


@patch("integrations.trello.client.TrelloApi")
def test_get_trello_client_without_a_tenant_raises_without_an_sdk_call(trello_api_mock):
    with patch("integrations.trello.client.get_trello_settings", return_value=_settings(tenant=None)):
        with pytest.raises(TrelloNotConfiguredError, match="TRELLO__TENANT__APP_KEY"):
            trello.get_trello_client()

    trello_api_mock.assert_not_called()
