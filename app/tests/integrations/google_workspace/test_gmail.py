from unittest.mock import patch
from integrations.google_workspace import gmail


def test_create_email_message():
    subject = "Test Subject"
    message = "Test Message"
    sender = "user.test@email.com"
    recipient = "user.recipient@email.com"
    message = gmail.create_email_message(subject, message, sender, recipient)
    assert message["message"]["raw"] is not None


@patch(
    "integrations.google_workspace.gmail.DEFAULT_DELEGATED_ADMIN_EMAIL",
    "delegated_user_email",
)
@patch("integrations.google_workspace.gmail.execute_google_api_call")
def test_create_draft(
    mock_execute_google_api_call,
):
    mock_execute_google_api_call.return_value = "message_id"
    message = {"message": {"raw": "encoded_message"}}

    message_id = gmail.create_draft(
        message=message,
        user_id="me",
        delegated_user_email="delegated_user_email",
    )

    scopes = [
        "https://www.googleapis.com/auth/gmail.compose",
        "https://www.googleapis.com/auth/gmail.modify",
    ]

    mock_execute_google_api_call.assert_called_once_with(
        service_name="gmail",
        version="v1",
        resource_path="users.drafts",
        method="create",
        scopes=scopes,
        delegated_user_email="delegated_user_email",
        userId="me",
        body=message,
    )

    assert message_id == "message_id"
