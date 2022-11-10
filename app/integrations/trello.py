import os
from trello import TrelloApi

TRELLO_APP_KEY = os.getenv("TRELLO_APP_KEY", None)
TRELLO_TOKEN = os.getenv("TRELLO_TOKEN", None)
TRELLO_ATIP_BOARD = os.getenv("TRELLO_ATIP_BOARD", None)


def add_atip_card_to_trello(title, description, due_date):
    trello = get_trello_client()
    list_id = get_atip_inbox_list_id_in_board()
    return trello.cards.new(title, idList=list_id, desc=description, due=due_date)


def get_atip_inbox_list_id_in_board():
    trello = get_trello_client()
    lists = trello.boards.get_field("lists", TRELLO_ATIP_BOARD)
    return list(filter(lambda x: x["name"] == "Inbox", lists))[0]["id"]


def get_trello_client():
    trello = TrelloApi(TRELLO_APP_KEY)
    trello.set_token(TRELLO_TOKEN)
    return trello
