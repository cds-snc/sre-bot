"""Google Docs API client with standardized OperationResult responses.

This module provides a client for interacting with Google Docs API,
including document creation, updates, and retrieval operations.
"""

import re
from typing import Any, Optional

import structlog

from infrastructure.clients.google_workspace.executor import execute_google_api_call
from infrastructure.clients.google_workspace.session_provider import SessionProvider
from infrastructure.operations.result import OperationResult

# Scopes
DOCS_SCOPE = "https://www.googleapis.com/auth/documents"

logger = structlog.get_logger()


class DocsClient:
    """Client for Google Docs API operations.

    Provides methods for creating, updating, and retrieving Google Docs documents.
    All methods return OperationResult for consistent error handling.

    Attributes:
        _session_provider: SessionProvider instance for authentication
        _logger: Structured logger with component context
    """

    def __init__(self, session_provider: SessionProvider) -> None:
        """Initialize DocsClient with a session provider.

        Args:
            session_provider: SessionProvider instance for Google API authentication
        """
        self._session_provider = session_provider
        self._logger = logger.bind(component="google_docs_client")

    # ========================================================================
    # Document Operations
    # ========================================================================

    def get_document(
        self,
        document_id: str,
        delegated_email: Optional[str] = None,
    ) -> OperationResult:
        """Get a document from Google Docs.

        Args:
            document_id: The ID of the document to retrieve
            delegated_email: Optional email to delegate authentication to

        Returns:
            OperationResult with document resource in data field

        Reference:
            https://developers.google.com/docs/api/reference/rest/v1/documents/get
        """
        self._logger.debug(
            "getting_document",
            document_id=document_id,
            delegated_user_email=delegated_email,
        )

        service = self._session_provider.get_service(
            service_name="docs",
            version="v1",
            scopes=[DOCS_SCOPE],
            delegated_user_email=delegated_email,
        )

        def api_call() -> Any:
            return service.documents().get(documentId=document_id).execute()

        return execute_google_api_call(
            operation_name="docs.documents.get",
            api_callable=api_call,
        )

    def create(
        self,
        title: str,
        delegated_email: Optional[str] = None,
    ) -> OperationResult:
        """Create a new document in Google Docs.

        Args:
            title: The title of the new document
            delegated_email: Optional email to delegate authentication to

        Returns:
            OperationResult with created document resource containing documentId

        Reference:
            https://developers.google.com/docs/api/reference/rest/v1/documents/create
        """
        self._logger.info(
            "creating_document",
            title=title,
            delegated_user_email=delegated_email,
        )

        service = self._session_provider.get_service(
            service_name="docs",
            version="v1",
            scopes=[DOCS_SCOPE],
            delegated_user_email=delegated_email,
        )

        def api_call() -> Any:
            return service.documents().create(body={"title": title}).execute()

        return execute_google_api_call(
            operation_name="docs.documents.create",
            api_callable=api_call,
        )

    def batch_update(
        self,
        document_id: str,
        requests: list[dict[str, Any]],
        delegated_email: Optional[str] = None,
    ) -> OperationResult:
        """Apply a list of updates to a document in Google Docs.

        Args:
            document_id: The ID of the document to update
            requests: A list of update request objects
            delegated_email: Optional email to delegate authentication to

        Returns:
            OperationResult with batch update response

        Reference:
            https://developers.google.com/docs/api/reference/rest/v1/documents/batchUpdate

        Example:
            requests = [
                {
                    "insertText": {
                        "location": {"index": 1},
                        "text": "Hello, World!"
                    }
                }
            ]
            result = client.batch_update(doc_id, requests)
        """
        self._logger.info(
            "batch_updating_document",
            document_id=document_id,
            requests_count=len(requests),
            delegated_user_email=delegated_email,
        )

        service = self._session_provider.get_service(
            service_name="docs",
            version="v1",
            scopes=[DOCS_SCOPE],
            delegated_user_email=delegated_email,
        )

        def api_call() -> Any:
            return (
                service.documents()
                .batchUpdate(documentId=document_id, body={"requests": requests})
                .execute()
            )

        return execute_google_api_call(
            operation_name="docs.documents.batchUpdate",
            api_callable=api_call,
        )

    # ========================================================================
    # Utility Functions
    # ========================================================================

    @staticmethod
    def extract_google_doc_id(url: str) -> Optional[str]:
        """Extract the Google Docs ID from a Google Docs URL.

        Args:
            url: The URL of the Google Docs document

        Returns:
            The Google Docs ID extracted from the URL, or None if not found

        Example:
            url = "https://docs.google.com/document/d/1ABC123/edit"
            doc_id = DocsClient.extract_google_doc_id(url)  # Returns "1ABC123"
        """
        logger.debug("extracting_google_doc_id", url=url)

        if not url:
            return None

        # Regular expression pattern to match Google Docs ID
        pattern = r"https://docs\.google\.com/document/d/([a-zA-Z0-9_-]+)/"

        # Search in the given text for all occurrences of pattern
        match = re.search(pattern, url)
        if match:
            return match.group(1)
        else:
            return None
