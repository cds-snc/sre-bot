"""Google Gmail API client with standardized OperationResult responses.

This module provides a client for interacting with Gmail API,
including email sending, draft creation, and message retrieval operations.
"""

import base64
from email.message import EmailMessage
from typing import Any, Optional

import structlog

from infrastructure.clients.google_workspace.executor import execute_google_api_call
from infrastructure.clients.google_workspace.session_provider import SessionProvider
from infrastructure.operations.result import OperationResult

# Gmail API scopes
GMAIL_SEND_SCOPE = "https://www.googleapis.com/auth/gmail.send"
GMAIL_COMPOSE_SCOPE = "https://www.googleapis.com/auth/gmail.compose"
GMAIL_MODIFY_SCOPE = "https://www.googleapis.com/auth/gmail.modify"
GMAIL_READONLY_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"

logger = structlog.get_logger()


class GmailClient:
    """Client for Gmail API operations.

    Provides methods for sending emails, creating drafts, and managing messages.
    All methods return OperationResult for consistent error handling.

    Attributes:
        _session_provider: SessionProvider instance for authentication
        _logger: Structured logger with component context
    """

    def __init__(self, session_provider: SessionProvider) -> None:
        """Initialize GmailClient with a session provider.

        Args:
            session_provider: SessionProvider instance for Google API authentication
        """
        self._session_provider = session_provider
        self._logger = logger.bind(component="google_gmail_client")

    # ========================================================================
    # Email Operations
    # ========================================================================

    def send_email(
        self,
        subject: str,
        body: str,
        sender: str,
        recipient: str,
        content_type: str = "plain",
        user_id: str = "me",
        delegated_email: Optional[str] = None,
    ) -> OperationResult:
        """Send an email via Gmail API.

        Args:
            subject: Email subject line
            body: Email body content
            sender: Sender email address
            recipient: Recipient email address
            content_type: Content type ('plain' or 'html'), defaults to 'plain'
            user_id: User ID for Gmail API (defaults to 'me')
            delegated_email: Optional email to delegate authentication to

        Returns:
            OperationResult with message data containing id, threadId, and labelIds

        Reference:
            https://developers.google.com/gmail/api/reference/rest/v1/users.messages/send

        Example:
            result = client.send_email(
                subject="Test Email",
                body="Hello, World!",
                sender="bot@example.com",
                recipient="user@example.com"
            )
            if result.is_success:
                message_id = result.data["id"]
        """
        self._logger.info(
            "sending_email",
            subject=subject,
            sender=sender,
            recipient=recipient,
            content_type=content_type,
            delegated_user_email=delegated_email,
        )

        # Create MIME message
        try:
            raw_message = self._create_mime_message(
                subject=subject,
                body=body,
                sender=sender,
                recipient=recipient,
                content_type=content_type,
            )
        except Exception as e:
            self._logger.error("failed_to_create_mime_message", error=str(e))
            return OperationResult.permanent_error(
                message=f"Failed to create email message: {str(e)}",
                error_code="MIME_CREATION_ERROR",
            )

        service = self._session_provider.get_service(
            service_name="gmail",
            version="v1",
            scopes=[GMAIL_SEND_SCOPE],
            delegated_user_email=delegated_email,
        )

        def api_call() -> Any:
            return (
                service.users()
                .messages()
                .send(userId=user_id, body={"raw": raw_message})
                .execute()
            )

        return execute_google_api_call(
            operation_name="gmail.users.messages.send",
            api_callable=api_call,
        )

    def create_draft(
        self,
        subject: str,
        body: str,
        sender: str,
        recipient: str,
        content_type: str = "plain",
        user_id: str = "me",
        delegated_email: Optional[str] = None,
    ) -> OperationResult:
        """Create a draft email via Gmail API.

        Args:
            subject: Email subject line
            body: Email body content
            sender: Sender email address
            recipient: Recipient email address
            content_type: Content type ('plain' or 'html'), defaults to 'plain'
            user_id: User ID for Gmail API (defaults to 'me')
            delegated_email: Optional email to delegate authentication to

        Returns:
            OperationResult with draft data containing id and message

        Reference:
            https://developers.google.com/gmail/api/reference/rest/v1/users.drafts/create

        Example:
            result = client.create_draft(
                subject="Draft Email",
                body="Draft content",
                sender="bot@example.com",
                recipient="user@example.com"
            )
            if result.is_success:
                draft_id = result.data["id"]
        """
        self._logger.info(
            "creating_draft",
            subject=subject,
            sender=sender,
            recipient=recipient,
            content_type=content_type,
            delegated_user_email=delegated_email,
        )

        # Create MIME message
        try:
            raw_message = self._create_mime_message(
                subject=subject,
                body=body,
                sender=sender,
                recipient=recipient,
                content_type=content_type,
            )
        except Exception as e:
            self._logger.error("failed_to_create_mime_message", error=str(e))
            return OperationResult.permanent_error(
                message=f"Failed to create email message: {str(e)}",
                error_code="MIME_CREATION_ERROR",
            )

        service = self._session_provider.get_service(
            service_name="gmail",
            version="v1",
            scopes=[GMAIL_COMPOSE_SCOPE, GMAIL_MODIFY_SCOPE],
            delegated_user_email=delegated_email,
        )

        def api_call() -> Any:
            return (
                service.users()
                .drafts()
                .create(userId=user_id, body={"message": {"raw": raw_message}})
                .execute()
            )

        return execute_google_api_call(
            operation_name="gmail.users.drafts.create",
            api_callable=api_call,
        )

    # ========================================================================
    # Message Operations
    # ========================================================================

    def get_message(
        self,
        message_id: str,
        user_id: str = "me",
        format: str = "full",
        delegated_email: Optional[str] = None,
    ) -> OperationResult:
        """Get a specific email message by ID.

        Args:
            message_id: The ID of the message to retrieve
            user_id: User ID for Gmail API (defaults to 'me')
            format: Format of the message ('full', 'metadata', 'minimal', 'raw')
            delegated_email: Optional email to delegate authentication to

        Returns:
            OperationResult with message data

        Reference:
            https://developers.google.com/gmail/api/reference/rest/v1/users.messages/get

        Example:
            result = client.get_message("msg_12345")
            if result.is_success:
                subject = result.data.get("snippet")
        """
        self._logger.debug(
            "getting_message",
            message_id=message_id,
            format=format,
            delegated_user_email=delegated_email,
        )

        service = self._session_provider.get_service(
            service_name="gmail",
            version="v1",
            scopes=[GMAIL_READONLY_SCOPE],
            delegated_user_email=delegated_email,
        )

        def api_call() -> Any:
            return (
                service.users()
                .messages()
                .get(userId=user_id, id=message_id, format=format)
                .execute()
            )

        return execute_google_api_call(
            operation_name="gmail.users.messages.get",
            api_callable=api_call,
        )

    def list_messages(
        self,
        query: Optional[str] = None,
        max_results: int = 100,
        user_id: str = "me",
        label_ids: Optional[list[str]] = None,
        delegated_email: Optional[str] = None,
    ) -> OperationResult:
        """List messages in the user's mailbox.

        Args:
            query: Gmail search query (e.g., "is:unread from:user@example.com")
            max_results: Maximum number of messages to return
            user_id: User ID for Gmail API (defaults to 'me')
            label_ids: Filter by label IDs (e.g., ["INBOX", "UNREAD"])
            delegated_email: Optional email to delegate authentication to

        Returns:
            OperationResult with list of message summaries (id and threadId)

        Reference:
            https://developers.google.com/gmail/api/reference/rest/v1/users.messages/list

        Example:
            result = client.list_messages(query="is:unread", max_results=50)
            if result.is_success:
                messages = result.data.get("messages", [])
                for msg in messages:
                    msg_id = msg["id"]
        """
        self._logger.debug(
            "listing_messages",
            query=query,
            max_results=max_results,
            label_ids=label_ids,
            delegated_user_email=delegated_email,
        )

        service = self._session_provider.get_service(
            service_name="gmail",
            version="v1",
            scopes=[GMAIL_READONLY_SCOPE],
            delegated_user_email=delegated_email,
        )

        def api_call() -> Any:
            params: dict[str, Any] = {
                "userId": user_id,
                "maxResults": max_results,
            }
            if query:
                params["q"] = query
            if label_ids:
                params["labelIds"] = label_ids

            return service.users().messages().list(**params).execute()

        return execute_google_api_call(
            operation_name="gmail.users.messages.list",
            api_callable=api_call,
        )

    # ========================================================================
    # Utility Functions
    # ========================================================================

    @staticmethod
    def _create_mime_message(
        subject: str,
        body: str,
        sender: str,
        recipient: str,
        content_type: str = "plain",
    ) -> str:
        """Create a base64-encoded MIME message for Gmail API.

        Args:
            subject: Email subject line
            body: Email body content
            sender: Sender email address
            recipient: Recipient email address
            content_type: Content type ('plain' or 'html')

        Returns:
            Base64-encoded MIME message string

        Raises:
            Exception: If message creation fails
        """
        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = sender
        message["To"] = recipient

        if content_type == "html":
            message.set_content(body, subtype="html")
        else:
            message.set_content(body)

        # Encode message for Gmail API
        encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")

        logger.debug(
            "mime_message_created",
            subject=subject,
            sender=sender,
            recipient=recipient,
            content_type=content_type,
            encoded_length=len(encoded_message),
        )

        return encoded_message
