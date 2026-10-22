"""Trello client module."""

from trello import TrelloApi  # type: ignore

from integrations.trello.settings import get_trello_settings

trello_settings = get_trello_settings()


def add_atip_card_to_trello(title, description, due_date):
    """Add a card to the ATIP Trello board."""
    trello = get_trello_client()
    list_id = get_atip_inbox_list_id_in_board()
    return trello.cards.new(title, idList=list_id, desc=description, due=due_date)


def get_atip_inbox_list_id_in_board():
    """Get the ID of the 'Inbox' list in the ATIP Trello board."""
    trello = get_trello_client()
    lists = trello.boards.get_field("lists", trello_settings.trello_atip_board)
    return list(filter(lambda x: x["name"] == "Inbox", lists))[0]["id"]


def get_trello_client():
    """Get a Trello client."""
    trello = TrelloApi(trello_settings.trello_app_key)
    trello.set_token(trello_settings.trello_token)
    return trello
