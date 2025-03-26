"""Trello client module."""

from trello import TrelloApi
from core.config import settings

TRELLO_ATIP_BOARD = settings.trello.TRELLO_ATIP_BOARD
TRELLO_APP_KEY = settings.trello.TRELLO_APP_KEY
TRELLO_TOKEN = settings.trello.TRELLO_TOKEN


def add_atip_card_to_trello(title, description, due_date):
    """Add a card to the ATIP Trello board."""
    trello = get_trello_client()
    list_id = get_atip_inbox_list_id_in_board()
    return trello.cards.new(title, idList=list_id, desc=description, due=due_date)


def get_atip_inbox_list_id_in_board():
    """Get the ID of the 'Inbox' list in the ATIP Trello board."""
    trello = get_trello_client()
    lists = trello.boards.get_field("lists", TRELLO_ATIP_BOARD)
    return list(filter(lambda x: x["name"] == "Inbox", lists))[0]["id"]


def get_trello_client():
    """Get a Trello client."""
    trello = TrelloApi(TRELLO_APP_KEY)
    trello.set_token(TRELLO_TOKEN)
    return trello
