from unittest.mock import patch

import pytest
from modules.incident import incident_document


@patch("modules.incident.incident_document.google_docs")
def test_update_incident_document_status_changes_occurred(google_docs_mock):
    document_id = "test_document_id"
    new_status = "In Progress"
    google_docs_mock.batch_update.return_value = {
        "replies": [
            {"replaceAllText": {"occurrencesChanged": 1}},
            {"replaceAllText": {}},
            {"replaceAllText": {}},
            {"replaceAllText": {}},
        ]
    }

    response = incident_document.update_incident_document_status(
        document_id, new_status
    )
    assert response is True

    expected_changes = [
        {
            "replaceAllText": {
                "containsText": {"text": "Status: Open", "matchCase": "false"},
                "replaceText": f"Status: {new_status}",
            }
        },
        {
            "replaceAllText": {
                "containsText": {
                    "text": "Status: Ready to be Reviewed",
                    "matchCase": "false",
                },
                "replaceText": f"Status: {new_status}",
            }
        },
        {
            "replaceAllText": {
                "containsText": {"text": "Status: Reviewed", "matchCase": "false"},
                "replaceText": f"Status: {new_status}",
            }
        },
        {
            "replaceAllText": {
                "containsText": {"text": "Status: Closed", "matchCase": "false"},
                "replaceText": f"Status: {new_status}",
            }
        },
    ]

    google_docs_mock.batch_update.assert_called_once_with(document_id, expected_changes)


@patch("modules.incident.incident_document.google_docs")
def test_update_incident_document_status_no_changes_occurred(google_docs_mock):
    document_id = "test_document_id"
    new_status = "In Progress"
    google_docs_mock.batch_update.return_value = {
        "replies": [
            {"replaceAllText": {}},
            {"replaceAllText": {}},
            {"replaceAllText": {}},
            {"replaceAllText": {}},
        ]
    }

    response = incident_document.update_incident_document_status(
        document_id, new_status
    )
    assert response is False

    expected_changes = [
        {
            "replaceAllText": {
                "containsText": {"text": "Status: Open", "matchCase": "false"},
                "replaceText": f"Status: {new_status}",
            }
        },
        {
            "replaceAllText": {
                "containsText": {
                    "text": "Status: Ready to be Reviewed",
                    "matchCase": "false",
                },
                "replaceText": f"Status: {new_status}",
            }
        },
        {
            "replaceAllText": {
                "containsText": {"text": "Status: Reviewed", "matchCase": "false"},
                "replaceText": f"Status: {new_status}",
            }
        },
        {
            "replaceAllText": {
                "containsText": {"text": "Status: Closed", "matchCase": "false"},
                "replaceText": f"Status: {new_status}",
            }
        },
    ]

    google_docs_mock.batch_update.assert_called_once_with(document_id, expected_changes)


def test_update_incident_document_status_invalid_status():
    document_id = "test_document_id"
    invalid_status = "Invalid Status"

    with pytest.raises(ValueError, match=f"Invalid status: {invalid_status}"):
        incident_document.update_incident_document_status(document_id, invalid_status)
