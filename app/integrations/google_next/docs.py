"""Google Docs API integration."""

from googleapiclient.discovery import Resource  # type: ignore

from integrations.google_next.service import (
    execute_google_api_call,
    handle_google_api_errors,
    get_google_service,
)
from core.logging import get_module_logger

DEFAULT_SCOPES = [
    "https://www.googleapis.com/auth/documents",
]

logger = get_module_logger()


class GoogleDocs:
    """
    A class to simplify the use of various Google Docs API operations across modules.

    This class provides methods to interact with the Google Workspace Docs API, including
    authentication, API calls, and error handling for Google API errors.

    Intended usage is to instantiate the class without any arguments, which will use default
    OAuth scopes and the service account for authentication. However, flexibility is provided
    to specify custom scopes, a delegated user email (to perform actions on behalf of a user),
    or a pre-authenticated service resource if needed for advanced or edge cases.

    Attributes:
        scopes (list): The list of OAuth scopes to request. Defaults to DEFAULT_SCOPES if not provided.
        delegated_email (str or None): The email address of the user to impersonate, if any.
        service (Resource): An authenticated Google Docs service resource. If not provided, it will be created using the default scopes and delegated email.
    """

    def __init__(
        self, scopes=None, delegated_email=None, service: Resource | None = None
    ):
        self.scopes = scopes if scopes else DEFAULT_SCOPES
        self.delegated_email = delegated_email
        self.service = service if service else self._get_docs_service()
        logger.debug(
            "google_docs_initialized",
            service_type="docs",
            scopes=scopes,
            delegated_email=delegated_email,
        )

    def _get_docs_service(self) -> Resource:
        """Get authenticated directory service for Google Workspace."""
        logger.debug(
            "getting_docs_service",
            service_type="docs",
            scopes=self.scopes,
            delegated_email=self.delegated_email,
        )
        return get_google_service("docs", "v1", self.scopes, self.delegated_email)

    @handle_google_api_errors
    def create(self, title: str, **kwargs) -> dict:
        """Creates a new and empty document in Google Docs.
        Args:
            title (str): The title of the new document.
            kwargs (dict): Additional parameters to pass to the API call. If provided, these will be merged with the default body.
        Returns:
            dict: The response from the Google Docs API

        Reference:
            https://developers.google.com/docs/api/reference/rest/v1/documents/create
        """
        logger.info(
            "creating_google_doc",
            service="google_docs",
            title=title,
            kwargs=kwargs if kwargs else None,
        )
        body = {
            "title": title,
        }

        if kwargs.get("body", None):
            body.update(kwargs.pop("body"))
        return execute_google_api_call(
            self.service,
            "documents",
            "create",
            body=body,
            **kwargs,
        )

    @handle_google_api_errors
    def batch_update(self, document_id: str, requests: list, **kwargs) -> dict:
        """Applies a list of updates to a document in Google Docs.

        Args:
            document_id (str): The id of the document to update.
            requests (list): A list of update requests.

        Returns:
            dict: The response from the Google Docs API.

        Reference:
            https://developers.google.com/docs/api/reference/rest/v1/documents/batchUpdate
        """
        logger.info(
            "updating_google_doc",
            service="google_docs",
            document_id=document_id,
            requests=requests,
            kwargs=kwargs if kwargs else None,
        )
        return execute_google_api_call(
            self.service,
            "documents",
            "batchUpdate",
            documentId=document_id,
            body={"requests": requests},
            **kwargs,
        )

    @handle_google_api_errors
    def get_document(self, document_id: str, **kwargs) -> dict:
        """Gets a document from Google Docs.

        Args:
            document_id (str): The id of the document to get.

        Returns:
            dict: The document resource.

        Reference:
            https://developers.google.com/docs/api/reference/rest/v1/documents/get
        """
        logger.info(
            "getting_google_doc",
            service="google_docs",
            document_id=document_id,
            kwargs=kwargs if kwargs else None,
        )
        return execute_google_api_call(
            self.service,
            "documents",
            "get",
            documentId=document_id,
            **kwargs,
        )
