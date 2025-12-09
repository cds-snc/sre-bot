"""
Modern Gmail API integration for Google Workspace.

This module provides a streamlined interface to the Gmail API using the standardized
google_service_next infrastructure. All functions return OperationResult objects
with consistent error handling and retry logic.

Key Functions:
    - send_email: Send an email via Gmail API
    - create_draft: Create a draft email
    - get_message: Retrieve a specific message
    - list_messages: List messages with optional query filters
"""

import base64
from email.message import EmailMessage
from typing import Optional

from core.logging import get_module_logger
from infrastructure.operations.result import OperationResult
from integrations.google_workspace.google_service_next import execute_google_api_call

logger = get_module_logger()

# Gmail API scopes
GMAIL_SEND_SCOPE = "https://www.googleapis.com/auth/gmail.send"
GMAIL_COMPOSE_SCOPE = "https://www.googleapis.com/auth/gmail.compose"
GMAIL_MODIFY_SCOPE = "https://www.googleapis.com/auth/gmail.modify"
GMAIL_READONLY_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"


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


def send_email(
    subject: str,
    body: str,
    sender: str,
    recipient: str,
    content_type: str = "plain",
    delegated_user_email: Optional[str] = None,
    user_id: str = "me",
) -> OperationResult:
    """Send an email via Gmail API.

    Args:
        subject: Email subject line
        body: Email body content
        sender: Sender email address
        recipient: Recipient email address
        content_type: Content type ('plain' or 'html'), defaults to 'plain'
        delegated_user_email: Email address for delegated access
        user_id: User ID for Gmail API (defaults to 'me')

    Returns:
        OperationResult with message ID in data field on success:
            {
                "id": "message_id",
                "threadId": "thread_id",
                "labelIds": ["SENT"]
            }

    Example:
        result = send_email(
            subject="Test Email",
            body="Hello, World!",
            sender="bot@example.com",
            recipient="user@example.com"
        )
        if result.is_success:
            message_id = result.data["id"]
            logger.info(f"Email sent: {message_id}")
        else:
            logger.error(f"Failed to send: {result.message}")
    """
    try:
        raw_message = _create_mime_message(
            subject, body, sender, recipient, content_type
        )
    except Exception as e:
        logger.error("failed_to_create_mime_message", error=str(e))
        return OperationResult.permanent_error(
            message=f"Failed to create email message: {str(e)}",
            error_code="MIME_CREATION_ERROR",
        )

    return execute_google_api_call(
        service_name="gmail",
        version="v1",
        resource_path="users.messages",
        method="send",
        scopes=[GMAIL_SEND_SCOPE],
        delegated_user_email=delegated_user_email,
        userId=user_id,
        body={"raw": raw_message},
    )


def create_draft(
    subject: str,
    body: str,
    sender: str,
    recipient: str,
    content_type: str = "plain",
    delegated_user_email: Optional[str] = None,
    user_id: str = "me",
) -> OperationResult:
    """Create a draft email via Gmail API.

    Args:
        subject: Email subject line
        body: Email body content
        sender: Sender email address
        recipient: Recipient email address
        content_type: Content type ('plain' or 'html'), defaults to 'plain'
        delegated_user_email: Email address for delegated access
        user_id: User ID for Gmail API (defaults to 'me')

    Returns:
        OperationResult with draft ID in data field on success:
            {
                "id": "draft_id",
                "message": {
                    "id": "message_id",
                    "threadId": "thread_id",
                    "labelIds": ["DRAFT"]
                }
            }
    """
    try:
        raw_message = _create_mime_message(
            subject, body, sender, recipient, content_type
        )
    except Exception as e:
        logger.error("failed_to_create_mime_message", error=str(e))
        return OperationResult.permanent_error(
            message=f"Failed to create email message: {str(e)}",
            error_code="MIME_CREATION_ERROR",
        )

    return execute_google_api_call(
        service_name="gmail",
        version="v1",
        resource_path="users.drafts",
        method="create",
        scopes=[GMAIL_COMPOSE_SCOPE, GMAIL_MODIFY_SCOPE],
        delegated_user_email=delegated_user_email,
        userId=user_id,
        body={"message": {"raw": raw_message}},
    )


def get_message(
    message_id: str,
    delegated_user_email: Optional[str] = None,
    user_id: str = "me",
    format: str = "full",
) -> OperationResult:
    """Get a specific email message by ID.

    Args:
        message_id: The ID of the message to retrieve
        delegated_user_email: Email address for delegated access
        user_id: User ID for Gmail API (defaults to 'me')
        format: Format of the message ('full', 'metadata', 'minimal', 'raw')

    Returns:
        OperationResult with message data on success
    """
    return execute_google_api_call(
        service_name="gmail",
        version="v1",
        resource_path="users.messages",
        method="get",
        scopes=[GMAIL_READONLY_SCOPE],
        delegated_user_email=delegated_user_email,
        userId=user_id,
        id=message_id,
        format=format,
    )


def list_messages(
    query: Optional[str] = None,
    max_results: int = 100,
    delegated_user_email: Optional[str] = None,
    user_id: str = "me",
    label_ids: Optional[list] = None,
) -> OperationResult:
    """List messages in the user's mailbox.

    Args:
        query: Gmail search query (e.g., "is:unread from:user@example.com")
        max_results: Maximum number of messages to return
        delegated_user_email: Email address for delegated access
        user_id: User ID for Gmail API (defaults to 'me')
        label_ids: Filter by label IDs (e.g., ["INBOX", "UNREAD"])

    Returns:
        OperationResult with list of messages on success.
        The data field contains a list of message summaries with 'id' and 'threadId'.
    """
    params = {
        "userId": user_id,
        "maxResults": max_results,
    }

    if query:
        params["q"] = query
    if label_ids:
        params["labelIds"] = label_ids

    return execute_google_api_call(
        service_name="gmail",
        version="v1",
        resource_path="users.messages",
        method="list",
        scopes=[GMAIL_READONLY_SCOPE],
        delegated_user_email=delegated_user_email,
        **params,
    )
