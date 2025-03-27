from unittest.mock import MagicMock, patch

from integrations import trello


@patch("integrations.trello.client.get_trello_client")
@patch("integrations.trello.client.get_atip_inbox_list_id_in_board")
def test_add_atip_card_to_trello(
    atip_inbox_list_id_in_board_mock, get_trello_client_mock
):
    trello_mock = MagicMock()
    trello_mock.cards.new.return_value = "card"
    get_trello_client_mock.return_value = trello_mock
    atip_inbox_list_id_in_board_mock.return_value = "list_id"
    assert trello.add_atip_card_to_trello("title", "description", "due_date") == "card"
    trello_mock.cards.new.assert_called_with(
        "title", idList="list_id", desc="description", due="due_date"
    )


@patch("integrations.trello.client.get_trello_client")
def test_get_atip_inbox_list_id_in_board(get_trello_client_mock):
    trello_mock = MagicMock()
    trello_mock.boards.get_field.return_value = [
        {"name": "Inbox", "id": "inbox_list_id"},
        {"name": "Done", "id": "done_list_id"},
    ]
    get_trello_client_mock.return_value = trello_mock
    assert trello.get_atip_inbox_list_id_in_board() == "inbox_list_id"


@patch("integrations.trello.client.TrelloApi")
def test_get_trello_client(trello_api_mock):
    trello_api_mock.return_value = MagicMock()
    assert trello.get_trello_client() == trello_api_mock()
    trello_api_mock.assert_called_with()
    trello_api_mock.return_value.set_token.assert_called_with('"TRELLO_TOKEN"')
