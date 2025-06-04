""" "Unit tests for the Google Docs API."""

# import unittest
from unittest.mock import MagicMock, patch

import pytest

# from integrations.google_next.docs import docs.GoogleDocs
from integrations.google_next import docs


@pytest.fixture
def mock_service():
    with patch(
        "integrations.google_next.docs.get_google_service"
    ) as mock_get_google_service:
        mock_get_google_service.return_value = MagicMock()
        yield mock_get_google_service


@pytest.fixture
def google_docs(mock_service):
    # Default usage: no arguments
    return docs.GoogleDocs()


@pytest.fixture
def google_docs_with_email(mock_service):
    scopes = ["https://www.googleapis.com/auth/documents"]
    delegated_email = "email@test.com"
    return docs.GoogleDocs(scopes, delegated_email)


@pytest.fixture
def google_docs_with_scopes(mock_service):
    scopes = ["https://www.googleapis.com/auth/documents.readonly"]
    return docs.GoogleDocs(scopes)


class TestGoogleDocs:
    @pytest.fixture(autouse=True)
    def setup(self, google_docs: docs.GoogleDocs):
        self.google_docs = google_docs

    def test_init_uses_defaults(self):
        """Test initialization without scopes and service raises ValueError."""
        assert self.google_docs.scopes == docs.DEFAULT_SCOPES
        assert self.google_docs.delegated_email is None

    @patch("integrations.google_next.docs.get_google_service")
    def test_init_with_delegated_email_scopes_and_service(self, mock_get_google_service):
        """Test initialization with delegated email and service."""
        mock_get_google_service.return_value = MagicMock()
        google_docs = docs.GoogleDocs(
            scopes=["https://www.googleapis.com/auth/documents"],
            delegated_email="email@test.com",
            service=mock_get_google_service.return_value,
        )
        assert google_docs.scopes == ["https://www.googleapis.com/auth/documents"]
        assert google_docs.delegated_email == "email@test.com"
        assert google_docs.service == mock_get_google_service.return_value

    @patch("integrations.google_next.docs.get_google_service")
    def test_get_docs_service(self, mock_get_google_service):
        """Test get_docs_service returns a service."""
        mock_get_google_service.return_value = MagicMock()
        service = self.google_docs._get_docs_service()
        assert service is not None
        mock_get_google_service.assert_called_once_with(
            "docs",
            "v1",
            self.google_docs.scopes,
            self.google_docs.delegated_email,
        )

    @patch("integrations.google_next.docs.execute_google_api_call")
    def test_create(self, mock_execute_google_api_call):
        """Test create calls execute_google_api_call with correct arguments."""
        title = "test_document"
        body = {"title": title}
        self.google_docs.create(title)
        mock_execute_google_api_call.assert_called_once_with(
            self.google_docs.service,
            "documents",
            "create",
            body=body,
        )

    @patch("integrations.google_next.docs.execute_google_api_call")
    def test_create_handles_kwargs(self, mock_execute_google_api_call):
        """Test create handles additional parameters."""
        title = "test_document"
        body = {"title": title, "key": "value"}
        self.google_docs.create(title, body={"key": "value"}, something="else")
        mock_execute_google_api_call.assert_called_once_with(
            self.google_docs.service,
            "documents",
            "create",
            body=body,
            something="else",
        )

    @patch("integrations.google_next.docs.execute_google_api_call")
    def test_batch_update(
        self,
        mock_execute_google_api_call,
    ):
        """Test batch_update calls execute_google_api_call with correct arguments."""
        document_id = "test_document_id"
        requests = [
            {"createHeader": {"type": "DEFAULT", "sectionBreakLocation": {"index": 1}}},
            {"insertText": {"location": {"index": 2}, "text": "Hello world"}},
            {"insertText": {"location": {"index": 3}, "text": "Foo"}},
        ]
        self.google_docs.batch_update(document_id, requests, something="else")
        mock_execute_google_api_call.assert_called_once_with(
            self.google_docs.service,
            "documents",
            "batchUpdate",
            documentId=document_id,
            body={"requests": requests},
            something="else",
        )

    @patch("integrations.google_next.docs.execute_google_api_call")
    def test_get_document(
        self,
        mock_execute_google_api_call,
    ):
        """Test get_document calls execute_google_api_call with correct arguments."""
        document_id = "test_document_id"
        self.google_docs.get_document(document_id, something="else")
        mock_execute_google_api_call.assert_called_once_with(
            self.google_docs.service,
            "documents",
            "get",
            documentId=document_id,
            something="else",
        )


def test_extract_googe_doc_id_valid_google_docs_url():
    url = "https://docs.google.com/document/d/1aBcD_efGHI/edit"
    assert docs.extract_google_doc_id(url) == "1aBcD_efGHI"


def test_extract_googe_doc_id_oogle_docs_url_with_parameters():
    url = "https://docs.google.com/document/d/1aBcD_efGHI/edit?usp=sharing"
    assert docs.extract_google_doc_id(url) == "1aBcD_efGHI"


def test_extract_googe_doc_id_non_google_docs_url():
    url = "https://www.example.com/page/d/1aBcD_efGHI/other"
    assert docs.extract_google_doc_id(url) is None


def test_extract_googe_doc_id_invalid_url_format():
    url = "https://docs.google.com/document/1aBcD_efGHI"
    assert docs.extract_google_doc_id(url) is None


def test_extract_googe_doc_id_empty_string():
    assert docs.extract_google_doc_id("") is None


def test_extract_googe_doc_id_none_input():
    assert docs.extract_google_doc_id(None) is None
