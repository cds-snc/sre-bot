"""Unit tests for the google_docs module."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from googleapiclient.errors import HttpError

from integrations.google_workspace import client as google_client
from integrations.google_workspace import google_docs

DOCS_SCOPES = ["https://www.googleapis.com/auth/documents"]


def _http_error(status: int) -> HttpError:
    class FakeResp(dict):
        def __init__(self) -> None:
            super().__init__()
            self.status = status
            self.reason = "boom"

    return HttpError(resp=FakeResp(), content=b"{}")


@pytest.fixture
def docs_client(monkeypatch):
    """Patch the Docs service factory and expose the mocked stub-typed Resource chain."""
    if not hasattr(google_client, "get_docs_service"):
        pytest.fail("integrations.google_workspace.client.get_docs_service is not implemented")

    service = MagicMock()
    factory = MagicMock(return_value=service)
    monkeypatch.setattr(google_client, "get_docs_service", factory)
    if hasattr(google_docs, "get_docs_service"):
        monkeypatch.setattr(google_docs, "get_docs_service", factory)
    return SimpleNamespace(factory=factory, service=service)


def test_create_returns_result(docs_client):
    create_call = docs_client.service.documents.return_value.create
    create_call.return_value.execute.return_value = {
        "documentId": "test_document_id",
        "title": "test_document",
        "body": {"content": [{}]},
        "headers": {},
    }

    result = google_docs.create("test_document")

    docs_client.factory.assert_called_once_with(scopes=DOCS_SCOPES, delegated_user_email=None)
    create_call.assert_called_once_with(body={"title": "test_document"})
    assert result == {
        "documentId": "test_document_id",
        "title": "test_document",
        "body": {"content": [{}]},
        "headers": {},
    }


def test_create_passes_delegated_user_email(docs_client):
    docs_client.service.documents.return_value.create.return_value.execute.return_value = {"documentId": "test_document_id"}

    google_docs.create("test_document", delegated_user_email="custom@example.com")

    docs_client.factory.assert_called_once_with(scopes=DOCS_SCOPES, delegated_user_email="custom@example.com")


def test_create_propagates_http_error(docs_client):
    error = _http_error(429)
    docs_client.service.documents.return_value.create.return_value.execute.side_effect = error

    with pytest.raises(HttpError) as exc_info:
        google_docs.create("test_document")

    assert exc_info.value is error


def test_batch_update_with_valid_requests_succeeds(docs_client):
    requests = [
        {"createHeader": {"type": "DEFAULT", "sectionBreakLocation": {"index": 1}}},
        {"insertText": {"location": {"index": 2}, "text": "Hello world"}},
        {"insertText": {"location": {"index": 3}, "text": "Foo"}},
    ]
    batch_update_call = docs_client.service.documents.return_value.batchUpdate
    batch_update_call.return_value.execute.return_value = {"documentId": "test_document_id", "replies": []}

    result = google_docs.batch_update("test_document_id", requests)

    docs_client.factory.assert_called_once_with(scopes=DOCS_SCOPES, delegated_user_email=None)
    batch_update_call.assert_called_once_with(documentId="test_document_id", body={"requests": requests})
    assert result == {"documentId": "test_document_id", "replies": []}


def test_batch_update_passes_delegated_user_email(docs_client):
    docs_client.service.documents.return_value.batchUpdate.return_value.execute.return_value = {}

    google_docs.batch_update("test_document_id", [], delegated_user_email="custom@example.com")

    docs_client.factory.assert_called_once_with(scopes=DOCS_SCOPES, delegated_user_email="custom@example.com")


def test_batch_update_propagates_http_error(docs_client):
    error = _http_error(429)
    docs_client.service.documents.return_value.batchUpdate.return_value.execute.side_effect = error

    with pytest.raises(HttpError) as exc_info:
        google_docs.batch_update("test_document_id", [])

    assert exc_info.value is error


def test_get_returns_document_resource(docs_client):
    get_call = docs_client.service.documents.return_value.get
    get_call.return_value.execute.return_value = {
        "documentId": "test_document_id",
        "title": "test_document",
        "body": {"content": [{}]},
        "documentStyle": {},
        "namedStyles": {},
        "revisionId": "test_revision_id",
        "suggestionsViewMode": "test_suggestions_view_mode",
        "inlineObjects": {},
        "lists": {},
    }

    document = google_docs.get_document("test_document_id")

    assert document == get_call.return_value.execute.return_value
    docs_client.factory.assert_called_once_with(scopes=DOCS_SCOPES, delegated_user_email=None)
    get_call.assert_called_once_with(documentId="test_document_id")


def test_get_document_passes_delegated_user_email(docs_client):
    docs_client.service.documents.return_value.get.return_value.execute.return_value = {}

    google_docs.get_document("test_document_id", delegated_user_email="custom@example.com")

    docs_client.factory.assert_called_once_with(scopes=DOCS_SCOPES, delegated_user_email="custom@example.com")


def test_get_document_propagates_classified_http_error(docs_client):
    error = _http_error(404)
    docs_client.service.documents.return_value.get.return_value.execute.side_effect = error

    with pytest.raises(HttpError) as exc_info:
        google_docs.get_document("test_document_id")

    assert exc_info.value is error


def test_get_document_propagates_unmapped_http_error(docs_client):
    error = _http_error(418)
    docs_client.service.documents.return_value.get.return_value.execute.side_effect = error

    with pytest.raises(HttpError) as exc_info:
        google_docs.get_document("test_document_id")

    assert exc_info.value is error


def test_get_document_propagates_non_http_error(docs_client):
    error = RuntimeError("boom")
    docs_client.service.documents.return_value.get.return_value.execute.side_effect = error

    with pytest.raises(RuntimeError) as exc_info:
        google_docs.get_document("test_document_id")

    assert exc_info.value is error


def test_google_docs_does_not_use_legacy_dispatcher():
    assert not hasattr(google_docs, "google_service")


def test_extract_googe_doc_id_valid_google_docs_url():
    url = "https://docs.google.com/document/d/1aBcD_efGHI/edit"
    assert google_docs.extract_google_doc_id(url) == "1aBcD_efGHI"


def test_extract_googe_doc_id_oogle_docs_url_with_parameters():
    url = "https://docs.google.com/document/d/1aBcD_efGHI/edit?usp=sharing"
    assert google_docs.extract_google_doc_id(url) == "1aBcD_efGHI"


def test_extract_googe_doc_id_non_google_docs_url():
    url = "https://www.example.com/page/d/1aBcD_efGHI/other"
    assert google_docs.extract_google_doc_id(url) is None


def test_extract_googe_doc_id_invalid_url_format():
    url = "https://docs.google.com/document/1aBcD_efGHI"
    assert google_docs.extract_google_doc_id(url) is None


def test_extract_googe_doc_id_empty_string():
    assert google_docs.extract_google_doc_id("") is None


def test_extract_googe_doc_id_none_input():
    assert google_docs.extract_google_doc_id(None) is None
