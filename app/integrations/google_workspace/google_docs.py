"""Google Docs module.

This module provides functions to create and manipulate Google Docs.
"""

import re
from typing import TYPE_CHECKING, cast

import structlog

from integrations.google_workspace import client as google_service_client

if TYPE_CHECKING:
    from googleapiclient._apis.docs.v1 import (  # pyright: ignore[reportMissingModuleSource]
        BatchUpdateDocumentRequest,
        Document,
    )

logger = structlog.get_logger()

DOCS_SCOPES = ["https://www.googleapis.com/auth/documents"]


def create(title: str, **kwargs) -> dict:
    """Creates a new document in Google Docs.

    Args:
        title (str): The title of the new document.
        **kwargs: Additional keyword arguments to pass to the API call. e.g., `delegated_user_email`.

    Returns:
        dict: The response from the Google Docs API containing the document ID.
    """
    service = google_service_client.get_docs_service(
        scopes=DOCS_SCOPES,
        delegated_user_email=kwargs.pop("delegated_user_email", None),
    )
    body = cast("Document", {"title": title})
    result: dict = google_service_client.execute_google_api_request(service.documents().create(body=body))
    return result


def batch_update(document_id: str, requests: list, **kwargs) -> dict:
    """Applies a list of updates to a document in Google Docs.

    Args:
        document_id (str): The id of the document to update.
        requests (list): A list of update requests.
        **kwargs: Additional keyword arguments to pass to the API call. e.g., `delegated_user_email`.

    Returns:
        dict: The response from the Google Docs API.
    """
    service = google_service_client.get_docs_service(
        scopes=DOCS_SCOPES,
        delegated_user_email=kwargs.pop("delegated_user_email", None),
    )
    body = cast("BatchUpdateDocumentRequest", {"requests": requests})
    result: dict = google_service_client.execute_google_api_request(
        service.documents().batchUpdate(documentId=document_id, body=body)
    )
    return result


def get_document(document_id: str, **kwargs) -> dict:
    """Gets a document from Google Docs.

    Args:
        document_id (str): The id of the document to get.
        **kwargs: Additional keyword arguments to pass to the API call. e.g., `delegated_user_email`.

    Returns:
        dict: The document resource.
    """
    service = google_service_client.get_docs_service(
        scopes=DOCS_SCOPES,
        delegated_user_email=kwargs.pop("delegated_user_email", None),
    )
    result: dict = google_service_client.execute_google_api_request(service.documents().get(documentId=document_id))
    return result


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
