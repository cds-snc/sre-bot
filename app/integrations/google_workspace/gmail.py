"""Gmail API integration for Google Workspace."""

import base64
from email.message import EmailMessage
from integrations.google_workspace import google_service
from core.logging import get_module_logger

GOOGLE_DELEGATED_ADMIN_EMAIL = google_service.GOOGLE_DELEGATED_ADMIN_EMAIL
logger = get_module_logger()
handle_google_api_errors = google_service.handle_google_api_errors


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
    logger.debug("email_message_created", email_message=email_message)
    return email_message


@handle_google_api_errors
def create_draft(
    message, user_id="me", delegated_user_email=GOOGLE_DELEGATED_ADMIN_EMAIL
):
    """Creates a new draft with the specified message.

    Args:
        message (EmailMessage): The message to create the draft with.
        user_id (str, optional): The user's email address. Default is 'me'.
        delegated_user_email (str, optional): The email address of the user to impersonate. Default is the default delegated admin email.

    Returns:
        dict: The draft object.
    """
    logger.debug(
        "creating_draft",
        user_id=user_id,
        delegated_user_email=delegated_user_email,
        message=message,
    )
    scopes = [
        "https://www.googleapis.com/auth/gmail.compose",
        "https://www.googleapis.com/auth/gmail.modify",
    ]

    return google_service.execute_google_api_call(
        service_name="gmail",
        version="v1",
        resource_path="users.drafts",
        method="create",
        scopes=scopes,
        delegated_user_email=delegated_user_email,
        userId=user_id,
        body=message,
    )
