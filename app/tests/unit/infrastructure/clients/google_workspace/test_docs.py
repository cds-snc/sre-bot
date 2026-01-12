"""Unit tests for Google Docs client."""

from unittest.mock import MagicMock


from infrastructure.clients.google_workspace.docs import DocsClient


class TestDocumentOperations:
    """Test document operations (get, create, batch_update)."""

    def test_get_document_success(self, mock_session_provider):
        """Test getting a document successfully."""
        # Setup
        client = DocsClient(mock_session_provider)
        mock_service = mock_session_provider.get_service.return_value
        mock_service.documents().get().execute.return_value = {
            "documentId": "doc123",
            "title": "Test Document",
            "body": {"content": []},
        }

        # Execute
        result = client.get_document("doc123")

        # Assert
        assert result.is_success
        assert result.data["documentId"] == "doc123"
        assert result.data["title"] == "Test Document"
        mock_service.documents().get.assert_called()

    def test_get_document_with_delegation(self, mock_session_provider):
        """Test getting a document with delegated email."""
        # Setup
        client = DocsClient(mock_session_provider)
        mock_service = mock_session_provider.get_service.return_value
        mock_service.documents().get().execute.return_value = {
            "documentId": "doc456",
            "title": "Delegated Document",
        }

        # Execute
        result = client.get_document("doc456", delegated_email="user@example.com")

        # Assert
        assert result.is_success
        mock_session_provider.get_service.assert_called_with(
            service_name="docs",
            version="v1",
            scopes=["https://www.googleapis.com/auth/documents"],
            delegated_user_email="user@example.com",
        )

    def test_create_document_success(self, mock_session_provider):
        """Test creating a new document."""
        # Setup
        client = DocsClient(mock_session_provider)
        mock_service = mock_session_provider.get_service.return_value
        mock_service.documents().create().execute.return_value = {
            "documentId": "new_doc123",
            "title": "New Test Document",
        }

        # Execute
        result = client.create("New Test Document")

        # Assert
        assert result.is_success
        assert result.data["documentId"] == "new_doc123"
        assert result.data["title"] == "New Test Document"
        mock_service.documents().create.assert_called()

    def test_create_document_with_delegation(self, mock_session_provider):
        """Test creating a document with delegated email."""
        # Setup
        client = DocsClient(mock_session_provider)
        mock_service = mock_session_provider.get_service.return_value
        mock_service.documents().create().execute.return_value = {
            "documentId": "delegated_doc",
            "title": "Delegated Doc",
        }

        # Execute
        result = client.create("Delegated Doc", delegated_email="admin@example.com")

        # Assert
        assert result.is_success
        mock_session_provider.get_service.assert_called_with(
            service_name="docs",
            version="v1",
            scopes=["https://www.googleapis.com/auth/documents"],
            delegated_user_email="admin@example.com",
        )

    def test_batch_update_success(self, mock_session_provider):
        """Test batch updating a document."""
        # Setup
        client = DocsClient(mock_session_provider)
        mock_service = mock_session_provider.get_service.return_value
        mock_service.documents().batchUpdate().execute.return_value = {
            "documentId": "doc123",
            "replies": [{"insertText": {}}],
        }

        requests = [{"insertText": {"location": {"index": 1}, "text": "Hello, World!"}}]

        # Execute
        result = client.batch_update("doc123", requests)

        # Assert
        assert result.is_success
        assert result.data["documentId"] == "doc123"
        assert "replies" in result.data
        mock_service.documents().batchUpdate.assert_called()

    def test_batch_update_multiple_requests(self, mock_session_provider):
        """Test batch updating with multiple requests."""
        # Setup
        client = DocsClient(mock_session_provider)
        mock_service = mock_session_provider.get_service.return_value
        mock_service.documents().batchUpdate().execute.return_value = {
            "documentId": "doc456",
            "replies": [{}, {}, {}],
        }

        requests = [
            {"insertText": {"location": {"index": 1}, "text": "Line 1"}},
            {"insertText": {"location": {"index": 7}, "text": "\n"}},
            {"insertText": {"location": {"index": 8}, "text": "Line 2"}},
        ]

        # Execute
        result = client.batch_update("doc456", requests)

        # Assert
        assert result.is_success
        assert len(result.data["replies"]) == 3

    def test_batch_update_with_delegation(self, mock_session_provider):
        """Test batch updating with delegated email."""
        # Setup
        client = DocsClient(mock_session_provider)
        mock_service = mock_session_provider.get_service.return_value
        mock_service.documents().batchUpdate().execute.return_value = {
            "documentId": "doc789",
        }

        requests = [{"insertText": {"location": {"index": 1}, "text": "Test"}}]

        # Execute
        result = client.batch_update(
            "doc789", requests, delegated_email="service@example.com"
        )

        # Assert
        assert result.is_success
        mock_session_provider.get_service.assert_called_with(
            service_name="docs",
            version="v1",
            scopes=["https://www.googleapis.com/auth/documents"],
            delegated_user_email="service@example.com",
        )


class TestUtilityFunctions:
    """Test utility functions (extract_google_doc_id)."""

    def test_extract_google_doc_id_success(self):
        """Test extracting document ID from valid URL."""
        url = "https://docs.google.com/document/d/1ABC123xyz-_/edit"
        doc_id = DocsClient.extract_google_doc_id(url)
        assert doc_id == "1ABC123xyz-_"

    def test_extract_google_doc_id_different_formats(self):
        """Test extracting document ID from various URL formats."""
        urls = [
            "https://docs.google.com/document/d/1ABC123/edit",
            "https://docs.google.com/document/d/xyz-456_789/view",
            "https://docs.google.com/document/d/test_doc-123/",
        ]
        expected_ids = ["1ABC123", "xyz-456_789", "test_doc-123"]

        for url, expected_id in zip(urls, expected_ids):
            doc_id = DocsClient.extract_google_doc_id(url)
            assert doc_id == expected_id

    def test_extract_google_doc_id_invalid_url(self):
        """Test extracting document ID from invalid URL returns None."""
        invalid_urls = [
            "https://example.com/document/123",
            "not a url",
            "https://docs.google.com/spreadsheets/d/123/",
        ]

        for url in invalid_urls:
            doc_id = DocsClient.extract_google_doc_id(url)
            assert doc_id is None

    def test_extract_google_doc_id_empty_string(self):
        """Test extracting document ID from empty string returns None."""
        doc_id = DocsClient.extract_google_doc_id("")
        assert doc_id is None

    def test_extract_google_doc_id_none(self):
        """Test extracting document ID from None returns None."""
        doc_id = DocsClient.extract_google_doc_id(None)
        assert doc_id is None


class TestErrorHandling:
    """Test error handling and OperationResult propagation."""

    def test_api_call_propagates_operation_result(self, mock_session_provider):
        """Test that executor errors are properly propagated as OperationResult."""
        # Setup
        client = DocsClient(mock_session_provider)
        mock_service = mock_session_provider.get_service.return_value

        # Simulate API error by having execute() raise an exception
        from googleapiclient.errors import HttpError

        mock_service.documents().get().execute.side_effect = HttpError(
            resp=MagicMock(status=404), content=b"Not found"
        )

        # Execute
        result = client.get_document("nonexistent_doc")

        # Assert - executor handles the error and returns OperationResult
        assert not result.is_success
        # The actual error message depends on executor implementation
