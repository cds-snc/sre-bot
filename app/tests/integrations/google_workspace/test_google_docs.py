"""Unit tests for google_docs module."""
from unittest.mock import patch

import integrations.google_workspace.google_docs as google_docs


@patch("integrations.google_workspace.google_docs.get_google_service")
def test_create_returns_document_id(get_google_service_mock):
    # the api states: Creates a blank document using the title given in the request. Other fields in the request, including any provided content, are ignored.
    get_google_service_mock.return_value.documents.return_value.create.return_value.execute.return_value = {
        "documentId": "test_document_id",
        "title": "test_document",
        "body": {"content": [{}]},
        "headers": {},
    }
    assert google_docs.create("test_document") == "test_document_id"


@patch("integrations.google_workspace.google_docs.get_google_service")
def test_batch_update_with_valid_requests_succeeds(get_google_service_mock):
    get_google_service_mock.return_value.documents.return_value.batchUpdate.return_value.execute.return_value = {
        "responses": [{"headerId": "test_header_id"}, {}, {}]
    }

    requests = [
        {"createHeader": {"type": "DEFAULT", "sectionBreakLocation": {"index": 1}}},
        {"insertText": {"location": {"index": 2}, "text": "Hello world"}},
        {"insertText": {"location": {"index": 3}, "text": "Foo"}},
    ]

    assert google_docs.batch_update("test_document_id", requests) is None
    get_google_service_mock.return_value.documents.return_value.batchUpdate.assert_called_once_with(
        documentId="test_document_id", body={"requests": requests}
    )


@patch("integrations.google_workspace.google_docs.get_google_service")
def test_get_returns_document_resource(get_google_service_mock):
    get_google_service_mock.return_value.documents.return_value.get.return_value.execute.return_value = {
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

    document = google_docs.get("test_document_id")
    assert document["documentId"] == "test_document_id"
    assert document["title"] == "test_document"
    assert document["body"] == {"content": [{}]}
