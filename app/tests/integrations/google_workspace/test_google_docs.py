from unittest.mock import patch
from integrations.google_workspace import google_docs


@patch("integrations.google_workspace.google_docs.SCOPES", ["tests", "scopes"])
@patch(
    "integrations.google_workspace.google_docs.google_service.execute_google_api_call"
)
def test_create_returns_result(execute_google_api_call_mock):
    # Mock the return value of execute_google_api_call
    execute_google_api_call_mock.return_value = {
        "documentId": "test_document_id",
        "title": "test_document",
        "body": {"content": [{}]},
        "headers": {},
    }

    # Call the create function
    result = google_docs.create("test_document")

    # Check that the create function returns the correct document id

    # Check that execute_google_api_call was called with the correct arguments
    execute_google_api_call_mock.assert_called_once_with(
        "docs",
        "v1",
        "documents",
        "create",
        scopes=["tests", "scopes"],
        body={"title": "test_document"},
    )

    assert result == {
        "documentId": "test_document_id",
        "title": "test_document",
        "body": {"content": [{}]},
        "headers": {},
    }


@patch("integrations.google_workspace.google_docs.SCOPES", ["tests", "scopes"])
@patch(
    "integrations.google_workspace.google_docs.google_service.execute_google_api_call"
)
def test_batch_update_with_valid_requests_succeeds(execute_google_api_call_mock):
    requests = [
        {"createHeader": {"type": "DEFAULT", "sectionBreakLocation": {"index": 1}}},
        {"insertText": {"location": {"index": 2}, "text": "Hello world"}},
        {"insertText": {"location": {"index": 3}, "text": "Foo"}},
    ]

    google_docs.batch_update("test_document_id", requests)

    # Check that execute_google_api_call was called with the correct arguments
    execute_google_api_call_mock.assert_called_once_with(
        "docs",
        "v1",
        "documents",
        "batchUpdate",
        scopes=["tests", "scopes"],
        documentId="test_document_id",
        body={"requests": requests},
    )


@patch("integrations.google_workspace.google_docs.SCOPES", ["tests", "scopes"])
@patch(
    "integrations.google_workspace.google_docs.google_service.execute_google_api_call"
)
def test_get_returns_document_resource(execute_google_api_call_mock):
    # Mock the return value of execute_google_api_call
    execute_google_api_call_mock.return_value = {
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

    # Check that the get function returns the correct document
    assert document == execute_google_api_call_mock.return_value

    # Check that execute_google_api_call was called with the correct arguments
    execute_google_api_call_mock.assert_called_once_with(
        "docs",
        "v1",
        "documents",
        "get",
        scopes=["tests", "scopes"],
        documentId="test_document_id",
    )


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
