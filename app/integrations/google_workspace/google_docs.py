"""Google Docs module.

This module provides functions to create and manipulate Google Docs.
"""

import re

from integrations.google_workspace import google_service
from core.logging import get_module_logger

SCOPES = [
    "https://www.googleapis.com/auth/documents",
]

logger = get_module_logger()
handle_google_api_errors = google_service.handle_google_api_errors


@handle_google_api_errors
def create(title: str):
    """Creates a new document in Google Docs.

    Args:
        title (str): The title of the new document.

    Returns:
        dict: The response from the Google Docs API containing the document ID.
    """
    return google_service.execute_google_api_call(
        "docs",
        "v1",
        "documents",
        "create",
        scopes=SCOPES,
        body={"title": title},
    )


@handle_google_api_errors
def batch_update(document_id: str, requests: list) -> dict:
    """Applies a list of updates to a document in Google Docs.

    Args:
        document_id (str): The id of the document to update.
        requests (list): A list of update requests.

    Returns:
        dict: The response from the Google Docs API.
    """
    return google_service.execute_google_api_call(
        "docs",
        "v1",
        "documents",
        "batchUpdate",
        scopes=SCOPES,
        documentId=document_id,
        body={"requests": requests},
    )


@handle_google_api_errors
def get_document(document_id: str) -> dict:
    """Gets a document from Google Docs.

    Args:
        document_id (str): The id of the document to get.

    Returns:
        dict: The document resource.
    """
    return google_service.execute_google_api_call(
        "docs",
        "v1",
        "documents",
        "get",
        scopes=SCOPES,
        documentId=document_id,
    )


def extract_google_doc_id(url):
    # if the url is empty or None, then log an error
    if not url:
        logger.error(
            "google_doc_id_extraction_failed",
            error="URL is empty or None",
        )
        return None

    # Regular expression pattern to match Google Docs ID
    pattern = r"https://docs.google.com/document/d/([a-zA-Z0-9_-]+)/"

    # Search in the given text for all occurences of pattern
    match = re.search(pattern, url)
    if match:
        return match.group(1)
    else:
        return None
