import re
from googleapiclient.discovery import Resource  # type: ignore
from integrations.google_next.service import (
    execute_google_api_call,
    handle_google_api_errors,
    get_google_service,
    GOOGLE_DELEGATED_ADMIN_EMAIL,
)


class GoogleDocs:
    """
    A class to simplify the use of various Google Docs API operations across modules.

    This class provides methods to interact with the Google Workspace Docs API, including
      It handles authentication and API calls,
    and includes error handling for Google API errors.

    While this class aims to simplify the usage of the Google Directory API, it is always possible
    to use the Google API Python client directly as per the official documentation:
    (https://googleapis.github.io/google-api-python-client/docs/)

    Attributes:
        scopes (list): The list of scopes to request.
        delegated_email (str): The email address of the user to impersonate.
        service (Resource): Optional - An authenticated Google service resource. If provided, the service will be used instead of creating a new one.
    """

    def __init__(
        self, scopes=None, delegated_email=None, service: Resource | None = None
    ):
        if not scopes and not service:
            raise ValueError("Either scopes or a service must be provided.")
        if not delegated_email and not service:
            delegated_email = GOOGLE_DELEGATED_ADMIN_EMAIL
        self.scopes = scopes
        self.delegated_email = delegated_email
        self.service = service if service else self._get_docs_service()

    def _get_docs_service(self) -> Resource:
        """Get authenticated directory service for Google Workspace."""
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
        return execute_google_api_call(
            self.service,
            "documents",
            "get",
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
