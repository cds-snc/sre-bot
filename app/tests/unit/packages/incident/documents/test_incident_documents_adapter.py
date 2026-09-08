from unittest.mock import MagicMock, Mock, patch

import pytest
from googleapiclient.errors import HttpError

from packages.incident.documents.adapters import google_docs


def _http_error(status: int = 403, message: str = "forbidden") -> HttpError:
    resp = Mock()
    resp.status = status
    return HttpError(resp=resp, content=f'{{"error":{{"message":"{message}"}}}}'.encode())


@patch("packages.incident.documents.adapters.google_docs.get_docs_service")
def test_replace_placeholders_success(mock_get_docs_service):
    mock_service = MagicMock()
    mock_get_docs_service.return_value = mock_service
    mock_service.documents.return_value.batchUpdate.return_value = {"replies": [{"replaceAllText": {"occurrencesChanged": 2}}]}

    result = google_docs.replace_placeholders(
        "document-id",
        {"{{status}}": "Closed", "{{team}}": "Platform"},
        match_case=True,
    )

    assert result is True
    mock_service.documents.return_value.batchUpdate.assert_called_once()


@patch("packages.incident.documents.adapters.google_docs.get_docs_service")
def test_fetch_document_content_success(mock_get_docs_service):
    mock_service = MagicMock()
    mock_get_docs_service.return_value = mock_service
    mock_service.documents.return_value.get.return_value.execute.return_value = {
        "body": {"content": [{"paragraph": {"elements": [{"textRun": {"content": "hello"}}]}}]}
    }

    result = google_docs.fetch_document_content("document-id")

    assert result == [{"paragraph": {"elements": [{"textRun": {"content": "hello"}}]}}]
    mock_service.documents.return_value.get.assert_called_once_with(documentId="document-id")


@patch("packages.incident.documents.adapters.google_docs.get_docs_service")
def test_apply_document_edits_success(mock_get_docs_service):
    mock_service = MagicMock()
    mock_get_docs_service.return_value = mock_service
    mock_service.documents.return_value.batchUpdate.return_value.execute.return_value = {"status": "ok"}

    result = google_docs.apply_document_edits("document-id", [{"insertText": {"text": "hello"}}])

    assert result == {"status": "ok"}
    mock_service.documents.return_value.batchUpdate.assert_called_once()


@patch("packages.incident.documents.adapters.google_docs.get_docs_service")
def test_replace_placeholders_degrades_on_classified_http_error(mock_get_docs_service):
    mock_service = MagicMock()
    mock_get_docs_service.return_value = mock_service
    mock_service.documents.return_value.batchUpdate.return_value.execute.side_effect = _http_error(403)

    result = google_docs.replace_placeholders("document-id", {"{{status}}": "Closed"})

    assert result is False


@patch("packages.incident.documents.adapters.google_docs.get_docs_service")
def test_fetch_document_content_degrades_on_classified_http_error(mock_get_docs_service):
    mock_service = MagicMock()
    mock_get_docs_service.return_value = mock_service
    mock_service.documents.return_value.get.return_value.execute.side_effect = _http_error(404)

    result = google_docs.fetch_document_content("document-id")

    assert result is None


@patch("packages.incident.documents.adapters.google_docs.get_docs_service")
def test_apply_document_edits_degrades_on_classified_http_error(mock_get_docs_service):
    mock_service = MagicMock()
    mock_get_docs_service.return_value = mock_service
    mock_service.documents.return_value.batchUpdate.return_value.execute.side_effect = _http_error(429)

    result = google_docs.apply_document_edits("document-id", [{"insertText": {"text": "hello"}}])

    assert result == {}


@patch("packages.incident.documents.adapters.google_docs.get_docs_service")
def test_adapter_propagates_unmapped_exception(mock_get_docs_service):
    mock_service = MagicMock()
    mock_get_docs_service.return_value = mock_service
    mock_service.documents.return_value.get.return_value.execute.side_effect = RuntimeError("unexpected")

    with pytest.raises(RuntimeError, match="unexpected"):
        google_docs.fetch_document_content("document-id")
