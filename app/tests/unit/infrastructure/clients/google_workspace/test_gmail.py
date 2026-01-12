"""Unit tests for Google Gmail client."""

from unittest.mock import MagicMock


from infrastructure.clients.google_workspace.gmail import GmailClient


class TestEmailOperations:
    """Test email operations (send_email, create_draft)."""

    def test_send_email_success(self, mock_session_provider):
        """Test sending an email successfully."""
        # Setup
        client = GmailClient(mock_session_provider)
        mock_service = mock_session_provider.get_service.return_value
        mock_service.users().messages().send().execute.return_value = {
            "id": "msg123",
            "threadId": "thread456",
            "labelIds": ["SENT"],
        }

        # Execute
        result = client.send_email(
            subject="Test Email",
            body="Hello, World!",
            sender="bot@example.com",
            recipient="user@example.com",
        )

        # Assert
        assert result.is_success
        assert result.data["id"] == "msg123"
        assert result.data["threadId"] == "thread456"
        assert "SENT" in result.data["labelIds"]
        mock_service.users().messages().send.assert_called()

    def test_send_email_with_html_content(self, mock_session_provider):
        """Test sending an HTML email."""
        # Setup
        client = GmailClient(mock_session_provider)
        mock_service = mock_session_provider.get_service.return_value
        mock_service.users().messages().send().execute.return_value = {
            "id": "msg_html",
            "threadId": "thread_html",
        }

        # Execute
        result = client.send_email(
            subject="HTML Email",
            body="<h1>Hello</h1>",
            sender="bot@example.com",
            recipient="user@example.com",
            content_type="html",
        )

        # Assert
        assert result.is_success
        assert result.data["id"] == "msg_html"

    def test_send_email_with_delegation(self, mock_session_provider):
        """Test sending email with delegated authentication."""
        # Setup
        client = GmailClient(mock_session_provider)
        mock_service = mock_session_provider.get_service.return_value
        mock_service.users().messages().send().execute.return_value = {
            "id": "delegated_msg",
            "threadId": "delegated_thread",
        }

        # Execute
        result = client.send_email(
            subject="Delegated Email",
            body="Test body",
            sender="bot@example.com",
            recipient="user@example.com",
            delegated_email="admin@example.com",
        )

        # Assert
        assert result.is_success
        mock_session_provider.get_service.assert_called_with(
            service_name="gmail",
            version="v1",
            scopes=["https://www.googleapis.com/auth/gmail.send"],
            delegated_user_email="admin@example.com",
        )

    def test_send_email_with_custom_user_id(self, mock_session_provider):
        """Test sending email with custom user ID."""
        # Setup
        client = GmailClient(mock_session_provider)
        mock_service = mock_session_provider.get_service.return_value
        mock_service.users().messages().send().execute.return_value = {
            "id": "custom_user_msg",
        }

        # Execute
        result = client.send_email(
            subject="Custom User Email",
            body="Test",
            sender="bot@example.com",
            recipient="user@example.com",
            user_id="custom_user@example.com",
        )

        # Assert
        assert result.is_success

    def test_create_draft_success(self, mock_session_provider):
        """Test creating a draft successfully."""
        # Setup
        client = GmailClient(mock_session_provider)
        mock_service = mock_session_provider.get_service.return_value
        mock_service.users().drafts().create().execute.return_value = {
            "id": "draft123",
            "message": {
                "id": "msg789",
                "threadId": "thread456",
                "labelIds": ["DRAFT"],
            },
        }

        # Execute
        result = client.create_draft(
            subject="Draft Email",
            body="Draft content",
            sender="bot@example.com",
            recipient="user@example.com",
        )

        # Assert
        assert result.is_success
        assert result.data["id"] == "draft123"
        assert result.data["message"]["id"] == "msg789"
        assert "DRAFT" in result.data["message"]["labelIds"]
        mock_service.users().drafts().create.assert_called()

    def test_create_draft_with_html(self, mock_session_provider):
        """Test creating a draft with HTML content."""
        # Setup
        client = GmailClient(mock_session_provider)
        mock_service = mock_session_provider.get_service.return_value
        mock_service.users().drafts().create().execute.return_value = {
            "id": "draft_html",
            "message": {"id": "msg_html"},
        }

        # Execute
        result = client.create_draft(
            subject="HTML Draft",
            body="<p>Draft content</p>",
            sender="bot@example.com",
            recipient="user@example.com",
            content_type="html",
        )

        # Assert
        assert result.is_success
        assert result.data["id"] == "draft_html"

    def test_create_draft_with_delegation(self, mock_session_provider):
        """Test creating draft with delegated authentication."""
        # Setup
        client = GmailClient(mock_session_provider)
        mock_service = mock_session_provider.get_service.return_value
        mock_service.users().drafts().create().execute.return_value = {
            "id": "delegated_draft",
        }

        # Execute
        result = client.create_draft(
            subject="Delegated Draft",
            body="Test",
            sender="bot@example.com",
            recipient="user@example.com",
            delegated_email="admin@example.com",
        )

        # Assert
        assert result.is_success
        mock_session_provider.get_service.assert_called_with(
            service_name="gmail",
            version="v1",
            scopes=[
                "https://www.googleapis.com/auth/gmail.compose",
                "https://www.googleapis.com/auth/gmail.modify",
            ],
            delegated_user_email="admin@example.com",
        )


class TestMessageOperations:
    """Test message retrieval operations (get_message, list_messages)."""

    def test_get_message_success(self, mock_session_provider):
        """Test getting a message successfully."""
        # Setup
        client = GmailClient(mock_session_provider)
        mock_service = mock_session_provider.get_service.return_value
        mock_service.users().messages().get().execute.return_value = {
            "id": "msg123",
            "threadId": "thread456",
            "snippet": "Email preview text...",
            "payload": {"headers": []},
        }

        # Execute
        result = client.get_message("msg123")

        # Assert
        assert result.is_success
        assert result.data["id"] == "msg123"
        assert result.data["snippet"] == "Email preview text..."
        mock_service.users().messages().get.assert_called()

    def test_get_message_with_format(self, mock_session_provider):
        """Test getting message with specific format."""
        # Setup
        client = GmailClient(mock_session_provider)
        mock_service = mock_session_provider.get_service.return_value
        mock_service.users().messages().get().execute.return_value = {
            "id": "msg_metadata",
        }

        # Execute
        result = client.get_message("msg_metadata", format="metadata")

        # Assert
        assert result.is_success

    def test_get_message_with_delegation(self, mock_session_provider):
        """Test getting message with delegated authentication."""
        # Setup
        client = GmailClient(mock_session_provider)
        mock_service = mock_session_provider.get_service.return_value
        mock_service.users().messages().get().execute.return_value = {"id": "msg_del"}

        # Execute
        result = client.get_message("msg_del", delegated_email="delegate@example.com")

        # Assert
        assert result.is_success
        mock_session_provider.get_service.assert_called_with(
            service_name="gmail",
            version="v1",
            scopes=["https://www.googleapis.com/auth/gmail.readonly"],
            delegated_user_email="delegate@example.com",
        )

    def test_list_messages_success(self, mock_session_provider):
        """Test listing messages successfully."""
        # Setup
        client = GmailClient(mock_session_provider)
        mock_service = mock_session_provider.get_service.return_value
        mock_service.users().messages().list().execute.return_value = {
            "messages": [
                {"id": "msg1", "threadId": "thread1"},
                {"id": "msg2", "threadId": "thread2"},
            ],
            "resultSizeEstimate": 2,
        }

        # Execute
        result = client.list_messages()

        # Assert
        assert result.is_success
        assert len(result.data["messages"]) == 2
        assert result.data["messages"][0]["id"] == "msg1"
        mock_service.users().messages().list.assert_called()

    def test_list_messages_with_query(self, mock_session_provider):
        """Test listing messages with search query."""
        # Setup
        client = GmailClient(mock_session_provider)
        mock_service = mock_session_provider.get_service.return_value
        mock_service.users().messages().list().execute.return_value = {
            "messages": [{"id": "unread_msg"}],
        }

        # Execute
        result = client.list_messages(query="is:unread from:user@example.com")

        # Assert
        assert result.is_success

    def test_list_messages_with_label_ids(self, mock_session_provider):
        """Test listing messages filtered by labels."""
        # Setup
        client = GmailClient(mock_session_provider)
        mock_service = mock_session_provider.get_service.return_value
        mock_service.users().messages().list().execute.return_value = {
            "messages": [{"id": "inbox_msg"}],
        }

        # Execute
        result = client.list_messages(label_ids=["INBOX", "UNREAD"])

        # Assert
        assert result.is_success

    def test_list_messages_with_max_results(self, mock_session_provider):
        """Test listing messages with custom max results."""
        # Setup
        client = GmailClient(mock_session_provider)
        mock_service = mock_session_provider.get_service.return_value
        mock_service.users().messages().list().execute.return_value = {
            "messages": [],
        }

        # Execute
        result = client.list_messages(max_results=50)

        # Assert
        assert result.is_success

    def test_list_messages_with_delegation(self, mock_session_provider):
        """Test listing messages with delegated authentication."""
        # Setup
        client = GmailClient(mock_session_provider)
        mock_service = mock_session_provider.get_service.return_value
        mock_service.users().messages().list().execute.return_value = {
            "messages": [],
        }

        # Execute
        result = client.list_messages(delegated_email="admin@example.com")

        # Assert
        assert result.is_success
        mock_session_provider.get_service.assert_called_with(
            service_name="gmail",
            version="v1",
            scopes=["https://www.googleapis.com/auth/gmail.readonly"],
            delegated_user_email="admin@example.com",
        )


class TestUtilityFunctions:
    """Test utility functions (_create_mime_message)."""

    def test_create_mime_message_plain_text(self):
        """Test creating plain text MIME message."""
        encoded = GmailClient._create_mime_message(
            subject="Test Subject",
            body="Test Body",
            sender="sender@example.com",
            recipient="recipient@example.com",
            content_type="plain",
        )

        assert isinstance(encoded, str)
        assert len(encoded) > 0
        # Base64 encoded strings should only contain these characters
        assert all(
            c in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_="
            for c in encoded
        )

    def test_create_mime_message_html(self):
        """Test creating HTML MIME message."""
        encoded = GmailClient._create_mime_message(
            subject="HTML Test",
            body="<h1>Test</h1>",
            sender="sender@example.com",
            recipient="recipient@example.com",
            content_type="html",
        )

        assert isinstance(encoded, str)
        assert len(encoded) > 0


class TestErrorHandling:
    """Test error handling and OperationResult propagation."""

    def test_api_call_propagates_operation_result(self, mock_session_provider):
        """Test that executor errors are properly propagated as OperationResult."""
        # Setup
        client = GmailClient(mock_session_provider)
        mock_service = mock_session_provider.get_service.return_value

        # Simulate API error
        from googleapiclient.errors import HttpError

        mock_service.users().messages().get().execute.side_effect = HttpError(
            resp=MagicMock(status=404), content=b"Not found"
        )

        # Execute
        result = client.get_message("nonexistent_msg")

        # Assert - executor handles the error and returns OperationResult
        assert not result.is_success
