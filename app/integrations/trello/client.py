"""Trello client module."""

from trello import TrelloApi  # type: ignore

from integrations.trello.settings import get_trello_settings


class TrelloNotConfiguredError(RuntimeError):
    """Raised when a Trello call is made without the TRELLO__TENANT__* entry."""


def add_atip_card_to_trello(title, description, due_date):
    """Add a card to the ATIP Trello board."""
    trello = get_trello_client()
    list_id = get_atip_inbox_list_id_in_board()
    return trello.cards.new(title, idList=list_id, desc=description, due=due_date)


def get_atip_inbox_list_id_in_board():
    """Get the ID of the 'Inbox' list in the ATIP Trello board."""
    trello = get_trello_client()
    lists = trello.boards.get_field("lists", get_trello_settings().atip_board)
    return list(filter(lambda x: x["name"] == "Inbox", lists))[0]["id"]


def get_trello_client():
    """Get a Trello client; raises ``TrelloNotConfiguredError`` without a tenant entry."""
    tenant = get_trello_settings().tenant
    if tenant is None:
        raise TrelloNotConfiguredError("Trello is not configured: TRELLO__TENANT__APP_KEY and TRELLO__TENANT__TOKEN are unset")
    trello = TrelloApi(tenant.app_key.get_secret_value())
    trello.set_token(tenant.token.get_secret_value())
    return trello
