"""Google Docs module.

This module provides functions to create and manipulate Google Docs.
"""

import re
import structlog

from integrations.google_workspace import google_service

logger = structlog.get_logger()
handle_google_api_errors = google_service.handle_google_api_errors


@handle_google_api_errors
def create(title: str, **kwargs) -> dict:
    """Creates a new document in Google Docs.

    Args:
        title (str): The title of the new document.
        **kwargs: Additional keyword arguments to pass to the API call. e.g., `delegated_user_email`.

    Returns:
        dict: The response from the Google Docs API containing the document ID.
    """
    return google_service.execute_google_api_call(
        "docs",
        "v1",
        "documents",
        "create",
        scopes=["https://www.googleapis.com/auth/documents"],
        body={"title": title},
        **kwargs,
    )


@handle_google_api_errors
def batch_update(document_id: str, requests: list, **kwargs) -> dict:
    """Applies a list of updates to a document in Google Docs.

    Args:
        document_id (str): The id of the document to update.
        requests (list): A list of update requests.
        **kwargs: Additional keyword arguments to pass to the API call. e.g., `delegated_user_email`.

    Returns:
        dict: The response from the Google Docs API.
    """
    return google_service.execute_google_api_call(
        "docs",
        "v1",
        "documents",
        "batchUpdate",
        scopes=["https://www.googleapis.com/auth/documents"],
        documentId=document_id,
        body={"requests": requests},
        **kwargs,
    )


@handle_google_api_errors
def get_document(document_id: str, **kwargs) -> dict:
    """Gets a document from Google Docs.

    Args:
        document_id (str): The id of the document to get.
        **kwargs: Additional keyword arguments to pass to the API call. e.g., `delegated_user_email`.

    Returns:
        dict: The document resource.
    """
    return google_service.execute_google_api_call(
        "docs",
        "v1",
        "documents",
        "get",
        scopes=["https://www.googleapis.com/auth/documents"],
        documentId=document_id,
        **kwargs,
    )


def extract_google_doc_id(url):
    """
    Extracts the Google Docs ID from a Google Docs URL.

    Args:
        url (str): The URL of the Google Docs document.

    Returns:
        str: The Google Docs ID extracted from the URL.
    """
    logger.debug(
        "extracting_google_doc_id",
        url=url,
    )
    if not url:
        return None

    # Regular expression pattern to match Google Docs ID
    pattern = r"https://docs.google.com/document/d/([a-zA-Z0-9_-]+)/"

    # Search in the given text for all occurences of pattern
    match = re.search(pattern, url)
    if match:
        return match.group(1)
    else:
        return None
