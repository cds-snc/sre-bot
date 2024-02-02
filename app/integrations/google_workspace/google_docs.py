"""Google Docs module.

This module provides functions to create and manipulate Google Docs.

Functions:
    create(title: str) -> str:
        Creates a new document in Google Docs and returns the id of the new document.

    batch_update(document_id: str, requests: list) -> None:
        Applies a list of updates to a document in Google Docs.

    get(document_id: str) -> dict:
        Gets a document from Google Docs and returns the document resource.
"""
from integrations.google_workspace.google_service import (get_google_service, handle_google_api_errors)


@handle_google_api_errors
def create(title: str) -> str:
    """Creates a new document in Google Docs.

    Args:
        title (str): The title of the new document.

    Returns:
        str: The id of the new document.
    """
    # pylint: disable=no-member
    service = get_google_service("docs", "v1")
    result = service.documents().create(body={"title": title}).execute()
    return result["documentId"]


@handle_google_api_errors
def batch_update(document_id: str, requests: list) -> None:
    """Applies a list of updates to a document in Google Docs.

    Args:
        document_id (str): The id of the document to update.
        requests (list): A list of update requests.

    Returns:
        None
    """
    # pylint: disable=no-member
    service = get_google_service("docs", "v1")
    service.documents().batchUpdate(
        documentId=document_id,
        body={"requests": requests},
    ).execute()


@handle_google_api_errors
def get(document_id: str) -> dict:
    """Gets a document from Google Docs.

    Args:
        document_id (str): The id of the document to get.

    Returns:
        dict: The document resource.
    """
    # pylint: disable=no-member
    service = get_google_service("docs", "v1")
    result = service.documents().get(documentId=document_id).execute()
    return result
