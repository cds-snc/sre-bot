"""Google Docs module.

This module provides functions to create and manipulate Google Docs.
"""

import logging
import re
from integrations.google_workspace.google_service import (
    handle_google_api_errors,
    execute_google_api_call,
)


@handle_google_api_errors
def create(title: str) -> str:
    """Creates a new document in Google Docs.

    Args:
        title (str): The title of the new document.

    Returns:
        str: The id of the new document.
    """
    result = execute_google_api_call(
        "docs",
        "v1",
        "documents",
        "create",
        scopes=["https://www.googleapis.com/auth/documents"],
        body={"title": title},
    )
    return result["documentId"]


@handle_google_api_errors
def batch_update(document_id: str, requests: list) -> dict:
    """Applies a list of updates to a document in Google Docs.

    Args:
        document_id (str): The id of the document to update.
        requests (list): A list of update requests.

    Returns:
        dict: The response from the Google Docs API.
    """
    return execute_google_api_call(
        "docs",
        "v1",
        "documents",
        "batchUpdate",
        scopes=["https://www.googleapis.com/auth/documents"],
        documentId=document_id,
        body={"requests": requests},
    )


@handle_google_api_errors
def get(document_id: str) -> dict:
    """Gets a document from Google Docs.

    Args:
        document_id (str): The id of the document to get.

    Returns:
        dict: The document resource.
    """
    return execute_google_api_call(
        "docs",
        "v1",
        "documents",
        "get",
        scopes=["https://www.googleapis.com/auth/documents.readonly"],
        documentId=document_id,
    )


def extract_google_doc_id(url):
    # if the url is empty or None, then log an error
    if not url:
        logging.error("URL is empty or None")
        return None

    # Regular expression pattern to match Google Docs ID
    pattern = r"https://docs.google.com/document/d/([a-zA-Z0-9_-]+)/"

    # Search in the given text for all occurences of pattern
    match = re.search(pattern, url)
    if match:
        return match.group(1)
    else:
        return None
