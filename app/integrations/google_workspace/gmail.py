"""Gmail API integration for Google Workspace."""

import base64
from email.message import EmailMessage
import logging
from integrations.google_workspace.google_service import (
    handle_google_api_errors,
    execute_google_api_call,
    DEFAULT_DELEGATED_ADMIN_EMAIL,
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def create_email_message(subject: str, message: str, sender: str, recipient: str):
    """Creates an EmailMessage object with the specified subject, message, sender, and recipient.

    Args:
        subject (str): The subject of the email.
        message (str): The body of the email.
        sender (str): The email address of the sender.
        recipient (str): The email address of the recipient.

    Returns:
        EmailMessage: The EmailMessage object.
    """
    email = EmailMessage()
    email["Subject"] = subject
    email.set_content(message)
    email["From"] = sender
    email["To"] = recipient
    encoded_message = base64.urlsafe_b64encode(email.as_bytes()).decode()
    email_message = {"message": {"raw": encoded_message}}
    return email_message


@handle_google_api_errors
def create_draft(
    message, user_id="me", delegated_user_email=DEFAULT_DELEGATED_ADMIN_EMAIL
):
    """Creates a new draft with the specified message.

    Args:
        message (EmailMessage): The message to create the draft with.
        user_id (str, optional): The user's email address. Default is 'me'.
        delegated_user_email (str, optional): The email address of the user to impersonate. Default is the default delegated admin email.

    Returns:
        dict: The draft object.
    """
    scopes = [
        "https://www.googleapis.com/auth/gmail.compose",
        "https://www.googleapis.com/auth/gmail.modify",
    ]

    return execute_google_api_call(
        service_name="gmail",
        version="v1",
        resource_path="users.drafts",
        method="create",
        scopes=scopes,
        delegated_user_email=delegated_user_email,
        userId=user_id,
        body=message,
    )
